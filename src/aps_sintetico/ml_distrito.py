"""ML por Distrito Sanitário: quanto de "Sim" (orientação sexual) cada DS terá no PRÓXIMO quadrimestre?

Serve para priorizar distritos (liga com as bolas vermelhas do mapa). Regressão em painel DS × quadrimestre.
Mesmas regras anti-vazamento de ml.py: variáveis só até o período t, alvo = Sim(t+1); teste = últimos 2 períodos
com alvo, estritamente depois do treino; escolha por walk-forward (janela expansível); pré-processamento dentro do
Pipeline; hiperparâmetros fixos a priori; teste usado uma vez. Amostra pequena (8 DS × ~11 períodos): por isso há
linhas de base (persistência, média móvel) e a escolha final penaliza complexidade (regra de 1 erro-padrão).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeRegressor

NUM = ["sim", "nao", "ni", "sim_ig", "lag1", "lag2", "mm3", "atraso", "acoes"]
ORDEM = {"persistencia": 0, "media_movel_3": 0, "ridge": 1, "arvore": 2, "floresta": 3}
NOMES = {"persistencia": "Persistência", "media_movel_3": "Média móvel (3)", "ridge": "Regressão ridge",
         "arvore": "Árvore de decisão", "floresta": "Floresta aleatória"}


def painel(saida: Path) -> pd.DataFrame:
    d = pd.read_parquet(Path(saida) / "analitica" / "fato_painel_ml.parquet")
    d = d[d["n_dado_real"] >= 20].copy()
    w = d["n_dado_real"].astype(float)
    def med(c):
        return (d[c].astype(float) * w).groupby([d["id_ds"], d["periodo"]]).sum() / w.groupby([d["id_ds"], d["periodo"]]).sum()
    g = pd.DataFrame({"sim": med("prop_sim_os"), "nao": med("prop_nao_os"), "ni": med("prop_ni_os"), "sim_ig": med("prop_sim_ig"),
                      "atraso": d.groupby(["id_ds", "periodo"])["atraso_medio_digitacao"].mean(),
                      "acoes": d.groupby(["id_ds", "periodo"])["n_acoes_ate_periodo"].sum(),
                      "equipes": d.groupby(["id_ds", "periodo"])["ine"].nunique()}).reset_index().sort_values(["id_ds", "periodo"])
    a = g.groupby("id_ds")["sim"]
    g["lag1"], g["lag2"] = a.shift(1), a.shift(2)
    g["mm3"] = g[["sim", "lag1", "lag2"]].mean(axis=1)
    g["alvo"] = a.shift(-1)
    return g


def pipe(est):
    pre = ColumnTransformer([("n", Pipeline([("i", SimpleImputer(strategy="median")), ("e", StandardScaler())]), NUM),
                             ("c", OneHotEncoder(handle_unknown="ignore"), ["id_ds"])])
    return Pipeline([("pre", pre), ("m", est)])


def treina(saida: Path, n_teste: int = 2, semente: int = 20261022) -> pd.DataFrame:
    saida = Path(saida)
    g = painel(saida)
    d = g[g["alvo"].notna()]
    per = sorted(d["periodo"].unique())
    p_te, p_tr = per[-n_teste:], per[:-n_teste]
    assert max(p_tr) < min(p_te), "VAZAMENTO: treino não é anterior ao teste"
    tr, te = d[d["periodo"].isin(p_tr)], d[d["periodo"].isin(p_te)]
    ests = {"ridge": Ridge(alpha=3.0), "arvore": DecisionTreeRegressor(max_depth=3, min_samples_leaf=5, random_state=semente),
            "floresta": RandomForestRegressor(n_estimators=300, min_samples_leaf=3, random_state=semente, n_jobs=-1)}
    X = NUM + ["id_ds"]
    def prev(nome, a, b):
        if nome == "persistencia":
            return b["sim"].values
        if nome == "media_movel_3":
            return b["mm3"].values
        return clone(pipe(ests[nome])).fit(a[X], a["alvo"]).predict(b[X])
    cv, res = {}, []
    for nome in ORDEM:
        erros = []
        for i in range(4, len(p_tr)):
            a, b = tr[tr["periodo"].isin(p_tr[:i])], tr[tr["periodo"] == p_tr[i]]
            erros.append(mean_absolute_error(b["alvo"], prev(nome, a, b)))
        cv[nome] = (float(np.mean(erros)), float(np.std(erros, ddof=1) / np.sqrt(len(erros))))
    cand = {k: v for k, v in cv.items() if k not in ("persistencia", "media_movel_3")}
    melhor = min(cand, key=lambda k: cand[k][0])
    elegiveis = [k for k, v in cand.items() if v[0] <= cand[melhor][0] + cand[melhor][1]]
    escolhido = min(elegiveis, key=lambda k: ORDEM[k])
    for nome in ORDEM:
        p = prev(nome, tr, te)
        res.append({"modelo": nome, "nome": NOMES[nome], "cv_mae_pp": cv[nome][0] * 100, "cv_ep_pp": cv[nome][1] * 100,
                    "teste_mae_pp": mean_absolute_error(te["alvo"], p) * 100, "escolhido": nome == escolhido})
    res = pd.DataFrame(res)
    ult = g[g["periodo"] == g["periodo"].max()].copy()
    final = clone(pipe(ests[escolhido])).fit(d[X], d["alvo"])
    ult["sim_previsto"] = final.predict(ult[X])
    ult["variacao_pp"] = (ult["sim_previsto"] - ult["sim"]) * 100
    ult["ordem_necessidade"] = ult["sim_previsto"].rank(method="first").astype(int)
    dest = saida / "ml"
    dest.mkdir(parents=True, exist_ok=True)
    res.to_csv(dest / "comparacao_distritos.csv", index=False)
    ult[["id_ds", "periodo", "equipes", "sim", "sim_previsto", "variacao_pp", "ordem_necessidade"]].to_parquet(dest / "distritos.parquet", index=False)
    (dest / "resumo_distritos.json").write_text(json.dumps({
        "escolhido": escolhido, "nome": NOMES[escolhido], "periodos_treino": list(map(int, p_tr)), "periodos_teste": list(map(int, p_te)),
        "n_treino": len(tr), "n_teste": len(te), "elegiveis_1ep": elegiveis, "aviso": "amostra pequena: 8 distritos"}, indent=2), encoding="utf-8")
    return res
