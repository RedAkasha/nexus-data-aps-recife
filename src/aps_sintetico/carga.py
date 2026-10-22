"""Etapa 8 – carga no PostgreSQL 16 (psycopg 3, sem depender do psql; funciona no Windows).

Rotas:
  direta (padrão)  : COPY dos CSV do núcleo gerados pelo exportador.
  --via-staging    : COPY dos CSV da staging (leiaute LEDI) e transformação pelo
                     sql/postgresql/06_staging_para_nucleo.sql. As duas rotas produzem as
                     mesmas linhas (teste em tests/test_rotas.py).
A conexão vem de --dsn ou da variável APS_DSN (padrão postgresql://aps:aps@localhost:5432/aps_recife).
"""
from __future__ import annotations

import csv
import logging
import os
from pathlib import Path

from .config import RAIZ

log = logging.getLogger("aps_sintetico")

DSN_PADRAO = "postgresql://aps:aps@localhost:5432/aps_recife"
SQL_PG = RAIZ / "sql" / "postgresql"
SCRIPTS_BASE = ["01_ddl.sql", "02_carga_dominios.sql", "03_validacao_carga.sql", "04_carga_estrutura.sql",
                "05_carga_parametros.sql"]
# tabelas que o gerador grava direto nas duas rotas (não existem no LEDI)
SEMPRE_DIRETAS = ["microarea", "acao_formativa", "parametro"]


def dsn(valor: str | None = None) -> str:
    return valor or os.environ.get("APS_DSN", DSN_PADRAO)


def conecta(valor: str | None = None):
    import psycopg
    return psycopg.connect(dsn(valor), autocommit=False)


def _executa_arquivo(cur, caminho: Path, **variaveis) -> None:
    sql = caminho.read_text(encoding="utf-8")
    for k, v in variaveis.items():
        sql = sql.replace(f":{k}", str(int(v)))
    cur.execute(sql)


def _copy(cur, tabela: str, arquivo: Path) -> int:
    with open(arquivo, encoding="utf-8", newline="") as f:
        cab = next(csv.reader([f.readline()]))
        cols = ", ".join(cab)
        with cur.copy(f"COPY {tabela} ({cols}) FROM STDIN WITH (FORMAT csv, NULL '\\N')") as cp:
            while bloco := f.read(1 << 20):
                cp.write(bloco)
    return cur.rowcount


def recria_esquemas(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS analitica CASCADE; DROP SCHEMA IF EXISTS stg CASCADE; "
                    "DROP SCHEMA IF EXISTS nucleo CASCADE;")
        for s in SCRIPTS_BASE:
            log.info("executando %s", s)
            _executa_arquivo(cur, SQL_PG / s)
    conn.commit()


def _poda_estrutura(cur, saida: Path) -> None:
    """Com só parte dos DS gerada, retira equipes e unidades sem dado (VC12)."""
    with open(saida / "nucleo" / "microarea.csv", encoding="utf-8") as f:
        ines = {ln.split(",")[1] for ln in list(f)[1:]}
    cur.execute("CREATE TEMPORARY TABLE tmp_ine (ine CHAR(10)) ON COMMIT DROP")
    with cur.copy("COPY tmp_ine (ine) FROM STDIN") as cp:
        for i in sorted(ines):
            cp.write_row((i,))
    cur.execute("DELETE FROM nucleo.equipe e WHERE NOT EXISTS (SELECT 1 FROM tmp_ine t WHERE t.ine = e.ine)")
    n = cur.rowcount
    cur.execute("DELETE FROM nucleo.unidade_saude u WHERE NOT EXISTS (SELECT 1 FROM nucleo.equipe e WHERE e.cnes = u.cnes)")
    if n:
        log.info("estrutura podada: %d equipes fora dos DS gerados", n)


