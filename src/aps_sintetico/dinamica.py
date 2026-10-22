"""Passo 6 – dinâmica mensal (2023-01 a data de corte) e versões da FCI.

* Óbitos: risco mensal por faixa etária × raça (negra / não negra) = óbitos do boletim
  SESAU 01/2025 ÷ população do Censo 2022; registro do óbito com prob. ``prob_registro_obito``.
* Nascimentos: por DS × raça da mãe (boletim, Tabela 3), mães de 15–49 anos ponderadas por
  um perfil de fecundidade [P]; o recém-nascido entra no domicílio da mãe.
* Mudanças: processo de Poisson por domicílio (``mobilidade_anual``); a família vai para um
  novo domicílio em outro bairro dos DS gerados, onde pode ser cadastrada de novo; a saída
  é registrada na equipe de origem com prob. ``prob_registro_mudanca``.
* Atualizações: processo de renovação por domicílio (visita do ACS), intervalo exponencial
  com média ``meses_entre_atualizacoes`` × ritmo da equipe.
* Componente temporal da equipe c_e(t) = tendência + AR(1) + efeito das oficinas.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import special

from . import parametros as P
from . import registro as REG
from .populacao import escolaridade_crianca
from .rng import fluxo

DIA = np.timedelta64(1, "D")
_ASFR = {15: 0.05, 20: 0.09, 25: 0.09, 30: 0.08, 35: 0.05, 40: 0.015, 45: 0.003}   # [P] forma
TEMA_ACAO = "Orientação sexual e identidade de gênero no cadastro individual"


def _d(x) -> np.ndarray:
    return np.asarray(pd.to_datetime(x).values.astype("datetime64[D]"))


def _idade(dob: np.ndarray, data: np.ndarray) -> np.ndarray:
    return ((data - dob).astype("timedelta64[D]").astype(np.int64) / 365.25).astype(int)


def meses(cfg) -> pd.DatetimeIndex:
    return pd.date_range(cfg.periodo.inicio, cfg.periodo.data_corte, freq="MS")


def indice_mes(cfg, datas: np.ndarray) -> np.ndarray:
    ini = pd.Timestamp(cfg.periodo.inicio)
    d = pd.DatetimeIndex(datas)
    return ((d.year - ini.year) * 12 + (d.month - ini.month)).values


# ------------------------------------------------------------------ componente temporal e oficinas
def componentes_equipe(cfg, mundo) -> None:
    eq = mundo.equipes
    din, of = cfg.dinamica, cfg.oficinas
    mundo.meses = meses(cfg)
    T, E = len(mundo.meses), len(eq)
    rng = fluxo(cfg.semente, "componente_temporal")
    tend = rng.normal(0, float(din.tendencia_sd), E)
    phi, sd = float(din.ar_phi), float(din.ar_sd)
    ar = np.zeros((E, T))
    ar[:, 0] = rng.normal(0, sd / np.sqrt(1 - phi * phi), E)
    for t in range(1, T):
        ar[:, t] = phi * ar[:, t - 1] + rng.normal(0, sd, E)
    # oficinas (tipo 1) e material formativo (tipo 2): datas escalonadas
    rng = fluxo(cfg.semente, "oficinas")
    terr = np.nonzero(eq["territorial"].values)[0]
    n_of = int(round(float(of.fracao_equipes) * len(terr)))
    t_ini = int(indice_mes(cfg, [pd.Timestamp(of.inicio)])[0])
    if of.alocacao == "focalizada":
        # escolhe as equipes com menor proporção observada antes do início (verdade + ruído):
        # parte do "baixo desempenho" é transitória (AR), o que gera regressão à média
        base = (eq["a_R"] + eq["u_R"] + eq["a_A"] + eq["v_A"]).values + 2 * ar[:, max(t_ini - 1, 0)]
        obs = base[terr] + rng.normal(0, 0.3, len(terr))
        escolhidas = terr[np.argsort(obs)[:n_of]]
    else:
        escolhidas = rng.choice(terr, n_of, replace=False)
    resto = np.setdiff1d(terr, escolhidas)
    material = rng.choice(resto, int(round(float(of.fracao_material) * len(terr))), replace=False)
    ini, fim = pd.Timestamp(of.inicio), pd.Timestamp(of.fim)
    acoes = []
    efeito = np.zeros((E, T))
    gama = float(of.efeito_logito)
    hl = of.meia_vida_meses
    for tipo, grupo, fator in ((1, escolhidas, 1.0), (2, material, float(of.efeito_material))):
        dias = rng.integers(0, (fim - ini).days + 1, len(grupo))
        for e, dd in zip(grupo, dias):
            data = ini + pd.Timedelta(days=int(dd))
            acoes.append((eq.at[e, "ine"], data.normalize(), tipo, TEMA_ACAO))
            t0 = int(indice_mes(cfg, [data])[0]) + 1        # efeito a partir do mês seguinte
            k = np.arange(T) - t0
            dec = np.ones(T) if hl in (None, 0) else 0.5 ** (np.clip(k, 0, None) / float(hl))
            efeito[e] += np.where(k >= 0, gama * fator * dec, 0.0)
    mundo.acoes = pd.DataFrame(acoes, columns=["ine", "dt_acao", "tipo_acao", "tema"]).sort_values(
        ["dt_acao", "ine"]).reset_index(drop=True)
    anos = np.arange(T) / 12.0
    C = tend[:, None] * anos[None, :] + ar + efeito
    mundo.verdade["C"] = C
    comp = pd.DataFrame({"ine": np.repeat(eq["ine"].values, T), "t": np.tile(np.arange(T), E),
                         "tendencia": (tend[:, None] * anos[None, :]).ravel(), "ar1": ar.ravel(),
                         "efeito_acao": efeito.ravel()})
    comp["competencia"] = [int(m.strftime("%Y%m")) for m in mundo.meses[comp["t"].values]]
    mundo.verdade["componentes"] = comp
    eq["tratada"] = np.isin(np.arange(E), escolhidas)
    eq["material"] = np.isin(np.arange(E), material)


def c_tempo(mundo, e_idx: np.ndarray, t: np.ndarray) -> np.ndarray:
    C = mundo.verdade["C"]
    tt = np.clip(t, 0, C.shape[1] - 1)
    return np.where(t >= 0, C[e_idx, tt], 0.0)


# ------------------------------------------------------------------ demografia
def _taxas_obito(cfg) -> tuple[np.ndarray, np.ndarray]:
    """Risco anual por idade simples (0..104) para negra e não negra."""
    pop = P.pop_sexo_idade_raca().sum(axis=0)                  # [101, 5]
    negra = pop[:, [1, 3]].sum(axis=1)
    nao = pop[:, [0, 2, 4]].sum(axis=1)
    ob = P.obitos_idade_raca()
    tx = np.zeros((2, 105))
    for _, r in ob.iterrows():
        a, b = int(r["ini"]), min(int(r["fim"]), 100)
        den = (negra if r["raca"] == "negra" else nao)[a:b + 1].sum()
        tx[0 if r["raca"] == "negra" else 1, a:(105 if b == 100 else b + 1)] = r["obitos"] / den
    # gradiente etário dentro de 60+ (Gompertz, dobra a cada 8 anos), mantendo a taxa média da faixa
    for g, popg in ((0, negra), (1, nao)):
        idades = np.arange(60, 101)
        forma = 2 ** ((idades - 60) / 8)
        w = popg[60:101]
        m = tx[g, 60]
        k = m * w.sum() / (forma * w).sum()
        tx[g, 60:101] = k * forma
        tx[g, 101:] = tx[g, 100]
    return tx, np.array([0.0])


def obitos(cfg, mundo) -> None:
    pes = mundo.pessoas
    tx, _ = _taxas_obito(cfg)
    rng = fluxo(cfg.semente, "obitos")
    dob = _d(pes["dob"])
    vivo = np.ones(len(pes), dtype=bool)
    dt = np.full(len(pes), np.datetime64("NaT"), dtype="datetime64[D]")
    grupo = np.where(np.isin(pes["raca"].values, [2, 4]), 0, 1)
    for m in mundo.meses:
        d0 = np.datetime64(m.date())
        nd = m.days_in_month
        existe = vivo & (dob <= d0 + nd)
        idade = np.clip(_idade(dob, np.full(len(pes), d0)), 0, 104)
        h = 1 - np.exp(-tx[grupo, idade] / 12)
        morre = existe & (rng.random(len(pes)) < h)
        dt[morre] = np.maximum(d0 + rng.integers(0, nd, morre.sum()), dob[morre])
        vivo &= ~morre
    pes["dt_obito"] = dt


def mudancas(cfg, mundo) -> None:
    """No máximo uma mudança por domicílio no período; destino em outro bairro dos DS gerados."""
    dom, pes, eq = mundo.domicilios, mundo.pessoas, mundo.equipes
    rng = fluxo(cfg.semente, "mudancas")
    ini, corte = np.datetime64(cfg.periodo.inicio), np.datetime64(cfg.periodo.data_corte)
    res = dom[(dom["tipo_imovel"] == 1) & (dom["n_mor"] > 0)]
    taxa = float(cfg.dinamica.mobilidade_anual)
    espera = (rng.exponential(365.25 / taxa, len(res))).astype(int)
    dt_m = ini + espera
    move = dt_m <= corte
    dom["dt_mud"] = pd.Series(pd.NaT, index=dom.index, dtype="datetime64[ns]")
    dom.loc[res.index[move], "dt_mud"] = dt_m[move]
    origem = dom.loc[res.index[move]]
    # destino: bairro proporcional à população; equipe do bairro (ou do DS) pela meta
    pop_b = dom[dom["tipo_imovel"] == 1].groupby("bairro")["n_mor"].sum()
    bairros = rng.choice(pop_b.index.values, len(origem), p=(pop_b / pop_b.sum()).values)
    ds_b = mundo.bairros.set_index("id_bairro")["id_ds"]
    terr = eq[eq["territorial"]]
    por_bairro = {b: g for b, g in terr.groupby("id_bairro")}
    por_ds = {d: g for d, g in terr.groupby("id_ds")}
    setores = mundo.setores.groupby("id_bairro")["cd_setor"].apply(np.array).to_dict()
    hid0 = int(dom["hid"].max()) + 1
    ines, micros, cods = [], [], []
    nmic = eq.set_index("ine")["n_microareas"]
    for b in bairros:
        alvo = por_bairro.get(b, por_ds[ds_b[b]])
        w = alvo["meta_escala1"].values
        i = alvo["ine"].values[rng.choice(len(alvo), p=w / w.sum())]
        ines.append(i)
        micros.append(f"{int(rng.integers(1, nmic[i] + 1)):02d}")
        cods.append(rng.choice(setores[b]))
    novos = pd.DataFrame({"hid": hid0 + np.arange(len(origem)), "bairro": bairros, "ds": ds_b.reindex(bairros).values,
                          "ref_pid": origem["ref_pid"].values, "n_mor": origem["n_mor"].values, "tipo_imovel": 1,
                          "setor": cods, "z1": origem["z1"].values, "renda_pc": origem["renda_pc"].values,
                          "renda_cod": origem["renda_cod"].values, "equipe": ines, "microarea": micros,
                          "origem_hid": origem["hid"].values, "dt_chegada": origem["dt_mud"].values})
    # novo cadastro no destino: probabilidade da equipe de destino (intercepto de cobertura)
    al = mundo.verdade["alpha_cobertura"]
    c = cfg.cobertura
    negro = pes.set_index("pid")["raca"].reindex(novos["ref_pid"]).isin([2, 4]).values
    lin = np.array([al.get(i, -30.0) for i in ines]) + float(c.beta_renda_pc) * novos["renda_pc"].fillna(0).values \
        + float(c.beta_negro) * negro
    novos["cadastrado"] = rng.random(len(novos)) < special.expit(lin)
    atraso = rng.exponential(float(c.rampa_meses) * 30.4, len(novos)).astype(int)
    dtc = _d(novos["dt_chegada"]) + atraso
    novos["cadastrado"] &= dtc <= corte
    novos["dt_cadastro"] = pd.to_datetime(np.where(novos["cadastrado"], dtc, np.datetime64("NaT")))
    # registro da saída na equipe de origem
    sai = rng.random(len(origem)) < float(cfg.dinamica.prob_registro_mudanca)
    dts = _d(origem["dt_mud"]) + rng.exponential(float(cfg.dinamica.atraso_saida_meses) * 30.4,
                                                    len(origem)).astype(int)
    dom["saida_registrada"] = False
    dom["dt_saida"] = pd.Series(pd.NaT, index=dom.index, dtype="datetime64[ns]")
    ok = sai & origem["cadastrado"].values & (dts <= corte)
    dom.loc[origem.index[ok], "saida_registrada"] = True
    dom.loc[origem.index[ok], "dt_saida"] = dts[ok]
    dom["origem_hid"] = -1
    dom = pd.concat([dom, novos], ignore_index=True)
    dom["cadastrado"] = dom["cadastrado"].fillna(False).astype(bool)
    dom["saida_registrada"] = dom["saida_registrada"].fillna(False).astype(bool)
    mundo.domicilios = dom
    # pessoas: domicílio de destino
    mapa = dict(zip(novos["origem_hid"], novos["hid"]))
    pes["dom2"] = pes["dom"].map(mapa).fillna(-1).astype(np.int64)
    d = mundo.domicilios.set_index("hid")
    pes["dt_mud"] = pd.to_datetime(d["dt_mud"].reindex(pes["dom"]).values)
    tem2 = pes["dom2"] >= 0
    pes["equipe2"] = None
    pes["microarea2"] = None
    pes.loc[tem2, "equipe2"] = d["equipe"].reindex(pes.loc[tem2, "dom2"]).values
    pes.loc[tem2, "microarea2"] = d["microarea"].reindex(pes.loc[tem2, "dom2"]).values


def nascimentos(cfg, mundo) -> None:
    pes = mundo.pessoas
    rng = fluxo(cfg.semente, "nascimentos")
    nas = P.nascimentos_ds()
    dob = _d(pes["dob"])
    dto = _d(pes["dt_obito"])
    dtm = _d(pes["dt_mud"])
    mulher = (pes["sexo"].values == 1) & (pes["dom"].values >= 0)
    negra = np.isin(pes["raca"].values, [2, 4])
    novos = []
    for m in mundo.meses:
        d0 = np.datetime64(m.date())
        nd = m.days_in_month
        idade = _idade(dob, np.full(len(pes), d0))
        vivo = np.isnat(dto) | (dto > d0 + nd)
        cand = mulher & vivo & (idade >= 15) & (idade <= 49)
        peso = np.zeros(len(pes))
        for a, v in _ASFR.items():
            peso[(idade >= a) & (idade < a + 5)] = v
        for d in cfg.distritos:
            for grupo, col in ((True, "negra"), (False, "nao_negra")):
                lam = nas.loc[d, col] / 12 * cfg.escala
                n = rng.poisson(lam)
                c = np.nonzero(cand & (pes["ds"].values == d) & (negra == grupo))[0]
                if n == 0 or len(c) == 0:
                    continue
                maes = c[rng.choice(len(c), min(n, len(c)), replace=False, p=peso[c] / peso[c].sum())]
                dia = d0 + rng.integers(0, nd, len(maes))
                novos.append(pd.DataFrame({"mae": maes, "dob": dia}))
    nb = pd.concat(novos, ignore_index=True)
    mae = pes.iloc[nb["mae"].values]
    depois = ~np.isnat(dtm[nb["mae"].values]) & (dtm[nb["mae"].values] <= nb["dob"].values)
    pid0 = int(pes["pid"].max()) + 1
    n = len(nb)
    bebe = pd.DataFrame({
        "pid": pid0 + np.arange(n), "bairro": mae["bairro"].values, "ds": mae["ds"].values,
        "sexo": (rng.random(n) >= 0.512).astype(np.int8), "idade_ref": np.zeros(n, np.int16),
        "dob": nb["dob"].values.astype("datetime64[s]"), "raca": mae["raca"].values, "residente": True,
        "dom": mae["dom"].values, "ref": False, "equipe": mae["equipe"].values, "instr_nivel": 0,
        "esc_adulto": -1, "u_esc": rng.random(n), "trabalho": -1, "def_funcional": False, "def_bits": 0,
        "p_def": 0.0, "os_true": -1, "lgb": False, "ig_true": np.where(rng.random(n) >= 0.512, 201, 200),
        "trans_nb": False, "nome_social": False, "recusa": False, "microarea": mae["microarea"].values,
        "cadastrado": False, "dt_reg": pd.NaT, "w_A": rng.normal(0, float(cfg.registro.sigma_pessoa), n),
        "u_def": rng.random(n), "u_ig_extra": rng.random(n), "dom2": mae["dom2"].values,
        "dt_mud": mae["dt_mud"].values, "equipe2": mae["equipe2"].values, "microarea2": mae["microarea2"].values,
        "mae_pid": mae["pid"].values, "nasc_serie": True, "nasceu_apos_mudanca": depois})
    # óbitos dos recém-nascidos (mesmo risco por idade)
    tx, _ = _taxas_obito(cfg)
    g = np.where(np.isin(bebe["raca"].values, [2, 4]), 0, 1)
    db = _d(bebe["dob"])
    dt = np.full(n, np.datetime64("NaT"), dtype="datetime64[D]")
    vivo = np.ones(n, dtype=bool)
    corte = np.datetime64(cfg.periodo.data_corte)
    for k in range(45):
        ini_k = db + int(k * 30.4)
        alvo = vivo & (ini_k <= corte)
        h = 1 - np.exp(-tx[g, min(k // 12, 104)] / 12)
        morre = alvo & (rng.random(n) < h)
        dt[morre] = np.minimum(ini_k[morre] + rng.integers(0, 30, morre.sum()), corte)
        vivo &= ~morre
    bebe["dt_obito"] = dt
    pes["mae_pid"] = -1
    pes["nasc_serie"] = False
    pes["nasceu_apos_mudanca"] = False
    mundo.pessoas = pd.concat([pes, bebe], ignore_index=True)
    mundo.verdade["nascimentos"] = pd.DataFrame({"mae_pid": bebe["mae_pid"].values, "pid": bebe["pid"].values,
                                                 "dob": bebe["dob"].values, "raca_mae": bebe["raca"].values})


def segmentos(cfg, mundo) -> None:
    """Fixa, por pessoa, o período coberto por cada cadastro (equipe de origem e de destino)."""
    pes, dom = mundo.pessoas, mundo.domicilios.set_index("hid")
    rng = fluxo(cfg.semente, "segmentos")
    corte = np.datetime64(cfg.periodo.data_corte)
    dob, dto, dtm = _d(pes["dob"]), _d(pes["dt_obito"]), _d(pes["dt_mud"])
    fim_vida = np.where(np.isnat(dto), corte, np.minimum(dto, corte))
    # recém-nascidos: cadastro após atraso, se o domicílio corrente estiver cadastrado
    nb = pes["nasc_serie"].values
    lag = rng.exponential(float(cfg.dinamica.atraso_cadastro_rn_meses) * 30.4, len(pes)).astype(int)
    dom_cad = dom["cadastrado"].reindex(pes["dom"]).fillna(False).values.astype(bool)
    dom2_cad = dom["cadastrado"].reindex(pes["dom2"]).fillna(False).values.astype(bool)
    dom2_dt = _d(dom["dt_cadastro"].reindex(pes["dom2"]).values)
    dom1_dt = _d(dom["dt_cadastro"].reindex(pes["dom"]).values)
    apos = pes["nasceu_apos_mudanca"].values
    rn1 = nb & ~apos & dom_cad
    dt_rn = np.maximum(dob + lag, np.where(np.isnat(dom1_dt), dob, dom1_dt))
    pes.loc[rn1, "cadastrado"] = True
    pes.loc[rn1, "dt_reg"] = dt_rn[rn1]
    # segmento 1
    dt_reg = _d(pes["dt_reg"])
    fim1 = np.where(np.isnat(dtm), fim_vida, np.minimum(dtm, fim_vida))
    seg1 = pes["cadastrado"].values & ~np.isnat(dt_reg) & (dt_reg <= fim1)
    pes["seg1"] = seg1
    pes["fim1"] = fim1
    # segmento 2: domicílio de destino cadastrado
    jit = rng.integers(0, 31, len(pes))
    ini2 = np.where(np.isnat(dom2_dt), np.datetime64("NaT"), dom2_dt + jit)
    ini2 = np.where(nb & apos, np.maximum(dob + lag, ini2), ini2)
    omite = rng.random(len(pes)) < float(cfg.cobertura.omissao_morador)
    seg2 = (pes["dom2"].values >= 0) & dom2_cad & ~np.isnat(ini2) & (ini2 <= fim_vida) & ~omite
    pes["seg2"] = seg2
    pes["ini2"] = np.where(seg2, ini2, np.datetime64("NaT"))
    pes["fim2"] = fim_vida


# ------------------------------------------------------------------ versões
def _visitas(rng, unidade: np.ndarray, ini: np.ndarray, fim: np.ndarray, media_dias: np.ndarray) -> pd.DataFrame:
    """Datas de visita (renovação exponencial) de cada unidade em (ini, fim]."""
    out_u, out_d = [], []
    atual = ini.copy()
    vivo = np.ones(len(unidade), dtype=bool)
    while vivo.any():
        atual = atual + rng.exponential(media_dias).astype(int) + 1
        vivo &= atual <= fim
        out_u.append(unidade[vivo])
        out_d.append(atual[vivo])
    return pd.DataFrame({"unidade": np.concatenate(out_u), "data": np.concatenate(out_d)})


def gera_versoes(cfg, mundo) -> None:
    pes, dom, eq = mundo.pessoas, mundo.domicilios, mundo.equipes
    rng = fluxo(cfg.semente, "versoes")
    corte = np.datetime64(cfg.periodo.data_corte)
    ritmo = eq.set_index("ine")["ritmo"]
    media = float(cfg.dinamica.meses_entre_atualizacoes) * 30.4
    # unidades de visita: domicílio (segmento 1 e 2) ou a própria pessoa (eCR/eAPP)
    d = dom[dom["cadastrado"] & (dom["tipo_imovel"] == 1)]
    fim_d = np.where(np.isnat(_d(d["dt_mud"])), corte, np.minimum(_d(d["dt_mud"]), corte))
    vis_d = _visitas(rng, d["hid"].values, _d(d["dt_cadastro"]), fim_d,
                     media * ritmo.reindex(d["equipe"]).values)
    esp = pes[pes["seg1"] & (pes["dom"] < 0)]
    vis_e = _visitas(rng, -(esp["pid"].values + 1), _d(esp["dt_reg"]), _d(esp["fim1"]),
                     media * ritmo.reindex(esp["equipe"]).values)
    vis = pd.concat([vis_d, vis_e], ignore_index=True)
    # cadastros iniciais e atualizações por pessoa e segmento
    blocos = []
    for seg in (1, 2):
        m = pes[f"seg{seg}"].values
        p = pes[m]
        ini = _d(p["dt_reg"] if seg == 1 else p["ini2"])
        fim = _d(p["fim1"] if seg == 1 else p["fim2"])
        uni = np.where(p["dom"].values >= 0, p["dom"].values if seg == 1 else p["dom2"].values,
                       -(p["pid"].values + 1))
        base = pd.DataFrame({"pos": np.nonzero(m)[0], "seg": seg, "unidade": uni, "ini": ini, "fim": fim,
                             "ine": (p["equipe"] if seg == 1 else p["equipe2"]).values,
                             "microarea": (p["microarea"] if seg == 1 else p["microarea2"]).values})
        blocos.append(base.assign(data=ini, tipo="inicial"))
        j = base.merge(vis, on="unidade")
        j = j[(j["data"] > j["ini"]) & (j["data"] <= j["fim"])]
        blocos.append(j.assign(tipo="atualizacao"))
    v = pd.concat(blocos, ignore_index=True)[["pos", "seg", "ine", "microarea", "data", "tipo"]]
    # eventos: saída por mudança (segmento 1) e óbito (segmento ativo na data)
    dtm, dto = _d(pes["dt_mud"]), _d(pes["dt_obito"])
    rec = pes["recusa"].values
    sai_dom = dom.set_index("hid")
    sai_ok = sai_dom["saida_registrada"].reindex(pes["dom"]).fillna(False).values.astype(bool)
    dt_sai = _d(sai_dom["dt_saida"].reindex(pes["dom"]).values)
    m_sai = pes["seg1"].values & sai_ok & ~rec & (np.isnat(dto) | (dto > dt_sai)) & (dt_sai <= corte)
    m_sai &= ~np.isnat(dtm) & (_d(pes["dt_reg"]) <= dtm)
    ev_s = pd.DataFrame({"pos": np.nonzero(m_sai)[0], "seg": 1, "ine": pes["equipe"].values[m_sai],
                         "microarea": pes["microarea"].values[m_sai], "data": dt_sai[m_sai], "tipo": "saida"})
    lag = rng.exponential(float(cfg.dinamica.atraso_saida_meses) * 30.4, len(pes)).astype(int)
    reg_ob = rng.random(len(pes)) < float(cfg.dinamica.prob_registro_obito)
    dt_ro = dto + lag
    morreu = ~np.isnat(dto) & reg_ob & ~rec & (dt_ro <= corte)
    em2 = morreu & pes["seg2"].values & (_d(pes["ini2"]) <= dto)
    em1 = morreu & ~em2 & pes["seg1"].values & (np.isnat(dtm) | (dto < dtm)) & (_d(pes["dt_reg"]) <= dto)
    ev_o = pd.concat([
        pd.DataFrame({"pos": np.nonzero(em1)[0], "seg": 1, "ine": pes["equipe"].values[em1],
                      "microarea": pes["microarea"].values[em1], "data": dt_ro[em1], "tipo": "obito"}),
        pd.DataFrame({"pos": np.nonzero(em2)[0], "seg": 2, "ine": pes["equipe2"].values[em2],
                      "microarea": pes["microarea2"].values[em2], "data": dt_ro[em2], "tipo": "obito"})])
    v = pd.concat([v, ev_s, ev_o], ignore_index=True)
    ordem_tipo = v["tipo"].map({"inicial": 0, "atualizacao": 1, "saida": 2, "obito": 3})
    v = v.assign(_o=ordem_tipo).sort_values(["pos", "seg", "data", "_o"]).drop(columns="_o").reset_index(drop=True)
    # eventos encerram a cadeia: descarta visitas posteriores a um evento
    ev = v["tipo"].isin(["saida", "obito"])
    apos_ev = ev.groupby([v["pos"], v["seg"]]).cumsum() - ev
    v = v[apos_ev.values == 0].reset_index(drop=True)
    _preenche(cfg, mundo, v, rng)


def _preenche(cfg, mundo, v: pd.DataFrame, rng) -> None:
    """Campos registrados em cada versão."""
    pes, eq = mundo.pessoas, mundo.equipes
    pos = v["pos"].values
    data = v["data"].values.astype("datetime64[D]")
    dob = _d(pes["dob"])[pos]
    idade = _idade(dob, data)
    e_idx = pd.Index(eq["ine"]).get_indexer(v["ine"].values)
    t = indice_mes(cfg, data)
    ct = c_tempo(mundo, e_idx, t)
    out = REG.desfecho(cfg, mundo, pos, v["ine"].values, idade, ct, rng)
    r = cfg.registro
    rec = pes["recusa"].values[pos]
    v["idade"] = idade
    v["recusa"] = rec
    v["raca"] = np.where(rec, -1, pes["raca"].values[pos])
    for k in ("os", "ig"):
        v[f"deseja_{k}"] = np.where(rec, -1, out[f"deseja_{k}"])
        v[k] = np.where(rec, -1, out[k])
        v[f"R_{k}"] = out[f"R_{k}"]
        v[f"nao_sem_perg_{k}"] = out[f"nao_sem_perg_{k}"] & ~rec
    v["p_sim_os"] = out["p_sim_os"]
    v["crianca"] = out["crianca"]
    # deficiência: registro persistente por pessoa (sensibilidade e falso-positivo)
    tem = pes["def_bits"].values[pos] > 0
    u = pes["u_def"].values[pos]
    reg = np.where(tem, u < float(r.sens_deficiencia), u > 1 - float(r.fp_deficiencia))
    nulo = rng.random(len(v)) < float(r.get("deficiencia_nao_perguntada", 0.02))
    v["tem_def"] = np.where(rec | nulo, -1, reg.astype(np.int8))
    v["def_bits_reg"] = np.where(v["tem_def"].values == 1,
                                 np.where(tem, pes["def_bits"].values[pos], 1 << rng.integers(0, 4, len(v))), 0)
    # escolaridade e trabalho na data da versão
    u_esc = pes["u_esc"].values[pos]
    esc_c = escolaridade_crianca(idade, u_esc)
    esc_a = pes["esc_adulto"].values[pos]
    esc_a = np.where(esc_a < 0, np.where(u_esc < 0.75, 60, 56), esc_a)
    v["escolaridade"] = np.where(rec, -1, np.where(idade < 18, esc_c, esc_a))
    trab = pes["trabalho"].values[pos]
    v["trabalho"] = np.where(rec | (idade < 14), -1, np.where(trab < 0, 73, trab))
    v["motivo"] = np.select([v["tipo"] == "saida", v["tipo"] == "obito"], [136, 135], -1)
    # os eventos repetem os atributos da versão anterior da cadeia
    ev = v["motivo"].values > 0
    cols = ["raca", "deseja_os", "os", "deseja_ig", "ig", "tem_def", "def_bits_reg", "escolaridade", "trabalho"]
    if ev.any():
        ant = v[cols].shift(1)
        mesmo = (v["pos"].shift(1) == v["pos"]) & (v["seg"].shift(1) == v["seg"])
        for c in cols:
            v.loc[ev & mesmo.values, c] = ant.loc[ev & mesmo.values, c].astype(v[c].dtype)
    v["dt_obito"] = np.where(v["motivo"].values == 135, _d(pes["dt_obito"])[pos], np.datetime64("NaT"))
    # digitação: atraso exponencial com média da equipe
    atraso = rng.exponential(eq.set_index("ine")["atraso_medio"].reindex(v["ine"]).values).astype(int)
    v["dt_digitacao"] = data + atraso
    lim = np.datetime64(pd.Timestamp(cfg.periodo.dt_geracao).date())
    v["transmitida"] = v["dt_digitacao"].values < lim
    v["cadeia"] = v.groupby(["pos", "seg"]).ngroup()
    primeira = ~v.duplicated("cadeia")
    # cadeia cuja ficha original ainda não foi transmitida fica fora da base
    cad_ok = v.loc[primeira].set_index("cadeia")["transmitida"]
    v = v[v["transmitida"].values & cad_ok.reindex(v["cadeia"]).values].reset_index(drop=True)
    v["n_versao"] = v.groupby("cadeia").cumcount()
    mundo.versoes = v.drop(columns=["transmitida"])


def verdade_equipe_mes(cfg, mundo) -> None:
    """p verdadeiro (probabilidade de Sim se a versão fosse feita no mês) e prevalências reais
    entre os cadastrados elegíveis vivos de cada equipe em cada competência."""
    pes, eq = mundo.pessoas, mundo.equipes
    linhas = []
    dob = _d(pes["dob"])
    ini1, fim1 = _d(pes["dt_reg"]), _d(pes["fim1"])
    ini2, fim2 = _d(pes["ini2"]), _d(pes["fim2"])
    for t, m in enumerate(mundo.meses):
        d = np.datetime64((m + pd.offsets.MonthEnd(0)).date())
        a1 = pes["seg1"].values & (ini1 <= d) & (fim1 >= d)
        a2 = pes["seg2"].values & (ini2 <= d) & (fim2 >= d)
        ativo = a1 | a2
        idx = np.nonzero(ativo)[0]
        ine = np.where(a2[idx], pes["equipe2"].values[idx], pes["equipe"].values[idx])
        idade = _idade(dob[idx], np.full(len(idx), d))
        el = idade >= int(cfg.regra.idade_min_elegivel)
        idx, ine, idade = idx[el], ine[el], idade[el]
        e_idx = pd.Index(eq["ine"]).get_indexer(ine)
        p_r, p_a, p_ai, _ = REG.probabilidades(cfg, mundo, idx, ine, idade, c_tempo(mundo, e_idx, np.full(len(idx), t)))
        df = pd.DataFrame({"ine": ine, "p_sim_os": p_r * p_a, "p_sim_ig": p_r * p_ai, "p_pergunta": p_r,
                           "lgb": pes["lgb"].values[idx], "trans_nb": pes["trans_nb"].values[idx],
                           "pcd": pes["def_bits"].values[idx] > 0, "negro": np.isin(pes["raca"].values[idx], [2, 4])})
        g = df.groupby("ine").agg(n_elegiveis=("p_sim_os", "size"), p_sim_os=("p_sim_os", "mean"),
                                  p_sim_ig=("p_sim_ig", "mean"), p_pergunta=("p_pergunta", "mean"),
                                  prev_lgb=("lgb", "mean"), prev_trans_nb=("trans_nb", "mean"),
                                  prev_pcd=("pcd", "mean"), prop_negro=("negro", "mean")).reset_index()
        g["competencia"] = int(m.strftime("%Y%m"))
        linhas.append(g)
    mundo.verdade["equipe_mes"] = pd.concat(linhas, ignore_index=True)


def defeitos_comportamento(cfg, mundo) -> None:
    """Defeitos de comportamento (Etapa 6) que entram no gabarito: 5, 6, 10, 11, 12 e 13."""
    v = mundo.versoes
    lim = int(cfg.defeitos.atraso_limite_dias)
    # id provisório: posição da versão; o exportador troca pelo uuid
    # 6: campo "Deseja informar" preenchido (Sim ou Não) para criança abaixo da idade mínima (RQ02)
    for i in np.nonzero(v["crianca"].values & ((v["deseja_os"].values >= 0) | (v["deseja_ig"].values >= 0)))[0]:
        mundo.defeito("cadastro_individual", i, 6, 6, "deseja_informar_os" if v.at[i, "deseja_os"] >= 0
                      else "deseja_informar_ig")
    el = ~v["crianca"].values & ~v["recusa"].values & (v["motivo"].values < 0)
    for k, campo in (("os", "deseja_informar_os"), ("ig", "deseja_informar_ig")):
        for i in np.nonzero(el & (v[f"deseja_{k}"].values == -1))[0]:
            mundo.defeito("cadastro_individual", i, 11, 6, campo)
        for i in np.nonzero(el & v[f"nao_sem_perg_{k}"].values)[0]:
            mundo.defeito("cadastro_individual", i, 12, 6, campo, original="pergunta não feita")
    for i in np.nonzero((v["tem_def"].values == -1) & ~v["recusa"].values)[0]:
        mundo.defeito("cadastro_individual", i, 13, 6, "tem_deficiencia", original="pergunta não feita")
    atraso = (v["dt_digitacao"].values.astype("datetime64[D]") - v["data"].values.astype("datetime64[D]")).astype(int)
    for i in np.nonzero(atraso > lim)[0]:
        mundo.defeito("cadastro_individual", i, 10, 6, "dt_digitacao", original=str(int(atraso[i])))
    # 5: versão vigente que não reflete óbito ou mudança não registrados
    pes = mundo.pessoas
    corte = np.datetime64(cfg.periodo.data_corte)
    ult = v.sort_values(["pos", "data", "dt_digitacao"]).drop_duplicates("pos", keep="last")
    p = pes.iloc[ult["pos"].values]
    morto = ~np.isnat(_d(p["dt_obito"])) & (_d(p["dt_obito"]) <= corte)
    mudou = ~np.isnat(_d(p["dt_mud"])) & (_d(p["dt_mud"]) <= corte) & (ult["seg"].values == 1)
    stale = (morto | mudou) & (ult["motivo"].values < 0)
    for i, mo in zip(ult.index[stale], morto[stale]):
        mundo.defeito("cadastro_individual", i, 5, 6, "motivo_saida", original="óbito" if mo else "mudança")
