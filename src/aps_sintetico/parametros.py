"""Leitura dos parâmetros oficiais (Etapa 5) e complementares, já no formato do gerador.

Os CSV seguem o formato longo de ``analitica.ref_parametro_oficial``. A coluna
``categoria`` traz dimensões ``chave=valor`` separadas por ``;``. Os códigos de cor
ou raça e de deficiência já são os do e-SUS. Sexo: H (homens) e M (mulheres) no
Censo; no gerador, 0 = masculino e 1 = feminino, como no LEDI.
"""
from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import pandas as pd

from .config import RAIZ

DADOS = RAIZ / "dados"
RACAS = np.array([1, 2, 3, 4, 5])          # branca, preta, amarela, parda, indígena (LEDI = IBGE)
NEGRO = np.array([False, True, False, True, False])
SEXO_CENSO = {"H": 0, "M": 1}
IDADE_MAX = 100                             # índice 100 = "100+"
MUNICIPIO = "2611606"


def _parse_cat(cat: str) -> dict:
    if cat in ("T", ""):
        return {}
    return dict(kv.split("=", 1) for kv in cat.split(";") if "=" in kv)


@lru_cache(maxsize=1)
def todos() -> pd.DataFrame:
    """Todos os parâmetros (Etapa 5 + complementares) num só DataFrame."""
    arquivos = sorted((DADOS / "parametros").glob("*.csv")) + \
        sorted((DADOS / "parametros_complementares").glob("*.csv"))
    df = pd.concat([pd.read_csv(a, dtype=str, keep_default_na=False) for a in arquivos], ignore_index=True)
    df["valor_num"] = pd.to_numeric(df["valor"], errors="coerce")
    return df


def seleciona(tabela: str | None = None, variavel: str | None = None, nivel: str | None = None,
              cd: str | None = None) -> pd.DataFrame:
    df = todos()
    m = pd.Series(True, index=df.index)
    if tabela:
        m &= df["tabela_fonte"] == tabela
    if variavel:
        m &= df["variavel"] == variavel
    if nivel:
        m &= df["nivel"] == nivel
    if cd:
        m &= df["cd_territorio"] == cd
    sub = df[m].copy()
    cats = sub["categoria"].map(_parse_cat)
    chaves = sorted({k for c in cats for k in c})
    for k in chaves:
        sub[k] = cats.map(lambda c, k=k: c.get(k, "T"))
    return sub


def valor(tabela: str, variavel: str, categoria: str = "T", nivel: str = "municipio",
          cd: str = MUNICIPIO) -> float:
    df = todos()
    m = (df["tabela_fonte"] == tabela) & (df["variavel"] == variavel) & (df["categoria"] == categoria) \
        & (df["nivel"] == nivel) & (df["cd_territorio"] == cd)
    if m.sum() != 1:
        raise KeyError(f"parâmetro não encontrado ou ambíguo: {tabela} {variavel} {categoria} {nivel} {cd}")
    return float(df.loc[m, "valor_num"].iloc[0])


def _idade_simples(rotulo: str) -> int | None:
    if rotulo == "100+":
        return IDADE_MAX
    return int(rotulo) if rotulo.isdigit() else None


# ---------------------------------------------------------------------- Censo 2022
@lru_cache(maxsize=1)
def pop_sexo_idade_raca() -> np.ndarray:
    """Semente do IPF: residentes por sexo x idade simples (0-100+) x cor ou raça (SIDRA 9606)."""
    s = seleciona("SIDRA 9606", "pop_residente")
    s = s[(s["raca"] != "T") & (s["raca"] != "SD") & (s["sexo"] != "T")]
    s = s[s["idade"].map(lambda r: _idade_simples(r) is not None)]
    arr = np.zeros((2, IDADE_MAX + 1, 5))
    for _, r in s.iterrows():
        arr[SEXO_CENSO[r["sexo"]], _idade_simples(r["idade"]), int(np.where(RACAS == int(r["raca"]))[0][0])] = \
            r["valor_num"]
    return arr


