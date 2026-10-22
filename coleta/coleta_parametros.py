#!/usr/bin/env python3
"""
Etapa 5 – Coleta dos parâmetros oficiais do gerador sintético PEC/e-SUS APS (Recife).

Projeto 3 – Dados · CESAR School · 2026.2 · Equipe 2 – Nexus Data

Duas fases, separadas de propósito:

  coletar    baixa as fontes públicas e grava instantâneos em raw/ (precisa de rede):
             · IBGE/SIDRA (API apisidra.ibge.gov.br) – marginais do Censo 2022 do Recife;
             · CNES (serviços JSON de cnes.datasus.gov.br) – UBS e equipes do Recife;
             · Prefeitura do Recife (CKAN dados.recife.pe.gov.br) – bairros e RPA;
             · CID-10 do DATASUS (CSV oficiais, espelho no GitHub).
  processar  lê só raw/ e gera, sem rede, os CSV versionados:
             · parametros/*.csv – formato longo de analitica.ref_parametro_oficial;
             · estrutura/*.csv  – território e domínios reais para o núcleo;
             · manifesto.json   – versão, data de acesso, linhas e SHA-256 de cada arquivo.
  verificar  confere totais e chaves dos CSV gerados (roda também ao fim de processar).

Uso:
  python3 coleta_parametros.py coletar   [--raw raw]
  python3 coleta_parametros.py processar [--raw raw] [--saida .]
  python3 coleta_parametros.py verificar [--saida .]

Só biblioteca padrão (Python 3.9+). Nenhum dado pessoal é coletado: do CNES ficam apenas
estabelecimentos públicos e equipes; o CPF do diretor clínico e o telefone que a API devolve
são descartados na coleta.
"""
import argparse
import collections
import csv
import datetime as dt
import hashlib
import io
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

VERSAO = "1.0.0"
MUNICIPIO_IBGE = "2611606"   # Recife (7 dígitos, IBGE)
MUNICIPIO_CNES = "261160"    # Recife (6 dígitos, CNES/DATASUS)
UA = "NexusData-Projeto3/1.0 (CESAR School; coleta de parametros publicos)"

# ----------------------------------------------------------------------------------------
# 1. Definição das consultas (a "receita" do scraper)
# ----------------------------------------------------------------------------------------
SIDRA_URL = "https://apisidra.ibge.gov.br/values/{}?formato=json"
SIDRA = {   # tabela: (caminho da API, descrição)
    "9514": ("t/9514/n6/2611606/v/93/p/2022/c2/all/c287/all/c286/all",
             "População residente por sexo, idade e forma de declaração da idade"),
    "9605": ("t/9605/n6/2611606/v/93/p/all/c86/all",
             "População residente por cor ou raça (2010 e 2022)"),
    "9606": ("t/9606/n6/2611606/v/93/p/2022/c86/all/c2/all/c287/all",
             "População residente por cor ou raça, sexo e idade"),
    "4712": ("t/4712/n6/2611606/v/all/p/2022",
             "Domicílios particulares permanentes ocupados e moradores"),
    "10125": ("t/10125/n6/2611606/v/11852,12785/p/2022/c2/all/c58/all",
              "Pessoas de 2 anos ou mais, total e com deficiência, por sexo e grupo de idade"),
    "10127": ("t/10127/n6/2611606/v/12785/p/2022/c1509/all",
              "Pessoas com deficiência por tipo de dificuldade funcional"),
    "10132": ("t/10132/n6/2611606/v/11852/p/2022/c86/all/c839/all",
              "Pessoas de 2 anos ou mais por cor ou raça e existência de deficiência"),
    "10145": ("t/10145/n6/2611606/v/93,13267/p/2022/c2/all/c58/all",
              "População residente e diagnosticada com autismo, por sexo e grupo de idade"),
    "10147": ("t/10147/n6/2611606/v/93,13267/p/2022/c86/all",
              "População residente e diagnosticada com autismo, por cor ou raça"),
    "10061": ("t/10061/n6/2611606/v/2667/p/2022/c1568/all/c58/all/c2/all/c86/all",
              "Pessoas de 18 anos ou mais por nível de instrução, idade, sexo e cor ou raça"),
    "10296": ("t/10296/n6/2611606/v/13604/p/2022/c2/all/c86/all/c386/all",
              "Moradores por sexo, cor ou raça e rendimento domiciliar per capita"),
    "10300": ("t/10300/n6/2611606/v/13432/p/2022/c629/all/c386/all",
              "Pessoas de 14+ por condição na força de trabalho e rendimento domiciliar per capita"),
    "9922": ("t/9922/n102/in%20n6%202611606/v/all/p/2022/c1/all",
             "Domicílios, moradores e média de moradores por bairro"),
    "9923": ("t/9923/n102/in%20n6%202611606/v/all/p/2022/c1/all",
             "População residente por bairro"),
}
CNES_BASE = "https://cnes.datasus.gov.br/services"
CKAN_BAIRROS = ("https://dados.recife.pe.gov.br/api/3/action/datastore_search"
                "?resource_id=a378d50a-5e55-4956-a28c-13305acfc2b3&limit=200")
CID10_URLS = {
    "CID-10-CATEGORIAS.CSV": "https://raw.githubusercontent.com/cleytonferrari/CidDataSus/master/"
                             "CIDImport/Repositorio/Resources/CID-10-CATEGORIAS.CSV",
    "CID-10-SUBCATEGORIAS.CSV": "https://raw.githubusercontent.com/cleytonferrari/CidDataSus/master/"
                                "CIDImport/Repositorio/Resources/CID-10-SUBCATEGORIAS.CSV",
}
TIPOS_EQUIPE_APS = {"70", "71", "72", "73", "74", "76"}   # ESF, ESB, eMulti, eCR, eAPP, EAP
TIPOS_EQUIPE_CADASTRO = {"70", "73", "74", "76"}           # equipes que fazem cadastro individual
TIPOS_EQUIPE_ESF_EAP = {"70", "76"}
CAMPOS_EST = ["cnes", "noFantasia", "coTipoEstabelecimento", "dsTipoEstabelecimento", "dsTpUnidade",
              "noLogradouro", "nuEndereco", "cep", "bairro", "nuLatitude", "nuLongitude",
              "coDistritoSanitario", "dsDistrito", "coMotivoDesab", "dsMotivoDesab", "nuCompDesab",
              "dtAtualizacao", "dtCarga"]
CAMPOS_EQ = ["tpEquipe", "dsEquipe", "coEquipe", "nomeEquipe", "coArea", "dsArea",
             "dtAtivacao", "dtDesativacao"]


# ----------------------------------------------------------------------------------------
# 2. Utilitários
# ----------------------------------------------------------------------------------------
def http_get(url, headers=None, tentativas=4, espera=2.0):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    ultimo = None
    for k in range(tentativas):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return r.read()
        except Exception as e:   # noqa: BLE001 – rede pública instável; repete com espera crescente
            ultimo = e
            time.sleep(espera * (k + 1))
    raise RuntimeError(f"falha ao baixar {url}: {ultimo}")


def sha256_arquivo(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 16), b""):
            h.update(bloco)
    return h.hexdigest()


def normaliza(txt):
    """Maiúsculas sem acento nem pontuação (para casar nomes de bairro entre fontes)."""
    s = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode().upper()
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z ]", " ", s)).strip()


def sidra_compacto(linhas_json):
    """Converte a resposta da API SIDRA (lista de dicionários, 1.ª linha = cabeçalho) no formato
    compacto dos instantâneos: {dims, names{dim:{código:nome}}, rows['c1\\t…\\tcn\\tV\\tMN']}."""
    cab, dados = linhas_json[0], linhas_json[1:]
    n = 1
    while f"D{n}N" in cab:
        n += 1
    dims = [cab[f"D{i}N"] for i in range(1, n)]
    names = {d: {} for d in dims}
    rows = []
    for x in dados:
        cods = []
        for i, d in enumerate(dims, 1):
            names[d][x[f"D{i}C"]] = x[f"D{i}N"]
            cods.append(x[f"D{i}C"])
        rows.append("\t".join(cods + [x["V"], x["MN"]]))
    return {"dims": dims, "names": names, "rows": rows}


