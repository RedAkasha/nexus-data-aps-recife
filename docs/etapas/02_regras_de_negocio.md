---
documento: Modelo conceitual (ER) e regras de negócio — Emulação de dados da APS para as políticas de equidade do Recife
projeto: Projeto 3 – Dados (CESAR School, 2026.2) · Equipe 2 – Nexus Data
etapa: Etapa 2 – Modelagem conceitual (modelo entidade-relacionamento)
versao: 1.0.0
data: 2026-10-19
status: rascunho para revisão do grupo
arquivos:
  - modelo_conceitual_aps_recife.brM3 (brModelo 3.2)
  - modelo_conceitual_aps_recife.xml (mesmo modelo no formato XML do brModelo)
  - modelo_conceitual_aps_recife.png (imagem exportada pelo próprio brModelo)
base: dicionario_dados.md v1.0.0; Emulacao_Dados_APS_Recife_Projeto3_v3 (Figura 13 e Tabela 8)
---

# Modelo conceitual e regras de negócio — Etapa 2

Este documento acompanha o diagrama ER feito no brModelo e cumpre o produto da Etapa 2 do plano: o diagrama e a descrição das regras de negócio. O modelo parte da proposta da Figura 13 e foi conferido campo a campo contra o dicionário de dados v1.0.0. As mudanças em relação à figura estão na seção 6.

## 1. Como abrir

No brModelo, use **Arquivo → Abrir** e escolha `modelo_conceitual_aps_recife.brM3`. Se a versão do Java da máquina recusar o binário, abra o `modelo_conceitual_aps_recife.xml` pela mesma opção, com o filtro "BrModelo(xml)". O conteúdo é o mesmo.

O diagrama tem **15 entidades**, **16 relacionamentos** e **80 atributos**. Cada entidade traz no campo *Dicionário* do brModelo uma descrição curta e as regras que se aplicam a ela. Cada atributo traz no campo *Tipo* o tipo SQL proposto, que o conversor do brModelo usa ao gerar o modelo lógico.

**Leitura das cardinalidades.** O brModelo usa a notação de Peter Chen adotada por Heuser. A cardinalidade escrita junto a uma entidade diz quantas ocorrências **dessa** entidade se associam a **uma** ocorrência da outra. Exemplo: em DISTRITO_SANITARIO (1,1) — contém — (1,n) UNIDADE_SAUDE, cada unidade está em exatamente um distrito e cada distrito contém uma ou mais unidades.

**Atributos.** Círculo preenchido marca o identificador. Círculo tracejado marca atributo opcional, que pode ficar vazio. Atributos codificados (raça/cor, orientação sexual etc.) aparecem como atributos simples no conceitual. Os valores aceitos são os domínios da seção 6 do dicionário, e cada domínio vira uma tabela de referência no modelo lógico (Etapa 3).

## 2. Entidades

| Entidade | O que representa | Identificador | Origem | Regras |
|---|---|---|---|---|
| DISTRITO_SANITARIO | Distritos Sanitários I a VIII | `id_ds` | Prefeitura do Recife (não existe no PEC) | RN01 |
| UNIDADE_SAUDE | Estabelecimento de saúde (USF, ECR, CAI…) | `cnes` | CNES real; `headerTransport.cnes` | RN02 |
| EQUIPE | Equipe de saúde | `ine` | INE real; `headerTransport.ine` | RN03 |
| PROFISSIONAL | Profissional fictício que registra fichas | `cns_profissional` | `headerTransport.profissionalCNS`, `cboCodigo_2002` | RN04 |
| MICROAREA | Microárea de uma equipe | `id_microarea` | `microarea` (FCI), `microArea` (FCDT) | RN05 |
| CIDADAO | Pessoa sintética, com atributos estáveis | `id_cidadao` | Projeto (LEDI só tem CPF/CNS) | RN06 |
| CADASTRO_INDIVIDUAL | Uma versão da FCI | `uuid` | `CadastroIndividual` e blocos internos | RN07–RN16 |
| TIPO_DEFICIENCIA | Domínio dos tipos de deficiência | `codigo_deficiencia` | Domínio `DeficienciaCidadao` | RN12 |
| ACAO_FORMATIVA | Oficina ou material recebido por uma equipe | `id_acao` | Projeto (não existe no e-SUS) | RN17–RN18 |
| ATENDIMENTO_INDIVIDUAL | Um atendimento da FAI | `id_atendimento` | `FichaAtendimentoIndividualChild` | RN19–RN22 |
| CODIGO_CLINICO | Domínio de CIAP2, CID-10 e Códigos AB | `codigo` | Campos `ciap` e `cid10` da FAI | RN21 |
| DOMICILIO | Imóvel cadastrado na FCDT | `id_domicilio` | `CadastroDomiciliar` | RN23–RN24 |
| FAMILIA | Família de um domicílio | `id_familia` | `FamiliaRow` | RN25 |
| PARAMETRO | Parâmetros de cada carga | `id_carga` | Projeto | RN26 |
| CONTROLE_DEFEITO | Gabarito dos defeitos injetados | `id_defeito` | Projeto (Etapa 7) | RN27 |

