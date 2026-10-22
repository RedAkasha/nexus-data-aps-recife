"""Etapa 10 – inferência sobre a base sintética, comparada à verdade (estudo ADEMP).

Alvos (estimandos) e métodos:
  θ_e   proporção esperada de "Sim" entre os elegíveis ativos da equipe na data de corte
        (média de P(Sim) das versões vigentes, arquivo verdade/versoes)
        · bruta y/n, intervalo de Wilson 95% (cobertura), estimativa bayesiana empírica
          beta-binomial (RMSE e ordenação: Spearman e precisão@k das piores equipes)
  viés MNAR  proporção LGB+ entre quem respondeu "Sim" × prevalência real entre os elegíveis
  efeito da oficina  diferença ingênua (tratadas × controles no fim), diferença-em-diferenças
        no painel observado e o mesmo DiD na verdade instantânea (quanto a medida vigente atrasa ou dilui)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import optimize, special, stats

from .config import carrega as carrega_cfg
from .valida import le_csv, vigente

LGB = {"154", "196", "197", "198", "199", "155"}


def wilson(y, n, z=1.959964):
    y, n = np.asarray(y, float), np.asarray(n, float)
    p = np.where(n > 0, y / np.maximum(n, 1), np.nan)
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return c - h, c + h


def ajusta_beta_binomial(y, n) -> tuple[float, float]:
    """Máxima verossimilhança marginal de (alfa, beta) da beta-binomial."""
    y, n = np.asarray(y, float), np.asarray(n, float)

    def nll(t):
        a, b = np.exp(t)
        return -(special.betaln(y + a, n - y + b) - special.betaln(a, b)).sum()
    m = (y / n).mean()
    v = max((y / n).var(), 1e-4)
    k = max(m * (1 - m) / v - 1, 1.0)
    r = optimize.minimize(nll, np.log([m * k, (1 - m) * k]), method="Nelder-Mead")
    a, b = np.exp(r.x)
    return float(a), float(b)


def estimativas_equipe(saida: Path) -> pd.DataFrame:
    saida = Path(saida)
    cfg = carrega_cfg(saida / "config_usada.yaml")
    D = {"cfg": cfg, "cadastro_individual": le_csv(saida / "nucleo" / "cadastro_individual.csv"),
         "cidadao": le_csv(saida / "nucleo" / "cidadao.csv")}
    v = vigente(D)
    v = v[v["ativo"] & ~v["crianca"]]
    ver = pd.read_parquet(saida / "verdade" / "versoes.parquet")[["uuid", "p_sim_os"]]
    v = v.merge(ver, on="uuid", how="left")
    v["sim"] = v["deseja_informar_os"] == "1"
    g = v.groupby("ine").agg(n=("sim", "size"), y=("sim", "sum"), theta=("p_sim_os", "mean")).reset_index()
    g = g[g["n"] > 0]
    g["bruta"] = g["y"] / g["n"]
    g["wilson_inf"], g["wilson_sup"] = wilson(g["y"], g["n"])
    a, b = ajusta_beta_binomial(g["y"], g["n"])
    g["eb"] = (a + g["y"]) / (a + b + g["n"])
    g.attrs["alfa_beta"] = (a, b)
    return g


def metricas_equipe(g: pd.DataFrame, k_frac: float = 0.1) -> dict:
    k = max(1, int(round(k_frac * len(g))))
    piores = set(g.nsmallest(k, "theta")["ine"])
    out = {"n_equipes": len(g), "alfa_beta": g.attrs.get("alfa_beta"),
           "cobertura_wilson": float(((g["wilson_inf"] <= g["theta"]) & (g["theta"] <= g["wilson_sup"])).mean()),
           "rmse_bruta": float(np.sqrt(((g["bruta"] - g["theta"]) ** 2).mean())),
           "rmse_eb": float(np.sqrt(((g["eb"] - g["theta"]) ** 2).mean())),
           "spearman_bruta": float(stats.spearmanr(g["bruta"], g["theta"]).statistic),
           "spearman_eb": float(stats.spearmanr(g["eb"], g["theta"]).statistic),
           "precisao_k_bruta": len(piores & set(g.nsmallest(k, "bruta")["ine"])) / k,
           "precisao_k_eb": len(piores & set(g.nsmallest(k, "eb")["ine"])) / k, "k": k}
    return out


def vies_mnar(saida: Path) -> dict:
    """Prevalência LGB+ estimada pelo registro × verdade, entre elegíveis ativos na data de corte."""
    saida = Path(saida)
    cfg = carrega_cfg(saida / "config_usada.yaml")
    D = {"cfg": cfg, "cadastro_individual": le_csv(saida / "nucleo" / "cadastro_individual.csv"),
         "cidadao": le_csv(saida / "nucleo" / "cidadao.csv")}
    v = vigente(D)
    v = v[v["ativo"] & ~v["crianca"]]
    pes = pd.read_parquet(saida / "verdade" / "pessoas.parquet")[["id_cidadao", "lgb", "trans_nb"]].dropna(
        subset=["id_cidadao"])
    pes["id_cidadao"] = pes["id_cidadao"].astype("int64").astype(str)
    v = v.merge(pes, on="id_cidadao", how="left")
    resp = v[v["deseja_informar_os"] == "1"]
    est = resp["orientacao_sexual"].isin(LGB).mean()
    real = v["lgb"].mean()
    # pós-estratificação por faixa etária: corrige a parte MAR (aceitação cai com a idade);
    # o que sobra de viés é a não resposta informativa (lambda)
    faixa = pd.cut(v["idade_na_data_corte"], [10, 17, 29, 39, 59, 200])
    v = v.assign(faixa=faixa, lgb_reg=v["orientacao_sexual"].isin(LGB))
    taxa = v[v["deseja_informar_os"] == "1"].groupby("faixa", observed=True)["lgb_reg"].mean()
    peso = v["faixa"].value_counts(normalize=True)
    pos = float((taxa * peso.reindex(taxa.index)).sum() / peso.reindex(taxa.index).sum())
    resp_ig = v[v["deseja_informar_ig"] == "1"]
    est_t = resp_ig["identidade_genero"].isin({"149", "150", "156", "203"}).mean()
    return {"lgb_estimada_entre_respondentes": float(est), "lgb_real_elegiveis": float(real),
            "vies_lgb_pp": float(100 * (est - real)), "razao_lgb": float(est / real) if real else np.nan,
            "lgb_pos_estratificada_idade": pos, "vies_pos_estratificado_pp": float(100 * (pos - real)),
            "trans_nb_estimada": float(est_t), "trans_nb_real": float(v["trans_nb"].mean()),
            "lambda_cenario": float(cfg.registro.lambda_lgb), "n_respondentes": int(len(resp)),
            "ep_estimada_pp": float(100 * np.sqrt(max(est * (1 - est), 1e-12) / max(len(resp), 1)))}


def efeito_oficina(saida: Path) -> dict:
    saida = Path(saida)
    cfg = carrega_cfg(saida / "config_usada.yaml")
    pm = pd.read_parquet(saida / "analitica" / "fato_painel_ml.parquet")
    pm = pm[pm["tipo_equipe"].isin([70, 76])]
    ac = le_csv(saida / "nucleo" / "acao_formativa.csv")
    of = ac[ac["tipo_acao"] == "1"].groupby("ine")["dt_acao"].min()
    dim = pd.read_parquet(saida / "analitica" / "dim_competencia.parquet")
    fim = dim.groupby("quadrimestre")["dt_fim"].max()
    ini = pd.Timestamp(cfg.oficinas.inicio)
    pre = [p for p, d in fim.items() if d < ini]
    pos = [p for p, d in fim.items() if d > pd.Timestamp(cfg.oficinas.fim)]
    if not pre or not pos:
        return {"erro": "série sem períodos antes e depois das oficinas"}
    tr = pm["ine"].isin(of.index)
    pm = pm.assign(tratada=tr)
    pre_m = pm[pm["periodo"].isin(pre)].groupby(["ine", "tratada"])["prop_sim_os"].mean()
    pos_m = pm[pm["periodo"].isin(pos)].groupby(["ine", "tratada"])["prop_sim_os"].mean()
    d = (pos_m - pre_m).dropna().reset_index()
    dt_, dc_ = d[d["tratada"]]["prop_sim_os"], d[~d["tratada"]]["prop_sim_os"]
    did = dt_.mean() - dc_.mean()
    ep_did = np.sqrt(dt_.var() / len(dt_) + dc_.var() / len(dc_))
    ult = pm[pm["periodo"] == max(pos)]
    ingenua = ult[ult["tratada"]]["prop_sim_os"].mean() - ult[~ult["tratada"]]["prop_sim_os"].mean()
    # mesma conta na verdade instantânea (P(Sim) se a pergunta fosse feita no mês)
    vm = pd.read_parquet(saida / "verdade" / "equipe_mes.parquet")
    vm["data"] = pd.to_datetime(vm["competencia"].astype(str), format="%Y%m")
    vm["tratada"] = vm["ine"].isin(of.index)
    vpre = vm[vm["data"] < ini].groupby(["ine", "tratada"])["p_sim_os"].mean()
    vpos = vm[vm["data"] > pd.Timestamp(cfg.oficinas.fim)].groupby(["ine", "tratada"])["p_sim_os"].mean()
    dv = (vpos - vpre).dropna().rename("d").reset_index()
    did_v = dv[dv["tratada"]]["d"].mean() - dv[~dv["tratada"]]["d"].mean()
    return {"alocacao": cfg.oficinas.alocacao, "efeito_logito_verdadeiro": float(cfg.oficinas.efeito_logito),
            "n_tratadas": int(tr.groupby(pm["ine"]).first().sum()), "diferenca_ingenua_pp": float(100 * ingenua),
            "did_observado_pp": float(100 * did), "ep_did_observado_pp": float(100 * ep_did),
            "did_verdade_instantanea_pp": float(100 * did_v)}


def relatorio(saida: Path) -> Path:
    saida = Path(saida)
    g = estimativas_equipe(saida)
    res = {"equipes": metricas_equipe(g), "mnar": vies_mnar(saida), "oficina": efeito_oficina(saida)}
    rel = saida / "relatorios"
    rel.mkdir(parents=True, exist_ok=True)
    g.to_csv(rel / "estimativas_equipe.csv", index=False)
    (rel / "inferencia.json").write_text(json.dumps(res, ensure_ascii=False, indent=2, default=float),
                                         encoding="utf-8")
    e, m, o = res["equipes"], res["mnar"], res["oficina"]
    txt = [
        "# Inferência sobre a base sintética (comparada à verdade)", "",
        "## 1. Proporção de \"Sim\" por equipe", "",
        f"- Equipes: {e['n_equipes']}; beta-binomial ajustada: α = {e['alfa_beta'][0]:.2f}, β = {e['alfa_beta'][1]:.2f}.",
        f"- Cobertura do intervalo de Wilson 95% para θ: {e['cobertura_wilson']:.1%}.",
        f"- RMSE: bruta {e['rmse_bruta']:.4f} × bayesiana empírica {e['rmse_eb']:.4f}.",
        f"- Spearman com a verdade: bruta {e['spearman_bruta']:.3f} × EB {e['spearman_eb']:.3f}.",
        f"- Precisão@{e['k']} (piores equipes): bruta {e['precisao_k_bruta']:.0%} × EB {e['precisao_k_eb']:.0%}.", "",
        "## 2. Viés por não resposta informativa (MNAR)", "",
        f"- λ do cenário = {m['lambda_cenario']:.3f}. LGB+ entre quem respondeu: {m['lgb_estimada_entre_respondentes']:.2%}; "
        f"real entre os elegíveis: {m['lgb_real_elegiveis']:.2%} (viés {m['vies_lgb_pp']:+.2f} p.p.; razão {m['razao_lgb']:.2f}).",
        f"- Pós-estratificada por idade: {m['lgb_pos_estratificada_idade']:.2%} (viés {m['vies_pos_estratificado_pp']:+.2f} p.p.; "
        f"erro-padrão amostral ≈ {m['ep_estimada_pp']:.2f} p.p.). Com λ = 0 a não resposta é ignorável dado a idade "
        "(a aceitação cai com a idade e LGB+ é mais comum entre jovens), e a pós-estratificação deve trazer o viés "
        "para dentro do erro amostral; com λ ≠ 0 sobra o viés de não resposta informativa, que nenhum ajuste por "
        "covariável remove.",
        f"- Trans e não binários: {m['trans_nb_estimada']:.2%} entre respondentes × {m['trans_nb_real']:.2%} reais.", "",
        "## 3. Efeito das oficinas", ""]
    if "erro" in o:
        txt.append(f"- {o['erro']}")
    else:
        txt += [f"- Alocação: {o['alocacao']}; efeito verdadeiro no logito: {o['efeito_logito_verdadeiro']}; "
                f"equipes tratadas: {o['n_tratadas']}.",
                f"- Diferença ingênua no fim da série: {o['diferenca_ingenua_pp']:+.2f} p.p.",
                f"- Diferença-em-diferenças no painel observado: {o['did_observado_pp']:+.2f} p.p. "
                f"(EP {o['ep_did_observado_pp']:.2f} p.p.; IC95% ±{1.96 * o['ep_did_observado_pp']:.2f}).",
                f"- Mesma DiD na verdade instantânea: {o['did_verdade_instantanea_pp']:+.2f} p.p. "
                "Só as versões feitas depois da oficina carregam o efeito: quando o pós-período é curto, o "
                "observado fica abaixo da verdade."]
    p = rel / "inferencia.md"
    p.write_text("\n".join(txt) + "\n", encoding="utf-8")
    return p
