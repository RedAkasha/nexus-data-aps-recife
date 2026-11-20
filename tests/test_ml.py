"""ML de alerta: garantias anti-vazamento e contrato dos arquivos de saída."""
import json

import pandas as pd
import pytest

from aps_sintetico import ml


def test_ml_sem_vazamento_e_saidas(saida):
    res = ml.treina(saida, usar_mlflow=False)
    r = json.loads((saida / "ml" / "resumo.json").read_text(encoding="utf-8"))
    assert max(r["periodos_treino"]) < min(r["periodos_teste"])
    assert r["auditoria_vazamento"]["treino_anterior_ao_teste"]
    assert r["auditoria_vazamento"]["colunas_proibidas_nas_variaveis"] == []
    assert res["escolhido"].sum() == 1 and set(res["modelo"]) >= {"persistencia", "logistica", "floresta"}
    p = pd.read_parquet(saida / "ml" / "predicoes.parquet")
    assert p["prob_alerta"].between(0, 1).all() and {"teste", "proximo"} <= set(p["fase"])
    assert (saida / "ml" / "JUSTIFICATIVA.md").exists()


def test_auditoria_barra_treino_depois_do_teste():
    d = pd.DataFrame({ml.ALVO: [0, 1, 0, 1], **{c: [0.1] * 4 for c in ml.NUM}, "id_ds": [1] * 4,
                      "tipo_equipe": ["a"] * 4})
    with pytest.raises(RuntimeError, match="VAZAMENTO"):
        ml.auditoria(d, d, [3, 4], [2, 3], 1)