PARAMETRO e CONTROLE_DEFEITO não têm relacionamentos por desenho. A primeira é lida por todas as visões; a segunda referencia registros de várias tabelas (RN26 e RN27).

## 3. Relacionamentos e cardinalidades

| Relacionamento | Entidades e cardinalidades | Leitura | Justificativa |
|---|---|---|---|
| contém | DISTRITO_SANITARIO (1,1) — UNIDADE_SAUDE (1,n) | Cada unidade está em um distrito; cada distrito contém ao menos uma unidade | Estrutura territorial da SESAU |
| abriga | UNIDADE_SAUDE (1,1) — EQUIPE (1,n) | Cada equipe pertence a uma unidade; cada unidade abriga ao menos uma equipe | CNES/INE |
| abrange | EQUIPE (1,1) — MICROAREA (1,n) | Cada microárea é de uma equipe; cada equipe tem ao menos uma microárea | Microárea 01–99 é numerada dentro da equipe |
| lota | EQUIPE (1,1) — PROFISSIONAL (1,n) | Cada profissional está lotado em uma equipe; cada equipe tem ao menos um profissional | Simplificação (seção 6) |
| recebe | EQUIPE (1,1) — ACAO_FORMATIVA (0,n) | Cada ação é de uma equipe; uma equipe pode não ter recebido nenhuma | O efeito das oficinas é medido por equipe |
| responde por | EQUIPE (0,1) — CADASTRO_INDIVIDUAL (0,n) | Cada versão aponta a equipe responsável, se houver; uma equipe responde por zero ou mais versões | `ine` não é obrigatório no LEDI |
| registra | PROFISSIONAL (1,1) — CADASTRO_INDIVIDUAL (0,n) | Cada versão é registrada por um profissional | `profissionalCNS` é obrigatório |
| possui | CIDADAO (1,1) — CADASTRO_INDIVIDUAL (1,n) | Cada versão é de um cidadão; todo cidadão tem ao menos uma versão | Cidadão só existe no banco a partir de um cadastro |
| atualiza (autorrelacionamento) | CADASTRO_INDIVIDUAL originadora (0,1) — atualização (0,n) | Uma atualização aponta a versão que a originou; uma versão pode originar várias | `uuidFichaOriginadora` (RN08) |
| declara | CADASTRO_INDIVIDUAL (0,n) — TIPO_DEFICIENCIA (0,n) | Uma versão declara de 0 a 6 tipos; um tipo aparece em várias versões | `deficienciasCidadao` é lista (N:N) |
| localiza | MICROAREA (0,1) — DOMICILIO (0,n) | Um domicílio está em no máximo uma microárea; fora de área, em nenhuma | `stForaArea` (R7 do dicionário) |
| reside em | DOMICILIO (1,1) — FAMILIA (0,n) | Cada família reside em um domicílio; comércio, terreno etc. não têm família | `familias` só para tipo de imóvel `1` |
| compõe | FAMILIA (0,1) — CIDADAO (1,n) | Um cidadão compõe no máximo uma família; toda família tem ao menos um membro | Cidadão pode estar cadastrado sem vínculo familiar |
| realiza | PROFISSIONAL (1,1) — ATENDIMENTO_INDIVIDUAL (0,n) | Cada atendimento tem um profissional principal | `lotacaoFormPrincipal` é obrigatório |
| é atendido em | CIDADAO (1,1) — ATENDIMENTO_INDIVIDUAL (0,n) | Cada atendimento é de um cidadão; um cidadão pode não ter atendimento | No banco sintético todo atendimento é identificado |
| avalia | ATENDIMENTO_INDIVIDUAL (0,n) — CODIGO_CLINICO (1,n) | Cada atendimento avalia ao menos um código; um código aparece em vários atendimentos | `problemasCondicoes` tem mínimo 1 |

