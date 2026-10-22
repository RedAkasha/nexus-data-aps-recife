"""Linha de comando: python -m aps_sintetico <comando> [opções].

Comandos (na ordem do fluxo):
  gerar         gera a base sintética (Etapas 6 e 7) e exporta núcleo, staging e verdade
  carregar      carrega a saída no PostgreSQL (rota direta ou --via-staging) e monta a analítica SQL
  validar       relatório de calibração, integridade e qualidade × gabarito (Etapa 8)
  analitica     tabelas analíticas em Parquet, sem banco (Etapa 9)
  inferencia    estimativas por equipe, viés MNAR e efeito das oficinas contra a verdade (Etapa 10)
  ml            treina e avalia os modelos de regressão (Etapa 10; MLflow opcional)
  sensibilidade cenários, réplicas e hipercubo latino (Etapa 10)
  painel        abre o painel Streamlit
  tudo          gerar → analitica → [carregar → validar] → inferencia → ml
"""
from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

from .config import RAIZ


def _saida(a) -> Path:
    if a.saida:
        return Path(a.saida)
    nome = a.cenario if getattr(a, "cenario", None) else "base"
    return RAIZ / "saida" / nome


def _cfg(a):
    from .config import carrega
    extra = {}
    if a.escala is not None:
        extra["escala"] = a.escala
    if a.distritos:
        extra["distritos"] = [int(x) for x in a.distritos.split(",")]
    if a.semente is not None:
        extra["semente"] = a.semente
    for kv in a.set or []:
        k, v = kv.split("=", 1)
        import yaml
        extra[k] = yaml.safe_load(v)
    return carrega(a.cenario, **extra)


def cmd_gerar(a):
    from . import gerador
    cfg = _cfg(a)
    man = gerador.gera_e_exporta(cfg, _saida(a))
    print(f"Base gerada em {_saida(a)}")
    for k, v in man["linhas"].items():
        if k.startswith("nucleo/"):
            print(f"  {k:45s} {v:>10,}".replace(",", "."))


def cmd_carregar(a):
    from . import carga
    if getattr(a, "mysql", False):
        print(f"Script de carga MySQL: {carga.script_mysql(_saida(a))}")
        return
    c = carga.carrega(_saida(a), a.dsn, via_staging=a.via_staging, analitica=not a.sem_analitica)
    print(f"Carga concluída ({'staging → núcleo' if a.via_staging else 'direta'}): {sum(v or 0 for v in c.values()):,} linhas")


def cmd_validar(a):
    from . import valida
    p = valida.relatorio(_saida(a), a.dsn, com_banco=not a.sem_banco)
    print(p.read_text(encoding="utf-8").split("## 1.")[0])
    print(f"Relatório: {p}")


def cmd_analitica(a):
    from . import analitica
    out = analitica.constroi(_saida(a))
    print("Tabelas analíticas (Parquet): " + ", ".join(f"{k} ({len(v)})" for k, v in out.items()))


def cmd_inferencia(a):
    from . import inferencia
    p = inferencia.relatorio(_saida(a))
    print(p.read_text(encoding="utf-8"))


def cmd_ml(a):
    from . import ml
    r = ml.treina(_saida(a), usar_mlflow=not a.sem_mlflow)
    print(r[["modelo", "mae", "rmse", "r2", "precisao_k", "cv_mae"]].to_string(index=False))


def cmd_sensibilidade(a):
    from . import sensibilidade
    cen = a.cenarios.split(",") if a.cenarios else None
    ds = [int(x) for x in a.distritos.split(",")] if a.distritos else None
    df = sensibilidade.roda(cen, replicas=a.replicas, escala=a.escala or 0.03, distritos=ds, lhs=a.lhs,
                            manter=a.manter)
    print(f"{len(df)} execuções; resumo em saida/sensibilidade/sensibilidade.md")


def cmd_painel(a):
    app = RAIZ / "painel" / "app.py"
    return subprocess.call([sys.executable, "-m", "streamlit", "run", str(app), "--", "--saida", str(_saida(a))])


def cmd_tudo(a):
    cmd_gerar(a)
    cmd_analitica(a)
    if not a.sem_banco:
        a.via_staging, a.sem_analitica = False, False
        cmd_carregar(a)
        cmd_validar(a)
    else:
        from . import valida
        valida.relatorio(_saida(a), com_banco=False)
    cmd_inferencia(a)
    cmd_ml(a)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m aps_sintetico", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-v", "--verboso", action="store_true")
    sub = ap.add_subparsers(dest="comando", required=True)

    def comum(p, gera=False, banco=False):
        p.add_argument("--cenario", help="nome em config/cenarios/ ou caminho de YAML (padrão: base)")
        p.add_argument("--saida", help="pasta de saída (padrão: saida/<cenário>)")
        if gera:
            p.add_argument("--escala", type=float, help="fração da população (0 < escala ≤ 1)")
            p.add_argument("--distritos", help="DS a gerar, ex.: 1,3,7")
            p.add_argument("--semente", type=int)
            p.add_argument("--set", action="append", metavar="CHAVE=VALOR",
                           help="sobrescreve um parâmetro, ex.: --set registro.lambda_lgb=-0.69")
        if banco:
            p.add_argument("--dsn", help="conexão PostgreSQL (padrão: variável APS_DSN)")
        return p

    comum(sub.add_parser("gerar", help="gera a base"), gera=True).set_defaults(f=cmd_gerar)
    p = comum(sub.add_parser("carregar", help="carrega no PostgreSQL"), banco=True)
    p.add_argument("--via-staging", action="store_true")
    p.add_argument("--sem-analitica", action="store_true")
    p.add_argument("--mysql", action="store_true", help="só escreve o script LOAD DATA para MySQL 8")
    p.set_defaults(f=cmd_carregar)
    p = comum(sub.add_parser("validar", help="relatório de validação"), banco=True)
    p.add_argument("--sem-banco", action="store_true", help="só a calibração (sem PostgreSQL)")
    p.set_defaults(f=cmd_validar)
    comum(sub.add_parser("analitica", help="camada analítica em Parquet")).set_defaults(f=cmd_analitica)
    comum(sub.add_parser("inferencia", help="inferência contra a verdade")).set_defaults(f=cmd_inferencia)
    p = comum(sub.add_parser("ml", help="modelos de regressão"))
    p.add_argument("--sem-mlflow", action="store_true")
    p.set_defaults(f=cmd_ml)
    p = sub.add_parser("sensibilidade", help="cenários e hipercubo latino")
    p.add_argument("--cenarios", help="lista separada por vírgula (padrão: todos)")
    p.add_argument("--replicas", type=int, default=1)
    p.add_argument("--escala", type=float)
    p.add_argument("--distritos")
    p.add_argument("--lhs", type=int, default=0, help="nº de pontos do hipercubo latino")
    p.add_argument("--manter", action="store_true", help="guarda as bases de cada execução")
    p.set_defaults(f=cmd_sensibilidade)
    comum(sub.add_parser("painel", help="abre o painel Streamlit")).set_defaults(f=cmd_painel)
    p = comum(sub.add_parser("tudo", help="fluxo completo"), gera=True, banco=True)
    p.add_argument("--sem-banco", action="store_true")
    p.add_argument("--sem-mlflow", action="store_true")
    p.set_defaults(f=cmd_tudo)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO if a.verboso else logging.WARNING,
                        format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    return a.f(a) or 0
