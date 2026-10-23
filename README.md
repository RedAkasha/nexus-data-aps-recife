# Gerador de dados sintéticos da APS do Recife (PEC e-SUS APS)

**Projeto 3 – Dados · CESAR School · 2026.2 · Equipe 2 – Nexus Data**

Este repositório gera, carrega, valida e analisa uma base **sintética** da Atenção Primária à Saúde do Recife. A base segue o leiaute do PEC e-SUS APS 8.7.0 (LEDI). O objetivo é apoiar o monitoramento do registro de **orientação sexual, identidade de gênero, raça/cor e deficiência** no cadastro individual, que é o foco da reunião com a Secretaria de Saúde (01/09/2026).

> **Dados sintéticos.** Nenhuma linha corresponde a uma pessoa real. Nomes, CPF, CNS e endereços são fictícios (CPF e CNS têm dígito verificador válido). As distribuições vêm de fontes oficiais e de premissas declaradas. A base **não** é um retrato da população do Recife e não pode ser apresentada como tal (RN28).

---

## Sumário

1. [O que o gerador faz](#1-o-que-o-gerador-faz)
2. [Estrutura do repositório](#2-estrutura-do-repositório)
3. [Instalação](#3-instalação)
4. [Execução rápida](#4-execução-rápida)
5. [Comandos](#5-comandos)
6. [Cenários e parâmetros](#6-cenários-e-parâmetros)
7. [Saídas](#7-saídas)
8. [Banco de dados](#8-banco-de-dados)
9. [Painel, inferência e aprendizado de máquina](#9-painel-inferência-e-aprendizado-de-máquina)
10. [Testes e reprodutibilidade](#10-testes-e-reprodutibilidade)
11. [Etapas do plano × código](#11-etapas-do-plano--código)
12. [Limitações e pendências](#12-limitações-e-pendências)
13. [Publicação no GitHub](#13-publicação-no-github)
14. [Licença e citação](#14-licença-e-citação)

---

## 1. O que o gerador faz

O gerador é um **modelo estatístico gerativo**, montado como um grafo acíclico dirigido (DAG). Cada variável é sorteada a partir das que a antecedem, e a ordem segue o Plano Metodológico (`docs/Plano_Metodologico_Etapa6_Gerador.pdf`):

| Passo | Método | Fonte principal |
|---|---|---|
| População por bairro × sexo × idade × raça/cor | *Iterative proportional fitting* (IPF) com restrição agrupada bairro → DS, seguido de integerização TRS | Censo 2022 (SIDRA 9606, 9922/9923); boletim SESAU 01/2025 (raça por DS) |
| Domicílios | Pessoa de referência por amostragem ponderada; homofilia racial nos demais moradores | Censo 2022 (domicílios por bairro) |
| Renda, instrução, trabalho | Cópula gaussiana (latente domiciliar) | Censo 2022 (SIDRA 10296, 10061) |
| Deficiência e tipos | Logística aditiva calibrada por *raking*; cópula gaussiana entre os tipos; TEA | Censo 2022 (SIDRA 10125, 10132, 10145) |
| Orientação sexual e identidade de gênero (verdade) | Bernoulli com gradiente etário | PNS 2019; Spizzirri et al. (2021) |
| Rede e território | Equipes e unidades reais do CNES; microáreas pela PNAB; profissionais fictícios | CNES (Etapa 5) |
| Cobertura | Seleção logística por domicílio, com intercepto da equipe calibrado à meta | Premissa SESAU (80%), teto por DS |
| **Registro** (o objeto do estudo) | Logística mista em duas etapas: a pergunta é feita (R) e a pessoa aceita (A). Efeitos de equipe correlacionados e efeito da pessoa; interceptos por USF calibrados por quadratura de Gauss–Hermite | Planilha SESAU (linha 3, faixa entre USF) |
| Dinâmica 2023-01 → data de corte | Óbitos por idade × raça; nascimentos por DS × raça da mãe; mudanças; renovação das fichas; tendência + AR(1) por equipe; oficinas escalonadas | Boletim SESAU 01/2025 |
| Atendimentos (FAI) | Poisson–Gama (binomial negativa) por idade × sexo; pré-natal pela distribuição de consultas por raça | Premissas; boletim SESAU (Tabela 1) |
| Defeitos (Etapa 7) | 13 tipos com gabarito em `controle_defeito` | Modelo lógico, seção 4.3 |

A **verdade** fica em `verdade/`: os atributos latentes de cada pessoa e a probabilidade de "Sim" por versão e por equipe × mês. Com ela, os métodos podem ser avaliados como num estudo de simulação (ADEMP). O banco não recebe nenhuma informação da verdade.

## 2. Estrutura do repositório

```
├── config/
│   ├── cenario_base.yaml        parâmetros do cenário base, com a classe de evidência de cada um
│   └── cenarios/*.yaml          cenários de sensibilidade (só as chaves que mudam)
├── dados/
│   ├── parametros/              CSV oficiais (Censo, PNS, literatura, premissas)
│   ├── parametros_complementares/boletim_sesau_2025.csv
│   ├── estrutura/               DS, bairros, unidades e equipes reais (CNES)
│   ├── raw/                     extrações brutas (SIDRA, CNES, CID-10) e manifesto
│   └── dominios.json            domínios do LEDI 8.7.0
├── coleta/                      coleta_parametros.py e gen_carga.py
├── src/aps_sintetico/           o pacote (gerador, carga, validação, analítica, inferência, ML)
├── sql/postgresql/              01–05 (DDL, domínios, validação, estrutura, parâmetros),
│                                06 staging → núcleo, 07 camada analítica
├── sql/mysql/                   01–05 equivalentes para MySQL 8
├── painel/app.py                painel Streamlit (segue o wireframe do grupo)
├── tests/                       pytest
├── docs/                        plano, documentação das etapas, data card
├── docker-compose.yml           PostgreSQL 16, MinIO e MLflow
├── pyproject.toml · requirements.txt · Makefile · .env.example
```

Os módulos de `src/aps_sintetico/`:

| Módulo | Conteúdo |
|---|---|---|
| `config.py`, `rng.py`, `parametros.py` | Cenários em YAML; fluxos de números aleatórios independentes por componente (PCG64 + SeedSequence); leitura dos CSV oficiais |
| `ipf.py`, `populacao.py` | IPF, TRS, pessoas, domicílios, setores sintéticos, socioeconômico |
| `atributos.py` |Deficiência, TEA, orientação sexual e identidade de gênero |
| `territorio.py`, `cobertura.py` | Rede, metas, microáreas, profissionais, adscrição, cobertura, primeiro cadastro |
| `registro.py` | Modelo de registro e calibração dos interceptos |
| `dinamica.py` | Componente temporal, oficinas, óbitos, mudanças, nascimentos, versões da FCI, verdade mensal, defeitos de comportamento |
| `atendimentos.py` |FAI: atendimentos, fichas, problemas e condições |
| `defeitos.py` | Identidades e defeitos de processo |
| `exporta.py` | Núcleo, *staging* (LEDI), verdade, referências e manifesto SHA-256 |
| `carga.py` | Carga no PostgreSQL (direta ou via *staging*); script para MySQL |
| `valida.py` | Calibração, integridade (VC), qualidade × gabarito (RQ), planilha SQL × Python |
| `analitica.py` | Camada analítica em Parquet (equivalente ao `07_analitica.sql`) |
| `inferencia.py` | Wilson, bayesiano empírico, viés MNAR, efeito das oficinas |
| `ml.py` | Regressão com partição temporal, *walk-forward*, MLflow |
| `sensibilidade.py` | Cenários, réplicas e hipercubo latino |
| `cli.py` | Linha de comando |

## 3. Instalação

Requisitos: **Python 3.10 ou superior**. O PostgreSQL 16 é opcional e só é necessário para etapas em SQL. O Docker também é opcional.

**Windows (PowerShell)**

```powershell
cd "C:\Users\<você>\...\Gerador de dados sintéticos"
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[tudo]"          # ou: pip install -r requirements.txt
```

Se o PowerShell bloquear o `Activate.ps1`, rode antes `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

**Linux, macOS ou WSL**

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[tudo]"
```

O extra `tudo` instala banco, painel, MLflow e testes. Sem o MLflow, use `pip install -e ".[banco,painel,dev]"`; o treino continua e grava as métricas em arquivo.

## 4. Execução rápida

```bash
# 1) base pequena (DS I e III, 2% da população), sem banco: ~20 s
python -m aps_sintetico tudo --cenario demo --sem-banco --sem-mlflow

# 2) painel com essa base
python -m aps_sintetico painel --cenario demo
```

Fluxo completo com banco, no cenário base (Recife inteiro a 10%):

```bash
docker compose up -d postgres            # ou um PostgreSQL 16 local
# PowerShell: $env:APS_DSN="postgresql://aps:aps@localhost:5432/aps_recife"
export APS_DSN=postgresql://aps:aps@localhost:5432/aps_recife
python -m aps_sintetico tudo
python -m aps_sintetico painel
```

`tudo` executa, nesta ordem: gerar → analítica (Parquet) → carregar (PostgreSQL, com a analítica em SQL) → validar → inferência → ML.

## 5. Comandos

`python -m aps_sintetico <comando> --help` mostra todas as opções. Opções comuns: `--cenario NOME` (padrão `base`), `--saida PASTA` (padrão `saida/<cenário>`), `--escala`, `--distritos 1,3,7`, `--semente`, `--set chave.subchave=valor`.

| Comando | O que faz |
|---|---|
| `gerar` | Gera a base e exporta núcleo, *staging*, verdade e manifesto |
| `carregar [--via-staging] [--dsn …] [--mysql]` | Recria os esquemas, roda `01`–`05`, carrega e roda `07_analitica.sql`. `--via-staging` carrega as fichas no leiaute LEDI e transforma com `06_staging_para_nucleo.sql`. `--mysql` só escreve `carga_mysql.sql` |
| `validar [--sem-banco]` | `relatorios/validacao.md`: calibração, VC01–VC15, RQ × gabarito, planilha SQL × Python |
| `analitica` | `analitica/*.parquet` sem banco (Power BI e painel) |
| `inferencia` | `relatorios/inferencia.md` |
| `ml [--sem-mlflow]` | `ml/metricas.csv`, `ml/predicoes.parquet`, `ml/relatorio_ml.md` |
| `sensibilidade [--cenarios a,b] [--replicas R] [--lhs N]` | `saida/sensibilidade/sensibilidade.md` |
| `painel` | Abre o Streamlit |
| `tudo [--sem-banco]` | Fluxo completo |

Exemplos:

```bash
python -m aps_sintetico gerar --cenario mnar_menor --escala 0.05
python -m aps_sintetico gerar --set registro.pi_nao_sem_pergunta=0.5 --saida saida/teste_pi
python -m aps_sintetico sensibilidade --replicas 3 --escala 0.02 --distritos 1,3
```

## 6. Cenários e parâmetros

`config/cenario_base.yaml` traz todos os parâmetros, cada um com a classe de evidência: **[A]** fonte oficial, **[B]** literatura ou derivado com premissa, **[C]** direção de estudo de serviço, **[P]** premissa do grupo. Um cenário em `config/cenarios/` sobrescreve só as chaves que mudam:

| Cenário | Pergunta que responde |
|---|---|
| `pi_alto`, `pi_muito_alto` | E se o "Não" for registrado sem a pergunta ter sido feita? (Apêndice A, pergunta 10) |
| `mnar_menor`, `mnar_maior` | Quanto as pessoas LGBT+ aceitam menos ou mais informar: viés da não resposta informativa |
| `equipe_sigma_baixo`, `equipe_sigma_alto` | Quanto pesa a variação entre equipes da mesma USF |
| `oficina_nula`, `oficina_moderada`, `oficina_focalizada` | Efeito verdadeiro das oficinas; alocação nas piores equipes (regressão à média) |
| `idade_min_10` | Regra do "dado real" com 10 anos (pendência P1) |
| `cobertura_baixa`, `cobertura_alta` | Cobertura municipal de 75% ou 90% |
| `deficiencia_sens_baixa`, `deficiencia_sens_alta` | Sensibilidade do registro de deficiência |
| `uso_lgb_trans_menor` | Menor uso dos serviços por pessoas LGBT+ e trans (Souza, 2018) |
| `demo` | Base pequena para testar a instalação |

**Metas por USF.** Sem a planilha autorizada, as metas de cada USF vêm de uma priori Beta ancorada na linha 3. Quando a SESAU autorizar, basta apontar `registro.metas_usf_csv` para um CSV `cnes,prop_sim,prop_ni`.

**Escala e memória.** `escala` é a fração da população. Com 8 GB de RAM, `escala ≤ 0.3` roda com folga; o Recife inteiro (`escala: 1.0`, ~1,5 milhão de pessoas e ~6 milhões de versões da FCI) pede 16 GB ou mais. Tempo e memória medidos estão na seção 10.

## 7. Saídas

Ficam em `saida/<cenário>/` (fora do Git; a mesma semente reproduz tudo):

```
nucleo/*.csv            tabelas do esquema nucleo, na ordem das FKs (carga direta)
staging/*.csv           fichas no leiaute LEDI (datas em ms, uuid originadora = uuid na 1ª versão)
analitica/              ref_parametro_complementar.csv + *.parquet da camada analítica
verdade/*.parquet       atributos latentes, P(Sim) por versão, verdade por equipe × mês,
                        componentes temporais, metas por USF, nascimentos, duplicidades
relatorios/             validacao.md, calibracao.csv, qualidade_vs_gabarito.csv, inferencia.md
ml/                     metricas.csv, predicoes.parquet, relatorio_ml.md
config_usada.yaml       parâmetros efetivos da execução
manifesto.json          linhas e SHA-256 de cada arquivo
```

Convenções dos CSV: UTF-8, vírgula, cabeçalho, booleano `1`/`0`, nulo `\N`, datas ISO 8601.

**Chaves substitutas determinísticas.** Cada id é o posto (*rank*) da chave natural, por exemplo `id_cidadao` ← `COALESCE(cpf, 'CNS'||cns)`. Por isso a carga direta e a rota *staging* → núcleo produzem linhas idênticas, e o gabarito vale para as duas. Isso é testado em `tests/test_banco.py`.

## 8. Banco de dados

**PostgreSQL 16 (testado).** `carregar` faz o seguinte:

1. Recria os esquemas `stg`, `nucleo` e `analitica` e roda `01`–`05`.
2. Retira as equipes dos DS que não foram gerados (VC12).
3. Carrega as referências complementares (boletim e raça × bairro do IPF).
4. Carrega o núcleo e a *staging*.
5. Roda `07_analitica.sql`.

Consultas úteis:

```sql
SELECT regra, COUNT(*) FROM analitica.vw_validacao_carga GROUP BY 1;   -- vazio = carga íntegra
SELECT * FROM analitica.vw_monitoramento_usf;                         -- colunas H a U da planilha
SELECT regra, COUNT(*) FROM analitica.vw_qualidade_registro GROUP BY 1;
SELECT * FROM analitica.fato_painel_ml WHERE ine = '0000153044' ORDER BY periodo;
```

**MySQL 8 (scripts equivalentes, não testados nesta entrega).**

```bash
mysql -u root -p < sql/mysql/01_ddl.sql      # e 02 a 05, na ordem
python -m aps_sintetico carregar --mysql      # escreve saida/base/carga_mysql.sql
mysql --local-infile=1 -u root -p < saida/base/carga_mysql.sql
```

A camada analítica para MySQL é a de Parquet (`python -m aps_sintetico analitica`). O `07_analitica.sql` usa recursos do PostgreSQL.

**Power BI.** Duas formas de conectar:

- Pelo conector PostgreSQL, apontando para as tabelas `analitica.*` e para a visão `vw_monitoramento_usf`.
- Pela pasta `saida/<cenário>/analitica/`, usando o conector Parquet.

## 9. Painel, inferência e aprendizado de máquina

**Painel** (`python -m aps_sintetico painel`). Segue o rascunho de wireframe do grupo:

- filtros por Distrito Sanitário, Unidade e competência;
- cartões de atendimentos, proporção de "Sim" e equipes em alerta;
- série mensal da proporção de "Sim" com as datas das oficinas;
- atendimentos por território;
- ranking por equipe;
- a planilha da SESAU (colunas H a U), com download;
- qualidade do registro × gabarito;
- "Prevenção IA", com as equipes de maior risco previstas.

O mapa por DS aparece como barras por distrito. Um mapa coroplético depende do GeoJSON dos bairros (dados abertos da Prefeitura), que não está no repositório.

**Inferência** (`inferencia`). Compara cada método com a verdade:

- Intervalo de Wilson: cobertura.
- Estimativa bayesiana empírica beta-binomial contra a proporção bruta: RMSE, Spearman e precisão@k das piores equipes.
- Viés da prevalência LGB+ estimada só com quem respondeu, bruto e pós-estratificado por idade.
- Efeito das oficinas: diferença ingênua e diferença-em-diferenças no painel observado, contra a mesma conta na verdade.

**ML** (`ml`). Prevê a proporção de "Sim" da equipe no quadrimestre seguinte (Tabela 10 do plano):

- Partição temporal, com validação *walk-forward* para escolher o modelo.
- Linhas de base: persistência e média móvel.
- Modelos: KNN, linear, ridge, árvore, floresta aleatória e *gradient boosting*, cada um no nível e na variação.
- Métricas: MAE, RMSE, R², MAE por DS e precisão@k.

Com `docker compose up -d` e `MLFLOW_TRACKING_URI=http://localhost:5000`, as execuções vão para o MLflow (backend PostgreSQL, artefatos no MinIO). Sem servidor, ficam num SQLite local (`./mlflow.db`; veja com `mlflow ui --backend-store-uri sqlite:///mlflow.db`).

## 10. Testes e reprodutibilidade

```bash
python -m pytest            # testes sem banco rodam sempre; os de banco exigem APS_DSN acessível
```

Os testes cobrem:

- Peças estatísticas: IPF, TRS, calibração por quadratura conferida por Monte Carlo, dígitos verificadores, formato do uuid do LEDI.
- Restrições do DDL reproduzidas em pandas.
- Gabarito.
- Reprodutibilidade: mesma semente, mesmo SHA-256.
- Calibração.
- Carga sem violação.
- Igualdade das rotas direta e *staging*.
- Igualdade SQL × Python da camada analítica.

A reprodutibilidade byte a byte vale para a mesma versão das bibliotecas. O Faker está fixado em `requirements.txt` porque as listas de nomes mudam entre versões. Com NumPy ou pandas de outra versão, a base continua válida, mas pode não ser idêntica.

**Medições** (cenário base, Recife inteiro a 10%, máquina de 2 vCPU e 7 GB):

| Medida | Valor |
|---|---|
| População gerada | 148.896 residentes + 680 pessoas acompanhadas por eCR/eAPP + 6.014 nascimentos na série |
| Núcleo | 127.207 cidadãos · 622.750 versões da FCI · 53.726 domicílios · 799.486 atendimentos · 1.030.742 problemas · 243.317 linhas de gabarito |
| Tempo | ~2,5 min para gerar e exportar; ~10 min para o fluxo `tudo` (com carga, analítica SQL, validação e ML) |
| Memória (pico) | 2,5 GB |
| Calibração | 55 de 55 verificações dentro da tolerância |
| Integridade | VC01–VC15 sem violação; rota *staging* idêntica à direta; analítica SQL idêntica à Python |

Os relatórios dessa execução estão em `docs/resultados/`.

## 11. Etapas do plano × código

| Etapa | Produto | Onde está |
|---|---|---|
| 1 | Dicionário de dados | `docs/etapas/01_dicionario_dados.md` |
| 2 | Modelo conceitual e regras de negócio | `docs/etapas/02_regras_de_negocio.md`, `modelo_conceitual_aps_recife.brM3` |
| 3 | Modelo lógico | `docs/etapas/03_modelo_logico.md` (+ `.brM3`, `.xml`, `.png`) |
| 4 | Modelo físico | `sql/*/01_ddl.sql`, `03_validacao_carga.sql`, `docs/etapas/04_documentacao_fisica.md` |
| 5 | Parâmetros oficiais | `coleta/`, `dados/`, `sql/*/04–05`, `docs/etapas/05_parametros_oficiais.md` |
| 6 | Gerador | `src/aps_sintetico/` (população → atendimentos), `config/`, `docs/Plano_Metodologico_Etapa6_Gerador.pdf` |
| 7 | Defeitos e gabarito | `dinamica.defeitos_comportamento`, `defeitos.py`, `nucleo.controle_defeito` |
| 8 | Carga e validação | `exporta.py`, `carga.py`, `sql/postgresql/06_staging_para_nucleo.sql`, `valida.py` |
| 9 | Camada analítica e painel | `sql/postgresql/07_analitica.sql`, `analitica.py`, `painel/app.py` |
| 10 | Inferência, ML e sensibilidade | `inferencia.py`, `ml.py`, `sensibilidade.py`, `config/cenarios/` |
| 11.1 | Repositório Git com README | este repositório |

`docs/data_card.md` descreve a base gerada: finalidade, fontes, premissas, limites e uso permitido.

## 12. Limitações e pendências

- **Metas por USF.** Saem de uma priori ancorada na linha 3 da planilha. Com a planilha autorizada, os interceptos passam a reproduzir cada USF.
- **Setores censitários.** São sintéticos (pendência E6). O Censo 2022 não publica raça/cor por bairro, então a referência de raça por território (Hellinger, RQ04) é a do próprio IPF.
- **Taxas de atendimento.** As taxas por idade × sexo são premissas de ordem de grandeza e devem ser calibradas com o SISAB.
- **Pendências da SESAU** (Apêndice A). Seguem abertas a semântica do "Não" (π), a idade mínima (10 ou 11) e se a recusa conta entre os ativos. Todas viraram parâmetros e cenários.
- **MySQL e Docker.** Os scripts estão escritos, mas não foram executados nesta entrega: o ambiente de desenvolvimento não tinha MySQL nem Docker. A rota PostgreSQL foi testada de ponta a ponta.

## 13. Publicação no GitHub

O repositório já vem com o histórico Git:

1. Crie um repositório vazio no GitHub (sem README), por exemplo `gerador-dados-sinteticos-aps-recife`.
2. Na pasta do projeto, rode:

```bash
git remote add origin https://github.com/RedAkasha/gerador-dados-sinteticos-aps-recife.git
git branch -M main
git push -u origin main
```

As pastas `saida/` e `mlruns/` e o arquivo `mlflow.db` ficam fora do Git, porque a semente reproduz tudo.

## 14. Licença e citação

Este repositório usa duas licenças, conforme o tipo de material. Os dados de terceiros continuam sob as condições das fontes.

| Material | Onde está | Licença |
|---|---|---|
| Código | `src/`, `painel/`, `tests/`, `coleta/`, `sql/`, `config/`, `docker/`, `docker-compose.yml`, `Makefile`, `pyproject.toml` | [MIT](https://opensource.org/license/mit) |
| Documentação | `README.md`, `docs/` (incluindo os PDFs do plano e da emulação e os modelos `.brM3`, `.xml` e `.png`) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.pt-br) |
| Dados sintéticos gerados | tudo o que o gerador grava em `saida/` (núcleo, *staging*, verdade, camada analítica e relatórios) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.pt-br) |
| Dados de fontes públicas | `dados/parametros/`, `dados/parametros_complementares/`, `dados/estrutura/`, `dados/raw/`, `dados/dominios.json` | Condições de cada fonte (abaixo) |

### Código: licença MIT

```text
MIT License

Copyright (c) 2026 Equipe 2 – Nexus Data (Projeto 3 – Dados, CESAR School)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

As bibliotecas usadas (NumPy, pandas, SciPy, scikit-learn, PyYAML, PyArrow, Faker, psycopg, Streamlit, Altair, MLflow) mantêm as próprias licenças, todas compatíveis com a MIT.

### Documentação e dados sintéticos: CC BY 4.0

© 2026 Equipe 2 – Nexus Data. A documentação e as bases geradas podem ser copiadas, adaptadas e redistribuídas para qualquer fim, desde que se dê crédito ao projeto e se indique se houve alteração. Texto completo: <https://creativecommons.org/licenses/by/4.0/legalcode.pt>.

Quem redistribuir uma base gerada deve manter o aviso de que os **dados são sintéticos**: nenhuma linha corresponde a pessoa real, e os números não são estatística do Recife (`docs/data_card.md`).

### Dados de fontes públicas

Os arquivos de `dados/` são cópias ou derivações de dados públicos. Eles foram incluídos para que a geração seja reprodutível e **não** estão cobertos pelas licenças acima. Quem reutilizá-los deve citar a fonte original e seguir as condições dela:

| Fonte | Arquivos |
|---|---|
| IBGE – Censo Demográfico 2022 (SIDRA) e Pesquisa Nacional de Saúde 2019 | `censo2022_*.csv`, `censo_pop_raca.csv`, `dados/raw/sidra_*` |
| Ministério da Saúde – CNES (DATASUS) | `cnes_*.csv`, `dados/estrutura/`, `dados/raw/cnes_recife_aps.tsv` |
| Ministério da Saúde – CID-10 (DATASUS) | `dados/raw/cid10/`, `dados/estrutura/dom_cid10.csv` |
| Ministério da Saúde – LEDI e-SUS APS 8.7.0 (tabelas de referência) | `dados/dominios.json` |
| Prefeitura do Recife – Portal de Dados Abertos (bairros e RPA) | `dados/raw/bairros_rpa_recife.csv` |
| Secretaria de Saúde do Recife – Boletim 01/2025 | `dados/parametros_complementares/boletim_sesau_2025.csv` |
| Literatura científica (Spizzirri et al., 2021, *Scientific Reports*, e demais citadas no plano) | `literatura_os_ig.csv` (só parâmetros numéricos extraídos) |

### Como citar

> EQUIPE 2 – NEXUS DATA. *Gerador de dados sintéticos da APS do Recife (PEC e-SUS APS)*. Versão 1.0.0. Recife: CESAR School, Projeto 3 – Dados, 2026. Disponível em: <(https://github.com/RedAkasha/nexus-data-aps-recife)>.

Projeto acadêmico de alunos, sem vínculo comercial nem caráter oficial da Secretaria de Saúde do Recife.
