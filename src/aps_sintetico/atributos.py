"""Passo 4 – atributos dependentes e verdadeiros (latentes) de cada pessoa.

DAG (Plano, Figura 1 e Apêndice B):
  idade, sexo, raça -> deficiência (logística aditiva calibrada às marginais 10125 e 10132)
  deficiência -> tipos (cópula gaussiana; correlação calibrada para a união do Censo)
  idade, sexo -> TEA (10145)
  idade, sexo -> OS* (PNS 2019; sem aresta raça -> OS*)
  idade -> IG* (Spizzirri et al., 2021; gradiente etário de premissa)
OS* e IG* são atributos de simulação: só vão para ``verdade/``; o banco recebe o
que for registrado no passo 5.
"""
from __future__ import annotations

import numpy as np
from scipy import optimize, special, stats

from . import parametros as P
from .rng import fluxo

# bits de deficiência verdadeira
VISUAL, AUDITIVA, FISICA, INTELECTUAL, TEA, OUTRA = 1, 2, 4, 8, 16, 32
BIT_CODIGO = {VISUAL: 13, AUDITIVA: 12, FISICA: 15, INTELECTUAL: 14, TEA: 232, OUTRA: 16}


def _calibra_logistica(grupo_a: np.ndarray, alvo_a: np.ndarray, grupo_b: np.ndarray, alvo_b: np.ndarray,
                       iter_: int = 40) -> np.ndarray:
    """logit p = alpha[a] + beta[b]; ajusta as médias por grupo às prevalências-alvo
    (raking de probabilidades, equivalente ao IPF do modelo log-linear sem interação)."""
    alpha = special.logit(np.clip(alvo_a, 1e-6, 1 - 1e-6))
    beta = np.zeros(len(alvo_b))
    for _ in range(iter_):
        for g in range(len(alvo_a)):
            m = grupo_a == g
            if m.any():
                f = lambda a: special.expit(a + beta[grupo_b[m]]).mean() - alvo_a[g]  # noqa: E731
                alpha[g] = optimize.brentq(f, -20, 20)
        for g in range(len(alvo_b)):
            m = grupo_b == g
            if m.any():
                f = lambda b: special.expit(alpha[grupo_a[m]] + b).mean() - alvo_b[g]  # noqa: E731
                beta[g] = optimize.brentq(f, -20, 20)
    return special.expit(alpha[grupo_a] + beta[grupo_b])


def rho_tipos(prev: np.ndarray, uniao: float) -> float:
    """Correlação permutável da cópula que reproduz P(ao menos um tipo) = união."""
    t = stats.norm.ppf(1 - prev)

    def f(r):
        c = np.full((len(prev), len(prev)), r)
        np.fill_diagonal(c, 1)
        # o CDF normal multivariado do SciPy usa quase-Monte Carlo randomizado: semente fixa
        # para que a mesma configuração gere a mesma base (reprodutibilidade byte a byte)
        mvn = stats.multivariate_normal(mean=np.zeros(len(prev)), cov=c)
        try:
            cdf = mvn.cdf(t, rng=np.random.default_rng(0))
        except TypeError:
            cdf = mvn.cdf(t, random_state=0)
        return 1 - cdf - uniao
    return float(optimize.brentq(f, 0.0, 0.95))


