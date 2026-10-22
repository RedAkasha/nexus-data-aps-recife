"""Etapa 8 – validação da base gerada.

1. Calibração (sem banco): cada marginal gerada contra a meta oficial ou a premissa declarada,
   com tolerância de equivalência max(1 p.p., 3·EP) para proporções e 3·sqrt(esperado) para
   contagens de Poisson (Plano metodológico, seção 6).
2. Integridade (banco): a visão analitica.vw_validacao_carga deve sair vazia.
3. Qualidade (banco): regras RQ da visão vw_qualidade_registro contra o gabarito
   (controle_defeito), com precisão e sensibilidade por regra.
4. Reprodução da planilha da SESAU: linha 3 (adultos e crianças) calculada em Python a partir
   dos CSV e, se houver banco, pela visão vw_monitoramento_usf (as duas têm de coincidir).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import parametros as P
from .config import carrega as carrega_cfg
from .populacao import raca_por_ds

RQ_DEFEITO = {"RQ01": [4], "RQ02": [6], "RQ03": [3, 2], "RQ05": [1], "RQ06": [5], "RQ07": [11, 12],
              "RQ10": [9], "RQ11": [13], "RQ12": [8]}


def le_csv(caminho: Path) -> pd.DataFrame:
    return pd.read_csv(caminho, dtype=str, na_values=[r"\N"], keep_default_na=False)


def le_saida(saida: Path) -> dict:
    saida = Path(saida)
    out = {"cfg": carrega_cfg(saida / "config_usada.yaml")}
    for t in ("cidadao", "cadastro_individual", "equipe_ref", "familia", "domicilio", "controle_defeito"):
        p = saida / "nucleo" / f"{t}.csv"
        if p.exists():
            out[t] = le_csv(p)
    for p in (saida / "verdade").glob("*.parquet"):
        out[f"v_{p.stem}"] = pd.read_parquet(p)
    return out


# ------------------------------------------------------------------ versão vigente (Python)
def vigente(D: dict) -> pd.DataFrame:
    """Réplica de analitica.vw_cadastro_vigente sobre os CSV do núcleo."""
    cfg = D["cfg"]
    ci, c = D["cadastro_individual"], D["cidadao"]
    corte = pd.Timestamp(cfg.periodo.data_corte)
    v = ci[pd.to_datetime(ci["dt_cadastro"]) <= corte].copy()
    v = v.sort_values(["id_cidadao", "dt_cadastro", "dt_digitacao", "uuid"], ascending=False, kind="mergesort")
    v = v.drop_duplicates("id_cidadao", keep="first")
    nasc = pd.to_datetime(c.set_index("id_cidadao")["dt_nascimento"].reindex(v["id_cidadao"]).values)
    # idade completa (date_part('year', age(corte, nascimento)))
    aniv = (nasc.month > corte.month) | ((nasc.month == corte.month) & (nasc.day > corte.day))
    idade = corte.year - nasc.year - aniv.astype(int)
    v["idade_na_data_corte"] = idade
    v["crianca"] = idade < int(cfg.regra.idade_min_elegivel)
    rec = v["recusa_cadastro"] == "1"
    v["ativo"] = v["motivo_saida"].isna() & (bool(cfg.regra.recusa_conta_ativo) | ~rec)
    return v


def linha3(D: dict) -> pd.DataFrame:
    v = vigente(D)
    v = v[v["ativo"]]
    out = []
    for nome, g in (("adultos", v[~v["crianca"]]), ("criancas", v[v["crianca"]])):
        n = len(g)
        out.append({"grupo": nome, "n": n, "sim": (g["deseja_informar_os"] == "1").mean(),
                    "nao": (g["deseja_informar_os"] == "0").mean(), "ni": g["deseja_informar_os"].isna().mean()})
    return pd.DataFrame(out)


# ------------------------------------------------------------------ calibração
def _prop(nome, alvo, obtido, n, classe, nota=""):
    se = np.sqrt(max(alvo * (1 - alvo), 1e-12) / max(n, 1))
    tol = max(0.01, 3 * se)
    return {"verificacao": nome, "classe": classe, "alvo": alvo, "obtido": obtido, "n": int(n), "ep": se,
            "tolerancia": tol, "ok": bool(abs(obtido - alvo) <= tol), "nota": nota}


def _cont(nome, esperado, obtido, classe, nota=""):
    tol = 3 * np.sqrt(max(esperado, 1))
    return {"verificacao": nome, "classe": classe, "alvo": esperado, "obtido": obtido, "n": int(obtido),
            "ep": np.sqrt(max(esperado, 1)), "tolerancia": tol, "ok": bool(abs(obtido - esperado) <= tol),
            "nota": nota}


def calibracao(saida: Path) -> pd.DataFrame:
    D = le_saida(saida)
    cfg = D["cfg"]
    pes = D["v_pessoas"]
    R = []
    base = pes[pes["residente"] & ~pes["nasc_serie"]]
    todos = sorted(cfg.distritos) == list(range(1, 9))
    # 1. população por DS (TRS: erro de arredondamento apenas)
    est = P.estrutura()
    pop_b = P.bairros_censo()
    ds_b = est["bairro"].set_index("id_bairro")["id_ds"]
    alvo_ds = pop_b["pop"].groupby(ds_b.reindex(pop_b.index)).sum() * cfg.escala
    for d in cfg.distritos:
        R.append(_cont(f"população do DS {d}", float(alvo_ds[d]), int((base["ds"] == d).sum()), "A",
                       "Censo 2022 (SIDRA 9922/9923) × escala"))
    # 2. raça/cor por DS (estimador indireto + IPF) e homofilia
    pi_ds, _ = raca_por_ds(cfg)
    for d in cfg.distritos:
        g = base[base["ds"] == d]
        tot = pi_ds.loc[d]
        alvo = float((tot[2] + tot[4]) / tot.sum())     # margem do IPF DS × raça
        R.append(_prop(f"proporção negra no DS {d}", alvo, float(g["raca"].isin([2, 4]).mean()), len(g), "B",
                       "boletim SESAU 01/2025 + Censo (estimador indireto)"))
    # 3. sexo × faixa etária (municipal)
    if todos:
        t = P.pop_sexo_idade_raca()
        faixas = [(0, 14), (15, 29), (30, 59), (60, 104)]
        for s in (0, 1):
            for a, b in faixas:
                alvo = t[s, a:min(b, 100) + 1].sum() / t.sum()
                ob = ((base["sexo"] == s) & base["idade_ref"].between(a, b)).mean()
                R.append(_prop(f"sexo {s}, {a}-{b} anos", float(alvo), float(ob), len(base), "A", "Censo 2022 (SIDRA 9606)"))
        alvo_r = t.sum(axis=(0, 1)) / t.sum()
        for i, r in enumerate(P.RACAS):
            R.append(_prop(f"raça/cor {r} (municipal)", float(alvo_r[i]), float((base["raca"] == r).mean()), len(base),
                           "A", "Censo 2022 (SIDRA 9606)"))
    # 4. deficiência (2 anos ou mais) e tipos
    el = base[base["idade_ref"] >= 2]
    nota_def = "Censo 2022 (SIDRA 10125/10132), meta municipal" + ("" if todos else "; DS parciais")
    R.append(_prop("prevalência de deficiência (2+)", P.prev_deficiencia_total(),
                   float(el["def_funcional"].mean()), len(el), "A", nota_def))
    bits = {13: 1, 12: 2, 15: 4, 14: 8, 232: 16}
    for cod_, alvo in P.tipos_deficiencia().items():
        R.append(_prop(f"tipo de deficiência {cod_}", float(alvo), float(((el["def_bits"] & bits[cod_]) > 0).mean()),
                       len(el), "A", nota_def))
    # 5. orientação sexual e identidade de gênero (premissas declaradas)
    ad = base[base["idade_ref"] >= 18]
    a = cfg.atributos
    R.append(_prop("LGB+ entre adultos (18+)", float(a.lgb_pe), float(ad["lgb"].mean()), len(ad), "B",
                   "PNS 2019 (PE) com gradiente etário"))
    R.append(_prop("trans entre adultos", float(a.trans), float(ad["ig_true"].isin([149, 150, 156]).mean()),
                   len(ad), "B", "Spizzirri et al. 2021"))
    R.append(_prop("não binários entre adultos", float(a.nao_binario), float((ad["ig_true"] == 203).mean()),
                   len(ad), "B", "Spizzirri et al. 2021"))
    # 6. cobertura por DS
    diag = json.loads((Path(saida) / "verdade" / "diagnostico.json").read_text(encoding="utf-8"))
    cob = {int(k): v for k, v in diag["cobertura"]["cobertura_ds"].items()}
    perda = {int(k): v for k, v in diag["cobertura"].get("perda_rampa_ds", {}).items()}
    for d in cfg.distritos:
        g = base[base["ds"] == d]
        alvo = cob[d] * (1 - float(cfg.cobertura.omissao_morador)) * (1 - perda.get(d, 0.0))
        R.append(_prop(f"cobertura cadastral no DS {d}", alvo, float(g["cadastrado"].mean()), len(g), "B",
                       f"meta K (Tabela 4) × (1 − omissão) × (1 − rampa {perda.get(d, 0):.1%})"))
    # 7. linha 3 da planilha
    L = linha3(D).set_index("grupo")
    for grupo, chave in (("adultos", "linha3_adultos"), ("criancas", "linha3_criancas")):
        for k in ("sim", "nao", "ni"):
            R.append(_prop(f"linha 3, {grupo}: {k}", float(cfg.registro[chave][k]), float(L.loc[grupo, k]),
                           L.loc[grupo, "n"], "A", "planilha SESAU (data de corte)"))
    # 8. nascimentos por ano e raça da mãe (boletim × escala × DS gerados)
    nas = D["v_nascimentos"]
    meses = (pd.Timestamp(cfg.periodo.data_corte) - pd.Timestamp(cfg.periodo.inicio)).days / 365.25
    alvo_n = P.nascimentos_ds().loc[list(cfg.distritos)].sum() * cfg.escala * meses
    negra = nas["raca_mae"].isin([2, 4])
    R.append(_cont("nascimentos, mãe negra (período)", float(alvo_n["negra"]), int(negra.sum()), "A",
                   "boletim SESAU 01/2025, Tabela 3"))
    R.append(_cont("nascimentos, mãe não negra (período)", float(alvo_n["nao_negra"]), int((~negra).sum()), "A",
                   "boletim SESAU 01/2025, Tabela 3"))
    # 9. óbitos (período): taxas por idade × raça (boletim ÷ Censo) aplicadas à população gerada
    from .dinamica import _taxas_obito
    tx, _ = _taxas_obito(cfg)
    g = np.where(base["raca"].isin([2, 4]).values, 0, 1)
    idade = np.clip(base["idade_ref"].values + 2, 0, 104)          # idade no meio do período
    alvo_o = float((1 - np.exp(-tx[g, idade] * meses)).sum())
    morte = base["dt_obito"].notna()
    R.append(_cont("óbitos de residentes (período)", alvo_o, int(morte.sum()), "A",
                   "boletim SESAU 01/2025, Tabela 4, padronização indireta"))

    df = pd.DataFrame(R)
    return df


# ------------------------------------------------------------------ banco
def integridade(dsn=None) -> pd.DataFrame:
    from .carga import consulta
    return consulta("SELECT regra, tabela, COUNT(*) AS n FROM analitica.vw_validacao_carga GROUP BY 1, 2 ORDER BY 1",
                    dsn)


def qualidade_vs_gabarito(dsn=None) -> pd.DataFrame:
    from .carga import consulta
    rq = consulta("SELECT regra, tabela, id_registro FROM analitica.vw_qualidade_registro", dsn)
    gab = consulta("SELECT tipo_defeito, tabela, id_registro FROM nucleo.controle_defeito", dsn)
    out = []
    for regra, tipos in RQ_DEFEITO.items():
        a = set(map(tuple, rq.loc[rq["regra"] == regra, ["tabela", "id_registro"]].values))
        g = set(map(tuple, gab.loc[gab["tipo_defeito"].isin(tipos), ["tabela", "id_registro"]].values))
        inter = len(a & g)
        out.append({"regra": regra, "defeitos": ",".join(map(str, tipos)), "n_regra": len(a), "n_gabarito": len(g),
                    "acertos": inter, "precisao": inter / len(a) if a else np.nan,
                    "sensibilidade": inter / len(g) if g else np.nan})
    return pd.DataFrame(out)


def planilha_sql(dsn=None) -> pd.DataFrame:
    from .carga import consulta
    return consulta("""SELECT SUM(j_dado_real) AS adultos, SUM(m_os_sim_dado_real) AS sim,
                              SUM(q_os_nao_dado_real) AS nao, SUM(u_os_ni_dado_real) AS ni,
                              SUM(i_criancas) AS criancas, SUM(l_os_sim_crianca) AS sim_criancas
                         FROM analitica.vw_monitoramento_usf""", dsn)


def relatorio(saida: Path, dsn=None, com_banco: bool = True) -> Path:
    saida = Path(saida)
    rel = saida / "relatorios"
    rel.mkdir(parents=True, exist_ok=True)
    cal = calibracao(saida)
    cal.to_csv(rel / "calibracao.csv", index=False)
    linhas = ["# Relatório de validação da base sintética", "",
              f"Saída: `{saida.name}` · aprovadas {int(cal['ok'].sum())} de {len(cal)} verificações de calibração "
              "(tolerância de equivalência max(1 p.p., 3·EP); contagens: 3·√esperado).", "",
              "## 1. Calibração", "", _md(cal, ["verificacao", "classe", "alvo", "obtido", "n", "tolerancia", "ok", "nota"]),
              ""]
    if com_banco:
        integ = integridade(dsn)
        linhas += ["## 2. Integridade da carga (VC01–VC15)", "",
                   "Nenhuma violação." if integ.empty else _md(integ, list(integ.columns)), ""]
        q = qualidade_vs_gabarito(dsn)
        q.to_csv(rel / "qualidade_vs_gabarito.csv", index=False)
        linhas += ["## 3. Regras de qualidade × gabarito", "",
                   "A RQ olha a versão vigente ou o cadastro inteiro conforme a regra; o gabarito marca a versão "
                   "em que o defeito nasceu. Sensibilidade abaixo de 1 em RQ02/RQ06/RQ07 é esperada (versões antigas "
                   "não vigentes); precisão abaixo de 1 aponta falso-positivo da regra.", "",
                   _md(q, list(q.columns)), ""]
        ps = planilha_sql(dsn)
        L = linha3(le_saida(saida)).set_index("grupo")
        n_ad = int(ps.at[0, "adultos"])
        iguais = n_ad == int(L.loc["adultos", "n"]) and int(ps.at[0, "sim"]) == round(L.loc["adultos", "sim"] * n_ad)
        linhas += ["## 4. Planilha da SESAU: SQL × Python", "",
                   f"Adultos (dado real): SQL {n_ad}, Python {int(L.loc['adultos', 'n'])}; Sim: SQL {int(ps.at[0, 'sim'])}, "
                   f"Python {round(L.loc['adultos', 'sim'] * L.loc['adultos', 'n'])} → "
                   f"{'coincidem' if iguais else 'DIVERGEM'}.", ""]
    p = rel / "validacao.md"
    p.write_text("\n".join(linhas), encoding="utf-8")
    return p


def _md(df: pd.DataFrame, cols: list) -> str:
    def f(x):
        if isinstance(x, (float, np.floating)):
            return f"{x:.4f}"
        if isinstance(x, (bool, np.bool_)):
            return "sim" if x else "**não**"
        return str(x)
    cab = "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols)
    return cab + "\n" + "\n".join("| " + " | ".join(f(r[c]) for c in cols) + " |" for _, r in df.iterrows())
