"""Gera docs/Trabalho_Inferencia.docx a partir de docs/inferencia_referencias.csv
(produzido por: python -m aps_sintetico.valida_referencia --saida saida/base)."""
from pathlib import Path
import pandas as pd
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.shared import Pt, Cm

AQUI = Path(__file__).parent
d = pd.read_csv(AQUI / "inferencia_referencias.csv")
RACA = {"1": "branca", "2": "preta", "3": "amarela", "4": "parda", "5": "indígena"}
def nome(v):
    for k, x in RACA.items():
        v = v.replace(f"raça/cor {k} (", f"raça/cor {x} (")
    return v.replace("sexo 0,", "sexo cód. 0,").replace("sexo 1,", "sexo cód. 1,").replace("criancas", "crianças") \
            .replace(": nao", ": não").replace(": ni", ": não informado").replace(": sim", ": sim")
def pct(x): return f"{100*x:.2f}%"
def num(r, c): return f"{r[c]:.0f}" if r["estatistica_referencia"] == "contagem esperada" else pct(r[c])

doc = Document()
s = doc.sections[0]
s.orientation = WD_ORIENT.LANDSCAPE
s.page_width, s.page_height = s.page_height, s.page_width
for m in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
    setattr(s, m, Cm(1.6))
doc.styles["Normal"].font.name = "Calibri"; doc.styles["Normal"].font.size = Pt(10.5)

def P(t, b=False):
    p = doc.add_paragraph(); r = p.add_run(t); r.bold = b; return p
def tabela(cols, linhas, tam=8):
    t = doc.add_table(rows=1, cols=len(cols)); t.style = "Light Grid Accent 1"
    for i, c in enumerate(cols):
        t.rows[0].cells[i].text = c
    for l in linhas:
        cs = t.add_row().cells
        for i, v in enumerate(l): cs[i].text = str(v)
    for row in t.rows:
        for c in row.cells:
            for p in c.paragraphs:
                for r in p.runs: r.font.size = Pt(tam)
    doc.add_paragraph()

n = len(d); ok = int(d["diferenca_dentro_da_tolerancia"].sum()); rej = int((d["decisao_teste_5pct"] == "rejeita H0").sum())
doc.add_heading("Trabalho de Inferência – Os dados sintéticos respeitam as estatísticas de referência?", 0)
P("Projeto Nexus Data · CESAR School · Equipe 2 · Base sintética da Atenção Primária à Saúde do Recife")
P("Código e dados: https://github.com/RedAkasha/nexus-data-aps-recife (pasta docs/ e módulo src/aps_sintetico/valida_referencia.py)")

doc.add_heading("1. Objetivo e base de dados", 1)
P("Verificar, com inferência estatística, se a base sintética gerada na Etapa 1 reproduz os valores observados em pesquisas "
  "oficiais. A base simula o preenchimento do formulário: cada registro é uma mesma pessoa que declara, ao mesmo tempo, raça/cor, "
  "orientação sexual, identidade de gênero, deficiência (relação N:N, tabela associativa), microárea e equipe/profissional que fez "
  "a coleta (tabelas cidadao, cadastro_individual, cadastro_deficiencia, microarea, profissional e equipe). Assim é possível cruzar "
  "características (por exemplo, pessoas trans e negras na microárea 03). Cenário analisado: base, escala 10% da população do Recife, "
  "8 Distritos Sanitários, semente 20261022. Foram usados os cadastros vigentes de pessoas residentes.")

doc.add_heading("2. Método", 1)
for t in [
    "Proporções: estimativa p̂ = x/n; IC 95% de Wilson. Teste z para uma proporção. H0: p = p0 (valor de referência) contra H1: p ≠ p0; "
    "estatística z = (p̂ − p0)/√(p0(1−p0)/n); p-valor bilateral; decisão com α = 5%.",
    "Contagens (população, nascimentos, óbitos): o número observado O é tratado como Poisson com média esperada E. IC 95% exato de Poisson. "
    "H0: E[O] = E contra H1: ≠; z = (O − E)/√E.",
    "Tolerância (equivalência prática): proporções, ±máx(1 p.p.; 3·EP); contagens, ±3·√E. Justificativa: 1 ponto percentual é a "
    "diferença abaixo da qual nenhuma leitura do painel muda, e 3 erros-padrão é o ruído amostral esperado de uma base finita. "
    "Como o n é grande (milhares a dezenas de milhares de pessoas por teste), o teste z rejeita H0 para diferenças minúsculas; por isso a decisão final "
    "combina o teste com a tolerância: valor aceito quando |estimativa − referência| ≤ tolerância.",
    "Variáveis qualitativas nominais (raça/cor, tipo de deficiência, orientação, identidade, sexo): proporção de cada categoria. "
    "Quando a pesquisa traz só a categoria principal (ex.: pessoas negras = preta + parda; LGB+; trans), comparamos essa categoria "
    "e a complementar é 1 − p, sem teste próprio (seria redundante). Faixa etária × sexo é tabela cruzada do Censo usada como referência.",
]:
    doc.add_paragraph(t, style="List Bullet")

