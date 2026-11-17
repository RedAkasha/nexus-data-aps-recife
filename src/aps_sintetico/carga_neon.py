"""Carga seletiva para o Neon (plano gratuito: limite de 1 GB por projeto).

A carga completa (`carregar`) ocupa cerca de 1,2 GB sem a staging e passa do limite. Esta rota
leva só o que responde às perguntas do projeto e deixa de fora o que é volume sem análise nova:

  estrutura   domínios, distritos, bairros, setores, unidades, equipes, microáreas,
              profissionais, lotações, ações formativas, parâmetros e referências oficiais
  cadastros   cidadao, cadastro_individual, cadastro_deficiencia, domicilio, familia
              (base das visões vw_cadastro_vigente, vw_monitoramento_* e vw_qualidade_registro)
  gabarito    controle_defeito (todos os defeitos apontam para tabelas de cadastro)
  analítica   dim_competencia, fato_indicador_equipe, fato_atendimento_equipe, fato_painel_ml,
              lidas dos Parquet de `python -m aps_sintetico analitica` (o 07_analitica.sql
              precisa das tabelas de atendimento, que não vão para o Neon)

Ficam de fora (as tabelas existem, vazias): ficha_atendimento, atendimento_individual,
atendimento_problema (~425 MB; a produção por equipe já está em fato_atendimento_equipe) e
toda a staging (cópia das mesmas fichas no leiaute LEDI).

Perfis:  padrao  (tudo acima, ~700 MB medidos num PostgreSQL 16)
         enxuto  (só estrutura e analítica, ~300 MB)

Uso:  $env:APS_DSN = '<string de conexão do Neon>'
      python -m aps_sintetico carregar-neon [--perfil enxuto]
"""
from __future__ import annotations

import io
import logging
import re
import time
from pathlib import Path

from . import carga

log = logging.getLogger("aps_sintetico")

CADASTROS = ["domicilio", "familia", "cidadao", "cadastro_individual", "cadastro_deficiencia"]
ESTRUTURA = ["setor_censitario", "microarea", "profissional", "lotacao", "acao_formativa", "parametro"]
GABARITO = ["controle_defeito"]
FORA = ["ficha_atendimento", "atendimento_individual", "atendimento_problema"]
ANALITICA = ["dim_competencia", "fato_atendimento_equipe", "fato_painel_ml", "fato_indicador_equipe"]
PERFIS = {
    "padrao": ESTRUTURA + CADASTROS + GABARITO,
    "enxuto": ESTRUTURA,
}
LIMITE_MB = 1024
# ordem das FKs do exportador (exporta.ORDEM_NUCLEO), sem as tabelas que ficam de fora
ORDEM = ["setor_censitario", "microarea", "profissional", "lotacao", "acao_formativa", "domicilio", "familia",
         "cidadao", "cadastro_individual", "cadastro_deficiencia", "parametro", "controle_defeito"]


def _indices_secundarios(tabelas: list[str]) -> list[tuple[str, str]]:
    """(esquema.nome, CREATE INDEX ...) do 01_ddl.sql para as tabelas carregadas. Criar esses índices
    depois do COPY deixa a carga mais rápida e os índices mais compactos."""
    ddl = (carga.SQL_PG / "01_ddl.sql").read_text(encoding="utf-8")
    alvo = {f"nucleo.{t}" for t in tabelas} | {f"analitica.{t}" for t in ANALITICA}
    out = []
    for m in re.finditer(r"^CREATE INDEX (\w+) ON ([\w.]+) \(.*?\);", ddl, flags=re.M):
        if m.group(2) in alvo:
            out.append((f"{m.group(2).split('.')[0]}.{m.group(1)}", m.group(0)))
    return out


def _visao_rq04() -> str:
    """A visão vw_rq04_raca_equipe fica no fim do 07_analitica.sql, que não roda no Neon."""
    sql = (carga.SQL_PG / "07_analitica.sql").read_text(encoding="utf-8")
    i = sql.index("CREATE OR REPLACE VIEW analitica.vw_rq04_raca_equipe")
    return sql[i:]


