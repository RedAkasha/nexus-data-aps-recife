"""Passo 8 – identificadores e textos sintéticos.

CPF com os dois dígitos verificadores (módulo 11) e CNS válido (definitivo começando
por 1 ou 2; provisório por 7, 8 ou 9; soma ponderada dos 15 dígitos, pesos 15 a 1,
divisível por 11), as mesmas regras de ``nucleo.fn_cpf_valido`` e ``fn_cns_valido``.

Atenção: um número válido sorteado pode coincidir com o de uma pessoa real. Os
atributos associados são fictícios, mas a versão pública do banco deve trocar CPF e
CNS por chaves substitutas ou ser distribuída como código + semente (Plano, 4.8).
"""
from __future__ import annotations

import numpy as np

try:  # listas de nomes do Faker, usadas de forma vetorizada (rápido e reprodutível)
    from faker.providers.address.pt_BR import Provider as _End
    from faker.providers.person.pt_BR import Provider as _Pes

    def _lista(x):
        return list(x.keys()) if hasattr(x, "keys") else list(x)

    NOMES_M = _lista(_Pes.first_names_male)
    NOMES_F = _lista(_Pes.first_names_female)
    SOBRENOMES = _lista(_Pes.last_names)
    LOGRADOUROS = _lista(getattr(_End, "street_prefixes", ["Rua", "Avenida", "Travessa"]))
except Exception:  # pragma: no cover - Faker ausente
    NOMES_M = ["José", "João", "Antônio", "Francisco", "Carlos", "Paulo", "Pedro", "Lucas", "Luiz", "Marcos"]
    NOMES_F = ["Maria", "Ana", "Francisca", "Antônia", "Adriana", "Juliana", "Márcia", "Fernanda", "Patrícia"]
    SOBRENOMES = ["Silva", "Santos", "Oliveira", "Souza", "Lima", "Pereira", "Ferreira", "Costa", "Rodrigues"]
    LOGRADOUROS = ["Rua", "Avenida", "Travessa"]

NOMES_RUA = ["das Flores", "do Sol", "da Aurora", "dos Coqueiros", "da Paz", "São João", "Nova", "do Futuro",
             "da Esperança", "das Palmeiras", "do Rosário", "da Harmonia", "Santa Luzia", "do Progresso",
             "da Liberdade", "das Mangueiras", "do Bom Jesus", "da Saudade", "dos Navegantes", "da Concórdia"]


def cpfs(rng: np.random.Generator, n: int, excluir: set | None = None) -> np.ndarray:
    """n CPFs válidos e únicos (strings de 11 dígitos)."""
    excluir = set() if excluir is None else excluir
    saida: list[str] = []
    while len(saida) < n:
        k = int((n - len(saida)) * 1.05) + 10
        base = rng.integers(0, 10, size=(k, 9))
        rep = (base == base[:, :1]).all(axis=1)
        base = base[~rep]
        d1 = (base * np.arange(10, 1, -1)).sum(axis=1) * 10 % 11
        d1[d1 == 10] = 0
        d2 = ((base * np.arange(11, 2, -1)).sum(axis=1) + d1 * 2) * 10 % 11
        d2[d2 == 10] = 0
        nums = np.concatenate([base, d1[:, None], d2[:, None]], axis=1)
        for linha in nums:
            s = "".join(map(str, linha))
            if s not in excluir:
                excluir.add(s)
                saida.append(s)
                if len(saida) == n:
                    break
    return np.array(saida, dtype=object)