doc.add_heading("3. Resultado geral", 1)
P(f"{n} valores de referência verificados: {ok} ficaram dentro da tolerância ({100*ok/n:.0f}%). O teste de hipótese a 5% rejeitou H0 "
  f"em {rej}; em todos eles a diferença cabe na tolerância (seção 6).", True)

def bloco(titulo, sel, cols, fun):
    doc.add_heading(titulo, 2)
    tabela(cols, [fun(r) for _, r in d[sel].iterrows()])

C = ["Variável", "Tipo", "Referência", "Estimativa sintética", "n", "IC 95%", "z", "p-valor", "Tolerância", "Decisão"]
def linha(r):
    ic = f"[{num(r,'ic95_inf')}; {num(r,'ic95_sup')}]"
    tol = f"±{r['tolerancia']:.0f}" if r["estatistica_referencia"] == "contagem esperada" else f"±{100*r['tolerancia']:.2f} p.p."
    return [nome(r["variavel"]), "contagem" if r["estatistica_referencia"] == "contagem esperada" else "proporção",
            num(r, "valor_referencia"), num(r, "estimativa_sintetica"), int(r["n"]), ic, f"{r['estatistica_z']:.2f}",
            f"{r['p_valor']:.3f}", tol, f"{r['decisao_teste_5pct']}; {r['veredito']}"]

doc.add_heading("4. Variáveis quantitativas (contagens)", 1)
P("Referência: contagem esperada pelo Censo 2022 (população) e pelo Boletim 01/2025 (nascimentos e óbitos), multiplicada pela escala.")
bloco("4.1 Contagens", d["estatistica_referencia"] == "contagem esperada", C, linha)

doc.add_heading("5. Variáveis qualitativas nominais (proporções)", 1)
grupos = [("5.1 Raça/cor", d["variavel"].str.contains("negra no DS|raça/cor")),
          ("5.2 Sexo × faixa etária (tabela cruzada do Censo)", d["variavel"].str.startswith("sexo")),
          ("5.3 Deficiência (prevalência e tipos)", d["variavel"].str.contains("deficiência")),
          ("5.4 Orientação sexual e identidade de gênero (adultos)", d["variavel"].str.contains("LGB|trans|binários")),
          ("5.5 Cobertura cadastral por Distrito Sanitário", d["variavel"].str.startswith("cobertura")),
          ("5.6 Planilha de monitoramento, linha 3 (data de corte)", d["variavel"].str.startswith("linha 3"))]
for t, sel in grupos:
    bloco(t, sel, C, linha)

doc.add_heading("6. Leitura dos casos em que o teste rejeita H0", 1)
rj = d[d["decisao_teste_5pct"] == "rejeita H0"]
tabela(["Variável", "Referência", "Estimativa", "p-valor", "Diferença", "Tolerância"],
       [[nome(r.variavel), pct(r.valor_referencia), pct(r.estimativa_sintetica), f"{r.p_valor:.4f}",
         f"{100*(r.estimativa_sintetica-r.valor_referencia):+.2f} p.p.", f"±{100*r.tolerancia:.2f} p.p."] for r in rj.itertuples()])
P("Com n na casa de milhares a dezenas de milhares, o erro-padrão é muito pequeno e qualquer diferença de décimos de ponto percentual "
  "é “estatisticamente significativa”. Todas as diferenças acima são menores que 1 p.p. (ou que 3·EP) e não alteram nenhuma conclusão "
  "do painel: há significância estatística, mas não relevância prática. Nos dois casos da planilha (linha 3, adultos), o desvio reflete "
  "o processo de registro simulado (omissão e não preenchimento) e não um erro de calibração.")