def _copy_parquet(cur, tabela: str, arquivo: Path, lote: int = 200_000) -> int:
    import pandas as pd
    df = pd.read_parquet(arquivo)
    for c in df.columns:
        if str(df[c].dtype).startswith("datetime"):
            df[c] = df[c].dt.strftime("%Y-%m-%d")
    cols = ", ".join(df.columns)
    with cur.copy(f"COPY {tabela} ({cols}) FROM STDIN WITH (FORMAT csv, NULL '\\N')") as cp:
        for i in range(0, len(df), lote):
            buf = io.StringIO()
            df.iloc[i:i + lote].to_csv(buf, index=False, header=False, na_rep="\\N")
            cp.write(buf.getvalue())
    return len(df)


def _mb(cur) -> float:
    cur.execute("SELECT pg_database_size(current_database())")
    return cur.fetchone()[0] / 1048576


def carrega(saida: Path, valor_dsn: str | None = None, perfil: str = "padrao") -> dict:
    saida = Path(saida)
    tabelas = PERFIS[perfil]
    faltam = [p for p in [saida / "analitica" / f"{t}.parquet" for t in ANALITICA] if not p.exists()]
    if faltam:
        raise FileNotFoundError("Faltam os Parquet da analítica; rode antes: python -m aps_sintetico analitica"
                                f" ({faltam[0].name})")
    conn = carga.conecta(valor_dsn)
    t0 = time.time()
    try:
        print("Recriando esquemas e domínios (01 a 05)...", flush=True)
        carga.recria_esquemas(conn)
        indices = _indices_secundarios(tabelas)
        contagem: dict = {}
        with conn.cursor() as cur:
            for nome, _ in indices:
                cur.execute(f"DROP INDEX {nome}")
            carga._poda_estrutura(cur, saida)
            ref = saida / "analitica" / "ref_parametro_complementar.csv"
            if ref.exists():
                cur.execute("DELETE FROM analitica.ref_parametro_oficial WHERE fonte IN "
                            "('Gerador IPF', 'SESAU Boletim 01/2025')")
                contagem["analitica.ref_parametro_oficial (+)"] = carga._copy(cur, "analitica.ref_parametro_oficial", ref)
            ordem = [t for t in ORDEM if t in tabelas]
            for t in ordem:
                print(f"  nucleo.{t:28s}", end=" ", flush=True)
                contagem[f"nucleo.{t}"] = carga._copy(cur, f"nucleo.{t}", saida / "nucleo" / f"{t}.csv")
                print(f"{contagem[f'nucleo.{t}']:>10,} linhas".replace(",", "."), flush=True)
            for t in ANALITICA:
                print(f"  analitica.{t:25s}", end=" ", flush=True)
                contagem[f"analitica.{t}"] = _copy_parquet(cur, f"analitica.{t}", saida / "analitica" / f"{t}.parquet")
                print(f"{contagem[f'analitica.{t}']:>10,} linhas".replace(",", "."), flush=True)
            print(f"Criando {len(indices)} índices secundários...", flush=True)
            for _, sql in indices:
                cur.execute(sql)
            cur.execute(_visao_rq04())
            cur.execute("ANALYZE")
        conn.commit()
        with conn.cursor() as cur:
            tamanho = _mb(cur)
        contagem["_tamanho_mb"] = tamanho
        contagem["_segundos"] = time.time() - t0
        return contagem
    except Exception as e:
        conn.rollback()
        if type(e).__name__ == "DiskFull" and perfil != "enxuto":
            raise RuntimeError("O banco passou do limite de armazenamento do projeto Neon. "
                               "Tente o perfil menor: python -m aps_sintetico carregar-neon --perfil enxuto") from e
        raise
    finally:
        conn.close()

