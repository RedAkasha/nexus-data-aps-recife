"""Atividade – inclui deficiência na tabela respostas_sinteticas (Neon).

Colunas novas (no padrão da Ficha de Cadastro Individual do e-SUS):
  tem_deficiencia    'Sim' / 'Não'
  tipos_deficiencia  tipos declarados, separados por '; ' (Visual, Auditiva, Física,
                     Intelectual / Cognitiva, TEA, Outra); NULL quando não tem deficiência

De onde vêm as probabilidades (Censo 2022, Recife; o Censo não publica deficiência por distrito)
  Prevalência por sexo e faixa etária (SIDRA 10125), ponderada pela população de 18+ anos
  (SIDRA 9606), e ajustada pela raça/cor de cada resposta com a razão de prevalências por raça
  (SIDRA 10132). Por isso este script precisa da coluna raca_cor (rode antes respostas_raca_cor.py).
  As diferenças entre distritos vêm só da composição por raça/cor.
  Tipos: cópula gaussiana com as prevalências dos tipos do e-SUS (premissas do gerador, SIDRA 10127)
  e correlação calibrada para reproduzir a prevalência total; 'Outra' em 3% das pessoas com
  deficiência (cenário base); TEA pelo autismo diagnosticado (SIDRA 10145), independente.
  São as mesmas fontes e regras do gerador do projeto (atributos.gera_deficiencia).

Como sorteia
  Uma semente por distrito (SEMENTE_BASE + id_ds), diferente das usadas para raça/cor. As colunas
  que já existem não mudam. Rodar de novo produz os mesmos valores.

Uso (PowerShell, na raiz do projeto)
  $env:APS_DSN = '<string de conexão do Neon>'
  python atividades/respostas_deficiencia.py
"""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg
from scipy import stats
from scipy.stats import binomtest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aps_sintetico import parametros as P  # noqa: E402
from aps_sintetico.atributos import rho_tipos  # noqa: E402
from aps_sintetico.config import carrega  # noqa: E402

TABELA = "respostas_sinteticas"
SEMENTE_BASE = 20261216
RACA_COD = {"Branca": 1, "Preta": 2, "Amarela": 3, "Parda": 4, "Indígena": 5}
TIPOS_FUNC = [(13, "Visual"), (12, "Auditiva"), (15, "Física"), (14, "Intelectual / Cognitiva")]
ORDEM_TIPOS = ["Visual", "Auditiva", "Física", "Intelectual / Cognitiva", "TEA", "Outra"]


def _media_adultos(tab: pd.DataFrame, pop_si: np.ndarray) -> float:
    """Prevalência média entre adultos: faixas do Censo ponderadas pela população por idade simples."""
    num = den = 0.0
    for _, r in tab.iterrows():
        ini, fim = max(int(r["ini"]), 18), min(int(r["fim"]), P.IDADE_MAX)
        if ini > fim:
            continue
        w = pop_si[int(r["sexo"]), ini:fim + 1].sum()
        num += w * float(r["prev"])
        den += w
    return num / den


def parametros() -> dict:
    pop = P.pop_sexo_idade_raca()                        # sexo × idade × raça (Recife)
    pop_si = pop.sum(axis=2)
    p_func = _media_adultos(P.deficiencia_sexo_idade(), pop_si)
    p_tea = _media_adultos(P.autismo_sexo_idade(), pop_si)
    # razão de prevalência por raça (10132), normalizada para manter a média dos adultos
    prev_r = P.deficiencia_raca()
    razao = np.array([prev_r[c] / P.prev_deficiencia_total() for c in P.RACAS])
    w = pop[:, 18:, :].sum(axis=(0, 1))
    w = w / w.sum()
    p_func_raca = {int(c): p_func * razao[i] / float((w * razao).sum()) for i, c in enumerate(P.RACAS)}
    tipos = P.tipos_deficiencia()
    prev_tipos = np.array([tipos[c] for c, _ in TIPOS_FUNC])
    return {"p_func_adulto": p_func, "p_tea_adulto": p_tea, "p_func_raca": p_func_raca,
            "limiares": stats.norm.ppf(1 - prev_tipos),
            "rho": rho_tipos(prev_tipos, P.prev_deficiencia_total()),
            "p_outra": float(carrega().atributos.outra_deficiencia)}


