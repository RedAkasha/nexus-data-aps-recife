# Previsão da proporção de "Sim" no quadrimestre seguinte

Treino: 3592 linhas equipe × período; teste: 862 linhas (períodos 20261, 20262). Modelo escolhido pela validação walk-forward: **floresta_variacao**.

| modelo | mae | rmse | r2 | precisao_k | cv_mae |
|---|---|---|---|---|---|
| persistencia | 0.0126 | 0.0183 | 0.9936 | 0.9070 | 0.0166 |
| media_movel_3 | 0.0182 | 0.0246 | 0.9885 | 0.8953 | 0.0220 |
| knn | 0.0258 | 0.0336 | 0.9785 | 0.8372 | 0.0287 |
| knn_variacao | 0.0133 | 0.0189 | 0.9932 | 0.9070 | 0.0172 |
| linear | 0.0128 | 0.0183 | 0.9937 | 0.9070 | 0.0169 |
| linear_variacao | 0.0128 | 0.0183 | 0.9937 | 0.9070 | 0.0169 |
| ridge | 0.0127 | 0.0182 | 0.9937 | 0.9186 | 0.0169 |
| ridge_variacao | 0.0127 | 0.0183 | 0.9937 | 0.9070 | 0.0169 |
| arvore | 0.0160 | 0.0217 | 0.9911 | 0.8721 | 0.0189 |
| arvore_variacao | 0.0132 | 0.0188 | 0.9933 | 0.9070 | 0.0172 |
| floresta | 0.0138 | 0.0193 | 0.9929 | 0.9186 | 0.0175 |
| floresta_variacao | 0.0129 | 0.0183 | 0.9937 | 0.9070 | 0.0168 |
| gradient_boosting | 0.0141 | 0.0194 | 0.9928 | 0.8837 | 0.0178 |
| gradient_boosting_variacao | 0.0133 | 0.0187 | 0.9933 | 0.8953 | 0.0173 |

Um modelo só agrega valor se vencer a persistência no teste; com séries de cadastro que mudam devagar (versões renovadas a cada ~18 meses), a persistência é um piso alto.