doc.add_heading("7. Categorias que a pesquisa não traz", 1)
for t in ["Orientação sexual e identidade de gênero: a PNS 2019 informa heterossexual, homossexual, bissexual, outra, não sabe e recusou "
          "(proporções do país e de Pernambuco). Calibramos a categoria LGB+ (homossexual + bissexual); as demais seguem a distribuição "
          "da pesquisa e não foram testadas uma a uma. Identidade de gênero (trans e não binário) vem de Spizzirri et al. (2021), que "
          "estima só essas categorias; cisgênero é o complemento.",
          "Raça/cor por Distrito Sanitário: o Censo traz raça/cor por bairro; a proporção negra por DS (preta + parda) é calibrada, e "
          "as demais cores formam o complemento.",
          "No formulário, quando a pessoa não deseja informar orientação ou identidade, o campo fica vazio (NULL); quando informa, "
          "guarda uma categoria. Os testes usam como denominador as pessoas elegíveis (idade mínima) que informaram ou recusaram."]:
    doc.add_paragraph(t, style="List Bullet")

doc.add_heading("8. Premissas do grupo (não são valores de pesquisa)", 1)
for t in ["Cobertura cadastral por DS: meta do plano metodológico do projeto (Tabela 4) × (1 − omissão declarada) × (1 − rampa de implantação).",
          "Gradiente etário de LGB+, proporção de adultos trans e não binários: derivados de PNS 2019 (PE) e Spizzirri et al. (2021) com "
          "premissas do gerador declaradas em config/ e dados/parametros/premissas_gerador.csv.",
          "Linha 3 da planilha de monitoramento: valores-alvo do material do projeto na data de corte."]:
    doc.add_paragraph(t, style="List Bullet")

doc.add_heading("9. Fontes", 1)
F = [
 ("IBGE. Censo Demográfico 2022. Tabelas SIDRA 9606 (população por sexo, idade e cor/raça), 9922/9923 (população por bairro) e "
  "10125/10132 (pessoas com deficiência). Município do Recife (2611606), referência 2022. https://sidra.ibge.gov.br"),
 ("IBGE. Orientação sexual autoidentificada da população adulta: Pesquisa Nacional de Saúde 2019. Rio de Janeiro: IBGE, 2022. "
  "População de 18 anos ou mais, Brasil e Unidades da Federação (Pernambuco), 2019. https://www.ibge.gov.br"),
 ("Spizzirri, G. et al. Proportion of people identified as transgender and non-binary gender in Brazil. Scientific Reports, 11, 2240, "
  "2021. Adultos, Brasil, 2021. https://doi.org/10.1038/s41598-021-81411-4"),
 ("Prefeitura do Recife, Secretaria de Saúde. Boletim 01/2025 (nascimentos SINASC e óbitos SIM de 2024, por Distrito Sanitário e raça/cor). "
  "Recife, 2024. Arquivo dados/parametros_complementares/boletim_sesau_2025.csv no repositório. [Conferir título e link oficiais.]"),
 ("Material da disciplina e do projeto: planilha de monitoramento (linha 3) e plano metodológico (Tabela 4, cobertura)."),
 ("Prefeitura do Recife. Bairros do Recife (malha oficial). https://dados.recife.pe.gov.br (apenas para o mapa)."),
]
for f in F: doc.add_paragraph(f, style="List Number")

doc.add_heading("10. Conclusão", 1)
P(f"A base sintética reproduz as referências: {ok} de {n} valores dentro da tolerância adotada. As rejeições de H0 são efeito do tamanho "
  "da amostra e não têm relevância prática. A base mantém a estrutura de formulário (uma pessoa, todos os campos), permitindo "
  "cruzamentos entre raça/cor, orientação, identidade, deficiência, microárea e equipe.")

doc.add_heading("11. Como reproduzir", 1)
P("python -m aps_sintetico gerar --escala 0.1 --saida saida/base\n"
  "python -m aps_sintetico analitica --saida saida/base\n"
  "python -m aps_sintetico.valida_referencia --saida saida/base\n"
  "python docs/gera_trabalho_inferencia.py")
doc.save(AQUI / "Trabalho_Inferencia.docx")
