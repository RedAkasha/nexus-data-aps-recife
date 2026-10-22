# Inferência sobre a base sintética (comparada à verdade)

## 1. Proporção de "Sim" por equipe

- Equipes: 432; beta-binomial ajustada: α = 1.38, β = 2.29.
- Cobertura do intervalo de Wilson 95% para θ: 94.7%.
- RMSE: bruta 0.0294 × bayesiana empírica 0.0297.
- Spearman com a verdade: bruta 0.992 × EB 0.992.
- Precisão@43 (piores equipes): bruta 86% × EB 86%.

## 2. Viés por não resposta informativa (MNAR)

- λ do cenário = 0.000. LGB+ entre quem respondeu: 1.04%; real entre os elegíveis: 1.03% (viés +0.01 p.p.; razão 1.01).
- Pós-estratificada por idade: 0.98% (viés -0.05 p.p.; erro-padrão amostral ≈ 0.05 p.p.). Com λ = 0 a não resposta é ignorável dado a idade (a aceitação cai com a idade e LGB+ é mais comum entre jovens), e a pós-estratificação deve trazer o viés para dentro do erro amostral; com λ ≠ 0 sobra o viés de não resposta informativa, que nenhum ajuste por covariável remove.
- Trans e não binários: 2.21% entre respondentes × 2.24% reais.

## 3. Efeito das oficinas

- Alocação: aleatoria; efeito verdadeiro no logito: 0.2; equipes tratadas: 125.
- Diferença ingênua no fim da série: +3.01 p.p.
- Diferença-em-diferenças no painel observado: +3.17 p.p. (EP 1.18 p.p.; IC95% ±2.32).
- Mesma DiD na verdade instantânea: +2.91 p.p. Só as versões feitas depois da oficina carregam o efeito: quando o pós-período é curto, o observado fica abaixo da verdade.
