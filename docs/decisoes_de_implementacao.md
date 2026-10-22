# Decisões de implementação (Etapas 6 a 11)

O plano metodológico da Etapa 6 e os modelos das Etapas 2 a 4 deixavam alguns pontos em aberto. Ao implementar, o grupo precisou decidir cada um deles. Este registro diz o que se decidiu e por quê, para revisão do grupo.

## Gerador (Etapa 6)

| # | Ponto | Decisão | Motivo |
|---|---|---|---|
| G1 | Raça/cor por DS | Estimador indireto pela razão de natalidade negra/não negra do boletim (12,8 / 7,5), seguido de IPF DS × raça contra as populações dos DS e o total municipal por raça. O resultado municipal fica em 61,1%, contra 61,0% no Censo | O Censo 2022 não publica raça por bairro ou DS |
| G2 | Unidade de seleção da cobertura | O domicílio (conglomerado), com intercepto por equipe resolvido por bisseção para atingir a meta | É o ACS que cadastra o domicílio inteiro; a omissão de moradores (2%) entra à parte |
| G3 | Adscrição | Cada equipe recebe domicílios do próprio bairro até a capacidade (meta ÷ teto). A capacidade ociosa absorve bairros sem UBS e excedentes do mesmo DS | Sem isso a cobertura de um DS ficava 20 p.p. abaixo da meta, porque as equipes não estão onde a população está |
| G4 | eCR e eAPP | Populações próprias (adultos; eAPP sobretudo masculina), sem domicílio nem família. eCR fica `fora_area` e sem microárea; eAPP usa a microárea 01 | Não são residentes de domicílio e não vêm do IPF |
| G5 | Calibração do registro | Os interceptos de R e A por USF são integrados por Gauss–Hermite sobre o efeito da equipe, o efeito da pessoa, o componente temporal na data de corte (τ, de tendência + AR(1)) e o termo de idade | Calibrar sem τ e sem o termo de idade deixava a linha 3 2 p.p. abaixo da meta, por causa da atenuação da média de logísticas |
| G6 | Deslocamento das crianças (κ) | Diferença entre os interceptos calibrados (com efeitos aleatórios) para adultos e para crianças da linha 3 | A diferença dos logitos marginais subestimava o deslocamento, e as crianças saíam com 14% de "Sim" em vez de 10% |
| G7 | Metas por USF sem a planilha | Beta(2,9; 10,7) para o "Sim" e Beta(2; 50) para o NI, deslocadas no logito para que a média ponderada pela população iguale a linha 3 | Mantém a dispersão observada (3% a 53%) e a âncora municipal |
| G8 | Mudança de território | No máximo uma por domicílio no período. A família vai para um novo domicílio de outro bairro, pode ser recadastrada lá (nova cadeia, mesmo cidadão) e tem a saída registrada na origem com prob. 0,6 | Gera, ao mesmo tempo, a desatualização (defeito 5) e a mudança de equipe da versão vigente |
| G9 | Atualizações | Renovação exponencial por domicílio (visita do ACS), com média de 18 meses × ritmo da equipe | Todos os moradores cadastrados são atualizados na mesma visita |
| G10 | Atributos que aparecem com a idade | A orientação sexual e a identidade verdadeiras são sorteadas também para crianças (com a taxa da adolescência), mas só ficam observáveis a partir da idade mínima | Evita que quem completa 11 anos durante a série fique sem atributo |
| G11 | Fichas ainda não transmitidas | Versões com digitação depois de `dt_geracao` ficam fora da base. Se a primeira versão de uma cadeia ficou fora, a cadeia inteira fica fora | Reproduz o atraso de transmissão e mantém a FK da cadeia |
| G12 | Atendimentos | Só de cadastrados ativos, em datas dentro do período ativo e nunca antes do nascimento. Pré-natal só nas datas em que a mãe estava cadastrada | Satisfaz VC04 e VC07 por construção |

## Defeitos (Etapa 7)

| # | Ponto | Decisão |
|---|---|---|
| D1 | Defeito 13 ("Tem deficiência" sem registro) | Campo `tem_deficiencia` nulo (RQ11). Nasce na Etapa 6 (pergunta não feita, 2%) e é reforçado na Etapa 7 (1%). Apagar só os tipos violaria a VC01, que é regra de integridade |
| D2 | Defeito 6 | Qualquer "Deseja informar" preenchido (Sim ou Não) para criança abaixo da idade mínima na data da versão, como na RQ02 |
| D3 | Defeito 8 | Nascimento de 111 a 120 anos antes da data de corte, ou 01/01/1900. Passa na VC03 (limite de 130 anos) e é acusado pela RQ12. Datas impossíveis ficam para a *staging* (modelo lógico, 6.4) |
| D4 | Defeito 3 | `id_registro_par` aponta a versão originadora, que é a referência da RQ03 |
| D5 | Defeito 7 de endereço | Só na *staging* (FCDT); o núcleo não guarda endereço (RN23) |
| D6 | Duplicidade | Novo cidadão só com CNS provisório, sem CPF, numa nova cadeia em data posterior. Em 80% dos casos o nome é idêntico e em 20% tem erro de digitação. A RQ05 só alcança os primeiros, e o gabarito mostra isso |

