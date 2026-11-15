"""Atividade da Aula 09 – Inferência Estatística 2026.2 (bases proxy).

Gera uma base SINTÉTICA de respostas (orientação sexual e identidade de gênero)
para cada Distrito Sanitário do Recife, com 10% dos adultos de cada DS (Censo 2022)
e uma semente por distrito; grava na tabela `respostas_sinteticas` (Neon/PostgreSQL);
valida por SQL e por binomtest contra 2,5% (IC de Wilson).

Uso (a partir da raiz do repositório):
    # conexão SOMENTE por variável de ambiente
    #   PowerShell: $env:APS_DSN="postgresql://USUARIO:SENHA@ep-xxx.REGIAO.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    #   bash:       export APS_DSN="postgresql://..."
    python atividade_aula09/gerar_respostas_neon.py              # gera, grava no banco e valida
    python atividade_aula09/gerar_respostas_neon.py --sem-banco  # só gera (CSV) e valida em pandas

Dependências: numpy, pandas, scipy e, para gravar, psycopg[binary].
Os dados são SINTÉTICOS: não descrevem pessoas reais nem a população do Recife.
"""
from __future__ import annotations

import argparse
import io
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = Path(__file__).resolve().parent / "saida"
TABELA = "respostas_sinteticas"
FRACAO = 0.10
SEMENTE_BASE = 2026          # semente do distrito = SEMENTE_BASE + id_ds
ALVO_LGB = 0.025             # PNS 2019, Recife (H0 do binomtest)
ALFA = 0.05
LGB = ["Gay", "Lésbica", "Bissexual"]

# ---------------------------------------------------------------- modelo (Aula 09)
P_NAO = 0.034                                   # PNS 2019: não sabe 1,1% + recusou 2,3%
P_TRANS, P_NB, P_OUTRO = 0.0069, 0.0119, 0.0010  # Spizzirri et al. 2021; H4
P_CIS = 1 - P_TRANS - P_NB - P_OUTRO
P_MULHER = 100 / (100 + 84.9)                    # Censo 2022, Recife: 84,9 homens por 100 mulheres
P_SIM = 1 - P_NAO

PROBS_GENERO = {
    "Homem cisgênero": P_CIS * (1 - P_MULHER),
    "Mulher cisgênero": P_CIS * P_MULHER,
    "Homem transgênero": P_TRANS / 2,            # H2
    "Mulher transgênero": P_TRANS / 2 * 2 / 3,   # H2 e H3: metade transfeminina, 1/3 travesti
    "Travesti": P_TRANS / 2 / 3,
    "Não-Binário": P_NB,
    "Outro": P_OUTRO,
}
PERFIL_DE = {
    "Homem cisgênero": "masc", "Homem transgênero": "masc",
    "Mulher cisgênero": "fem", "Mulher transgênero": "fem", "Travesti": "fem",
    "Não-Binário": "misto", "Outro": "misto",    # H7
}


def probs_orientacao() -> dict[str, dict[str, float]]:
    fator = (0.025 / 0.018) / P_SIM              # Recife ÷ Brasil (H6), dentro do "Sim"
    p = {
        "masc": {"Gay": 0.014 * fator, "Lésbica": 0.0, "Bissexual": 0.005 * fator},
        "fem": {"Gay": 0.0, "Lésbica": 0.009 * fator, "Bissexual": 0.008 * fator},
    }
    m, f = p["masc"], p["fem"]
    p["misto"] = {c: (m[c] + f[c]) / 2 for c in m}
    for d in p.values():
        d["Assexual"] = 0.0004 / P_SIM           # H5: "outra" 0,1% → 40/40/20
        d["Pansexual"] = 0.0004 / P_SIM
        d["Outro"] = 0.0002 / P_SIM
        d["Heterossexual"] = 1 - sum(d.values())
    return p


PROBS_ORIENT = probs_orientacao()