## 4. Regras de negócio

Cada regra indica a origem e onde deve ser garantida: **estrutura** (chave, FK, cardinalidade), **restrição** (`CHECK`, `UNIQUE`, gatilho) ou **derivação** (visão ou consulta).

### 4.1 Território e equipes

**RN01 — Distrito Sanitário.** O Recife tem oito Distritos Sanitários, de I a VIII. Toda unidade de saúde pertence a exatamente um distrito. O distrito não existe no PEC, então a ligação vem da tabela territorial da Prefeitura. *Origem:* plano, seção 1. *Garantia:* estrutura (FK obrigatória).

**RN02 — Unidade de saúde.** A unidade é identificada pelo CNES real, de 7 dígitos. Nome e tipo vêm do CNES e não são digitados. As 143–144 linhas da planilha precisam ser conciliadas com as 141 USF antes da carga (modalidades eCR e CAI). *Origem:* dicionário, seção 8; plano, seção 2.1. *Garantia:* restrição (`CHAR(7)`, só dígitos).

**RN03 — Equipe.** A equipe é identificada pelo INE real, de 10 dígitos, e pertence a uma unidade. É a unidade de análise do painel e do problema de ML (equipe × período). *Origem:* reunião de 01/09; plano, Tabela 10. *Garantia:* estrutura e restrição (`CHAR(10)`).

**RN04 — Profissional.** O profissional é fictício, identificado por CNS sintético com dígito verificador válido. O CBO deve estar entre os permitidos para o modelo de informação da ficha que ele registra (Grupos de CBO do LEDI). No modelo, cada profissional fica lotado em uma equipe. *Origem:* LEDI, `headerTransport`. *Garantia:* restrição (validação de CNS; CBO contra domínio).

**RN05 — Microárea.** A microárea tem código de 01 a 99, único dentro da equipe (`UNIQUE(ine, codigo_microarea)`). Microáreas de equipes diferentes podem repetir o código. *Origem:* fichas (legenda "usar 01 a 99"). *Garantia:* restrição.

### 4.2 Cidadão e cadastro individual

**RN06 — Cidadão.** O cidadão guarda só os atributos estáveis da pessoa: data de nascimento, sexo e identificadores. CPF e CNS são sintéticos, com dígito verificador válido, únicos quando preenchidos, e ao menos um dos dois é obrigatório (`CHECK (cpf IS NOT NULL OR cns IS NOT NULL)`). O nome é gerado pelo Faker e nunca corresponde a pessoa real. A mesma pessoa cadastrada duas vezes, uma por CPF e outra por CNS, é representada como **dois cidadãos**. É o defeito de duplicidade da Etapa 7, registrado em CONTROLE_DEFEITO. *Origem:* plano, Tabela 8; dicionário, D9. *Garantia:* restrição.

**RN07 — Versões do cadastro.** Cada envio de FCI é uma nova versão em CADASTRO_INDIVIDUAL, identificada pelo `uuid`. Todo cidadão tem ao menos uma versão, e cada versão pertence a um único cidadão. Versões antigas nunca são apagadas nem sobrescritas. *Origem:* LEDI, `uuid` e `fichaAtualizada`. *Garantia:* estrutura.

