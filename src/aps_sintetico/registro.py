"""Passo 5 – modelo de registro (o mecanismo de dado faltante é o objeto do estudo).

Duas etapas, logística mista (Plano, seção 4.5):
    R  (a pergunta de OS foi feita)     logit P(R=1) = a_R[usf] + u_e + c_e(t) + kappa_R * crianca
    A  (a pessoa aceita informar | R=1) logit P(A=1) = a_A[usf] + v_e + c_e(t) + w_i
                                         + lambda * LGB + b_idade * (idade - 40) + kappa_A * crianca
    (u_e, v_e) ~ N2(0, sigma^2 [[1, rho], [rho, 1]]),  w_i ~ N(0, sigma_w^2)
Registro: R=1, A=1 -> "Sim" (valor); R=1, A=0 -> "Não"; R=0 -> "Não" com prob. pi (o campo
deseja_informar sai FALSE sem a pergunta) ou NI (nulo).
Os interceptos por USF são calibrados por quadratura de Gauss–Hermite para reproduzir
P(Sim) e P(NI) de cada USF; os deslocamentos kappa vêm da linha 3 da planilha.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import optimize, special

from .rng import fluxo

_GH_X, _GH_W = np.polynomial.hermite_e.hermegauss(24)
_GH_W = _GH_W / _GH_W.sum()


def _grade_2d(s_u: float, s_v: float, cov: float):
    """Nós e pesos de Gauss–Hermite para (u, v) normal bivariada (Cholesky)."""
    z1, z2 = np.meshgrid(_GH_X, _GH_X, indexing="ij")
    w = np.outer(_GH_W, _GH_W).ravel()
    r = 0.0 if s_u * s_v == 0 else cov / (s_u * s_v)
    u = s_u * z1.ravel()
    v = s_v * (r * z1.ravel() + np.sqrt(max(1 - r * r, 0)) * z2.ravel())
    return u, v, w


def calibra_interceptos(p_sim: float, p_ni: float, pi: float, sigma: float, rho: float, sigma_w: float,
                        desloc: float = 0.0, tau: float = 0.0, s_extra_a: float = 0.0) -> tuple[float, float]:
    """Resolve (a_R, a_A) tais que E[P(R)] = 1 - p_ni/(1-pi) e E[P(R)P(A)] = p_sim,
    integrando o efeito de equipe (u, v), o da pessoa w (somado a v) e o componente temporal
    da equipe na data de corte (DP tau, comum a R e A). ``desloc`` e ``s_extra_a`` são a média e o
    DP do termo de idade, que só entra na aceitação."""
    p_r = float(np.clip(1 - p_ni / max(1 - pi, 1e-9), 1e-4, 1 - 1e-4))
    s_u = np.sqrt(sigma ** 2 + tau ** 2)
    s_v = np.sqrt(sigma ** 2 + sigma_w ** 2 + tau ** 2 + s_extra_a ** 2)
    u, v, w = _grade_2d(s_u, s_v, rho * sigma * sigma + tau ** 2)
    a_r = optimize.brentq(lambda a: (w * special.expit(a + u)).sum() - p_r, -25, 25)
    alvo = float(np.clip(p_sim, 1e-5, p_r - 1e-5))
    a_a = optimize.brentq(lambda a: (w * special.expit(a_r + u) * special.expit(a + desloc + v)).sum() - alvo,
                          -25, 25)
    return a_r, a_a


def tau_corte(cfg) -> float:
    """DP do componente temporal (tendência + AR(1)) na data de corte."""
    d = cfg.dinamica
    anos = (pd.Timestamp(cfg.periodo.data_corte) - pd.Timestamp(cfg.periodo.inicio)).days / 365.25
    var_ar = float(d.ar_sd) ** 2 / (1 - float(d.ar_phi) ** 2)
    return float(np.sqrt((float(d.tendencia_sd) * anos) ** 2 + var_ar))


def termo_idade(cfg, mundo) -> tuple[float, float]:
    """Média e DP de b_idade * (idade - 40) entre os cadastrados elegíveis (idade de referência + 4 anos)."""
    p = mundo.pessoas
    idade = p.loc[p["cadastrado"], "idade_ref"].values + 4
    idade = idade[idade >= int(cfg.regra.idade_min_elegivel)]
    x = float(cfg.registro.inclinacao_idade) * (np.clip(idade, 11, 90) - 40)
    return (float(x.mean()), float(x.std())) if len(x) else (0.0, 0.0)


def deslocamentos_crianca(cfg, idade=(0.0, 0.0)) -> tuple[float, float]:
    """kappa_R e kappa_A: diferença de logito entre crianças e adultos na linha 3."""
    r = cfg.registro
    pi, sig, rho, sw = (float(r.pi_nao_sem_pergunta), float(r.sigma_equipe), float(r.rho_ra),
                        float(r.sigma_pessoa))
    ad, cr = r.linha3_adultos, r.linha3_criancas
    # interceptos municipais dos adultos e dos menores; o deslocamento é a diferença no
    # logito latente (integrada sobre os efeitos aleatórios, sem a atenuação da média marginal)
    tau = tau_corte(cfg)
    ar_a, aa_a = calibra_interceptos(ad["sim"], ad["ni"], pi, sig, rho, sw, desloc=idade[0], tau=tau,
                                     s_extra_a=idade[1])
    ar_c, aa_c = calibra_interceptos(cr["sim"], cr["ni"], pi, sig, rho, sw, tau=tau)
    return float(ar_c - ar_a), float(aa_c - aa_a)


def metas_usf(cfg, mundo) -> pd.DataFrame:
    """Metas (prop. Sim e NI entre adultos) por USF: CSV autorizado ou priori Beta,
    deslocada no logito para que a média ponderada pela população iguale a linha 3."""
    r = cfg.registro
    eq = mundo.equipes
    pop = mundo.pessoas[mundo.pessoas["cadastrado"]].groupby("equipe").size()
    usf = eq.assign(pop=eq["ine"].map(pop).fillna(0)).groupby("cnes")["pop"].sum()
    if r.metas_usf_csv:
        m = pd.read_csv(r.metas_usf_csv, dtype={"cnes": str}).set_index("cnes")
        return m.reindex(usf.index).fillna(m.mean()).assign(pop=usf)
    rng = fluxo(cfg.semente, "metas_usf")
    sim = rng.beta(*r.usf_sim_beta, len(usf))
    ni = rng.beta(*r.usf_ni_beta, len(usf))
    w = usf.values / max(usf.values.sum(), 1)

    def ancora(x, alvo):
        lx = special.logit(np.clip(x, 1e-4, 1 - 1e-4))
        d = optimize.brentq(lambda d: (w * special.expit(lx + d)).sum() - alvo, -10, 10)
        return special.expit(lx + d)
    return pd.DataFrame({"prop_sim": ancora(sim, r.linha3_adultos["sim"]),
                         "prop_ni": ancora(ni, r.linha3_adultos["ni"]), "pop": usf.values}, index=usf.index)


def _kappa_entre_usf(cfg, mundo, ints: dict, tau: float) -> tuple[float, float]:
    """Deslocamentos das crianças resolvidos sobre a mistura real de USF (pesos = crianças
    cadastradas de cada USF), para que a linha 3 das crianças saia na meta municipal."""
    r = cfg.registro
    pi, sig, rho, sw = (float(r.pi_nao_sem_pergunta), float(r.sigma_equipe), float(r.rho_ra),
                        float(r.sigma_pessoa))
    cr = r.linha3_criancas
    p = mundo.pessoas
    eq = mundo.equipes.set_index("ine")
    m = p["cadastrado"] & (p["idade_ref"] + 4 < int(cfg.regra.idade_min_elegivel)) & p["equipe"].isin(eq.index)
    w = eq["cnes"].reindex(p.loc[m, "equipe"]).value_counts()
    w = w[w.index.isin(list(ints))]
    if w.empty:
        return deslocamentos_crianca(cfg)
    a_r = np.array([ints[c][0] for c in w.index])[:, None]
    a_a = np.array([ints[c][1] for c in w.index])[:, None]
    wu = (w.values / w.values.sum())[:, None]
    u, v, wg = _grade_2d(np.sqrt(sig ** 2 + tau ** 2), np.sqrt(sig ** 2 + sw ** 2 + tau ** 2),
                         rho * sig * sig + tau ** 2)
    p_r = float(np.clip(1 - cr["ni"] / max(1 - pi, 1e-9), 1e-4, 1 - 1e-4))
    k_r = optimize.brentq(lambda k: (wu * wg * special.expit(a_r + k + u)).sum() - p_r, -20, 20)
    pr = special.expit(a_r + k_r + u)
    k_a = optimize.brentq(lambda k: (wu * wg * pr * special.expit(a_a + k + v)).sum() - cr["sim"], -20, 20)
    return float(k_r), float(k_a)


def gera_parametros_registro(cfg, mundo) -> None:
    """Interceptos por USF, efeitos de equipe e da pessoa, regime de raça/cor."""
    r = cfg.registro
    eq = mundo.equipes
    sig, rho, sw, pi = float(r.sigma_equipe), float(r.rho_ra), float(r.sigma_pessoa), float(r.pi_nao_sem_pergunta)
    metas = metas_usf(cfg, mundo)
    tau = tau_corte(cfg)
    ti = termo_idade(cfg, mundo)
    ints = {c: calibra_interceptos(m.prop_sim, m.prop_ni, pi, sig, rho, sw, desloc=ti[0], tau=tau, s_extra_a=ti[1])
            for c, m in metas.iterrows()}
    rng = fluxo(cfg.semente, "efeitos_equipe")
    cov = sig * sig * np.array([[1, rho], [rho, 1]])
    uv = rng.multivariate_normal([0, 0], cov, len(eq))
    eq["a_R"] = eq["cnes"].map(lambda c: ints[c][0])
    eq["a_A"] = eq["cnes"].map(lambda c: ints[c][1])
    eq["u_R"], eq["v_A"] = uv[:, 0], uv[:, 1]
    eq["hetero_raca"] = rng.random(len(eq)) < float(r.regime_hetero)
    eq["ritmo"] = rng.lognormal(0, float(cfg.dinamica.dp_ritmo_equipe), len(eq))
    atrasada = rng.random(len(eq)) < float(cfg.atendimentos.equipes_atrasadas)
    media = np.where(atrasada, 20.0, float(cfg.atendimentos.atraso_digitacao_dias))
    eq["atraso_medio"] = media * rng.lognormal(0, 0.3, len(eq))
    k_r, k_a = _kappa_entre_usf(cfg, mundo, ints, tau)
    mundo.verdade["registro"] = {"kappa_R": k_r, "kappa_A": k_a, "metas_usf": metas.reset_index()}
    pes = mundo.pessoas
    rng = fluxo(cfg.semente, "efeito_pessoa")
    pes["w_A"] = rng.normal(0, sw, len(pes))
    pes["u_def"] = rng.random(len(pes))            # persistência do registro de deficiência
    pes["u_ig_extra"] = rng.random(len(pes))


def probabilidades(cfg, mundo, idx: np.ndarray, ine: np.ndarray, idade: np.ndarray, c_tempo: np.ndarray):
    """P(R), P(A_os | R) e P(A_ig | R) de cada par (pessoa, equipe, momento)."""
    r = cfg.registro
    pes, eq = mundo.pessoas, mundo.equipes.set_index("ine")
    k_r, k_a = mundo.verdade["registro"]["kappa_R"], mundo.verdade["registro"]["kappa_A"]
    crianca = idade < int(cfg.regra.idade_min_elegivel)
    e = eq.loc[ine]
    lin_r = e["a_R"].values + e["u_R"].values + c_tempo + k_r * crianca
    lin_a = (e["a_A"].values + e["v_A"].values + c_tempo + pes["w_A"].values[idx]
             + float(r.inclinacao_idade) * (np.clip(idade, 11, 90) - 40) * ~crianca + k_a * crianca)
    p_r = special.expit(lin_r)
    p_a_os = special.expit(lin_a + float(r.lambda_lgb) * pes["lgb"].values[idx])
    p_a_ig = special.expit(lin_a + float(r.ig_desloca_aceita) + float(r.lambda_lgb) * pes["trans_nb"].values[idx])
    return p_r, p_a_os, p_a_ig, crianca


def desfecho(cfg, mundo, idx: np.ndarray, ine: np.ndarray, idade: np.ndarray, c_tempo: np.ndarray, rng) -> dict:
    """Sorteia o registro de OS/IG de um lote de versões (vetorizado).
    idx: posições em mundo.pessoas; ine: equipe da versão; c_tempo: componente temporal no logito."""
    r = cfg.registro
    pes = mundo.pessoas
    p_r, p_a_os, p_a_ig, crianca = probabilidades(cfg, mundo, idx, ine, idade, c_tempo)
    n = len(idx)
    R = rng.random(n) < p_r
    uA = rng.random(n)
    A_os = uA < p_a_os
    A_ig = uA < p_a_ig
    junto = rng.random(n) < float(r.ig_perguntado_junto)
    R_ig = np.where(R, junto, rng.random(n) < (1 - float(r.ig_perguntado_junto)) * p_r)
    pi = float(r.pi_nao_sem_pergunta)
    u_pi = rng.random(n)
    out = {}
    for nome, Rk, Ak in (("os", R, A_os), ("ig", R_ig, A_ig)):
        sim = Rk & Ak
        nao_perg = ~Rk & (u_pi < pi)
        deseja = np.where(sim, 1, np.where(Rk | nao_perg, 0, -1)).astype(np.int8)   # -1 = nulo (NI)
        out[f"R_{nome}"], out[f"deseja_{nome}"], out[f"nao_sem_perg_{nome}"] = Rk, deseja, nao_perg
    os_v = pes["os_true"].values[idx].copy()
    os_v[crianca] = 148                                  # resposta registrada para criança (defeito 6)
    sexo = pes["sexo"].values[idx]
    ig_v = pes["ig_true"].values[idx].copy()
    ig_v[crianca] = np.where(sexo[crianca] == 0, 200, 201)
    out["os"] = np.where(out["deseja_os"] == 1, os_v, -1)
    out["ig"] = np.where(out["deseja_ig"] == 1, ig_v, -1)
    out["p_sim_os"] = p_r * p_a_os
    out["crianca"] = crianca
    return out
