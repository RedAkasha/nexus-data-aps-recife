# Comparação final de modelos e justificativa técnica

**Problema:** classificar se a equipe terminará o próximo quadrimestre com "Sim" em orientação sexual abaixo de 15% (alerta de baixo preenchimento). Prevalência no teste: 0,202.

**Modelo definitivo: Regressão logística.** Treino 20231–20253 (3592 linhas), teste [20261, 20262] (862 linhas).

## 1. Comparação (teste, usado uma vez; limiar fixado no walk-forward p/ revocação ≥ 80%)

| Modelo | AP walk-forward (± EP) | AP teste | AUC | Precisão | Revocação | F1 | Precisão@10% |
|---|---|---|---|---|---|---|---|
| Persistência (regra) | 0,991 ± 0,001 | 0,994 | 0,999 | 1,000 | 0,787 | 0,881 | 1,000 |
| Regressão logística ✅ | 0,987 ± 0,003 | 0,994 | 0,999 | 0,993 | 0,764 | 0,864 | 1,000 |
| Árvore de decisão | 0,979 ± 0,005 | 0,980 | 0,990 | 1,000 | 0,747 | 0,855 | 1,000 |
| KNN | 0,969 ± 0,003 | 0,978 | 0,994 | 0,986 | 0,787 | 0,875 | 1,000 |
| Floresta aleatória | 0,989 ± 0,003 | 0,994 | 0,999 | 1,000 | 0,776 | 0,874 | 1,000 |

**Onde a persistência não enxerga** (equipes hoje fora de alerta; novos alertas no teste: 13):

| Modelo | Revocação dos novos alertas | AP entre equipes fora de alerta |
|---|---|---|
| Persistência (regra) | 0,000 | 0,724 |
| Regressão logística | 0,000 | 0,714 |
| Árvore de decisão | 0,000 | 0,507 |
| KNN | 0,231 | 0,434 |
| Floresta aleatória | 0,000 | 0,628 |

IC 95% (bootstrap por equipe) do AP do definitivo: 0,987–0,999; diferença para a persistência: -0,001 a 0,002.

## 2. Por que este modelo

- **Critério definido antes do teste:** maior AP médio no walk-forward; entre os que ficam a 1 erro-padrão do melhor (Regressão logística, Floresta aleatória), o mais explicável. Venceu a persistência no walk-forward: não.
- **Persistência é um rival muito forte:** ~95% das equipes mantêm o estado (baixo/não baixo) de um quadrimestre para o outro, então "quem está baixo hoje" já acerta quase tudo. Por isso o modelo definitivo é avaliado também onde a regra é cega: nas equipes que HOJE estão fora de alerta (tabela abaixo). Resultado honesto: nenhum modelo supera a persistência de forma clara (diferenças dentro do IC) e os novos alertas são raros e difíceis de antecipar. Mantemos a regressão logística como definitivo por empate técnico + explicabilidade (coeficientes legíveis, pontuação contínua de risco para ordenar a fila), e deixamos a persistência como regra de comparação visível no painel.
- **Métrica principal = AP** (área sob precisão–revocação): só ~1 em cada 5 equipes entra em alerta, e a acurácia seria enganosa com classe rara.
- **Revocação ≥ 80%:** perder uma equipe que vai ficar baixa custa mais do que apoiar uma que não precisava.
- **Explicabilidade:** a equipe de saúde precisa entender por que foi sinalizada; empate técnico favorece o modelo simples.

## 3. Como evitamos vazamento

- Treino termina em 20253, teste começa em 20261 (treino anterior ao teste: sim).
- Variáveis só usam dados até o fim do quadrimestre t; o rótulo é do t+1.
- Walk-forward (janela expansível) para escolher modelo e limiar; pré-processamento dentro do Pipeline.
- Hiperparâmetros fixos a priori; teste usado uma única vez.
- Teste de sanidade: com rótulos embaralhados o AP foi 0,237 (≈ prevalência 0,202).
- Bootstrap agrupado por equipe (linhas da mesma equipe não são independentes).

## 4. Variáveis mais importantes (permutação no teste)

| Variável | Queda no AP |
|---|---|
| prop_nao_os | 0,147 |
| prop_sim_os | 0,141 |
| prop_sim_ig | 0,109 |
| media_movel_3 | 0,081 |
| prop_ni_os | 0,012 |
| id_ds | 0,002 |
| n_acoes_ate_periodo | 0,001 |
| prop_sim_os_lag1 | 0,000 |

## 5. Limites

- Base sintética: o desempenho mostra o método, não o desempenho real na rede.
- O modelo prevê risco, não causa; a decisão de apoio é da equipe gestora.

## Por Distrito Sanitário

| Modelo | Erro validação (p.p.) | Erro teste (p.p.) | Escolhido |
|---|---|---|---|
| Persistência | 0.28 | 0.18 |  |
| Média móvel (3) | 0.45 | 0.28 |  |
| Regressão ridge | 0.36 | 0.24 | sim |
| Árvore de decisão | 0.58 | 0.40 |  |
| Floresta aleatória | 0.44 | 0.28 |  |

A persistência (repetir o valor atual) erra menos que os modelos aprendidos: o Sim de cada distrito muda menos de 1 p.p. por quadrimestre.
