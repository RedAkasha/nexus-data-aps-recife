"""Painel Nexus Data · APS Recife – segue o mockup "Visão Geral - Recife" do grupo.

Páginas: Visão Geral, Ad. Preenchimento (adequação do preenchimento) e Prevenção IA.
Lê as tabelas analíticas em Parquet (python -m aps_sintetico analitica) de uma saída do gerador,
sem precisar do banco. Executar:
    streamlit run painel/app.py -- --saida saida/base
Mapa: salve o GeoJSON de bairros da Prefeitura em painel/assets/ (ver painel/LEIAME.md). Sem o
arquivo, o painel mostra barras por distrito no lugar do mapa.
Os dados são SINTÉTICOS; nenhuma linha corresponde a pessoa real.

Definições (as mesmas de src/aps_sintetico/analitica.py e da planilha da SESAU):
  * cadastrados = cidadãos ativos na competência (soma de raça/cor, que todo cadastro tem);
  * "Sim" em orientação sexual = pessoa aceitou informar; denominador = elegíveis (idade ≥ mínima) =
    "dado real" = Sim + Não + Não informado;
  * completude = 1 − (sem registro ÷ denominador do campo). OS e IG só entre elegíveis.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from aps_sintetico import parametros as P  # noqa: E402
import geo  # noqa: E402

LIMIAR_ALERTA = 0.15          # "Sim" abaixo de 15% = equipe em alerta
# Paleta categórica validada (dataviz), uma cor fixa por DS: a cor segue o distrito, nunca o ranking
COR_DS = {1: "#2a78d6", 2: "#eb6834", 3: "#1baf7a", 4: "#eda100", 5: "#e87ba4", 6: "#008300",
          7: "#6250d6", 8: "#e34948"}
NOMES_DS = {i: f"DS {i}" for i in range(1, 9)}
ESCALA_DS = alt.Scale(domain=list(NOMES_DS.values()), range=list(COR_DS.values()))
INK, INK2, MUDO, SEM_DADO = "#0b0b0b", "#52514e", "#898781", "#d9d8d4"
# campo -> (categorias do denominador | None = todas, categorias "sem registro", só elegíveis?)
CAMPOS = {"OS": ("Orientação sexual", ["SIM", "NAO", "NAO_INFORMADO"], ["NAO_INFORMADO"], True),
          "IG": ("Identidade de gênero", ["SIM", "NAO", "NAO_INFORMADO"], ["NAO_INFORMADO"], True),
          "RACA_COR": ("Raça/cor", None, ["VAZIO"], False),
          "DEFICIENCIA": ("Deficiência", ["SIM", "NAO", "SEM_REGISTRO"], ["SEM_REGISTRO"], False)}


ORDEM_CAMPOS = [v[0] for v in CAMPOS.values()]


# ----------------------------------------------------------------------------- dados
def _args() -> Path:
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", default=str(RAIZ / "saida" / "base"))
    a, _ = ap.parse_known_args(sys.argv[1:])
    return Path(a.saida)


def _den(f: pd.DataFrame, marcador: str) -> pd.DataFrame:
    """Linhas do denominador de um campo (sem as linhas de detalhe por código, que repetem a contagem)."""
    _, cats, _, so_el = CAMPOS[marcador]
    x = f[f["marcador"] == marcador]
    if cats is not None:
        x = x[x["categoria"].isin(cats)]
    return x[x["elegivel"]] if so_el else x


def completude(f: pd.DataFrame, por: list[str]) -> pd.DataFrame:
    """Completude por campo (e por `por`): Registros = denominador; Sem registro = categorias vazias."""
    partes = []
    for m, (nome, _, vazias, _) in CAMPOS.items():
        x = _den(f, m)
        x = x.assign(vazio=x["categoria"].isin(vazias))
        g = x.groupby(por + ["vazio"])["n"].sum().unstack("vazio", fill_value=0) if por else \
            x.groupby("vazio")["n"].sum().to_frame().T
        g = g.reindex(columns=[False, True], fill_value=0)
        g.columns = ["ok", "sem"]
        g = g.reset_index() if por else g.reset_index(drop=True)
        g["Campo"], g["Registros"] = nome, g["ok"] + g["sem"]
        g["Completude"] = g["ok"] / g["Registros"].where(g["Registros"] > 0)
        partes.append(g.drop(columns="ok").rename(columns={"sem": "Sem registro"}))
    return pd.concat(partes, ignore_index=True)


@st.cache_data(show_spinner="Lendo tabelas analíticas…")
def carrega(saida: str) -> dict:
    s = Path(saida)
    a = s / "analitica"
    out = {k: pd.read_parquet(a / f"{k}.parquet") for k in
           ("dim_competencia", "fato_indicador_equipe", "fato_atendimento_equipe", "fato_painel_ml",
            "monitoramento_equipe")}
    est = P.estrutura()
    uni = est["unidade"]
    out["unidade"] = uni[["cnes", "nome_unidade"]] if "nome_unidade" in uni else \
        uni[["cnes"]].assign(nome_unidade=uni["cnes"])
    out["equipe"] = est["equipe"][["ine", "nome_equipe", "cnes", "tipo_equipe"]]
    out["manifesto"] = json.loads((s / "manifesto.json").read_text(encoding="utf-8"))
    q = s / "relatorios" / "qualidade_vs_gabarito.csv"
    out["qualidade"] = pd.read_csv(q) if q.exists() else None
    p = s / "ml" / "predicoes.parquet"
    out["predicoes"] = pd.read_parquet(p) if p.exists() else None
    out["comps"] = sorted(out["dim_competencia"]["competencia"].tolist())
    f = out["fato_indicador_equipe"]
    # cadastros ativos por competência (e por DS)
    rc = f[f["marcador"] == "RACA_COR"]
    out["cad"] = rc.groupby("competencia")["n"].sum()
    out["cad_ds"] = rc.groupby(["competencia", "id_ds"])["n"].sum()
    # "Sim" e "não informado" em orientação sexual, entre elegíveis, por competência × DS
    o = f[(f["marcador"] == "OS") & f["elegivel"] & f["categoria"].isin(["SIM", "NAO", "NAO_INFORMADO"])]
    t = o.pivot_table(index=["competencia", "id_ds"], columns="categoria", values="n", aggfunc="sum").fillna(0)
    den = t.sum(axis=1)
    t = pd.DataFrame({"prop_sim": t["SIM"] / den, "prop_ni": t["NAO_INFORMADO"] / den}).reset_index()
    t["DS"] = t["id_ds"].map(NOMES_DS)
    out["serie_ds"] = t
    g = o.groupby(["competencia", "categoria"])["n"].sum().unstack(fill_value=0)
    out["sim_geral"] = g["SIM"] / g.sum(axis=1)
    # completude por competência (município) para o gráfico de evolução
    out["compl_serie"] = pd.concat(
        [completude(f[f["competencia"] == c], []).assign(competencia=c) for c in out["comps"][-24:]],
        ignore_index=True)
    return out


@st.cache_data(show_spinner="Montando o mapa…")
def carrega_geo(caminho: str, mtime: float) -> dict:
    return geo.carregar(caminho)


# ----------------------------------------------------------------------------- formatação
def _mes(c) -> str:
    return f"{str(c)[4:]}/{str(c)[:4]}"


def _periodo(p) -> str:
    return f"{str(p)[4:]}º quadrimestre de {str(p)[:4]}"


def _pct(x, casas=1) -> str:
    return "–" if pd.isna(x) else f"{x * 100:.{casas}f}%".replace(".", ",")


def _int(x) -> str:
    return f"{int(x):,}".replace(",", ".")


def _delta(x, rel=False) -> str:
    """rel: variação relativa (%); senão, diferença em pontos percentuais."""
    return f"{abs(x) * 100:.1f}%".replace(".", ",") if rel else f"{abs(x) * 100:.1f} p.p.".replace(".", ",")


def cartao(col, titulo, valor, delta, bom_se_sobe: bool | None, nota="", rel=False):
    seta, cor = "", MUDO
    if delta is not None and not pd.isna(delta) and round(delta * 100, 1) != 0:
        seta = "▲" if delta > 0 else "▼"
        cor = INK2 if bom_se_sobe is None else ("#006300" if (delta > 0) == bom_se_sobe else "#d03b3b")
    d = f"<span style='color:{cor};font-weight:600'>{seta} {_delta(delta, rel)}</span>" if seta else ""
    col.markdown(
        f"<div style='border:1px solid #d9d8d4;border-radius:10px;padding:14px 16px;height:100%'>"
        f"<div style='color:{INK2};font-size:0.9rem'>{titulo}</div>"
        f"<div style='font-size:2rem;font-weight:700;line-height:1.2'>{valor} "
        f"<span style='font-size:0.95rem'>{d}</span></div>"
        f"<div style='color:{MUDO};font-size:0.8rem'>{nota}</div></div>", unsafe_allow_html=True)


# ----------------------------------------------------------------------------- necessidade por DS (bolas)
# Códigos do e-SUS (dados/dominios.json): raça/cor 2 = preta, 4 = parda; orientação 148 = heterossexual;
# identidade 200/201 = homem/mulher cisgênero.
BOLAS = {"Nenhuma": None,
         "População negra (preta + parda)": "negra",
         "Pessoas com deficiência": "deficiencia",
         "Orientação sexual não heterossexual": "os",
         "Identidade de gênero não cisgênero": "ig",
         "Sem registro de orientação sexual": "ni_os"}
COD_OS = ["148", "154", "155", "196", "197", "198", "199"]
COD_IG = ["149", "150", "151", "156", "200", "201", "203"]


def necessidade(f: pd.DataFrame, chave: str) -> pd.DataFrame:
    """Por DS: quantidade, denominador e % do indicador escolhido (f = uma competência)."""
    def soma(x):
        return x.groupby("id_ds")["n"].sum()
    if chave == "negra":
        x = f[f["marcador"] == "RACA_COR"]
        qtd, den = soma(x[x["categoria"].isin(["2", "4"])]), soma(x)
    elif chave == "deficiencia":
        x = f[(f["marcador"] == "DEFICIENCIA") & f["categoria"].isin(["SIM", "NAO", "SEM_REGISTRO"])]
        qtd, den = soma(x[x["categoria"] == "SIM"]), soma(x)
    elif chave == "os":
        x = f[(f["marcador"] == "OS") & f["categoria"].isin(COD_OS)]
        qtd, den = soma(x[x["categoria"] != "148"]), soma(x)
    elif chave == "ig":
        x = f[(f["marcador"] == "IG") & f["categoria"].isin(COD_IG)]
        qtd, den = soma(x[~x["categoria"].isin(["200", "201"])]), soma(x)
    else:
        x = _den(f, "OS")
        qtd, den = soma(x[x["categoria"] == "NAO_INFORMADO"]), soma(x)
    d = pd.DataFrame({"qtd": qtd, "den": den}).fillna(0).reset_index()
    d["pct"] = d["qtd"] / d["den"].where(d["den"] > 0)
    d["DS"] = d["id_ds"].map(NOMES_DS)
    return d


# ----------------------------------------------------------------------------- mapa
def mapa(G: dict | None, tot: pd.DataFrame, modo: str, bolas: pd.DataFrame | None = None, medida: str = "Quantidade"):
    """Bairros do Recife coloridos por DS ou pelo indicador do DS. Sem a malha, barras por DS."""
    v = tot.set_index("id_ds")
    col = {"Distrito Sanitário": None, "% de \"Sim\" (orientação sexual)": "prop_sim",
           "% não informado (orientação sexual)": "prop_ni"}[modo]
    if G is None:
        d = tot.assign(DS=tot["id_ds"].map(NOMES_DS))
        if col is None:
            col = "prop_sim"
        return alt.Chart(d).mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, size=22).encode(
            y=alt.Y("DS:N", sort=list(NOMES_DS.values()), title=None),
            x=alt.X(f"{col}:Q", title=modo if modo != "Distrito Sanitário" else "% de \"Sim\"",
                    axis=alt.Axis(format="%")),
            color=alt.Color("DS:N", scale=ESCALA_DS, legend=None),
            tooltip=[alt.Tooltip("DS:N", title="Distrito"), alt.Tooltip(f"{col}:Q", format=".1%")]
        ).properties(height=430)
    feats = []
    for f in G["bairros"]:
        p = dict(f["properties"])
        d = p["id_ds"]
        p["valor"] = None if (col is None or d not in v.index) else float(v.loc[d, col])
        p["cor"] = "#ecebe6" if (bolas is not None and col is None) else COR_DS.get(d, SEM_DADO)   # base neutra deixa as bolas em destaque
        feats.append({**f, "properties": p})
    tip = [alt.Tooltip("properties.bairro:N", title="Bairro"), alt.Tooltip("properties.DS:N", title="Distrito")]
    if col is None:
        cor = alt.Color("properties.cor:N", scale=None)
    else:
        lo, hi = float(v[col].min()), float(v[col].max())
        cor = alt.condition("isValid(datum.properties.valor)",
                            alt.Color("properties.valor:Q", title=modo, scale=alt.Scale(
                                scheme="blues", domain=[lo, hi if hi > lo else lo + 1e-6]),
                                legend=alt.Legend(format=".0%", orient="bottom", titleLimit=320, gradientLength=220)),
                            alt.value(SEM_DADO))
        tip.append(alt.Tooltip("properties.valor:Q", title=modo, format=".1%"))
    bairros = alt.Chart(alt.Data(values=feats)).mark_geoshape(stroke="white", strokeWidth=0.6).encode(
        color=cor, tooltip=tip)
    contorno = alt.Chart(alt.Data(values=G["ds"])).mark_geoshape(filled=False, stroke=INK, strokeWidth=1.4)
    rot = alt.Chart(alt.Data(values=G["rotulos"])).encode(longitude="lon:Q", latitude="lat:Q", text="DS:N")
    halo = rot.mark_text(fontSize=12, fontWeight="bold", color="white", stroke="white", strokeWidth=4)
    texto = rot.mark_text(fontSize=12, fontWeight="bold", color=INK)
    camadas = [bairros, contorno]
    if bolas is not None:
        col_b = "qtd" if medida == "Quantidade" else "pct"
        pts = pd.DataFrame(G["rotulos"]).merge(bolas, on="id_ds")
        pts["valor"] = pts[col_b].fillna(0)
        top = float(pts["valor"].max()) or 1.0
        bol = alt.Chart(pts).mark_circle(color="#d03b3b", opacity=0.72, stroke="#7a1d1d", strokeWidth=1.2).encode(
            longitude="lon:Q", latitude="lat:Q",
            size=alt.Size("valor:Q", scale=alt.Scale(domain=[0, top], range=[0, 7000]), legend=None),
            tooltip=[alt.Tooltip("DS:N", title="Distrito"), alt.Tooltip("qtd:Q", title="Quantidade", format=",.0f"),
                     alt.Tooltip("pct:Q", title="% do distrito", format=".1%")])
        camadas.append(bol)
    camadas += [halo, texto]
    return alt.layer(*camadas).project(type="mercator").properties(height=470)


def legenda_ds(tot: pd.DataFrame, n_eq: pd.Series, modo: str, extra: dict | None = None):
    col = {"% de \"Sim\" (orientação sexual)": "prop_sim", "% não informado (orientação sexual)": "prop_ni"}.get(modo)
    v = tot.set_index("id_ds")
    linhas = ["<div style='font-size:0.85rem;line-height:1.35;white-space:nowrap'><b>Distritos</b>"]
    for d in range(1, 9):
        val = f"<b style='float:right;margin-left:10px'>{_pct(v.loc[d, col])}</b>" if col and d in v.index else ""
        if extra is not None:
            val = f"<b style='float:right;margin-left:10px;color:#d03b3b'>{extra.get(d, '–')}</b>"
        linhas.append(f"<div style='margin-top:7px'><span style='display:inline-block;width:11px;height:11px;"
                      f"border-radius:50%;background:{COR_DS[d]};margin-right:6px'></span>DS {d}{val}<br>"
                      f"<span style='margin-left:17px;font-size:0.76rem;color:{MUDO}'>{int(n_eq.get(d, 0))} equipes</span></div>")
    linhas.append("</div>")
    st.markdown("".join(linhas), unsafe_allow_html=True)


# ----------------------------------------------------------------------------- gráficos
def tendencia(s: pd.DataFrame, meses: int, comps: list):
    d = s[s["competencia"].isin(comps[-meses:])].copy()
    d["data"] = pd.to_datetime(d["competencia"].astype(str), format="%Y%m")
    sel = alt.selection_point(fields=["DS"], bind="legend")
    base = alt.Chart(d).encode(
        x=alt.X("data:T", title=None, axis=alt.Axis(format="%m/%Y", labelColor=MUDO)),
        y=alt.Y("prop_sim:Q", title="% de \"Sim\" (orientação sexual)", axis=alt.Axis(format="%"),
                scale=alt.Scale(zero=False)),
        color=alt.Color("DS:N", scale=ESCALA_DS, legend=alt.Legend(title=None, orient="right")),
        opacity=alt.condition(sel, alt.value(1), alt.value(0.15)))
    pts = base.mark_circle(size=60, stroke="white", strokeWidth=2).encode(
        tooltip=[alt.Tooltip("data:T", format="%m/%Y", title="competência"), "DS:N",
                 alt.Tooltip("prop_sim:Q", format=".1%", title="Sim")])
    return (base.mark_line(strokeWidth=2) + pts).add_params(sel).properties(height=280)


def alertas(D: dict) -> pd.DataFrame:
    """Equipes com "Sim" observado abaixo do limiar, por período (id_ds, periodo, n_alerta, n_equipes)."""
    p = D["fato_painel_ml"]
    p = p[p["n_dado_real"] > 0].assign(alerta=lambda x: x["prop_sim_os"] < LIMIAR_ALERTA)
    return p.groupby(["periodo", "id_ds"]).agg(n_alerta=("alerta", "sum"), n_equipes=("alerta", "size")).reset_index()


def ranking_ds(D: dict, comp, comp_ant) -> pd.DataFrame:
    s = D["serie_ds"]
    a = s[s["competencia"] == comp].set_index("id_ds")
    b = s[s["competencia"] == comp_ant].set_index("id_ds").reindex(a.index)
    r = pd.DataFrame({"Distrito": a.index.map(NOMES_DS), "% Sim (OS)": a["prop_sim"].values,
                      "% Não informado": a["prop_ni"].values,
                      "Δ 6m (p.p.)": ((a["prop_sim"] - b["prop_sim"]) * 100).values}, index=a.index)
    al = alertas(D)
    al = al[al["periodo"] == al["periodo"].max()].set_index("id_ds")
    r["Equipes <15%"] = al["n_alerta"].reindex(r.index).fillna(0).astype(int)
    return r.sort_values("% Sim (OS)").reset_index(drop=True)


# ----------------------------------------------------------------------------- páginas
def visao_geral(D: dict):
    st.markdown("# Visão Geral - Recife")
    comps = D["comps"]
    comp = comps[-1]
    ant = comps[-13] if len(comps) > 12 else comps[0]
    cad, sim = D["cad"], D["sim_geral"]
    al = alertas(D).groupby("periodo")[["n_alerta", "n_equipes"]].sum()
    al["pct"] = al["n_alerta"] / al["n_equipes"]
    per = al.index.max()
    per_ant = al.index[-2] if len(al) > 1 else per
    c1, c2, c3 = st.columns(3)
    cartao(c1, "Pacientes cadastrados (ativos)", _int(cad[comp]),
           (cad[comp] - cad[ant]) / cad[ant] if cad[ant] else None, True, f"vs. {_mes(ant)}", rel=True)
    cartao(c2, "Orientação sexual: \"Sim\" no dado real", _pct(sim[comp]), sim[comp] - sim[ant], True,
           f"vs. {_mes(ant)} · só pessoas elegíveis")
    cartao(c3, "Equipes com \"Sim\" abaixo de 15%", _pct(al.loc[per, "pct"]), al.loc[per, "pct"] - al.loc[per_ant, "pct"],
           False, f"{int(al.loc[per, 'n_alerta'])} de {int(al.loc[per, 'n_equipes'])} equipes · {_periodo(per)}")
    st.write("")
    esq, dir_ = st.columns([1, 1.05], gap="large")
    tot = D["serie_ds"][D["serie_ds"]["competencia"] == comp]
    n_eq = D["monitoramento_equipe"].groupby("id_ds")["ine"].nunique()
    with esq:
        st.markdown("##### Mapa por Distrito Sanitário")
        c_a, c_b, c_c = st.columns([1.3, 1.5, 1])
        modo = c_a.selectbox("Colorir por", ["Distrito Sanitário", "% de \"Sim\" (orientação sexual)",
                                             "% não informado (orientação sexual)"])
        nome_b = c_b.selectbox("Bolas vermelhas: onde há mais", list(BOLAS))
        medida = c_c.selectbox("Medida", ["Quantidade", "% do distrito"])
        bolas, extra = None, None
        if BOLAS[nome_b]:
            fl = D["fato_indicador_equipe"]
            bolas = necessidade(fl[fl["competencia"] == comp], BOLAS[nome_b])
            extra = {int(r.id_ds): (_int(r.qtd) if medida == "Quantidade" else _pct(r.pct)) for r in bolas.itertuples()}
        arq = geo.arquivo_malha()
        G = carrega_geo(str(arq), arq.stat().st_mtime) if arq else None
        lg, mp = st.columns([1.1, 3])
        with lg:
            legenda_ds(tot, n_eq, modo, extra)
        with mp:
            st.altair_chart(mapa(G, tot, modo, bolas, medida), width="stretch")
        if G is None:
            st.warning("Mapa aguardando a malha de bairros do Recife em `painel/assets/` "
                       "(`bairros-do-recife.geojson`). Por ora, barras por DS.")
        else:
            d = G["diag"]
            sem = d[d["id_ds"].isna()]
            with st.expander(f"Diagnóstico da malha · {len(d)} bairros · {len(sem)} sem distrito"):
                st.caption(f"Propriedade do nome: `{G['propriedade_nome']}` · "
                           f"reprojetada de metros para graus: {'sim' if G['reprojetado'] else 'não'}")
                st.dataframe(d[d["casamento"] != "exato"], width="stretch", hide_index=True)
    with dir_:
        h1, h2 = st.columns([3, 1])
        h1.markdown("##### Tendência por Distrito Sanitário")
        meses = h2.selectbox("Período", [6, 12, 24], format_func=lambda m: f"{m} meses", label_visibility="collapsed")
        st.altair_chart(tendencia(D["serie_ds"], meses, comps), width="stretch")
        with st.expander("Ver como tabela"):
            t = D["serie_ds"][D["serie_ds"]["competencia"].isin(comps[-meses:])].pivot(
                index="competencia", columns="DS", values="prop_sim")
            t.index = [_mes(c) for c in t.index]
            st.dataframe(t.style.format("{:.1%}"), width="stretch")
        st.markdown("##### Ranking de Distritos")
        r = ranking_ds(D, comp, comps[-7] if len(comps) > 6 else comps[0])
        st.dataframe(r, width="stretch", hide_index=True, column_config={
            "Distrito": st.column_config.TextColumn(width=70),
            "% Sim (OS)": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1, width=120),
            "% Não informado": st.column_config.NumberColumn(format="percent", width=95),
            "Δ 6m (p.p.)": st.column_config.NumberColumn(format="%+.1f", width=80),
            "Equipes <15%": st.column_config.NumberColumn(width=90)})
        st.caption("Do menor para o maior \"Sim\" (pessoa aceitou informar a orientação sexual). "
                   "\"Equipes < 15%\": equipes com \"Sim\" abaixo de 15% no último quadrimestre.")


def filtros(D: dict):
    c1, c2 = st.columns([1, 1.6])
    mon = D["monitoramento_equipe"].merge(D["unidade"], on="cnes", how="left")
    ds = c1.selectbox("Distrito Sanitário", ["Todos"] + [NOMES_DS[d] for d in sorted(mon["id_ds"].dropna().astype(int).unique())])
    if ds != "Todos":
        mon = mon[mon["id_ds"] == int(ds.split()[1])]
    uni = mon[["cnes", "nome_unidade"]].drop_duplicates().sort_values("nome_unidade")
    u = c2.selectbox("Unidade de Saúde", ["Todas"] + [f"{r.nome_unidade} ({r.cnes})" for r in uni.itertuples()])
    if u != "Todas":
        mon = mon[mon["cnes"] == u[-8:-1]]
    return set(mon["ine"]), mon


def preenchimento(D: dict):
    st.markdown("# Adequação do Preenchimento")
    ines, mon = filtros(D)
    comp = D["comps"][-1]
    f = D["fato_indicador_equipe"]
    f = f[(f["competencia"] == comp) & f["ine"].isin(ines)]
    c = completude(f, [])
    st.subheader(f"Completude dos campos de equidade · {_mes(comp)}")
    bar = alt.Chart(c).mark_bar(color=COR_DS[1], cornerRadiusTopRight=4, cornerRadiusBottomRight=4, size=22).encode(
        y=alt.Y("Campo:N", sort="-x", title=None),
        x=alt.X("Completude:Q", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1])),
        tooltip=["Campo:N", alt.Tooltip("Completude:Q", format=".1%"), "Registros:Q", "Sem registro:Q"])
    st.altair_chart(bar.properties(height=190), width="stretch")
    ns = f[f["marcador"] == "NOME_SOCIAL"]
    st.caption(f"Orientação sexual e identidade de gênero: só pessoas elegíveis (idade ≥ mínima). "
               f"Nome social é opcional e não entra na completude: {_pct(ns[ns['categoria'] == 'PREENCHIDO']['n'].sum() / max(ns['n'].sum(), 1))} "
               f"dos cadastros têm nome social.")
    esq, dir_ = st.columns(2, gap="large")
    with esq:
        st.markdown("##### Completude por Distrito Sanitário")
        cd = completude(f, ["id_ds"])
        t = cd.pivot(index="id_ds", columns="Campo", values="Completude").reset_index()
        t.insert(0, "Distrito", t.pop("id_ds").map(NOMES_DS))
        t = t[["Distrito"] + ORDEM_CAMPOS]
        st.dataframe(t, width="stretch", hide_index=True, column_config={
            k: st.column_config.NumberColumn(format="percent") for k in ORDEM_CAMPOS})
    with dir_:
        st.markdown("##### Evolução da completude (município)")
        s = D["compl_serie"].copy()
        s["data"] = pd.to_datetime(s["competencia"].astype(str), format="%Y%m")
        ln = alt.Chart(s).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=40)).encode(
            x=alt.X("data:T", title=None, axis=alt.Axis(format="%m/%Y")),
            y=alt.Y("Completude:Q", axis=alt.Axis(format="%"), scale=alt.Scale(zero=False)),
            color=alt.Color("Campo:N", legend=alt.Legend(title=None, orient="bottom", columns=2),
                            scale=alt.Scale(domain=ORDEM_CAMPOS, range=[COR_DS[1], COR_DS[2], COR_DS[3], COR_DS[4]])),
            tooltip=["Campo:N", alt.Tooltip("data:T", format="%m/%Y"), alt.Tooltip("Completude:Q", format=".1%")])
        st.altair_chart(ln.properties(height=250), width="stretch")
    st.dataframe(c[["Campo", "Registros", "Sem registro", "Completude"]], width="stretch", hide_index=True,
                 column_config={"Completude": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1)})
    tab1, tab2, tab3 = st.tabs(["Ranking por equipe", "Planilha SESAU (colunas H a U)", "Qualidade × gabarito"])
    with tab1:
        m = mon.merge(D["equipe"][["ine", "nome_equipe"]], on="ine", how="left").dropna(subset=["n_os_sim_pct"])
        m = m.sort_values("n_os_sim_pct").head(30)
        m["DS"] = m["id_ds"].map(NOMES_DS)
        st.caption("As 30 equipes com menor proporção de \"Sim\" (dado real, data de corte).")
        bar = alt.Chart(m).mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4).encode(
            y=alt.Y("nome_equipe:N", sort="x", title=None, axis=alt.Axis(labelLimit=260)),
            x=alt.X("n_os_sim_pct:Q", title="% de Sim", axis=alt.Axis(format="%")),
            color=alt.Color("DS:N", scale=ESCALA_DS),
            tooltip=["nome_equipe:N", "ine:N", "DS:N", alt.Tooltip("n_os_sim_pct:Q", format=".1%"),
                     alt.Tooltip("j_dado_real:Q", title="elegíveis")])
        st.altair_chart(bar.properties(height=max(240, 18 * len(m))), width="stretch")
        st.caption("Equipes pequenas oscilam mais: compare com o intervalo de Wilson do relatório de inferência "
                   "(python -m aps_sintetico inferencia).")
    with tab2:
        g = mon.groupby(["id_ds", "cnes", "nome_unidade"]).sum(numeric_only=True).reset_index()
        g["n_os_sim_pct"] = g["m_os_sim_dado_real"] / g["j_dado_real"].where(g["j_dado_real"] > 0)
        g["r_os_nao_pct"] = g["q_os_nao_dado_real"] / g["j_dado_real"].where(g["j_dado_real"] > 0)
        st.dataframe(g, width="stretch", hide_index=True,
                     column_config={"n_os_sim_pct": st.column_config.NumberColumn(format="percent"),
                                    "r_os_nao_pct": st.column_config.NumberColumn(format="percent")})
        st.download_button("Baixar CSV", g.to_csv(index=False).encode("utf-8"), "monitoramento_usf.csv", "text/csv")
    with tab3:
        if D["qualidade"] is None:
            st.info("Rode `python -m aps_sintetico validar` com o banco carregado para gerar o relatório.")
        else:
            st.dataframe(D["qualidade"], width="stretch", hide_index=True)


def prevencao(D: dict):
    st.markdown("# Prevenção IA")
    p = D["predicoes"]
    if p is None:
        st.info("Ainda não há previsões. Rode `python -m aps_sintetico ml` (ou coloque o `predicoes.parquet` do "
                "modelo final em `saida/<cenário>/ml/`) e esta página passa a mostrar as equipes de maior risco.")
        return
    st.caption("Previsão da proporção de \"Sim\" (orientação sexual) de cada equipe no período seguinte. "
               "A página lê `ml/predicoes.parquet` e funciona com qualquer modelo que mantenha as colunas "
               "`ine, periodo, id_ds, prop_sim_os, previsto`.")
    ines, _ = filtros(D)
    lim = st.slider("Limiar de alerta (\"Sim\" previsto abaixo de)", 0.05, 0.40, LIMIAR_ALERTA, 0.01, format="%.2f")
    per = p["periodo"].max()
    u = p[(p["periodo"] == per) & p["ine"].isin(ines)].merge(D["equipe"][["ine", "nome_equipe", "cnes"]], on="ine", how="left")
    u = u.merge(D["unidade"], on="cnes", how="left")
    u["DS"] = u["id_ds"].map(NOMES_DS)
    u["Alerta"] = u["previsto"] < lim
    u["Variação (p.p.)"] = (u["previsto"] - u["prop_sim_os"]) * 100
    k1, k2, k3 = st.columns(3)
    cartao(k1, "Equipes em alerta", _int(u["Alerta"].sum()), None, None, f"de {len(u)} filtradas")
    cartao(k2, "Modelo", str(u["modelo"].iloc[0]) if "modelo" in u and len(u) else "–", None, None, "da execução em uso")
    cartao(k3, "Período de referência", _periodo(per), None, None, "base da previsão")
    st.write("")
    tab = u.sort_values("previsto")[["nome_equipe", "nome_unidade", "DS", "prop_sim_os", "previsto",
                                    "Variação (p.p.)", "Alerta"]].rename(
        columns={"nome_equipe": "Equipe", "nome_unidade": "Unidade", "prop_sim_os": "Sim atual", "previsto": "Sim previsto"})
    st.dataframe(tab.head(50), width="stretch", hide_index=True, column_config={
        "Sim atual": st.column_config.NumberColumn(format="percent"),
        "Sim previsto": st.column_config.NumberColumn(format="percent"),
        "Variação (p.p.)": st.column_config.NumberColumn(format="%+.1f")})
    st.download_button("Baixar previsões (CSV)", tab.to_csv(index=False).encode("utf-8"), "previsoes_equipes.csv", "text/csv")


def main():
    st.set_page_config(page_title="Nexus Data · APS Recife", page_icon="🩺", layout="wide")
    saida = _args()
    if not (saida / "analitica" / "fato_painel_ml.parquet").exists():
        st.error(f"Não há tabelas analíticas em {saida}. Rode `python -m aps_sintetico tudo` antes.")
        return
    D = carrega(str(saida))
    with st.sidebar:
        st.markdown("## Nexus **Data**")
        pagina = st.radio("Navegação", ["Visão Geral", "Ad. Preenchimento", "Prevenção IA"], label_visibility="collapsed")
        st.divider()
        man = D["manifesto"]
        try:
            quando = pd.Timestamp(man["dt_geracao"]).strftime("%d/%m/%Y - %H:%M")
        except (ValueError, TypeError):
            quando = str(man["dt_geracao"])
        st.markdown(f"**Última atualização**  \n{quando}")
        st.caption(f"Cenário `{man['nome']}` · escala {man['escala']} · semente {man['semente']}  \n"
                   "**Dados sintéticos** – não representam pessoas reais.")
    {"Visão Geral": visao_geral, "Ad. Preenchimento": preenchimento, "Prevenção IA": prevencao}[pagina](D)


main()
