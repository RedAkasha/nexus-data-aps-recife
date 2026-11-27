"""Página "Banco de Dados": estatística, CRUD, gatilhos/procedimentos e views, tudo sobre o banco relacional.

O banco é o SQLite saida/<cenário>/preenchimento.db (formulário relacional + tabelas analíticas copiadas do pipeline:
monitoramento_equipe e painel_ml). Os gráficos e indicadores leem do banco por SQL, não de arquivos.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import extra


def abre(saida: Path, D: dict) -> sqlite3.Connection:
    con = extra.abre_banco(saida)
    extra._sincroniza_estrutura(con, saida, D)
    D["monitoramento_equipe"].to_sql("monitoramento_equipe", con, if_exists="replace", index=False)
    D["fato_painel_ml"].to_sql("painel_ml", con, if_exists="replace", index=False)
    return con


def pagina(D: dict, saida: Path, cores: dict):
    st.markdown("# Banco de Dados")
    st.caption("Tudo nesta página é lido do banco relacional (SQLite) por SQL: indicadores, gráficos, CRUD, gatilhos e views.")
    con = abre(saida, D)
    t1, t2, t3, t4 = st.tabs(["Estatística", "CRUD (4 tabelas)", "Gatilhos e procedimentos", "Views"])
    with t1:
        estatistica(con, cores)
    with t2:
        crud(con)
    with t3:
        gatilhos(con)
    with t4:
        views(con, cores)
    con.close()


# ------------------------------------------------------------------ estatística
def estatistica(con, cores):
    m = pd.read_sql("SELECT id_ds, ine, j_dado_real AS elegiveis, n_os_sim_pct AS pct_sim FROM monitoramento_equipe "
                    "WHERE n_os_sim_pct IS NOT NULL", con)
    pm = pd.read_sql("SELECT periodo, id_ds, prop_sim_os FROM painel_ml", con)
    f1, f2 = st.columns([2, 1])
    ds = f1.multiselect("Distritos Sanitários", sorted(m["id_ds"].unique()), default=sorted(m["id_ds"].unique()),
                        format_func=lambda x: f"DS {x}")
    minimo = f2.slider("Mínimo de elegíveis por equipe", 0, 300, 20, 10)
    m = m[m["id_ds"].isin(ds) & (m["elegiveis"] >= minimo)]
    pm = pm[pm["id_ds"].isin(ds)]
    if m.empty:
        st.info("Nenhuma equipe com esses filtros.")
        return
    x = m["pct_sim"] * 100
    faixa = (x // 5 * 5).astype(int)
    moda = int(faixa.mode().iloc[0])
    k = st.columns(6)
    for c, (t, v) in zip(k, [("Equipes", f"{len(m)}"), ("Média", f"{x.mean():.1f}%"), ("Mediana", f"{x.median():.1f}%"),
                             ("Moda (faixa de 5 p.p.)", f"{moda}–{moda + 5}%"), ("Variância", f"{x.var(ddof=1):.1f}"),
                             ("Desvio padrão", f"{x.std(ddof=1):.1f} p.p.")]):
        c.metric(t, v)
    a, b = st.columns(2)
    with a:
        st.markdown("##### 1. Distribuição do % de Sim por equipe")
        h = alt.Chart(pd.DataFrame({"pct": x})).mark_bar(color=cores[1]).encode(
            x=alt.X("pct:Q", bin=alt.Bin(step=5), title="% de Sim"), y=alt.Y("count():Q", title="Equipes"))
        r = alt.Chart(pd.DataFrame({"v": [x.mean()], "l": ["média"]})).mark_rule(color="#d03b3b", strokeDash=[5, 3]).encode(x="v:Q")
        r2 = alt.Chart(pd.DataFrame({"v": [x.median()]})).mark_rule(color="#333").encode(x="v:Q")
        st.altair_chart((h + r + r2).properties(height=240), width="stretch")
        st.caption("Linha vermelha tracejada = média; preta = mediana.")
    with b:
        st.markdown("##### 2. Comparativo por Distrito (boxplot)")
        bx = alt.Chart(m.assign(DS="DS " + m["id_ds"].astype(str), pct=x)).mark_boxplot(extent="min-max").encode(
            x=alt.X("DS:N", title=None), y=alt.Y("pct:Q", title="% de Sim"),
            color=alt.Color("DS:N", legend=None, scale=alt.Scale(range=list(cores.values()))))
        st.altair_chart(bx.properties(height=240), width="stretch")
    a, b = st.columns(2)
    with a:
        st.markdown("##### 3. Tendência no tempo (média das equipes)")
        t = pm.groupby("periodo")["prop_sim_os"].mean().reset_index()
        t["rotulo"] = t["periodo"].astype(str).str[:4] + "/" + t["periodo"].astype(str).str[4:] + "Q"
        ln = alt.Chart(t).mark_line(point=True, color=cores[2]).encode(
            x=alt.X("rotulo:N", title=None, sort=None), y=alt.Y("prop_sim_os:Q", axis=alt.Axis(format="%"), title="% de Sim"))
        st.altair_chart(ln.properties(height=240), width="stretch")
        if len(t) > 2:
            sl = np.polyfit(range(len(t)), t["prop_sim_os"], 1)[0]
            st.caption(f"Inclinação da reta de tendência: {sl * 100:+.2f} p.p. por quadrimestre.")
    with b:
        st.markdown("##### 4. Correlação: tamanho da base × % de Sim")
        r_ = float(np.corrcoef(m["elegiveis"], m["pct_sim"])[0, 1]) if len(m) > 2 else float("nan")
        sc = alt.Chart(m.assign(pct=x)).mark_circle(opacity=.5, color=cores[3], size=45).encode(
            x=alt.X("elegiveis:Q", title="Elegíveis (n)"), y=alt.Y("pct:Q", title="% de Sim"), tooltip=["ine", "elegiveis", "pct"])
        st.altair_chart((sc + sc.transform_regression("elegiveis", "pct").mark_line(color="#d03b3b")).properties(height=240), width="stretch")
        st.caption(f"Correlação de Pearson r = {r_:.2f}.")
    a, b = st.columns(2)
    with a:
        st.markdown("##### 5. Equipes em alerta (Sim < 15%) por Distrito")
        al = m.assign(alerta=m["pct_sim"] < 0.15).groupby("id_ds").agg(alerta=("alerta", "sum"), equipes=("alerta", "size")).reset_index()
        al["DS"] = "DS " + al["id_ds"].astype(str)
        st.altair_chart(alt.Chart(al).mark_bar(color="#d03b3b").encode(
            x=alt.X("DS:N", title=None), y=alt.Y("alerta:Q", title="Equipes em alerta"), tooltip=["DS", "alerta", "equipes"]).properties(height=240),
            width="stretch")
    with b:
        st.markdown("##### 6. Cadastros do formulário por raça/cor")
        d = pd.read_sql("SELECT raca_cor, SUM(pessoas) AS pessoas FROM vw_raca_identidade GROUP BY 1", con)
        if d.empty:
            st.info("Sem cadastros no formulário. Use Preenchimento Virtual para cadastrar ou gerar exemplos.")
        else:
            st.altair_chart(alt.Chart(d).mark_arc(innerRadius=50).encode(
                theta="pessoas:Q", color=alt.Color("raca_cor:N", scale=alt.Scale(range=list(cores.values())), legend=alt.Legend(title=None)),
                tooltip=["raca_cor", "pessoas"]).properties(height=240), width="stretch")
    st.markdown("##### Estatística descritiva por Distrito")
    g = m.assign(pct=x).groupby("id_ds")["pct"].agg(equipes="count", media="mean", mediana="median", variancia="var", desvio="std",
                                                   minimo="min", maximo="max").round(2).reset_index()
    st.dataframe(g, hide_index=True, width="stretch")


# ------------------------------------------------------------------ CRUD
TABELAS = {"pessoa": ("id_pessoa", "Cadastros (pessoa)"), "profissional": ("id_profissional", "Profissionais"),
           "microarea": ("id_microarea", "Microáreas"), "deficiencia": ("id_deficiencia", "Tipos de deficiência")}


def crud(con):
    st.caption("Criar, ler, atualizar e excluir em 4 tabelas. Edite a grade, adicione linhas no fim e use a lixeira para excluir; "
               "depois clique em Salvar. Os gatilhos continuam valendo: uma regra violada cancela tudo e mostra o motivo.")
    tab = st.selectbox("Tabela", list(TABELAS), format_func=lambda t: TABELAS[t][1])
    pk = TABELAS[tab][0]
    orig = pd.read_sql(f"SELECT * FROM {tab} ORDER BY {pk} DESC LIMIT 100", con)
    ed = st.data_editor(orig, num_rows="dynamic", disabled=[pk], hide_index=True, width="stretch", key=f"ed_{tab}")
    st.caption(f"Mostrando as 100 últimas linhas de {len(pd.read_sql(f'SELECT 1 FROM {tab}', con))}.")
    if st.button("Salvar alterações", type="primary", key=f"sv_{tab}"):
        cols = [c for c in orig.columns if c != pk]
        novos = lambda v: None if pd.isna(v) else (v.item() if hasattr(v, "item") else v)   # noqa: E731
        try:
            con.execute("BEGIN")
            n = {"inseridas": 0, "atualizadas": 0, "excluídas": 0}
            ids_orig = set(orig[pk])
            ids_ed = set(ed[pk].dropna().astype(int))
            for i in ids_orig - ids_ed:
                con.execute(f"DELETE FROM {tab} WHERE {pk} = ?", (int(i),)); n["excluídas"] += 1
            for _, r in ed.iterrows():
                vals = [novos(r[c]) for c in cols]
                if pd.isna(r[pk]):
                    if all(v is None for v in vals):
                        continue
                    con.execute(f"INSERT INTO {tab} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", vals); n["inseridas"] += 1
                else:
                    o = orig[orig[pk] == r[pk]].iloc[0]
                    if any(not (pd.isna(o[c]) and v is None) and o[c] != v for c, v in zip(cols, vals)):
                        con.execute(f"UPDATE {tab} SET {', '.join(c + ' = ?' for c in cols)} WHERE {pk} = ?", vals + [int(r[pk])])
                        n["atualizadas"] += 1
            con.commit()
            st.success(f"Salvo: {n['inseridas']} inserida(s), {n['atualizadas']} atualizada(s), {n['excluídas']} excluída(s).")
            st.rerun() if sum(n.values()) else None
        except sqlite3.DatabaseError as e:
            con.rollback()
            st.error(f"Nada foi salvo. Motivo do banco: {e}")


# ------------------------------------------------------------------ gatilhos e procedimentos
def gatilhos(con):
    st.markdown("##### Gatilhos (triggers) ativos")
    st.dataframe(pd.read_sql("SELECT name AS gatilho, tbl_name AS tabela, "
                             "CASE WHEN name LIKE '%menor%' THEN 'menor de 11 anos: orientação/identidade = NULL' "
                             "WHEN name LIKE '%fechada%' THEN 'regra 8: carga fechada é imutável' "
                             "ELSE 'auditoria de INSERT/UPDATE/DELETE' END AS regra FROM sqlite_master WHERE type = 'trigger'", con),
                 hide_index=True, width="stretch")
    a, b = st.columns(2, gap="large")
    with a:
        st.markdown("##### Demonstração 1: menor de idade")
        st.caption("Tenta gravar uma criança de 5 anos com orientação sexual preenchida. O gatilho deve barrar.")
        if st.button("Tentar gravar (deve falhar)"):
            nasc = date(date.today().year - 5, 1, 1).isoformat()
            ma = con.execute("SELECT MIN(id_microarea) FROM microarea").fetchone()[0]
            try:
                con.execute("INSERT INTO pessoa (id_raca_cor, id_orientacao_sexual, id_microarea, data_coleta, dt_nascimento) "
                            "VALUES (1, 148, ?, ?, ?)", (ma, datetime.now().isoformat(timespec="seconds"), nasc))
                con.commit()
                st.warning("Gravou: o gatilho não disparou.")
            except sqlite3.DatabaseError as e:
                con.rollback()
                st.success(f"Barrado pelo gatilho: {e}")
    with b:
        st.markdown("##### Procedimento: fechar carga (regra 8)")
        st.caption("Tudo coletado até a data escolhida fica imutável. Depois, tente alterar ou excluir um cadastro na aba CRUD.")
        d = st.date_input("Fechar cadastros coletados até", value=date.today(), key="fecha")
        if st.button("Executar procedimento fechar_carga"):
            con.execute("INSERT INTO carga_fechada (data_fechamento, fechada_em) VALUES (?, ?)", (d.isoformat(), datetime.now().isoformat(timespec="seconds")))
            con.commit()
            st.success(f"Carga fechada até {d:%d/%m/%Y}.")
        if st.button("Reabrir todas as cargas (apenas para a demonstração)"):
            con.execute("DELETE FROM carga_fechada"); con.commit(); st.info("Cargas reabertas.")
        st.dataframe(pd.read_sql("SELECT * FROM carga_fechada ORDER BY id_carga DESC", con), hide_index=True, width="stretch")
    st.markdown("##### Auditoria (efeito dos gatilhos de INSERT/UPDATE/DELETE)")
    st.dataframe(pd.read_sql("SELECT * FROM auditoria_pessoa ORDER BY id_auditoria DESC LIMIT 20", con), hide_index=True, width="stretch")
    st.info("SQLite não tem procedures nem funções armazenadas. Aqui, a função idade é uma expressão SQL dentro das views e o "
            "procedimento é executado pelo painel. No MySQL da disciplina, estes mesmos objetos viram CREATE PROCEDURE, CREATE FUNCTION e CREATE TRIGGER.")


# ------------------------------------------------------------------ views
def views(con, cores):
    st.caption("Views do banco, com filtros e gráfico. Cada uma é uma consulta salva (CREATE VIEW).")
    v = st.selectbox("View", ["vw_resumo_equipe", "vw_raca_identidade", "vw_pessoa_idade (faixa etária)"])
    if v == "vw_resumo_equipe":
        minp = st.slider("Mínimo de pessoas cadastradas", 0, 50, 1)
        d = pd.read_sql("SELECT equipe, pessoas, informaram_orientacao, pct_informou_orientacao FROM vw_resumo_equipe "
                        "WHERE pessoas >= ? ORDER BY pessoas DESC LIMIT 25", con, params=(minp,))
        st.dataframe(d, hide_index=True, width="stretch")
        if len(d):
            st.altair_chart(alt.Chart(d).mark_bar(color=cores[1]).encode(
                y=alt.Y("equipe:N", sort="-x", title=None), x=alt.X("pessoas:Q"), tooltip=list(d.columns)).properties(height=max(200, 22 * len(d))),
                width="stretch")
    elif v == "vw_raca_identidade":
        d = pd.read_sql("SELECT * FROM vw_raca_identidade", con)
        st.dataframe(d, hide_index=True, width="stretch")
        if len(d):
            st.altair_chart(alt.Chart(d).mark_bar().encode(x=alt.X("raca_cor:N", title=None), y="pessoas:Q",
                            color=alt.Color("identidade:N", scale=alt.Scale(range=list(cores.values()))),
                            tooltip=list(d.columns)).properties(height=280), width="stretch")
    else:
        d = pd.read_sql("SELECT faixa_etaria, COUNT(*) AS pessoas FROM vw_pessoa_idade GROUP BY 1 ORDER BY 1", con)
        st.dataframe(d, hide_index=True, width="stretch")
        if len(d):
            st.altair_chart(alt.Chart(d).mark_bar(color=cores[2]).encode(x=alt.X("faixa_etaria:N", title="Faixa etária", sort=None), y="pessoas:Q",
                            tooltip=list(d.columns)).properties(height=260), width="stretch")
    if con.execute("SELECT COUNT(*) FROM pessoa").fetchone()[0] == 0:
        st.info("O formulário ainda está vazio: cadastre pessoas ou gere exemplos em Preenchimento Virtual.")
