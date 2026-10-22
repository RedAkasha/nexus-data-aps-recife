"""Painel de monitoramento (Etapa 9) – segue o rascunho de wireframe do grupo.

Lê as tabelas analíticas em Parquet (python -m aps_sintetico analitica) de uma saída do
gerador, sem precisar do banco. Executar:
    streamlit run painel/app.py -- --saida saida/base
Os dados são SINTÉTICOS; nenhuma linha corresponde a pessoa real.
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

from aps_sintetico import parametros as P  # noqa: E402

AZUL, CINZA, LARANJA = "#2a78d6", "#8a8984", "#eb6834"   # paleta de referência (slots 1 e 2)
NOMES_DS = {i: f"DS {r}" for i, r in enumerate(["I", "II", "III", "IV", "V", "VI", "VII", "VIII"], start=1)}


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
    out["unidade"] = est["unidade"][["cnes", "nome_unidade"]] if "nome_unidade" in est["unidade"] else \
        est["unidade"][["cnes"]].assign(nome_unidade=est["unidade"]["cnes"])
    out["equipe"] = est["equipe"][["ine", "nome_equipe", "cnes", "tipo_equipe"]]
    acoes = s / "nucleo" / "acao_formativa.csv"
    out["acoes"] = pd.read_csv(acoes, dtype=str) if acoes.exists() else pd.DataFrame(columns=["ine", "dt_acao"])
    man = json.loads((s / "manifesto.json").read_text(encoding="utf-8"))
    out["manifesto"] = man
    q = s / "relatorios" / "qualidade_vs_gabarito.csv"
    out["qualidade"] = pd.read_csv(q) if q.exists() else None
    p = s / "ml" / "predicoes.parquet"
    out["predicoes"] = pd.read_parquet(p) if p.exists() else None
    return out


def filtros(D: dict):
    c1, c2, c3 = st.columns([1, 1.4, 1])
    ds_ok = sorted(D["monitoramento_equipe"]["id_ds"].dropna().astype(int).unique())
    ds = c1.selectbox("Distrito Sanitário", ["Todos"] + [NOMES_DS[d] for d in ds_ok])
    mon = D["monitoramento_equipe"].merge(D["unidade"], on="cnes", how="left")
    if ds != "Todos":
        mon = mon[mon["id_ds"] == [k for k, v in NOMES_DS.items() if v == ds][0]]
    uni = mon[["cnes", "nome_unidade"]].drop_duplicates().sort_values("nome_unidade")
    u = c2.selectbox("Unidade de Saúde", ["Todas"] + [f"{r.nome_unidade} ({r.cnes})" for r in uni.itertuples()])
    if u != "Todas":
        mon = mon[mon["cnes"] == u[-8:-1]]
    comp = D["dim_competencia"]["competencia"].tolist()
    c = c3.selectbox("Competência", comp[::-1], format_func=lambda x: f"{str(x)[4:]}/{str(x)[:4]}")
    return set(mon["ine"]), c, mon


def cartao(col, titulo, valor, nota):
    col.markdown(f"<div style='border:1px solid #d9d8d4;border-radius:10px;padding:14px 16px'>"
                 f"<div style='color:#52514e;font-size:0.9rem'>{titulo}</div>"
                 f"<div style='font-size:1.9rem;font-weight:600'>{valor}</div>"
                 f"<div style='color:#8a8984;font-size:0.8rem'>{nota}</div></div>", unsafe_allow_html=True)


def visao_geral(D: dict):
    ines, comp, mon = filtros(D)
    fie = D["fato_indicador_equipe"]
    f = fie[(fie["competencia"] == comp) & fie["ine"].isin(ines) & fie["elegivel"]]
    os_ = f[f["marcador"] == "OS"].groupby("categoria")["n"].sum()
    n = int(os_.reindex(["SIM", "NAO", "NAO_INFORMADO"]).fillna(0).sum())
    fae = D["fato_atendimento_equipe"]
    at = fae[(fae["competencia"] == comp) & fae["ine"].isin(ines)]
    pm = D["fato_painel_ml"]
    ult = pm[pm["ine"].isin(ines)].sort_values("periodo").groupby("ine").tail(1)
    alerta = int((ult["prop_sim_os"] < 0.15).sum())
    c1, c2, c3 = st.columns(3)
    cartao(c1, "Atendimentos (FAI) na competência", f"{int(at['n_atendimentos'].sum()):,}".replace(",", "."),
           f"{int(at['n_cidadaos_atendidos'].sum()):,} cidadãos atendidos".replace(",", "."))
    cartao(c2, "Orientação sexual: \"Sim\" no dado real", f"{os_.get('SIM', 0) / n:.1%}" if n else "–",
           f"não informado: {os_.get('NAO_INFORMADO', 0) / n:.1%} de {n:,} elegíveis".replace(",", ".") if n else "")
    cartao(c3, "⚠ Equipes com \"Sim\" abaixo de 15%", f"{alerta}",
           f"de {len(ult)} equipes no último quadrimestre")
    st.write("")
    # série temporal da proporção de Sim, com as oficinas
    st.subheader("Proporção de \"Sim\" (orientação sexual) por competência")
    s = fie[fie["ine"].isin(ines) & fie["elegivel"] & (fie["marcador"] == "OS") &
            fie["categoria"].isin(["SIM", "NAO", "NAO_INFORMADO"])]
    s = s.pivot_table(index="competencia", columns="categoria", values="n", aggfunc="sum").fillna(0)
    s = (s.get("SIM", 0) / s.sum(axis=1)).rename("prop").reset_index()
    s["data"] = pd.to_datetime(s["competencia"].astype(str), format="%Y%m")
    linha = alt.Chart(s).mark_line(color=AZUL, strokeWidth=2).encode(
        x=alt.X("data:T", title=None, axis=alt.Axis(format="%m/%Y", tickCount=12)),
        y=alt.Y("prop:Q", title="proporção de Sim", axis=alt.Axis(format="%"), scale=alt.Scale(zero=False)),
        tooltip=[alt.Tooltip("data:T", format="%m/%Y", title="competência"),
                 alt.Tooltip("prop:Q", format=".1%", title="Sim")])
    ac = D["acoes"][D["acoes"]["ine"].isin(ines)].copy()
    camadas = [linha]
    if len(ac):
        ac["data"] = pd.to_datetime(ac["dt_acao"])
        ac["tipo"] = ac["tipo_acao"].map({"1": "oficina", "2": "material formativo"}).fillna("outra")
        camadas.append(alt.Chart(ac).mark_tick(color=CINZA, thickness=1, size=14).encode(
            x=alt.X("data:T", axis=alt.Axis(format="%m/%Y")), y=alt.value(0), tooltip=[alt.Tooltip("data:T", format="%d/%m/%Y"), "tipo:N", "ine:N"]))
    st.altair_chart(alt.layer(*camadas).properties(height=260), width="stretch")
    st.caption("Marcas cinzas no topo: datas de oficinas e materiais formativos das equipes filtradas.")
    # atendimentos por território
    st.subheader("Atendimentos por território")
    nivel = st.radio("Agrupar por", ["Distrito Sanitário", "Unidade de Saúde"], horizontal=True,
                     label_visibility="collapsed")
    a = at.merge(D["equipe"], on="ine").merge(D["unidade"], on="cnes", how="left")
    a = a.merge(mon[["ine", "id_ds"]], on="ine", how="left")
    if nivel == "Distrito Sanitário":
        g = a.groupby("id_ds")["n_atendimentos"].sum().reset_index()
        g["território"] = g["id_ds"].map(NOMES_DS)
    else:
        g = a.groupby("nome_unidade")["n_atendimentos"].sum().reset_index().rename(columns={"nome_unidade": "território"})
        g = g.sort_values("n_atendimentos", ascending=False).head(20)
    bar = alt.Chart(g).mark_bar(color=AZUL, cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=36).encode(
        x=alt.X("território:N", sort="-y", title=None, axis=alt.Axis(labelAngle=0 if nivel == "Distrito Sanitário"
                                                                       else -40, labelLimit=180)),
        y=alt.Y("n_atendimentos:Q", title="atendimentos"),
        tooltip=["território:N", alt.Tooltip("n_atendimentos:Q", format=",")])
    st.altair_chart(bar.properties(height=300), width="stretch")


def ranking(D: dict):
    ines, comp, mon = filtros(D)
    st.subheader("Ranking das equipes (dado real, data de corte)")
    m = mon.merge(D["equipe"][["ine", "nome_equipe"]], on="ine", how="left").sort_values("n_os_sim_pct")
    m["DS"] = m["id_ds"].map(NOMES_DS)
    bar = alt.Chart(m).mark_bar(color=AZUL, cornerRadiusTopRight=4, cornerRadiusBottomRight=4).encode(
        y=alt.Y("nome_equipe:N", sort="x", title=None), x=alt.X("n_os_sim_pct:Q", title="proporção de Sim",
                                                               axis=alt.Axis(format="%")),
        tooltip=["nome_equipe:N", "ine:N", "DS:N", alt.Tooltip("n_os_sim_pct:Q", format=".1%"),
                 alt.Tooltip("j_dado_real:Q", title="elegíveis")])
    st.altair_chart(bar.properties(height=max(240, 16 * len(m))), width="stretch")
    st.caption("Equipes pequenas oscilam mais: compare com o intervalo de Wilson e a estimativa bayesiana "
               "empírica do relatório de inferência (python -m aps_sintetico inferencia).")


def planilha(D: dict):
    ines, comp, mon = filtros(D)
    st.subheader("Monitoramento por USF – colunas H a U da planilha da SESAU")
    g = mon.groupby(["id_ds", "cnes", "nome_unidade"]).sum(numeric_only=True).reset_index()
    g["n_os_sim_pct"] = g["m_os_sim_dado_real"] / g["j_dado_real"]
    g["r_os_nao_pct"] = g["q_os_nao_dado_real"] / g["j_dado_real"]
    st.dataframe(g, width="stretch", hide_index=True,
                 column_config={"n_os_sim_pct": st.column_config.NumberColumn(format="percent"),
                                "r_os_nao_pct": st.column_config.NumberColumn(format="percent")})
    st.download_button("Baixar CSV", g.to_csv(index=False).encode("utf-8"), "monitoramento_usf.csv", "text/csv")


def qualidade(D: dict):
    st.subheader("Regras de qualidade × gabarito de defeitos")
    if D["qualidade"] is None:
        st.info("Rode `python -m aps_sintetico validar` com o banco carregado para gerar o relatório.")
        return
    st.dataframe(D["qualidade"], width="stretch", hide_index=True)


def prevencao(D: dict):
    st.subheader("Prevenção IA – equipes com maior risco de baixa proporção de Sim no próximo quadrimestre")
    p = D["predicoes"]
    if p is None:
        st.info("Rode `python -m aps_sintetico ml` para treinar os modelos e gerar as predições.")
        return
    ines, _, _ = filtros(D)
    p = p[p["ine"].isin(ines)].sort_values("previsto").head(30)
    st.dataframe(p, width="stretch", hide_index=True)


def main():
    st.set_page_config(page_title="APS Recife · dados sintéticos", page_icon="🩺", layout="wide")
    saida = _args()
    if not (saida / "analitica" / "fato_painel_ml.parquet").exists():
        st.error(f"Não há tabelas analíticas em {saida}. Rode `python -m aps_sintetico tudo` antes.")
        return
    D = carrega(str(saida))
    with st.sidebar:
        st.markdown("## ✚ APS Recife")
        pagina = st.radio("Navegação", ["Visão geral", "Ranking por equipe", "Relatórios (planilha)",
                                        "Qualidade do registro", "Prevenção IA"], label_visibility="collapsed")
        st.divider()
        man = D["manifesto"]
        st.caption(f"Última atualização: {man['dt_geracao']}\n\nCenário `{man['nome']}` · escala {man['escala']} · "
                   f"semente {man['semente']}\n\n**Dados sintéticos** – não representam pessoas reais.")
    st.title("Dashboard")
    {"Visão geral": visao_geral, "Ranking por equipe": ranking, "Relatórios (planilha)": planilha,
     "Qualidade do registro": qualidade, "Prevenção IA": prevencao}[pagina](D)


main()
