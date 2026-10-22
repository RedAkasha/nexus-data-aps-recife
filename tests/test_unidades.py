"""Testes das peças estatísticas, sem gerar a base."""
import numpy as np

from aps_sintetico import identificadores as I
from aps_sintetico import ipf, registro
from aps_sintetico.config import carrega
from aps_sintetico.rng import fluxo


def test_rng_reprodutivel_e_independente():
    a = fluxo(1, "x", 2).random(5)
    assert np.allclose(a, fluxo(1, "x", 2).random(5))
    assert not np.allclose(a, fluxo(1, "y", 2).random(5))


def test_cpf_cns_validos_e_unicos():
    rng = fluxo(7, "teste")
    cpf, cns = I.cpfs(rng, 5000), I.cnss(rng, 5000)
    assert len(set(cpf)) == 5000 and len(set(cns)) == 5000
    assert all(I.cpf_valido(c) for c in cpf) and all(I.cns_valido(c) for c in cns)
    assert not I.cpf_valido("11111111111")


def test_uuid_ledi():
    u = I.uuids_ledi(fluxo(1, "u"), np.array(["0001163"] * 3))
    assert all(len(x) == 44 and x.startswith("0001163-") and x[22] == "4" for x in u)


def test_ipf_reproduz_margens():
    rng = np.random.default_rng(0)
    alvo_l, alvo_c = np.array([30.0, 70.0]), np.array([20.0, 50.0, 30.0])
    semente = rng.random((2, 3)) + 0.1
    x, it, desvio = ipf.ipf(semente, [ipf.Restricao((0,), alvo_l.reshape(2, 1)),
                                      ipf.Restricao((1,), alvo_c.reshape(1, 3))])
    assert np.allclose(x.sum(axis=1), alvo_l, atol=1e-6) and np.allclose(x.sum(axis=0), alvo_c, atol=1e-6)


def test_trs_preserva_total():
    x = np.array([[1.4, 2.6], [0.5, 3.5]])
    n = ipf.trs(x, np.random.default_rng(1))
    assert n.sum() == round(x.sum()) and (np.abs(n - x) < 1).all()


def test_calibracao_interceptos_por_quadratura():
    """Monte Carlo do modelo misto reproduz P(Sim) e P(NI) alvo."""
    p_sim, p_ni, pi, s, rho, sw = 0.30, 0.04, 0.0, 1.0, 0.5, 0.8
    a_r, a_a = registro.calibra_interceptos(p_sim, p_ni, pi, s, rho, sw)
    rng = np.random.default_rng(3)
    uv = rng.multivariate_normal([0, 0], [[s * s, rho * s * s], [rho * s * s, s * s]], 400_000)
    w = rng.normal(0, sw, 400_000)
    pr = 1 / (1 + np.exp(-(a_r + uv[:, 0])))
    pa = 1 / (1 + np.exp(-(a_a + uv[:, 1] + w)))
    assert abs((pr * pa).mean() - p_sim) < 0.003
    assert abs((1 - pr).mean() - p_ni) < 0.002


def test_cenario_sobrescreve_so_o_que_muda():
    c = carrega("oficina_focalizada")
    assert c.oficinas.alocacao == "focalizada" and c.oficinas.efeito_logito == 0.2
    c = carrega(None, **{"registro.lambda_lgb": -0.5})
    assert c.registro.lambda_lgb == -0.5 and c.registro.sigma_equipe == 1.0
