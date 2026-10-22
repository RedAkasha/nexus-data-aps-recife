---
documento: Parâmetros oficiais — Emulação de dados da APS para as políticas de equidade do Recife
projeto: Projeto 3 – Dados (CESAR School, 2026.2) · Equipe 2 – Nexus Data
etapa: Etapa 5 – Coleta dos parâmetros oficiais
versao: 1.0.0
data: 2026-10-20
status: rascunho para revisão do grupo
arquivos:
  - coleta_parametros.py (coletor e processador; só biblioteca padrão do Python)
  - gen_carga.py (gera os scripts SQL a partir dos CSV)
  - parametros/*.csv (13 arquivos, 6.032 linhas, formato de analitica.ref_parametro_oficial)
  - estrutura/*.csv (território, unidades, equipes, tipos do CNES, CID-10)
  - raw/ (instantâneos das fontes, com manifesto_raw.json)
  - manifesto.json (versão, linhas e SHA-256 de cada CSV)
  - 04_carga_estrutura.sql (os dois SGBD)
  - 05_carga_parametros.sql (os dois SGBD)
base: Emulacao_Dados_APS_Recife_Projeto3_v3 (Etapa 5, Tabelas 5, 6 e 7); modelo_logico.md v1.0.0; documentacao_fisica.md v1.0.0
---

# Parâmetros oficiais — Etapa 5

A Etapa 5 do plano pede quatro coisas: baixar do SIDRA as marginais do Recife, baixar do CNES a estrutura de unidades e equipes e conciliá-la com a planilha da SESAU, processar os dados da PNAD Contínua e da PNS 2019 e salvar tudo em CSV versionados, com fonte, data de acesso e intervalo de incerteza. Pede também o coletor automático do SIDRA (o *scraper* da Sprint 1). Este documento descreve o que foi coletado, como, o que mudou nos parâmetros iniciais da Tabela 6 e o que ficou pendente.

Resumo do que saiu:

- **14 tabelas do SIDRA** (Censo 2022), entre elas as cinco pedidas no plano (9514, 9605, 10125, 10127, 10132) e duas no nível de bairro (9922 e 9923), que o plano não conhecia.
- **Estrutura real do CNES**: 153 unidades e 432 equipes ativas em 13/10/2026, com INE real, além do histórico de ativação de 809 equipes.
- **Território**: 94 bairros com população, domicílios e moradores, ligados a RPA e a Distrito Sanitário.
- **CID-10 completa** do DATASUS (14.233 códigos), o que resolve a pendência F2 da Etapa 4.
- **Tipos de unidade e de equipe** do CNES, o que resolve a pendência F1.
- **Parâmetros de literatura** (PNS 2019 e Spizzirri et al., 2021) e **premissas** do gerador no mesmo formato, cada uma marcada como tal.
- Carga testada no **PostgreSQL 16.15** e no **MySQL 8.0.46**, com conteúdo idêntico nos dois.

## 1. Como executar

O coletor tem três fases. Só a primeira usa a rede.

```
python3 coleta_parametros.py coletar      # baixa as fontes para raw/ (SIDRA, CNES, Prefeitura, CID-10)
python3 coleta_parametros.py processar    # lê raw/ e gera parametros/, estrutura/ e manifesto.json
python3 coleta_parametros.py verificar    # confere totais e chaves (roda também ao fim de processar)
python3 gen_carga.py                      # gera out/04_carga_estrutura.sql e out/05_carga_parametros.sql
```

A separação é proposital: o que vai para o banco sai sempre de um instantâneo guardado em `raw/`, com data de acesso e SHA-256 em `raw/manifesto_raw.json`. Rodar `processar` duas vezes sobre o mesmo `raw/` gera arquivos idênticos, byte a byte (conferido pelos hashes do `manifesto.json`). Para atualizar os parâmetros, roda-se `coletar` de novo e compara-se o manifesto novo com o antigo.

Ordem da carga no banco, depois dos scripts da Etapa 4:

```
01_ddl → 02_carga_dominios → 04_carga_estrutura → 05_carga_parametros → 03_validacao_carga
```

No MySQL, use `--default-character-set=utf8mb4`, como na Etapa 4. O `04` esvazia e recarrega as tabelas de território, unidade e equipe; por isso roda antes de qualquer dado gerado.

**Como os dados foram obtidos nesta versão.** O ambiente de trabalho do grupo não alcança os sites do governo pela linha de comando, então a coleta de 20/10/2026 foi feita no navegador, com as mesmas URLs e os mesmos filtros que o `coletar` usa (seção 2), e os instantâneos foram transferidos compactados e conferidos por SHA-256. As funções que convertem a resposta das APIs no formato dos instantâneos foram testadas sem rede. A fase `coletar` em si ainda não rodou de ponta a ponta numa máquina com acesso direto; é o primeiro teste a fazer (pendência E1).

## 2. Fontes coletadas

| Fonte | Acesso | O que entrou | Data de acesso |
|---|---|---|---|
| IBGE, Censo 2022, SIDRA | API `apisidra.ibge.gov.br`, município 2611606 | Tabelas 9514, 9605, 9606, 4712, 10125, 10127, 10132, 10145, 10147, 10061, 10296, 10300 | 20/10/2026 |
| IBGE, Censo 2022, SIDRA (bairros) | API SIDRA, nível 102 (bairro) dentro do município | Tabelas 9922 (domicílios e moradores) e 9923 (população) dos 94 bairros | 20/10/2026 |
| Ministério da Saúde, CNES | Serviços JSON de `cnes.datasus.gov.br` (estabelecimentos, ficha, equipes) | 430 estabelecimentos públicos; 161 UBS ou unidades com equipe de APS; 809 equipes | 20/10/2026 (carga do CNES de 13/10/2026) |
| Prefeitura do Recife, dados abertos | API CKAN de `dados.recife.pe.gov.br`, recurso “Bairros e RPAs do Recife” | 94 bairros e a RPA de cada um | 20/10/2026 |
| DATASUS, CID-10 | CSV oficiais de categorias e subcategorias (espelho no GitHub) | 2.045 categorias e 12.188 subcategorias | 20/10/2026 |
| IBGE, PNS 2019 | Publicação *Orientação sexual autoidentificada da população adulta* (2022) | Proporções nacionais, de Pernambuco, por idade e por cor ou raça | 20/10/2026 |
| Spizzirri et al. (2021) | *Scientific Reports*, v. 11, 2021 | Proporção de pessoas trans e não binárias, com IC 95% | 15/10/2026 (plano) |

Do CNES ficam só dados do estabelecimento e da equipe. A ficha do estabelecimento devolve também o CPF do diretor clínico, telefone e e-mail; esses campos são descartados na própria coleta e não estão em `raw/`. Nenhum nome de profissional é coletado.

O SIDRA marca zero absoluto com “-”; o coletor converte para 0. As tabelas de deficiência, autismo, instrução e rendimento vêm da amostra do Censo; o SIDRA não publica o erro amostral delas, então os parâmetros saem sem intervalo (seção 8).

## 3. Formato dos CSV

Cada arquivo de `parametros/` tem as dez colunas de `analitica.ref_parametro_oficial` e mais três de documentação:

| Coluna | Conteúdo |
|---|---|
| `fonte` | Ex.: `IBGE Censo 2022`, `MS CNES`, `IBGE PNS 2019`, `Premissa SESAU`, `Premissa Projeto` |
| `tabela_fonte` | Ex.: `SIDRA 9606`, `CNES servicos`, `Tabela 7 + SIDRA 10127` |
| `nivel` | `municipio`, `ds`, `bairro`, `uf`, `pais`, `usf` |
| `cd_territorio` | Código IBGE do município ou do bairro, número do DS, `26` (PE), `BR` |
| `variavel` | Ex.: `pop_residente`, `prev_pcd`, `equipes_ativas`, `cobertura_esf` |
| `categoria` | Combinação de dimensões no formato `chave=valor;chave=valor` (ex.: `raca=4;sexo=M;idade=37`); `T` = total |
| `valor`, `ic_inferior`, `ic_superior` | Valor central e intervalo, quando existe |
| `dt_acesso` | Data de acesso à fonte |
| `tipo_intervalo` | `IC95`, `sensibilidade`, `faixa_observada` ou `limites` |
| `unidade`, `nota` | Unidade e observação (não vão para o banco) |

Os códigos de cor ou raça e de tipo de deficiência nas categorias já são os do e-SUS (1 branca, 2 preta, 3 amarela, 4 parda, 5 indígena; `SD` = sem declaração). Assim o gerador compara o que gera com o parâmetro sem tabela de tradução. Sexo usa `H`, `M` e `T`; idade usa o ano simples (`37`), a faixa (`5-9`) ou o limite aberto (`100+`).

| Arquivo | Linhas | Conteúdo |
|---|---:|---|
| `censo2022_pop_sexo_idade.csv` | 366 | Sexo × idade simples e grupos quinquenais (9514) |
| `censo2022_pop_raca_sexo_idade.csv` | 2.196 | Cor ou raça × sexo × idade (9606), a semente do IPF |
| `censo_pop_raca.csv` | 26 | Cor ou raça em 2010 e 2022, contagem e proporção (9605) |
| `censo2022_domicilios.csv` | 3 | Domicílios, moradores e média do município (4712) |
| `censo2022_deficiencia.csv` | 279 | Deficiência por sexo e idade (10125), por tipo (10127), por cor ou raça (10132) |
| `censo2022_autismo.csv` | 216 | Autismo diagnosticado por sexo e idade (10145) e por cor ou raça (10147) |
| `censo2022_instrucao.csv` | 1.710 | Instrução de 18+ por idade, sexo e cor ou raça (10061) |
| `censo2022_renda.csv` | 276 | Rendimento domiciliar per capita por sexo e cor ou raça (10296) e por força de trabalho (10300) |
| `censo2022_territorio.csv` | 416 | População, domicílios e moradores por bairro e por DS; população por equipe |
| `cnes_estrutura.csv` | 47 | Unidades e equipes ativas por DS e no município |
| `cnes_serie_equipes.csv` | 460 | eSF + eAP ativas por competência, jan/2023 a out/2026 |
| `literatura_os_ig.csv` | 18 | PNS 2019 e Spizzirri et al. (2021) |
| `premissas_gerador.csv` | 19 | Premissas da Tabela 6 e correspondência da Tabela 7 |

`estrutura/` tem os registros que vão direto para o núcleo (`distrito_sanitario`, `bairro`, `unidade_saude`, `equipe`, `dom_tipo_unidade`, `dom_tipo_equipe`, `dom_cid10`) e três arquivos de referência que não são carregados: `bairro_referencia.csv` (código IBGE, RPA e origem do DS de cada bairro), `equipe_historico.csv` (datas de ativação e desativação) e `conciliacao_cnes.csv` (uma linha por estabelecimento, com o motivo de inclusão ou exclusão).

## 4. Censo 2022: o que os dados mostram

**População.** O Recife tem 1.488.920 residentes: 683.536 homens e 805.384 mulheres. As idades simples somam exatamente o total (conferido pelo `verificar`). Crianças de 0 a 10 anos, que saem do “dado real” da planilha, são 192.273 (12,9%); adultos de 18 anos ou mais são 78,5%; pessoas de 60 anos ou mais, 17,7%.

**Cor ou raça.**

| Categoria | 2010 | 2022 |
|---|---:|---:|
| Branca | 41,4% | 38,8% |
| Preta | 8,3% | 12,3% |
| Parda | 49,1% | 48,5% |
| Amarela | 0,96% | 0,18% |
| Indígena | 0,24% | 0,18% |
| Pretos + pardos | 57,4% | 60,8% |

A proporção de amarelos caiu de quase 1% para 0,18% entre os dois censos. É a referência para o caso de concentração anômala de registros “amarela” relatado pela Secretaria. A tabela 9606 traz 47 pessoas sem declaração de cor ou raça; elas ficam numa linha própria (`raca=SD`), e a semente do IPF soma 1.488.873.

**Deficiência.** São 122.531 pessoas com deficiência entre 1.460.199 de 2 anos ou mais (8,39%). A prevalência é maior nas mulheres (9,6%) que nos homens (6,9%), sobe com a idade (1,9% de 2 a 4 anos, 4,0% de 15 a 19, 21,1% a partir de 60 e 32,0% de 80 a 84) e varia por cor ou raça (7,7% em brancos, 8,5% em pardos, 9,9% em pretos e 10,7% em indígenas). Essas relações entram no DAG do gerador (idade → deficiência; cor ou raça → deficiência) com fonte citada.

**Autismo.** O Censo 2022 perguntou por diagnóstico de autismo: 1,42% dos residentes (1,80% dos homens, 1,10% das mulheres). O e-SUS tem o tipo de deficiência “TEA” (código 232), que a Tabela 7 do plano não previa. A correspondência foi acrescentada (seção 6).

**Domicílios.** São 547.461 domicílios particulares permanentes ocupados, com 2,70 moradores em média. A Etapa 4 usou 2,79, a média nacional; o volume estimado de `domicilio` e `familia` cresce cerca de 3%, dentro da margem já declarada (pendência F4, resolvida em parte). A média por bairro vai de 1,89 (Soledade) a 3,30 (Pau Ferro).

**Instrução, rendimento e trabalho.** Entre adultos de 18 anos ou mais, 22,8% não têm instrução ou não completaram o fundamental e 26,1% têm superior completo. O superior completo é de 39,2% entre brancos, 18,7% entre pardos e 14,1% entre pretos. No rendimento domiciliar per capita, 34,9% dos moradores vivem com até meio salário mínimo (incluídos os sem rendimento); entre pretos e pardos são cerca de 41%, entre brancos 25%. A taxa de desocupação de 14 anos ou mais é de 7,9%. Esses cruzamentos substituem, no nível do município, os microdados da PNAD Contínua (seção 8).

## 5. Estrutura real: unidades, equipes e território

### 5.1 Unidades e equipes do CNES

Dos 4.728 estabelecimentos do Recife no CNES, 430 são da administração pública. Desses, 161 são unidades básicas ou têm equipe de APS. Entram no banco as **153 unidades ativas com pelo menos uma equipe que faz cadastro individual** e as **432 equipes ativas desses tipos**:

| Tipo de equipe (código CNES) | Equipes ativas | Entra em `nucleo.equipe` |
|---|---:|---|
| ESF – Saúde da Família (70) | 414 | sim |
| EAP – Atenção Primária (76) | 2 | sim |
| eCR – Consultório na Rua (73) | 6 | sim |
| eAPP – Atenção Primária Prisional (74) | 10 | sim |
| ESB – Saúde Bucal (71) | 332 | não (não faz cadastro individual) |
| eMulti (72) | 20 | não |

As oito unidades que ficam de fora estão em `conciliacao_cnes.csv`: cinco desativadas no CNES entre 2023 e 2025 (USF Coelhos I, USF Santana, CS Boa Vista, CS João de Barros e a UBS Prisional PAMFA) e três sem equipe de cadastro (a Unidade de Cuidados Integrais Guilherme Abath, o DSEI Pernambuco e o ambulatório do Presídio Aníbal Bruno).

As seis eCR não têm unidade própria no CNES: estão vinculadas a seis USF (Romero Marques Ipiranga, Coelhos, Nossa Senhora do Pilar, Guilherme Robalinho, União das Vilas e Casarão do Cordeiro). As dez eAPP estão em quatro UBS prisionais. As 149 unidades com eSF ou eAP têm de uma a oito equipes; as mais comuns têm duas (52 unidades), três (31) ou quatro (33).

| Distrito | Bairros | População | Unidades | eSF + eAP | Pessoas por eSF/eAP |
|---|---:|---:|---:|---:|---:|
| DS I | 11 | 73.764 | 10 | 23 | 3.207 |
| DS II | 18 | 210.249 | 21 | 61 | 3.447 |
| DS III | 16 | 130.201 | 9 | 24 | 5.425 |
| DS IV | 12 | 281.986 | 24 | 63 | 4.476 |
| DS V | 16 | 246.058 | 26 | 71 | 3.466 |
| DS VI | 5 | 244.453 | 15 | 44 | 5.556 |
| DS VII | 13 | 173.680 | 23 | 69 | 2.517 |
| DS VIII | 3 | 128.529 | 25 | 61 | 2.107 |
| **Recife** | **94** | **1.488.920** | **153** | **416** | **3.579** |

A relação entre residentes e equipes varia mais de duas vezes entre os distritos. Isso tem consequência direta para o gerador: com cerca de 3 mil cadastrados por equipe, os DS III e VI (Casa Forte, Graças, Boa Viagem, Pina) não podem ter cobertura perto de 80%, e os DS VII e VIII ficam perto de 100%. A cobertura deve ser sorteada por distrito ou por bairro, a partir da capacidade das equipes, e não como 80% uniforme. Com 80% de cobertura no município (Tabela 6), seriam 1.191.136 cadastrados, ou 2.863 por eSF/eAP.

### 5.2 Conciliação com o plano e com a planilha

| Número | Origem | Situação |
|---|---|---|
| 141 USF e 384 equipes | Documento de apresentação do desafio | O CNES tinha 379 eSF + eAP em 01/01/2024 e 148 unidades; a contagem do desafio parece ser de 2023–2024 |
| 143 a 144 linhas | Planilha da SESAU, JUL–SET 2025 | Em 30/09/2025, o CNES tinha 149 unidades com eSF/eAP e 424 eSF + eAP; mais as 4 UBS prisionais e as eCR, que a planilha separa em abas próprias |
| 153 unidades e 432 equipes | CNES, carga de 13/10/2026 | É a estrutura carregada no banco |

O número de eSF + eAP ativas, reconstruído das datas de ativação e desativação, foi de 324 em jan/2023, 379 em jan/2024, 419 em jan/2025, 424 em set/2025 e 416 em out/2026 (`cnes_serie_equipes.csv`). O crescimento de quase cem equipes em 2023–2024 é real e precisa aparecer na dinâmica do gerador: equipes novas começam com cadastro pequeno, o que interessa diretamente ao problema de regressão.

A série é uma aproximação. Ela parte do instantâneo atual, então não vê equipes excluídas do CNES nem mudanças de tipo de equipe. Para uma série exata, é preciso baixar os arquivos mensais de equipes do FTP do DATASUS (pendência E3).

A conciliação linha a linha com a planilha depende de ter a lista de CNES das 143–144 linhas. Com ela, basta cruzar com `conciliacao_cnes.csv` (pendência E4).

### 5.3 Bairros e distritos sanitários

O IBGE publica, para o Censo 2022, população e domicílios dos 94 bairros oficiais do Recife (tabelas 9922 e 9923). A soma dos bairros bate com o município: 1.488.920 pessoas e 547.461 domicílios. A Prefeitura publica a RPA de cada bairro, mas não o distrito sanitário. O distrito foi obtido assim:

1. Nas RPA 1, 2, 4 e 5, o distrito é o de mesmo número (57 bairros).
2. As RPA 3 e 6 se dividem em dois distritos cada (III e VII; VI e VIII). Nelas, o distrito vem das UBS do bairro no CNES, que registra o distrito de cada unidade (26 bairros).
3. Dez bairros das RPA 3 e 6 não têm UBS. Para eles, o distrito foi inferido pela vizinhança: Brejo da Guabiraba e Pau Ferro no DS VII; Aflitos, Casa Forte, Derby, Jaqueira, Monteiro, Parnamirim, Santana e Tamarineira no DS III.
4. Graças tem uma UBS que o CNES registra no DS I. O bairro foi mantido no DS III, o da sua RPA, e a unidade fica ligada ao bairro.

O resultado fecha com a divisão conhecida: DS VI com cinco bairros (Boa Viagem, Brasília Teimosa, Imbiribeira, Ipsep e Pina), DS VIII com três (Cohab, Ibura e Jordão) e DS VII com treze. A origem de cada distrito está em `bairro_referencia.csv`. Os dez bairros inferidos e o caso de Graças precisam de confirmação da SESAU (pendência E5). Isso resolve, com essa ressalva, as pendências P4 e P5 do modelo lógico (unidade → distrito pelo bairro).

O CNES escreve alguns bairros de outra forma (Jordão Baixo e Alto, Ibura de Baixo, Sítio dos Pintos, Poço da Panela, UR-07 Várzea). O coletor os traduz para o bairro oficial (`ALIAS_BAIRRO`). O `id_bairro` é formado pelos três últimos dígitos do código IBGE do bairro (de 001, Recife, a 094, Brasília Teimosa).

Os setores censitários ficaram de fora: o SIDRA não tem o nível de setor para essas tabelas, e os agregados por setor do Censo 2022 são arquivos nacionais grandes, a baixar à parte. `nucleo.setor_censitario` fica vazia nesta versão e o gerador calibra por bairro, que o plano já admite (“por setor censitário ou bairro coberto”). Pendência E6.

## 6. Tabela 6 atualizada

| Parâmetro | Valor central | Intervalo | Fonte | Mudança em relação ao plano |
|---|---:|---|---|---|
| População total | 1.488.920 | fator de escala 1% a 100% | Censo 2022 (9514) | — |
| Cobertura ESF (cadastrados / residentes) | 80% | 75% a 90% | SESAU; SISAB pendente | Variar por distrito conforme a capacidade das equipes (5.1) |
| Pretos + pardos | 60,8% | por bairro: não disponível | Censo 2022 (9605) | Por bairro, só com agregados por setor (E6) |
| Amarelos | 0,18% | — | Censo 2022 (9605) | Era 0,2% |
| Pessoas com deficiência (2+) | 8,39% | por sexo, idade e cor ou raça | Censo 2022 (10125, 10132) | Gradiente por idade e cor ou raça disponível |
| Autismo (TEA) | 1,42% | por sexo, idade e cor ou raça | Censo 2022 (10145, 10147) | Novo |
| Moradores por domicílio | 2,70 | por bairro, de 1,89 a 3,30 | Censo 2022 (4712, 9922) | A Etapa 4 usou 2,79 |
| Homossexuais ou bissexuais (18+) | 1,0% (PE) | 1,0% a 1,8% | PNS 2019 | Gradiente etário acrescentado: 4,8% (18–29), 1,9% (30–39), 1,0% (40–59), 0,2% (60+), no Brasil |
| Recusa ou não sabe (18+) | 3,4% | 2% a 6% | PNS 2019 | — |
| Pessoas transgênero | 0,69% | 0,48% a 0,90% (IC 95%) | Spizzirri et al. (2021) | — |
| Pessoas não binárias | 1,19% | 0,92% a 1,47% (IC 95%) | Spizzirri et al. (2021) | — |
| “Deseja informar OS?” = Sim, por USF | média da planilha | ~3% a ~53% | Planilha SESAU | Ponto médio (28%) só como reserva, até as metas por USF serem autorizadas |
| Dispersão entre equipes da mesma USF | DP 0,5 ou 1,0 no logito | dois cenários | Premissa | Valores propostos (a validar) |
| Idade mínima elegível para OS/IG | 11 anos | 10 ou 11 | SESAU | — |
| Efeito de uma oficina | 0; 0,2; 0,5 no logito | nulo, pequeno, moderado | Premissa | Valores propostos (a validar) |

A PNS não mostrou diferença significativa da proporção de homossexuais ou bissexuais entre brancos (1,8%), pretos e pardos (1,9%). O gerador, portanto, não deve ligar orientação sexual a cor ou raça; a única dependência documentada é com a idade. O gradiente etário é nacional; deve ser usado como razão entre faixas, aplicada à taxa de Pernambuco.

Os valores propostos para a dispersão entre equipes e para o efeito da oficina estão em escala logito, porque é nela que o modelo de registro em duas etapas (Etapa 6) soma os efeitos. Um efeito de 0,5 leva uma equipe com 30% de “Sim” a cerca de 41%. São propostas para o grupo discutir; estão marcadas como `Premissa Projeto` no CSV.

## 7. Tabela 7 com valores

A correspondência entre as dificuldades funcionais do Censo e os tipos de deficiência do e-SUS ganhou valores (`premissas_gerador.csv`). Como uma pessoa pode ter mais de uma dificuldade, as proporções entre pessoas com deficiência somam mais de 100%; o gerador sorteia os tipos como múltipla escolha.

| e-SUS (código) | Censo 2022 | Prevalência (2+) | Entre pessoas com deficiência |
|---|---|---:|---:|
| Visual (13) | Enxergar | 4,89% | 58,3% |
| Auditiva (12) | Ouvir | 1,41% | 16,8% |
| Física (15) | Andar ou subir degraus ∪ pegar pequenos objetos | 3,95% (3,13% a 4,76%) | 47,0% (37,3% a 56,8%) |
| Intelectual/Cognitiva (14) | Funções mentais (aproximação) | 1,62% | 19,3% |
| TEA (232) | Autismo diagnosticado | 1,42% da população | — |
| Outra (16) | Sem equivalente | — | 3% (1% a 5%), proposta |

A sobreposição entre “andar” (45.714 pessoas) e “pegar objetos” (23.859) não é publicada. O valor da deficiência física fica, portanto, entre a maior das duas e a soma; o ponto médio é o valor central. O TEA é medido no Censo sobre toda a população, não só sobre quem tem dificuldade funcional, e por isso não entra na distribuição entre pessoas com deficiência.

## 8. PNAD Contínua e PNS: o que foi possível

O plano pedia os microdados da PNAD Contínua (filtrados para o Recife) e da PNS 2019. Nenhum dos dois foi processado nesta versão:

- **PNAD Contínua.** Os cruzamentos de que o gerador precisa (instrução, rendimento e trabalho por idade, sexo e cor ou raça) existem no Censo 2022 para o próprio município (tabelas 10061, 10296 e 10300), com amostra muito maior que a da PNAD numa capital. Eles foram usados no lugar dos microdados. A PNAD continua útil para atualizar o rendimento depois de 2022 e para a relação entre escolaridade e renda na mesma pessoa, que o SIDRA não cruza (pendência E7).
- **PNS 2019.** As tabelas de orientação sexual não estão no SIDRA, e a amostra da PNS para o Recife é pequena, como o próprio plano adverte. Entraram os valores publicados pelo IBGE (Brasil, Pernambuco, idade e cor ou raça). Os intervalos de confiança da publicação estão em gráficos e não foram extraídos; o intervalo de Pernambuco segue o da Tabela 6 (pendência E8).

As tabelas do Censo que vêm da amostra (deficiência, autismo, instrução, rendimento) têm erro amostral, que o SIDRA não publica. Para a calibração, são tratadas como exatas; a análise de sensibilidade da Etapa 6 cobre a incerteza pelos parâmetros de comportamento, que são muito mais incertos que estes.

## 9. CID-10 completa e pré-natal

`estrutura/dom_cid10.csv` tem 14.233 códigos sem ponto: as 2.045 categorias (três caracteres) e as 12.188 subcategorias (quatro caracteres) do DATASUS. Os 554 códigos do LEDI carregados na Etapa 4 estão todos lá e mantêm a descrição do LEDI; o `04_carga_estrutura.sql` acrescenta os 13.679 restantes. Isso permite gerar atendimentos com CID-10 fora da relação CIAP2 × CID10 do LEDI, como acontece no PEC.

A lista de CIAP2 de pré-natal (pendência F3) continua aberta. O LEDI proíbe “CIAP2 relacionada ao pré-natal” antes dos 9 anos, mas não diz quais são. A relação do LEDI mostra as candidatas do capítulo W (W78 gravidez, W84 gravidez de alto risco e, possivelmente, W71, W79, W80, W81 e W85), e o guia de qualificação dos indicadores cita só a W78. A carga da Etapa 4 marca W78 e W84; a decisão fica para quando houver a lista oficial.

## 10. Testes

| Teste | Resultado |
|---|---|
| Soma das idades simples = total (9514) | 1.488.920 = 1.488.920 |
| Soma por cor ou raça + sem declaração = total (9605) | 1.488.873 + 47 |
| Semente do IPF (9606) = soma por cor ou raça | 1.488.873 |
| Soma dos bairros = município (população e domicílios) | 1.488.920 e 547.461 |
| Soma dos distritos = município | 1.488.920 |
| Prevalência de deficiência no intervalo da lista de verificação (8% a 9%) | 8,39% |
| Proporções e prevalências em [0, 1]; valor dentro do intervalo | todas |
| Chave primária de `ref_parametro_oficial` sem repetição | 6.032 chaves distintas |
| Unidades, equipes e bairros: códigos válidos e chaves estrangeiras | CNES de 7 dígitos, INE de 10, sem órfãos |
| Reprodutibilidade (`processar` duas vezes) | manifestos idênticos |
| Carga no PostgreSQL 16.15 e no MySQL 8.0.46 | sem erro; conteúdo idêntico nas oito tabelas carregadas |
| Validação de carga (`vw_validacao_carga`) depois da estrutura | só VC12 em 432 equipes (sem microárea e sem lotação) |

O VC12 nas equipes é esperado. Microáreas e lotações são criadas pelo gerador (Etapa 6), e a regra existe para garantir que nenhuma equipe fique sem elas depois da carga completa. Distritos e unidades já passam no VC12.

## 11. Pendências

| N.º | Pendência | Impacto | Como resolver |
|---|---|---|---|
| E1 | Rodar `coletar` de ponta a ponta numa máquina com acesso direto às fontes | O coletor foi testado só nas partes sem rede | Qualquer computador do grupo; comparar o `manifesto_raw.json` novo com o atual |
| E2 | Cadastros por equipe e cobertura do SISAB e do e-Gestor | A meta por equipe do gerador ainda é a capacidade, não o cadastro real | Relatório de cadastro individual do SISAB por equipe; o navegador perdeu a conexão antes desta coleta |
| E3 | Série exata de equipes pelos arquivos mensais do CNES no FTP do DATASUS | A série atual não vê equipes excluídas nem mudança de tipo | Baixar os arquivos de equipes do Recife de 2023 a 2026 |
| E4 | Lista de CNES das 143–144 linhas da planilha | Conciliação linha a linha | Pedir à SESAU junto com a autorização da planilha |
| E5 | Confirmar o distrito de 10 bairros sem UBS e o caso de Graças | Mapa por DS e calibração por distrito | SESAU ou malha oficial dos distritos sanitários |
| E6 | Setores censitários (lista, bairro de cada um e agregados do Censo 2022) | Calibração mais fina que o bairro; `setor_censitario` vazia | Agregados por setor e malha de setores do IBGE |
| E7 | Microdados da PNAD Contínua do Recife | Relação escolaridade × renda na mesma pessoa e atualização pós-2022 | Pacote de microdados do IBGE, processado à parte |
| E8 | Intervalos de confiança da PNS 2019 para PE e por idade | Intervalos da Tabela 6 | Tabelas da publicação ou microdados da PNS |
| F3 | Lista oficial de CIAP2 de pré-natal | VC07 | Manual do PEC ou equipe técnica do e-SUS |
| F5 | Produção do SISAB (atendimentos por cadastrado) | Volume e calibração de atendimentos | Junto com E2 |

Das pendências da Etapa 4, F1 (tipos do CNES) e F2 (CID-10 completa) estão resolvidas; F4 foi resolvida para moradores por domicílio e para o número real de unidades e equipes, mas não para setores (E6) nem para microáreas, que dependem do cadastro por equipe (E2); F3 e F5 continuam abertas.

## Referências

BRASIL. Ministério da Saúde. Cadastro Nacional de Estabelecimentos de Saúde (CNES). Disponível em: https://cnes.datasus.gov.br. Acesso em: 20 out. 2026.

BRASIL. Ministério da Saúde. DATASUS. CID-10: categorias e subcategorias (arquivos CSV). Espelho em: https://github.com/cleytonferrari/CidDataSus. Acesso em: 20 out. 2026.

IBGE. Censo Demográfico 2022: tabelas 4712, 9514, 9605, 9606, 9922, 9923, 10061, 10125, 10127, 10132, 10145, 10147, 10296 e 10300. SIDRA. Disponível em: https://sidra.ibge.gov.br. Acesso em: 20 out. 2026.

IBGE. Orientação sexual autoidentificada da população adulta: Pesquisa Nacional de Saúde 2019. Rio de Janeiro: IBGE, 2022. Disponível em: https://agenciadenoticias.ibge.gov.br/media/com_mediaibge/arquivos/dc3c7903468565be702f076f9795980a.pdf. Acesso em: 20 out. 2026.

RECIFE. Prefeitura. Portal de Dados Abertos: Bairros e RPAs do Recife. Disponível em: https://dados.recife.pe.gov.br/dataset/area-urbana. Acesso em: 20 out. 2026.

SPIZZIRRI, G. et al. Proportion of people identified as transgender and non-binary gender in Brazil. Scientific Reports, v. 11, n. 1, 2021. DOI: 10.1038/s41598-021-81411-4.
