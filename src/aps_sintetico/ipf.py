"""Ajuste proporcional iterativo (IPF; Deming e Stephan, 1940) e integerização TRS.

O IPF converge para a tabela de menor divergência de Kullback-Leibler em relação
à semente que satisfaz as marginais (Csiszár, 1975) e preserva as razões de
chances da semente nas interações não restringidas (Bishop; Fienberg; Holland, 1975).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Restricao:
    """Marginal-alvo de um tensor.

    ``eixos``: eixos mantidos na marginal. ``alvo``: array com a forma da soma
    sobre os demais eixos (``keepdims=True``). ``grupos``: opcional; agrega o eixo
    ``eixo_grupo`` segundo o vetor de rótulos (ex.: bairro -> distrito) antes de
    comparar com o alvo, cujo eixo correspondente tem tamanho ``grupos.max()+1``.
    """
    eixos: tuple[int, ...]
    alvo: np.ndarray
    grupos: np.ndarray | None = None
    eixo_grupo: int | None = None

    def soma(self, x: np.ndarray) -> np.ndarray:
        outros = tuple(i for i in range(x.ndim) if i not in self.eixos)
        s = x.sum(axis=outros, keepdims=True)
        if self.grupos is None:
            return s
        forma = list(s.shape)
        forma[self.eixo_grupo] = int(self.grupos.max()) + 1
        g = np.zeros(forma)
        idx = [slice(None)] * s.ndim
        for k in range(len(self.grupos)):
            idx_k = list(idx)
            idx_k[self.eixo_grupo] = slice(k, k + 1)
            idx_g = list(idx)
            idx_g[self.eixo_grupo] = slice(int(self.grupos[k]), int(self.grupos[k]) + 1)
            g[tuple(idx_g)] += s[tuple(idx_k)]
        return g

    def aplica(self, x: np.ndarray, soma: np.ndarray) -> None:
        fator = np.divide(self.alvo, soma, out=np.zeros_like(soma, dtype=float), where=soma > 0)
        if self.grupos is not None:
            fator = np.take(fator, self.grupos, axis=self.eixo_grupo)
        x *= fator


def ipf(semente: np.ndarray, restricoes: list[Restricao], tol: float = 1e-6, max_iter: int = 1000):
    """Retorna (tabela ajustada, iterações, desvio máximo final)."""
    x = semente.astype(float).copy()
    for r in restricoes:
        if not np.isclose(r.alvo.sum(), restricoes[0].alvo.sum(), rtol=1e-6):
            raise ValueError("marginais com totais diferentes: o IPF não converge")
    desvio = np.inf
    for it in range(1, max_iter + 1):
        desvio = 0.0
        for r in restricoes:
            s = r.soma(x)
            desvio = max(desvio, float(np.abs(s - r.alvo).max()))
            r.aplica(x, s)
        if desvio < tol:
            return x, it, desvio
    raise RuntimeError(f"IPF não convergiu em {max_iter} iterações (desvio {desvio:.3g})")


def trs(x: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Truncar, replicar e sortear (Lovelace; Ballas, 2013): contagens inteiras que
    preservam o total arredondado e, em esperança, cada célula."""
    plano = x.ravel()
    inteiro = np.floor(plano).astype(np.int64)
    resto = plano - inteiro
    faltam = int(round(plano.sum())) - int(inteiro.sum())
    if faltam > 0:
        p = resto / resto.sum()
        escolhidos = rng.choice(plano.size, size=faltam, replace=False, p=p)
        inteiro[escolhidos] += 1
    return inteiro.reshape(x.shape)
