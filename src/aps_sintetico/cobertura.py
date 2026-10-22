"""Passo 3 – adscrição territorial, cobertura e data do primeiro cadastro.

O ACS cadastra domicílios, então a unidade de seleção é o domicílio (amostragem por
conglomerados). Em cada equipe:
    logit P(cadastrado_h) = alpha_e + beta_renda * renda_pc_h + beta_negro * negro_ref_h
com alpha_e resolvido por bisseção para que o número esperado de pessoas cadastradas
iguale a meta da equipe (calibração do intercepto); o sorteio é de Poisson.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import optimize, special

from .rng import fluxo


def gera_populacoes_especiais(cfg, mundo) -> None:
    """Pessoas em situação de rua (eCR) e privadas de liberdade (eAPP): não são residentes
    de domicílio e não vêm do IPF; quantidades por equipe são premissas."""
    eq = mundo.equipes
    pes = mundo.pessoas
    ref = np.datetime64(cfg.periodo.referencia_censo)
    novas = []
    pid0 = int(pes["pid"].max()) + 1
    for _, e in eq[~eq["territorial"]].iterrows():
        rng = fluxo(cfg.semente, "especiais", int(e["ine"]))
        n = max(1, int(round(e["meta_escala1"] * cfg.escala)))
        eapp = e["tipo_equipe"] == 74
        idade = rng.integers(18, 46 if eapp else 66, n)
        sexo = (rng.random(n) >= (0.93 if eapp else 0.80)).astype(np.int8)
        raca = rng.choice([1, 2, 4], n, p=[0.25, 0.20, 0.55]).astype(np.int8)
        dob = ref - (idade * 365.25 + rng.random(n) * 365.25).astype(int).astype("timedelta64[D]")
        novas.append(pd.DataFrame({"pid": pid0 + np.arange(n), "bairro": e["id_bairro"], "ds": e["id_ds"],
                                   "sexo": sexo, "idade_ref": idade.astype(np.int16), "dob": dob, "raca": raca,
                                   "residente": False, "dom": -1, "ref": False, "equipe": e["ine"]}))
        pid0 += n
    if novas:
        mundo.pessoas = pd.concat([pes, *novas], ignore_index=True)


def adscreve(cfg, mundo) -> None:
    """Liga cada domicílio a uma equipe territorial e a uma microárea."""
    dom, eq = mundo.domicilios, mundo.equipes
    terr = eq[eq["territorial"]]
    teto = float(cfg.cobertura.teto_equipe)
    dom["equipe"] = ""
    for d, g in dom.groupby("ds"):
        rng = fluxo(cfg.semente, "adscricao", int(d))
        eq_d = terr[terr["id_ds"] == d]
        cap = (eq_d.set_index("ine")["meta_escala1"] * cfg.escala / teto).to_dict()   # pessoas
        livre = dict(cap)
        por_bairro = {b: list(x["ine"]) for b, x in eq_d.groupby("id_bairro")}
        sobra = []
        # 1) cada equipe recebe domicílios do próprio bairro até a capacidade do território
        for b, gb in g.groupby("bairro"):
            ordem = rng.permutation(gb.index.values)
            ines = por_bairro.get(b, [])
            if not ines:
                sobra.extend(ordem)
                continue
            w = np.array([cap[i] for i in ines])
            esc = np.array(ines)[rng.choice(len(ines), len(ordem), p=w / w.sum())]
            for h, i in zip(ordem, esc):
                tam = dom.at[h, "n_mor"]
                if livre[i] >= tam:
                    dom.at[h, "equipe"] = i
                    livre[i] -= tam
                else:
                    sobra.append(h)
        # 2) capacidade ociosa absorve bairros vizinhos (sem UBS ou excedentes) do mesmo DS
        sobra = rng.permutation(np.array(sobra, dtype=int))
        ines = np.array(list(cap))
        for h in sobra:
            tam = dom.at[h, "n_mor"]
            folga = np.array([livre[i] for i in ines])
            ok = folga >= tam
            if ok.any():
                i = ines[ok][rng.choice(ok.sum(), p=folga[ok] / folga[ok].sum())]
                livre[i] -= tam
            else:                                     # território descoberto: adscrito mas fora da capacidade
                b = dom.at[h, "bairro"]
                cand = por_bairro.get(b, list(ines))
                i = cand[rng.integers(len(cand))]
            dom.at[h, "equipe"] = i
    nmic = eq.set_index("ine")["n_microareas"]
    rng = fluxo(cfg.semente, "microarea_domicilio")
    k = nmic.reindex(dom["equipe"]).values
    dom["microarea"] = [f"{int(x):02d}" for x in (rng.random(len(dom)) * k).astype(int) + 1]


def seleciona_cadastrados(cfg, mundo) -> None:
    dom, eq, pes = mundo.domicilios, mundo.equipes, mundo.pessoas
    c = cfg.cobertura
    res = dom["tipo_imovel"] == 1
    negro_ref = pes.set_index("pid")["raca"].reindex(dom["ref_pid"]).isin([2, 4]).values
    dom["cadastrado"] = False
    alphas = {}
    for ine, g in dom[res].groupby("equipe"):
        rng = fluxo(cfg.semente, "cobertura", int(ine))
        e = eq.set_index("ine").loc[ine]
        tam = g["n_mor"].values
        meta = min(e["meta_escala1"] * cfg.escala, float(c.teto_equipe) * tam.sum())
        lin = float(c.beta_renda_pc) * g["renda_pc"].fillna(0).values + float(c.beta_negro) * negro_ref[g.index]
        f = lambda a: (special.expit(a + lin) * tam).sum() - meta  # noqa: E731
        a = optimize.brentq(f, -30, 30) if 0 < meta < tam.sum() else (30.0 if meta >= tam.sum() else -30.0)
        alphas[ine] = a
        dom.loc[g.index, "cadastrado"] = rng.random(len(g)) < special.expit(a + lin)
    rng = fluxo(cfg.semente, "cobertura_nr")
    nr = ~res
    dom.loc[nr, "cadastrado"] = rng.random(nr.sum()) < 0.6
    mundo.verdade["alpha_cobertura"] = alphas
    # pessoas: herdam o domicílio, com omissão eventual de morador
    rng = fluxo(cfg.semente, "omissao")
    d = dom.set_index("hid")
    tem_dom = pes["dom"] >= 0
    pes.loc[tem_dom, "equipe"] = d["equipe"].reindex(pes.loc[tem_dom, "dom"]).values
    pes.loc[tem_dom, "microarea"] = d["microarea"].reindex(pes.loc[tem_dom, "dom"]).values
    cad = np.zeros(len(pes), dtype=bool)
    cad[tem_dom.values] = d["cadastrado"].reindex(pes.loc[tem_dom, "dom"]).values.astype(bool)
    cad &= ~((rng.random(len(pes)) < float(c.omissao_morador)) & ~pes["ref"].values)
    cad[~tem_dom.values] = True                      # eCR e eAPP
    pes["cadastrado"] = cad
    pes.loc[~tem_dom, "microarea"] = np.where(
        pes.loc[~tem_dom, "equipe"].map(eq.set_index("ine")["tipo_equipe"]) == 74, "01", None)


def datas_primeiro_cadastro(cfg, mundo) -> None:
    """Primeiro cadastro: legado (antes de 2023) nas equipes já ativas; dentro da série para
    o restante e para equipes novas, com rampa exponencial após a ativação."""
    dom, eq, pes = mundo.domicilios, mundo.equipes, mundo.pessoas
    p = cfg.periodo
    inicio, corte, leg = (pd.Timestamp(p.inicio), pd.Timestamp(p.data_corte), pd.Timestamp(p.inicio_legado))
    ativ = eq.set_index("ine")["dt_ativacao"]
    rng = fluxo(cfg.semente, "datas_cadastro")

    def sorteia(ine_arr):
        n = len(ine_arr)
        a = pd.to_datetime(ativ.reindex(ine_arr).values)
        a = a.where(~pd.isna(a), leg)
        data = np.empty(n, dtype="datetime64[D]")
        antiga = (a <= inicio)
        legado = antiga & (rng.random(n) < float(cfg.cobertura.prop_legado))
        ini_l = np.maximum(a.values.astype("datetime64[D]"), np.datetime64(leg.date()))
        span = (np.datetime64((inicio - pd.Timedelta(days=1)).date()) - ini_l).astype(int).clip(1)
        data[legado] = ini_l[legado] + (rng.random(legado.sum()) * span[legado]).astype(int)
        serie = antiga & ~legado
        span_s = (corte - inicio).days
        data[serie] = np.datetime64(inicio.date()) + (rng.random(serie.sum()) * span_s).astype(int)
        nova = ~antiga
        rampa = rng.exponential(float(cfg.cobertura.rampa_meses) * 30.4, nova.sum()).astype(int)
        data[nova] = a.values.astype("datetime64[D]")[nova] + rampa
        return data

    cad_dom = dom["cadastrado"].values
    dom["dt_cadastro"] = pd.NaT
    dom.loc[cad_dom, "dt_cadastro"] = sorteia(dom.loc[cad_dom, "equipe"].values)
    tem_dom = pes["dom"] >= 0
    d_dom = dom.set_index("hid")["dt_cadastro"]
    dt = pd.Series(pd.NaT, index=pes.index, dtype="datetime64[ns]")
    dt[tem_dom] = pd.to_datetime(d_dom.reindex(pes.loc[tem_dom, "dom"]).values)
    jitter = pd.to_timedelta(rng.integers(0, 31, len(pes)), unit="D")
    dt = dt + jitter
    esp = ~tem_dom
    dt[esp] = pd.to_datetime(sorteia(pes.loc[esp, "equipe"].values))
    dob = pd.to_datetime(pes["dob"].values)
    dt = pd.Series(np.maximum(dt.values, (dob + pd.Timedelta(days=15)).values), index=pes.index)
    dt[~pes["cadastrado"]] = pd.NaT
    fora = dt > corte
    # perda por rampa: cadastros sorteados para depois da data de corte (equipes novas, legado)
    sel = pes["cadastrado"] & pes["residente"]
    perda = (fora & sel).groupby(pes["ds"]).sum() / sel.groupby(pes["ds"]).sum().replace(0, np.nan)
    mundo.diagnostico.setdefault("cobertura", {})["perda_rampa_ds"] = perda.fillna(0).round(5).to_dict()
    pes["cadastrado"] = pes["cadastrado"] & ~fora
    dt[fora] = pd.NaT
    pes["dt_reg"] = dt.values.astype("datetime64[D]")
    dom.loc[dom["dt_cadastro"] > corte, "cadastrado"] = False
