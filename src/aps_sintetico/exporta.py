"""Exportação: núcleo (CSV na ordem das FKs), staging no leiaute do LEDI (CSV), verdade
(Parquet) e manifesto com SHA-256.

Convenções dos CSV: UTF-8, separador vírgula, cabeçalho, booleano 1/0, nulo ``\\N``
(COPY ... CSV NULL '\\N' no PostgreSQL; LOAD DATA no MySQL), datas ISO 8601.
Datas da staging em milissegundos desde 1970 (LEDI), à meia-noite de Recife (UTC−3).

Chaves substitutas determinísticas: cada id é o posto (rank) da chave natural, de modo que a
carga direta e a rota staging → núcleo (sql/postgresql/06_staging_para_nucleo.sql) produzem
os mesmos ids e o gabarito vale para as duas:
  id_cidadao   ← ordem de COALESCE(cpf, 'CNS' || cns)
  id_domicilio ← ordem do uuid da FCDT · id_familia ← (uuid da FCDT, nº da família)
  id_microarea ← (ine, código) · id_atendimento ← (uuid da ficha, nº do atendimento)
  id_acao      ← (ine, data, tipo)
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import identificadores as I
from .atributos import BIT_CODIGO
from .dinamica import _d
from .rng import fluxo
from .territorio import CBO_ACS, CBO_ENFERMEIRO

NULO = r"\N"
IBGE_RECIFE = "2611606"
ORDEM_NUCLEO = ["setor_censitario", "microarea", "profissional", "lotacao", "acao_formativa", "domicilio",
                "familia", "cidadao", "cadastro_individual", "cadastro_deficiencia", "ficha_atendimento",
                "atendimento_individual", "atendimento_problema", "parametro", "controle_defeito"]
ORDEM_STG = ["malha_territorial", "profissional_lotacao", "fcdt", "fcdt_familia", "fci", "fai", "fai_problema"]


# ------------------------------------------------------------------ utilidades
def _ms(datas) -> np.ndarray:
    """Data (ou data-hora local) → milissegundos UTC (Recife = UTC−3), nulo preservado."""
    d = pd.to_datetime(pd.Series(datas))
    ms = (d - pd.Timestamp("1970-01-01")).dt.total_seconds() * 1000 + 3 * 3600 * 1000
    return ms.round().astype("Int64").values


def _b(x) -> pd.Series:
    return pd.Series(x).astype("boolean").astype("Int8")


def _cod(x) -> pd.Series:
    """Código inteiro com -1 → nulo."""
    s = pd.Series(np.asarray(x)).astype("Int64")
    return s.where(s >= 0)


def _data(x) -> pd.Series:
    return pd.Series(pd.to_datetime(pd.Series(x)).dt.strftime("%Y-%m-%d")).replace({"NaT": None})


def _rank(*cols) -> np.ndarray:
    df = pd.DataFrame({f"c{i}": np.asarray(c) for i, c in enumerate(cols)})
    ordem = df.sort_values(list(df.columns), kind="mergesort").index.values
    r = np.empty(len(df), dtype=np.int64)
    r[ordem] = np.arange(1, len(df) + 1)
    return r


def _grava(df: pd.DataFrame, caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(caminho, index=False, na_rep=NULO, lineterminator="\n", encoding="utf-8")


def _sha(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


# ------------------------------------------------------------------ montagem das tabelas
def monta_tabelas(cfg, mundo) -> dict[str, pd.DataFrame]:
    """Atribui ids e uuids e devolve as tabelas do núcleo (DataFrames prontos)."""
    rng = fluxo(cfg.semente, "exporta")
    pes, eq, dom, v, cid = mundo.pessoas, mundo.equipes, mundo.domicilios, mundo.versoes, mundo.cidadaos
    cnes_eq = eq.set_index("ine")["cnes"]
    T: dict[str, pd.DataFrame] = {}
    # território sintético e rede
    T["setor_censitario"] = mundo.setores[["cd_setor", "id_bairro"]].sort_values("cd_setor").reset_index(drop=True)
    mic = mundo.microareas.copy()
    mic["id_microarea"] = _rank(mic["ine"], mic["codigo_microarea"])
    T["microarea"] = mic[["id_microarea", "ine", "codigo_microarea"]].sort_values("id_microarea")
    id_mic = mic.set_index(["ine", "codigo_microarea"])["id_microarea"]
    lot = mundo.lotacoes
    T["profissional"] = lot[["cns_profissional", "nome_profissional"]].drop_duplicates("cns_profissional")
    T["lotacao"] = lot[["cns_profissional", "ine", "cbo"]]
    ac = mundo.acoes.copy()
    ac["id_acao"] = _rank(ac["ine"], ac["dt_acao"], ac["tipo_acao"])
    T["acao_formativa"] = ac.assign(dt_acao=_data(ac["dt_acao"]).values)[
        ["id_acao", "ine", "dt_acao", "tipo_acao", "tema"]].sort_values("id_acao")
    # domicílios e famílias (FCDT)
    d = dom[dom["cadastrado"]].copy().reset_index(drop=True)
    d["uuid"] = I.uuids_ledi(rng, cnes_eq.reindex(d["equipe"]).values)
    d["id_domicilio"] = _rank(d["uuid"])
    d["id_microarea"] = id_mic.reindex(list(zip(d["equipe"], d["microarea"]))).values
    d["ativo"] = ~d["saida_registrada"].fillna(False).astype(bool)
    T["domicilio"] = pd.DataFrame({"id_domicilio": d["id_domicilio"], "uuid_ficha": d["uuid"],
                                   "tipo_imovel": d["tipo_imovel"].astype(int), "cd_setor": d["setor"],
                                   "id_microarea": d["id_microarea"].astype("Int64").values, "fora_area": 0,
                                   "ativo": _b(d["ativo"].values).values}).sort_values("id_domicilio")
    f = d[(d["tipo_imovel"] == 1) & (d["n_mor"] > 0)].copy()
    f["id_familia"] = _rank(f["uuid"], np.ones(len(f)))
    dtc = _d(f["dt_cadastro"])
    desde = np.where(f["origem_hid"].values >= 0, _d(f["dt_chegada"]),
                     dtc - (rng.exponential(8 * 365.25, len(f))).astype(int))
    f["reside_desde"] = desde
    T["familia"] = pd.DataFrame({"id_familia": f["id_familia"], "id_domicilio": f["id_domicilio"],
                                 "renda_familiar": _cod(f["renda_cod"].fillna(-1).astype(int)).values,
                                 "num_membros": f["n_mor"].astype(int).clip(1, 999).values,
                                 "reside_desde": _data(f["reside_desde"]).values,
                                 "mudou_se": _b(f["saida_registrada"].fillna(False).values).values}
                                ).sort_values("id_familia")
    fam_por_hid = f.set_index("hid")["id_familia"]
    mundo.verdade["_d"] = d
    # cidadãos
    chave = np.where(pd.notna(cid["cpf"]), cid["cpf"].astype(object), "CNS" + cid["cns"].astype(str))
    cid["id_cidadao"] = _rank(chave)
    T["cidadao"] = pd.DataFrame({"id_cidadao": cid["id_cidadao"], "cpf": cid["cpf"], "cns": cid["cns"],
                                 "nome": cid["nome"], "dt_nascimento": _data(cid["dob"]).values,
                                 "sexo": cid["sexo"].astype(int),
                                 "id_familia": fam_por_hid.reindex(cid["hid_familia"]).astype("Int64").values}
                                ).sort_values("id_cidadao")
    # versões da FCI
    v["uuid"] = I.uuids_ledi(rng, cnes_eq.reindex(v["ine"]).values)
    primeira = v["uuid"].values[(v.index.values - v["n_versao"].values)]
    v["uuid_originadora"] = np.where(v["n_versao"].values > 0, primeira, None)
    v["id_cidadao"] = cid["id_cidadao"].values[v["cid"].values]
    tipo_eq = eq.set_index("ine")["tipo_equipe"].reindex(v["ine"]).values
    ecr = tipo_eq == 73
    acs = lot[lot["cbo"] == CBO_ACS].set_index(["ine", "microarea"])["cns_profissional"]
    enf = lot[lot["cbo"] == CBO_ENFERMEIRO].drop_duplicates("ine").set_index("ine")["cns_profissional"]
    terr = np.isin(tipo_eq, [70, 76])
    v["cns_profissional"] = np.where(terr, acs.reindex(list(zip(v["ine"], v["microarea"]))).values,
                                     enf.reindex(v["ine"]).values)
    v["cbo"] = np.where(terr, CBO_ACS, CBO_ENFERMEIRO)
    v["microarea_out"] = np.where(ecr, None, v["microarea"].values)
    resp = np.where(pes["dom"].values[v["pos"].values] >= 0, pes["ref"].values[v["pos"].values], None)
    v["responsavel"] = resp
    ci = pd.DataFrame({
        "uuid": v["uuid"], "id_cidadao": v["id_cidadao"], "uuid_originadora": v["uuid_originadora"],
        "cns_profissional": v["cns_profissional"], "ine": v["ine"], "dt_cadastro": _data(v["data"]).values,
        "dt_digitacao": _data(v["dt_digitacao"]).values, "ficha_atualizada": _b(v["n_versao"].values > 0).values,
        "recusa_cadastro": _b(v["recusa"].values).values,
        "responsavel_familiar": pd.Series(resp).astype("boolean").astype("Int8").values,
        "microarea": v["microarea_out"], "fora_area": _b(ecr).values, "raca_cor": _cod(v["raca"]).values,
        "etnia": _cod(v["etnia"]).values, "nome_social": v["nome_social"],
        "deseja_informar_os": _cod(v["deseja_os"]).values, "orientacao_sexual": _cod(v["os"]).values,
        "deseja_informar_ig": _cod(v["deseja_ig"]).values, "identidade_genero": _cod(v["ig"]).values,
        "tem_deficiencia": _cod(v["tem_def"]).values, "escolaridade": _cod(v["escolaridade"]).values,
        "situacao_trabalho": _cod(v["trabalho"]).values, "motivo_saida": _cod(v["motivo"]).values,
        "dt_obito": _data(v["dt_obito"]).values})
    T["cadastro_individual"] = ci
    bits = v["def_bits_reg"].fillna(0).astype(int).values
    linhas = [(u, c) for b, cod_ in BIT_CODIGO.items() for u, c in
              zip(v["uuid"].values[(bits & b) > 0], [cod_] * int(((bits & b) > 0).sum()))]
    T["cadastro_deficiencia"] = pd.DataFrame(linhas, columns=["uuid", "codigo_deficiencia"]).sort_values(
        ["uuid", "codigo_deficiencia"])
    # FAI
    fi, at, pr = mundo.fichas.copy(), mundo.atendimentos.copy(), mundo.problemas.copy()
    pos_cid = pd.Series(cid.loc[cid["dup_de"] < 0, "id_cidadao"].values, index=cid.loc[cid["dup_de"] < 0, "pos"].values)
    at["id_cidadao"] = pos_cid.reindex(at["pos"]).values
    at = at[pd.notna(at["id_cidadao"])].copy()
    fi = fi[fi["ficha"].isin(at["ficha"])].copy()
    fi["uuid_ficha"] = I.uuids_ledi(rng, cnes_eq.reindex(fi["ine"]).values)
    at["uuid_ficha"] = fi.set_index("ficha")["uuid_ficha"].reindex(at["ficha"]).values
    at["id_atendimento"] = _rank(at["uuid_ficha"], at["nu_atendimento"])
    T["ficha_atendimento"] = pd.DataFrame({"uuid_ficha": fi["uuid_ficha"], "cns_profissional": fi["cns_profissional"],
                                           "ine": fi["ine"], "dt_atendimento": _data(fi["data"]).values,
                                           "dt_digitacao": _data(fi["dt_digitacao"]).values})
    T["atendimento_individual"] = pd.DataFrame({
        "id_atendimento": at["id_atendimento"], "uuid_ficha": at["uuid_ficha"],
        "nu_atendimento": at["nu_atendimento"].astype(int), "id_cidadao": at["id_cidadao"].astype(np.int64),
        "dt_hora_inicio": pd.to_datetime(at["dt_hora_inicio"]).dt.strftime("%Y-%m-%d %H:%M:%S"),
        "tipo_atendimento": at["tipo_atendimento"].astype(int), "local_atendimento": at["local_atendimento"].astype(int),
        "turno": at["turno"].astype(int)}).sort_values("id_atendimento")
    id_at = at.set_index("id_at")["id_atendimento"]
    pr = pr[pr["id_at"].isin(id_at.index)].copy()
    pr["id_atendimento"] = id_at.reindex(pr["id_at"]).values
    T["atendimento_problema"] = pr[["id_atendimento", "nu_item", "ciap", "cid10"]].sort_values(
        ["id_atendimento", "nu_item"])
    mundo.verdade["_at"] = at
    mundo.verdade["_fi"] = fi
    # parâmetro da carga
    p = cfg.periodo
    T["parametro"] = pd.DataFrame([{
        "id_carga": int(cfg.id_carga), "data_corte": p.data_corte, "idade_min_elegivel": int(cfg.regra.idade_min_elegivel),
        "recusa_conta_ativo": int(bool(cfg.regra.recusa_conta_ativo)),
        "meses_desatualizado": int(cfg.regra.meses_desatualizado), "semente": int(cfg.semente),
        "fator_escala": float(cfg.escala), "versao_gerador": str(cfg.versao_gerador), "dt_geracao": p.dt_geracao}])
    # gabarito
    T["controle_defeito"] = _gabarito(mundo, v, cid)
    return T


def _gabarito(mundo, v, cid) -> pd.DataFrame:
    df = pd.DataFrame(mundo.defeitos, columns=["tabela", "id_registro", "tipo_defeito", "etapa", "campo",
                                               "id_registro_par", "valor_original"])
    uuid = v["uuid"].values
    idc = cid["id_cidadao"].values

    def traduz(tab, x):
        if x is None or (isinstance(x, float) and np.isnan(x)):
            return None
        i = int(x)
        return uuid[i] if tab == "cadastro_individual" else str(idc[i])
    df["id_registro"] = [traduz(t, x) for t, x in zip(df["tabela"], df["id_registro"])]
    df["id_registro_par"] = [traduz(t, x) for t, x in zip(df["tabela"], df["id_registro_par"])]
    df = df.sort_values(["tabela", "id_registro", "tipo_defeito", "campo"], na_position="first").reset_index(drop=True)
    df.insert(0, "id_defeito", np.arange(1, len(df) + 1))
    return df


# ------------------------------------------------------------------ staging (leiaute LEDI)
def monta_staging(cfg, mundo, T: dict) -> dict[str, pd.DataFrame]:
    rng = fluxo(cfg.semente, "staging")
    v, cid, pes, eq, lot = mundo.versoes, mundo.cidadaos, mundo.pessoas, mundo.equipes, mundo.lotacoes
    d = mundo.verdade["_d"]
    cnes_eq = eq.set_index("ine")["cnes"]
    ba = mundo.bairros.set_index("id_bairro")
    ds_nome = mundo.distritos.set_index("id_ds")["nome_ds"]
    S: dict[str, pd.DataFrame] = {}
    setor = T["setor_censitario"]
    S["malha_territorial"] = pd.DataFrame({"cd_setor": setor["cd_setor"],
                                           "nome_bairro": ba["nome_bairro"].reindex(setor["id_bairro"]).values,
                                           "id_bairro": setor["id_bairro"].values,
                                           "nome_ds": ds_nome.reindex(ba["id_ds"].reindex(setor["id_bairro"])).values})
    S["profissional_lotacao"] = lot[["cns_profissional", "nome_profissional", "ine", "cbo"]].copy()
    # FCDT
    logr, num, cep = I.enderecos(rng, len(d))
    acs = lot[lot["cbo"] == CBO_ACS].set_index(["ine", "microarea"])["cns_profissional"]
    S["fcdt"] = pd.DataFrame({
        "profissional_cns": acs.reindex(list(zip(d["equipe"], d["microarea"]))).values, "cbo_codigo_2002": CBO_ACS,
        "cnes": cnes_eq.reindex(d["equipe"]).values, "ine": d["equipe"].values,
        "data_atendimento": _ms(d["dt_cadastro"]), "codigo_ibge_municipio": IBGE_RECIFE, "uuid": d["uuid"].values,
        "uuid_ficha_originadora": d["uuid"].values, "ficha_atualizada": 0, "tp_cds_origem": 3,
        "status_termo_recusa": 0, "tipo_de_imovel": d["tipo_imovel"].astype(int).values, "tipo_endereco": None,
        "st_ativo": _b(d["ativo"].values).values, "bairro": ba["nome_bairro"].reindex(d["bairro"]).values,
        "cep": cep, "codigo_ibge_municipio_endereco": IBGE_RECIFE, "nome_logradouro": logr, "numero": num,
        "numero_dne_uf": "26", "tipo_logradouro_numero_dne": "081", "micro_area": d["microarea"].values,
        "st_fora_area": 0, "localizacao": 83, "situacao_moradia_posse_terra": None, "tipo_domicilio": None,
        "cd_setor": d["setor"].values})
    # erro de digitação no endereço (defeito 7 da FCDT, só existe na staging)
    m7 = rng.random(len(d)) < float(cfg.defeitos.erro_endereco)
    from .defeitos import _typo
    for i in np.nonzero(m7)[0]:
        orig = S["fcdt"].at[i, "nome_logradouro"]
        S["fcdt"].at[i, "nome_logradouro"] = _typo(rng, orig)
        mundo.defeito("domicilio", int(T["domicilio"].set_index("uuid_ficha").loc[d.at[i, "uuid"], "id_domicilio"]),
                      7, 7, "nome_logradouro", original=orig)
    fam = d[(d["tipo_imovel"] == 1) & (d["n_mor"] > 0)]
    ref_cid = cid[cid["dup_de"] < 0].set_index("pos")
    ref_pos = pd.Index(pes["pid"]).get_indexer(fam["ref_pid"].values)
    rc = ref_cid.reindex(ref_pos)
    TF = T["familia"].set_index("id_domicilio")
    S["fcdt_familia"] = pd.DataFrame({
        "uuid": fam["uuid"].values, "nu_familia": 1, "numero_cns_responsavel": rc["cns"].values,
        "cpf_responsavel": rc["cpf"].values, "data_nascimento_responsavel": _ms(rc["dob"].values),
        "numero_membros_familia": fam["n_mor"].astype(int).values,
        "renda_familiar": TF["renda_familiar"].reindex(fam["id_domicilio"]).values,
        "reside_desde": _ms(TF["reside_desde"].reindex(fam["id_domicilio"]).values),
        "st_mudanca": TF["mudou_se"].reindex(fam["id_domicilio"]).values})
    # FCI
    c = cid.iloc[v["cid"].values].reset_index(drop=True)
    ci = T["cadastro_individual"]
    pos = v["pos"].values
    idade = v["idade"].values
    ref_dom = pes["dom"].values[pos]
    dom_ref = mundo.domicilios.set_index("hid")["ref_pid"]
    seg2 = v["seg"].values == 2
    hid = np.where(seg2, pes["dom2"].values[pos], ref_dom)
    rpid = dom_ref.reindex(hid).values
    rpos = pd.Index(pes["pid"]).get_indexer(np.nan_to_num(rpid, nan=-1).astype(np.int64))
    rr = ref_cid.reindex(rpos)
    bits = v["def_bits_reg"].fillna(0).astype(int).values
    defs = [",".join(str(cod_) for b, cod_ in BIT_CODIGO.items() if x & b) or None for x in bits]
    sem_cpf = pd.isna(c["cpf"]).values
    S["fci"] = pd.DataFrame({
        "profissional_cns": v["cns_profissional"].values, "cbo_codigo_2002": v["cbo"].values,
        "cnes": cnes_eq.reindex(v["ine"]).values, "ine": v["ine"].values, "data_atendimento": _ms(v["data"]),
        "codigo_ibge_municipio": IBGE_RECIFE, "uuid": v["uuid"].values,
        "uuid_ficha_originadora": np.where(v["n_versao"].values > 0, v["uuid_originadora"].values, v["uuid"].values),
        "ficha_atualizada": ci["ficha_atualizada"].values, "tp_cds_origem": 3,
        "status_termo_recusa_cadastro_individual_atencao_basica": ci["recusa_cadastro"].values,
        "cpf_cidadao": c["cpf"].values, "cns_cidadao": c["cns"].values, "st_nao_possui_cpf": _b(sem_cpf).values,
        "justificativa_nao_possui_cpf": np.where(sem_cpf, np.where(idade < 18, 2, 3), None),
        "nome_cidadao": c["nome"].values, "nome_social": ci["nome_social"].values,
        "data_nascimento_cidadao": _ms(c["dob"].values), "sexo_cidadao": c["sexo"].astype(int).values,
        "raca_cor_cidadao": ci["raca_cor"].values, "etnia": ci["etnia"].values, "nacionalidade_cidadao": 1,
        "pais_nascimento": 31, "codigo_ibge_municipio_nascimento": IBGE_RECIFE, "nome_mae_cidadao": c["nome_mae"].values,
        "desconhece_nome_mae": 0, "nome_pai_cidadao": None, "desconhece_nome_pai": 1,
        "status_eh_responsavel": ci["responsavel_familiar"].values,
        "cpf_responsavel_familiar": np.where(pes["ref"].values[pos], None, rr["cpf"].values),
        "cns_responsavel_familiar": np.where(pes["ref"].values[pos], None, rr["cns"].values),
        "microarea": ci["microarea"].values, "st_fora_area": ci["fora_area"].values,
        "status_deseja_informar_orientacao_sexual": ci["deseja_informar_os"].values,
        "orientacao_sexual_cidadao": ci["orientacao_sexual"].values,
        "status_deseja_informar_identidade_genero": ci["deseja_informar_ig"].values,
        "identidade_genero_cidadao": ci["identidade_genero"].values,
        "status_tem_alguma_deficiencia": ci["tem_deficiencia"].values, "deficiencias_cidadao": defs,
        "grau_instrucao_cidadao": ci["escolaridade"].values,
        "situacao_mercado_trabalho_cidadao": ci["situacao_trabalho"].values, "relacao_parentesco_cidadao": None,
        "status_frequenta_escola": _b((idade >= 4) & (idade < 18)).values,
        "status_membro_povo_comunidade_tradicional": 0, "co_povo_comunidade_tradicional": None,
        "motivo_saida_cidadao": ci["motivo_saida"].values, "data_obito": _ms(v["dt_obito"]), "numero_do": None,
        "dt_digitacao": ci["dt_digitacao"].values})
    _familia_do_cidadao(T, S)
    # FAI
    at, fi = mundo.verdade["_at"], mundo.verdade["_fi"]
    ca = cid[cid["dup_de"] < 0].set_index("pos").reindex(at["pos"])
    cbo_prof = lot.drop_duplicates("cns_profissional").set_index("cns_profissional")["cbo"]
    fim = pd.to_datetime(at["dt_hora_inicio"]) + pd.to_timedelta(rng.integers(10, 40, len(at)), unit="m")
    data_f = fi.set_index("ficha").reindex(at["ficha"])
    sem = pd.isna(ca["cpf"]).values
    idade_at = ((at["data"].values.astype("datetime64[D]") - ca["dob"].values.astype("datetime64[D]")).astype(int)
                / 365.25)
    S["fai"] = pd.DataFrame({
        "uuid_ficha": at["uuid_ficha"].values, "tp_cds_origem": 3, "profissional_cns": at["cns_profissional"].values,
        "cbo_codigo_2002": cbo_prof.reindex(at["cns_profissional"]).values, "cnes": cnes_eq.reindex(at["ine"]).values,
        "ine": at["ine"].values, "data_atendimento": _ms(data_f["data"].values), "codigo_ibge_municipio": IBGE_RECIFE,
        "nu_atendimento": at["nu_atendimento"].astype(int).values, "cpf_cidadao": ca["cpf"].values,
        "cns_cidadao": ca["cns"].values, "st_cidadao_nao_possui_cpf": _b(sem).values,
        "justificativa_nao_possui_cpf": np.where(sem, np.where(idade_at < 18, 2, 3), None),
        "data_nascimento": _ms(ca["dob"].values), "sexo": ca["sexo"].astype(int).values,
        "local_de_atendimento": at["local_atendimento"].astype(int).values, "turno": at["turno"].astype(int).values,
        "tipo_atendimento": at["tipo_atendimento"].astype(int).values, "condutas": None,
        "data_hora_inicial_atendimento": _ms(at["dt_hora_inicio"].values), "data_hora_final_atendimento": _ms(fim.values),
        "dt_digitacao": _data(data_f["dt_digitacao"].values).values})
    pr = T["atendimento_problema"].merge(T["atendimento_individual"][["id_atendimento", "uuid_ficha", "nu_atendimento"]],
                                         on="id_atendimento")
    S["fai_problema"] = pd.DataFrame({"uuid_ficha": pr["uuid_ficha"], "nu_atendimento": pr["nu_atendimento"],
                                      "nu_item": pr["nu_item"], "ciap": pr["ciap"], "cid10": pr["cid10"],
                                      "is_avaliado": 1})
    for k, df in S.items():
        df.insert(0, "motivo_rejeicao", None)
        df.insert(0, "st_processamento", "P")
        df.insert(0, "nu_linha", np.arange(1, len(df) + 1))
        df.insert(0, "id_carga", int(cfg.id_carga))
    # o defeito de endereço entrou depois do gabarito: refaz a tabela
    T["controle_defeito"] = _gabarito(mundo, v, cid)
    return S


def _chave(cpf, cns) -> pd.Series:
    cpf, cns = pd.Series(cpf, dtype=object), pd.Series(cns, dtype=object)
    return pd.Series(np.where(cpf.notna(), cpf, np.where(cns.notna(), "CNS" + cns.astype(str), None)), dtype=object)


def _familia_do_cidadao(T: dict, S: dict) -> None:
    """RN: a família do cidadão é a do responsável indicado na versão vigente da FCI; entre as
    famílias desse responsável vale a da FCDT mais recente. A mesma regra está no SQL 06."""
    fci = S["fci"]
    ordem = fci.assign(_u=fci["uuid"].astype(str)).sort_values(
        ["data_atendimento", "dt_digitacao", "_u"], ascending=False, kind="mergesort")
    ult = ordem.assign(_k=_chave(ordem["cpf_cidadao"].values, ordem["cns_cidadao"].values).values)
    ult = ult.drop_duplicates("_k", keep="first")
    resp = _chave(ult["cpf_responsavel_familiar"].values, ult["cns_responsavel_familiar"].values).values
    k_resp = np.where(ult["status_eh_responsavel"].fillna(0).astype(int).values == 1, ult["_k"].values, resp)
    fam = S["fcdt_familia"].merge(S["fcdt"][["uuid", "data_atendimento"]], on="uuid")
    fam = fam.assign(_k=_chave(fam["cpf_responsavel"].values, fam["numero_cns_responsavel"].values).values,
                     _u=fam["uuid"].astype(str))
    fam = fam[fam["_k"].notna()].sort_values(["data_atendimento", "_u"], ascending=False, kind="mergesort")
    fam = fam.drop_duplicates("_k", keep="first")
    idfam = T["familia"].merge(T["domicilio"][["id_domicilio", "uuid_ficha"]], on="id_domicilio")
    idfam = idfam.set_index("uuid_ficha")["id_familia"]
    fam_por_chave = pd.Series(idfam.reindex(fam["uuid"]).values, index=fam["_k"].values)
    por_cid = pd.Series(fam_por_chave.reindex(k_resp).values, index=ult["_k"].values)
    c = T["cidadao"]
    chave = _chave(c["cpf"].values, c["cns"].values).values
    c["id_familia"] = pd.array(por_cid.reindex(chave).values, dtype="Int64")
    # família sem nenhum membro (todos se mudaram e foram recadastrados em outra família, ou as
    # fichas ainda não foram transmitidas) não entra na carga (VC09); os ids são recalculados
    usadas = set(c["id_familia"].dropna().astype(int))
    fam = T["familia"]
    manter = fam["id_familia"].isin(usadas).values
    uuid_dom = T["domicilio"].set_index("id_domicilio")["uuid_ficha"]
    fam = fam[manter].copy()
    fam["_u"] = uuid_dom.reindex(fam["id_domicilio"]).values
    novo = pd.Series(_rank(fam["_u"]), index=fam["id_familia"].values)
    fam["id_familia"] = novo.values
    T["familia"] = fam.drop(columns="_u").sort_values("id_familia")
    c["id_familia"] = pd.array(novo.reindex(c["id_familia"].astype("float").values).values, dtype="Int64")
    S["fcdt_familia"] = S["fcdt_familia"][S["fcdt_familia"]["uuid"].isin(set(fam["_u"]))].reset_index(drop=True)


# ------------------------------------------------------------------ verdade
def monta_verdade(cfg, mundo) -> dict[str, pd.DataFrame]:
    pes, v, cid = mundo.pessoas, mundo.versoes, mundo.cidadaos
    V = {}
    idc = cid[cid["dup_de"] < 0].set_index("pos")["id_cidadao"]
    cols = ["pid", "ds", "bairro", "sexo", "idade_ref", "dob", "raca", "residente", "dom", "dom2", "equipe",
            "equipe2", "cadastrado", "seg1", "seg2", "def_funcional", "def_bits", "os_true", "lgb", "ig_true",
            "trans_nb", "nome_social", "recusa", "w_A", "dt_obito", "dt_mud", "mae_pid", "nasc_serie"]
    pv = pes[cols].copy()
    pv["id_cidadao"] = idc.reindex(np.arange(len(pes))).astype("Int64").values
    V["pessoas"] = pv
    V["versoes"] = pd.DataFrame({"uuid": v["uuid"], "id_cidadao": v["id_cidadao"], "seg": v["seg"],
                                 "tipo": v["tipo"], "R_os": v["R_os"], "R_ig": v["R_ig"],
                                 "nao_sem_pergunta_os": v["nao_sem_perg_os"], "p_sim_os": v["p_sim_os"],
                                 "crianca_na_versao": v["crianca"]})
    eq = mundo.equipes.drop(columns=[c for c in ("territorial",) if c not in mundo.equipes])
    V["equipes"] = eq
    V["equipe_mes"] = mundo.verdade["equipe_mes"]
    V["componentes"] = mundo.verdade["componentes"]
    V["metas_usf"] = mundo.verdade["registro"]["metas_usf"]
    V["nascimentos"] = mundo.verdade["nascimentos"]
    dup = mundo.verdade.get("duplicidades")
    if dup is not None:
        V["duplicidades"] = pd.DataFrame({"id_cidadao_duplicado": cid["id_cidadao"].values[dup["cid_duplicado"].values],
                                          "id_cidadao_original": cid["id_cidadao"].values[dup["cid_original"].values]})
    return V


def monta_referencias(cfg, mundo) -> pd.DataFrame:
    """Parâmetros complementares para analitica.ref_parametro_oficial: boletim SESAU 01/2025 e
    a referência bairro × raça/cor do IPF (o Censo 2022 não publica raça por bairro)."""
    cols = ["fonte", "tabela_fonte", "nivel", "cd_territorio", "variavel", "categoria", "valor", "ic_inferior",
            "ic_superior", "dt_acesso"]
    from .config import RAIZ
    bol = pd.read_csv(RAIZ / "dados" / "parametros_complementares" / "boletim_sesau_2025.csv", dtype=str)[cols]
    x = mundo.verdade["tensor_ipf"].sum(axis=(1, 2))                  # [bairro, raça]
    linhas = []
    for b in range(x.shape[0]):
        tot = x[b].sum()
        for i, r in enumerate((1, 2, 3, 4, 5)):
            linhas.append(("Gerador IPF", "IPF Censo 2022 + boletim", "bairro", f"{IBGE_RECIFE}{b + 1:03d}",
                           "prop_raca_cor", str(r), f"{x[b, i] / tot:.6f}" if tot else "0", None, None,
                           str(pd.Timestamp(cfg.periodo.dt_geracao).date())))
    return pd.concat([bol, pd.DataFrame(linhas, columns=cols)], ignore_index=True)


def grava(cfg, mundo, destino: Path) -> dict:
    destino = Path(destino)
    T = monta_tabelas(cfg, mundo)
    S = monta_staging(cfg, mundo, T)
    V = monta_verdade(cfg, mundo)
    arquivos = {}
    ref = monta_referencias(cfg, mundo)
    _grava(ref, destino / "analitica" / "ref_parametro_complementar.csv")
    arquivos["analitica/ref_parametro_complementar.csv"] = len(ref)
    for nome in ORDEM_NUCLEO:
        p = destino / "nucleo" / f"{nome}.csv"
        _grava(T[nome], p)
        arquivos[f"nucleo/{nome}.csv"] = len(T[nome])
    for nome in ORDEM_STG:
        p = destino / "staging" / f"{nome}.csv"
        _grava(S[nome], p)
        arquivos[f"staging/{nome}.csv"] = len(S[nome])
    (destino / "verdade").mkdir(parents=True, exist_ok=True)
    for nome, df in V.items():
        df = df.copy()
        for c in df.columns:
            if df[c].dtype == object:
                df[c] = df[c].astype("string")
        df.to_parquet(destino / "verdade" / f"{nome}.parquet", index=False)
        arquivos[f"verdade/{nome}.parquet"] = len(df)
    (destino / "verdade" / "diagnostico.json").write_text(
        json.dumps(_jsonavel(mundo.diagnostico), ensure_ascii=False, indent=2), encoding="utf-8")
    from .config import salva
    salva(cfg, destino / "config_usada.yaml")
    manifesto = {"nome": cfg.nome, "versao_gerador": cfg.versao_gerador, "semente": cfg.semente,
                 "escala": cfg.escala, "distritos": list(cfg.distritos), "dt_geracao": cfg.periodo.dt_geracao,
                 "linhas": arquivos,
                 "sha256": {k: _sha(destino / k) for k in sorted(arquivos) + ["config_usada.yaml"]}}
    (destino / "manifesto.json").write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifesto


def _jsonavel(x):
    if isinstance(x, dict):
        return {str(k): _jsonavel(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonavel(i) for i in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return float(x)
    if isinstance(x, np.ndarray):
        return x.tolist()
    return x
