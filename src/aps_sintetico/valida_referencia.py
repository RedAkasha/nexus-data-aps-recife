"""Trabalho de Inferência: os dados sintéticos respeitam os valores de referência?

Para cada valor de referência (calibração de valida.calibracao) calcula: estimativa e n, IC 95%
(Wilson para proporções; exato de Poisson para contagens), teste de hipótese (z para uma
proporção; z de Poisson para contagens), tolerância e decisão. Saída: CSV e relatório Markdown
em saida/<cenário>/relatorios/. Uso: python -m aps_sintetico.valida_referencia [--saida saida/base]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from . import valida
from .config import RAIZ

FONTES = {
    "Censo 2022": "IBGE. Censo Demográfico 2022 (SIDRA, tabelas 9606/9922/9923/10125/10132). Recife (2611606), 2022. "
                  "https://sidra.ibge.gov.br",
    "PNS 2019": "IBGE. Pesquisa Nacional de Saúde 2019; Orientação sexual autoidentificada (2022). PE, adultos 18+, 2019. "
                "https://www.ibge.gov.br",
    "Spizzirri": "Spizzirri G. et al. Proportion of people identified as transgender and non-binary gender in Brazil. "
                 "Scientific Reports 11, 2240 (2021). Brasil, adultos, 2021. https://doi.org/10.1038/s41598-021-81411-4",
    "boletim": "Secretaria de Saúde do Recife. Boletim 01/2025 (SINASC/SIM 2024). Recife, por DS, 2024. "
               "(arquivo dados/parametros_complementares/boletim_sesau_2025.csv)",
    "planilha": "Planilha de monitoramento de dados de raça/cor, orientação sexual e identidade de gênero (linha 3), "
                "material do projeto, data de corte.",
    "K": "Meta de cobertura cadastral por DS (Tabela 4 do plano metodológico do projeto) × omissão declarada.",
}


def fonte(nota: str) -> str:
    for k, v in FONTES.items():
        if k.lower() in nota.lower():
            return v
    if "SESAU" in nota:
        return FONTES["boletim"]
    return nota


def tipo(v: str) -> str:
    if "óbitos" in v or "nascimentos" in v or v.startswith("população"):
        return "quantitativa discreta (contagem)"
    if v.startswith("raça") or "tipo de def" in v or v.startswith("sexo"):
        return "qualitativa nominal (proporção de categoria)"
    return "qualitativa nominal (proporção da categoria principal)"


def analisa(cal: pd.DataFrame, nivel: float = 0.95) -> pd.DataFrame:
    z95 = stats.norm.ppf(0.975)
    linhas = []
    for r in cal.itertuples():
        contagem = r.n == r.obtido and r.alvo > 1.5            # _cont devolve n = obtido
        if contagem:
            o, e = int(r.obtido), float(r.alvo)
            lo = stats.chi2.ppf(0.025, 2 * o) / 2 if o else 0.0
            hi = stats.chi2.ppf(0.975, 2 * (o + 1)) / 2
            z = (o - e) / np.sqrt(max(e, 1))
            est, ic, tol, h0 = o, (lo, hi), r.tolerancia, f"H0: contagem esperada = {e:.0f} (Poisson)"
            alvo = e
        else:
            p, p0, n = float(r.obtido), float(r.alvo), int(r.n)
            den = 1 + z95**2 / n
            c = (p + z95**2 / (2 * n)) / den
            m = z95 * np.sqrt(p * (1 - p) / n + z95**2 / (4 * n**2)) / den
            z = (p - p0) / np.sqrt(max(p0 * (1 - p0), 1e-12) / n)
            est, ic, tol, h0, alvo = p, (c - m, c + m), r.tolerancia, f"H0: p = {p0:.4f}", p0
        pval = 2 * (1 - stats.norm.cdf(abs(z)))
        dentro = abs(est - alvo) <= tol
        ic_dentro = ic[0] >= alvo - tol and ic[1] <= alvo + tol
        linhas.append({
            "variavel": r.verificacao, "tipo": tipo(r.verificacao), "estatistica_referencia": "contagem esperada" if contagem else "proporção",
            "valor_referencia": alvo, "estimativa_sintetica": est, "n": int(r.n), "ic95_inf": ic[0], "ic95_sup": ic[1],
            "hipoteses": (h0 + "; H1: ≠"), "estatistica_z": z, "p_valor": pval,
            "tolerancia": tol, "tolerancia_justificativa": "máx(1 p.p.; 3·EP)" if not contagem else "3·√esperado (3 desvios de Poisson)",
            "decisao_teste_5pct": "não rejeita H0" if pval >= 0.05 else "rejeita H0",
            "diferenca_dentro_da_tolerancia": bool(dentro), "ic_dentro_da_tolerancia": bool(ic_dentro),
            "veredito": "aceito" if dentro else "fora da tolerância", "fonte": fonte(r.nota), "nota": r.nota})
    return pd.DataFrame(linhas)


def relatorio(saida: Path) -> Path:
    df = analisa(valida.calibracao(saida))
    dest = saida / "relatorios"
    dest.mkdir(exist_ok=True)
    df.to_csv(dest / "inferencia_referencias.csv", index=False)
    f = lambda x: f"{x:.4f}"   # noqa: E731
    L = ["# Inferência: dados sintéticos × valores de referência", "",
         f"{len(df)} valores de referência; {int(df['diferenca_dentro_da_tolerancia'].sum())} dentro da tolerância, "
         f"{int((df['decisao_teste_5pct'] == 'rejeita H0').sum())} com rejeição de H0 a 5%.", "",
         "Tolerância: proporções ±máx(1 p.p.; 3·EP) — 1 p.p. é a diferença que não muda nenhuma leitura do painel e 3·EP "
         "é o ruído amostral esperado; contagens ±3·√esperado (Poisson). Quando n é muito grande, o teste z rejeita "
         "diferenças minúsculas; por isso a decisão final combina o teste com a tolerância (equivalência prática).", "",
         "| Variável | Tipo | Referência | Estimativa | n | IC 95% | Hipóteses | z | p | Tolerância | Decisão |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in df.itertuples():
        L.append(f"| {r.variavel} | {r.tipo} | {f(r.valor_referencia)} | {f(r.estimativa_sintetica)} | {r.n} | "
                 f"[{f(r.ic95_inf)}; {f(r.ic95_sup)}] | {r.hipoteses} | {r.estatistica_z:.2f} | {r.p_valor:.3f} | "
                 f"±{f(r.tolerancia)} | {r.decisao_teste_5pct}; {r.veredito} |")
    L += ["", "## Fontes", ""] + [f"- {v}" for v in dict.fromkeys(df["fonte"])]
    p = dest / "inferencia_referencias.md"
    p.write_text("\n".join(L), encoding="utf-8")
    return p


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", default=str(RAIZ / "saida" / "base"))
    a = ap.parse_args()
    p = relatorio(Path(a.saida))
    d = pd.read_csv(p.with_suffix(".csv"))
    print(p, len(d), d["veredito"].value_counts().to_dict(), d["decisao_teste_5pct"].value_counts().to_dict())