@lru_cache(maxsize=1)
def bairros_censo() -> pd.DataFrame:
    """População, domicílios e média de moradores dos 94 bairros (SIDRA 9922/9923)."""
    s = seleciona("SIDRA 9922/9923", nivel="bairro")
    p = s.pivot_table(index="cd_territorio", columns="variavel", values="valor_num", aggfunc="first")
    p.index = p.index.str[-3:].astype(int)
    p.index.name = "id_bairro"
    return p[["pop_residente", "dom_ocupados", "media_moradores_dpp"]].rename(
        columns={"pop_residente": "pop", "dom_ocupados": "dom", "media_moradores_dpp": "media"})


def _faixa(rotulo: str) -> tuple[int, int]:
    if rotulo.endswith("+"):
        return int(rotulo[:-1]), IDADE_MAX
    a, b = rotulo.split("-")
    return int(a), int(b)


@lru_cache(maxsize=1)
def deficiencia_sexo_idade() -> pd.DataFrame:
    """Prevalência de deficiência (2+ anos) por sexo e faixa fina (SIDRA 10125)."""
    s = seleciona("SIDRA 10125", "prev_pcd")
    finas = ["2-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-54",
             "55-59", "60-64", "65-69", "70-74", "75-79", "80-84", "85-89", "90-94", "95-99", "100+"]
    s = s[(s["sexo"] != "T") & s["idade"].isin(finas)]
    out = pd.DataFrame({"sexo": s["sexo"].map(SEXO_CENSO), "faixa": s["idade"], "prev": s["valor_num"]})
    out[["ini", "fim"]] = out["faixa"].map(_faixa).tolist()
    return out.reset_index(drop=True)


@lru_cache(maxsize=1)
def deficiencia_raca() -> dict[int, float]:
    s = seleciona("SIDRA 10132", "prev_pcd")
    s = s[s["raca"] != "T"]
    return {int(r): float(v) for r, v in zip(s["raca"], s["valor_num"])}


@lru_cache(maxsize=1)
def prev_deficiencia_total() -> float:
    return valor("SIDRA 10132", "prev_pcd", "raca=T")


@lru_cache(maxsize=1)
def tipos_deficiencia() -> dict[int, float]:
    """Prevalência (2+) dos tipos do e-SUS (Tabela 7 do plano; premissas_gerador.csv)."""
    s = seleciona(variavel="prev_tipo_deficiencia_esus")
    return {int(t): float(v) for t, v in zip(s["tipo"], s["valor_num"])}


@lru_cache(maxsize=1)
def autismo_sexo_idade() -> pd.DataFrame:
    s = seleciona("SIDRA 10145", "prev_autismo")
    s = s[(s["sexo"] != "T") & (s["idade"] != "T")]
    out = pd.DataFrame({"sexo": s["sexo"].map(SEXO_CENSO), "faixa": s["idade"], "prev": s["valor_num"]})
    out[["ini", "fim"]] = out["faixa"].map(_faixa).tolist()
    return out.reset_index(drop=True)


FAIXAS_INSTR = ["18-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-54", "55-59", "60-64",
                "65-69", "70-74", "75-79", "80+"]


@lru_cache(maxsize=1)
def instrucao() -> np.ndarray:
    """Pessoas 18+ por nível de instrução (1-4) x faixa x sexo x raça (SIDRA 10061)."""
    s = seleciona("SIDRA 10061", "pessoas_18mais")
    s = s[(s["instr"] != "T") & (s["sexo"] != "T") & (s["raca"] != "T") & s["idade"].isin(FAIXAS_INSTR)]
    arr = np.zeros((4, len(FAIXAS_INSTR), 2, 5))
    for _, r in s.iterrows():
        arr[int(r["instr"]) - 1, FAIXAS_INSTR.index(r["idade"]), SEXO_CENSO[r["sexo"]],
            int(np.where(RACAS == int(r["raca"]))[0][0])] = r["valor_num"]
    return arr


