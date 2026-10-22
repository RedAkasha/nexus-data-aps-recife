"""Etapa 10 – aprendizado de máquina supervisionado (regressão) sobre fato_painel_ml.

Problema: prever a proporção de "Sim" (orientação sexual, dado real) de cada equipe no
quadrimestre seguinte com o que se sabe até o fim do quadrimestre atual (RN18).
Partição temporal: treino nos períodos iniciais, teste nos dois últimos períodos com alvo;
validação cruzada em janela expansível (walk-forward) dentro do treino para escolher o modelo.
Linhas de base: persistência (alvo = valor atual) e média móvel dos três últimos períodos.
Cada modelo é treinado de dois modos: no nível do alvo e na variação (alvo − valor atual),
que soma a previsão à persistência.
Modelos: KNN, regressão linear, ridge, árvore de decisão, floresta aleatória e gradient boosting
(scikit-learn), com o mesmo pré-processamento (imputação + padronização) num Pipeline.
Métricas: MAE, RMSE, R² (geral e por DS) e precisão@k na identificação das equipes de pior
desempenho futuro. Se o MLflow estiver instalado, cada modelo vira uma execução registrada
(parâmetros, métricas e o pipeline), no servidor de MLFLOW_TRACKING_URI ou em ./mlflow.db (SQLite).
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.neighbors import KNeighborsRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeRegressor

log = logging.getLogger("aps_sintetico")

NUM = ["prop_sim_os", "prop_nao_os", "prop_ni_os", "prop_sim_ig", "prop_sim_os_lag1", "prop_sim_os_lag2",
       "prop_criancas", "prop_60_mais", "dist_raca_cor_censo", "atraso_medio_digitacao", "n_acoes_ate_periodo",
       "log_n", "media_movel_3"]
CAT = ["id_ds", "tipo_equipe"]
ALVO = "alvo_prop_sim_os"


def modelos(semente: int) -> dict:
    return {
        "knn": KNeighborsRegressor(n_neighbors=15, weights="distance"),
        "linear": LinearRegression(),
        "ridge": Ridge(alpha=1.0),
        "arvore": DecisionTreeRegressor(max_depth=5, min_samples_leaf=20, random_state=semente),
        "floresta": RandomForestRegressor(n_estimators=300, min_samples_leaf=5, n_jobs=-1, random_state=semente),
        "gradient_boosting": HistGradientBoostingRegressor(max_depth=4, learning_rate=0.05, max_iter=300,
                                                           random_state=semente),
    }


def prepara(pm: pd.DataFrame) -> pd.DataFrame:
    d = pm.sort_values(["ine", "periodo"]).copy()
    for c in NUM[:-2] + [ALVO, "alvo_prop_sim_ig"]:
        if c in d:
            d[c] = pd.to_numeric(d[c], errors="coerce")
    d["log_n"] = np.log1p(d["n_dado_real"].astype(float))
    d["media_movel_3"] = d[["prop_sim_os", "prop_sim_os_lag1", "prop_sim_os_lag2"]].mean(axis=1)
    d = d[d["n_dado_real"] >= 20]                                  # equipes com base mínima
    return d


def pipeline(est) -> Pipeline:
    pre = ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("esc", StandardScaler())]), NUM),
        ("cat", OneHotEncoder(handle_unknown="ignore"), CAT)])
    return Pipeline([("pre", pre), ("modelo", est)])


def _metricas(y, p, ds=None) -> dict:
    out = {"mae": float(mean_absolute_error(y, p)), "rmse": float(np.sqrt(mean_squared_error(y, p))),
           "r2": float(r2_score(y, p))}
    if ds is not None:
        for d in sorted(pd.unique(ds)):
            m = ds == d
            out[f"mae_ds{int(d)}"] = float(mean_absolute_error(y[m], p[m]))
    return out


def precisao_k(teste: pd.DataFrame, previsto: np.ndarray, frac: float = 0.1) -> float:
    """Em cada período de teste: das k equipes com pior alvo real, quantas o modelo põe entre as k piores."""
    t = teste.assign(_p=previsto)
    acertos, total = 0, 0
    for _, g in t.groupby("periodo"):
        k = max(1, int(round(frac * len(g))))
        acertos += len(set(g.nsmallest(k, ALVO)["ine"]) & set(g.nsmallest(k, "_p")["ine"]))
        total += k
    return acertos / total if total else np.nan


def treina(saida: Path, n_teste: int = 2, semente: int = 20261022, usar_mlflow: bool = True) -> pd.DataFrame:
    saida = Path(saida)
    pm = pd.read_parquet(saida / "analitica" / "fato_painel_ml.parquet")
    d = prepara(pm)
    d = d[d[ALVO].notna()]
    periodos = sorted(d["periodo"].unique())
    teste_p = periodos[-n_teste:]
    treino, teste = d[~d["periodo"].isin(teste_p)], d[d["periodo"].isin(teste_p)]
    X, y = treino[NUM + CAT], treino[ALVO].values
    Xt, yt = teste[NUM + CAT], teste[ALVO].values
    resultados, previsoes = [], {}
    # linhas de base
    for nome, p in (("persistencia", teste["prop_sim_os"].values), ("media_movel_3", teste["media_movel_3"].values)):
        col = "prop_sim_os" if nome == "persistencia" else "media_movel_3"
        vp = periodos[:-n_teste][4:]
        cvb = np.mean([mean_absolute_error(g[ALVO], g[col]) for _, g in treino[treino["periodo"].isin(vp)]
                       .groupby("periodo")]) if vp else np.nan
        r = {"modelo": nome, **_metricas(yt, p, teste["id_ds"].values), "precisao_k": precisao_k(teste, p),
             "cv_mae": float(cvb)}
        resultados.append(r)
        previsoes[nome] = p
    mlf = _mlflow(usar_mlflow)
    if mlf:
        mlf.set_experiment("aps_recife_prop_sim_os")
    base_tr, base_te = treino["prop_sim_os"].values, teste["prop_sim_os"].values
    for (nome0, est0), modo in [(m, md) for m in modelos(semente).items() for md in ("nivel", "variacao")]:
        from sklearn.base import clone
        est = clone(est0)
        nome = nome0 if modo == "nivel" else f"{nome0}_variacao"
        pipe = pipeline(est)
        cv = _walk_forward(pipe, treino, periodos[:-n_teste], variacao=modo == "variacao")
        pipe.fit(X, y - base_tr if modo == "variacao" else y)
        p = pipe.predict(Xt) + (base_te if modo == "variacao" else 0)
        p = np.clip(p, 0, 1)
        r = {"modelo": nome, **_metricas(yt, p, teste["id_ds"].values), "precisao_k": precisao_k(teste, p),
             "cv_mae": cv}
        resultados.append(r)
        previsoes[nome] = p
        if mlf:
            with mlf.start_run(run_name=nome):
                mlf.log_params({"modelo": nome, "n_treino": len(treino), "n_teste": len(teste),
                                "periodos_teste": ",".join(map(str, teste_p)), "saida": saida.name,
                                **{k: v for k, v in est.get_params().items() if isinstance(v, (int, float, str))}})
                mlf.log_metrics({k: v for k, v in r.items() if isinstance(v, float) and np.isfinite(v)})
                try:
                    import mlflow.sklearn
                    mlflow.sklearn.log_model(pipe, name="modelo")
                except Exception as e:  # noqa: BLE001
                    log.warning("modelo não registrado no MLflow: %s", e)
    res = pd.DataFrame(resultados)
    # escolha pela validação cruzada (não pelo teste); a persistência é o piso a vencer
    candidatos = res[res["cv_mae"].notna() & ~res["modelo"].isin(["persistencia", "media_movel_3"])]
    melhor = candidatos.sort_values("cv_mae").iloc[0]["modelo"]
    destino = saida / "ml"
    destino.mkdir(parents=True, exist_ok=True)
    res.to_csv(destino / "metricas.csv", index=False)
    pred = teste[["ine", "periodo", "id_ds", "n_dado_real", "prop_sim_os", ALVO]].copy()
    pred["previsto"] = previsoes[melhor]
    pred["previsto_persistencia"] = previsoes["persistencia"]
    pred["modelo"] = melhor
    pred["melhor_que_persistencia_cv"] = bool(candidatos["cv_mae"].min() < res.loc[res["modelo"] == "persistencia",
                                                                                    "cv_mae"].iloc[0])
    pred.to_parquet(destino / "predicoes.parquet", index=False)
    (destino / "resumo.json").write_text(json.dumps({"melhor_por_cv": melhor, "periodos_teste": list(map(int, teste_p)),
                                                     "n_treino": len(treino), "n_teste": len(teste)}, indent=2),
                                         encoding="utf-8")
    _relatorio(destino, res, melhor, teste_p, len(treino), len(teste))
    return res


def _walk_forward(pipe, treino: pd.DataFrame, periodos: list, min_periodos: int = 4, variacao: bool = False) -> float:
    """MAE médio em janela expansível: treina até t-1 e testa em t."""
    from sklearn.base import clone
    erros = []
    for i in range(min_periodos, len(periodos)):
        tr = treino[treino["periodo"].isin(periodos[:i])]
        te = treino[treino["periodo"] == periodos[i]]
        if len(te) == 0 or len(tr) < 30:
            continue
        b_tr = tr["prop_sim_os"].values if variacao else 0
        b_te = te["prop_sim_os"].values if variacao else 0
        m = clone(pipe).fit(tr[NUM + CAT], tr[ALVO].values - b_tr)
        erros.append(mean_absolute_error(te[ALVO].values, np.clip(m.predict(te[NUM + CAT]) + b_te, 0, 1)))
    return float(np.mean(erros)) if erros else np.nan


def _mlflow(usar: bool):
    if not usar:
        return None
    try:
        import mlflow
    except ImportError:
        log.info("MLflow não instalado: métricas só em arquivo")
        return None
    if not os.environ.get("MLFLOW_TRACKING_URI"):
        from .config import RAIZ
        # backend local em SQLite (o de arquivos ./mlruns está descontinuado nas versões novas)
        mlflow.set_tracking_uri("sqlite:///" + (RAIZ / "mlflow.db").resolve().as_posix())
    return mlflow


def _relatorio(destino: Path, res: pd.DataFrame, melhor: str, teste_p, n_tr, n_te) -> None:
    cols = ["modelo", "mae", "rmse", "r2", "precisao_k", "cv_mae"]
    linhas = ["# Previsão da proporção de \"Sim\" no quadrimestre seguinte", "",
              f"Treino: {n_tr} linhas equipe × período; teste: {n_te} linhas (períodos {', '.join(map(str, teste_p))}). "
              f"Modelo escolhido pela validação walk-forward: **{melhor}**.", "",
              "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in res.iterrows():
        linhas.append("| " + " | ".join(f"{r[c]:.4f}" if isinstance(r[c], float) else str(r[c]) for c in cols) + " |")
    linhas += ["", "Um modelo só agrega valor se vencer a persistência no teste; com séries de cadastro que mudam "
               "devagar (versões renovadas a cada ~18 meses), a persistência é um piso alto."]
    (destino / "relatorio_ml.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