## Carga (Etapa 8)

| # | Ponto | Decisão |
|---|---|---|
| C1 | Chaves substitutas | Posto da chave natural, com `ORDER BY … COLLATE "C"` no SQL e ordenação por código no Python. Por isso as rotas direta e *staging* → núcleo são idênticas (testado) |
| C2 | Família do cidadão | É a do responsável indicado na versão vigente da FCI. Entre as famílias desse responsável vale a da FCDT mais recente. A regra é a mesma em Python e no `06` |
| C3 | VC09 (família sem membro) | Famílias sem nenhum membro não entram na carga: todos se mudaram e foram recadastrados em outra família, ou as fichas ainda não foram transmitidas |
| C4 | VC12 com DS parciais | A carga retira as equipes e unidades dos DS que não foram gerados |
| C5 | Microárea, ação formativa, parâmetro e gabarito | Entram direto do gerador nas duas rotas. Não existem no LEDI: a microárea vem da territorialização, e as outras três são do projeto |
| C6 | Datas da *staging* | Milissegundos desde 1970 à meia-noite de Recife (UTC−3), convertidos de volta por `stg.fn_ms_data` |
| C7 | Referência de raça por território | Linhas `fonte = 'Gerador IPF'` em `ref_parametro_oficial`, com a distribuição bairro × raça do IPF. Junto vão as linhas do boletim SESAU |

## Camada analítica (Etapa 9)

| # | Ponto | Decisão |
|---|---|---|
| A1 | Versão vigente por competência | A mesma regra da `vw_cadastro_vigente` (RN09), aplicada ao fim de cada mês com intervalos de validade (LEAD) |
| A2 | Faixas etárias | `00-10`, `11-17`, `18-29`, `30-39`, `40-59`, `60+`, compatíveis com o gradiente da PNS e com a regra do dado real |
| A3 | Atraso de digitação no painel ML | Média de `dt_digitacao − dt_cadastro` das FCI do quadrimestre (RQ08) |
| A4 | Hellinger (RQ04) | Distribuição de raça/cor registrada na equipe (sem vazios) contra a referência dos bairros dos domicílios adscritos, ponderada pelo nº de domicílios. Fica em `fato_painel_ml.dist_raca_cor_censo` e na visão `vw_rq04_raca_equipe` |

## Achados que o grupo deve conhecer

- **Com poucos DS, o efeito da oficina some no ruído.** A tendência própria de cada equipe (DP de 0,15 por ano no logito, cerca de 0,55 em 3,7 anos) é maior que o efeito de 0,2. Com o Recife inteiro (125 equipes tratadas), a diferença-em-diferenças recupera o efeito: +3,2 p.p. no observado, +2,9 p.p. na verdade (`docs/resultados/inferencia_base_10pct.md`). Com só dois ou três DS, não recupera.
- **A proporção vigente reage com atraso.** Só as versões feitas depois de uma oficina carregam o efeito, e a renovação leva cerca de 18 meses. Na base de 10%, as oficinas se espalham de 2024 a meados de 2026 e o pós-período é o último quadrimestre. Nessa configuração, o observado (+3,2 p.p.) ficou perto da verdade (+2,9 p.p.). Com oficinas recentes ou um pós-período curto, o observado subestima o efeito. Isso vale para a avaliação real das oficinas da SESAU.
- **A persistência é um piso alto para o ML.** A proporção muda devagar, e modelos que preveem a variação (alvo − atual) empatam com ela ou a vencem por pouco. Isso é coerente com o processo gerador e deve aparecer na discussão de ML I.
- **A RQ06 é um proxy fraco do defeito 5.** Muitos cadastros com mais de 24 meses estão corretos (precisão baixa), e o defeito real só aparece pelo gabarito.
- **Sensibilidade** (`docs/resultados/sensibilidade_3ds_3pct.md`).
  - Com λ = ln 0,5, a prevalência LGB+ estimada entre respondentes cai cerca de 0,3 p.p., um quarto da prevalência real. A pós-estratificação por idade não corrige essa queda. Com λ = 0, o viés pós-estratificado fica em torno de zero.
  - Com as oficinas nas piores equipes (alocação focalizada), a comparação ingênua no fim da série dá −28 p.p., com o sinal trocado. A diferença-em-diferenças volta a ser positiva, mas soma regressão à média ao efeito.
  - Com π = 0,9, a linha 3 fica cerca de 4 p.p. abaixo da meta: quase toda a pergunta passa a ser "não feita", e a calibração perde precisão.