def carrega(saida: Path, valor_dsn: str | None = None, via_staging: bool = False, recriar: bool = True,
            analitica: bool = True) -> dict:
    from .exporta import ORDEM_NUCLEO, ORDEM_STG
    saida = Path(saida)
    conn = conecta(valor_dsn)
    try:
        if recriar:
            recria_esquemas(conn)
        contagem: dict = {}
        with conn.cursor() as cur:
            _poda_estrutura(cur, saida)
            ref = saida / "analitica" / "ref_parametro_complementar.csv"
            if ref.exists():
                cur.execute("DELETE FROM analitica.ref_parametro_oficial WHERE fonte IN "
                            "('Gerador IPF', 'SESAU Boletim 01/2025')")
                contagem["analitica.ref_parametro_oficial (+)"] = _copy(cur, "analitica.ref_parametro_oficial", ref)
            if via_staging:
                for t in SEMPRE_DIRETAS:
                    contagem[f"nucleo.{t}"] = _copy(cur, f"nucleo.{t}", saida / "nucleo" / f"{t}.csv")
                for t in ORDEM_STG:
                    contagem[f"stg.{t}"] = _copy(cur, f"stg.{t}", saida / "staging" / f"{t}.csv")
                carga = int(open(saida / "nucleo" / "parametro.csv", encoding="utf-8").readlines()[1].split(",")[0])
                _executa_arquivo(cur, SQL_PG / "06_staging_para_nucleo.sql", carga=carga)
                contagem["nucleo.controle_defeito"] = _copy(cur, "nucleo.controle_defeito",
                                                            saida / "nucleo" / "controle_defeito.csv")
            else:
                for t in ORDEM_NUCLEO:
                    contagem[f"nucleo.{t}"] = _copy(cur, f"nucleo.{t}", saida / "nucleo" / f"{t}.csv")
                for t in ORDEM_STG:          # a staging também é carregada (VC15 e auditoria)
                    contagem[f"stg.{t}"] = _copy(cur, f"stg.{t}", saida / "staging" / f"{t}.csv")
            cur.execute("ANALYZE")
            if analitica:
                log.info("executando 07_analitica.sql")
                _executa_arquivo(cur, SQL_PG / "07_analitica.sql")
        conn.commit()
        return contagem
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def consulta(sql: str, valor_dsn: str | None = None):
    import pandas as pd
    with conecta(valor_dsn) as conn, conn.cursor() as cur:
        cur.execute(sql)
        cols = [d.name for d in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


# ------------------------------------------------------------------ MySQL 8 (rota direta)
def script_mysql(saida: Path) -> Path:
    """Escreve <saida>/carga_mysql.sql com LOAD DATA LOCAL INFILE para o núcleo, a staging e as
    referências. Rodar depois de sql/mysql/01 a 05:
        mysql --local-infile=1 -u root -p < saida/base/carga_mysql.sql
    (o servidor precisa de local_infile=ON). A camada analítica no MySQL fica para o Parquet
    (python -m aps_sintetico analitica) – o 07_analitica.sql é específico do PostgreSQL."""
    from .exporta import ORDEM_NUCLEO, ORDEM_STG
    saida = Path(saida).resolve()
    linhas = ["-- Gerado por aps_sintetico.carga.script_mysql – carga direta no MySQL 8",
              "SET NAMES utf8mb4;", "SET FOREIGN_KEY_CHECKS = 1;", ""]
    with open(saida / "nucleo" / "microarea.csv", encoding="utf-8") as f:
        ines = sorted({ln.split(",")[1] for ln in list(f)[1:]})
    lista = ", ".join(f"'{i}'" for i in ines)
    linhas += ["-- só as equipes dos DS gerados (VC12)",
               f"DELETE FROM nucleo.equipe WHERE ine NOT IN ({lista});",
               "DELETE u FROM nucleo.unidade_saude u LEFT JOIN nucleo.equipe e ON e.cnes = u.cnes WHERE e.ine IS NULL;",
               "DELETE FROM analitica.ref_parametro_oficial WHERE fonte IN ('Gerador IPF', 'SESAU Boletim 01/2025');", ""]
    alvos = [("analitica.ref_parametro_oficial", saida / "analitica" / "ref_parametro_complementar.csv")]
    alvos += [(f"nucleo.{t}", saida / "nucleo" / f"{t}.csv") for t in ORDEM_NUCLEO]
    alvos += [(f"stg.{t}", saida / "staging" / f"{t}.csv") for t in ORDEM_STG]
    for tabela, arq in alvos:
        with open(arq, encoding="utf-8") as f:
            cab = f.readline().strip().split(",")
        caminho = arq.as_posix()
        linhas.append(f"LOAD DATA LOCAL INFILE '{caminho}' INTO TABLE {tabela} CHARACTER SET utf8mb4 "
                      f"FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' ESCAPED BY '\\\\' "
                      f"LINES TERMINATED BY '\\n' IGNORE 1 LINES ({', '.join(cab)});")
    p = saida / "carga_mysql.sql"
    p.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return p
