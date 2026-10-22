"""Passo 7 – produção da FAI (atendimentos individuais) dos cadastrados ativos.

Contagem mensal de Poisson–Gama (binomial negativa): Y_im ~ Poisson(lambda_im * g_i),
g_i ~ Gama(k, 1/k) (heterogeneidade individual), lambda_im = taxa(idade, sexo)/12 ×
sazonalidade(mês) × oferta da equipe × razões de taxa de grupo (LGB/trans e PcD, cenários).
Pré-natal: cada gestação de mãe cadastrada recebe um número de consultas sorteado pela
distribuição por raça da mãe (boletim SESAU, Tabela 1), com CIAP W78 e CID-10 Z34.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import parametros as P
from .config import RAIZ
from .dinamica import _d, _idade
from .rng import fluxo
from .territorio import CBO_ENFERMEIRO, CBO_MEDICO

# perfil de problemas por faixa etária [P] (ordem de grandeza da APS)
_PERFIS = {
    "0-9": {"A98": .30, "R74": .20, "R05": .08, "D73": .07, "A03": .07, "H71": .05, "R78": .05, "S74": .05,
            "R96": .04, "D01": .04, "F70": .05},
    "10-19": {"A98": .25, "R74": .15, "W14": .08, "W11": .05, "S74": .07, "N01": .07, "D01": .07, "P74": .06,
              "R96": .05, "U71": .05, "T83": .05, "D73": .05},
    "20-59": {"A98": .18, "K86": .14, "T90": .06, "P74": .07, "P76": .05, "L03": .08, "R74": .07, "N01": .05,
              "U71": .05, "W14": .05, "T93": .04, "T82": .04, "D01": .04, "L84": .03, "N89": .03, "Y99": .02},
    "60+": {"K86": .28, "T90": .14, "A98": .10, "T93": .07, "K87": .05, "L03": .06, "L15": .05, "P76": .04,
            "P74": .04, "U71": .04, "R74": .05, "L84": .04},
}
_SO_F = {"W14", "W11", "W78", "W84"}
_SO_M = {"Y99"}


def _faixa_taxa(idade: np.ndarray) -> np.ndarray:
    return np.searchsorted([1, 5, 10, 20, 40, 60, 80], idade, side="right")


def _taxas(cfg) -> np.ndarray:
    """taxa anual [faixa 0..7, sexo 0/1]."""
    t = cfg.atendimentos.taxas_anuais
    chaves = ["0", "1-4", "5-9", "10-19", "20-39", "40-59", "60-79", "80+"]
    out = np.zeros((8, 2))
    for i, k in enumerate(chaves):
        v = t[k]
        out[i] = [v["M"], v["F"]] if isinstance(v, dict) else [v, v]
    return out


def _ciap_cid():
    dom = json.loads((RAIZ / "dados" / "dominios.json").read_text(encoding="utf-8"))
    cids = {c[0] for c in dom["dom_cid10"]}
    rel = {}
    for a, b in dom["relacao_ciap_cid"]:
        if b in cids and a not in rel:
            rel[a] = b
    return rel


def ativos_no_mes(cfg, mundo, d_fim: np.datetime64):
    pes = mundo.pessoas
    ini1, fim1 = _d(pes["dt_reg"]), _d(pes["fim1"])
    ini2, fim2 = _d(pes["ini2"]), _d(pes["fim2"])
    a1 = pes["seg1"].values & (ini1 <= d_fim) & (fim1 >= d_fim - 27)
    a2 = pes["seg2"].values & (ini2 <= d_fim) & (fim2 >= d_fim - 27)
    idx = np.nonzero(a1 | a2)[0]
    em2 = a2[idx]
    ine = np.where(em2, pes["equipe2"].values[idx], pes["equipe"].values[idx])
    lo = np.where(em2, ini2[idx], ini1[idx])
    hi = np.where(em2, fim2[idx], fim1[idx])
    return idx, ine, lo, hi


def gera_atendimentos(cfg, mundo) -> None:
    pes, eq = mundo.pessoas, mundo.equipes
    a = cfg.atendimentos
    rng = fluxo(cfg.semente, "atendimentos")
    taxa = _taxas(cfg)
    k = float(a.forma_gama)
    gama = rng.gamma(k, 1 / k, len(pes))
    oferta = pd.Series(rng.lognormal(0, float(a.dp_oferta_equipe), len(eq)), index=eq["ine"].values)
    rr = np.where(pes["lgb"].values | pes["trans_nb"].values, float(a.rr_lgb_trans), 1.0) * \
        np.where(pes["def_bits"].values > 0, float(a.rr_pcd), 1.0)
    saz = {int(k_): float(v) for k_, v in a.sazonalidade.items()}
    dob = _d(pes["dob"])
    sexo = pes["sexo"].values
    blocos = []
    for m in mundo.meses:
        d0 = np.datetime64(m.date())
        d_fim = np.datetime64((m + pd.offsets.MonthEnd(0)).date())
        idx, ine, lo, hi = ativos_no_mes(cfg, mundo, d_fim)
        idade = np.clip(_idade(dob[idx], np.full(len(idx), d0)), 0, 110)
        lam = taxa[_faixa_taxa(idade), sexo[idx]] / 12 * saz.get(m.month, 1.0) * oferta.reindex(ine).values \
            * gama[idx] * rr[idx]
        n = rng.poisson(lam)
        q = n > 0
        if not q.any():
            continue
        rep = np.repeat(np.arange(q.sum()), n[q])
        # dia sorteado dentro do mês e do período de cadastro ativo (nunca antes do nascimento)
        ini_d = np.maximum(np.maximum(lo[q], dob[idx][q]), d0)[rep]
        fim_d = np.minimum(hi[q], d_fim)[rep]
        span = np.maximum((fim_d - ini_d).astype(int), 0) + 1
        dia = ini_d + (rng.random(len(rep)) * span).astype(int)
        blocos.append(pd.DataFrame({"pos": idx[q][rep], "ine": ine[q][rep], "data": dia, "prenatal": False}))
    # pré-natal
    nas = mundo.verdade.get("nascimentos")
    if nas is not None and len(nas):
        blocos.append(_prenatal(cfg, mundo, nas, rng))
    at = pd.concat(blocos, ignore_index=True)
    # óbito: nenhum atendimento após a morte
    dto = _d(pes["dt_obito"])[at["pos"].values]
    at = at[np.isnat(dto) | (at["data"].values.astype("datetime64[D]") <= dto)].reset_index(drop=True)
    _campos(cfg, mundo, at, rng)


def _prenatal(cfg, mundo, nas: pd.DataFrame, rng) -> pd.DataFrame:
    pes = mundo.pessoas
    pos_mae = pd.Index(pes["pid"]).get_indexer(nas["mae_pid"].values)
    tab = P.consultas_prenatal()
    faixas = {"0": (0, 0), "1-3": (1, 3), "4-6": (4, 6), "7+": (7, 12)}
    inicio = np.datetime64(cfg.periodo.inicio)
    linhas = []
    for i, (pm, dob, rm) in enumerate(zip(pos_mae, nas["dob"].values.astype("datetime64[D]"), nas["raca_mae"].values)):
        col = "negra" if rm in (2, 4) else "nao_negra"
        pr = tab[col] / tab[col].sum()
        f = rng.choice(pr.index.values, p=pr.values)
        lo, hi = faixas[f]
        n = int(rng.integers(lo, hi + 1))
        if n == 0:
            continue
        ini_g = dob - 266 + int(rng.integers(42, 120))       # captação entre 6 e 17 semanas
        datas = np.sort(ini_g + rng.integers(0, max((dob - 7 - ini_g).astype(int), 1), n))
        datas = datas[datas >= inicio]
        if not len(datas):
            continue
        linhas.append(pd.DataFrame({"pos": pm, "data": datas, "prenatal": True}))
    if not linhas:
        return pd.DataFrame(columns=["pos", "ine", "data", "prenatal"])
    pn = pd.concat(linhas, ignore_index=True)
    # equipe da mãe na data; só conta se a mãe estava com cadastro ativo
    d = pn["data"].values.astype("datetime64[D]")
    p = pes.iloc[pn["pos"].values]
    a1 = p["seg1"].values & (_d(p["dt_reg"]) <= d) & (_d(p["fim1"]) >= d)
    a2 = p["seg2"].values & (_d(p["ini2"]) <= d) & (_d(p["fim2"]) >= d)
    pn["ine"] = np.where(a2, p["equipe2"].values, p["equipe"].values)
    return pn[a1 | a2].reset_index(drop=True)


def _campos(cfg, mundo, at: pd.DataFrame, rng) -> None:
    eq, lot = mundo.equipes, mundo.lotacoes
    a = cfg.atendimentos
    n = len(at)
    tipo_eq = eq.set_index("ine")["tipo_equipe"].reindex(at["ine"]).values
    pn = at["prenatal"].values.astype(bool)
    at["tipo_atendimento"] = np.where(pn, 1, rng.choice([1, 2, 4, 5, 6], n, p=[.35, .25, .10, .25, .05]))
    loc = rng.choice([1, 4, 6], n, p=[.90, .07, .03])
    at["local_atendimento"] = np.select([tipo_eq == 73, tipo_eq == 74], [3, 9], loc)
    turno = rng.choice([1, 2, 3], n, p=[.55, .42, .03])
    at["turno"] = turno
    hora = np.select([turno == 1, turno == 2], [7 * 60 + rng.integers(0, 270, n), 13 * 60 + rng.integers(0, 210, n)],
                     18 * 60 + rng.integers(0, 120, n))
    at["dt_hora_inicio"] = pd.to_datetime(at["data"].values.astype("datetime64[D]")) + pd.to_timedelta(hora, unit="m")
    # profissional: médico ou enfermeiro da equipe (pré-natal alterna)
    cbo = np.where(rng.random(n) < 0.55, CBO_MEDICO, CBO_ENFERMEIRO)
    prof = lot[lot["cbo"].isin([CBO_MEDICO, CBO_ENFERMEIRO])].set_index(["ine", "cbo"])["cns_profissional"]
    prof = prof[~prof.index.duplicated()]
    at["cns_profissional"] = prof.reindex(list(zip(at["ine"], cbo))).values
    # fichas: lote por profissional e dia (até 99 atendimentos)
    at = at.sort_values(["cns_profissional", "data", "dt_hora_inicio"]).reset_index(drop=True)
    grp = at.groupby(["cns_profissional", "ine", "data"]).ngroup()
    ordem = at.groupby(grp).cumcount()
    lote = ordem // int(a.max_por_ficha)
    at["ficha"] = pd.factorize(grp.values.astype(np.int64) * 1000 + lote.values)[0]
    at["nu_atendimento"] = (ordem % int(a.max_por_ficha) + 1).astype(np.int16)
    fichas = at.drop_duplicates("ficha")[["ficha", "cns_profissional", "ine", "data"]].reset_index(drop=True)
    atraso = rng.exponential(eq.set_index("ine")["atraso_medio"].reindex(fichas["ine"]).values).astype(int)
    fichas["dt_digitacao"] = fichas["data"].values.astype("datetime64[D]") + atraso
    lim = np.datetime64(pd.Timestamp(cfg.periodo.dt_geracao).date())
    fichas = fichas[fichas["dt_digitacao"].values < lim].reset_index(drop=True)
    at = at[at["ficha"].isin(fichas["ficha"])].reset_index(drop=True)
    at["id_at"] = np.arange(len(at))
    mundo.fichas, mundo.atendimentos = fichas, at
    mundo.problemas = _problemas(cfg, mundo, at, rng)


def _problemas(cfg, mundo, at: pd.DataFrame, rng) -> pd.DataFrame:
    pes = mundo.pessoas
    a = cfg.atendimentos
    rel = _ciap_cid()
    idade = _idade(_d(pes["dob"])[at["pos"].values], at["data"].values.astype("datetime64[D]"))
    sexo = pes["sexo"].values[at["pos"].values]
    faixa = np.select([idade < 10, idade < 20, idade < 60], ["0-9", "10-19", "20-59"], "60+")
    n_extra = rng.poisson(float(a.problemas_extra_media), len(at))
    out_at, out_ciap = [], []
    for f, perfil in _PERFIS.items():
        for s in (0, 1):
            m = np.nonzero((faixa == f) & (sexo == s) & ~at["prenatal"].values.astype(bool))[0]
            if not len(m):
                continue
            cods = [c for c in perfil if not ((s == 0 and c in _SO_F) or (s == 1 and c in _SO_M))]
            pr = np.array([perfil[c] for c in cods])
            pr = pr / pr.sum()
            k = 1 + np.minimum(n_extra[m], len(cods) - 1)
            for kk in np.unique(k):
                mm = m[k == kk]
                # sorteio sem reposição (Gumbel-top-k)
                g = np.log(pr)[None, :] - np.log(-np.log(rng.random((len(mm), len(cods)))))
                top = np.argsort(-g, axis=1)[:, :kk]
                out_at.append(np.repeat(at["id_at"].values[mm], kk))
                out_ciap.append(np.array(cods)[top].ravel())
    pnm = at["prenatal"].values.astype(bool)
    out_at.append(at["id_at"].values[pnm])
    out_ciap.append(np.full(pnm.sum(), "W78"))
    pr = pd.DataFrame({"id_at": np.concatenate(out_at), "ciap": np.concatenate(out_ciap)})
    pr = pr.sort_values("id_at", kind="stable").reset_index(drop=True)
    pr["nu_item"] = pr.groupby("id_at").cumcount() + 1
    cid = pr["ciap"].map(rel)
    usa = (rng.random(len(pr)) < float(a.prob_cid)) | (pr["ciap"] == "W78")
    pr["cid10"] = np.where(usa & cid.notna(), cid, None)
    return pr