def p_lgb_efetivo() -> float:
    """P(LGB) implícita no modelo, sobre todos os adultos (inclui o \"Não\" na orientação)."""
    pf: dict[str, float] = {}
    for gen, p in PROBS_GENERO.items():
        pf[PERFIL_DE[gen]] = pf.get(PERFIL_DE[gen], 0.0) + p
    return P_SIM * sum(pf[k] * sum(PROBS_ORIENT[k][c] for c in LGB) for k in pf)


def gerar_base(n: int, seed: int) -> pd.DataFrame:
    """Mesma lógica da célula 14 da aula: informa(gênero) → gênero → perfil → orientação → informa(orient.)."""
    rng = np.random.default_rng(seed)
    opc, p_sn = ["Sim", "Não"], [P_SIM, P_NAO]
    inf_g = rng.choice(opc, size=n, p=p_sn)
    gen = rng.choice(list(PROBS_GENERO), size=n, p=list(PROBS_GENERO.values()))
    perf = pd.Series(gen).map(PERFIL_DE)
    ori = pd.Series(index=perf.index, dtype=object)
    for nome, probs in PROBS_ORIENT.items():
        m = perf == nome
        ori[m] = rng.choice(list(probs), size=int(m.sum()), p=list(probs.values()))
    inf_o = rng.choice(opc, size=n, p=p_sn)
    return pd.DataFrame({
        "informa_orientacao_sexual": inf_o,
        "orientacao_sexual": ori.where(inf_o == "Sim"),
        "informa_identidade_genero": inf_g,
        "identidade_genero": pd.Series(gen).where(inf_g == "Sim"),
    })


# ---------------------------------------------------------------- Censo 2022 → adultos por DS
def adultos_por_ds() -> pd.DataFrame:
    """Adultos (18+) por DS = população do DS × proporção de 18+ do município.

    O Censo 2022 do repositório traz população total por DS (soma dos bairros, SIDRA 9922/9923)
    e idade só no município (SIDRA 9514). Premissa: estrutura etária igual em todos os DS.
    """
    t = pd.read_csv(RAIZ / "dados/parametros/censo2022_territorio.csv")
    ds = t[(t.nivel == "ds") & (t.variavel == "pop_residente")]
    ds = ds.assign(id_ds=ds.cd_territorio.astype(int))[["id_ds", "valor"]].rename(columns={"valor": "pop_ds"}).astype({"pop_ds": int})
    a = pd.read_csv(RAIZ / "dados/parametros/censo2022_pop_sexo_idade.csv")
    cat = a.set_index("categoria")["valor"]
    total = cat["sexo=T;idade=T"]
    menores = sum(cat[f"sexo=T;idade={i}"] for i in range(18))
    p_adulto = (total - menores) / total
    ds["prop_adultos_recife"] = p_adulto
    ds["adultos_ds"] = (ds.pop_ds * p_adulto).round().astype(int)
    ds["n_amostra"] = (ds.adultos_ds * FRACAO).round().astype(int)
    ds["semente"] = SEMENTE_BASE + ds.id_ds
    return ds.sort_values("id_ds").reset_index(drop=True)


# ---------------------------------------------------------------- banco
def conectar():
    dsn = os.environ.get("APS_DSN")
    if not dsn:
        sys.exit("Defina a variável de ambiente APS_DSN (connection string do Neon) ou use --sem-banco.")
    import psycopg
    return psycopg.connect(dsn)


DDL = f"""
DROP TABLE IF EXISTS {TABELA};
CREATE TABLE {TABELA} (
    id_ds                      smallint NOT NULL,
    id_resposta                integer  NOT NULL,
    informa_orientacao_sexual  text     NOT NULL CHECK (informa_orientacao_sexual IN ('Sim','Não')),
    orientacao_sexual          text,
    informa_identidade_genero  text     NOT NULL CHECK (informa_identidade_genero IN ('Sim','Não')),
    identidade_genero          text,
    PRIMARY KEY (id_ds, id_resposta),
    CHECK ((informa_orientacao_sexual = 'Sim') = (orientacao_sexual IS NOT NULL)),
    CHECK ((informa_identidade_genero = 'Sim') = (identidade_genero IS NOT NULL))
);
COMMENT ON TABLE {TABELA} IS 'DADOS SINTÉTICOS (Aula 09, Inferência Estatística 2026.2). Não descrevem pessoas reais.';
"""