def conecta():
    dsn = os.environ.get("APS_DSN")
    if not dsn:
        sys.exit("Defina a variável de ambiente APS_DSN com a conexão do Neon antes de rodar.")
    return psycopg.connect(dsn)


def _tipos_funcionais(rng, n: int, limiares: np.ndarray, rho: float) -> np.ndarray:
    """n × 4 booleanos, com pelo menos um tipo por pessoa (amostragem por rejeição)."""
    cov = np.full((4, 4), rho)
    np.fill_diagonal(cov, 1)
    out = np.zeros((n, 4), dtype=bool)
    feito = 0
    while feito < n:
        z = rng.multivariate_normal(np.zeros(4), cov, size=(n - feito) * 14)
        z = z[(z > limiares).any(axis=1)][: n - feito]
        out[feito:feito + len(z)] = z > limiares
        feito += len(z)
    return out


def sorteia(conn, par: dict) -> pd.DataFrame:
    ids = pd.DataFrame(conn.execute(f"SELECT id_ds, id_resposta, raca_cor FROM {TABELA} "
                                    "ORDER BY id_ds, id_resposta").fetchall(),
                       columns=["id_ds", "id_resposta", "raca_cor"])
    if ids["raca_cor"].isna().any():
        sys.exit("A coluna raca_cor está vazia em algumas linhas; rode antes atividades/respostas_raca_cor.py.")
    partes = []
    for ds, g in ids.groupby("id_ds", sort=True):
        rng = np.random.default_rng(SEMENTE_BASE + int(ds))
        g = g.copy()
        n = len(g)
        p = g["raca_cor"].map(lambda r: par["p_func_raca"][RACA_COD[r]]).values
        func = rng.random(n) < p
        tea = rng.random(n) < par["p_tea_adulto"]
        tipos = np.zeros((n, 6), dtype=bool)               # colunas na ordem de ORDEM_TIPOS
        tipos[func, :4] = _tipos_funcionais(rng, int(func.sum()), par["limiares"], par["rho"])
        tipos[:, 4] = tea
        tipos[:, 5] = func & (rng.random(n) < par["p_outra"])
        tem = tipos.any(axis=1)
        g["tem_deficiencia"] = np.where(tem, "Sim", "Não")
        g["tipos_deficiencia"] = ["; ".join(t for t, b in zip(ORDEM_TIPOS, linha) if b) or None for linha in tipos]
        g["p_esperado"] = 1 - (1 - p) * (1 - par["p_tea_adulto"])
        partes.append(g)
    return pd.concat(partes, ignore_index=True)


def grava(conn, df: pd.DataFrame) -> int:
    cols = ["id_ds", "id_resposta", "tem_deficiencia", "tipos_deficiencia"]
    with conn.cursor() as cur:
        cur.execute(f"ALTER TABLE {TABELA} ADD COLUMN IF NOT EXISTS tem_deficiencia TEXT")
        cur.execute(f"ALTER TABLE {TABELA} ADD COLUMN IF NOT EXISTS tipos_deficiencia TEXT")
        cur.execute("CREATE TEMPORARY TABLE tmp_def (id_ds SMALLINT, id_resposta INT, tem_deficiencia TEXT, "
                    "tipos_deficiencia TEXT) ON COMMIT DROP")
        buf = io.StringIO()
        df[cols].to_csv(buf, index=False, header=False, na_rep="\\N")
        with cur.copy("COPY tmp_def FROM STDIN WITH (FORMAT csv, NULL '\\N')") as cp:
            cp.write(buf.getvalue())
        cur.execute(f"UPDATE {TABELA} r SET tem_deficiencia = t.tem_deficiencia, "
                    "tipos_deficiencia = t.tipos_deficiencia FROM tmp_def t "
                    "WHERE r.id_ds = t.id_ds AND r.id_resposta = t.id_resposta")
        n = cur.rowcount
    if n != len(df):
        conn.rollback()
        sys.exit(f"Esperava atualizar {len(df)} linhas e atualizei {n}; nada foi gravado.")
    conn.commit()
    return n


