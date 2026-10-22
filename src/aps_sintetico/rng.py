"""Fluxos aleatórios reprodutíveis e independentes.

Cada módulo (e, quando faz sentido, cada distrito) recebe o seu próprio gerador,
derivado da semente do cenário por ``numpy.random.SeedSequence``. Assim a mesma
semente gera o mesmo banco, e gerar um distrito isolado não altera os demais.
"""
from __future__ import annotations

import zlib

import numpy as np


def fluxo(semente: int, nome: str, *chaves: int) -> np.random.Generator:
    entropia = [int(semente), zlib.crc32(nome.encode("utf-8"))] + [int(c) for c in chaves]
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence(entropia)))
