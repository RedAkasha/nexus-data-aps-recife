"""Orquestra a geração (Etapas 6 e 7) na ordem do DAG e exporta o resultado."""
from __future__ import annotations

import logging
import time
from pathlib import Path

from . import atendimentos, atributos, cobertura, defeitos, dinamica, exporta, populacao, registro, territorio
from .config import RAIZ
from .modelo import Mundo

log = logging.getLogger("aps_sintetico")

PASSOS = [
    ("estrutura territorial e rede", territorio.gera_estrutura),
    ("população (IPF + TRS)", populacao.gera_pessoas),
    ("domicílios (homofilia)", populacao.gera_domicilios),
    ("populações especiais (eCR, eAPP)", cobertura.gera_populacoes_especiais),
    ("renda, instrução e trabalho", populacao.gera_socioeconomico),
    ("deficiência", atributos.gera_deficiencia),
    ("orientação sexual e identidade de gênero", atributos.gera_os_ig),
    ("microáreas e profissionais", territorio.gera_microareas_profissionais),
    ("adscrição", cobertura.adscreve),
    ("cobertura", cobertura.seleciona_cadastrados),
    ("datas do primeiro cadastro", cobertura.datas_primeiro_cadastro),
    ("modelo de registro", registro.gera_parametros_registro),
    ("componente temporal e oficinas", dinamica.componentes_equipe),
    ("óbitos", dinamica.obitos),
    ("mudanças", dinamica.mudancas),
    ("nascimentos", dinamica.nascimentos),
    ("segmentos de cadastro", dinamica.segmentos),
    ("versões da FCI", dinamica.gera_versoes),
    ("verdade por equipe e mês", dinamica.verdade_equipe_mes),
    ("defeitos de comportamento (Etapa 6)", dinamica.defeitos_comportamento),
    ("atendimentos (FAI)", atendimentos.gera_atendimentos),
    ("identidades", defeitos.monta_cidadaos),
    ("defeitos de processo (Etapa 7)", defeitos.injeta),
]


def gera(cfg) -> Mundo:
    mundo = Mundo(cfg)
    for nome, passo in PASSOS:
        t = time.perf_counter()
        passo(cfg, mundo)
        log.info("%-45s %6.1f s", nome, time.perf_counter() - t)
    return mundo


def destino_padrao(cfg) -> Path:
    return RAIZ / "saida" / str(cfg.nome)


def gera_e_exporta(cfg, destino: Path | None = None) -> dict:
    mundo = gera(cfg)
    destino = Path(destino) if destino else destino_padrao(cfg)
    t = time.perf_counter()
    man = exporta.grava(cfg, mundo, destino)
    log.info("%-45s %6.1f s", "exportação", time.perf_counter() - t)
    return man