SQL_VALIDACAO = f"""
SELECT id_ds,
       COUNT(*)                                                            AS n,
       COUNT(*) FILTER (WHERE tem_deficiencia = 'Sim')                     AS com_deficiencia,
       COUNT(*) FILTER (WHERE tipos_deficiencia LIKE '%Visual%')           AS visual,
       COUNT(*) FILTER (WHERE tipos_deficiencia LIKE '%Auditiva%')         AS auditiva,
       COUNT(*) FILTER (WHERE tipos_deficiencia LIKE '%Física%')           AS fisica,
       COUNT(*) FILTER (WHERE tipos_deficiencia LIKE '%Intelectual%')      AS intelectual,
       COUNT(*) FILTER (WHERE tipos_deficiencia LIKE '%TEA%')              AS tea,
       COUNT(*) FILTER (WHERE tipos_deficiencia LIKE '%Outra%')            AS outra
FROM {TABELA}
GROUP BY id_ds
ORDER BY id_ds"""


def valida(conn, df: pd.DataFrame) -> pd.DataFrame:
    """Contagem SQL por DS e binomtest de 'tem deficiência' contra a prevalência esperada do DS
    (média das probabilidades usadas, que dependem da raça/cor de cada resposta)."""
    obs = pd.DataFrame(conn.execute(SQL_VALIDACAO).fetchall(),
                       columns=["id_ds", "n", "com_def", "Visual", "Auditiva", "Física", "Intelectual", "TEA", "Outra"])
    esp = df.groupby("id_ds")["p_esperado"].mean()
    linhas = []
    for _, r in obs.iterrows():
        n, k, p0 = int(r["n"]), int(r["com_def"]), float(esp.loc[r["id_ds"]])
        t = binomtest(k, n, p0)
        linhas.append({"DS": int(r["id_ds"]), "n": n, "%def": round(100 * k / n, 2), "%esperado": round(100 * p0, 2),
                       **{f"%{c}": round(100 * int(r[c]) / n, 2)
                          for c in ["Visual", "Auditiva", "Física", "Intelectual", "TEA", "Outra"]},
                       "p": round(t.pvalue, 3), "rejeita_H0": t.pvalue < 0.05})
    return pd.DataFrame(linhas)


def main() -> None:
    pd.set_option("display.width", 200)
    par = parametros()
    print(f"Prevalência entre adultos (Censo 2022, Recife): deficiência funcional "
          f"{par['p_func_adulto']:.2%}; TEA {par['p_tea_adulto']:.2%}")
    print("Deficiência funcional por raça/cor:",
          {r: f"{par['p_func_raca'][c]:.2%}" for r, c in RACA_COD.items()})
    print(f"Correlação da cópula entre tipos: {par['rho']:.3f}")
    print("Sementes:", {ds: SEMENTE_BASE + ds for ds in range(1, 9)})
    with conecta() as conn:
        df = sorteia(conn, par)
        n = grava(conn, df)
        print(f"\nColunas tem_deficiencia e tipos_deficiencia gravadas em {n:,} linhas de {TABELA}."
              .replace(",", "."))
        print("\nValidação (contagem SQL por DS + binomtest de 'tem deficiência', α = 5%):")
        print(valida(conn, df).to_string(index=False))


if __name__ == "__main__":
    main()
