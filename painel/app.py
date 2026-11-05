"""Painel Nexus Data · APS Recife – segue o mockup "Visão Geral - Recife" do grupo.

Páginas: Visão Geral, Ad. Preenchimento (adequação do preenchimento) e Prevenção IA.
Lê as tabelas analíticas em Parquet (python -m aps_sintetico analitica) de uma saída do
gerador, sem precisar do banco. Executar:
    streamlit run painel/app.py -- --saida saida/base
Mapa: coloque a malha dos Distritos Sanitários em painel/assets/distritos_sanitarios.geojson
(propriedade com o número do DS, 1 a 8). Sem o arquivo, o painel mostra barras por distrito.
Os dados são SINTÉTICOS; nenhuma linha corresponde a pessoa real.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from aps_sintetico import parametros as P  # noqa: E402

GEOJSON = Path(__file__).parent / "assets" / "distritos_sanitarios.geojson"
LIMIAR_ALERTA = 0.15          # mesmo corte do painel anterior: "Sim" abaixo de 15%
# Paleta categórica validada (dataviz), uma cor fixa por DS: a cor segue o distrito, nunca o ranking
COR_DS = {1: "#2a78d6", 2: "#eb6834", 3: "#1baf7a", 4: "#eda100", 5: "#e87ba4", 6: "#008300",
          7: "#6250d6", 8: "#e34948"}
NOMES_DS = {i: f"DS {i}" for i in range(1, 9)}
ESCALA_DS = alt.Scale(domain=list(NOMES_DS.values()), range=list(COR_DS.values()))
INK, INK2, MUDO = "#0b0b0b", "#52514e", "#898781"
MARCADORES = {"OS": "Orientação sexual", "IG": "Identidade de gênero", "RACA_COR": "Raça/cor",
              "DEFICIENCIA": "Deficiência", "NOME_SOCIAL": "Nome social"}
VAZIOS = {"OS": ["NAO_INFORMADO"], "IG": ["NAO_INFORMADO"], "RACA_COR": ["VAZIO"],
          "DEFICIENCIA": ["SEM_REGISTRO"], "NOME_SOCIAL": ["VAZIO"]}


# ----------------------------------------------------------------------------- dados
def _args() -> Path:
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", default=str(RAIZ / "saida" / "base"))
    a, _ = ap.parse_known_args(sys.argv[1:])
    return Path(a.saida)


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
    return out


def _mes(c) -> str:
    return f"{str(c)[4:]}/{str(c)[:4]}"


def _pct(x, casas=1) -> str:
    return "–" if pd.isna(x) else f"{x * 100:.{casas}f}%".replace(".", ",")


def _int(x) -> str:
    return f"{int(x):,}".replace(",", ".")


def _pp(x) -> str:
    return "–" if pd.isna(x) else f"{x * 100:+.1f} p.p.".replace(".", ",")


def serie_cadastrados(D) -> pd.Series:
    """Cadastros ativos por competência = soma do marcador raça/cor (todo cidadão ativo tem uma linha)."""
    f = D["fato_indicador_equipe"]
    return f[f["marcador"] == "RACA_COR"].groupby("competencia")["n"].sum()


def serie_sim_ds(D) -> pd.DataFrame:
    """% de 'Sim' em orientação sexual (dado real) por competência × DS."""
    f = D["fato_indicador_equipe"]
    f = f[(f["marcador"] == "OS") & f["elegivel"] & f["categoria"].isin(["SIM", "NAO", "NAO_INFORMADO"])]
    t = f.pivot_table(index=["competencia", "id_ds"], columns="categoria", values="n", aggfunc="sum").fillna(0)
    t["prop_sim"] = t["SIM"] / t.sum(axis=1)
    t["prop_ni"] = t["NAO_INFORMADO"] / (t["SIM"] + t["NAO"] + t["NAO_INFORMADO"])
    t = t.reset_index()
    t["DS"] = t["id_ds"].map(NOMES_DS)
    return t[["competencia", "id_ds", "DS", "prop_sim", "prop_ni"]]


def alerta_ml(D, limiar: float) -> tuple[float, float, int, int]:
    """Parcela de equipes com 'Sim' previsto abaixo do limiar, no último período e no anterior."""
    p = D["predicoes"]
    if p is None or p.empty:
        return float("nan"), float("nan"), 0, 0
    per = sorted(p["periodo"].unique())
    def parcela(x):
        return (x["previsto"] < limiar).mean(), int((x["previsto"] < limiar).sum()), len(x)
    a, na, n = parcela(p[p["periodo"] == per[-1]])
    b = parcela(p[p["periodo"] == per[-2]])[0] if len(per) > 1 else float("nan")
    return a, b, na, n


# ----------------------------------------------------------------------------- componentes
def cartao(col, titulo, valor, delta, bom_se_sobe: bool | None, nota="", rel=False):
    cor = MUDO
    seta = ""
    if delta is not None and not pd.isna(delta) and round(delta * 100, 1) != 0:
        seta = "▲" if delta > 0 else "▼"
        cor = ("#006300" if (delta > 0) == bom_se_sobe else "#d03b3b") if bom_se_sobe is not None else INK2
    d = f"<span style='color:{cor};font-weight:600'>{seta} {delta_txt(delta, rel)}</span>" if seta else ""
    col.markdown(
        f"<div style='border:1px solid #d9d8d4;border-radius:10px;padding:14px 16px;height:100%'>"
        f"<div style='color:{INK2};font-size:0.9rem'>{titulo}</div>"
        f"<div style='font-size:2rem;font-weight:700;line-height:1.2'>{valor} "
        f"<span style='font-size:0.95rem'>{d}</span></div>"
        f"<div style='color:{MUDO};font-size:0.8rem'>{nota}</div></div>", unsafe_allow_html=True)


def delta_txt(x, rel=False) -> str:
    """rel: variação relativa (%); senão, diferença em pontos percentuais."""
    if x is None or pd.isna(x):
        return ""
    return f"{abs(x) * 100:.1f}%".replace(".", ",") if rel else f"{abs(x) * 100:.1f} p.p.".replace(".", ",")


def _props_geo(feat: dict) -> int | None:
    pr = feat.get("properties", {})
    if str(pr.get("ds", "")).isdigit():
        return int(pr["ds"])
    for v in feat.get("properties", {}).values():
        m = re.search(r"\b([1-8])\b|DS\s*([1-8])|^([1-8])$", str(v), re.I)
        if m:
            return int(next(g for g in m.groups() if g))
    return None


def mapa_ds(g: pd.DataFrame, col: str, titulo: str):
    """Coroplético se o GeoJSON existir; senão barras por DS (cor fixa do distrito)."""
    if GEOJSON.exists():
        gj = json.loads(GEOJSON.read_text(encoding="utf-8"))
        val = g.set_index("id_ds")[col]
        for f in gj["features"]:
            n = _props_geo(f)
            f["properties"]["id_ds"] = n
            f["properties"]["valor"] = None if n not in val.index else float(val[n])
            f["properties"]["DS"] = NOMES_DS.get(n, "?")
        ch = alt.Chart(alt.Data(values=gj["features"])).mark_geoshape(stroke="white", strokeWidth=1.5).encode(
            color=alt.Color("properties.valor:Q", title=titulo, scale=alt.Scale(scheme="blues"),
                            legend=alt.Legend(format=".0%")),
            tooltip=[alt.Tooltip("properties.DS:N", title="Distrito"),
                     alt.Tooltip("properties.valor:Q", title=titulo, format=".1%")],
        ).project("mercator").properties(height=380)
        return ch
    return alt.Chart(g.assign(DS=g["id_ds"].map(NOMES_DS))).mark_bar(
        cornerRadiusTopRight=4, cornerRadiusBottomRight=4, size=22).encode(
        y=alt.Y("DS:N", sort=list(NOMES_DS.values()), title=None),
        x=alt.X(f"{col}:Q", title=titulo, axis=alt.Axis(format="%")),
        color=alt.Color("DS:N", scale=ESCALA_DS, legend=None),
        tooltip=[alt.Tooltip("DS:N", title="Distrito"), alt.Tooltip(f"{col}:Q", title=titulo, format=".1%")],
    ).properties(height=380)


def tendencia(s: pd.DataFrame, meses: int, comps: list):
    jan = comps[-meses:]
    d = s[s["competencia"].isin(jan)].copy()
    d["data"] = pd.to_datetime(d["competencia"].astype(str), format="%Y%m")
    sel = alt.selection_point(fields=["DS"], bind="legend")
    base = alt.Chart(d).encode(
        x=alt.X("data:T", title=None, axis=alt.Axis(format="%m/%Y", labelColor=MUDO)),
        y=alt.Y("prop_sim:Q", title="% de \"Sim\" (orientação sexual)", axis=alt.Axis(format="%"),
                scale=alt.Scale(zero=False)),
        color=alt.Color("DS:N", scale=ESCALA_DS, legend=alt.Legend(title=None, orient="right")),
        opacity=alt.condition(sel, alt.value(1), alt.value(0.15)))
    linhas = base.mark_line(strokeWidth=2)
    pts = base.mark_circle(size=60, stroke="white", strokeWidth=2).encode(
        tooltip=[alt.Tooltip("data:T", format="%m/%Y", title="competência"), "DS:N",
                 alt.Tooltip("prop_sim:Q", format=".1%", title="Sim")])
    return (linhas + pts).add_params(sel).properties(height=300)


def ranking_ds(D, s: pd.DataFrame, comp, comp_ant) -> pd.DataFrame:
    a = s[s["competencia"] == comp].set_index("id_ds")
    b = s[s["competencia"] == comp_ant].set_index("id_ds")
    r = pd.DataFrame({"Distrito": a.index.map(NOMES_DS), "% Sim (OS)": a["prop_sim"].values,
                      "% Não informado": a["prop_ni"].values,
                      "Variação (p.p.)": ((a["prop_sim"] - b["prop_sim"]) * 100).values}, index=a.index)
    ml = D["predicoes"]
    if ml is not None:
        u = ml[ml["periodo"] == ml["periodo"].max()]
        r["Equipes em alerta (ML)"] = u.assign(al=u["previsto"] < LIMIAR_ALERTA).groupby("id_ds")["al"].sum() \
            .reindex(r.index).fillna(0).astype(int)
    return r.sort_values("% Sim (OS)").reset_index(drop=True)


# ----------------------------------------------------------------------------- páginas
def visao_geral(D: dict):
    st.markdown("# Visão Geral - Recife")
    comps = D["comps"]
    comp = comps[-1]
    ant = comps[-13] if len(comps) > 12 else comps[0]
    cad = serie_cadastrados(D)
    s = serie_sim_ds(D)
    tot = s[s["competencia"] == comp]
    fie = D["fato_indicador_equipe"]
    def sim_geral(c):
        f = fie[(fie["competencia"] == c) & (fie["marcador"] == "OS") & fie["elegivel"]]
        n = f[f["categoria"].isin(["SIM", "NAO", "NAO_INFORMADO"])]["n"].sum()
        return f[f["categoria"] == "SIM"]["n"].sum() / n if n else float("nan")
    sim, sim0 = sim_geral(comp), sim_geral(ant)
    al, al0, n_al, n_eq = alerta_ml(D, LIMIAR_ALERTA)
    c1, c2, c3 = st.columns(3)
    cartao(c1, "Pacientes cadastrados (ativos)", _int(cad[comp]),
           (cad[comp] - cad[ant]) / cad[ant] if cad[ant] else None, True, f"vs. {_mes(ant)}", rel=True)
    cartao(c2, "Orientação sexual: \"Sim\" no dado real", _pct(sim), sim - sim0, True,
           f"vs. {_mes(ant)} · só pessoas elegíveis")
    cartao(c3, "Equipes em risco de baixo preenchimento", _pct(al),
           None if pd.isna(al0) else al - al0, False,
           f"{n_al} de {n_eq} equipes com \"Sim\" previsto < {LIMIAR_ALERTA:.0%} (modelo de ML)")
    st.write("")
    ce, cd = st.columns([1, 1.15])
    with ce:
        st.markdown("##### Mapa por Distrito Sanitário")
        met = st.selectbox("Indicador", ["% de \"Sim\" (orientação sexual)", "% não informado (orientação sexual)"],
                           label_visibility="collapsed")
        col = "prop_sim" if met.startswith("% de") else "prop_ni"
        st.altair_chart(mapa_ds(tot, col, met), width="stretch")
        if not GEOJSON.exists():
            st.caption("Mapa coroplético aguardando a malha dos Distritos Sanitários "
                       "(`painel/assets/distritos_sanitarios.geojson`); por ora, barras por DS.")
    with cd:
        h1, h2 = st.columns([3, 1])
        h1.markdown("##### Tendência por Distrito Sanitário")
        meses = h2.selectbox("Período", [6, 12, 24], format_func=lambda m: f"{m} meses",
                             label_visibility="collapsed")
        st.altair_chart(tendencia(s, meses, comps), width="stretch")
        with st.expander("Ver como tabela"):
            t = s[s["competencia"].isin(comps[-meses:])].pivot(index="competencia", columns="DS", values="prop_sim")
            t.index = [_mes(c) for c in t.index]
            st.dataframe(t.style.format("{:.1%}"), width="stretch")
    st.markdown("##### Ranking de Distritos")
    r = ranking_ds(D, s, comp, comps[-7] if len(comps) > 6 else comps[0])
    cfg = {"% Sim (OS)": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1),
           "% Não informado": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1),
           "Variação (p.p.)": st.column_config.NumberColumn(format="%+.1f", help="vs. 6 meses antes")}
    st.dataframe(r, width="stretch", hide_index=True, column_config=cfg)
    st.caption("Ordenado do menor para o maior \"Sim\". A variação compara com seis meses antes.")


def filtros(D: dict):
    c1, c2 = st.columns([1, 1.6])
    mon = D["monitoramento_equipe"].merge(D["unidade"], on="cnes", how="left")
    ds_ok = sorted(mon["id_ds"].dropna().astype(int).unique())
    ds = c1.selectbox("Distrito Sanitário", ["Todos"] + [NOMES_DS[d] for d in ds_ok])
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
    linhas = []
    for m, nome in MARCADORES.items():
        x = f[f["marcador"] == m]
        tot = x["n"].sum()
        vaz = x[x["categoria"].isin(VAZIOS[m])]["n"].sum()
        linhas.append({"Campo": nome, "Registros": int(tot), "Sem preenchimento": int(vaz),
                       "Completude": 1 - vaz / tot if tot else float("nan")})
    comp_df = pd.DataFrame(linhas)
    st.subheader(f"Completude dos campos de equidade · {_mes(comp)}")
    bar = alt.Chart(comp_df).mark_bar(color=COR_DS[1], cornerRadiusTopRight=4, cornerRadiusBottomRight=4, size=22
                                       ).encode(
        y=alt.Y("Campo:N", sort="-x", title=None), x=alt.X("Completude:Q", axis=alt.Axis(format="%"),
                                                          scale=alt.Scale(domain=[0, 1])),
        tooltip=["Campo:N", alt.Tooltip("Completude:Q", format=".1%"), "Registros:Q", "Sem preenchimento:Q"])
    st.altair_chart(bar.properties(height=210), width="stretch")
    st.dataframe(comp_df, width="stretch", hide_index=True,
                 column_config={"Completude": st.column_config.ProgressColumn(format="percent", min_value=0,
                                                                              max_value=1)})
    tab1, tab2, tab3 = st.tabs(["Ranking por equipe", "Planilha SESAU (colunas H a U)", "Qualidade × gabarito"])
    with tab1:
        m = mon.merge(D["equipe"][["ine", "nome_equipe"]], on="ine", how="left").sort_values("n_os_sim_pct")
        m["DS"] = m["id_ds"].map(NOMES_DS)
        m = m.head(30)
        st.caption("As 30 equipes com menor proporção de Sim.")
        bar = alt.Chart(m).mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4).encode(
            y=alt.Y("nome_equipe:N", sort="x", title=None),
            x=alt.X("n_os_sim_pct:Q", title="% de Sim", axis=alt.Axis(format="%")),
            color=alt.Color("DS:N", scale=ESCALA_DS),
            tooltip=["nome_equipe:N", "ine:N", "DS:N", alt.Tooltip("n_os_sim_pct:Q", format=".1%"),
                     alt.Tooltip("j_dado_real:Q", title="elegíveis")])
        st.altair_chart(bar.properties(height=max(240, 16 * len(m))), width="stretch")
        st.caption("Equipes pequenas oscilam mais: compare com o intervalo de Wilson e a estimativa bayesiana "
                   "do relatório de inferência (python -m aps_sintetico inferencia).")
    with tab2:
        g = mon.groupby(["id_ds", "cnes", "nome_unidade"]).sum(numeric_only=True).reset_index()
        g["n_os_sim_pct"] = g["m_os_sim_dado_real"] / g["j_dado_real"]
        g["r_os_nao_pct"] = g["q_os_nao_dado_real"] / g["j_dado_real"]
        st.dataframe(g, width="stretch", hide_index=True,
                     column_config={"n_os_sim_pct": st.column_config.NumberColumn(format="percent"),
                                    "r_os_nao_pct": st.column_config.NumberColumn(format="percent")})
        st.download_button("Baixar CSV", g.to_csv(index=False).encode("utf-8"), "monitoramento_usf.csv",
                           "text/csv")
    with tab3:
        if D["qualidade"] is None:
            st.info("Rode `python -m aps_sintetico validar` com o banco carregado para gerar o relatório.")
        else:
            st.dataframe(D["qualidade"], width="stretch", hide_index=True)


def prevencao(D: dict):
    st.markdown("# Prevenção IA")
    p = D["predicoes"]
    if p is None:
        st.info("Rode `python -m aps_sintetico ml` para treinar os modelos e gerar as predições.")
        return
    st.caption("Previsão da proporção de \"Sim\" (orientação sexual) de cada equipe no próximo quadrimestre. "
               "O modelo só vale se vencer a persistência no teste; veja `ml/relatorio_ml.md`.")
    ines, _ = filtros(D)
    c1, c2 = st.columns([1, 2])
    lim = c1.slider("Limiar de alerta (\"Sim\" previsto abaixo de)", 0.05, 0.40, LIMIAR_ALERTA, 0.01, format="%.2f")
    per = p["periodo"].max()
    u = p[(p["periodo"] == per) & p["ine"].isin(ines)].merge(D["equipe"][["ine", "nome_equipe", "cnes"]], on="ine",
                                                              how="left")
    u = u.merge(D["unidade"], on="cnes", how="left")
    u["DS"] = u["id_ds"].map(NOMES_DS)
    u["Alerta"] = u["previsto"] < lim
    u["Variação (p.p.)"] = (u["previsto"] - u["prop_sim_os"]) * 100
    k1, k2, k3 = st.columns(3)
    cartao(k1, "Equipes em alerta", _int(u["Alerta"].sum()), None, None, f"de {len(u)} filtradas")
    cartao(k2, "Modelo escolhido", u["modelo"].iloc[0] if len(u) else "–", None, None,
           "melhor que a persistência na validação" if len(u) and u["melhor_que_persistencia_cv"].iloc[0]
           else "não superou a persistência na validação")
    cartao(k3, "Último período", f"{str(per)[:4]}/Q{str(per)[4:]}", None, None, "base da previsão")
    st.write("")
    tab = u.sort_values("previsto")[["nome_equipe", "nome_unidade", "DS", "prop_sim_os", "previsto",
                                    "Variação (p.p.)", "Alerta"]].rename(
        columns={"nome_equipe": "Equipe", "nome_unidade": "Unidade", "prop_sim_os": "Sim atual",
                 "previsto": "Sim previsto"})
    st.dataframe(tab.head(50), width="stretch", hide_index=True, column_config={
        "Sim atual": st.column_config.NumberColumn(format="percent"),
        "Sim previsto": st.column_config.NumberColumn(format="percent"),
        "Variação (p.p.)": st.column_config.NumberColumn(format="%+.1f")})
    st.download_button("Baixar previsões (CSV)", tab.to_csv(index=False).encode("utf-8"), "previsoes_equipes.csv",
                       "text/csv")


def main():
    st.set_page_config(page_title="Nexus Data · APS Recife", page_icon="🩺", layout="wide")
    saida = _args()
    if not (saida / "analitica" / "fato_painel_ml.parquet").exists():
        st.error(f"Não há tabelas analíticas em {saida}. Rode `python -m aps_sintetico tudo` antes.")
        return
    D = carrega(str(saida))
    with st.sidebar:
        st.markdown("## Nexus **Data**")
        pagina = st.radio("Navegação", ["Visão Geral", "Ad. Preenchimento", "Prevenção IA"],
                          label_visibility="collapsed")
        st.divider()
        man = D["manifesto"]
        st.markdown(f"**Última atualização**  \n{man['dt_geracao']}")
        st.caption(f"Cenário `{man['nome']}` · escala {man['escala']} · semente {man['semente']}  \n"
                   "**Dados sintéticos** – não representam pessoas reais.")
    {"Visão Geral": visao_geral, "Ad. Preenchimento": preenchimento, "Prevenção IA": prevencao}[pagina](D)


main()