**RN08 — Cadeia de atualizações.** A primeira versão de um cidadão não tem originadora. No LEDI ela é marcada com `uuidFichaOriginadora = uuid`; no banco, a FK fica nula. Uma versão com `ficha_atualizada = true` aponta obrigatoriamente a versão que a originou, e ambas pertencem ao mesmo cidadão. *Origem:* LEDI, `uuidFichaOriginadora`. *Garantia:* restrição (`CHECK` e gatilho para "mesmo cidadão").

**RN09 — Versão vigente.** Na data de corte, a versão vigente de um cidadão é a de maior `dt_cadastro` menor ou igual a `parametro.data_corte`. Só ela entra nos indicadores. Contar todas as versões infla os totais. *Origem:* plano, Etapa 8 e Tabela 9. *Garantia:* derivação (visão `vw_cadastro_vigente`).

**RN10 — Cidadão ativo e saída.** É ativo o cidadão cuja versão vigente não tem `motivo_saida`. Se a saída for Óbito (`135`), `dt_obito` é obrigatória e fica entre `dt_nascimento` e `dt_cadastro`. Se for Mudança de território (`136`), `dt_obito` fica nula. Ainda falta confirmar se versões com recusa de cadastro entram entre os ativos. *Origem:* LEDI, `SaidaCidadaoCadastro`; dicionário, seção 8 (coluna H). *Garantia:* restrição (`CHECK`) e derivação.

**RN11 — Vínculo do cidadão à equipe.** O cidadão é ligado à equipe **pela versão do cadastro**, e não por um atributo fixo da pessoa. A equipe do cidadão na data de corte é a equipe da versão vigente. A versão pode não ter equipe, porque `ine` não é obrigatório no LEDI. A microárea gravada na versão deve existir na equipe responsável. Com `fora_area = true`, a microárea fica nula. *Origem:* plano, decisão (ii) da Etapa 2; dicionário, R7. *Garantia:* restrição (`CHECK`) e gatilho para a microárea da equipe.

**RN12 — Deficiência.** Com `tem_deficiencia = true`, a versão declara de 1 a 6 tipos em `declara`. Com `false`, não declara nenhum. Nulo significa falha de registro, não "Não", porque o campo não é obrigatório no LEDI 8.7.0. Os tipos aceitos são os do domínio, incluindo TEA (`232`). *Origem:* LEDI, `deficienciasCidadao`; dicionário, D1 e D4. *Garantia:* gatilho (contagem de tipos) e estrutura (PK composta impede tipo repetido).

**RN13 — Orientação sexual.** `deseja_informar_os = true` exige `orientacao_sexual` preenchida. `false` exige `orientacao_sexual` nula. `deseja_informar_os` nulo representa "não informado" e só ocorre em cadastros legados. *Origem:* LEDI, R1 do dicionário; dicionário, D5. *Garantia:* restrição (`CHECK`).

**RN14 — Identidade de gênero.** A mesma regra da RN13 vale para `deseja_informar_ig` e `identidade_genero`. *Origem:* LEDI, R2. *Garantia:* restrição.

**RN15 — Raça/cor e etnia.** Raça/cor é obrigatória em toda versão sem recusa. Etnia é obrigatória quando raça/cor = Indígena (`5`) e proibida nos demais casos. Raça/cor, nome social, orientação sexual, identidade de gênero e deficiência são **autodeclarados**: ficam na versão do cadastro, o que permite representar a divergência entre versões. Nenhum processo do projeto infere ou imputa esses valores. *Origem:* LEDI, R4; plano, salvaguarda da Etapa 10. *Garantia:* restrição e política de uso.

**RN16 — Recusa de cadastro.** Com `recusa_cadastro = true`, a versão não traz dados sociodemográficos nem saída: raça/cor, orientação sexual, identidade de gênero, deficiência, escolaridade, situação de trabalho e motivo de saída ficam nulos. *Origem:* LEDI, R9. *Garantia:* restrição (`CHECK`).

### 4.3 Ações formativas

**RN17 — Ação formativa por equipe.** Cada ação formativa (oficina ou material) pertence a uma única equipe. Uma oficina com várias equipes gera uma ocorrência por equipe participante. Uma equipe pode não ter recebido nenhuma ação. *Origem:* reunião de 01/09; plano, decisão (iii). *Garantia:* estrutura.

