"""Testes da base gerada (sem banco): regras do DDL reproduzidas em pandas, reprodutibilidade
e calibração."""
import json

import pandas as pd

from aps_sintetico import config, gerador, valida
from aps_sintetico.valida import le_csv


def test_manifesto_e_arquivos(saida):
    man = json.loads((saida / "manifesto.json").read_text(encoding="utf-8"))
    for k in man["sha256"]:
        assert (saida / k).exists()
    assert man["linhas"]["nucleo/cadastro_individual.csv"] > 0


def test_reprodutibilidade(saida, tmp_path):
    cfg = config.carrega("demo")
    gerador.gera_e_exporta(cfg, tmp_path)
    a = json.loads((saida / "manifesto.json").read_text(encoding="utf-8"))["sha256"]
    b = json.loads((tmp_path / "manifesto.json").read_text(encoding="utf-8"))["sha256"]
    iguais = [k for k in a if k.startswith(("nucleo/", "staging/")) and a[k] == b[k]]
    assert len(iguais) == sum(k.startswith(("nucleo/", "staging/")) for k in a)


def test_restricoes_do_cadastro(saida):
    ci = le_csv(saida / "nucleo" / "cadastro_individual.csv")
    os_, d_os = ci["orientacao_sexual"], ci["deseja_informar_os"]
    assert ((d_os == "1") == os_.notna()).all()                                   # ck_ci_os
    assert ((ci["deseja_informar_ig"] == "1") == ci["identidade_genero"].notna()).all()
    at = ci["ficha_atualizada"] == "1"
    assert (ci.loc[at, "uuid_originadora"].notna()).all() and ci.loc[~at, "uuid_originadora"].isna().all()
    assert (pd.to_datetime(ci["dt_digitacao"]) >= pd.to_datetime(ci["dt_cadastro"])).all()
    ob = ci["motivo_saida"] == "135"
    assert (pd.to_datetime(ci.loc[ob, "dt_obito"]) <= pd.to_datetime(ci.loc[ob, "dt_cadastro"])).all()
    rec = ci["recusa_cadastro"] == "1"
    assert ci.loc[rec, ["deseja_informar_os", "tem_deficiencia", "escolaridade"]].isna().all().all()
    assert ((ci["raca_cor"] == "5") == ci["etnia"].notna()).all()                 # ck_ci_etnia


def test_chaves_e_identificadores(saida):
    c = le_csv(saida / "nucleo" / "cidadao.csv")
    assert c["id_cidadao"].is_unique and c["cpf"].dropna().is_unique and c["cns"].dropna().is_unique
    assert (c["cpf"].notna() | c["cns"].notna()).all()
    ci = le_csv(saida / "nucleo" / "cadastro_individual.csv")
    assert ci["uuid"].is_unique and set(ci["id_cidadao"]) == set(c["id_cidadao"])     # VC10


def test_gabarito_aponta_para_registros(saida):
    g = le_csv(saida / "nucleo" / "controle_defeito.csv")
    ci = set(le_csv(saida / "nucleo" / "cadastro_individual.csv")["uuid"])
    cid = set(le_csv(saida / "nucleo" / "cidadao.csv")["id_cidadao"])
    assert g.loc[g["tabela"] == "cadastro_individual", "id_registro"].isin(ci).all()
    assert g.loc[g["tabela"] == "cidadao", "id_registro"].isin(cid).all()
    assert set(g["tipo_defeito"].astype(int)) <= set(range(1, 14))


def test_calibracao(saida):
    cal = valida.calibracao(saida)
    # numa base de 2% algumas contagens oscilam; exige-se a grande maioria dentro da tolerância
    assert cal["ok"].mean() >= 0.85, cal[~cal["ok"]]
    linha3 = cal[cal["verificacao"].str.startswith("linha 3, adultos")]
    assert linha3["ok"].all()
