"""Uma base pequena (DS I e III, 2% da população) gerada uma vez por sessão de teste."""
import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))


@pytest.fixture(scope="session")
def saida(tmp_path_factory):
    from aps_sintetico import analitica, config, gerador
    cfg = config.carrega("demo")
    destino = tmp_path_factory.mktemp("demo")
    gerador.gera_e_exporta(cfg, destino)
    analitica.constroi(destino)
    return destino


def banco_disponivel() -> bool:
    try:
        import psycopg
        from aps_sintetico.carga import dsn
        with psycopg.connect(dsn(), connect_timeout=3):
            return True
    except Exception:
        return False


precisa_banco = pytest.mark.skipif(not banco_disponivel() and not os.environ.get("APS_EXIGE_BANCO"),
                                   reason="PostgreSQL indisponível (defina APS_DSN)")