RENDA_CAT = ["sem", "ate0.25", "0.25-0.5", "0.5-1", "1-2", "2-3", "3-5", "5-10", "10-15", "15-20", "20+"]
RENDA_LIM = [(0, 0), (0.0, 0.25), (0.25, 0.5), (0.5, 1), (1, 2), (2, 3), (3, 5), (5, 10), (10, 15), (15, 20), (20, 40)]


@lru_cache(maxsize=1)
def renda() -> np.ndarray:
    """Moradores por sexo x raça x rendimento domiciliar per capita em SM (SIDRA 10296)."""
    s = seleciona("SIDRA 10296", "moradores_dpp")
    s = s[(s["sexo"] != "T") & (s["raca"] != "T") & (s["renda_pc"] != "T")]
    arr = np.zeros((2, 5, len(RENDA_CAT)))
    for _, r in s.iterrows():
        arr[SEXO_CENSO[r["sexo"]], int(np.where(RACAS == int(r["raca"]))[0][0]),
            RENDA_CAT.index(r["renda_pc"])] = r["valor_num"]
    return arr


# ---------------------------------------------------------------- Boletim SESAU 01/2025
@lru_cache(maxsize=1)
def nascimentos_ds() -> pd.DataFrame:
    s = seleciona("Boletim 01/2025 Tab.3", "nascidos_vivos_2024", nivel="ds")
    p = s.pivot_table(index="cd_territorio", columns="raca_mae", values="valor_num", aggfunc="first")
    p.index = p.index.astype(int)
    p.index.name = "id_ds"
    return p[["negra", "nao_negra"]]


@lru_cache(maxsize=1)
def obitos_idade_raca() -> pd.DataFrame:
    s = seleciona("Boletim 01/2025 Tab.4", "obitos_2024")
    out = pd.DataFrame({"faixa": s["idade"], "raca": s["raca"], "obitos": s["valor_num"]})
    out[["ini", "fim"]] = out["faixa"].map(_faixa).tolist()
    return out.reset_index(drop=True)


@lru_cache(maxsize=1)
def consultas_prenatal() -> pd.DataFrame:
    s = seleciona("Boletim 01/2025 Tab.1", "nv_consultas_prenatal_2024")
    p = s.pivot_table(index="consultas", columns="raca_mae", values="valor_num", aggfunc="first")
    return p.loc[["0", "1-3", "4-6", "7+"]]


# ---------------------------------------------------------------------- estrutura
@lru_cache(maxsize=1)
def estrutura() -> dict[str, pd.DataFrame]:
    e = DADOS / "estrutura"
    rd = lambda n: pd.read_csv(e / n, dtype=str, keep_default_na=False)  # noqa: E731
    ds = rd("distrito_sanitario.csv").astype({"id_ds": int})
    ba = rd("bairro.csv").astype({"id_bairro": int, "id_ds": int})
    un = rd("unidade_saude.csv").astype({"tipo_unidade": int, "id_bairro": int})
    eq = rd("equipe.csv").astype({"tipo_equipe": int})
    hi = rd("equipe_historico.csv")[["ine", "dt_ativacao"]]
    eq = eq.merge(hi, on="ine", how="left")
    eq["dt_ativacao"] = pd.to_datetime(eq["dt_ativacao"]).dt.date
    un = un.merge(ba[["id_bairro", "id_ds"]], on="id_bairro")
    eq = eq.merge(un[["cnes", "id_bairro", "id_ds"]], on="cnes")
    return {"ds": ds, "bairro": ba, "unidade": un, "equipe": eq}


@lru_cache(maxsize=1)
def dominios() -> dict:
    return json.loads((DADOS / "dominios.json").read_text(encoding="utf-8"))