**RN18 — Efeito da ação.** A ação guarda data e tipo. O **efeito** sobre o registro não é atributo do banco: é parâmetro do gerador (verdade conhecida, Tabela 6) e só aparece nos dados por meio do comportamento da equipe nas competências seguintes. Para o ML, entram como variáveis as ações realizadas até o fim do período de referência, nunca as futuras. *Origem:* plano, Tabela 10. *Garantia:* derivação (atributos de entrada do modelo).

### 4.4 Atendimentos

**RN19 — Atendimento.** Cada atendimento tem um profissional principal e um cidadão. O profissional auxiliar da FAI fica fora da v1. *Origem:* LEDI, `VariasLotacoesHeader`. *Garantia:* estrutura.

**RN20 — Datas do atendimento.** `dt_hora_inicio` não pode ser anterior a `dt_atendimento` nem posterior à data atual. `dt_nascimento` do cidadão não pode ser posterior a `dt_atendimento` nem mais de 130 anos anterior a ela. `dt_digitacao` é igual ou posterior a `dt_atendimento`, com atraso simulado por equipe. Esse campo não existe no LEDI (dicionário, seção 11). *Origem:* LEDI, R10. *Garantia:* restrição (`CHECK`) e gatilho para a data de nascimento.

**RN21 — Problemas e condições avaliados.** Cada atendimento avalia ao menos um código clínico, sem repetir o mesmo código. O código é CIAP2, CID-10 ou um dos cinco Códigos AB do LEDI, indicado em `sistema`. Não se aceita CIAP2 de pré-natal para menores de 9 anos, e `W78` só com CID-10 da família `Z34`. *Origem:* LEDI, R14; dicionário, seção 10. *Garantia:* estrutura (PK composta) e gatilho.

**RN22 — Tipo e local do atendimento.** O tipo de atendimento aceita só `1`, `2`, `4`, `5` e `6`, e o local só `1` a `10`. *Origem:* LEDI, R15. *Garantia:* restrição (`CHECK`).

### 4.5 Domicílios e famílias

**RN23 — Localização do domicílio.** O domicílio está em no máximo uma microárea. Fora de área, fica sem microárea. No núcleo, bairro e setor censitário são os únicos dados de localização. Logradouro, número, CEP e coordenadas ficam só na *staging*, gerados pelo Faker, e nunca entram em análise. O mapa é feito por Distrito Sanitário. *Origem:* dicionário, seção 4; reunião de 01/09. *Garantia:* estrutura e política de uso.

**RN24 — Situação do domicílio.** Só imóveis do tipo Domicílio (`1`) têm famílias. Um domicílio só é inativado numa atualização, quando todas as famílias se mudaram. *Origem:* LEDI, R12 e R13. *Garantia:* gatilho.

**RN25 — Família.** Cada família reside em um único domicílio e tem ao menos um membro. Um cidadão compõe no máximo uma família e pode estar cadastrado sem vínculo familiar. O responsável familiar é identificado por CPF **ou** CNS. A renda segue o domínio `RendaFamiliar`, e o número de membros, quando informado, é maior que zero. *Origem:* LEDI, `FamiliaRow`; dicionário, D12. *Garantia:* estrutura e restrição.

### 4.6 Parâmetros, qualidade e privacidade

**RN26 — Parâmetros e "dado real".** Cada carga tem uma linha em PARAMETRO com data de corte, idade mínima elegível (11 anos; 10 a confirmar), semente e fator de escala. Todas as visões leem esses valores e nunca os fixam no código. É criança quem tem, na data de corte, idade menor que `idade_min_elegivel`. Percentuais são calculados na consulta e nunca armazenados. A mesma semente gera banco idêntico. *Origem:* plano, Tabelas 6 e 9 e Apêndice B. *Garantia:* derivação.

