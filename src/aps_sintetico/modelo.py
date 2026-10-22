"""Contêiner do mundo sintético em memória."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class Mundo:
    cfg: dict
    # território e rede
    distritos: pd.DataFrame | None = None
    bairros: pd.DataFrame | None = None
    setores: pd.DataFrame | None = None
    unidades: pd.DataFrame | None = None
    equipes: pd.DataFrame | None = None
    microareas: pd.DataFrame | None = None
    profissionais: pd.DataFrame | None = None
    lotacoes: pd.DataFrame | None = None
    acoes: pd.DataFrame | None = None
    # população
    pessoas: pd.DataFrame | None = None
    domicilios: pd.DataFrame | None = None
    # registros
    versoes: pd.DataFrame | None = None           # uma linha por versão da FCI
    deficiencias: pd.DataFrame | None = None      # versão x tipo declarado
    fichas: pd.DataFrame | None = None            # cabeçalho da FAI
    atendimentos: pd.DataFrame | None = None
    problemas: pd.DataFrame | None = None
    defeitos: list = field(default_factory=list)  # gabarito (controle_defeito)
    # verdade e diagnósticos
    verdade: dict = field(default_factory=dict)
    diagnostico: dict = field(default_factory=dict)
    meses: pd.DatetimeIndex | None = None

    def defeito(self, tabela: str, id_registro, tipo: int, etapa: int, campo=None, par=None, original=None):
        self.defeitos.append((tabela, str(id_registro), int(tipo), int(etapa), campo,
                              None if par is None else str(par), None if original is None else str(original)[:70]))
