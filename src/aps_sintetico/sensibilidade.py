"""Etapa 10 – análise de sensibilidade (ADEMP): cenários nomeados, réplicas e hipercubo latino.

Cada execução gera uma base pequena (escala e DS escolhidos), monta a camada analítica em
Python e mede, contra a verdade: a reprodução da linha 3, o viés MNAR, a recuperação do
efeito da oficina e a qualidade das estimativas por equipe. As réplicas (sementes diferentes)
dão o erro de Monte Carlo de cada medida.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import qmc

from . import analitica, gerador, inferencia
from .config import RAIZ, carrega
from .valida import le_saida, linha3

log = logging.getLogger("aps_sintetico")

CENARIOS = ["base", "pi_alto", "pi_muito_alto", "mnar_menor", "mnar_maior", "equipe_sigma_baixo",
            "equipe_sigma_alto", "oficina_nula", "oficina_moderada", "oficina_focalizada", "idade_min_10",
            "cobertura_baixa", "cobertura_alta", "deficiencia_sens_baixa", "deficiencia_sens_alta"]

LHS_FAIXAS = {"registro.sigma_equipe": (0.5, 1.5), "registro.lambda_lgb": (-0.7, 0.4),
              "registro.pi_nao_sem_pergunta": (0.0, 0.9), "oficinas.efeito_logito": (0.0, 0.5),
              "registro.sens_deficiencia": (0.5, 0.9)}


def _uma(cfg, destino: Path, manter: bool) -> dict:
    gerador.gera_e_exporta(cfg, destino)
    analitica.constroi(destino)
    L = linha3(le_saida(destino)).set_index("grupo")
    e = inferencia.metricas_equipe(inferencia.estimativas_equipe(destino))
    m = inferencia.vies_mnar(destino)
    o = inferencia.efeito_oficina(destino)
    pes = pd.read_parquet(destino / "verdade" / "pessoas.parquet")
    pcd_reg = None
    try:
        ci = pd.read_csv(destino / "nucleo" / "cadastro_individual.csv", usecols=["tem_deficiencia"], dtype=str)
        pcd_reg = float((ci["tem_deficiencia"] == "1").mean())
    except Exception:  # noqa: BLE001
        pass
    linha = {"linha3_sim": L.loc["adultos", "sim"], "linha3_ni": L.loc["adultos", "ni"],
             "linha3_nao": L.loc["adultos", "nao"], "cobertura_wilson": e["cobertura_wilson"],
             "rmse_bruta": e["rmse_bruta"], "rmse_eb": e["rmse_eb"], "spearman_eb": e["spearman_eb"],
             "precisao_k_eb": e["precisao_k_eb"], "vies_lgb_pp": m["vies_lgb_pp"],
             "vies_lgb_pos_estrat_pp": m["vies_pos_estratificado_pp"], "razao_lgb": m["razao_lgb"],
             "did_obs_pp": o.get("did_observado_pp"), "did_verdade_pp": o.get("did_verdade_instantanea_pp"),
             "ingenua_pp": o.get("diferenca_ingenua_pp"), "pcd_registrada_versoes": pcd_reg,
             "pcd_real": float((pes["def_bits"] > 0).mean())}
    if not manter:
        shutil.rmtree(destino, ignore_errors=True)
    return linha


def roda(cenarios: list[str] | None = None, replicas: int = 1, escala: float = 0.03,
         distritos: list[int] | None = None, lhs: int = 0, destino: Path | None = None, manter: bool = False
         ) -> pd.DataFrame:
    destino = Path(destino) if destino else RAIZ / "saida" / "sensibilidade"
    destino.mkdir(parents=True, exist_ok=True)
    distritos = distritos or [1, 3, 7]
    linhas = []
    execucoes = [(c, {}) for c in (cenarios or CENARIOS)]
    if lhs:
        amostra = qmc.LatinHypercube(d=len(LHS_FAIXAS), seed=20261022).random(lhs)
        lo = np.array([v[0] for v in LHS_FAIXAS.values()])
        hi = np.array([v[1] for v in LHS_FAIXAS.values()])
        for i, u in enumerate(qmc.scale(amostra, lo, hi)):
            execucoes.append((f"lhs_{i:03d}", dict(zip(LHS_FAIXAS, map(float, u)))))
    for nome, extra in execucoes:
        for r in range(replicas):
            base = None if nome.startswith("lhs_") else (None if nome == "base" else nome)
            cfg = carrega(base, escala=escala, distritos=distritos, **extra)
            cfg["semente"] = int(cfg["semente"]) + r
            cfg["nome"] = f"{nome}_r{r}"
            log.info("sensibilidade: %s (réplica %d)", nome, r)
            res = _uma(cfg, destino / cfg["nome"], manter)
            linhas.append({"cenario": nome, "replica": r, **extra, **res})
    df = pd.DataFrame(linhas)
    df.to_csv(destino / "resultados.csv", index=False)
    _resumo(df, destino)
    return df


def _resumo(df: pd.DataFrame, destino: Path) -> None:
    med = ["linha3_sim", "linha3_ni", "vies_lgb_pp", "vies_lgb_pos_estrat_pp", "did_obs_pp", "did_verdade_pp",
           "ingenua_pp", "rmse_bruta", "rmse_eb", "cobertura_wilson", "pcd_registrada_versoes", "pcd_real"]
    g = df.groupby("cenario")[med]
    m, n = g.mean(), g.size()
    ep = g.std(ddof=1).div(np.sqrt(n), axis=0)
    linhas = ["# Análise de sensibilidade", "",
              f"{len(df)} execuções; médias por cenário (entre parênteses, erro de Monte Carlo quando há réplicas).",
              "Colunas em proporção (linha3_*, rmse_*, cobertura_wilson, pcd_*) ou pontos percentuais (_pp). "
              "Viés LGB+: estimativa entre respondentes − prevalência real; DiD: diferença-em-diferenças do efeito "
              "das oficinas no painel observado e na verdade; ingênua: tratadas − controles no fim da série.",
              "", "| cenário | " + " | ".join(med) + " |", "|---|" + "---|" * len(med)]
    for c in m.index:
        cel = []
        for k in med:
            v, e = m.at[c, k], ep.at[c, k] if n[c] > 1 else np.nan
            cel.append("–" if pd.isna(v) else (f"{v:.3f}" + (f" ({e:.3f})" if pd.notna(e) else "")))
        linhas.append(f"| {c} | " + " | ".join(cel) + " |")
    (destino / "sensibilidade.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
