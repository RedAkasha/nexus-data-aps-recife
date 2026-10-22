"""Testes com PostgreSQL: carga sem violação, rota staging = rota direta, SQL = Python."""
import pytest

from aps_sintetico import analitica, carga
from conftest import precisa_banco

TABELAS = ["setor_censitario", "microarea", "profissional", "lotacao", "acao_formativa", "domicilio", "familia",
           "cidadao", "cadastro_individual", "cadastro_deficiencia", "ficha_atendimento", "atendimento_individual",
           "atendimento_problema", "parametro"]


@pytest.fixture(scope="module")
def direta(saida):
    carga.carrega(saida)
    return {t: carga.consulta(f"SELECT * FROM nucleo.{t}") for t in TABELAS}


@precisa_banco
def test_carga_sem_violacao(direta):
    assert carga.consulta("SELECT * FROM analitica.vw_validacao_carga").empty


@precisa_banco
def test_sql_igual_python(direta, saida):
    A = analitica.constroi(saida)
    for t in ("fato_painel_ml", "fato_atendimento_equipe", "fato_indicador_equipe"):
        assert analitica.compara(carga.consulta(f"SELECT * FROM analitica.{t}"), A[t]) == [], t
    mon = carga.consulta("SELECT * FROM analitica.vw_monitoramento_equipe")
    assert analitica.compara(mon, A["monitoramento_equipe"][mon.columns]) == []


@precisa_banco
def test_rotas_direta_e_staging_iguais(direta, saida):
    carga.carrega(saida, via_staging=True, analitica=False)
    for t in TABELAS:
        a = direta[t].astype(str).sort_values(list(direta[t].columns)).reset_index(drop=True)
        b = carga.consulta(f"SELECT * FROM nucleo.{t}")[list(direta[t].columns)].astype(str)
        b = b.sort_values(list(b.columns)).reset_index(drop=True)
        assert a.equals(b), t
    assert carga.consulta("SELECT * FROM analitica.vw_validacao_carga").empty