def gera_deficiencia(cfg, mundo) -> None:
    pes = mundo.pessoas
    rng = fluxo(cfg.semente, "deficiencia")
    idade = pes["idade_ref"].values
    sexo = pes["sexo"].values
    n = len(pes)
    bits = np.zeros(n, dtype=np.int16)
    elegivel = idade >= 2
    tab = P.deficiencia_sexo_idade()
    # grupo a = (sexo, faixa fina); grupo b = raça
    ga = np.full(n, -1)
    for k, r in tab.iterrows():
        ga[(sexo == r["sexo"]) & (idade >= r["ini"]) & (idade <= r["fim"])] = k
    prev_r = P.deficiencia_raca()
    gb = np.searchsorted(P.RACAS, pes["raca"].values)
    alvo_b = np.array([prev_r[int(c)] for c in P.RACAS])
    m = elegivel & (ga >= 0)
    p = np.zeros(n)
    p[m] = _calibra_logistica(ga[m], tab["prev"].values, gb[m], alvo_b)
    defi = rng.random(n) < p
    # tipos: cópula gaussiana, condicionada a ao menos um tipo (amostragem por rejeição)
    tipos = P.tipos_deficiencia()
    cods = [13, 12, 15, 14]
    prev = np.array([tipos[c] for c in cods])
    rho = cfg.atributos.rho_tipos_deficiencia or rho_tipos(prev, P.prev_deficiencia_total())
    mundo.diagnostico.setdefault("atributos", {})["rho_tipos_deficiencia"] = round(float(rho), 4)
    t = stats.norm.ppf(1 - prev)
    cov = np.full((4, 4), rho)
    np.fill_diagonal(cov, 1)
    idx = np.nonzero(defi)[0]
    falta = idx.copy()
    bit_vals = np.array([VISUAL, AUDITIVA, FISICA, INTELECTUAL])
    while len(falta):
        z = rng.multivariate_normal(np.zeros(4), cov, size=len(falta) * 14)
        ok = (z > t).any(axis=1)
        z = z[ok][: len(falta)]
        bits[falta[: len(z)]] = ((z > t) * bit_vals).sum(axis=1)
        falta = falta[len(z):]
    outra = defi & (rng.random(n) < float(cfg.atributos.outra_deficiencia))
    bits[outra] |= OUTRA
    # TEA (10145), independente das dificuldades funcionais
    aut = P.autismo_sexo_idade()
    p_tea = np.zeros(n)
    for _, r in aut.iterrows():
        p_tea[(sexo == r["sexo"]) & (idade >= r["ini"]) & (idade <= r["fim"])] = r["prev"]
    tea = rng.random(n) < p_tea
    bits[tea] |= TEA
    pes["def_funcional"] = defi
    pes["def_bits"] = bits
    pes["p_def"] = p


def _faixa_os(idade: np.ndarray) -> np.ndarray:
    return np.select([idade < 11, idade < 18, idade < 30, idade < 40, idade < 60], [-1, 0, 1, 2, 3], 4)


def gera_os_ig(cfg, mundo) -> None:
    pes = mundo.pessoas
    a = cfg.atributos
    rng = fluxo(cfg.semente, "os_ig")
    idade = pes["idade_ref"].values
    sexo = pes["sexo"].values
    n = len(pes)
    grad = a.gradiente_os
    razao = {k: v / float(a.os_media_brasil) for k, v in grad.items()}
    taxa = float(a.lgb_pe)
    f = _faixa_os(idade)
    # crianças recebem o atributo da adolescência: só é observável a partir da idade mínima
    p_lgb = np.select([f <= 0, f == 1, f == 2, f == 3, f == 4],
                      [taxa * razao["18-29"] * float(a.os_adolescente_fator), taxa * razao["18-29"],
                       taxa * razao["30-39"], taxa * razao["40-59"], taxa * razao["60+"]], 0.0)
    lgb = rng.random(n) < p_lgb
    tipo = rng.choice(["homossexual", "bissexual", "outra"], n, p=[a.dist_lgb["homossexual"],
                                                                  a.dist_lgb["bissexual"], a.dist_lgb["outra"]])
    outra_cod = rng.choice(list(a.dist_outra_os.keys()), n, p=list(a.dist_outra_os.values()))
    os_ = np.full(n, 148, dtype=np.int16)          # heterossexual
    homo = lgb & (tipo == "homossexual")
    os_[homo & (sexo == 0)] = 196                   # gay
    os_[homo & (sexo == 1)] = 197                   # lésbica
    os_[lgb & (tipo == "bissexual")] = 154
    os_[lgb & (tipo == "outra")] = np.asarray(outra_cod, dtype=np.int16)[lgb & (tipo == "outra")]
    # identidade de gênero
    gi = a.gradiente_ig
    mult = np.select([idade < 30, idade < 50], [gi["11-29"], gi["30-49"]], gi["50+"])
    adul = idade >= 18
    norm = mult[adul].mean() if adul.any() else 1.0
    p_trans = float(a.trans) * mult / norm
    p_nb = float(a.nao_binario) * mult / norm
    u = rng.random(n)
    trans = u < p_trans
    nb = (u >= p_trans) & (u < p_trans + p_nb)
    ig = np.where(sexo == 0, 200, 201).astype(np.int16)   # cisgênero
    cod_trans = rng.choice(list(a.dist_trans.keys()), n, p=list(a.dist_trans.values())).astype(np.int16)
    # mulher trans e travesti: sexo atribuído masculino; homem trans: feminino
    cod_trans = np.where(sexo == 1, 149, np.where(cod_trans == 149, 150, cod_trans))
    ig[trans] = cod_trans[trans]
    ig[nb] = 203
    pes["os_true"] = os_
    pes["lgb"] = lgb
    pes["ig_true"] = ig
    pes["trans_nb"] = trans | nb
    pes["nome_social"] = pes["trans_nb"] & (rng.random(n) < float(a.nome_social_trans_nb))
    pes["recusa"] = rng.random(n) < float(a.recusa_cadastro)
