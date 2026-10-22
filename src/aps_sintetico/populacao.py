"""Passo 2 – população base, domicílios, renda, escolaridade e trabalho.

1. Cor ou raça por Distrito Sanitário: estimador indireto a partir dos nascidos
   vivos por raça da mãe (boletim SESAU 01/2025), corrigido pela razão de
   natalidade, e ajustado por IPF aos totais do DS e do município (Plano, 3.2a).
2. IPF do tensor bairro x sexo x idade x raça: semente = estrutura municipal da
   tabela 9606 replicada; restrições = população do bairro (9923), sexo x idade x
   raça do município (9606) e raça por DS (passo 1).
3. Integerização TRS e expansão em pessoas.
4. Domicílios: pessoa de referência adulta, tamanho com média do bairro e
   homofilia racial (premissa); renda domiciliar per capita (10296) e instrução
   (10061) ligadas por cópula gaussiana.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from . import parametros as P
from .ipf import Restricao, ipf, trs
from .rng import fluxo


# ---------------------------------------------------------------- raça por DS
def raca_por_ds(cfg) -> tuple[pd.DataFrame, dict]:
    """Retorna tabela DS x raça (contagens na escala 1) e diagnóstico do estimador."""
    nasc = P.nascimentos_ds()
    r = float(cfg.populacao.razao_natalidade)
    s = nasc["negra"] / (nasc["negra"] + nasc["nao_negra"])
    pi = s / (s + (1 - s) * r)
    s_mun = nasc["negra"].sum() / nasc.values.sum()
    pi_mun = s_mun / (s_mun + (1 - s_mun) * r)

    semente_mun = P.pop_sexo_idade_raca()
    tot_raca = semente_mun.sum(axis=(0, 1))
    pop_b = P.bairros_censo()
    ba = P.estrutura()["bairro"].set_index("id_bairro")
    pop_ds = pop_b["pop"].groupby(ba.loc[pop_b.index, "id_ds"]).sum().sort_index()
    tot_raca = tot_raca / tot_raca.sum() * pop_ds.sum()

    a, ind = tot_raca[2] / tot_raca.sum(), tot_raca[4] / tot_raca.sum()
    frac_preta = tot_raca[1] / (tot_raca[1] + tot_raca[3])
    semente = np.zeros((8, 5))
    for d in range(1, 9):
        resto = 1 - a - ind
        semente[d - 1] = pop_ds[d] * np.array([resto * (1 - pi[d]), resto * pi[d] * frac_preta, a,
                                                resto * pi[d] * (1 - frac_preta), ind])
    x, it, _ = ipf(semente, [Restricao((0,), pop_ds.values.reshape(8, 1).astype(float)),
                             Restricao((1,), tot_raca.reshape(1, 5))])
    tab = pd.DataFrame(x, index=pd.Index(range(1, 9), name="id_ds"), columns=P.RACAS)
    diag = {"pi_negro_estimado": pi.round(4).to_dict(), "pi_municipio_estimado": round(float(pi_mun), 4),
            "pi_municipio_censo": round(float((tot_raca[1] + tot_raca[3]) / (tot_raca[0] + tot_raca[1] + tot_raca[3])), 4),
            "iteracoes_ipf_ds": it}
    return tab, diag


def tensor_populacao(cfg) -> tuple[np.ndarray, dict]:
    """Tensor ajustado [bairro(94), sexo(2), idade(101), raça(5)] na escala 1."""
    sem = P.pop_sexo_idade_raca()
    pop_b = P.bairros_censo().sort_index()
    total = pop_b["pop"].sum()
    sem = sem / sem.sum() * total                           # redistribui as 47 pessoas sem declaração
    ba = P.estrutura()["bairro"].set_index("id_bairro").loc[pop_b.index]
    grupos = (ba["id_ds"].values - 1).astype(int)
    tab_ds, diag = raca_por_ds(cfg)
    nb = len(pop_b)
    semente = (pop_b["pop"].values / total)[:, None, None, None] * sem[None, :, :, :]
    restr = [Restricao((0,), pop_b["pop"].values.reshape(nb, 1, 1, 1).astype(float)),
             Restricao((1, 2, 3), sem[None, :, :, :]),
             Restricao((0, 3), tab_ds.values.reshape(8, 1, 1, 5), grupos=grupos, eixo_grupo=0)]
    x, it, desvio = ipf(semente, restr, tol=1e-4, max_iter=2000)
    diag.update({"iteracoes_ipf": it, "desvio_final_ipf": desvio})
    return x, diag


# ---------------------------------------------------------------- pessoas
def gera_pessoas(cfg, mundo) -> None:
    x, diag = tensor_populacao(cfg)
    mundo.diagnostico["populacao"] = diag
    mundo.verdade["tensor_ipf"] = x
    pop_b = P.bairros_censo().sort_index()
    ba = P.estrutura()["bairro"].set_index("id_bairro")
    bairros_sel = [b for b in pop_b.index if ba.loc[b, "id_ds"] in cfg.distritos]
    linhas = []
    ref = np.datetime64(cfg.periodo.referencia_censo)
    for b in bairros_sel:
        rng = fluxo(cfg.semente, "populacao", b)
        cont = trs(x[b - 1] * cfg.escala, rng)                # [sexo, idade, raça]
        idx = np.nonzero(cont)
        reps = cont[idx]
        sexo = np.repeat(idx[0], reps)
        idade = np.repeat(idx[1], reps)
        raca = P.RACAS[np.repeat(idx[2], reps)]
        n = len(sexo)
        # idade 100+ distribuída entre 100 e 104 anos
        idade = np.where(idade == P.IDADE_MAX, idade + rng.integers(0, 5, n), idade)
        dias = (idade * 365.25 + rng.random(n) * 365.25).astype(int)
        dob = ref - dias.astype("timedelta64[D]")
        linhas.append(pd.DataFrame({"bairro": b, "ds": int(ba.loc[b, "id_ds"]), "sexo": sexo.astype(np.int8),
                                    "idade_ref": idade.astype(np.int16), "dob": dob, "raca": raca.astype(np.int8)}))
    pes = pd.concat(linhas, ignore_index=True)
    pes.insert(0, "pid", np.arange(len(pes), dtype=np.int64))
    pes["residente"] = True
    mundo.pessoas = pes


# ---------------------------------------------------------------- domicílios
def _amostra_ponderada(rng, pesos: np.ndarray, k: int) -> np.ndarray:
    """k índices sem reposição com probabilidade proporcional ao peso (Efraimidis-Spirakis)."""
    chaves = np.log(rng.random(len(pesos))) / np.maximum(pesos, 1e-12)
    return np.argsort(-chaves)[:k]


def gera_domicilios(cfg, mundo) -> None:
    pes = mundo.pessoas
    pop_b = P.bairros_censo()
    kappa = float(cfg.populacao.homofilia_racial)
    pes["dom"] = -1
    pes["ref"] = False
    doms = []
    hid0 = 0
    negro = np.isin(pes["raca"].values, [2, 4])
    for b, grupo in pes.groupby("bairro", sort=True):
        rng = fluxo(cfg.semente, "domicilios", int(b))
        idx = grupo.index.values
        n_h = max(1, int(round(pop_b.loc[b, "dom"] * cfg.escala)))
        idade = grupo["idade_ref"].values
        adultos = np.nonzero(idade >= 18)[0]
        n_h = min(n_h, len(adultos))
        if n_h == 0:
            continue
        w = np.select([idade[adultos] < 25, idade[adultos] < 30, idade[adultos] < 80], [0.25, 0.7, 1.0], 0.9)
        refs = adultos[_amostra_ponderada(rng, w, n_h)]
        hids = hid0 + np.arange(n_h)
        pes.loc[idx[refs], "dom"] = hids
        pes.loc[idx[refs], "ref"] = True
        resto = np.setdiff1d(np.arange(len(idx)), refs)
        # vagas: tamanho extra ~ Poisson(média - 1), ajustado ao total exato
        media = len(idx) / n_h
        extra = rng.poisson(max(media - 1, 0.01), n_h)
        dif = len(resto) - extra.sum()
        if dif > 0:
            np.add.at(extra, rng.integers(0, n_h, dif), 1)
        elif dif < 0:
            for _ in range(-dif):
                pos = np.nonzero(extra > 0)[0]
                extra[pos[rng.integers(0, len(pos))]] -= 1
        g_ref = negro[idx[refs]]
        vagas = {g: rng.permutation(np.repeat(np.nonzero(g_ref == g)[0], extra[g_ref == g])) for g in (True, False)}
        ponteiro = {True: 0, False: 0}
        ordem = rng.permutation(resto)
        quer = np.where(rng.random(len(ordem)) < kappa, negro[idx[ordem]], ~negro[idx[ordem]])
        destino = np.empty(len(ordem), dtype=np.int64)
        for j, g in enumerate(quer):
            g = bool(g)
            if ponteiro[g] >= len(vagas[g]):
                g = not g
            destino[j] = vagas[g][ponteiro[g]]
            ponteiro[g] += 1
        pes.loc[idx[ordem], "dom"] = hids[destino]
        tam = 1 + extra
        doms.append(pd.DataFrame({"hid": hids, "bairro": b, "ds": int(grupo["ds"].iloc[0]),
                                  "ref_pid": pes.loc[idx[refs], "pid"].values, "n_mor": tam, "tipo_imovel": 1}))
        hid0 += n_h
    dom = pd.concat(doms, ignore_index=True)
    # imóveis não residenciais (FCDT sem família; VC08)
    rng = fluxo(cfg.semente, "nao_residencial")
    n_nr = int(round(len(dom) * float(cfg.populacao.nao_residencial)))
    base = dom.iloc[rng.integers(0, len(dom), n_nr)]
    tipos = rng.choice([2, 3, 4, 5, 6, 12, 99], size=n_nr, p=[0.55, 0.12, 0.08, 0.08, 0.05, 0.07, 0.05])
    nr = pd.DataFrame({"hid": hid0 + np.arange(n_nr), "bairro": base["bairro"].values, "ds": base["ds"].values,
                       "ref_pid": -1, "n_mor": 0, "tipo_imovel": tipos})
    mundo.domicilios = pd.concat([dom, nr], ignore_index=True)
    _setores(cfg, mundo)


def _setores(cfg, mundo) -> None:
    """Setores censitários sintéticos (pendência E6): código 2611606 + bairro(3) + nº(5)."""
    dom = mundo.domicilios
    pop_b = P.bairros_censo()
    dom["setor"] = ""
    setores = []
    for b, g in dom.groupby("bairro"):
        rng = fluxo(cfg.semente, "setores", int(b))
        k = max(1, int(np.ceil(pop_b.loc[b, "pop"] / cfg.populacao.pessoas_por_setor)))
        cods = np.array([f"2611606{int(b):03d}{i + 1:05d}" for i in range(k)], dtype=object)
        dom.loc[g.index, "setor"] = cods[rng.integers(0, k, len(g))]
        setores.append(pd.DataFrame({"cd_setor": cods, "id_bairro": int(b)}))
    mundo.setores = pd.concat(setores, ignore_index=True)


# ---------------------------------------------------------------- renda, instrução, trabalho
_ESC_NIVEL = {
    1: ([65, 64, 54, 55, 58], [0.08, 0.05, 0.35, 0.45, 0.07]),
    2: ([56, 59, 60], [0.60, 0.10, 0.30]),
    3: ([60, 62, 63], [0.70, 0.10, 0.20]),
    4: ([63], [1.0]),
}
_ESC_IDOSO_N1 = ([65, 64, 54, 55, 58], [0.30, 0.10, 0.40, 0.15, 0.05])


def escolaridade_crianca(idade: np.ndarray, u: np.ndarray) -> np.ndarray:
    """Curso que frequenta (regra por idade; u ~ U(0,1) estável por pessoa)."""
    return np.select(
        [idade < 2, idade < 4, idade < 6, idade < 7, idade < 11, idade < 15, idade < 18],
        [np.full_like(idade, 65), np.where(u < 0.5, 51, 65), np.full_like(idade, 52), np.full_like(idade, 53),
         np.full_like(idade, 54), np.full_like(idade, 55), np.where(u < 0.75, 60, 56)], -1).astype(np.int16)


def faixa_instr(idade: np.ndarray) -> np.ndarray:
    lim = [20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80]
    return np.searchsorted(lim, idade, side="right")


def gera_socioeconomico(cfg, mundo) -> None:
    pes, dom = mundo.pessoas, mundo.domicilios
    rng = fluxo(cfg.semente, "socioeconomico")
    res = dom[dom["tipo_imovel"] == 1].set_index("hid")
    z1 = rng.standard_normal(len(res))
    res = res.assign(z1=z1)
    # renda per capita condicional à pessoa de referência (sexo, raça), quantil pelo latente z1
    rp = pes.set_index("pid").loc[res["ref_pid"].values]
    tab = P.renda()
    cdf = np.cumsum(tab / tab.sum(axis=2, keepdims=True), axis=2)
    ir = np.searchsorted(P.RACAS, rp["raca"].values)
    u = stats.norm.cdf(z1)
    cat = np.array([np.searchsorted(cdf[s, r], uu) for s, r, uu in zip(rp["sexo"].values, ir, u)])
    cat = np.minimum(cat, len(P.RENDA_CAT) - 1)
    lim = np.array(P.RENDA_LIM)
    renda_pc = lim[cat, 0] + rng.random(len(cat)) * (lim[cat, 1] - lim[cat, 0])
    total = renda_pc * res["n_mor"].values
    cod = np.select([total == 0, total <= 0.25, total <= 0.5, total <= 1, total <= 2, total <= 3, total <= 4],
                    [8, 1, 2, 3, 4, 7, 5], 6)
    res = res.assign(renda_pc=renda_pc, renda_cod=cod)
    dom.loc[dom["tipo_imovel"] == 1, "z1"] = z1
    dom.loc[dom["tipo_imovel"] == 1, "renda_pc"] = renda_pc
    dom.loc[dom["tipo_imovel"] == 1, "renda_cod"] = cod
    # instrução dos adultos: tabela 10061 condicional (faixa, sexo, raça), latente correlacionado com z1
    rho = float(cfg.populacao.rho_escolaridade_renda)
    z1_p = res["z1"].reindex(pes["dom"].values).fillna(0).values
    z = rho * z1_p + np.sqrt(1 - rho ** 2) * rng.standard_normal(len(pes))
    ins = P.instrucao()
    cdf_i = np.cumsum(ins / np.maximum(ins.sum(axis=0, keepdims=True), 1), axis=0)
    adultos = pes["idade_ref"].values >= 18
    f = faixa_instr(pes["idade_ref"].values)
    irp = np.searchsorted(P.RACAS, pes["raca"].values)
    uu = stats.norm.cdf(z)
    nivel = np.zeros(len(pes), dtype=np.int8)
    a_idx = np.nonzero(adultos)[0]
    c = cdf_i[:, f[a_idx], pes["sexo"].values[a_idx], irp[a_idx]]          # [4, n]
    nivel[a_idx] = 1 + (uu[a_idx][None, :] > c).sum(axis=0).clip(0, 3)
    pes["instr_nivel"] = nivel
    esc = np.full(len(pes), -1, dtype=np.int16)
    for nv, (cods, pr) in _ESC_NIVEL.items():
        m = nivel == nv
        if nv == 1:
            idoso = m & (pes["idade_ref"].values >= 60)
            esc[idoso] = rng.choice(_ESC_IDOSO_N1[0], idoso.sum(), p=_ESC_IDOSO_N1[1])
            m = m & ~idoso
        esc[m] = rng.choice(cods, m.sum(), p=pr)
    pes["esc_adulto"] = esc
    pes["u_esc"] = rng.random(len(pes))
    # situação no mercado de trabalho [P]
    idade = pes["idade_ref"].values
    trab = np.full(len(pes), -1, dtype=np.int16)
    m = (idade >= 14) & (idade < 18)
    trab[m] = rng.choice([73, 68, 70], m.sum(), p=[0.85, 0.10, 0.05])
    cods = [67, 68, 69, 70, 147, 66, 72, 73, 71, 74]
    base = np.array([0.30, 0.11, 0.04, 0.16, 0.06, 0.02, 0.09, 0.17, 0.03, 0.02])
    alto = np.array([0.40, 0.06, 0.06, 0.08, 0.14, 0.05, 0.06, 0.10, 0.03, 0.02])
    baixo = np.array([0.20, 0.14, 0.02, 0.22, 0.02, 0.01, 0.12, 0.22, 0.03, 0.02])
    for pr, cond in ((alto, nivel == 4), (baixo, nivel == 1), (base, (nivel == 2) | (nivel == 3))):
        mm = (idade >= 18) & (idade < 65) & cond
        trab[mm] = rng.choice(cods, mm.sum(), p=pr / pr.sum())
    m = idade >= 65
    trab[m] = rng.choice([71, 73, 70, 67, 74], m.sum(), p=[0.72, 0.15, 0.06, 0.03, 0.04])
    pes["trabalho"] = trab
