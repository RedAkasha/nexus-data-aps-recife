"""Passo 1 – estrutura territorial e rede (DS, bairros, unidades e equipes reais do CNES).

Microáreas: ⌈meta da equipe na escala 1 / 750⌉, limitado a 12 (PNAB 2011: até 750
pessoas por ACS e até 12 ACS por equipe). Profissionais fictícios: um ACS por
microárea (CBO 515105), um médico (225142) e um enfermeiro (223565) por equipe.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import optimize

from . import identificadores as I
from . import parametros as P
from .rng import fluxo

TERRITORIAIS = (70, 76)        # eSF e eAP
CBO_ACS, CBO_MEDICO, CBO_ENFERMEIRO = "515105", "225142", "223565"


def gera_estrutura(cfg, mundo) -> None:
    est = P.estrutura()
    mundo.distritos = est["ds"]
    mundo.bairros = est["bairro"]
    mundo.unidades = est["unidade"][est["unidade"]["id_ds"].isin(cfg.distritos)].reset_index(drop=True)
    eq = est["equipe"][est["equipe"]["id_ds"].isin(cfg.distritos)].copy().reset_index(drop=True)
    eq["territorial"] = eq["tipo_equipe"].isin(TERRITORIAIS)
    eq["dt_ativacao"] = pd.to_datetime(eq["dt_ativacao"])
    mundo.equipes = eq
    _metas(cfg, mundo, est)


def _metas(cfg, mundo, est) -> None:
    """Meta de cadastrados por equipe (escala 1): K resolvido para a cobertura municipal,
    limitada pelo teto do território de cada DS (Plano, Tabela 4)."""
    pop_b = P.bairros_censo()
    ba = est["bairro"].set_index("id_bairro")
    pop_ds = pop_b["pop"].groupby(ba.loc[pop_b.index, "id_ds"]).sum()
    todas = est["equipe"][est["equipe"]["tipo_equipe"].isin(TERRITORIAIS)]
    n_ds = todas.groupby("id_ds").size().reindex(pop_ds.index, fill_value=0)
    cob, teto = float(cfg.cobertura.municipal), float(cfg.cobertura.teto_equipe)
    alvo = cob * pop_ds.sum()
    f = lambda k: np.minimum(pop_ds.values * teto, n_ds.values * k).sum() - alvo  # noqa: E731
    k = optimize.brentq(f, 100, 50000)
    meta_ds = pd.Series(np.minimum(pop_ds.values * teto, n_ds.values * k), index=pop_ds.index)
    mundo.diagnostico["cobertura"] = {"capacidade_por_equipe": round(k, 1),
                                      "cobertura_ds": (meta_ds / pop_ds).round(3).to_dict()}
    eq = mundo.equipes
    rng = fluxo(cfg.semente, "metas_equipe")
    eq["meta_escala1"] = 0.0
    for d, g in eq[eq["territorial"]].groupby("id_ds"):
        ruido = rng.lognormal(0, float(cfg.cobertura.dp_meta_equipe), len(g))
        eq.loc[g.index, "meta_escala1"] = meta_ds[d] / n_ds[d] * ruido / ruido.mean()
    eq.loc[eq["tipo_equipe"] == 73, "meta_escala1"] = float(cfg.cobertura.ecr_pessoas)
    eq.loc[eq["tipo_equipe"] == 74, "meta_escala1"] = float(cfg.cobertura.eapp_pessoas)
    m = np.ceil(eq["meta_escala1"] / float(cfg.cobertura.pessoas_por_acs)).clip(1, cfg.cobertura.max_microareas)
    m[~eq["territorial"]] = 1
    eq["n_microareas"] = m.astype(int)


def gera_microareas_profissionais(cfg, mundo) -> None:
    eq = mundo.equipes
    linhas = []
    for _, e in eq.iterrows():
        for k in range(1, int(e["n_microareas"]) + 1):
            linhas.append((e["ine"], f"{k:02d}"))
    mundo.microareas = pd.DataFrame(linhas, columns=["ine", "codigo_microarea"])
    rng = fluxo(cfg.semente, "profissionais")
    prof = []
    for _, e in eq.iterrows():
        if e["territorial"]:
            cbos = [CBO_ACS] * int(e["n_microareas"]) + [CBO_MEDICO, CBO_ENFERMEIRO]
            micro = [f"{k:02d}" for k in range(1, int(e["n_microareas"]) + 1)] + [None, None]
        else:
            cbos, micro = [CBO_MEDICO, CBO_ENFERMEIRO], [None, None]
        for c, mi in zip(cbos, micro):
            prof.append((e["ine"], c, mi))
    lot = pd.DataFrame(prof, columns=["ine", "cbo", "microarea"])
    lot["cns_profissional"] = I.cnss(rng, len(lot))
    sexo = (rng.random(len(lot)) < np.where(lot["cbo"] == CBO_MEDICO, 0.55, 0.80)).astype(int)
    lot["nome_profissional"] = I.nomes(rng, sexo)
    mundo.lotacoes = lot
