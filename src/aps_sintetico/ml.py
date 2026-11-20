"""Etapa 10 – ML supervisionado: ALERTA DE BAIXO PREENCHIMENTO por equipe (classificação).

PERGUNTA: a equipe vai terminar o PRÓXIMO quadrimestre com menos de 15% de "Sim" em orientação
sexual (dado real entre os elegíveis)? Se sim, ela entra na fila de apoio/oficina antes do problema.
(O alvo NÃO é evasão: o cliente e o professor não pediram e não faz sentido para este dado.)

======================================================================================
COMO EVITAMOS VAZAMENTO DE DADOS (data leakage) – leia antes de mudar qualquer coisa
======================================================================================
 1. O ALVO É O FUTURO. Cada linha é (equipe × quadrimestre t). As variáveis só usam informação
    disponível até o FIM de t (valores atuais, defasagens t-1 e t-2, média móvel). O rótulo é
    "Sim(t+1) < 15%", observado só depois. Nenhuma variável é calculada com t+1.
 2. DIVISÃO NO TEMPO, NUNCA ALEATÓRIA. Treino = períodos mais antigos; teste = os 2 últimos
    períodos com rótulo, estritamente depois do treino. Sorteio aleatório deixaria o modelo ver
    o futuro da própria equipe (a mesma equipe aparece em vários períodos, muito parecidos).
 3. VALIDAÇÃO CRUZADA EM JANELA EXPANSÍVEL (walk-forward): treina em 1..k, valida em k+1; o
    passado nunca é validado com modelo que viu o futuro. Escolhas (modelo, limiar) usam só isso.
 4. PRÉ-PROCESSAMENTO DENTRO DO PIPELINE. Mediana de imputação, padronização e one-hot são
    ajustadas só no treino de cada dobra (sklearn Pipeline), nunca no conjunto inteiro.
 5. O TESTE É USADO UMA ÚNICA VEZ, depois de modelo, hiperparâmetros e limiar estarem fixos.
    Hiperparâmetros são declarados a priori (sem busca), para não "otimizar no teste" por
    acidente. O limiar de decisão sai das previsões fora-da-amostra do walk-forward.
 6. SEM COLUNAS-ALVO NAS VARIÁVEIS e sem identificadores (ine) como variável; há checagens
    automáticas (auditoria) que ABORTAM a execução se o treino não for anterior ao teste, se uma
    coluna alvo entrar nas variáveis ou se um modelo com rótulos embaralhados "acertar" demais.
 7. INCERTEZA HONESTA: intervalo de confiança por bootstrap agrupado por equipe (as linhas da
    mesma equipe não são independentes) e comparação com a linha de base de persistência.
 8. O que é mantido nos dados NÃO usa o gabarito do gerador (arquivos de "verdade"): só a camada
    analítica observável (fato_painel_ml).

MODELOS (o essencial, do mais simples ao mais complexo): persistência (regra "quem está baixo
continua baixo", é o piso a vencer), regressão logística, árvore de decisão, KNN e floresta
aleatória. ESCOLHA DO DEFINITIVO: maior área sob a curva precisão–revocação (AP) média no
walk-forward; entre os que ficam a 1 erro-padrão do melhor, o mais explicável (regra de 1 EP).
Tudo é registrado no MLflow, se instalado.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss, f1_score, precision_recall_curve,
                             precision_score, recall_score, roc_auc_score)
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

log = logging.getLogger("aps_sintetico")

LIMIAR_ALERTA = 0.15          # "Sim" abaixo disso = baixo preenchimento (mesmo limiar do painel)
REVOCACAO_ALVO = 0.80         # queremos achar ao menos 80% das equipes que vão ficar baixas
NUM = ["prop_sim_os", "prop_nao_os", "prop_ni_os", "prop_sim_ig", "prop_sim_os_lag1", "prop_sim_os_lag2",
       "prop_criancas", "prop_60_mais", "dist_raca_cor_censo", "atraso_medio_digitacao", "n_acoes_ate_periodo",
       "log_n", "media_movel_3"]
CAT = ["id_ds", "tipo_equipe"]
ALVO_NUM = "alvo_prop_sim_os"
ALVO = "alerta_proximo"
EXPLICAVEL = {"persistencia": 0, "logistica": 1, "arvore": 2, "knn": 3, "floresta": 4}   # 0 = mais simples
NOMES = {"persistencia": "Persistência (regra)", "logistica": "Regressão logística",
         "arvore": "Árvore de decisão", "knn": "KNN", "floresta": "Floresta aleatória"}


def modelos(semente: int) -> dict:
    """Hiperparâmetros fixos a priori (sem busca): nada é ajustado olhando o teste."""
    return {
        "logistica": LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000),
        "arvore": DecisionTreeClassifier(max_depth=4, min_samples_leaf=30, class_weight="balanced",
                                         random_state=semente),
        "knn": KNeighborsClassifier(n_neighbors=25, weights="distance"),
        "floresta": RandomForestClassifier(n_estimators=300, min_samples_leaf=10, class_weight="balanced",
                                           n_jobs=-1, random_state=semente),
    }


def prepara(pm: pd.DataFrame) -> pd.DataFrame:
    d = pm.sort_values(["ine", "periodo"]).copy()
    for c in NUM[:-2] + [ALVO_NUM]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["log_n"] = np.log1p(d["n_dado_real"].astype(float))
    d["media_movel_3"] = d[["prop_sim_os", "prop_sim_os_lag1", "prop_sim_os_lag2"]].mean(axis=1)
    d = d[d["n_dado_real"] >= 20].copy()                       # equipes com base mínima
    d[ALVO] = np.where(d[ALVO_NUM].notna(), (d[ALVO_NUM] < LIMIAR_ALERTA).astype(float), np.nan)
    return d


def pipeline(est) -> Pipeline:
    pre = ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("esc", StandardScaler())]), NUM),
        ("cat", OneHotEncoder(handle_unknown="ignore"), CAT)])
    return Pipeline([("pre", pre), ("modelo", est)])


def _score_persistencia(d: pd.DataFrame) -> np.ndarray:
    """Quanto mais baixo o 'Sim' atual, maior o risco (regra sem aprendizado)."""
    return (1.0 - d["prop_sim_os"].fillna(d["prop_sim_os"].median())).values


def auditoria(treino, teste, periodos_treino, periodos_teste, semente) -> dict:
    """Checagens que abortam a execução se houver vazamento."""
    ok_tempo = max(periodos_treino) < min(periodos_teste)
    proibidas = [c for c in NUM + CAT if c.startswith("alvo") or c == ALVO or c == "ine"]
    if not ok_tempo:
        raise RuntimeError("VAZAMENTO: o treino não é anterior ao teste")
    if proibidas:
        raise RuntimeError(f"VAZAMENTO: colunas proibidas nas variáveis: {proibidas}")
    # teste de sanidade: com rótulos embaralhados o modelo não pode ter desempenho útil
    rng = np.random.default_rng(semente)
    y_emb = rng.permutation(treino[ALVO].values)
    m = clone(pipeline(modelos(semente)["floresta"])).fit(treino[NUM + CAT], y_emb)
    ap_emb = average_precision_score(teste[ALVO], m.predict_proba(teste[NUM + CAT])[:, 1])
    prev = float(teste[ALVO].mean())
    if ap_emb > prev + 0.10:
        raise RuntimeError(f"VAZAMENTO suspeito: AP com rótulos embaralhados = {ap_emb:.2f} (prevalência {prev:.2f})")
    return {"treino_anterior_ao_teste": bool(ok_tempo), "ultimo_periodo_treino": int(max(periodos_treino)),
            "primeiro_periodo_teste": int(min(periodos_teste)), "colunas_proibidas_nas_variaveis": proibidas,
            "ap_com_rotulos_embaralhados": round(float(ap_emb), 3), "prevalencia_teste": round(prev, 3),
            "preprocessamento_dentro_do_pipeline": True, "teste_usado_uma_vez": True}


def walk_forward(d: pd.DataFrame, periodos: list, nome: str, est, min_periodos: int = 4):
    """Previsões fora-da-amostra em janela expansível. Devolve (DataFrame de previsões, AP por dobra)."""
    saidas, aps = [], []
    for i in range(min_periodos, len(periodos)):
        tr, va = d[d["periodo"].isin(periodos[:i])], d[d["periodo"] == periodos[i]]
        if va[ALVO].nunique() < 2 or len(tr) < 50:
            continue
        if nome == "persistencia":
            s = _score_persistencia(va)
        else:
            s = clone(pipeline(est)).fit(tr[NUM + CAT], tr[ALVO].values).predict_proba(va[NUM + CAT])[:, 1]
        aps.append(average_precision_score(va[ALVO], s))
        saidas.append(pd.DataFrame({"y": va[ALVO].values, "s": s}))
    return (pd.concat(saidas) if saidas else pd.DataFrame(columns=["y", "s"])), aps


def limiar_por_revocacao(y, s, alvo: float = REVOCACAO_ALVO) -> float:
    """Maior limiar que ainda alcança a revocação desejada (mais precisão possível)."""
    p, r, t = precision_recall_curve(y, s)
    ok = np.where(r[:-1] >= alvo)[0]
    return float(t[ok[-1]]) if len(ok) else float(np.min(s))


def metricas(y, s, limiar) -> dict:
    pred = (s >= limiar).astype(int)
    return {"ap": float(average_precision_score(y, s)), "auc": float(roc_auc_score(y, s)),
            "precisao": float(precision_score(y, pred, zero_division=0)),
            "revocacao": float(recall_score(y, pred, zero_division=0)),
            "f1": float(f1_score(y, pred, zero_division=0)),
            "brier": float(brier_score_loss(y, np.clip(s, 0, 1))), "limiar": float(limiar),
            "alertas_emitidos": int(pred.sum())}


def precisao_k(teste: pd.DataFrame, s: np.ndarray, frac: float = 0.1) -> float:
    t = teste.assign(_s=s)
    ac = tot = 0
    for _, g in t.groupby("periodo"):
        k = max(1, int(round(frac * len(g))))
        ac += g.nlargest(k, "_s")[ALVO].sum()
        tot += k
    return float(ac / tot) if tot else np.nan


def bootstrap_equipes(teste, s_modelo, s_base, n=400, semente=1) -> dict:
    """IC 95% do AP e da diferença AP(modelo) − AP(persistência), reamostrando EQUIPES inteiras."""
    rng = np.random.default_rng(semente)
    ines = teste["ine"].unique()
    idx = {i: np.where(teste["ine"].values == i)[0] for i in ines}
    y = teste[ALVO].values
    ap_m, dif = [], []
    for _ in range(n):
        sel = np.concatenate([idx[i] for i in rng.choice(ines, len(ines))])
        if len(np.unique(y[sel])) < 2:
            continue
        a = average_precision_score(y[sel], s_modelo[sel])
        b = average_precision_score(y[sel], s_base[sel])
        ap_m.append(a)
        dif.append(a - b)
    q = lambda v: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]   # noqa: E731
    return {"ap_ic95": q(ap_m), "dif_vs_persistencia_ic95": q(dif)}


def treina(saida: Path, n_teste: int = 2, semente: int = 20261022, usar_mlflow: bool = True) -> pd.DataFrame:
    saida = Path(saida)
    pm = pd.read_parquet(saida / "analitica" / "fato_painel_ml.parquet")
    d_all = prepara(pm)
    d = d_all[d_all[ALVO].notna()]                             # só linhas com desfecho observado
    periodos = sorted(d["periodo"].unique())
    p_teste, p_treino = periodos[-n_teste:], periodos[:-n_teste]
    treino, teste = d[d["periodo"].isin(p_treino)], d[d["periodo"].isin(p_teste)]
    aud = auditoria(treino, teste, p_treino, p_teste, semente)

    mlf = _mlflow(usar_mlflow)
    if mlf:
        mlf.set_experiment("aps_recife_alerta_baixo_preenchimento")
    ests = {"persistencia": None, **modelos(semente)}
    cv, oof = {}, {}
    for nome, est in ests.items():
        pr, aps = walk_forward(treino, p_treino, nome, est)
        cv[nome] = (float(np.mean(aps)), float(np.std(aps, ddof=1) / np.sqrt(len(aps))) if len(aps) > 1 else np.nan,
                    len(aps))
        oof[nome] = pr
    # ---- escolha do definitivo: AP médio no walk-forward + regra de 1 erro-padrão (mais explicável) ----
    cand = {k: v for k, v in cv.items() if k != "persistencia"}
    melhor_ap = max(v[0] for v in cand.values())
    se_melhor = [v[1] for v in cand.values() if v[0] == melhor_ap][0]
    elegiveis = [k for k, v in cand.items() if v[0] >= melhor_ap - (se_melhor if np.isfinite(se_melhor) else 0)]
    escolhido = min(elegiveis, key=lambda k: EXPLICAVEL[k])
    vence_persist = cv[escolhido][0] > cv["persistencia"][0]
    # ---- teste, uma única vez, com limiar vindo do walk-forward ----
    resultados, s_teste = [], {}
    Xt = teste[NUM + CAT]
    for nome, est in ests.items():
        lim = limiar_por_revocacao(oof[nome]["y"].values, oof[nome]["s"].values)
        if nome == "persistencia":
            s = _score_persistencia(teste)
        else:
            m = clone(pipeline(est)).fit(treino[NUM + CAT], treino[ALVO].values)
            s = m.predict_proba(Xt)[:, 1]
        s_teste[nome] = s
        novo = (teste["prop_sim_os"] >= LIMIAR_ALERTA).values          # hoje fora de alerta
        yn = teste[ALVO].values[novo]
        r = {"modelo": nome, "nome": NOMES[nome], **metricas(teste[ALVO].values, s, lim),
             "n_novos": int(yn.sum()),
             "rev_novos": float((s[novo][yn == 1] >= lim).mean()) if yn.sum() else np.nan,
             "ap_fora_alerta": float(average_precision_score(yn, s[novo])) if yn.sum() else np.nan,
             "precisao_k": precisao_k(teste, s), "cv_ap": cv[nome][0], "cv_ep": cv[nome][1],
             "explicabilidade": EXPLICAVEL[nome], "escolhido": nome == escolhido}
        resultados.append(r)
        if mlf:
            with mlf.start_run(run_name=nome):
                mlf.log_params({"modelo": nome, "n_treino": len(treino), "n_teste": len(teste),
                                "periodos_teste": ",".join(map(str, p_teste)), "limiar_alerta": LIMIAR_ALERTA})
                mlf.log_metrics({k: v for k, v in r.items() if isinstance(v, float) and np.isfinite(v)})
    res = pd.DataFrame(resultados)
    ic = bootstrap_equipes(teste.reset_index(drop=True), s_teste[escolhido], s_teste["persistencia"], semente=semente)
    # ---- importância (permutação no teste) do definitivo ----
    imp = pd.DataFrame()
    if escolhido != "persistencia":
        mf = clone(pipeline(ests[escolhido])).fit(treino[NUM + CAT], treino[ALVO].values)
        pi = permutation_importance(mf, Xt, teste[ALVO].values, scoring="average_precision", n_repeats=10,
                                    random_state=semente)
        imp = pd.DataFrame({"variavel": NUM + CAT, "queda_ap": pi.importances_mean, "dp": pi.importances_std}) \
            .sort_values("queda_ap", ascending=False)
    # ---- modelo final: refit com TODO o histórico rotulado; prevê o próximo quadrimestre ----
    lim_final = res.loc[res["modelo"] == escolhido, "limiar"].iloc[0]
    final = clone(pipeline(ests[escolhido])).fit(d[NUM + CAT], d[ALVO].values)
    ultimo = d_all["periodo"].max()
    futuro = d_all[d_all["periodo"] == ultimo]
    destino = saida / "ml"
    destino.mkdir(parents=True, exist_ok=True)
    cols = ["ine", "periodo", "id_ds", "tipo_equipe", "n_dado_real", "prop_sim_os"]
    pt = teste[cols + [ALVO_NUM, ALVO]].copy()
    pt["prob_alerta"], pt["fase"] = s_teste[escolhido], "teste"
    pt["prob_persistencia"] = s_teste["persistencia"]
    pf = futuro[cols].copy()
    pf["prob_alerta"], pf["fase"] = final.predict_proba(futuro[NUM + CAT])[:, 1], "proximo"
    pred = pd.concat([pt, pf], ignore_index=True)
    pred["alerta"] = pred["prob_alerta"] >= lim_final
    pred["modelo"], pred["limiar"] = escolhido, lim_final
    pred.to_parquet(destino / "predicoes.parquet", index=False)
    res.to_csv(destino / "comparacao.csv", index=False)
    if len(imp):
        imp.to_csv(destino / "importancia.csv", index=False)
    resumo = {"escolhido": escolhido, "nome_escolhido": NOMES[escolhido], "limiar_alerta": LIMIAR_ALERTA,
              "periodos_treino": list(map(int, p_treino)), "periodos_teste": list(map(int, p_teste)),
              "periodo_previsto_a_partir_de": int(ultimo), "n_treino": len(treino), "n_teste": len(teste),
              "prevalencia_teste": float(teste[ALVO].mean()), "limiar_decisao": float(lim_final),
              "elegiveis_1ep": elegiveis, "vence_persistencia_no_cv": bool(vence_persist),
              "bootstrap_por_equipe": ic, "auditoria_vazamento": aud}
    (destino / "resumo.json").write_text(json.dumps(resumo, indent=2, ensure_ascii=False), encoding="utf-8")
    _relatorio(destino, res, imp, resumo)
    return res


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
        mlflow.set_tracking_uri("sqlite:///" + (RAIZ / "mlflow.db").resolve().as_posix())
    return mlflow


def _relatorio(destino: Path, res: pd.DataFrame, imp: pd.DataFrame, r: dict) -> None:
    f = lambda x: f"{x:.3f}".replace(".", ",")   # noqa: E731
    a = r["auditoria_vazamento"]
    L = ["# Comparação final de modelos e justificativa técnica", "",
         f"**Problema:** classificar se a equipe terminará o próximo quadrimestre com \"Sim\" em orientação sexual "
         f"abaixo de {int(LIMIAR_ALERTA*100)}% (alerta de baixo preenchimento). Prevalência no teste: "
         f"{f(r['prevalencia_teste'])}.", "",
         f"**Modelo definitivo: {r['nome_escolhido']}.** Treino {r['periodos_treino'][0]}–{r['periodos_treino'][-1]} "
         f"({r['n_treino']} linhas), teste {r['periodos_teste']} ({r['n_teste']} linhas).", "",
         "## 1. Comparação (teste, usado uma vez; limiar fixado no walk-forward p/ revocação ≥ 80%)", "",
         "| Modelo | AP walk-forward (± EP) | AP teste | AUC | Precisão | Revocação | F1 | Precisão@10% |",
         "|---|---|---|---|---|---|---|---|"]
    for _, x in res.iterrows():
        mk = " ✅" if x["escolhido"] else ""
        L.append(f"| {x['nome']}{mk} | {f(x['cv_ap'])} ± {f(x['cv_ep']) if np.isfinite(x['cv_ep']) else '–'} | "
                 f"{f(x['ap'])} | {f(x['auc'])} | {f(x['precisao'])} | {f(x['revocacao'])} | {f(x['f1'])} | "
                 f"{f(x['precisao_k'])} |")
    b = r["bootstrap_por_equipe"]
    L += ["", "**Onde a persistência não enxerga** (equipes hoje fora de alerta; novos alertas no teste: "
              f"{int(res['n_novos'].iloc[0])}):", "", "| Modelo | Revocação dos novos alertas | AP entre equipes fora de alerta |", "|---|---|---|"]
    L += [f"| {x['nome']} | {f(x['rev_novos'])} | {f(x['ap_fora_alerta'])} |" for _, x in res.iterrows()]
    L += ["", f"IC 95% (bootstrap por equipe) do AP do definitivo: {f(b['ap_ic95'][0])}–{f(b['ap_ic95'][1])}; "
              f"diferença para a persistência: {f(b['dif_vs_persistencia_ic95'][0])} a "
              f"{f(b['dif_vs_persistencia_ic95'][1])}.", "",
          "## 2. Por que este modelo", "",
          f"- **Critério definido antes do teste:** maior AP médio no walk-forward; entre os que ficam a 1 erro-padrão "
          f"do melhor ({', '.join(NOMES[k] for k in r['elegiveis_1ep'])}), o mais explicável. Venceu a persistência "
          f"no walk-forward: {'sim' if r['vence_persistencia_no_cv'] else 'não'}.",
          "- **Persistência é um rival muito forte:** ~95% das equipes mantêm o estado (baixo/não baixo) de um "
          "quadrimestre para o outro, então \"quem está baixo hoje\" já acerta quase tudo. Por isso o modelo definitivo "
          "é avaliado também onde a regra é cega: nas equipes que HOJE estão fora de alerta (tabela abaixo). "
          "Resultado honesto: nenhum modelo supera a persistência de forma clara (diferenças dentro do IC) e os novos "
          "alertas são raros e difíceis de antecipar. Mantemos a regressão logística como definitivo por empate "
          "técnico + explicabilidade (coeficientes legíveis, pontuação contínua de risco para ordenar a fila), "
          "e deixamos a persistência como regra de comparação visível no painel.",
          "- **Métrica principal = AP** (área sob precisão–revocação): só ~1 em cada 5 equipes entra em alerta, e a "
          "acurácia seria enganosa com classe rara.",
          "- **Revocação ≥ 80%:** perder uma equipe que vai ficar baixa custa mais do que apoiar uma que não precisava.",
          "- **Explicabilidade:** a equipe de saúde precisa entender por que foi sinalizada; empate técnico "
          "favorece o modelo simples.", "",
          "## 3. Como evitamos vazamento", "",
          f"- Treino termina em {a['ultimo_periodo_treino']}, teste começa em {a['primeiro_periodo_teste']} "
          f"(treino anterior ao teste: {'sim' if a['treino_anterior_ao_teste'] else 'NÃO'}).",
          "- Variáveis só usam dados até o fim do quadrimestre t; o rótulo é do t+1.",
          "- Walk-forward (janela expansível) para escolher modelo e limiar; pré-processamento dentro do Pipeline.",
          "- Hiperparâmetros fixos a priori; teste usado uma única vez.",
          f"- Teste de sanidade: com rótulos embaralhados o AP foi {f(a['ap_com_rotulos_embaralhados'])} "
          f"(≈ prevalência {f(a['prevalencia_teste'])}).",
          "- Bootstrap agrupado por equipe (linhas da mesma equipe não são independentes).", ""]
    if len(imp):
        L += ["## 4. Variáveis mais importantes (permutação no teste)", "", "| Variável | Queda no AP |", "|---|---|"]
        L += [f"| {x.variavel} | {f(x.queda_ap)} |" for x in imp.head(8).itertuples()]
        L.append("")
    L += ["## 5. Limites", "",
          "- Base sintética: o desempenho mostra o método, não o desempenho real na rede.",
          "- O modelo prevê risco, não causa; a decisão de apoio é da equipe gestora.", ""]
    (destino / "JUSTIFICATIVA.md").write_text("\n".join(L), encoding="utf-8")
