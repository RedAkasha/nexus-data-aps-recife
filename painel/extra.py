"""Abas extras do painel: Preenchimento Virtual (formulário → banco) e SQL e Inferência.

Preenchimento Virtual: formulário de UMA pessoa com orientação, identidade, deficiência (N:N), raça/cor,
microárea e equipe. Grava num banco SQLite relacional (saida/<cenário>/preenchimento.db) com tabelas de domínio
e chaves estrangeiras, como pediu o professor. "Não deseja informar" grava NULL; "Sim" grava uma categoria.
SQL e Inferência: consultas SQL (com resultado e gráfico) e gráficos de inferência (calibração e KPI χ² por equipe).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from scipy import stats

RAIZ = Path(__file__).resolve().parents[1]
DDL = """
CREATE TABLE IF NOT EXISTS raca_cor (id_raca_cor INTEGER PRIMARY KEY, descricao TEXT);
CREATE TABLE IF NOT EXISTS orientacao_sexual (id_orientacao_sexual INTEGER PRIMARY KEY, descricao TEXT);
CREATE TABLE IF NOT EXISTS identidade_genero (id_identidade_genero INTEGER PRIMARY KEY, descricao TEXT);
CREATE TABLE IF NOT EXISTS deficiencia (id_deficiencia INTEGER PRIMARY KEY, descricao TEXT);
CREATE TABLE IF NOT EXISTS equipe (id_equipe TEXT PRIMARY KEY, nome TEXT);
CREATE TABLE IF NOT EXISTS microarea (id_microarea INTEGER PRIMARY KEY, codigo INTEGER, id_equipe TEXT REFERENCES equipe);
CREATE TABLE IF NOT EXISTS profissional (id_profissional INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT,
    id_equipe TEXT REFERENCES equipe, UNIQUE(nome, id_equipe));