SQL_VALIDACAO = f"""
SELECT id_ds,
       COUNT(*)                                                                AS n,
       COUNT(*) FILTER (WHERE orientacao_sexual IN ('Gay','Lésbica','Bissexual')) AS k_lgb,
       COUNT(*) FILTER (WHERE informa_orientacao_sexual = 'Não')                AS nao_informa
FROM {TABELA} GROUP BY id_ds ORDER BY id_ds
"""


def gravar(con, bases: dict[int, pd.DataFrame]) -> None:
    with con.cursor() as cur:
        cur.execute(DDL)
        cols = "id_ds,id_resposta,informa_orientacao_sexual,orientacao_sexual,informa_identidade_genero,identidade_genero"
        with cur.copy(f"COPY {TABELA} ({cols}) FROM STDIN (FORMAT csv, NULL '')") as cp:
            for id_ds, b in bases.items():
                df = b.copy()
                df.insert(0, "id_resposta", np.arange(1, len(df) + 1))
                df.insert(0, "id_ds", id_ds)
                buf = io.StringIO()
                df.to_csv(buf, index=False, header=False)
                cp.write(buf.getvalue())
    con.commit()


def resultados_sql(con) -> pd.DataFrame:
    with con.cursor() as cur:
        cur.execute(SQL_VALIDACAO)
        return pd.DataFrame(cur.fetchall(), columns=["id_ds", "n", "k_lgb", "nao_informa"])


def resultados_pandas(bases: dict[int, pd.DataFrame]) -> pd.DataFrame:
    linhas = []
    for id_ds, b in bases.items():
        linhas.append((id_ds, len(b), int(b.orientacao_sexual.isin(LGB).sum()),
                       int((b.informa_orientacao_sexual == "Não").sum())))
    return pd.DataFrame(linhas, columns=["id_ds", "n", "k_lgb", "nao_informa"])


def testar(res: pd.DataFrame) -> pd.DataFrame:
    out = []
    for r in res.itertuples():
        t = stats.binomtest(int(r.k_lgb), n=int(r.n), p=ALVO_LGB)
        ic = t.proportion_ci(confidence_level=0.95, method="wilson")
        out.append((r.id_ds, r.n, r.k_lgb, r.k_lgb / r.n, ic.low, ic.high, t.pvalue))
    d = pd.DataFrame(out, columns=["id_ds", "n", "k_lgb", "prop_lgb", "ic_inf", "ic_sup", "p_valor"])
    d["rejeita_H0_5pct"] = d.p_valor < ALFA
    d["rejeita_bonferroni"] = d.p_valor < ALFA / len(d)
    return d