def bairros_csv(comp9923, comp9922):
    """Tabela por bairro (situação do domicílio = Total, código 6795) a partir das tabelas 9922/9923."""
    m = {}
    for comp in (comp9923, comp9922):
        dims = comp["dims"]
        ib, iv = dims.index("Bairro"), dims.index("Variável")
        isit = next(i for i, d in enumerate(dims) if d.startswith("Situação"))
        for r in comp["rows"]:
            c = r.split("\t")
            if c[isit] != "6795":
                continue
            reg = m.setdefault(c[ib], {"nome": comp["names"]["Bairro"][c[ib]].replace(" - Recife - PE", "")})
            reg[c[iv]] = c[-2]
    out = io.StringIO()
    out.write("cd_bairro,nome,pop_residente,dom_ocupados,moradores_dpp,media_moradores\n")
    for cd in sorted(m):
        r = m[cd]
        out.write(",".join([cd, r["nome"], r["93"], r["381"], r["382"], r["5930"]]) + "\n")
    return out.getvalue()


# ----------------------------------------------------------------------------------------
# 3. Fase "coletar" (rede)
# ----------------------------------------------------------------------------------------
def coletar(raw):
    os.makedirs(os.path.join(raw, "cid10"), exist_ok=True)
    hoje = dt.date.today().isoformat()
    origem = {}

    print("[SIDRA] consultando", len(SIDRA), "tabelas")
    comp = {}
    for tab, (caminho, _) in SIDRA.items():
        url = SIDRA_URL.format(caminho)
        comp[tab] = sidra_compacto(json.loads(http_get(url)))
        origem.setdefault("sidra_compact.json", []).append(url)
        print(f"  {tab}: {len(comp[tab]['rows'])} linhas")
        time.sleep(0.5)
    bairros = bairros_csv(comp.pop("9923"), comp.pop("9922"))
    with open(os.path.join(raw, "sidra_compact.json"), "w", encoding="utf-8") as f:
        json.dump(comp, f, ensure_ascii=False)
    with open(os.path.join(raw, "sidra_9922_9923_bairros.csv"), "w", encoding="utf-8") as f:
        f.write(bairros)
    origem["sidra_9922_9923_bairros.csv"] = [SIDRA_URL.format(SIDRA[t][0]) for t in ("9922", "9923")]

    print("[CNES] estabelecimentos e equipes do município", MUNICIPIO_CNES)
    hdr = {"Accept": "application/json", "Referer": "https://cnes.datasus.gov.br/"}
    todos = json.loads(http_get(f"{CNES_BASE}/estabelecimentos?municipio={MUNICIPIO_CNES}", hdr))
    publicos = [e for e in todos if e.get("natJuridica") == "1"]   # administração pública
    det, eqs = {}, {}
    for k, e in enumerate(publicos, 1):
        d = json.loads(http_get(f"{CNES_BASE}/estabelecimentos/{e['id']}", hdr))
        det[e["cnes"]] = {c: d.get(c) for c in CAMPOS_EST}           # descarta CPF/telefone/e-mail
        eqs[e["cnes"]] = json.loads(http_get(f"{CNES_BASE}/estabelecimentos-equipes/{e['id']}", hdr))
        if k % 50 == 0:
            print(f"  {k}/{len(publicos)}")
        time.sleep(0.2)
    sel = sorted(c for c in det if det[c]["dsTipoEstabelecimento"] == "UNIDADE BASICA DE SAUDE"
                 or any(q["tpEquipe"] in TIPOS_EQUIPE_APS for q in eqs.get(c) or []))
    linhas = ["##EST", "\t".join(CAMPOS_EST)]
    for c in sel:
        linhas.append("\t".join("" if det[c][k] is None else str(det[c][k]) for k in CAMPOS_EST))
    linhas += ["##EQ", "\t".join(["cnes"] + CAMPOS_EQ)]
    for c in sel:
        for q in eqs.get(c) or []:
            linhas.append("\t".join([c] + ["" if q.get(k) is None else str(q[k]) for k in CAMPOS_EQ]))
    with open(os.path.join(raw, "cnes_recife_aps.tsv"), "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")
    origem["cnes_recife_aps.tsv"] = [f"{CNES_BASE}/estabelecimentos?municipio={MUNICIPIO_CNES}",
                                     f"{CNES_BASE}/estabelecimentos/{{id}}",
                                     f"{CNES_BASE}/estabelecimentos-equipes/{{id}}"]
    print(f"  {len(publicos)} estabelecimentos públicos; {len(sel)} UBS/APS gravados")

    print("[Prefeitura] bairros e RPA")
    j = json.loads(http_get(CKAN_BAIRROS))
    with open(os.path.join(raw, "bairros_rpa_recife.csv"), "w", encoding="utf-8") as f:
        f.write("bairro,rpa\n")
        for r in j["result"]["records"]:
            f.write(f"{r['Bairro']},{r['rpa']}\n")
    origem["bairros_rpa_recife.csv"] = [CKAN_BAIRROS]

    print("[DATASUS] CID-10")
    for nome, url in CID10_URLS.items():
        with open(os.path.join(raw, "cid10", nome), "wb") as f:
            f.write(http_get(url))
        origem[f"cid10/{nome}"] = [url]

    grava_manifesto_raw(raw, origem, hoje)