**RN27 — Controle de defeitos.** Cada defeito injetado na Etapa 7 é registrado com a tabela, o identificador do registro afetado e o tipo do defeito: duplicidade, raça/cor errada ou divergente, cadastro desatualizado, OS/IG registrada para criança, erro de digitação, atraso de digitação. A referência é polimórfica e não tem FK, por desenho. A tabela não participa dos indicadores; serve de gabarito e de rótulo para o modelo de detecção. *Origem:* plano, Etapa 7. *Garantia:* política de uso.

**RN28 — Natureza sintética e privacidade.** Todos os registros são fictícios e não podem ser apresentados como retrato da população do Recife. Nenhum atributo autodeclarado é inferido ou imputado. A análise é feita por equipe e período, nunca por pessoa, e nenhuma geolocalização individual entra no núcleo. *Origem:* plano, Etapa 0 e seção 8; LGPD. *Garantia:* política de uso (termo de dados sintéticos).

## 5. Rastreabilidade das regras

| Regra | Dicionário v1.0.0 | Plano v3 |
|---|---|---|
| RN09, RN10, RN26 | Seção 8 (planilha) | Tabelas 6 e 9 |
| RN11 | R7 | Etapa 2, decisão (ii) |
| RN12 | R3, D1, D4, seção 9 | Tabela 7 |
| RN13, RN14 | R1, R2, D5, D6 | Tabela 3 |
| RN15 | R4 | Etapa 10 (salvaguarda) |
| RN16 | R9 | — |
| RN20 | R10, seção 11 | Etapa 6, passo 7 |
| RN21, RN22 | R14, R15, seção 10 | Seção 3.3 |
| RN23, RN24, RN25 | R7, R12, R13, D12 | Etapa 6, passo 1 |
| RN27 | D9 | Etapa 7 |

## 6. Decisões de modelagem em relação à Figura 13

| Mudança | Motivo |
|---|---|
| Entrou **TIPO_DEFICIENCIA**, e `cadastro_deficiencia` virou o relacionamento N:N **declara** | No conceitual, a tabela associativa é um relacionamento; ela volta a ser tabela no lógico |
| Entrou **CODIGO_CLINICO**, com o relacionamento N:N **avalia** | Um atendimento avalia vários CIAP2/CID-10 (`problemasCondicoes` é lista) |
| Entrou o autorrelacionamento **atualiza** em CADASTRO_INDIVIDUAL | Representa a cadeia `uuid`/`uuidFichaOriginadora`, base da versão vigente |
| A ligação equipe–versão do cadastro ficou **(0,1)** do lado da equipe | `ine` não é obrigatório no LEDI 8.7.0 |
| A microárea do cadastro ficou como **atributo**, e não relacionamento | Evita ciclo com equipe; a coerência é garantida pela RN11 |
| A ligação profissional–equipe ficou **(1,1)** para o profissional | Simplificação: no PEC real o profissional pode ter várias lotações, mas cada ficha já traz CNES e INE no cabeçalho. Pode virar N:N no lógico se o grupo quiser |
| As tabelas de domínio da Figura 13 viraram **atributos com domínio** | Diagrama legível; os domínios do LEDI entram como tabelas de referência na Etapa 3 |
| `dt_digitacao` entrou em CADASTRO_INDIVIDUAL e ATENDIMENTO_INDIVIDUAL | Exigência do plano (seção 3.1), mesmo sem campo no LEDI |
| CIDADAO ganhou `nome` sintético | Necessário para simular erros de grafia (Etapa 7); nunca entra em análise |

## 7. Pendências que afetam o modelo

- Se versões com recusa de cadastro contam entre os ativos (RN10). Isso muda a coluna H da planilha.
- Idade mínima elegível de 10 ou 11 anos (RN26; Apêndice A, pergunta 1).
- Semântica de `st_informar_orientacao_sexual` no DW (dicionário, D6), antes de montar a *staging* a partir do DW real.
- Se o profissional deve ter lotação N:N (seção 6), caso o grupo vá emular profissionais em mais de uma equipe.

## Histórico de versões

| Versão | Data | Alteração |
|---|---|---|
| 1.0.0 | 2026-10-19 | Primeira versão: diagrama ER no brModelo (15 entidades, 16 relacionamentos, 80 atributos) e regras RN01–RN28 |
