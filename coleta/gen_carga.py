#!/usr/bin/env python3
"""Gera os scripts SQL portáveis (MySQL 8.0.16+ / PostgreSQL 16) da Etapa 5 a partir dos CSV
de coleta_parametros.py:
  04_carga_estrutura.sql  – CID-10 completa, tipos do CNES, distritos, bairros, unidades, equipes
  05_carga_parametros.sql – analitica.ref_parametro_oficial (formato longo)"""
import csv, json, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "out")
LOTE = 400


def q(v):
    return "NULL" if v is None or v == "" else "'" + str(v).replace("'", "''") + "'"


def n(v):
    return "NULL" if v == "" else str(v)


def le(p):
    with open(os.path.join(BASE, p), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def inserts(tabela, cols, linhas, fmt):
    out = []
    for i in range(0, len(linhas), LOTE):
        bloco = linhas[i:i + LOTE]
        out.append(f"INSERT INTO {tabela} ({', '.join(cols)}) VALUES\n" +
                   ",\n".join("    (" + ", ".join(f(r[c]) for c, f in zip(cols, fmt)) + ")" for r in bloco) + ";")
    return "\n".join(out)


def main():
    man = json.load(open(os.path.join(BASE, "manifesto.json"), encoding="utf-8"))
    ver, ref = man["versao"], man["referencia_cnes"]
    os.makedirs(OUT, exist_ok=True)
    cab = (f"-- Projeto 3 – Dados (CESAR School, 2026.2) · Equipe 2 – Nexus Data · v{ver} · {man['gerado_em']}\n"
           "-- Serve para MySQL 8.0.16+ e PostgreSQL 16 (SQL padrão; nomes qualificados pela camada).\n"
           "-- Gerado por gen_carga.py a partir dos CSV de coleta_parametros.py (ver manifesto.json).\n")

    cid = le("estrutura/dom_cid10.csv")
    novos = [r for r in cid if r["origem"] == "DATASUS"]
    tu, te = le("estrutura/dom_tipo_unidade.csv"), le("estrutura/dom_tipo_equipe.csv")
    ds, ba = le("estrutura/distrito_sanitario.csv"), le("estrutura/bairro.csv")
    un, eq = le("estrutura/unidade_saude.csv"), le("estrutura/equipe.csv")
    s = ["-- =====================================================================",
         "-- Etapa 5 – Coleta dos parâmetros oficiais · carga da estrutura real",
         cab.rstrip("\n"),
         f"-- Fontes: CNES (carga de {ref}), IBGE Censo 2022 (bairros, SIDRA 9922/9923), Prefeitura do",
         "-- Recife (bairros e RPA, dados abertos), CID-10 do DATASUS. Execute depois de 01_ddl e",
         "-- 02_carga_dominios e antes de qualquer dado gerado (as tabelas abaixo são esvaziadas).",
         "-- =====================================================================", "",
         "DELETE FROM nucleo.equipe;", "DELETE FROM nucleo.unidade_saude;", "DELETE FROM nucleo.setor_censitario;",
         "DELETE FROM nucleo.bairro;", "DELETE FROM nucleo.distrito_sanitario;",
         "DELETE FROM nucleo.dom_tipo_equipe;", "DELETE FROM nucleo.dom_tipo_unidade;", "",
         f"-- dom_cid10: +{len(novos)} códigos do DATASUS (categorias e subcategorias, sem ponto). Os 554 do",
         "-- LEDI já vieram de 02_carga_dominios e mantêm a descrição do LEDI; total = "
         f"{len(cid)}.",
         inserts("nucleo.dom_cid10", ["codigo", "descricao"], novos, [q, q]), "",
         "-- dom_tipo_unidade: tipo de unidade do CNES usado pelas unidades de APS do Recife",
         inserts("nucleo.dom_tipo_unidade", ["codigo", "descricao"], tu, [n, q]), "",
         "-- dom_tipo_equipe: tipos de equipe do CNES (tabela de tipos de equipe) presentes nas UBS do Recife",
         inserts("nucleo.dom_tipo_equipe", ["codigo", "descricao"], te, [n, q]), "",
         "-- distrito_sanitario: DS I a VIII",
         inserts("nucleo.distrito_sanitario", ["id_ds", "nome_ds"], ds, [n, q]), "",
         "-- bairro: 94 bairros oficiais; id_bairro = 3 últimos dígitos do código IBGE do bairro;",
         "-- distrito pela RPA e, nas RPA 3 e 6, pelas UBS do CNES (ver bairro_referencia.csv)",
         inserts("nucleo.bairro", ["id_bairro", "nome_bairro", "id_ds"], ba, [n, q, n]), "",
         f"-- unidade_saude: {len(un)} UBS ativas com equipe que faz cadastro individual (CNES, {ref})",
         inserts("nucleo.unidade_saude", ["cnes", "nome_unidade", "tipo_unidade", "id_bairro"], un, [q, q, n, n]), "",
         f"-- equipe: {len(eq)} equipes ativas (eSF 70, eCR 73, eAPP 74, eAP 76); INE real do CNES",
         inserts("nucleo.equipe", ["ine", "nome_equipe", "tipo_equipe", "cnes"], eq, [q, q, n, q]), ""]
    open(os.path.join(OUT, "04_carga_estrutura.sql"), "w", encoding="utf-8").write("\n".join(s))

    cols = ["fonte", "tabela_fonte", "nivel", "cd_territorio", "variavel", "categoria", "valor",
            "ic_inferior", "ic_superior", "dt_acesso"]
    fmt = [q, q, q, q, q, q, n, n, n, q]
    p = ["-- =====================================================================",
         "-- Etapa 5 – Coleta dos parâmetros oficiais · carga de analitica.ref_parametro_oficial",
         cab.rstrip("\n"),
         "-- Formato longo: uma linha por (fonte, tabela, nível, território, variável, categoria).",
         "-- As colunas tipo_intervalo, unidade e nota dos CSV são documentação e não são carregadas.",
         "-- =====================================================================", "",
         "DELETE FROM analitica.ref_parametro_oficial;", ""]
    total = 0
    for nome in sorted(os.listdir(os.path.join(BASE, "parametros"))):
        linhas = le(f"parametros/{nome}")
        total += len(linhas)
        p += [f"-- {nome}: {len(linhas)} linhas", inserts("analitica.ref_parametro_oficial", cols, linhas, fmt), ""]
    open(os.path.join(OUT, "05_carga_parametros.sql"), "w", encoding="utf-8").write("\n".join(p))
    print(f"04: {len(novos)} CID + {len(te)} tipos + {len(ba)} bairros + {len(un)} unidades + {len(eq)} equipes; "
          f"05: {total} parâmetros")


if __name__ == "__main__":
    main()
