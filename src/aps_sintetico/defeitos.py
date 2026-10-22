"""Etapa 7 – identidades e injeção de defeitos de qualidade, com gabarito.

Os defeitos de comportamento (5, 6, 10, 11, 12) nascem na Etapa 6 (dinamica.py). Aqui entram
os defeitos de processo, injetados depois da geração e registrados em controle_defeito:
  1 duplicidade de cidadão · 2 raça/cor errada (heteroidentificação ou excesso de amarela) ·
  3 raça/cor divergente entre versões · 4 raça/cor vazia em versão antiga · 7 erro de
  digitação (nome; o de endereço entra na staging, exporta.py) · 8 data de nascimento
  implausível · 9 escolaridade incompatível com a idade · 13 "Tem deficiência" sem registro.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import identificadores as I
from .dinamica import _d
from .rng import fluxo

_ETNIAS_PE = [251, 252, 49, 173, 174, 175, 27, 85, 86, 95, 215, 225]   # povos de Pernambuco


def monta_cidadaos(cfg, mundo) -> None:
    """Uma linha por pessoa com ao menos uma versão transmitida (identidade civil)."""
    pes, v = mundo.pessoas, mundo.versoes
    rng = fluxo(cfg.semente, "identidades")
    pos = np.unique(v["pos"].values)
    p = pes.iloc[pos]
    n = len(pos)
    idade = p["idade_ref"].values
    tem_cpf = rng.random(n) < np.where(idade >= 18, 0.95, 0.70)
    tem_cns = rng.random(n) < 0.92
    tem_cns |= ~tem_cpf
    cpf = np.where(tem_cpf, I.cpfs(rng, n), None)
    cns = np.where(tem_cns, I.cnss(rng, n), None)
    sexo = p["sexo"].values
    nome = I.nomes(rng, sexo)
    # nome social: prenome do gênero da identidade + sobrenomes do nome civil
    ig = p["ig_true"].values
    fem_ig = np.isin(ig, [150, 156, 201]) | ((ig == 203) & (rng.random(n) < 0.5))
    pren = I.prenomes(rng, fem_ig)
    sobren = np.array([x.split(" ", 1)[1] for x in nome], dtype=object)
    nsoc = np.where(p["nome_social"].values, pren + " " + sobren, None)
    mae = I.nomes(rng, np.ones(n, dtype=int))
    # família corrente: domicílio de destino (se cadastrado lá) ou de origem
    fam = np.where(p["seg2"].values, p["dom2"].values, p["dom"].values)
    mundo.cidadaos = pd.DataFrame({"cid": np.arange(n), "pos": pos, "cpf": cpf, "cns": cns, "nome": nome,
                                   "nome_social": nsoc, "dob": _d(p["dob"]), "sexo": sexo, "nome_mae": mae,
                                   "hid_familia": fam, "dup_de": -1})
    mapa = pd.Series(np.arange(n), index=pos)
    v["cid"] = mapa.reindex(v["pos"]).values
    # etnia das pessoas indígenas (código e-SUS)
    et = pd.Series(rng.choice(_ETNIAS_PE, len(pes)), index=pes.index)
    v["etnia"] = np.where(v["raca"].values == 5, et.reindex(v["pos"]).values, -1)
    v["nome_social"] = mundo.cidadaos["nome_social"].values[v["cid"].values]


def _typo(rng, s: str) -> str:
    """Um erro de digitação: troca, omissão ou duplicação de letra."""
    if len(s) < 4:
        return s + "A"
    i = int(rng.integers(1, len(s) - 2))
    op = rng.integers(0, 3)
    if op == 0:
        return s[:i] + s[i + 1] + s[i] + s[i + 2:]
    if op == 1:
        return s[:i] + s[i + 1:]
    return s[:i] + s[i] + s[i:]


def injeta(cfg, mundo) -> None:
    d = cfg.defeitos
    v, cid, eq = mundo.versoes, mundo.cidadaos, mundo.equipes
    rng = fluxo(cfg.semente, "defeitos_etapa7")
    n_v = len(v)
    ev = v["motivo"].values > 0
    rec = v["recusa"].values
    # 2: heteroidentificação nas equipes com esse regime (pardos lidos como brancos etc.)
    hetero = eq.set_index("ine")["hetero_raca"].reindex(v["ine"]).values.astype(bool)
    amarela = pd.Series(rng.random(len(eq)) < float(d.equipes_amarela), index=eq["ine"]).reindex(v["ine"]).values
    raca = v["raca"].values.copy()
    m2 = hetero & ~ev & ~rec & (raca > 0) & (rng.random(n_v) < float(d.raca_errada_hetero))
    troca = {4: (1, 2), 2: (4, 4), 1: (4, 1), 3: (1, 4), 5: (4, 4)}
    nova = raca.copy()
    u = rng.random(n_v)
    for r_, (a, b) in troca.items():
        mm = m2 & (raca == r_)
        nova[mm] = np.where(u[mm] < 0.6, a, b)
    m2 &= nova != raca
    m2b = amarela & ~ev & ~rec & (raca > 0) & (raca != 3) & (rng.random(n_v) < float(d.raca_amarela_prob))
    nova[m2b] = 3
    for i in np.nonzero(m2 | m2b)[0]:
        mundo.defeito("cadastro_individual", i, 2, 7, "raca_cor", original=raca[i])
    # 3: divergência pontual numa atualização (sem relação com o regime da equipe)
    upd = (v["n_versao"].values > 0) & ~ev & ~rec & (nova > 0)
    m3 = upd & (rng.random(n_v) < float(d.raca_divergente)) & ~(m2 | m2b)
    alt = np.array([1, 2, 3, 4])
    for i in np.nonzero(m3)[0]:
        outra = alt[alt != nova[i]]
        mundo.defeito("cadastro_individual", i, 3, 7, "raca_cor", par=i - int(v.at[i, "n_versao"]), original=nova[i])
        nova[i] = rng.choice(outra)
    # 4: raça/cor vazia em versões anteriores ao ano de corte do legado
    ano = pd.DatetimeIndex(v["data"].values).year
    m4 = (ano < int(d.ano_legado)) & ~rec & ~ev & (nova > 0) & (rng.random(n_v) < float(d.raca_vazia_legado))
    for i in np.nonzero(m4)[0]:
        mundo.defeito("cadastro_individual", i, 4, 7, "raca_cor", original=nova[i])
    nova[m4] = -1
    # eventos (saída/óbito) repetem a raça da versão anterior da cadeia
    for i in np.nonzero(ev)[0]:
        if i > 0 and v.at[i, "n_versao"] > 0:
            nova[i] = nova[i - 1]
    v["raca"] = nova
    v.loc[(v["raca"] != 5), "etnia"] = -1
    v.loc[(v["raca"] == 5) & (v["etnia"] < 0), "etnia"] = _ETNIAS_PE[0]
    # 9: escolaridade incompatível com a idade
    idade = v["idade"].values
    m9 = (idade >= 5) & (idade < 14) & ~rec & ~ev & (rng.random(n_v) < float(d.escolaridade_incompativel))
    for i in np.nonzero(m9)[0]:
        mundo.defeito("cadastro_individual", i, 9, 7, "escolaridade", original=v.at[i, "escolaridade"])
    v.loc[m9, "escolaridade"] = np.where(idade[m9] < 10, rng.choice([56, 60], m9.sum()), 63)
    # 13: "Tem deficiência" sem registro (campo nulo, RQ11); o tipo declarado se perde junto
    m13 = (v["tem_def"].values >= 0) & ~ev & ~rec & (rng.random(n_v) < float(d.deficiencia_sem_registro))
    for i in np.nonzero(m13)[0]:
        mundo.defeito("cadastro_individual", i, 13, 7, "tem_deficiencia", original=int(v.at[i, "tem_def"]))
    v.loc[m13, "tem_def"] = -1
    v.loc[m13, "def_bits_reg"] = 0
    # 8: data de nascimento implausível (ano trocado ou 01/01/1900)
    nc = len(cid)
    dob = cid["dob"].values.astype("datetime64[D]").copy()
    m8a = rng.random(nc) < float(d.data_implausivel)
    m8b = ~m8a & (rng.random(nc) < float(d.data_1900))
    for i in np.nonzero(m8a | m8b)[0]:
        mundo.defeito("cidadao", i, 8, 7, "dt_nascimento", original=str(dob[i]))
    # idade entre 111 e 120 anos na data de corte (passa na VC03, que tolera até 130; a RQ12 acusa)
    corte = np.datetime64(cfg.periodo.data_corte)
    dob[m8a] = corte - (rng.uniform(111, 120, m8a.sum()) * 365.25).astype(int)
    dob[m8b] = np.datetime64("1900-01-01")
    cid["dob"] = dob
    # 7: erro de digitação no nome
    m7 = rng.random(nc) < float(d.erro_nome)
    nomes = cid["nome"].values.copy()
    for i in np.nonzero(m7)[0]:
        mundo.defeito("cidadao", i, 7, 7, "nome", original=nomes[i])
        nomes[i] = _typo(rng, nomes[i])
    cid["nome"] = nomes
    _duplicidades(cfg, mundo, rng)


def _duplicidades(cfg, mundo, rng) -> None:
    """1: o mesmo cidadão recadastrado com outra identificação (só CNS provisório, sem CPF)
    numa nova cadeia; 80% com o nome idêntico, 20% com variação de digitação."""
    v, cid = mundo.versoes, mundo.cidadaos
    nc = len(cid)
    k = int(round(nc * float(cfg.defeitos.duplicidade)))
    if k == 0:
        return
    origem = rng.choice(nc, k, replace=False)
    novos = cid.iloc[origem].copy()
    novos["cid"] = nc + np.arange(k)
    novos["dup_de"] = cid["cid"].values[origem]
    novos["cpf"] = None
    usados = set(cid["cns"].dropna())
    novos["cns"] = I.cnss(rng, k, excluir=usados, prop_definitivo=0.0)
    var = rng.random(k) < 0.2
    novos.loc[var, "nome"] = [_typo(rng, s) for s in novos.loc[var, "nome"]]
    mundo.cidadaos = pd.concat([cid, novos], ignore_index=True)
    # nova cadeia: uma cópia da última versão (não evento) do original, em data posterior
    ult = v[v["motivo"] < 0].sort_values(["cid", "data"]).drop_duplicates("cid", keep="last").set_index("cid")
    base = ult.reindex(cid["cid"].values[origem])
    ok = base["pos"].notna().values
    base = base[ok].reset_index()
    corte = np.datetime64(cfg.periodo.data_corte)
    d0 = base["data"].values.astype("datetime64[D]")
    span = np.maximum((corte - d0).astype(int), 1)
    nova_data = d0 + (rng.random(len(base)) * span).astype(int)
    base["data"] = nova_data
    base["dt_digitacao"] = nova_data + rng.integers(0, 8, len(base))
    lim = np.datetime64(pd.Timestamp(cfg.periodo.dt_geracao).date())
    base["dt_digitacao"] = np.minimum(base["dt_digitacao"].values.astype("datetime64[D]"), lim - 1)
    base["cid"] = novos["cid"].values[ok]
    base["tipo"] = "inicial"
    base["n_versao"] = 0
    base["seg"] = 9                                    # cadeia da duplicidade
    base["cadeia"] = v["cadeia"].max() + 1 + np.arange(len(base))
    mundo.versoes = pd.concat([v, base[v.columns]], ignore_index=True)
    for j, (c_novo, c_orig) in enumerate(zip(novos["cid"].values[ok], novos["dup_de"].values[ok])):
        mundo.defeito("cidadao", c_novo, 1, 7, "id_cidadao", par=c_orig)
    mundo.verdade["duplicidades"] = pd.DataFrame({"cid_duplicado": novos["cid"].values,
                                                  "cid_original": novos["dup_de"].values})