def grava_manifesto_raw(raw, origem, data_acesso):
    man = {"gerado_em": data_acesso, "arquivos": {}}
    for nome, urls in origem.items():
        p = os.path.join(raw, nome)
        man["arquivos"][nome] = {"sha256": sha256_arquivo(p), "bytes": os.path.getsize(p),
                                 "dt_acesso": data_acesso, "origem": urls}
    with open(os.path.join(raw, "manifesto_raw.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=1)


# ----------------------------------------------------------------------------------------
# 4. Fase "processar" (sem rede)
# ----------------------------------------------------------------------------------------
COLUNAS = ["fonte", "tabela_fonte", "nivel", "cd_territorio", "variavel", "categoria", "valor",
           "ic_inferior", "ic_superior", "dt_acesso", "tipo_intervalo", "unidade", "nota"]
RACA_IBGE_ESUS = {"2776": "1", "2777": "2", "2778": "3", "2779": "4", "2780": "5", "95251": "T"}
NOME_RACA = {"1": "Branca", "2": "Preta", "3": "Amarela", "4": "Parda", "5": "Indígena", "T": "Total"}
SEXO_IBGE = {"4": "H", "5": "M", "6794": "T"}
ROMANO = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8}
NOME_DS = {v: f"DS {k}" for k, v in ROMANO.items()}

# Nomes de bairro do CNES que não coincidem com os 94 bairros oficiais (IBGE/Prefeitura).
ALIAS_BAIRRO = {"JORDAO BAIXO": "JORDAO", "JORDAO ALTO": "JORDAO", "IBURA DE BAIXO": "IBURA",
                "SITIO DOS PINTOS": "SITIO DOS PINTOS SAO BRAS", "POCO DA PANELA": "POCO",
                "UR VARZEA": "VARZEA"}
# Bairros das RPA 3 e 6 (divididas entre dois distritos) sem UBS no CNES: distrito inferido
# pela contiguidade com bairros de distrito conhecido. A CONFIRMAR com a SESAU.
DS_INFERIDO = {"BREJO DA GUABIRABA": 7, "PAU FERRO": 7, "AFLITOS": 3, "CASA FORTE": 3, "DERBY": 3,
               "JAQUEIRA": 3, "MONTEIRO": 3, "PARNAMIRIM": 3, "SANTANA": 3, "TAMARINEIRA": 3}


def idade_ibge(nome):
    """Rótulo de idade do IBGE → código curto ('0', '37', '100+', '5-9', '2+', 'T'); None = descartar."""
    if nome == "Total":
        return "T"
    if nome == "Menos de 1 ano":
        return "0"
    if "mês" in nome or "meses" in nome:
        return None   # subdivisões do primeiro ano (9514/9606) não são usadas
    m = re.fullmatch(r"(\d+) anos? ou mais", nome)
    if m:
        return m.group(1) + "+"
    m = re.fullmatch(r"(\d+) a (\d+) anos", nome)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.fullmatch(r"(\d+) anos?", nome)
    if m:
        return m.group(1)
    raise ValueError(f"rótulo de idade inesperado: {nome}")


def valor_sidra(v):
    if v == "-":          # convenção do IBGE: zero absoluto
        return 0.0
    if v in ("..", "...", "X"):
        return None       # não se aplica / não disponível / sigilo
    return float(v)


class Saida:
    """Acumula linhas por arquivo, garante a chave primária de ref_parametro_oficial."""

    def __init__(self):
        self.arquivos = collections.OrderedDict()
        self.chaves = set()

    def add(self, arq, fonte, tab, nivel, cd, var, cat, valor, lo=None, hi=None, dt_acesso="",
            tipo="", unid="", nota=""):
        assert len(fonte) <= 30 and len(tab) <= 30 and len(nivel) <= 12 and len(cd) <= 15, (fonte, tab)
        assert len(var) <= 40 and len(cat) <= 40, (var, cat)
        k = (fonte, tab, nivel, cd, var, cat)
        if k in self.chaves:
            raise ValueError(f"chave duplicada em ref_parametro_oficial: {k}")
        self.chaves.add(k)
        fmt = lambda x: "" if x is None else (str(int(x)) if float(x).is_integer() and abs(x) >= 1
                                              else f"{x:.6f}".rstrip("0").rstrip("."))
        self.arquivos.setdefault(arq, []).append(
            [fonte, tab, nivel, cd, var, cat, fmt(valor), fmt(lo), fmt(hi), dt_acesso, tipo, unid, nota])


def le_raw(raw):
    with open(os.path.join(raw, "sidra_compact.json"), encoding="utf-8") as f:
        sidra = json.load(f)
    with open(os.path.join(raw, "sidra_9922_9923_bairros.csv"), encoding="utf-8") as f:
        bairros = list(csv.DictReader(f))
    with open(os.path.join(raw, "bairros_rpa_recife.csv"), encoding="utf-8") as f:
        rpa = list(csv.DictReader(f))
    with open(os.path.join(raw, "cnes_recife_aps.tsv"), encoding="utf-8") as f:
        txt = f.read()
    est_txt, eq_txt = txt.split("##EQ\n")
    est = list(csv.DictReader(io.StringIO(est_txt.replace("##EST\n", "")), delimiter="\t"))
    eq = list(csv.DictReader(io.StringIO(eq_txt), delimiter="\t"))
    man = {}
    p = os.path.join(raw, "manifesto_raw.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            man = json.load(f)
    return sidra, bairros, rpa, est, eq, man


def linhas_sidra(sidra, tab):
    t = sidra[tab]
    return t, [r.split("\t") for r in t["rows"]]


def processa_sidra(S, sidra, dt_sidra):
    F = "IBGE Censo 2022"

    # 9514 – sexo × idade (forma de declaração = Total)
    t, rows = linhas_sidra(sidra, "9514")
    for r in rows:
        if r[5] != "113635":
            continue
        idade = idade_ibge(t["names"]["Idade"][r[4]])
        if idade is None:
            continue
        S.add("censo2022_pop_sexo_idade.csv", F, "SIDRA 9514", "municipio", MUNICIPIO_IBGE,
              "pop_residente", f"sexo={SEXO_IBGE[r[3]]};idade={idade}", valor_sidra(r[-2]),
              dt_acesso=dt_sidra, unid="pessoas")

    # 9605 – cor ou raça, 2010 e 2022 (contagem e proporção)
    t, rows = linhas_sidra(sidra, "9605")
    tot = {r[2]: valor_sidra(r[-2]) for r in rows if r[3] == "95251"}
    for r in rows:
        fonte = "IBGE Censo " + r[2]
        raca = RACA_IBGE_ESUS[r[3]]
        v = valor_sidra(r[-2])
        S.add("censo_pop_raca.csv", fonte, "SIDRA 9605", "municipio", MUNICIPIO_IBGE, "pop_residente",
              f"raca={raca}", v, dt_acesso=dt_sidra, unid="pessoas", nota=NOME_RACA[raca])
        if raca != "T":
            S.add("censo_pop_raca.csv", fonte, "SIDRA 9605", "municipio", MUNICIPIO_IBGE,
                  "prop_pop_residente", f"raca={raca}", v / tot[r[2]], dt_acesso=dt_sidra,
                  unid="proporção", nota=NOME_RACA[raca])
    # sem declaração de cor ou raça (Total − soma das cinco categorias; 47 pessoas em 2022)
    for ano in tot:
        sd = tot[ano] - sum(valor_sidra(r[-2]) for r in rows if r[2] == ano and r[3] != "95251")
        S.add("censo_pop_raca.csv", "IBGE Censo " + ano, "SIDRA 9605", "municipio", MUNICIPIO_IBGE,
              "pop_residente", "raca=SD", sd, dt_acesso=dt_sidra, unid="pessoas",
              nota="Sem declaração: Total − soma das categorias (derivado)")
    # pretos + pardos (indicador da Tabela 6)
    for ano in tot:
        pp = sum(valor_sidra(r[-2]) for r in rows if r[2] == ano and r[3] in ("2777", "2779"))
        S.add("censo_pop_raca.csv", "IBGE Censo " + ano, "SIDRA 9605", "municipio", MUNICIPIO_IBGE,
              "prop_pop_residente", "raca=2+4", pp / tot[ano], dt_acesso=dt_sidra, unid="proporção",
              nota="Pretos + pardos")

    # 9606 – cor ou raça × sexo × idade (semente do IPF)
    t, rows = linhas_sidra(sidra, "9606")
    for r in rows:
        idade = idade_ibge(t["names"]["Idade"][r[5]])
        if idade is None:
            continue
        S.add("censo2022_pop_raca_sexo_idade.csv", F, "SIDRA 9606", "municipio", MUNICIPIO_IBGE,
              "pop_residente", f"raca={RACA_IBGE_ESUS[r[3]]};sexo={SEXO_IBGE[r[4]]};idade={idade}",
              valor_sidra(r[-2]), dt_acesso=dt_sidra, unid="pessoas")

    # 4712 – domicílios do município
    t, rows = linhas_sidra(sidra, "4712")
    var4712 = {"381": ("dom_ocupados", "domicílios"), "382": ("moradores_dpp", "pessoas"),
               "5930": ("media_moradores_dpp", "pessoas por domicílio")}
    for r in rows:
        nome, unid = var4712[r[1]]
        S.add("censo2022_domicilios.csv", F, "SIDRA 4712", "municipio", MUNICIPIO_IBGE, nome, "T",
              valor_sidra(r[-2]), dt_acesso=dt_sidra, unid=unid)

    # 10125 – deficiência por sexo × grupo de idade (contagem e prevalência)
    t, rows = linhas_sidra(sidra, "10125")
    base = {(r[3], r[4]): valor_sidra(r[-2]) for r in rows if r[1] == "11852"}
    for r in rows:
        cat = f"sexo={SEXO_IBGE[r[3]]};idade={idade_ibge(t['names']['Grupo de idade'][r[4]])}"
        cat = cat.replace("idade=T", "idade=2+")
        v = valor_sidra(r[-2])
        nome = "pessoas_2mais" if r[1] == "11852" else "pcd_2mais"
        S.add("censo2022_deficiencia.csv", F, "SIDRA 10125", "municipio", MUNICIPIO_IBGE, nome, cat, v,
              dt_acesso=dt_sidra, unid="pessoas")
        if r[1] == "12785" and base.get((r[3], r[4])):
            S.add("censo2022_deficiencia.csv", F, "SIDRA 10125", "municipio", MUNICIPIO_IBGE,
                  "prev_pcd", cat, v / base[(r[3], r[4])], dt_acesso=dt_sidra, unid="proporção")

    # 10127 – tipo de dificuldade funcional (uma pessoa pode ter mais de um tipo)
    t, rows = linhas_sidra(sidra, "10127")
    cod_dif = {"58771": "T", "73771": "enxergar", "73772": "ouvir", "73773": "andar",
               "73789": "pegar", "73790": "mental"}
    pop2 = base[("6794", "95253")]
    for r in rows:
        v = valor_sidra(r[-2])
        S.add("censo2022_deficiencia.csv", F, "SIDRA 10127", "municipio", MUNICIPIO_IBGE,
              "pcd_2mais", f"dificuldade={cod_dif[r[3]]}", v, dt_acesso=dt_sidra, unid="pessoas",
              nota=t["names"]["Tipos de dificuldades funcionais"][r[3]][:180])
        S.add("censo2022_deficiencia.csv", F, "SIDRA 10127", "municipio", MUNICIPIO_IBGE,
              "prev_pcd", f"dificuldade={cod_dif[r[3]]}", v / pop2, dt_acesso=dt_sidra, unid="proporção",
              nota="Sobre a população de 2 anos ou mais")

    # 10132 – deficiência por cor ou raça
    t, rows = linhas_sidra(sidra, "10132")
    b = {r[3]: valor_sidra(r[-2]) for r in rows if r[4] == "46583"}
    cod_def = {"46583": "T", "58765": "sim", "58766": "nao"}
    for r in rows:
        cat = f"raca={RACA_IBGE_ESUS[r[3]]};deficiencia={cod_def[r[4]]}"
        v = valor_sidra(r[-2])
        S.add("censo2022_deficiencia.csv", F, "SIDRA 10132", "municipio", MUNICIPIO_IBGE,
              "pessoas_2mais", cat, v, dt_acesso=dt_sidra, unid="pessoas")
        if r[4] == "58765":
            S.add("censo2022_deficiencia.csv", F, "SIDRA 10132", "municipio", MUNICIPIO_IBGE,
                  "prev_pcd", f"raca={RACA_IBGE_ESUS[r[3]]}", v / b[r[3]], dt_acesso=dt_sidra,
                  unid="proporção")

    # 10145 e 10147 – autismo (TEA, código 232 do e-SUS)
    for tab, dim in (("10145", None), ("10147", "Cor ou raça")):
        t, rows = linhas_sidra(sidra, tab)
        for r in rows:
            if tab == "10145":
                cat = f"sexo={SEXO_IBGE[r[3]]};idade={idade_ibge(t['names']['Grupo de idade'][r[4]])}"
            else:
                cat = f"raca={RACA_IBGE_ESUS[r[3]]}"
            v = valor_sidra(r[-2])
            nome = "pop_residente" if r[1] == "93" else "pop_autismo"
            S.add("censo2022_autismo.csv", F, f"SIDRA {tab}", "municipio", MUNICIPIO_IBGE, nome, cat, v,
                  dt_acesso=dt_sidra, unid="pessoas")
        basea = {}
        for r in rows:
            if r[1] == "93":
                basea[tuple(r[3:-2])] = valor_sidra(r[-2])
        for r in rows:
            if r[1] != "13267":
                continue
            bb = basea.get(tuple(r[3:-2]))
            if not bb:
                continue
            if tab == "10145":
                cat = f"sexo={SEXO_IBGE[r[3]]};idade={idade_ibge(t['names']['Grupo de idade'][r[4]])}"
            else:
                cat = f"raca={RACA_IBGE_ESUS[r[3]]}"
            S.add("censo2022_autismo.csv", F, f"SIDRA {tab}", "municipio", MUNICIPIO_IBGE, "prev_autismo",
                  cat, valor_sidra(r[-2]) / bb, dt_acesso=dt_sidra, unid="proporção")

    # 10061 – nível de instrução (18+) por idade, sexo e cor ou raça
    t, rows = linhas_sidra(sidra, "10061")
    cod_ins = {"9493": "1", "9494": "2", "9495": "3", "99713": "4", "120704": "T"}
    for r in rows:
        cat = (f"instr={cod_ins[r[3]]};idade={idade_ibge(t['names']['Grupo de idade'][r[4]])};"
               f"sexo={SEXO_IBGE[r[5]]};raca={RACA_IBGE_ESUS[r[6]]}").replace("idade=T", "idade=18+")
        S.add("censo2022_instrucao.csv", F, "SIDRA 10061", "municipio", MUNICIPIO_IBGE, "pessoas_18mais",
              cat, valor_sidra(r[-2]), dt_acesso=dt_sidra, unid="pessoas",
              nota="instr: 1 sem instrução/fund. incompleto; 2 fund. completo/médio incompleto; "
                   "3 médio completo/superior incompleto; 4 superior completo")

    # 10296 e 10300 – rendimento domiciliar per capita (classes de salário mínimo)
    cod_rend = {"9680": "T", "9681": "ate0.25", "9682": "0.25-0.5", "9683": "0.5-1", "9684": "1-2",
                "9685": "2-3", "9686": "3-5", "9687": "5-10", "9688": "10-15", "9689": "15-20",
                "9690": "20+", "9692": "sem"}
    t, rows = linhas_sidra(sidra, "10296")
    for r in rows:
        cat = f"sexo={SEXO_IBGE[r[3]]};raca={RACA_IBGE_ESUS[r[4]]};renda_pc={cod_rend[r[5]]}"
        S.add("censo2022_renda.csv", F, "SIDRA 10296", "municipio", MUNICIPIO_IBGE, "moradores_dpp", cat,
              valor_sidra(r[-2]), dt_acesso=dt_sidra, unid="pessoas",
              nota="renda_pc em salários mínimos; exclui pensionistas e empregados domésticos")
    t, rows = linhas_sidra(sidra, "10300")
    cod_ft = {"32385": "T", "32386": "ft", "32387": "ocupada", "32446": "desocupada", "32447": "fora_ft"}
    for r in rows:
        S.add("censo2022_renda.csv", F, "SIDRA 10300", "municipio", MUNICIPIO_IBGE, "pessoas_14mais",
              f"ft={cod_ft[r[3]]};renda_pc={cod_rend[r[4]]}", valor_sidra(r[-2]),
              dt_acesso=dt_sidra, unid="pessoas")


def territorio(bairros, rpa, est):
    """Liga bairro → RPA → distrito sanitário. Regra: DS = RPA nas RPA 1, 2, 4 e 5; nas RPA 3 e 6
    (divididas em III/VII e VI/VIII) o DS vem das UBS do bairro no CNES; sem UBS, DS_INFERIDO."""
    rpa_n = {}
    for r in rpa:
        n = normaliza(r["bairro"])
        rpa_n[ALIAS_BAIRRO.get(n, n)] = int(r["rpa"])
    ev = collections.defaultdict(collections.Counter)
    for e in est:
        m = re.search(r"SANITARIO ([IVX]+)", e["dsDistrito"] or "")
        if m:
            n = normaliza(e["bairro"])
            ev[ALIAS_BAIRRO.get(n, n)][ROMANO[m.group(1)]] += 1
    out, avisos = [], []
    for b in bairros:
        n = normaliza(b["nome"])
        r = rpa_n.get(n)
        if r is None:
            raise ValueError(f"bairro sem RPA: {b['nome']}")
        cnes_ds = ev[n].most_common(1)[0][0] if ev[n] else None
        if r in (1, 2, 4, 5):
            ds, origem = r, "rpa"
            if cnes_ds is not None and cnes_ds != r:
                origem = "rpa_diverge_cnes"
                avisos.append(f"{b['nome']}: RPA {r}, UBS do CNES no DS {cnes_ds}")
        else:
            validos = (3, 7) if r == 3 else (6, 8)
            if cnes_ds in validos:
                ds, origem = cnes_ds, "cnes"
            else:
                ds, origem = DS_INFERIDO.get(n, r), "inferido"
                if cnes_ds is not None:
                    origem = "rpa_diverge_cnes"
                    avisos.append(f"{b['nome']}: RPA {r}, UBS do CNES no DS {cnes_ds}; mantido DS {ds}")
        out.append({"id_bairro": int(b["cd_bairro"][-3:]), "cd_bairro_ibge": b["cd_bairro"],
                    "nome_bairro": b["nome"], "rpa": r, "id_ds": ds, "origem_ds": origem,
                    "pop_residente": int(b["pop_residente"]), "dom_ocupados": int(b["dom_ocupados"]),
                    "moradores_dpp": int(b["moradores_dpp"]), "media_moradores": float(b["media_moradores"])})
    return out, avisos


def data_br(s):
    return dt.datetime.strptime(s, "%d/%m/%Y").date() if s else None


def ativa_em(q, d):
    return data_br(q["dtAtivacao"]) <= d and (not q["dtDesativacao"] or data_br(q["dtDesativacao"]) > d)


def processa_cnes(S, est, eq, bairros_t, dt_cnes, dt_ref):
    """Estrutura real (unidades, equipes) e parâmetros de conciliação."""
    F, T = "MS CNES", "CNES servicos"
    id_bairro = {normaliza(b["nome_bairro"]): b["id_bairro"] for b in bairros_t}
    ds_bairro = {b["id_bairro"]: b["id_ds"] for b in bairros_t}
    E = {e["cnes"]: e for e in est}
    por_cnes = collections.defaultdict(list)
    for q in eq:
        por_cnes[q["cnes"]].append(q)

    unidades, equipes, conc = [], [], []
    for c in sorted(E):
        e = E[c]
        ativas = [q for q in por_cnes[c] if not q["dtDesativacao"]]
        tipos = collections.Counter(q["tpEquipe"] for q in ativas)
        n = normaliza(e["bairro"])
        idb = id_bairro.get(ALIAS_BAIRRO.get(n, n))
        m = re.search(r"SANITARIO ([IVX]+)", e["dsDistrito"] or "")
        ds_cnes = ROMANO[m.group(1)] if m else None
        incl = not e["coMotivoDesab"] and any(t in TIPOS_EQUIPE_CADASTRO for t in tipos)
        if e["coMotivoDesab"]:
            motivo = f"desativada no CNES ({e['dsMotivoDesab']}, {e['nuCompDesab']})"
        elif not incl:
            motivo = "sem equipe ativa que faça cadastro individual (eSF, eAP, eCR, eAPP)"
        else:
            motivo = ""
        if incl and idb is None:
            raise ValueError(f"bairro do CNES não reconhecido: {e['bairro']} ({c})")
        if incl:
            if e["dsTpUnidade"] != "CENTRO DE SAUDE/UNIDADE BASICA":
                raise ValueError(f"tipo de unidade inesperado em {c}: {e['dsTpUnidade']}")
            unidades.append({"cnes": c, "nome_unidade": e["noFantasia"][:100], "tipo_unidade": 2,
                             "id_bairro": idb})
            for q in sorted(ativas, key=lambda q: q["coEquipe"]):
                if q["tpEquipe"] in TIPOS_EQUIPE_CADASTRO:
                    equipes.append({"ine": q["coEquipe"], "nome_equipe": q["nomeEquipe"][:60],
                                    "tipo_equipe": int(q["tpEquipe"]), "cnes": c})
        conc.append({"cnes": c, "nome": e["noFantasia"], "bairro_cnes": e["bairro"],
                     "id_bairro": "" if idb is None else idb,
                     "ds_cnes": "" if ds_cnes is None else ds_cnes,
                     "ds_bairro": "" if idb is None else ds_bairro[idb],
                     "esf": tipos["70"], "eap": tipos["76"], "ecr": tipos["73"], "eapp": tipos["74"],
                     "esb": tipos["71"], "emulti": tipos["72"],
                     "incluida": "sim" if incl else "não", "motivo_exclusao": motivo})

    # parâmetros: unidades e equipes ativas na data de referência, por DS e no município
    ds_unid = {u["cnes"]: ds_bairro[u["id_bairro"]] for u in unidades}
    cont = collections.Counter()
    for q in equipes:
        cont[(ds_unid[q["cnes"]], str(q["tipo_equipe"]))] += 1
    for ds in range(1, 9):
        nu = sum(1 for u in unidades if ds_unid[u["cnes"]] == ds)
        S.add("cnes_estrutura.csv", F, T, "ds", str(ds), "unidades_aps_ativas", "T", nu,
              dt_acesso=dt_cnes, unid="unidades", nota=f"Referência {dt_ref.isoformat()} (carga CNES)")
        for tp in sorted(TIPOS_EQUIPE_CADASTRO):
            S.add("cnes_estrutura.csv", F, T, "ds", str(ds), "equipes_ativas", f"tipo_equipe={tp}",
                  cont[(ds, tp)], dt_acesso=dt_cnes, unid="equipes")
    S.add("cnes_estrutura.csv", F, T, "municipio", MUNICIPIO_IBGE, "unidades_aps_ativas", "T",
          len(unidades), dt_acesso=dt_cnes, unid="unidades")
    for tp in sorted(TIPOS_EQUIPE_APS):
        n = sum(1 for c, lst in por_cnes.items() if not E[c]["coMotivoDesab"]
                for q in lst if q["tpEquipe"] == tp and not q["dtDesativacao"])
        S.add("cnes_estrutura.csv", F, T, "municipio", MUNICIPIO_IBGE, "equipes_ativas",
              f"tipo_equipe={tp}", n, dt_acesso=dt_cnes, unid="equipes")

    # série mensal de eSF + eAP ativas (último dia de cada competência), reconstruída das datas
    # de ativação e desativação do instantâneo atual – aproximação (ver documentação)
    hist = [q for q in eq if q["tpEquipe"] in TIPOS_EQUIPE_ESF_EAP]
    d = dt.date(2023, 1, 1)
    while d <= dt_ref:
        prox = dt.date(d.year + (d.month == 12), d.month % 12 + 1, 1)
        fim = min(prox - dt.timedelta(days=1), dt_ref)
        at = [q for q in hist if ativa_em(q, fim)]
        comp = f"competencia={d.year}{d.month:02d}"
        S.add("cnes_serie_equipes.csv", F, T, "municipio", MUNICIPIO_IBGE, "equipes_esf_eap_ativas", comp,
              len(at), dt_acesso=dt_cnes, unid="equipes", nota=f"Ativas em {fim.isoformat()}")
        S.add("cnes_serie_equipes.csv", F, T, "municipio", MUNICIPIO_IBGE, "unidades_com_esf_eap", comp,
              len({q["cnes"] for q in at}), dt_acesso=dt_cnes, unid="unidades")
        por_ds = collections.Counter(ds_bairro[id_bairro[ALIAS_BAIRRO.get(normaliza(E[q["cnes"]]["bairro"]),
                                                                        normaliza(E[q["cnes"]]["bairro"]))]]
                                     for q in at)
        for ds in range(1, 9):
            S.add("cnes_serie_equipes.csv", F, T, "ds", str(ds), "equipes_esf_eap_ativas", comp,
                  por_ds[ds], dt_acesso=dt_cnes, unid="equipes")
        d = prox

    historico = [{"ine": q["coEquipe"], "cnes": q["cnes"], "tipo_equipe": int(q["tpEquipe"]),
                  "cd_area": q["coArea"], "dt_ativacao": data_br(q["dtAtivacao"]).isoformat(),
                  "dt_desativacao": data_br(q["dtDesativacao"]).isoformat() if q["dtDesativacao"] else ""}
                 for q in sorted(eq, key=lambda q: (q["cnes"], q["coEquipe"]))
                 if q["tpEquipe"] in TIPOS_EQUIPE_APS]
    tipos_eq = sorted({(int(q["tpEquipe"]), q["dsEquipe"]) for q in eq})
    return unidades, equipes, conc, historico, tipos_eq


def processa_territorio(S, bairros_t, unidades, equipes, dt_sidra):
    F = "IBGE Censo 2022"
    for b in bairros_t:
        cd = b["cd_bairro_ibge"]
        for var, v, u in (("pop_residente", b["pop_residente"], "pessoas"),
                          ("dom_ocupados", b["dom_ocupados"], "domicílios"),
                          ("moradores_dpp", b["moradores_dpp"], "pessoas"),
                          ("media_moradores_dpp", b["media_moradores"], "pessoas por domicílio")):
            S.add("censo2022_territorio.csv", F, "SIDRA 9922/9923", "bairro", cd, var, "T", v,
                  dt_acesso=dt_sidra, unid=u, nota=b["nome_bairro"])
    ds_unid = {u["cnes"]: next(b["id_ds"] for b in bairros_t if b["id_bairro"] == u["id_bairro"])
               for u in unidades}
    for ds in range(1, 9):
        bs = [b for b in bairros_t if b["id_ds"] == ds]
        pop = sum(b["pop_residente"] for b in bs)
        dom = sum(b["dom_ocupados"] for b in bs)
        mor = sum(b["moradores_dpp"] for b in bs)
        neq = sum(1 for q in equipes if q["tipo_equipe"] in (70, 76) and ds_unid[q["cnes"]] == ds)
        S.add("censo2022_territorio.csv", F, "SIDRA 9922/9923", "ds", str(ds), "pop_residente", "T", pop,
              dt_acesso=dt_sidra, unid="pessoas", nota="Soma dos bairros do distrito (bairro → DS)")
        S.add("censo2022_territorio.csv", F, "SIDRA 9922/9923", "ds", str(ds), "dom_ocupados", "T", dom,
              dt_acesso=dt_sidra, unid="domicílios")
        S.add("censo2022_territorio.csv", F, "SIDRA 9922/9923", "ds", str(ds), "media_moradores_dpp", "T",
              mor / dom, dt_acesso=dt_sidra, unid="pessoas por domicílio")
        S.add("censo2022_territorio.csv", F, "SIDRA 9922/9923", "ds", str(ds), "n_bairros", "T", len(bs),
              dt_acesso=dt_sidra, unid="bairros")
        if neq:
            S.add("censo2022_territorio.csv", "Derivado Censo+CNES", "SIDRA 9923 + CNES", "ds", str(ds),
                  "pop_por_equipe_esf_eap", "T", pop / neq, dt_acesso=dt_sidra, unid="pessoas por equipe",
                  nota=f"{neq} eSF/eAP ativas no distrito")


def processa_literatura(S):
    """Parâmetros publicados (sem microdados): PNS 2019 e Spizzirri et al. (2021)."""
    F, T, D = "IBGE PNS 2019", "Orientacao sexual 2022", "2026-10-20"
    nota = "IBGE (2022), Orientação sexual autoidentificada da população adulta: PNS 2019"
    for cat, v in (("os=heterossexual", .948), ("os=homossexual", .012), ("os=bissexual", .007),
                   ("os=outra", .001), ("os=nao_sabe", .011), ("os=recusou", .023)):
        S.add("literatura_os_ig.csv", F, T, "pais", "BR", "prop_orientacao_18mais", cat, v, dt_acesso=D,
              unid="proporção", nota=nota)
    S.add("literatura_os_ig.csv", F, T, "pais", "BR", "prop_homo_bi_18mais", "T", .018, dt_acesso=D,
          unid="proporção", nota="2,9 milhões de adultos (1,8%)")
    S.add("literatura_os_ig.csv", F, T, "uf", "26", "prop_homo_bi_18mais", "T", .010, .010, .018,
          dt_acesso=D, tipo="sensibilidade", unid="proporção",
          nota="Pernambuco; intervalo PE a Brasil (Tabela 6); IC 95% da UF não extraído")
    for faixa, v in (("18-29", .048), ("30-39", .019), ("40-59", .010), ("60+", .002)):
        S.add("literatura_os_ig.csv", F, T, "pais", "BR", "prop_homo_bi_18mais", f"idade={faixa}", v,
              dt_acesso=D, unid="proporção", nota="Gradiente etário nacional (usar como razão relativa)")
    for raca, v in (("1", .018), ("2", .019), ("4", .019)):
        S.add("literatura_os_ig.csv", F, T, "pais", "BR", "prop_homo_bi_18mais", f"raca={raca}", v,
              dt_acesso=D, unid="proporção", nota="Sem diferença significativa entre brancos, pretos e pardos")
    S.add("literatura_os_ig.csv", F, T, "pais", "BR", "prop_recusa_nao_sabe_18mais", "T", .034, .02, .06,
          dt_acesso=D, tipo="sensibilidade", unid="proporção", nota="Não sabe (1,1%) + recusou (2,3%)")
    F2, T2, D2 = "Spizzirri et al. 2021", "Scientific Reports 2021", "2026-10-15"
    S.add("literatura_os_ig.csv", F2, T2, "pais", "BR", "prop_transgenero", "T", .0069, .0048, .0090,
          dt_acesso=D2, tipo="IC95", unid="proporção", nota="Amostra de 6.000 adultos; sem diferença regional")
    S.add("literatura_os_ig.csv", F2, T2, "pais", "BR", "prop_nao_binario", "T", .0119, .0092, .0147,
          dt_acesso=D2, tipo="IC95", unid="proporção")


def processa_premissas(S, sidra):
    """Premissas da Tabela 6 e correspondência da Tabela 7 (não são dados oficiais)."""
    FS, FP, D = "Premissa SESAU", "Premissa Projeto", "2026-10-20"
    S.add("premissas_gerador.csv", FS, "Reuniao 01/09/2026", "municipio", MUNICIPIO_IBGE, "cobertura_esf",
          "T", .80, .75, .90, dt_acesso=D, tipo="sensibilidade", unid="proporção",
          nota="Cadastrados / residentes; ajustar ao SISAB quando disponível")
    S.add("premissas_gerador.csv", FS, "Planilha monitoramento", "usf", "faixa", "prop_os_sim_dado_real",
          "T", .28, .03, .53, dt_acesso=D, tipo="faixa_observada", unid="proporção",
          nota="Ponto médio da faixa entre USF (~3% a ~53%); trocar pelas metas por USF quando autorizadas")
    S.add("premissas_gerador.csv", FS, "Planilha monitoramento", "usf", "linha3", "prop_os_sim_dado_real",
          "T", 2500 / 6613, dt_acesso=D, unid="proporção", nota="Exemplo conferido (linha 3 da planilha)")
    S.add("premissas_gerador.csv", FS, "Reuniao 01/09/2026", "municipio", MUNICIPIO_IBGE,
          "idade_min_elegivel_os_ig", "T", 11, 10, 11, dt_acesso=D, tipo="sensibilidade", unid="anos",
          nota="Regra do dado real; confirmar se 10 anos completos saem")
    for cen, v in (("nulo", 0.0), ("pequeno", 0.2), ("moderado", 0.5)):
        S.add("premissas_gerador.csv", FP, "Tabela 6", "municipio", MUNICIPIO_IBGE, "efeito_oficina_logito",
              f"cenario={cen}", v, dt_acesso=D, unid="log-odds",
              nota="PROPOSTA a validar pelo grupo: efeito sobre o logito de perguntar e registrar")
    for cen, v in (("baixa", 0.5), ("alta", 1.0)):
        S.add("premissas_gerador.csv", FP, "Tabela 6", "municipio", MUNICIPIO_IBGE,
              "dp_efeito_equipe_logito", f"cenario={cen}", v, dt_acesso=D, unid="log-odds",
              nota="PROPOSTA: desvio-padrão do efeito próprio da equipe dentro da USF")
    # Tabela 7 – prevalência por tipo do e-SUS a partir das dificuldades do Censo
    t = sidra["10127"]
    v = {r.split("\t")[3]: float(r.split("\t")[-2]) for r in t["rows"]}
    pop2 = next(float(r.split("\t")[-2]) for r in sidra["10125"]["rows"]
                if r.startswith("2611606\t11852\t2022\t6794\t95253\t"))
    tot = v["58771"]
    an, pe = v["73773"], v["73789"]
    regras = [("13", "Visual", v["73771"], None, None, "", "enxergar"),
              ("12", "Auditiva", v["73772"], None, None, "", "ouvir"),
              ("15", "Física", (max(an, pe) + an + pe) / 2, max(an, pe), an + pe, "limites",
               "andar ∪ pegar; sobreposição desconhecida → entre o maior e a soma"),
              ("14", "Intelectual/Cognitiva", v["73790"], None, None, "", "funções mentais (aproximação)")]
    for cod, nome, val, lo, hi, tipo, nota in regras:
        S.add("premissas_gerador.csv", FP, "Tabela 7 + SIDRA 10127", "municipio", MUNICIPIO_IBGE,
              "prev_tipo_deficiencia_esus", f"tipo={cod}", val / pop2,
              None if lo is None else lo / pop2, None if hi is None else hi / pop2, dt_acesso=D, tipo=tipo,
              unid="proporção", nota=f"{nome}: {nota}")
        S.add("premissas_gerador.csv", FP, "Tabela 7 + SIDRA 10127", "municipio", MUNICIPIO_IBGE,
              "dist_tipo_entre_pcd", f"tipo={cod}", val / tot,
              None if lo is None else lo / tot, None if hi is None else hi / tot, dt_acesso=D, tipo=tipo,
              unid="proporção", nota=f"{nome}: entre pessoas com deficiência (soma > 1, múltipla escolha)")
    S.add("premissas_gerador.csv", FP, "Tabela 7", "municipio", MUNICIPIO_IBGE, "dist_tipo_entre_pcd",
          "tipo=16", .03, .01, .05, dt_acesso=D, tipo="sensibilidade", unid="proporção",
          nota="Outra: sem equivalente no Censo; PROPOSTA de proporção residual")
    aut = next(float(r.split("\t")[-2]) for r in sidra["10147"]["rows"]
               if r.startswith("2611606\t13267\t2022\t95251\t"))
    popt = next(float(r.split("\t")[-2]) for r in sidra["10147"]["rows"]
                if r.startswith("2611606\t93\t2022\t95251\t"))
    S.add("premissas_gerador.csv", FP, "SIDRA 10147", "municipio", MUNICIPIO_IBGE,
          "prev_tipo_deficiencia_esus", "tipo=232", aut / popt, dt_acesso=D, unid="proporção",
          nota="TEA: autismo diagnosticado (Censo 2022) – correspondência nova, fora da Tabela 7")


def processa_cid10(raw, ledi_cid):
    cods = {}
    for nome, col in (("CID-10-CATEGORIAS.CSV", "CAT"), ("CID-10-SUBCATEGORIAS.CSV", "SUBCAT")):
        with open(os.path.join(raw, "cid10", nome), encoding="latin-1") as f:
            for r in csv.DictReader(f, delimiter=";"):
                c = r[col].strip()
                if c:
                    cods[c] = r["DESCRICAO"].strip()
    faltam = sorted(c for c in ledi_cid if c not in cods)
    return cods, faltam


def escreve_csv(caminho, cab, linhas):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cab)
        w.writerows(linhas)


def processar(raw, saida, ledi_dominios=None):
    sidra, bairros, rpa, est, eq, man_raw = le_raw(raw)
    arqs = man_raw.get("arquivos", {})
    dt_sidra = arqs.get("sidra_compact.json", {}).get("dt_acesso", "2026-10-20")
    dt_cnes = arqs.get("cnes_recife_aps.tsv", {}).get("dt_acesso", "2026-10-20")
    dt_ref = max(data_br(e["dtCarga"]) for e in est if e["dtCarga"])   # data da carga do CNES

    S = Saida()
    processa_sidra(S, sidra, dt_sidra)
    bairros_t, avisos = territorio(bairros, rpa, est)
    unidades, equipes, conc, historico, tipos_eq = processa_cnes(S, est, eq, bairros_t, dt_cnes, dt_ref)
    processa_territorio(S, bairros_t, unidades, equipes, dt_sidra)
    processa_literatura(S)
    processa_premissas(S, sidra)

    pdir = os.path.join(saida, "parametros")
    for arq, linhas in S.arquivos.items():
        escreve_csv(os.path.join(pdir, arq), COLUNAS, linhas)

    edir = os.path.join(saida, "estrutura")
    escreve_csv(os.path.join(edir, "distrito_sanitario.csv"), ["id_ds", "nome_ds"],
                [[i, NOME_DS[i]] for i in range(1, 9)])
    escreve_csv(os.path.join(edir, "bairro.csv"), ["id_bairro", "nome_bairro", "id_ds"],
                [[b["id_bairro"], b["nome_bairro"], b["id_ds"]] for b in bairros_t])
    escreve_csv(os.path.join(edir, "bairro_referencia.csv"),
                ["id_bairro", "cd_bairro_ibge", "nome_bairro", "rpa", "id_ds", "origem_ds"],
                [[b[k] for k in ("id_bairro", "cd_bairro_ibge", "nome_bairro", "rpa", "id_ds", "origem_ds")]
                 for b in bairros_t])
    escreve_csv(os.path.join(edir, "dom_tipo_unidade.csv"), ["codigo", "descricao"],
                [[2, "CENTRO DE SAUDE/UNIDADE BASICA"]])
    escreve_csv(os.path.join(edir, "dom_tipo_equipe.csv"), ["codigo", "descricao"], tipos_eq)
    escreve_csv(os.path.join(edir, "unidade_saude.csv"), ["cnes", "nome_unidade", "tipo_unidade", "id_bairro"],
                [[u[k] for k in ("cnes", "nome_unidade", "tipo_unidade", "id_bairro")] for u in unidades])
    escreve_csv(os.path.join(edir, "equipe.csv"), ["ine", "nome_equipe", "tipo_equipe", "cnes"],
                [[q[k] for k in ("ine", "nome_equipe", "tipo_equipe", "cnes")] for q in equipes])
    escreve_csv(os.path.join(edir, "equipe_historico.csv"),
                ["ine", "cnes", "tipo_equipe", "cd_area", "dt_ativacao", "dt_desativacao"],
                [[h[k] for k in ("ine", "cnes", "tipo_equipe", "cd_area", "dt_ativacao", "dt_desativacao")]
                 for h in historico])
    escreve_csv(os.path.join(edir, "conciliacao_cnes.csv"), list(conc[0].keys()),
                [list(c.values()) for c in conc])

    ledi_cid = []
    if ledi_dominios and os.path.exists(ledi_dominios):
        with open(ledi_dominios, encoding="utf-8") as f:
            ledi_cid = [c for c, _ in json.load(f)["dom_cid10"]]
    cid, faltam = processa_cid10(raw, ledi_cid)
    escreve_csv(os.path.join(edir, "dom_cid10.csv"), ["codigo", "descricao", "origem"],
                [[c, cid[c][:200], "LEDI" if c in ledi_cid else "DATASUS"] for c in sorted(cid)])

    # manifesto da versão
    man = {"versao": VERSAO, "gerado_em": dt.date.today().isoformat(), "referencia_cnes": dt_ref.isoformat(),
           "raw": arqs, "avisos_territorio": avisos, "cid10_ledi_ausentes_no_datasus": faltam, "arquivos": {}}
    for sub in ("parametros", "estrutura"):
        for nome in sorted(os.listdir(os.path.join(saida, sub))):
            p = os.path.join(saida, sub, nome)
            with open(p, encoding="utf-8") as f:
                n = sum(1 for _ in f) - 1
            man["arquivos"][f"{sub}/{nome}"] = {"linhas": n, "sha256": sha256_arquivo(p)}
    with open(os.path.join(saida, "manifesto.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=1)
    print(f"parametros: {sum(len(v) for v in S.arquivos.values())} linhas em {len(S.arquivos)} arquivos")
    print(f"estrutura: {len(bairros_t)} bairros, {len(unidades)} unidades, {len(equipes)} equipes, "
          f"{len(cid)} códigos CID-10 ({len(faltam)} do LEDI ausentes no DATASUS)")
    for a in avisos:
        print("  aviso:", a)
    return verificar(saida)


# ----------------------------------------------------------------------------------------
# 5. Fase "verificar"
# ----------------------------------------------------------------------------------------
def verificar(saida):
    pdir = os.path.join(saida, "parametros")
    P = []
    for nome in sorted(os.listdir(pdir)):
        with open(os.path.join(pdir, nome), encoding="utf-8") as f:
            P += [dict(r, arquivo=nome) for r in csv.DictReader(f)]
    falhas = []

    def ok(cond, msg):
        if not cond:
            falhas.append(msg)

    chaves = collections.Counter(tuple(r[k] for k in COLUNAS[:6]) for r in P)
    ok(max(chaves.values()) == 1, "chave primária repetida em parametros/")
    ok(all(r["valor"] != "" for r in P), "valor vazio")
    for r in P:
        if r["ic_inferior"] and r["ic_superior"]:
            ok(float(r["ic_inferior"]) <= float(r["valor"]) <= float(r["ic_superior"]),
               f"valor fora do intervalo: {r['variavel']} {r['categoria']}")

    def v(fonte, var, cat, nivel="municipio", cd=MUNICIPIO_IBGE, tab=None):
        xs = [float(r["valor"]) for r in P if r["fonte"] == fonte and r["variavel"] == var
              and r["categoria"] == cat and r["nivel"] == nivel and r["cd_territorio"] == cd
              and (tab is None or r["tabela_fonte"] == tab)]
        return xs[0] if xs else None

    F = "IBGE Censo 2022"
    total = v(F, "pop_residente", "sexo=T;idade=T", tab="SIDRA 9514")
    ok(total == 1488920, f"população total {total}")
    soma_idades = sum(float(r["valor"]) for r in P if r["tabela_fonte"] == "SIDRA 9514"
                      and re.fullmatch(r"sexo=T;idade=(\d+|100\+)", r["categoria"]))
    ok(soma_idades == total, f"soma das idades simples {soma_idades} ≠ {total}")
    sd = v(F, "pop_residente", "raca=SD", tab="SIDRA 9605")
    soma_raca = sum(v(F, "pop_residente", f"raca={c}", tab="SIDRA 9605") for c in "12345")
    ok(soma_raca + sd == total and sd < 0.0001 * total, f"soma por raça {soma_raca} + SD {sd}")
    soma_ipf = sum(float(r["valor"]) for r in P if r["tabela_fonte"] == "SIDRA 9606"
                   and re.fullmatch(r"raca=[1-5];sexo=[HM];idade=(\d+|100\+)", r["categoria"]))
    ok(soma_ipf == soma_raca, f"soma da semente 9606 {soma_ipf} ≠ {soma_raca}")
    pop_b = sum(float(r["valor"]) for r in P if r["nivel"] == "bairro" and r["variavel"] == "pop_residente")
    pop_ds = sum(float(r["valor"]) for r in P if r["nivel"] == "ds" and r["variavel"] == "pop_residente")
    ok(pop_b == total and pop_ds == total, f"bairros {pop_b} / distritos {pop_ds}")
    dom = v(F, "dom_ocupados", "T", tab="SIDRA 4712")
    dom_b = sum(float(r["valor"]) for r in P if r["nivel"] == "bairro" and r["variavel"] == "dom_ocupados")
    ok(dom == dom_b, f"domicílios município {dom} × bairros {dom_b}")
    prev = v(F, "prev_pcd", "sexo=T;idade=2+", tab="SIDRA 10125")
    ok(prev is not None and 0.08 <= prev <= 0.09, f"prevalência de deficiência {prev}")
    pp = v(F, "prop_pop_residente", "raca=2+4", tab="SIDRA 9605")
    ok(pp is not None and abs(pp - 0.608) < 0.001, f"pretos + pardos {pp}")
    prevs = [float(r["valor"]) for r in P if r["variavel"].startswith(("prev_", "prop_"))]
    ok(all(0 <= x <= 1 for x in prevs), "prevalência ou proporção fora de [0, 1]")
    aut = v(F, "prev_autismo", "sexo=T;idade=T", tab="SIDRA 10145")
    ok(aut is not None and 0.005 < aut < 0.03, f"prevalência de autismo {aut}")

    edir = os.path.join(saida, "estrutura")
    with open(os.path.join(edir, "unidade_saude.csv"), encoding="utf-8") as f:
        U = list(csv.DictReader(f))
    with open(os.path.join(edir, "equipe.csv"), encoding="utf-8") as f:
        Q = list(csv.DictReader(f))
    with open(os.path.join(edir, "bairro.csv"), encoding="utf-8") as f:
        B = list(csv.DictReader(f))
    ok(len(B) == 94 and len({b["nome_bairro"] for b in B}) == 94, "bairros")
    ok({b["id_ds"] for b in B} == {str(i) for i in range(1, 9)}, "todo distrito tem bairro")
    ok(len({u["cnes"] for u in U}) == len(U) and all(re.fullmatch(r"\d{7}", u["cnes"]) for u in U), "CNES")
    ok(len({q["ine"] for q in Q}) == len(Q) and all(re.fullmatch(r"\d{10}", q["ine"]) for q in Q), "INE")
    ok({q["cnes"] for q in Q} <= {u["cnes"] for u in U}, "equipe com unidade inexistente")
    ok({u["id_bairro"] for u in U} <= {b["id_bairro"] for b in B}, "unidade com bairro inexistente")
    neq = v("MS CNES", "equipes_ativas", "tipo_equipe=70") + v("MS CNES", "equipes_ativas", "tipo_equipe=76")
    ok(neq == sum(1 for q in Q if q["tipo_equipe"] in ("70", "76")), "equipes eSF/eAP")

    print("verificação:", "OK" if not falhas else f"{len(falhas)} falha(s)")
    for x in falhas:
        print("  ✗", x)
    return not falhas


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fase", choices=["coletar", "processar", "verificar"])
    ap.add_argument("--raw", default="raw")
    ap.add_argument("--saida", default=".")
    ap.add_argument("--ledi", default="dominios.json",
                    help="dominios.json da Etapa 4 (marca os 554 códigos CID-10 do LEDI)")
    a = ap.parse_args()
    if a.fase == "coletar":
        coletar(a.raw)
    elif a.fase == "processar":
        sys.exit(0 if processar(a.raw, a.saida, a.ledi) else 1)
    else:
        sys.exit(0 if verificar(a.saida) else 1)


if __name__ == "__main__":
    main()
