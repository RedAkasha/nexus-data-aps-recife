"""Etapa 9 – camada analítica em Python (sem banco), equivalente a sql/postgresql/07_analitica.sql.

Lê os CSV do núcleo e grava em <saida>/analitica/*.parquet as tabelas que o painel e o
Power BI consomem: dim_competencia, fato_indicador_equipe, fato_atendimento_equipe,
fato_painel_ml e monitoramento_usf (colunas H a U da planilha da SESAU). O teste
tests/test_analitica.py confere que o SQL e o Python produzem os mesmos números.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import parametros as P
from .valida import le_csv, vigente
from .config import carrega as carrega_cfg

FAIXAS = [(10, "00-10"), (17, "11-17"), (29, "18-29"), (39, "30-39"), (59, "40-59"), (200, "60+")]


def _arred(x, casas: int):
    """Arredondamento meio-para-cima (o ROUND do SQL), não o bancário do numpy."""
    f = 10.0 ** casas
    x = np.asarray(x, dtype=float)
    return np.sign(x) * np.floor(np.abs(x) * f + 0.5 + 1e-9) / f


def _idade(nasc: pd.Series, ref: pd.Timestamp) -> np.ndarray:
    n = pd.to_datetime(nasc)
    aniv = (n.dt.month > ref.month) | ((n.dt.month == ref.month) & (n.dt.day > ref.day))
    return (ref.year - n.dt.year - aniv.astype(int)).values


def _faixa(idade: np.ndarray) -> np.ndarray:
    lim = np.array([f[0] for f in FAIXAS])
    nomes = np.array([f[1] for f in FAIXAS], dtype=object)
    return nomes[np.searchsorted(lim, idade, side="left")]


def _estrutura():
    est = P.estrutura()
    eq = est["equipe"][["ine", "cnes", "tipo_equipe"]].copy()
    uni = est["unidade"][["cnes", "id_bairro"]]
    ba = est["bairro"][["id_bairro", "id_ds"]]
    return eq.merge(uni, on="cnes").merge(ba, on="id_bairro")


def dim_competencia(fa: pd.DataFrame, corte: pd.Timestamp) -> pd.DataFrame:
    ini = pd.to_datetime(fa["dt_atendimento"]).min().to_period("M").to_timestamp()
    m = pd.date_range(ini, corte.to_period("M").to_timestamp(), freq="MS")
    return pd.DataFrame({"competencia": m.strftime("%Y%m").astype(int), "dt_inicio": m,
                         "dt_fim": m + pd.offsets.MonthEnd(0), "ano": m.year, "mes": m.month,
                         "quadrimestre": m.year * 10 + (m.month - 1) // 4 + 1,
                         "semestre": m.year * 10 + (m.month - 1) // 6 + 1})


def _codigo(s: pd.Series, nulo: int = -1) -> np.ndarray:
    return pd.to_numeric(s, errors="coerce").fillna(nulo).astype(np.int16).values


def _versoes_ativas(cfg, ci: pd.DataFrame, cid: pd.DataFrame, est: pd.DataFrame) -> dict:
    """Versões não encerradas, em colunas numéricas compactas (memória ~ 40 bytes/versão)."""
    v = ci.sort_values(["id_cidadao", "dt_cadastro", "dt_digitacao", "uuid"], kind="mergesort")
    dt = pd.to_datetime(v["dt_cadastro"]).values.astype("datetime64[D]").astype(np.int64)
    mesmo = v["id_cidadao"].values[1:] == v["id_cidadao"].values[:-1]
    prox = np.full(len(v), np.iinfo(np.int64).max)
    prox[:-1] = np.where(mesmo, dt[1:], np.iinfo(np.int64).max)
    rec = (v["recusa_cadastro"] == "1").values
    ok = v["motivo_saida"].isna().values & (bool(cfg.regra.recusa_conta_ativo) | ~rec)
    nasc = pd.to_datetime(cid.set_index("id_cidadao")["dt_nascimento"].reindex(v["id_cidadao"]).values)
    ines = pd.Index(sorted(est["ine"]))
    o = {"uuid": v["uuid"].values[ok], "dt": dt[ok], "prox": prox[ok],
         "ine": ines.get_indexer(v["ine"].values[ok]).astype(np.int32),
         "ano": nasc.year.values[ok].astype(np.int32), "mes": nasc.month.values[ok].astype(np.int8),
         "dia": nasc.day.values[ok].astype(np.int8),
         "os": _codigo(v["deseja_informar_os"])[ok].astype(np.int8), "os_c": _codigo(v["orientacao_sexual"])[ok],
         "ig": _codigo(v["deseja_informar_ig"])[ok].astype(np.int8), "ig_c": _codigo(v["identidade_genero"])[ok],
         "raca": _codigo(v["raca_cor"])[ok].astype(np.int8), "def": _codigo(v["tem_deficiencia"])[ok].astype(np.int8),
         "ns": v["nome_social"].notna().values[ok], "ines": ines}
    return o


_CAT3 = {1: "SIM", 0: "NAO"}
_FAIXA_NOMES = np.array([f[1] for f in FAIXAS], dtype=object)


def _idade_em(o: dict, idx: np.ndarray, f: pd.Timestamp) -> np.ndarray:
    aniv = (o["mes"][idx] > f.month) | ((o["mes"][idx] == f.month) & (o["dia"][idx] > f.day))
    return f.year - o["ano"][idx] - aniv.astype(np.int32)


def _agrega_mes(o: dict, idx: np.ndarray, idade: np.ndarray, idade_min: int, def_por_versao: pd.DataFrame):
    """Contagens do mês por (equipe, faixa, elegível, marcador, categoria)."""
    fx = np.searchsorted(np.array([f[0] for f in FAIXAS]), idade, side="left").astype(np.int8)
    base = pd.DataFrame({"ine": o["ine"][idx], "fx": fx, "el": idade >= idade_min})
    partes = []

    def conta(marcador, cat, mascara=None):
        b = base if mascara is None else base[mascara]
        c = cat if mascara is None else cat[mascara]
        g = b.assign(categoria=c).groupby(["ine", "fx", "el", "categoria"], observed=True).size()
        partes.append(g.rename("n").reset_index().assign(marcador=marcador))
    for k, nome, nulo in (("os", "OS", "NAO_INFORMADO"), ("ig", "IG", "NAO_INFORMADO"), ("def", "DEFICIENCIA", "SEM_REGISTRO")):
        x = o[k][idx]
        conta(nome, np.where(x == 1, "SIM", np.where(x == 0, "NAO", nulo)))
    for k, nome in (("os_c", "OS"), ("ig_c", "IG")):
        x = o[k][idx]
        conta(nome, x.astype(str), x >= 0)
    r = o["raca"][idx]
    conta("RACA_COR", np.where(r >= 0, r.astype(str), "VAZIO"))
    conta("NOME_SOCIAL", np.where(o["ns"][idx], "PREENCHIDO", "VAZIO"))
    if len(def_por_versao):
        pos = pd.Series(np.arange(len(idx)), index=idx)
        d = def_por_versao[def_por_versao["vpos"].isin(idx)]
        j = pos.reindex(d["vpos"]).values
        b = base.iloc[j].assign(categoria=d["codigo_deficiencia"].values)
        g = b.groupby(["ine", "fx", "el", "categoria"]).size()
        partes.append(g.rename("n").reset_index().assign(marcador="DEFICIENCIA"))
    return pd.concat(partes, ignore_index=True), base


def _painel_mes(o: dict, idx: np.ndarray, idade: np.ndarray, base: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    el = base["el"].values
    x = base.assign(sim=el & (o["os"][idx] == 1), nao=el & (o["os"][idx] == 0), ni=el & (o["os"][idx] == -1),
                    sim_ig=el & (o["ig"][idx] == 1), cri=~el, s60=idade >= 60)
    g = x.groupby("ine").agg(n_dado_real=("el", "sum"), n_sim=("sim", "sum"), n_nao=("nao", "sum"),
                             n_ni=("ni", "sum"), n_sim_ig=("sim_ig", "sum"), n_cri=("cri", "sum"),
                             n_60=("s60", "sum"), n_ativos=("el", "size")).reset_index()
    r = o["raca"][idx]
    rr = pd.DataFrame({"ine": o["ine"][idx][r >= 0], "raca_cor": r[r >= 0].astype(str)})
    rr = rr.groupby(["ine", "raca_cor"]).size().rename("c").reset_index()
    return g, rr


def percorre_competencias(cfg, ci, cid, cdef, dim, est):
    """Uma passada mês a mês: indicadores, cadastrados ativos e os insumos do painel."""
    o = _versoes_ativas(cfg, ci, cid, est)
    vpos = pd.Series(np.arange(len(o["uuid"])), index=o["uuid"])
    dpv = pd.DataFrame({"vpos": vpos.reindex(cdef["uuid"]).values, "codigo_deficiencia": cdef["codigo_deficiencia"].values})
    dpv = dpv[dpv["vpos"].notna()].astype({"vpos": np.int64})
    fim_periodo = set(dim.groupby("quadrimestre")["competencia"].max())
    q_de = dim.set_index("competencia")["quadrimestre"]
    imin = int(cfg.regra.idade_min_elegivel)
    ind, cad, pai, rac = [], [], [], []
    for _, d in dim.iterrows():
        f = pd.Timestamp(d["dt_fim"])
        fd = np.datetime64(f.date()).astype("datetime64[D]").astype(np.int64)
        idx = np.nonzero((o["dt"] <= fd) & (o["prox"] > fd))[0]
        idade = _idade_em(o, idx, f)
        a, base = _agrega_mes(o, idx, idade, imin, dpv)
        ind.append(a.assign(competencia=d["competencia"]))
        cad.append(base.groupby("ine").size().rename("n_cadastrados").reset_index().assign(competencia=d["competencia"]))
        if d["competencia"] in fim_periodo:
            g, rr = _painel_mes(o, idx, idade, base)
            pai.append(g.assign(periodo=q_de[d["competencia"]]))
            rac.append(rr.assign(periodo=q_de[d["competencia"]]))
    ines = o["ines"]
    e = est.set_index("ine")

    def rotula(df):
        df["ine"] = ines[df["ine"].values]
        return df
    x = rotula(pd.concat(ind, ignore_index=True))
    x["faixa_etaria"] = _FAIXA_NOMES[x["fx"].values]
    x["elegivel"] = x["el"].astype(bool)
    x["cnes"] = e["cnes"].reindex(x["ine"]).values
    x["id_ds"] = e["id_ds"].reindex(x["ine"]).values
    x = x.groupby(["competencia", "ine", "cnes", "id_ds", "marcador", "categoria", "faixa_etaria", "elegivel"],
                  as_index=False)["n"].sum()
    return x, rotula(pd.concat(cad, ignore_index=True)), rotula(pd.concat(pai, ignore_index=True)), \
        rotula(pd.concat(rac, ignore_index=True))


def fato_atendimento(cad: pd.DataFrame, fa: pd.DataFrame, ai: pd.DataFrame, dim: pd.DataFrame) -> pd.DataFrame:
    a = ai[["uuid_ficha", "id_atendimento", "id_cidadao"]].merge(fa, on="uuid_ficha")
    a["competencia"] = pd.to_datetime(a["dt_atendimento"]).dt.strftime("%Y%m").astype(int)
    a = a[a["competencia"].isin(dim["competencia"])]
    a["atraso"] = (pd.to_datetime(a["dt_digitacao"]) - pd.to_datetime(a["dt_atendimento"])).dt.days
    g = a.groupby(["competencia", "ine"]).agg(n_atendimentos=("id_atendimento", "size"),
                                              n_cidadaos_atendidos=("id_cidadao", "nunique"),
                                              atraso_medio_digitacao=("atraso", "mean")).reset_index()
    out = g.merge(cad, on=["competencia", "ine"], how="outer")
    for k in ("n_atendimentos", "n_cidadaos_atendidos", "n_cadastrados"):
        out[k] = out[k].fillna(0).astype(int)
    out["atraso_medio_digitacao"] = _arred(out["atraso_medio_digitacao"], 2)
    return out


def _ref_raca(saida: Path, dom: pd.DataFrame) -> pd.DataFrame:
    ref = le_csv(saida / "analitica" / "ref_parametro_complementar.csv")
    ref = ref[(ref["fonte"] == "Gerador IPF") & (ref["variavel"] == "prop_raca_cor")]
    ref = ref.assign(id_bairro=ref["cd_territorio"].str[-3:].astype(int), q=ref["valor"].astype(float),
                     raca_cor=ref["categoria"])
    mic = le_csv(saida / "nucleo" / "microarea.csv")
    setor = le_csv(saida / "nucleo" / "setor_censitario.csv")
    d = dom.merge(mic, on="id_microarea").merge(setor, on="cd_setor")
    peso = d.groupby(["ine", "id_bairro"]).size().rename("peso").reset_index()
    peso["id_bairro"] = peso["id_bairro"].astype(int)
    x = peso.merge(ref[["id_bairro", "raca_cor", "q"]], on="id_bairro")
    x["wq"] = x["peso"] * x["q"]
    r = x.groupby(["ine", "raca_cor"]).agg(wq=("wq", "sum"), peso=("peso", "sum")).reset_index()
    r["q"] = r["wq"] / r["peso"]
    return r[["ine", "raca_cor", "q"]]


def fato_painel(g: pd.DataFrame, rac: pd.DataFrame, dim: pd.DataFrame, ci: pd.DataFrame, acoes: pd.DataFrame,
                ref: pd.DataFrame, est: pd.DataFrame) -> pd.DataFrame:
    fim = dim.groupby("quadrimestre").agg(competencia=("competencia", "max"), dt_fim=("dt_fim", "max"),
                                          dt_inicio=("dt_inicio", "min")).reset_index().rename(
        columns={"quadrimestre": "periodo"})
    den = g["n_dado_real"].replace(0, np.nan)
    p = pd.DataFrame({"ine": g["ine"], "periodo": g["periodo"], "n_dado_real": g["n_dado_real"].astype(int),
                      "prop_sim_os": _arred(g["n_sim"] / den, 5), "prop_nao_os": _arred(g["n_nao"] / den, 5),
                      "prop_ni_os": _arred(g["n_ni"] / den, 5), "prop_sim_ig": _arred(g["n_sim_ig"] / den, 5),
                      "prop_criancas": _arred(g["n_cri"] / g["n_ativos"], 5),
                      "prop_60_mais": _arred(g["n_60"] / g["n_ativos"], 5)})
    r = rac.copy()
    r["p"] = r["c"] / r.groupby(["periodo", "ine"])["c"].transform("sum")
    r = r[r["ine"].isin(ref["ine"])].merge(ref, on=["ine", "raca_cor"], how="left").fillna({"q": 0})
    h = r.assign(bc=np.sqrt(r["p"] * r["q"])).groupby(["periodo", "ine"])["bc"].sum()
    h = pd.Series(_arred(np.sqrt(np.clip(1 - h.values, 0, None)), 5), index=h.index)
    p = p.merge(h.rename("dist_raca_cor_censo").reset_index(), on=["periodo", "ine"], how="left")
    c2 = pd.DataFrame({"ine": ci["ine"].values, "dt": pd.to_datetime(ci["dt_cadastro"]).values,
                       "atraso": (pd.to_datetime(ci["dt_digitacao"]) - pd.to_datetime(ci["dt_cadastro"])).dt.days.values})
    at, na = [], []
    for _, f in fim.iterrows():
        m = c2[(c2["dt"] >= f["dt_inicio"]) & (c2["dt"] <= f["dt_fim"])]
        a = m.groupby("ine")["atraso"].mean().rename("atraso_medio_digitacao").reset_index()
        a["atraso_medio_digitacao"] = _arred(a["atraso_medio_digitacao"], 2)
        at.append(a.assign(periodo=f["periodo"]))
        n_ac = acoes[pd.to_datetime(acoes["dt_acao"]) <= f["dt_fim"]].groupby("ine").size()
        na.append(pd.DataFrame({"ine": n_ac.index, "n_acoes_ate_periodo": n_ac.values, "periodo": f["periodo"]}))
    p = p.merge(pd.concat(at), on=["periodo", "ine"], how="left").merge(pd.concat(na), on=["periodo", "ine"], how="left")
    p["n_acoes_ate_periodo"] = p["n_acoes_ate_periodo"].fillna(0).astype(int)
    e = est.set_index("ine")
    p["id_ds"] = e["id_ds"].reindex(p["ine"]).values
    p["tipo_equipe"] = e["tipo_equipe"].reindex(p["ine"]).values
    p = p.sort_values(["ine", "periodo"]).reset_index(drop=True)
    gp = p.groupby("ine")
    p["prop_sim_os_lag1"] = gp["prop_sim_os"].shift(1)
    p["prop_sim_os_lag2"] = gp["prop_sim_os"].shift(2)
    p["alvo_prop_sim_os"] = gp["prop_sim_os"].shift(-1)
    p["alvo_prop_sim_ig"] = gp["prop_sim_ig"].shift(-1)
    cols = ["ine", "periodo", "id_ds", "tipo_equipe", "n_dado_real", "prop_sim_os", "prop_nao_os", "prop_ni_os",
            "prop_sim_ig", "prop_sim_os_lag1", "prop_sim_os_lag2", "prop_criancas", "prop_60_mais",
            "dist_raca_cor_censo", "atraso_medio_digitacao", "n_acoes_ate_periodo", "alvo_prop_sim_os",
            "alvo_prop_sim_ig"]
    return p[cols]


def monitoramento_usf(cfg, saida: Path, est: pd.DataFrame) -> pd.DataFrame:
    """Réplica de vw_monitoramento_equipe (colunas H–U) por equipe; a soma por USF é direta."""
    D = {"cfg": cfg, "cadastro_individual": le_csv(saida / "nucleo" / "cadastro_individual.csv"),
         "cidadao": le_csv(saida / "nucleo" / "cidadao.csv")}
    v = vigente(D)
    v = v[v["ativo"]]
    e = est.set_index("ine")
    v["cnes"] = e["cnes"].reindex(v["ine"]).values
    v["id_ds"] = e["id_ds"].reindex(v["ine"]).values
    cr = v["crianca"]
    os_ = v["deseja_informar_os"]
    ig = v["deseja_informar_ig"]
    v = v.assign(h=1, i=cr, j=~cr, k=os_ == "1", l_=(os_ == "1") & cr, m=(os_ == "1") & ~cr, o=os_ == "0",
                 q=(os_ == "0") & ~cr, s=os_.isna(), u=os_.isna() & ~cr, igs=(ig == "1") & ~cr,
                 ign=(ig == "0") & ~cr, igi=ig.isna() & ~cr)
    g = v.groupby(["id_ds", "cnes", "ine"])[["h", "i", "j", "k", "l_", "m", "o", "q", "s", "u", "igs", "ign", "igi"]
                                            ].sum().reset_index()
    g = g.rename(columns={"h": "h_ativos", "i": "i_criancas", "j": "j_dado_real", "k": "k_os_sim",
                          "l_": "l_os_sim_crianca", "m": "m_os_sim_dado_real", "o": "o_os_nao",
                          "q": "q_os_nao_dado_real", "s": "s_os_ni", "u": "u_os_ni_dado_real",
                          "igs": "ig_sim_dado_real", "ign": "ig_nao_dado_real", "igi": "ig_ni_dado_real"})
    g["n_os_sim_pct"] = (g["m_os_sim_dado_real"] / g["j_dado_real"].replace(0, np.nan)).round(4)
    g["r_os_nao_pct"] = (g["q_os_nao_dado_real"] / g["j_dado_real"].replace(0, np.nan)).round(4)
    return g


def constroi(saida: Path) -> dict[str, pd.DataFrame]:
    saida = Path(saida)
    cfg = carrega_cfg(saida / "config_usada.yaml")
    n = saida / "nucleo"
    ci, cid = le_csv(n / "cadastro_individual.csv"), le_csv(n / "cidadao.csv")
    cdef, dom = le_csv(n / "cadastro_deficiencia.csv"), le_csv(n / "domicilio.csv")
    acoes = le_csv(n / "acao_formativa.csv")
    fa = le_csv(n / "ficha_atendimento.csv")
    est = _estrutura()
    corte = pd.Timestamp(cfg.periodo.data_corte)
    dim = dim_competencia(fa, corte)
    ind, cad, pai, rac = percorre_competencias(cfg, ci, cid, cdef, dim, est)
    ai = le_csv(n / "atendimento_individual.csv")
    out = {"dim_competencia": dim, "fato_indicador_equipe": ind,
           "fato_atendimento_equipe": fato_atendimento(cad, fa, ai, dim),
           "fato_painel_ml": fato_painel(pai, rac, dim, ci, acoes, _ref_raca(saida, dom), est),
           "monitoramento_equipe": monitoramento_usf(cfg, saida, est)}
    del ai
    destino = saida / "analitica"
    destino.mkdir(parents=True, exist_ok=True)
    for k, df in out.items():
        df.to_parquet(destino / f"{k}.parquet", index=False)
    return out


TEXTO = {"ine", "cnes", "marcador", "categoria", "faixa_etaria"}
CHAVES = ["competencia", "periodo", "ine", "marcador", "categoria", "faixa_etaria", "elegivel"]


def compara(a: pd.DataFrame, b: pd.DataFrame, tol: float = 1e-4) -> list[str]:
    """Diferenças entre duas versões da mesma tabela analítica (SQL × Python)."""
    cols = list(a.columns)

    def norm(df):
        df = df[cols].copy()
        for c in cols:
            if c in TEXTO:
                df[c] = df[c].astype(str)
            elif c == "elegivel":
                df[c] = df[c].astype(bool)
            else:
                df[c] = pd.to_numeric(df[c].astype(object).where(df[c].notna(), np.nan)).astype(float)
        return df.sort_values([k for k in CHAVES if k in cols]).reset_index(drop=True)
    x, y = norm(a), norm(b)
    if len(x) != len(y):
        return [f"linhas: {len(x)} × {len(y)}"]
    erros = []
    for c in cols:
        if c in TEXTO or c == "elegivel":
            if not (x[c].values == y[c].values).all():
                erros.append(f"{c}: valores diferentes")
        else:
            nn = int((x[c].isna() != y[c].isna()).sum())
            d = np.nanmax(np.abs(x[c].values - y[c].values)) if x[c].notna().any() else 0.0
            if nn or d > tol:
                erros.append(f"{c}: dif. máx. {d:.6f}, nulos divergentes {nn}")
    return erros
