"""Atividade – inclui raça/cor na tabela respostas_sinteticas (Neon).

De onde vêm as probabilidades
  O Censo 2022 não publica raça/cor por bairro nem por distrito sanitário. Por isso o script usa
  a estimativa por DS do próprio gerador do projeto (populacao.raca_por_ds): nascidos vivos de
  2024 por raça da mãe em cada DS (Boletim SESAU 01/2025), corrigidos pela natalidade maior entre
  mulheres negras e ajustados por IPF à população dos DS e aos totais de raça/cor do Censo 2022.
  Essa estimativa vale para todas as idades; o script a ajusta para adultos (18+) com a estrutura
  municipal do Censo 2022 (SIDRA 9606): p(raça | DS, adulto) ∝ p(raça | DS) × p(raça | adulto) / p(raça).

Como sorteia
  Uma semente por distrito (SEMENTE_BASE + id_ds). Raça/cor é sorteada de forma independente da
  orientação sexual e da identidade de gênero: a PNS 2019 não encontrou diferença significativa na
  proporção de homossexuais e bissexuais entre brancos, pretos e pardos. As colunas que já existem
  não mudam, então o binomtest contra 2,5% continua igual.

Uso (PowerShell, na raiz do projeto)
  $env:APS_DSN = '<string de conexão do Neon>'
  python atividades/respostas_raca_cor.py

Rodar de novo produz os mesmos valores (mesmas sementes, mesma ordem por id_resposta).
"""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg
from scipy.stats import chisquare

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aps_sintetico import parametros as P  # noqa: E402
from aps_sintetico.config import carrega  # noqa: E402
from aps_sintetico.populacao import raca_por_ds  # noqa: E402

TABELA = "respostas_sinteticas"
SEMENTE_BASE = 20261116
# códigos do IBGE/e-SUS (P.RACAS = 1, 2, 3, 4, 5) → rótulos do dom_raca_cor
ROTULOS = {1: "Branca", 2: "Preta", 3: "Amarela", 4: "Parda", 5: "Indígena"}
ORDEM = ["Branca", "Preta", "Parda", "Amarela", "Indígena"]


def probabilidades() -> pd.DataFrame:
    """Probabilidade de cada raça/cor entre os adultos de cada DS (linhas: id_ds 1 a 8)."""
    tab, _ = raca_por_ds(carrega())
    p_ds = tab.div(tab.sum(axis=1), axis=0)
    pop = P.pop_sexo_idade_raca()                       # sexo × idade (0-100+) × raça, Recife
    adultos = pop[:, 18:, :].sum(axis=(0, 1))
    todos = pop.sum(axis=(0, 1))
    ajuste = (adultos / adultos.sum()) / (todos / todos.sum())
    p = p_ds * ajuste
    p = p.div(p.sum(axis=1), axis=0)
    p.columns = [ROTULOS[int(c)] for c in p.columns]
    return p[ORDEM]


def conecta():
    dsn = os.environ.get("APS_DSN")
    if not dsn:
        sys.exit("Defina a variável de ambiente APS_DSN com a conexão do Neon antes de rodar.")
    return psycopg.connect(dsn)


def sorteia(conn, p: pd.DataFrame) -> pd.DataFrame:
    """Sorteia raça/cor para cada resposta, distrito a distrito, com a semente do distrito."""
    ids = pd.DataFrame(conn.execute(f"SELECT id_ds, id_resposta FROM {TABELA} ORDER BY id_ds, id_resposta")
                       .fetchall(), columns=["id_ds", "id_resposta"])
    if ids.duplicated().any():
        sys.exit("A tabela tem pares (id_ds, id_resposta) repetidos; não dá para atualizar linha a linha.")
    partes = []
    for ds, g in ids.groupby("id_ds", sort=True):
        rng = np.random.default_rng(SEMENTE_BASE + int(ds))
        g = g.copy()
        g["raca_cor"] = rng.choice(ORDEM, size=len(g), p=p.loc[int(ds)].values)
        partes.append(g)
    return pd.concat(partes, ignore_index=True)


def grava(conn, df: pd.DataFrame) -> int:
    with conn.cursor() as cur:
        cur.execute(f"ALTER TABLE {TABELA} ADD COLUMN IF NOT EXISTS raca_cor TEXT")
        cur.execute("CREATE TEMPORARY TABLE tmp_raca (id_ds SMALLINT, id_resposta INT, raca_cor TEXT) ON COMMIT DROP")
        buf = io.StringIO()
        df.to_csv(buf, index=False, header=False)
        with cur.copy("COPY tmp_raca (id_ds, id_resposta, raca_cor) FROM STDIN WITH (FORMAT csv)") as cp:
            cp.write(buf.getvalue())
        cur.execute(f"UPDATE {TABELA} r SET raca_cor = t.raca_cor FROM tmp_raca t "
                    "WHERE r.id_ds = t.id_ds AND r.id_resposta = t.id_resposta")
        n = cur.rowcount
    if n != len(df):
        conn.rollback()
        sys.exit(f"Esperava atualizar {len(df)} linhas e atualizei {n}; nada foi gravado.")
    conn.commit()
    return n


SQL_VALIDACAO = f"""
SELECT id_ds,
       COUNT(*)                                          AS n,
       COUNT(*) FILTER (WHERE raca_cor = 'Branca')       AS branca,
       COUNT(*) FILTER (WHERE raca_cor = 'Preta')        AS preta,
       COUNT(*) FILTER (WHERE raca_cor = 'Parda')        AS parda,
       COUNT(*) FILTER (WHERE raca_cor = 'Amarela')      AS amarela,
       COUNT(*) FILTER (WHERE raca_cor = 'Indígena')     AS indigena,
       COUNT(*) FILTER (WHERE raca_cor IS NULL)          AS sem_raca
FROM {TABELA}
GROUP BY id_ds
ORDER BY id_ds"""


def valida(conn, p: pd.DataFrame) -> pd.DataFrame:
    """Contagem por DS no banco e qui-quadrado de aderência contra as probabilidades usadas."""
    obs = pd.DataFrame(conn.execute(SQL_VALIDACAO).fetchall(),
                       columns=["id_ds", "n", "Branca", "Preta", "Parda", "Amarela", "Indígena", "sem_raca"])
    linhas = []
    for _, r in obs.iterrows():
        o = r[ORDEM].astype(float).values
        e = p.loc[int(r["id_ds"])].values * o.sum()
        teste = chisquare(o, e)
        linhas.append({"DS": int(r["id_ds"]), "n": int(r["n"]),
                       **{f"%{c}": round(100 * v / r["n"], 1) for c, v in zip(ORDEM, o)},
                       "sem_raca": int(r["sem_raca"]),
                       "qui2": round(float(teste.statistic), 2), "p": round(float(teste.pvalue), 3),
                       "rejeita_H0": teste.pvalue < 0.05})
    return pd.DataFrame(linhas)


def main() -> None:
    pd.set_option("display.width", 160)
    p = probabilidades()
    print("Probabilidades de raça/cor entre adultos, por DS (%):")
    print((100 * p).round(1).to_string())
    print("Sementes:", {ds: SEMENTE_BASE + ds for ds in p.index})
    with conecta() as conn:
        df = sorteia(conn, p)
        n = grava(conn, df)
        print(f"\nColuna raca_cor gravada em {n:,} linhas de {TABELA}.".replace(",", "."))
        print("\nValidação (contagem SQL por DS + qui-quadrado de aderência, α = 5%):")
        print(valida(conn, p).to_string(index=False))


if __name__ == "__main__":
    main()