CREATE TABLE IF NOT EXISTS pessoa (id_pessoa INTEGER PRIMARY KEY AUTOINCREMENT,
    id_raca_cor INTEGER NOT NULL REFERENCES raca_cor,
    id_orientacao_sexual INTEGER REFERENCES orientacao_sexual,   -- NULL = não deseja informar
    id_identidade_genero INTEGER REFERENCES identidade_genero,   -- NULL = não deseja informar
    id_microarea INTEGER NOT NULL REFERENCES microarea,
    id_profissional INTEGER REFERENCES profissional, data_coleta TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS pessoa_deficiencia (id_pessoa INTEGER REFERENCES pessoa,
    id_deficiencia INTEGER REFERENCES deficiencia, PRIMARY KEY (id_pessoa, id_deficiencia));
"""


def abre_banco(saida: Path) -> sqlite3.Connection:
    con = sqlite3.connect(saida / "preenchimento.db")
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(DDL)
    dom = json.loads((RAIZ / "dados" / "dominios.json").read_text(encoding="utf-8"))
    for tab, chave, col in (("raca_cor", "dom_raca_cor", "id_raca_cor"),
                            ("orientacao_sexual", "dom_orientacao_sexual", "id_orientacao_sexual"),
                            ("identidade_genero", "dom_identidade_genero", "id_identidade_genero"),
                            ("deficiencia", "dom_tipo_deficiencia", "id_deficiencia")):
        con.executemany(f"INSERT OR IGNORE INTO {tab} ({col}, descricao) VALUES (?, ?)", dom[chave])
    con.commit()
    return con


def _sincroniza_estrutura(con, saida: Path, D: dict):
    eq = D["equipe"][["ine", "nome_equipe"]].astype(str)
    con.executemany("INSERT OR IGNORE INTO equipe (id_equipe, nome) VALUES (?, ?)", eq.values.tolist())
    ma = pd.read_csv(saida / "nucleo" / "microarea.csv", dtype=str)
    ma["ine"] = ma["ine"].str.zfill(10)
    con.executemany("INSERT OR IGNORE INTO microarea (id_microarea, codigo, id_equipe) VALUES (?, ?, ?)",
                    [(int(a), int(c), i) for a, i, c in zip(ma["id_microarea"], ma["ine"], ma["codigo_microarea"])])
    con.commit()


def preenchimento_virtual(D: dict, saida: Path):
    st.markdown("# Preenchimento Virtual")
    st.caption("Simula o formulário: cada envio é UMA pessoa que declara tudo ao mesmo tempo. Fica num banco relacional "
               "(pessoa + tabelas de domínio + deficiência N:N) e alimenta o cruzamento abaixo.")
    con = abre_banco(saida)
    _sincroniza_estrutura(con, saida, D)
    dom = {t: pd.read_sql(f"SELECT * FROM {t}", con) for t in ("raca_cor", "orientacao_sexual", "identidade_genero", "deficiencia")}
    eq = pd.read_sql("SELECT e.id_equipe, e.nome FROM equipe e JOIN microarea m ON m.id_equipe = e.id_equipe "
                     "GROUP BY e.id_equipe ORDER BY e.nome", con)
    esq, dir_ = st.columns([1, 1.2], gap="large")
    with esq:
        st.markdown("##### Novo cadastro")
        nome_eq = st.selectbox("Equipe que fez a coleta", eq["nome"], key="f_eq")
        id_eq = eq.loc[eq["nome"] == nome_eq, "id_equipe"].iloc[0]
        mas = pd.read_sql("SELECT id_microarea, codigo FROM microarea WHERE id_equipe = ? ORDER BY codigo", con, params=(id_eq,))
        with st.form("formulario", clear_on_submit=True):
            prof = st.text_input("Profissional (nome)", placeholder="opcional")
            micro = st.selectbox("Microárea", mas["codigo"], format_func=lambda c: f"Microárea {int(c):02d}")
            raca = st.selectbox("Raça/cor", dom["raca_cor"]["descricao"])
            q_os = st.radio("Deseja informar a orientação sexual?", ["Não", "Sim"], horizontal=True)
            os_ = st.selectbox("Orientação sexual (se Sim)", dom["orientacao_sexual"]["descricao"])
            q_ig = st.radio("Deseja informar a identidade de gênero?", ["Não", "Sim"], horizontal=True)
            ig = st.selectbox("Identidade de gênero (se Sim)", dom["identidade_genero"]["descricao"])
            defs = st.multiselect("Deficiência (pode marcar mais de uma)", dom["deficiencia"]["descricao"])
            enviar = st.form_submit_button("Salvar cadastro", type="primary")
        if enviar:
            f = lambda t, c, v: int(dom[t].loc[dom[t]["descricao"] == v, c].iloc[0])   # noqa: E731
            idp = None
            if prof.strip():
                con.execute("INSERT OR IGNORE INTO profissional (nome, id_equipe) VALUES (?, ?)", (prof.strip(), id_eq))
                idp = con.execute("SELECT id_profissional FROM profissional WHERE nome=? AND id_equipe=?",
                                  (prof.strip(), id_eq)).fetchone()[0]
            cur = con.execute(
                "INSERT INTO pessoa (id_raca_cor, id_orientacao_sexual, id_identidade_genero, id_microarea, id_profissional, data_coleta) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (f("raca_cor", "id_raca_cor", raca),
                 f("orientacao_sexual", "id_orientacao_sexual", os_) if q_os == "Sim" else None,
                 f("identidade_genero", "id_identidade_genero", ig) if q_ig == "Sim" else None,
                 int(mas.loc[mas["codigo"] == micro, "id_microarea"].iloc[0]), idp, datetime.now().isoformat(timespec="seconds")))
            con.executemany("INSERT INTO pessoa_deficiencia VALUES (?, ?)",
                            [(cur.lastrowid, f("deficiencia", "id_deficiencia", x)) for x in defs])
            con.commit()
            st.success(f"Cadastro nº {cur.lastrowid} salvo.")
        if st.button("Gerar 200 cadastros de exemplo"):
            rng = np.random.default_rng(len(pd.read_sql("SELECT 1 FROM pessoa", con)) + 1)
            ids_ma = pd.read_sql("SELECT id_microarea FROM microarea", con)["id_microarea"].values
            for _ in range(200):
                cur = con.execute(
                    "INSERT INTO pessoa (id_raca_cor, id_orientacao_sexual, id_identidade_genero, id_microarea, data_coleta) VALUES (?,?,?,?,?)",
                    (int(rng.choice(dom["raca_cor"]["id_raca_cor"], p=[.35, .1, .5, .03, .02])),
                     int(rng.choice(dom["orientacao_sexual"]["id_orientacao_sexual"])) if rng.random() < .4 else None,
                     int(rng.choice(dom["identidade_genero"]["id_identidade_genero"])) if rng.random() < .4 else None,
                     int(rng.choice(ids_ma)), datetime.now().isoformat(timespec="seconds")))
                for x in dom["deficiencia"]["id_deficiencia"][rng.random(len(dom["deficiencia"])) < .05]:
                    con.execute("INSERT INTO pessoa_deficiencia VALUES (?,?)", (cur.lastrowid, int(x)))
            con.commit()
            st.rerun()
    with dir_:
        n = con.execute("SELECT COUNT(*) FROM pessoa").fetchone()[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("Pessoas cadastradas", n)
        c2.metric("Com deficiência", con.execute("SELECT COUNT(DISTINCT id_pessoa) FROM pessoa_deficiencia").fetchone()[0])
        c3.metric("Informaram orientação", con.execute("SELECT COUNT(*) FROM pessoa WHERE id_orientacao_sexual IS NOT NULL").fetchone()[0])
        if n == 0:
            st.info("Preencha o formulário ou gere cadastros de exemplo para ver o cruzamento.")
        else:
            base = pd.read_sql(
                "SELECT p.id_pessoa, r.descricao AS raca_cor, COALESCE(o.descricao,'(não informou)') AS orientacao, "
                "COALESCE(i.descricao,'(não informou)') AS identidade, m.codigo AS microarea, e.nome AS equipe, "
                "(SELECT COUNT(*) FROM pessoa_deficiencia d WHERE d.id_pessoa = p.id_pessoa) AS n_deficiencias, p.data_coleta "
                "FROM pessoa p JOIN raca_cor r USING (id_raca_cor) JOIN microarea m USING (id_microarea) "
                "JOIN equipe e ON e.id_equipe = m.id_equipe LEFT JOIN orientacao_sexual o USING (id_orientacao_sexual) "
                "LEFT JOIN identidade_genero i USING (id_identidade_genero)", con)
            st.markdown("##### Cruzamento")
            a, b = st.columns(2)
            ev = {"raca_cor": "Raça/cor", "orientacao": "Orientação", "identidade": "Identidade de gênero", "microarea": "Microárea"}
            x = a.selectbox("Linhas", list(ev), format_func=ev.get, index=0)
            y = b.selectbox("Colunas", list(ev), format_func=ev.get, index=2)
            if x == y:
                st.warning("Escolha campos diferentes.")
            else:
                ct = base.groupby([x, y]).size().reset_index(name="pessoas")
                st.altair_chart(alt.Chart(ct).mark_rect().encode(
                    x=alt.X(f"{y}:N", title=ev[y]), y=alt.Y(f"{x}:N", title=ev[x]),
                    color=alt.Color("pessoas:Q", scale=alt.Scale(scheme="blues")),
                    tooltip=[x, y, "pessoas"]).properties(height=260), width="stretch")
            st.markdown("##### Últimos cadastros")
            st.dataframe(base.sort_values("id_pessoa", ascending=False).head(15), hide_index=True, width="stretch")
            st.download_button("Baixar cadastros (CSV)", base.to_csv(index=False).encode("utf-8"), "cadastros_formulario.csv", "text/csv")
    con.close()


# ------------------------------------------------------------------ SQL e Inferência
CONSULTAS = {
    "Ranking de equipes por % de Sim (RANK)": (
        "SELECT RANK() OVER (ORDER BY n_os_sim_pct) AS posicao, ine, id_ds, ROUND(n_os_sim_pct*100,1) AS pct_sim\n"
        "FROM monitoramento_equipe WHERE n_os_sim_pct IS NOT NULL ORDER BY posicao LIMIT 15", "ine", "pct_sim"),
    "Média e desvio padrão do % de Sim por DS": (
        "SELECT id_ds, COUNT(*) AS equipes, ROUND(AVG(n_os_sim_pct)*100,1) AS media_pct,\n"
        "       ROUND(SQRT(AVG(n_os_sim_pct*n_os_sim_pct)-AVG(n_os_sim_pct)*AVG(n_os_sim_pct))*100,1) AS desvio_pct\n"
        "FROM monitoramento_equipe WHERE n_os_sim_pct IS NOT NULL GROUP BY id_ds ORDER BY id_ds", "id_ds", "media_pct"),
    "Evolução do % de Sim por período (LAG)": (
        "SELECT periodo, pct_sim, ROUND(pct_sim - LAG(pct_sim) OVER (ORDER BY periodo), 2) AS variacao_pp FROM (\n"
        "  SELECT periodo, ROUND(AVG(prop_sim_os)*100,2) AS pct_sim FROM fato_painel_ml GROUP BY periodo) ORDER BY periodo",
        "periodo", "pct_sim"),
    "Equipes em alerta (Sim < 15%) por DS": (
        "SELECT id_ds, SUM(CASE WHEN n_os_sim_pct < 0.15 THEN 1 ELSE 0 END) AS em_alerta, COUNT(*) AS equipes\n"
        "FROM monitoramento_equipe WHERE n_os_sim_pct IS NOT NULL GROUP BY id_ds ORDER BY id_ds", "id_ds", "em_alerta"),
    "Formulário: pessoas por raça/cor × identidade": (
        "SELECT r.descricao AS raca_cor, COALESCE(i.descricao,'(não informou)') AS identidade, COUNT(*) AS pessoas\n"
        "FROM form.pessoa p JOIN form.raca_cor r USING (id_raca_cor)\n"
        "LEFT JOIN form.identidade_genero i USING (id_identidade_genero) GROUP BY 1, 2 ORDER BY pessoas DESC", "raca_cor", "pessoas"),
    "Formulário: pessoas trans e negras por microárea": (
        "SELECT m.codigo AS microarea, COUNT(*) AS pessoas\n"
        "FROM form.pessoa p JOIN form.microarea m USING (id_microarea)\n"
        "WHERE p.id_identidade_genero IN (149,150,156) AND p.id_raca_cor IN (2,4) GROUP BY 1 ORDER BY pessoas DESC", "microarea", "pessoas"),
}


def _conn_consultas(saida: Path, D: dict):
    con = sqlite3.connect(":memory:")
    D["monitoramento_equipe"].to_sql("monitoramento_equipe", con, index=False)
    D["fato_painel_ml"].to_sql("fato_painel_ml", con, index=False)
    abre_banco(saida).close()
    con.execute("ATTACH DATABASE ? AS form", (str(saida / "preenchimento.db"),))
    return con


def _chi2_equipes(D: dict) -> pd.DataFrame:
    f = D["fato_indicador_equipe"]
    f = f[(f["marcador"] == "RACA_COR") & (f["competencia"] == f["competencia"].max())]
    t = f.pivot_table(index=["ine", "id_ds"], columns="categoria", values="n", aggfunc="sum", fill_value=0)
    t = t.loc[t.sum(axis=1) >= 30]
    esp = t.groupby(level="id_ds").transform("sum")
    esp = esp.div(esp.sum(axis=1), axis=0).mul(t.sum(axis=1), axis=0)     # proporção do DS × total da equipe
    ok = esp.gt(0).all(axis=1)
    t, esp = t[ok], esp[ok]
    chi = ((t - esp) ** 2 / esp).sum(axis=1)
    k = t.shape[1]
    out = pd.DataFrame({"chi2": chi, "gl": k - 1, "n": t.sum(axis=1)})
    out["p_valor"] = 1 - stats.chi2.cdf(out["chi2"], k - 1)
    out["cramer_v"] = np.sqrt(out["chi2"] / (out["n"] * (k - 1)))
    return out.reset_index()


def sql_inferencia(D: dict, saida: Path, cores: dict):
    st.markdown("# SQL e Inferência")
    t1, t2, t3 = st.tabs(["Consultas SQL", "KPI χ² por equipe", "Inferência × referências"])
    with t1:
        nome = st.selectbox("Consulta", list(CONSULTAS))
        sql, x, y = CONSULTAS[nome]
        st.code(sql, language="sql")
        con = _conn_consultas(saida, D)
        try:
            df = pd.read_sql(sql, con)
            st.dataframe(df, hide_index=True, width="stretch")
            if len(df) and y in df:
                st.altair_chart(alt.Chart(df).mark_bar(color=cores[1]).encode(
                    x=alt.X(f"{x}:N", sort=None, title=x), y=alt.Y(f"{y}:Q", title=y), tooltip=list(df.columns)).properties(height=240),
                    width="stretch")
            elif nome.startswith("Formulário"):
                st.info("Sem dados no formulário ainda: use a aba Preenchimento Virtual para cadastrar ou gerar exemplos.")
        except Exception as e:   # noqa: BLE001
            st.error(f"Erro na consulta: {e}")
        con.close()
        with st.expander("Consulta livre (somente leitura)"):
            livre = st.text_area("SQL", "SELECT id_ds, COUNT(*) AS equipes FROM monitoramento_equipe GROUP BY id_ds")
            if livre.strip().lower().startswith("select"):
                con = _conn_consultas(saida, D)
                try:
                    st.dataframe(pd.read_sql(livre, con), hide_index=True, width="stretch")
                except Exception as e:   # noqa: BLE001
                    st.error(str(e))
                con.close()
            else:
                st.caption("Só consultas SELECT são executadas.")
    with t2:
        st.caption("Para cada equipe: a distribuição de raça/cor combina com a do seu Distrito Sanitário? "
                   "H0: a equipe tem a mesma distribuição do DS (teste χ² de aderência, α = 5%). Último período; equipes com ≥ 30 cadastros. "
                   "Como n é grande, usamos também V de Cramér (tamanho do efeito): V ≥ 0,10 = diferença relevante.")
        q = _chi2_equipes(D)
        q["Rejeita H0 (p<5%)"] = q["p_valor"] < 0.05
        q["Relevante (V≥0,10)"] = q["cramer_v"] >= 0.10
        a, b, c = st.columns(3)
        a.metric("Equipes avaliadas", len(q))
        b.metric("Rejeitam H0", f"{q['Rejeita H0 (p<5%)'].mean():.0%}")
        c.metric("Diferença relevante", f"{q['Relevante (V≥0,10)'].mean():.0%}")
        r = q.groupby("id_ds").agg(rejeitam=("Rejeita H0 (p<5%)", "mean"), relevantes=("Relevante (V≥0,10)", "mean")).reset_index()
        r = r.melt("id_ds", var_name="Critério", value_name="Proporção de equipes")
        r["DS"] = "DS " + r["id_ds"].astype(str)
        st.altair_chart(alt.Chart(r).mark_bar().encode(
            x=alt.X("DS:N", title=None), xOffset="Critério:N", y=alt.Y("Proporção de equipes:Q", axis=alt.Axis(format="%")),
            color=alt.Color("Critério:N", scale=alt.Scale(range=[cores[1], cores[2]]), legend=alt.Legend(orient="bottom", title=None)),
            tooltip=["DS", "Critério", alt.Tooltip("Proporção de equipes:Q", format=".0%")]).properties(height=260), width="stretch")
        st.markdown("##### Equipes que mais se afastam do seu DS")
        top = q.sort_values("cramer_v", ascending=False).head(15).merge(D["equipe"][["ine", "nome_equipe"]], on="ine", how="left")
        st.dataframe(top[["nome_equipe", "id_ds", "n", "chi2", "p_valor", "cramer_v"]], hide_index=True, width="stretch", column_config={
            "chi2": st.column_config.NumberColumn("χ²", format="%.1f"), "p_valor": st.column_config.NumberColumn("p-valor", format="%.4f"),
            "cramer_v": st.column_config.NumberColumn("V de Cramér", format="%.3f")})
    with t3:
        for cand in (saida / "relatorios" / "inferencia_referencias.csv", RAIZ / "docs" / "inferencia_referencias.csv"):
            if cand.exists():
                d = pd.read_csv(cand)
                break
        else:
            st.info("Rode `python -m aps_sintetico.valida_referencia --saida saida/base`.")
            return
        st.caption("Estimativa sintética × valor de referência, com IC 95% e a faixa de tolerância (proporções).")
        d = d[d["estatistica_referencia"] == "proporção"].copy()
        d["grupo"] = np.select([d["variavel"].str.contains("cobertura"), d["variavel"].str.contains("raça|negra"),
                                d["variavel"].str.contains("deficiência"), d["variavel"].str.startswith("sexo"),
                                d["variavel"].str.startswith("linha 3")],
                               ["Cobertura por DS", "Raça/cor", "Deficiência", "Sexo × idade", "Planilha (linha 3)"], "Orientação/identidade")
        g = st.selectbox("Grupo", sorted(d["grupo"].unique()))
        d = d[d["grupo"] == g]
        d["dif"] = (d["estimativa_sintetica"] - d["valor_referencia"]) * 100
        d["lo"] = (d["ic95_inf"] - d["valor_referencia"]) * 100
        d["hi"] = (d["ic95_sup"] - d["valor_referencia"]) * 100
        d["tol"] = d["tolerancia"] * 100
        base = alt.Chart(d).encode(y=alt.Y("variavel:N", title=None, sort=None, axis=alt.Axis(labelLimit=260, labelOverlap=False)))
        d["tol_neg"] = -d["tol"]
        graf = (base.mark_rule(color="#888").encode(x=alt.X("lo:Q", title="Diferença para a referência (p.p.)"), x2="hi:Q") +
                base.mark_circle(size=70, color=cores[1]).encode(x="dif:Q", tooltip=["variavel", alt.Tooltip("dif:Q", format=".2f"),
                                                                                    alt.Tooltip("p_valor:Q", format=".4f"), "veredito"]) +
                base.mark_tick(color="#d03b3b", thickness=2, size=14).encode(x="tol:Q") +
                base.mark_tick(color="#d03b3b", thickness=2, size=14).encode(x="tol_neg:Q"))
        st.altair_chart(graf.properties(height=max(160, 24 * len(d))), width="stretch")
        st.caption("Ponto = diferença observada; linha cinza = IC 95%; marcas vermelhas = tolerância. Dentro das marcas = aceito.")
        st.dataframe(d[["variavel", "valor_referencia", "estimativa_sintetica", "n", "p_valor", "decisao_teste_5pct", "veredito"]],
                     hide_index=True, width="stretch")