def cnss(rng: np.random.Generator, n: int, excluir: set | None = None, prop_definitivo: float = 0.7) -> np.ndarray:
    """n CNS válidos e únicos (15 dígitos)."""
    excluir = set() if excluir is None else excluir
    pesos = np.arange(15, 0, -1)
    saida: list[str] = []
    while len(saida) < n:
        k = int((n - len(saida)) * 1.3) + 10
        definitivo = rng.random(k) < prop_definitivo
        nums = np.empty((k, 15), dtype=np.int64)
        # definitivo: 11 dígitos (PIS) + "00" + ajuste + DV; provisório: 7/8/9 + 13 dígitos + DV
        nums[:, 0] = np.where(definitivo, rng.integers(1, 3, k), rng.integers(7, 10, k))
        nums[:, 1:14] = rng.integers(0, 10, size=(k, 13))
        nums[definitivo, 11] = 0
        nums[definitivo, 12] = 0
        soma = (nums[:, :14] * pesos[:14]).sum(axis=1)
        dv = (11 - soma % 11) % 11
        ok = dv < 10
        nums[:, 14] = np.where(ok, dv, 0)
        for linha in nums[ok]:
            s = "".join(map(str, linha))
            if s not in excluir:
                excluir.add(s)
                saida.append(s)
                if len(saida) == n:
                    break
    return np.array(saida, dtype=object)


def cpf_valido(s: str) -> bool:
    if len(s) != 11 or not s.isdigit() or len(set(s)) == 1:
        return False
    d = [int(c) for c in s]
    d1 = sum(d[i] * (10 - i) for i in range(9)) * 10 % 11 % 10
    d2 = (sum(d[i] * (11 - i) for i in range(9)) + d1 * 2) * 10 % 11 % 10
    return d1 == d[9] and d2 == d[10]


def cns_valido(s: str) -> bool:
    if len(s) != 15 or not s.isdigit() or s[0] not in "12789":
        return False
    return sum(int(c) * (15 - i) for i, c in enumerate(s)) % 11 == 0


def nomes(rng: np.random.Generator, sexo: np.ndarray) -> np.ndarray:
    """Nome + dois sobrenomes, conforme o sexo (0 masculino, 1 feminino)."""
    n = len(sexo)
    pm = rng.integers(0, len(NOMES_M), n)
    pf = rng.integers(0, len(NOMES_F), n)
    s1 = rng.integers(0, len(SOBRENOMES), n)
    s2 = rng.integers(0, len(SOBRENOMES), n)
    prim = np.where(sexo == 1, np.array(NOMES_F, dtype=object)[pf], np.array(NOMES_M, dtype=object)[pm])
    sob = np.array(SOBRENOMES, dtype=object)
    out = prim + " " + sob[s1] + " " + sob[s2]
    return np.array([x[:70] for x in out], dtype=object)


def prenomes(rng: np.random.Generator, feminino: np.ndarray) -> np.ndarray:
    pm = np.array(NOMES_M, dtype=object)[rng.integers(0, len(NOMES_M), len(feminino))]
    pf = np.array(NOMES_F, dtype=object)[rng.integers(0, len(NOMES_F), len(feminino))]
    return np.where(feminino, pf, pm)


def uuids_ledi(rng: np.random.Generator, cnes: np.ndarray) -> np.ndarray:
    """UUID no formato do LEDI: CNES + '-' + UUID v4 (44 caracteres)."""
    n = len(cnes)
    b = rng.integers(0, 256, size=(n, 16), dtype=np.uint8)
    b[:, 6] = (b[:, 6] & 0x0F) | 0x40
    b[:, 8] = (b[:, 8] & 0x3F) | 0x80
    hexs = [x.tobytes().hex() for x in b]
    return np.array([f"{c}-{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}" for c, h in zip(cnes, hexs)],
                    dtype=object)


def enderecos(rng: np.random.Generator, n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Logradouro, número e CEP (faixa 50000-000 a 52999-999 do Recife). Só na staging."""
    pref = np.array(["Rua", "Avenida", "Travessa", "Rua", "Rua"], dtype=object)[rng.integers(0, 5, n)]
    nome = np.array(NOMES_RUA, dtype=object)[rng.integers(0, len(NOMES_RUA), n)]
    num = rng.integers(1, 2000, n).astype(str).astype(object)
    cep = (rng.integers(50000000, 53000000, n)).astype(str).astype(object)
    return pref + " " + nome, num, cep
