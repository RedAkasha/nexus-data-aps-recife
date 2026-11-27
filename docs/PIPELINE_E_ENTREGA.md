# Pipeline, bancos e entrega (Etapa 06)

Link do projeto: https://github.com/RedAkasha/nexus-data-aps-recife (branch `painel-visao-geral`)

## Pipeline: da origem ao consumo
1. **Origem:** Censo 2022 (IBGE), PNS 2019, Spizzirri et al. 2021, Boletim 01/2025 e planilha de monitoramento (`dados/parametros/`).
2. **Geração:** `python -m aps_sintetico gerar` cria pessoas sintéticas com todas as características juntas (um registro = uma pessoa) e exporta núcleo, staging e verdade.
3. **Validação e inferência:** `valida` e `valida_referencia` comparam a base com as referências (IC 95%, teste z, tolerância).
4. **Banco relacional:** DDL de 55 tabelas em `sql/mysql` e `sql/postgresql` (carga via `carregar`).
5. **Camada analítica:** `analitica` grava tabelas Parquet (indicadores por equipe, monitoramento, painel de ML).
6. **ML:** `ml` compara 5 modelos (persistência, regressão logística, árvore, KNN, floresta) para alertar baixo preenchimento, sem vazamento.
7. **Consumo:** painel Streamlit (mapa, indicadores, Prevenção IA, Preenchimento Virtual, Banco de Dados, SQL e Inferência).

## Bancos usados e por quê
- **PostgreSQL/MySQL (DDL do repositório):** modelo relacional completo do e-SUS, com integridade e consultas SQL.
- **SQLite (`preenchimento.db`):** banco do formulário e do painel; leve, sem servidor, portátil para a demonstração; tem tabelas de domínio, `pessoa_deficiencia` (N:N), gatilhos, views e auditoria.
- **Parquet:** camada analítica colunar, rápida para os gráficos agregados.

## Requisitos da Etapa 06 × onde estão
| Requisito | Onde |
|---|---|
| CRUD em ≥ 4 tabelas | Painel > Banco de Dados > CRUD (pessoa, profissional, microárea, deficiência) |
| Gatilhos / procedimentos / funções | Banco de Dados > Gatilhos e procedimentos (menor de 11 anos, carga fechada, auditoria, fechar_carga) |
| Consultas e views | Banco de Dados > Views; SQL e Inferência > Consultas SQL (com consulta livre) |
| Indicadores | Banco de Dados > Estatística (equipes, média, mediana, moda, variância, desvio padrão) |
| ≥ 6 gráficos dinâmicos | Estatística: histograma, boxplot, tendência, dispersão com correlação, barras de alerta, rosca |
| Filtros interativos | Distritos, mínimo de elegíveis, tabela, view |

## Como executar
```
git clone https://github.com/RedAkasha/nexus-data-aps-recife.git && cd nexus-data-aps-recife
git checkout painel-visao-geral
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[painel]"
python -m aps_sintetico gerar --escala 0.1 --saida saida/base
python -m aps_sintetico analitica --saida saida/base
python -m aps_sintetico ml --saida saida/base
python -m aps_sintetico painel --saida saida/base
```
