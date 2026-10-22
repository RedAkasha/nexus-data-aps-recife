"""Leitura do cenário (YAML) com herança do cenário base."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

RAIZ = Path(__file__).resolve().parents[2]
CONFIG_BASE = RAIZ / "config" / "cenario_base.yaml"


class Cfg(dict):
    """Dicionário com acesso por atributo (cfg.registro.sigma_equipe)."""

    def __getattr__(self, nome: str) -> Any:
        try:
            v = self[nome]
        except KeyError as exc:
            raise AttributeError(nome) from exc
        return Cfg(v) if isinstance(v, dict) and not isinstance(v, Cfg) else v

    def __setattr__(self, nome: str, valor: Any) -> None:
        self[nome] = valor


def _mescla(base: dict, novo: dict) -> dict:
    saida = copy.deepcopy(base)
    for k, v in (novo or {}).items():
        if isinstance(v, dict) and isinstance(saida.get(k), dict) and not k.startswith("dist_") \
                and k not in ("taxas_anuais", "gradiente_os", "gradiente_ig", "sazonalidade"):
            saida[k] = _mescla(saida[k], v)
        else:
            saida[k] = copy.deepcopy(v)
    return saida


def carrega(caminho: str | Path | None = None, **sobrescreve: Any) -> Cfg:
    """Carrega o cenário base e, se informado, um cenário que o sobrescreve.

    Argumentos nomeados sobrescrevem chaves de primeiro nível ou com ponto
    (ex.: ``carrega(escala=0.05, **{"registro.sigma_equipe": 1.5})``).
    """
    base = yaml.safe_load(CONFIG_BASE.read_text(encoding="utf-8"))
    if caminho:
        caminho = Path(caminho)
        if not caminho.exists() and (RAIZ / "config" / "cenarios" / f"{caminho}.yaml").exists():
            caminho = RAIZ / "config" / "cenarios" / f"{caminho}.yaml"
        if caminho.resolve() != CONFIG_BASE.resolve():
            base = _mescla(base, yaml.safe_load(caminho.read_text(encoding="utf-8")))
    for chave, valor in sobrescreve.items():
        if valor is None:
            continue
        alvo = base
        partes = chave.split(".")
        for p in partes[:-1]:
            alvo = alvo.setdefault(p, {})
        alvo[partes[-1]] = valor
    if not 0 < float(base["escala"]) <= 1:
        raise ValueError("escala deve estar em (0, 1]")
    return Cfg(base)


def _simples(x):
    if isinstance(x, dict):
        return {k: _simples(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_simples(v) for v in x]
    return x


def salva(cfg: dict, caminho: Path) -> None:
    Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    Path(caminho).write_text(yaml.safe_dump(_simples(cfg), allow_unicode=True, sort_keys=False), encoding="utf-8")