def relatorio(ds: pd.DataFrame, t: pd.DataFrame, origem: str, conj: pd.DataFrame) -> str:
    L = ["# Atividade da Aula 09 – bases proxy por Distrito Sanitário", "",
         "> **SINTÉTICO.** Nenhuma linha descreve pessoas reais nem a população do Recife.", "",
         f"Origem dos totais: {origem}. Tabela: `{TABELA}`. H₀: p(LGB) = {ALVO_LGB:.1%}, bilateral, α = {ALFA}, IC de Wilson.", "",
         "## Amostra por distrito", "",
         "| DS | População (Censo 2022) | Adultos (estimados) | n = 10% | Semente |", "|---|--:|--:|--:|--:|"]
    for r in ds.itertuples():
        L.append(f"| {r.id_ds} | {r.pop_ds:,} | {r.adultos_ds:,} | {r.n_amostra:,} | {r.semente} |".replace(",", "."))
    L += ["", f"Adultos = população do DS × {ds.prop_adultos_recife.iloc[0]:.4f} (proporção de 18+ no município; premissa: mesma estrutura etária em todos os DS).", "",
          "## binomtest contra 2,5%", "",
          "| DS | n | k (LGB) | proporção | IC95% Wilson | p-valor | rejeita H₀ (5%) | rejeita (Bonferroni) |", "|---|--:|--:|--:|---|--:|---|---|"]
    for r in t.itertuples():
        L.append(f"| {r.id_ds} | {r.n} | {r.k_lgb} | {r.prop_lgb:.2%} | [{r.ic_inf:.2%}; {r.ic_sup:.2%}] | {r.p_valor:.3f} | "
                 f"{'sim' if r.rejeita_H0_5pct else 'não'} | {'sim' if r.rejeita_bonferroni else 'não'} |")
    rej = t[t.rejeita_H0_5pct]
    L += ["", f"Distritos que rejeitaram H₀ a 5%: **{len(rej)} de {len(t)}**"
          + (f" (DS {', '.join(map(str, rej.id_ds))})." if len(rej) else "."), "",
          f"Conjunto (todos os DS): {int(conj.k_lgb.iloc[0])}/{int(conj.n.iloc[0])} = {conj.prop_lgb.iloc[0]:.2%}, p = {conj.p_valor.iloc[0]:.3f}.", "",
          "## Leitura", "",
          "- A base é gerada com p = 2,5% de LGB (probabilidade condicional ao “Sim” dividida por 0,966). Logo, rejeitar H₀ aqui indicaria bug ou azar, não descoberta.",
          f"- Com α = 0,05 e {len(t)} testes independentes, espera-se rejeitar ≈ {len(t) * ALFA:.1f} distrito só por acaso (P(≥1 rejeição) ≈ {1 - (1 - ALFA) ** len(t):.0%}). Uma rejeição isolada é compatível com isso; por Bonferroni (α/{len(t)} = {ALFA / len(t):.4f}) o limiar fica mais exigente.",
          "- Distritos menores têm n pequeno, IC mais largo e pouco poder: o teste quase nunca rejeita neles, e uma rejeição ali pesa mais.",
          f"- O p(LGB) implícito no modelo é {p_lgb_efetivo():.3%}, não exatamente {ALVO_LGB:.1%}: as probabilidades por perfil vêm de valores arredondados da PNS e a mistura de gênero muda um pouco o total. A diferença é de {abs(p_lgb_efetivo() - ALVO_LGB) * 100:.3f} p.p., desprezível frente ao erro amostral (e só vira rejeição com n muito grande).", ""]
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sem-banco", action="store_true", help="não conecta; valida em pandas e grava CSV")
    a = ap.parse_args()

    ds = adultos_por_ds()
    bases = {int(r.id_ds): gerar_base(int(r.n_amostra), int(r.semente)) for r in ds.itertuples()}
    SAIDA.mkdir(exist_ok=True)
    todas = pd.concat([b.assign(id_ds=i) for i, b in bases.items()], ignore_index=True)
    todas.to_csv(SAIDA / "base_proxy_SINTETICA_por_ds.csv", index=False)

    if a.sem_banco:
        res, origem = resultados_pandas(bases), "pandas (sem banco)"
    else:
        con = conectar()
        gravar(con, bases)
        res, origem = resultados_sql(con), f"consulta SQL em `{TABELA}` no banco de APS_DSN"
        con.close()
    t = testar(res)
    conj = testar(pd.DataFrame([{"id_ds": 0, "n": res.n.sum(), "k_lgb": res.k_lgb.sum()}]))
    t.to_csv(SAIDA / "validacao_por_ds.csv", index=False)
    texto = relatorio(ds, t, origem, conj)
    (SAIDA / "relatorio_aula09.md").write_text(texto, encoding="utf-8")
    print(texto)


if __name__ == "__main__":
    main()
