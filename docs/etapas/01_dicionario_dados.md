---
documento: Dicionário de dados — Emulação de dados da APS para as políticas de equidade do Recife
projeto: Projeto 3 – Dados (CESAR School, 2026.2) · Equipe 2 – Nexus Data
etapa: Etapa 1 – Levantamento de requisitos e dicionário de dados
versao: 1.0.0
data: 2026-10-19
status: rascunho para revisão do grupo
fontes:
  - LEDI APS 8.7.0 (PEC 5.5.26+), extraído em 19/10/2026
  - Data Warehouse Relatórios e-SUS APS PEC, documentação de integração 8.7.0 (alterada em 11/09/2026)
  - Fichas em papel CI/e-SUS AB v5.2, CD/e-SUS AB v3.2 e FAI/e-SUS AB v3.2
  - Emulacao_Dados_APS_Recife_Projeto3_v3 (Tabelas 1, 3, 7, 8 e 9)
---

# Dicionário de dados — Etapa 1

Este dicionário cobre os quatro itens da Etapa 1 do plano de emulação:

1. as fichas FCI, FCDT e FAI e a documentação do LEDI APS 8.7.0 e do *Data Warehouse* (DW) do PEC, que são as fontes;
2. cada campo, com nome, tipo, obrigatoriedade, domínio e regra de preenchimento condicional (seções 2 a 6);
3. o mapeamento das colunas da planilha da SESAU para os campos que as geram, com a regra do "dado real" (seção 8);
4. a correspondência entre as categorias de deficiência do IBGE e as do e-SUS (seção 9, Tabela 7 revisada).

As seções 10 a 12 registram o que a Etapa 2 precisa saber antes de modelar: a codificação das condições da FAI, os campos que o projeto cria e que não existem no e-SUS, e as divergências encontradas entre as fontes.

O arquivo é Markdown puro para ser versionado no Git junto com o DDL e o gerador. Cada alteração entra no histórico ao final e sobe a versão no cabeçalho.

## 1. Convenções

**Escopo.** As três fichas somam 275 campos no LEDI 8.7.0, sem contar o cabeçalho. Todos estão listados, mas só os usados recebem linha detalhada. A coluna **Uso** indica o destino de cada campo:

| Uso | Significado | Campos |
|---|---|---|
| `N·tabela` | Entra no **núcleo** (3FN), na tabela indicada, conforme a Tabela 8 e a Figura 13 do plano | 59 |
| `S` | Só na ***staging***: obrigatório no LEDI ou necessário para a ficha ser válida; o gerador preenche com valor padrão ou plausível, mas o campo não é analisado | 38 |
| `—` | Fora do escopo da v1: aparece só na lista "Não gerados" do bloco e fica nulo | 178 |

`N·(bloco)` marca um campo do LEDI que é um objeto aninhado; o conteúdo dele é detalhado no bloco seguinte.

**Obrigatoriedade (Obr.)**, como no LEDI: `S` sim, `N` não, `C` condicional. A condição está na coluna Regras.

**Tam.** é o mínimo–máximo de caracteres ou de itens de lista, como no LEDI.

**Coluna DW** é a coluna equivalente no DW do PEC (`tb_fat_*`). A camada *staging* deve imitar essas colunas se o dado real vier do DW. As colunas `co_dim_*` são chaves para as dimensões do DW. O DW não as liga ao campo LEDI por link; a ligação foi feita pelo nome da dimensão.

**Conversão de tipos LEDI → SQL** (proposta para a Etapa 3):

| Tipo no LEDI | Staging (formato de chegada) | Núcleo |
|---|---|---|
| `Long` de data (epoch em milissegundos) | `BIGINT` | `DATE` |
| `Long` de data e hora | `BIGINT` | `TIMESTAMP` / `DATETIME` |
| `Long` / `Integer` de código | `INT` | `SMALLINT` com FK para a tabela de domínio |
| `String` de tamanho fixo (CPF 11, CNS 15, CNES 7, INE 10, IBGE 7, CBO 6) | `VARCHAR` | `CHAR(n)` com `CHECK` de formato |
| `String` livre | `VARCHAR(máx)` | `VARCHAR(máx)` |
| `Boolean` | `BOOLEAN` | `BOOLEAN`, aceitando `NULL` quando ausência tem significado (ver seção 8) |
| `List<Long>` | texto ou JSON | tabela associativa N:N (ex.: `cadastro_deficiencia`) |
| `List<Objeto>` | tabela filha | tabela filha com FK |
| `Double` | `DOUBLE` | `DECIMAL(p,s)` |

## 2. Cabeçalho comum

#### Cabeçalho de ficha única (`UnicaLotacaoHeader`)

Usado pela FCI e pela FCDT: um profissional por ficha.

| # | Campo LEDI | Descrição | Tipo | Obr. | Tam. | Domínio | Regras LEDI | Coluna DW | Uso |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `profissionalCNS` | CNS do profissional. | String | S | 15 |  | CNS validado de acordo com o algoritmo de validação; Somente registros de profissionais com vínculo com o respectivo município são considerados válidos | `tb_fat_*.co_dim_profissional` | N·profissional |
| 2 | `cboCodigo_2002` | Código do CBO do profissional. | String | S |  | [Grupos de CBO por ficha](https://integracao.esusaps.bridge.ufsc.tech/ledi/documentacao/regras/grupo_cbo.html) | Somente as CBOs apresentadas na tabela do respectivo modelo de informação podem ser adicionadas neste campo | `tb_fat_*.co_dim_cbo` | N·profissional |
| 3 | `cnes` | Código do CNES do estabelecimento de saúde onde o profissional está lotado. | String | S | 7 |  | Deve ser preenchido com a mesma informação do campo #3 cnesDadoSerializado | `tb_fat_*.co_dim_unidade_saude` | N·unidade_saude |
| 4 | `ine` | Código INE da equipe do profissional. | String | N | 10 |  | Deve ser preenchido com a mesma informação do campo #5 ineDadoSerializado | `tb_fat_*.co_dim_equipe` | N·equipe |
| 5 | `dataAtendimento` | Data em que está sendo realizada a ação. | Long | S |  |  | Não pode ser posterior à data atual | `tb_fat_*.co_dim_tempo` | N·(data da ficha) |
| 6 | `codigoIbgeMunicipio` | Código IBGE do município. | String | S | 7 | Municípios (IBGE, 7 dígitos) | Deve ser preenchido com a mesma informação do campo #4 codIbge | `tb_fat_*.co_dim_municipio` | S |

#### Cabeçalho de várias lotações (`VariasLotacoesHeader`)

Usado pela FAI: profissional principal e, opcionalmente, um compartilhado.

| # | Campo LEDI | Descrição | Tipo | Obr. | Tam. | Domínio | Regras LEDI | Coluna DW | Uso |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `lotacaoFormPrincipal` | Profissional responsável pelo atendimento. | LotacaoHeader | S |  |  |  |  | N·profissional |
| 2 | `lotacaoFormAtendimentoCompartilhado` | Profissional auxiliar no atendimento. | LotacaoHeader | N |  |  |  |  | — |
| 3 | `dataAtendimento` | Data em que está sendo realizada a ação. | Long | S |  |  | Não pode ser posterior à data atual | `tb_fat_*.co_dim_tempo` | N·atendimento_individual |
| 4 | `codigoIbgeMunicipio` | Código IBGE do município. | String | S | 7 | Municípios (IBGE, 7 dígitos) | Deve ser preenchido com a mesma informação do campo #4 codIbge | `tb_fat_*.co_dim_municipio` | S |

#### Lotação do profissional (`LotacaoHeader`)

Conteúdo de `lotacaoFormPrincipal` e `lotacaoFormAtendimentoCompartilhado` da FAI.

| # | Campo LEDI | Descrição | Tipo | Obr. | Tam. | Domínio | Regras LEDI | Coluna DW | Uso |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `profissionalCNS` | CNS do profissional. | String | S | 15 |  | CNS validado de acordo com o algoritmo de validação; Somente registros de profissionais com vínculo com o respectivo município são considerados válidos | `tb_fat_*.co_dim_profissional` | N·profissional |
| 2 | `cboCodigo_2002` | Código do CBO do profissional. | String | S |  | [Grupos de CBO por ficha](https://integracao.esusaps.bridge.ufsc.tech/ledi/documentacao/regras/grupo_cbo.html) | Se for registro de lotacaoFormPrincipal somente as Grupos de CBOs por Modelo de Informação apresentadas na tabela do respectivo modelo de informação podem ser adicionadas neste campo; Se for registro de lotacaoFormAtendimentoCompartilhado a referência é a Lista com todas as CBOs | `tb_fat_*.co_dim_cbo` | N·profissional |
| 3 | `cnes` | Código do CNES da unidade de saúde que o profissional está lotado. | String | S | 7 |  | Se for registro de lotacaoFormPrincipal, deve ser preenchido com a mesma informação do campo #3 cnesDadoSerializado; Se for registro de lotacaoFormAtendimentoCompartilhado, pode ser preenchido com qualquer CNES pertencente ao respectivo município | `tb_fat_*.co_dim_unidade_saude` | N·unidade_saude |
| 4 | `ine` | Código INE da equipe do profissional. | String | N | 10 |  | Se for registro de lotacaoFormPrincipal, deve ser preenchido com a mesma informação do campo #5 ineDadoSerializado; Se for registro de lotacaoFormAtendimentoCompartilhado, pode ser preenchido com qualquer INE pertencente ao respectivo município | `tb_fat_*.co_dim_equipe` | N·equipe |


## 3. Ficha de Cadastro Individual (FCI)

Ficha em papel CI/e-SUS AB v5.2. Modelo de informação LEDI `CadastroIndividual`. Fato no DW: `tb_fat_cad_individual`.

Cada envio é uma **versão** do cadastro. A primeira versão tem `uuidFichaOriginadora = uuid`; as atualizações (`fichaAtualizada = true`) apontam para o `uuid` da versão que as originou. É essa cadeia que permite separar `cidadao` de `cadastro_individual` no modelo ER.

#### Registro principal (`CadastroIndividual`)

| # | Campo LEDI | Descrição | Tipo | Obr. | Tam. | Domínio | Regras LEDI | Coluna DW | Uso |
|---|---|---|---|---|---|---|---|---|---|
| 4 | `fichaAtualizada` | Marcador que indica se o registro é uma atualização. | Boolean | S |  |  | Caso seja um registro de atualização, o campo uuidFichaOriginadora deve ser preenchido com o UUID do registro que o originou |  | N·cadastro_individual |
| 5 | `identificacaoUsuarioCidadao` | Dados que identificam o cidadão. | IdentificacaoUsuarioCidadao | C |  |  | Opcional se o campo statusTermoRecusaCadastroIndividualAtencaoBasica = true |  | N·(bloco) |
| 6 | `informacoesSocioDemograficas` | Informações sociodemográficas fornecidas pelo cidadão. | InformacoesSocioDemograficas | C |  |  | Não deve ser preenchido se o campo statusTermoRecusaCadastroIndividualAtencaoBasica = true |  | N·(bloco) |
| 7 | `statusTermoRecusaCadastroIndividualAtencaoBasica` | Marcador que indica se o termo de recusa foi assinalado. | Boolean | N |  |  |  | `tb_fat_cad_individual.st_recusa_cadastro` | N·cadastro_individual |
| 8 | `tpCdsOrigem` | Tipo de origem dos dados do registro. | Integer | S | 1 |  | Utilizar valor 3 (sistemas terceiros) |  | S |
| 9 | `uuid` | Código UUID para identificar o registro na base de dados nacional. | String | C | 36–44 |  | É recomendado concatenar o CNES na frente do UUID, de modo que os 7 dígitos (CNES) + 1 de hífen somados aos 36 (32 caracteres + 4 hífen) do UUID são a limitação de 44 bytes do campo. Formato canônico | `tb_fat_cad_individual.nu_uuid_ficha` | N·cadastro_individual |
| 10 | `uuidFichaOriginadora` | Código UUID para identificar o registro que originou o cadastro atual. | String | S | 36–44 |  | Se for um registro de atualização, deve ser preenchido com o UUID do registro que o originou. Se for um registro de cadastro, este campo deve ser igual ao campo UUID | `tb_fat_cad_individual.nu_uuid_ficha_origem` | N·cadastro_individual |
| 12 | `saidaCidadaoCadastro` | Dados referentes a saída do cidadão do cadastro. | SaidaCidadaoCadastro | N |  |  |  |  | N·(bloco) |
| 13 | `headerTransport` | Dados referentes ao profissional e a data do cadastro. | UnicaLotacaoHeader | S |  |  | Somente as CBOs apresentadas na Tabela 1 - CBOs que podem registrar o Modelo de Informação de Cadastro Individual podem ser adicionadas no campo CBO do profissional |  | N·(bloco) |

Não gerados na v1 (permanecem nulos na *staging*): `condicoesDeSaude` (CondicoesDeSaude), `emSituacaoDeRua` (EmSituacaoDeRua).

#### Identificação do usuário/cidadão (`IdentificacaoUsuarioCidadao`)

| # | Campo LEDI | Descrição | Tipo | Obr. | Tam. | Domínio | Regras LEDI | Coluna DW | Uso |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `nomeSocial` | Nome social do cidadão. | String | N | 0–70 |  | Somente texto e apóstrofo (') | `tb_fat_cad_individual.no_nome_social` | N·cadastro_individual |
| 2 | `codigoIbgeMunicipioNascimento` | Código IBGE do município. | String | C | 7 | Municípios (IBGE, 7 dígitos) | Só pode ser preenchido se o campo nacionalidadeCidadao = 1 (Brasileiro). Neste caso é de preenchimento obrigatório | `tb_fat_cad_individual.co_dim_municipio_cidadao` | S |
| 3 | `dataNascimentoCidadao` | Data de nascimento do cidadão no formato epoch time. | Long | S |  |  | Não pode ser posterior a dataAtendimento ou mais anterior que 130 anos a partir da dataAtendimento | `tb_fat_cad_individual.dt_nascimento` | N·cidadao |
| 4 | `desconheceNomeMae` | Marcador que indica que o cidadão desconhece o nome da mãe | Boolean | N |  |  |  | `tb_fat_cad_individual.st_desconhece_mae` | S |
| 6 | `nacionalidadeCidadao` | Código do marcador que indica se o cidadão é brasileiro, naturalizado ou estrangeiro. | Long | S |  | [Nacionalidade](#dom-nacionalidade) |  | `tb_fat_cad_individual.co_dim_nacionalidade` | S |
| 7 | `nomeCidadao` | Nome completo do cidadão. | String | S | 3–70 |  | As regras de validação de um nome estão descritas em Validar nome | `tb_fat_cad_individual.no_nome` | S |
| 8 | `nomeMaeCidadao` | Nome da mãe do cidadão. | String | C | 3–70 |  | As regras de validação de um nome estão descritas em Validar nome; Não deve ser preenchido se o campo desconheceNomeMae = true | `tb_fat_cad_individual.no_nome_mae` | S |
| 9 | `cnsCidadao` | CNS do cidadão. | String | C | 15 |  | Validado por algoritmo; Não pode ser preenchido se o campo cpfCidadao for preenchido; Este campo é de preenchimento obrigatório apenas se o campo cpfCidadao não estiver preenchido e o campo stNaoPossuiCpf = true | `tb_fat_cad_individual.nu_cns` | N·cidadao |
| 10 | `cnsResponsavelFamiliar` | CNS do responsável do cidadão. | String | N | 15 |  | Validado por algoritmo; Só pode ser preenchido se o campo statusEhResponsavel = false; Não pode ser preenchido se o campo cpfResponsavelFamiliar for preenchido | `tb_fat_cad_individual.nu_cns_responsavel` | N·cadastro_individual |
| 13 | `paisNascimento` | Código do país de nascimento do cidadão. | Long | C |  | Países | Só pode ser preenchido se o campo nacionalidadeCidadao = 3 (Estrangeiro). Neste caso o preenchimento é obrigatório; Se o campo nacionalidadeCidadao for igual a 1 (Brasileira), este campo deve ser preenchido com 31 (BRASIL) | `tb_fat_cad_individual.co_dim_pais_nascimento` | S |
| 14 | `racaCorCidadao` | Código da raça / cor do cidadão. | Long | S |  | [RacaCor](#dom-racacor) |  | `tb_fat_cad_individual.co_dim_raca_cor` | N·cadastro_individual |
| 15 | `sexoCidadao` | Código do sexo do cidadão. | Long | S |  | [Sexo](#dom-sexo) |  | `tb_fat_cad_individual.co_dim_sexo` | N·cidadao |
| 16 | `statusEhResponsavel` | Marcador que indica se o cidadão é responsável familiar. | Boolean | N |  |  |  | `tb_fat_cad_individual.st_responsavel_familiar` | N·cadastro_individual |
| 17 | `etnia` | Etnia do cidadão. | Long | C |  | [etnia](#dom-etnia) | Só deve ser preenchido se o campo racaCorCidadao = 5. Neste caso o preenchimento é obrigatório; O campo deve ser preenchido com a informação da coluna Código descrito no Dicionário de dados | `tb_fat_cad_individual.co_dim_etnia` | N·cadastro_individual |
| 18 | `nomePaiCidadao` | Nome do pai do cidadão. | String | C | 3–70 |  | As regras de validação de um nome estão descritas em Validar nome; Não deve ser preenchido se o campo desconheceNomePai = true. Caso contrário, o preenchimento é obrigatório | `tb_fat_cad_individual.no_nome_pai` | S |
| 19 | `desconheceNomePai` | Marcador que indica que o cidadão desconhece o nome do pai. | Boolean | N |  |  |  | `tb_fat_cad_individual.st_desconhece_pai` | S |
| 23 | `microarea` | Microárea na qual o cidadão se encontra. | String | N | 2 |  | Não deve ser preenchido se o campo stForaArea = true | `tb_fat_cad_individual.nu_micro_area` | N·cadastro_individual |
| 24 | `stForaArea` | Marcador que indica que o cidadão está fora da área. | Boolean | N |  |  |  |  | N·cadastro_individual |
| 25 | `cpfCidadao` | CPF do cidadão. | String | C | 11 |  | Somente CPF válido será aceito; Não pode ser preenchido se o campo cnsCidadao for preenchido; Este campo é de preenchimento obrigatório se o campo cnsCidadao não estiver preenchido e o campo stNaoPossuiCpf = false | `tb_fat_cad_individual.nu_cpf_cidadao` | N·cidadao |
| 26 | `cpfResponsavelFamiliar` | CPF do responsável do cidadão. | String | N | 11 |  | Somente CPF válido será aceito; Só pode ser preenchido se o campo statusEhResponsavel = false; Não pode ser preenchido se o campo cnsResponsavelFamiliar for preenchido | `tb_fat_cad_individual.nu_cpf_responsavel` | N·cadastro_individual |
| 30 | `stNaoPossuiCpf` | Marcador que indica que o CPF do cidadão não existe ou não está disponível no momento do cadastro. | Boolean | S |  |  |  | `tb_fat_cad_individual.st_nao_possui_cpf` | N·cidadao |
| 31 | `justificativaNaoPossuiCpf` | Justificativa para o cidadão não possuir ou não informar CPF. | Long | C |  | [JustificativaNaoPossuiCpf](#dom-justificativanaopossuicpf) | É permitido o envio apenas de justificativas que constam na listagem de referência; Não pode ser preenchido se o campo stNaoPossuiCpf = false; É obrigatório se o campo stNaoPossuiCpf = true | `tb_fat_cad_individual.co_dim_just_nao_possui_cpf` | S |

Não gerados na v1 (permanecem nulos na *staging*): `emailCidadao` (String), `telefoneCelular` (String), `numeroNisPisPasep` (String), `dtNaturalizacao` (Long), `portariaNaturalizacao` (String), `dtEntradaBrasil` (Long), `estadoCivil` (Long), `tipoSanguineo` (Long), `dnv` (String).

#### Informações sociodemográficas (`InformacoesSocioDemograficas`)

Bloco das três políticas de equidade: deficiência, orientação sexual e identidade de gênero.

| # | Campo LEDI | Descrição | Tipo | Obr. | Tam. | Domínio | Regras LEDI | Coluna DW | Uso |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `deficienciasCidadao` | Código das deficiências que o cidadão possui. | List&lt;Long&gt; | C | 1–6 | [DeficienciaCidadao](#dom-deficienciacidadao) | Requerido preenchimento de pelo menos um item se o campo statusTemAlgumaDeficiencia = true; Não deve ser preenchido se o campo statusTemAlgumaDeficiencia = false | `tb_fat_cad_individual.st_defi_auditiva st_defi_intelectual_cognitiva st_defi_outra st_defi_visual st_defi_fisica` | N·cadastro_deficiencia |
| 2 | `grauInstrucaoCidadao` | Código do curso mais elevado que o cidadão frequenta ou frequentou. | Long | N |  | [CursoMaisElevado](#dom-cursomaiselevado) |  | `tb_fat_cad_individual.co_dim_tipo_escolaridade` | N·cadastro_individual |
| 4 | `orientacaoSexualCidadao` | Código da orientação sexual informada pelo cidadão. | Long | C |  | [OrientacaoSexual](#dom-orientacaosexual) | Não pode ser preenchido se o campo statusDesejaInformarOrientacaoSexual = false; É de preenchimento obrigatório se o campo statusDesejaInformarOrientacaoSexual = true | `tb_fat_cad_individual.co_dim_tipo_orientacao_sexual` | N·cadastro_individual |
| 6 | `relacaoParentescoCidadao` | Código da relação de parentesco com o responsável familiar. | Long | N |  | [RelacaoParentesco](#dom-relacaoparentesco) | Só pode ser preenchido se o campo statusEhResponsavel = false | `tb_fat_cad_individual.co_dim_tipo_parentesco` | S |
| 7 | `situacaoMercadoTrabalhoCidadao` | Código da situação do cidadão no mercado de trabalho. | Long | N |  | [SituacaoMercadoTrabalho](#dom-situacaomercadotrabalho) |  | `tb_fat_cad_individual.co_dim_situacao_trabalho` | N·cadastro_individual |
| 8 | `statusDesejaInformarOrientacaoSexual` | Marcador que indica se o cidadão deseja informar sua orientação sexual. | Boolean | S |  |  |  | `tb_fat_cad_individual.st_informar_orientacao_sexual` | N·cadastro_individual |
| 10 | `statusFrequentaEscola` | Marcador que indica se o cidadão frequenta escola ou creche. | Boolean | N |  |  |  | `tb_fat_cad_individual.st_frequenta_creche` | S |
| 11 | `statusMembroPovoComunidadeTradicional` | Marcador que indica se o cidadão é membro de um povo ou comunidade tradicional. | Boolean | N |  |  |  | `tb_fat_cad_individual.st_comunidade_tradicional` | S |
| 14 | `statusTemAlgumaDeficiencia` | Marcador que indica se cidadão tem alguma deficiência. | Boolean | N |  |  |  | `tb_fat_cad_individual.st_deficiencia` | N·cadastro_individual |
| 15 | `identidadeGeneroCidadao` | Código da identidade de gênero informada pelo cidadão. | Long | C |  | [identidadeGeneroCidadao](#dom-identidadegenerocidadao) | Não pode ser preenchido se o campo statusDesejaInformarIdentidadeGenero = false; É de preenchimento obrigatório se o campo statusDesejaInformarIdentidadeGenero = true | `tb_fat_cad_individual.co_dim_identidade_genero` | N·cadastro_individual |
| 16 | `statusDesejaInformarIdentidadeGenero` | Marcador que indica se o cidadão deseja informar sua identidade de gênero. | Boolean | S |  |  |  | `tb_fat_cad_individual.st_informar_identidade_genero` | N·cadastro_individual |
| 18 | `coPovoComunidadeTradicional` | Código do povo ou comunidade tradicional que o cidadão pertence. | Long | N |  | [povoComunidadeTradicional](#dom-povocomunidadetradicional) | Não deve ser preenchido se o campo statusMembroPovoComunidadeTradicional = false | `tb_fat_cad_individual.co_dim_povo_comunidad_trad` | S |

Não gerados na v1 (permanecem nulos na *staging*): `ocupacaoCodigoCbo2002` (String), `statusFrequentaBenzedeira` (Boolean), `statusParticipaGrupoComunitario` (Boolean), `statusPossuiPlanoSaudePrivado` (Boolean), `responsavelPorCrianca` (List&lt;Long&gt;).

#### Saída do cidadão do cadastro (`SaidaCidadaoCadastro`)

Define o status "ativo" usado no relatório.

| # | Campo LEDI | Descrição | Tipo | Obr. | Tam. | Domínio | Regras LEDI | Coluna DW | Uso |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `motivoSaidaCidadao` | Código do motivo da saída do cidadão do cadastro. | Long | N |  | [MotivoSaida](#dom-motivosaida) | Não pode ser preenchido se o campo statusTermoRecusaCadastroIndividualAtencaoBasica = true | `tb_fat_cad_individual.co_dim_tipo_saida_cadastro` | N·cadastro_individual |
| 2 | `dataObito` | Data de óbito do cidadão. | Long | C |  |  | Só pode ser preenchido se o campo motivoSaidaCidadao = 135. Neste caso o preenchimento é obrigatório; Não pode ser anterior a dataNascimentoCidadao; Não pode ser anterior a dtEntradaBrasil; Não pode ser anterior a dtNaturalizacao; Não pode ser posterior a dataAtendimento | `tb_fat_cad_individual.dt_obito` | N·cadastro_individual |
| 3 | `numeroDO` | Número da declaração de óbito do cidadão. | String | N | 9 |  | Só pode ser preenchido se o campo motivoSaidaCidadao = 135 | `tb_fat_cad_individual.nu_obito_do` | S |

#### Condições de saúde autorreferidas (`CondicoesDeSaude`)

Não gerados na v1 (permanecem nulos na *staging*): `descricaoCausaInternacaoEm12Meses` (String), `descricaoOutraCondicao1` (String), `descricaoOutraCondicao2` (String), `descricaoOutraCondicao3` (String), `descricaoPlantasMedicinaisUsadas` (String), `doencaCardiaca` (List&lt;Long&gt;), `doencaRespiratoria` (List&lt;Long&gt;), `doencaRins` (List&lt;Long&gt;), `maternidadeDeReferencia` (String), `situacaoPeso` (Long), `statusEhDependenteAlcool` (Boolean), `statusEhDependenteOutrasDrogas` (Boolean), `statusEhFumante` (Boolean), `statusEhGestante` (Boolean), `statusEstaAcamado` (Boolean), `statusEstaDomiciliado` (Boolean), `statusTemDiabetes` (Boolean), `statusTemDoencaRespiratoria` (Boolean), `statusTemHanseniase` (Boolean), `statusTemHipertensaoArterial` (Boolean), `statusTemTeveCancer` (Boolean), `statusTemTeveDoencasRins` (Boolean), `statusTemTuberculose` (Boolean), `statusTeveAvcDerrame` (Boolean), `statusTeveDoencaCardiaca` (Boolean), `statusTeveInfarto` (Boolean), `statusTeveInternadoem12Meses` (Boolean), `statusUsaOutrasPraticasIntegrativasOuComplementares` (Boolean), `statusUsaPlantasMedicinais` (Boolean), `statusDiagnosticoMental` (Boolean).

#### Cidadão em situação de rua (`EmSituacaoDeRua`)

Não gerados na v1 (permanecem nulos na *staging*): `grauParentescoFamiliarFrequentado` (String), `higienePessoalSituacaoRua` (List&lt;Long&gt;), `origemAlimentoSituacaoRua` (List&lt;Long&gt;), `outraInstituicaoQueAcompanha` (String), `quantidadeAlimentacoesAoDiaSituacaoRua` (Long), `statusAcompanhadoPorOutraInstituicao` (Boolean), `statusPossuiReferenciaFamiliar` (Boolean), `statusRecebeBeneficio` (Boolean), `statusSituacaoRua` (Boolean), `statusTemAcessoHigienePessoalSituacaoRua` (Boolean), `statusVisitaFamiliarFrequentemente` (Boolean), `tempoSituacaoRua` (Long).

#### Triagem para insegurança alimentar (TRIA) (`InformacoesSocioEconomicas`)

Não gerados na v1 (permanecem nulos na *staging*): `alimentosAcabaramAntesTerDinheiroComprarMais` (Boolean), `comeuAlgunsAlimentosQueTinhaDinheiroAcabou` (Boolean).


## 4. Ficha de Cadastro Domiciliar e Territorial (FCDT)

Ficha em papel CD/e-SUS AB v3.2. Modelo LEDI `CadastroDomiciliar`. Fatos no DW: `tb_fat_cad_domiciliar` e `tb_fat_cad_dom_familia`.

Latitude e longitude ficam de fora por decisão do projeto: a Secretaria não quer endereço individual, e o mapa é feito por Distrito Sanitário.

#### Registro principal (`CadastroDomiciliar`)

| # | Campo LEDI | Descrição | Tipo | Obr. | Tam. | Domínio | Regras LEDI | Coluna DW | Uso |
|---|---|---|---|---|---|---|---|---|---|
| 2 | `condicaoMoradia` | Condições de moradia do domicílio. | CondicaoMoradia | C |  |  | Não deve ser preenchido se o campo tipoDeImovel = 02 Comércio, 03 Terreno baldio, 04 Ponto Estratégico, 05 Escola, 06 Creche, 12 Estabelecimento Religioso, 13 CASAI ou 99 Outros; Não deve ser preenchido se o campo statusTermoRecusa = true |  | S |
| 3 | `enderecoLocalPermanencia` | Informações sobre o endereço do domicílio. | EnderecoLocalPermanencia | C |  |  | Preenchimento obrigatório caso o campo statusTermoRecusa = false |  | N·(bloco) |
| 4 | `familias` | Lista das famílias que residem no domicílio. | List&lt;FamiliaRow&gt; | C |  |  | Só pode ser preenchido se o campo tipoDeImovel = 01 Domicílio; Não pode ser preenchido se o campo stAtivo = false; Não podem ser cadastradas famílias com o mesmo numeroCnsResponsavel; Não pode ser preenchido caso o campo statusTermoRecusa = true |  | N·familia |
| 5 | `fichaAtualizada` | Marcador que indica se o registro é uma atualização. | Boolean | S | 1 |  | Caso seja um registro de atualização, o campo uuidFichaOriginadora deve ser preenchido com o UUID do registro que o originou |  | N·domicilio |
| 8 | `statusTermoRecusa` | Marcador que indica se o termo de recusa de cadastro do domicílio foi selecionado. | Boolean | N |  |  |  | `tb_fat_cad_domiciliar.st_recusa_cadastro`<br>`tb_fat_cad_dom_familia.st_recusa_cadastro` | N·domicilio |
| 9 | `tpCdsOrigem` | Tipo de origem dos dados do registro. | Integer | S | 1 |  | Utilizar valor 3 (sistemas terceiros) |  | S |
| 10 | `uuid` | Código UUID para identificar o registro na base de dados nacional. | String | S | 36–44 |  | É recomendado concatenar o CNES na frente do UUID, de modo que os 7 dígitos (CNES) + 1 de hífen somados aos 36 (32 caracteres + 4 hífen) do UUID são a limitação de 44 bytes do campo. Formato canônico | `tb_fat_cad_domiciliar.nu_uuid_ficha`<br>`tb_fat_cad_dom_familia.nu_uuid_ficha` | N·domicilio |
| 11 | `uuidFichaOriginadora` | Código UUID para identificar o registro que originou o cadastro atual. | String | S | 36–44 |  | Se for um registro de atualização, deve ser preenchido com o UUID do registro que o originou. Se for um registro de cadastro, este campo deve ser igual ao campo UUID | `tb_fat_cad_domiciliar.nu_uuid_ficha_origem`<br>`tb_fat_cad_dom_familia.nu_uuid_ficha_origem` | N·domicilio |
| 12 | `tipoDeImovel` | Indica o tipo de imóvel do domicílio. | Long | S |  | [tipoDeImovel](#dom-tipodeimovel) |  | `tb_fat_cad_domiciliar.co_dim_tipo_imovel` | N·domicilio |
| 14 | `headerTransport` | Informações sobre o profissional e a data do cadastro. | UnicaLotacaoHeader | S |  |  | Somente as CBOs apresentadas na Tabela 2 - CBOs que podem registrar o Modelo de Informação de Cadastro Domiciliar e Territorial podem ser adicionadas no campo CBO do profissional |  | N·(bloco) |
| 17 | `tipoEndereco` | Código do tipo de endereço do cadastro. | Integer | S | 1 |  | Utilizar valor 3 (logradouro) | `tb_fat_cad_domiciliar.co_dim_tipo_endereco` | S |
| 18 | `stAtivo` | Indica se o cadastro do imóvel está ativo. | Boolean | N |  |  | Só pode ser preenchido se o campo fichaAtualizada = true; Só pode ser true se não houver famílias no cadastro ou todas as famílias tiverem stMudanca = true |  | N·domicilio |

Não gerados na v1 (permanecem nulos na *staging*): `animaisNoDomicilio` (List&lt;Long&gt;), `quantosAnimaisNoDomicilio` (String), `stAnimaisNoDomicilio` (Boolean), `instituicaoPermanencia` (InstituicaoPermanencia), `latitude` (Double), `longitude` (Double).

#### Endereço/local de permanência (`EnderecoLocalPermanencia`)

O banco guarda bairro e microárea; logradouro, número e CEP são gerados pelo Faker só na *staging* e nunca usados em análise.

| # | Campo LEDI | Descrição | Tipo | Obr. | Tam. | Domínio | Regras LEDI | Coluna DW | Uso |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `bairro` | Bairro onde está localizado o domicílio. | String | S | 0–72 |  |  | `tb_fat_cad_domiciliar.no_bairro` | N·domicilio |
| 2 | `cep` | CEP do logradouro do domicílio. | String | S | 8 |  | Apenas números | `tb_fat_cad_domiciliar.nu_cep` | S |
| 3 | `codigoIbgeMunicipio` | Código IBGE do município. | String | S | 7 | Municípios (IBGE, 7 dígitos) |  | `tb_fat_cad_domiciliar.co_dim_municipio_cidadao` | S |
| 5 | `nomeLogradouro` | Nome do logradouro. | String | S | 0–72 |  |  | `tb_fat_cad_domiciliar.no_logradouro` | S |
| 6 | `numero` | Número do domicílio. | String | S | 1–10 |  | Apenas letras e números; Não pode ser preenchido caso stSemNumero = true | `tb_fat_cad_domiciliar.nu_num_logradouro` | S |
| 7 | `numeroDneUf` | Código indexador referente a Unidade Federativa. | String | S |  |  |  |  | S |
| 10 | `tipoLogradouroNumeroDne` | Tipo do logradouro onde está o domicílio. | String | S |  |  | Deve ser informado o código DNE | `tb_fat_cad_domiciliar.co_dim_tipo_logradouro` | S |
| 13 | `microArea` | Microárea na qual o cidadão se encontra. | String | C | 2 |  | Não deve ser preenchido se o campo stForaArea = true. Caso contrário, o preenchimento é obrigatório | `tb_fat_cad_domiciliar.nu_micro_area`<br>`tb_fat_cad_dom_familia.nu_micro_area` | N·microarea |
| 14 | `stForaArea` | Marcador que indica que o cidadão está fora da área. | Boolean | N |  |  |  |  | N·domicilio |

Não gerados na v1 (permanecem nulos na *staging*): `complemento` (String), `telefoneContato` (String), `telefoneResidencia` (String), `stSemNumero` (Boolean), `pontoReferencia` (String).

#### Condições de moradia (`CondicaoMoradia`)

| # | Campo LEDI | Descrição | Tipo | Obr. | Tam. | Domínio | Regras LEDI | Coluna DW | Uso |
|---|---|---|---|---|---|---|---|---|---|
| 5 | `localizacao` | Código da localização do domicílio. | Long | S |  | [LocalizacaoDaMoradia](#dom-localizacaodamoradia) |  | `tb_fat_cad_domiciliar.co_dim_tipo_localizacao` | S |
| 9 | `situacaoMoradiaPosseTerra` | Código da situação de moradia ou de posse da terra. | Long | S |  | [SituacaoDeMoradia](#dom-situacaodemoradia) | Não devem ser preenchidos se o campo tipoDeImovel = 07 Abrigo, 08 Instituição de longa permanência para idosos, 09 Unidade prisional, 10 Unidade de medida socioeducativa ou 11 Delegacia | `tb_fat_cad_domiciliar.co_dim_tipo_situacao_moradia` | S |
| 12 | `tipoDomicilio` | Código do tipo de domicílio. | Long | N |  | [TipoDeDomicilio](#dom-tipodedomicilio) | Não deve ser preenchido se o campo tipoDeImovel = 07 Abrigo, 08 Instituição de longa permanência para idosos, 09 Unidade prisional, 10 Unidade de medida socioeducativa, 11 Delegacia ou 13 CASAI | `tb_fat_cad_domiciliar.co_dim_tipo_domicilio` | S |

Não gerados na v1 (permanecem nulos na *staging*): `abastecimentoAgua` (Long), `areaProducaoRural` (Long), `destinoLixo` (Long), `formaEscoamentoBanheiro` (Long), `materialPredominanteParedesExtDomicilio` (Long), `nuComodos` (String), `nuMoradores` (String), `stDisponibilidadeEnergiaEletrica` (Boolean), `tipoAcessoDomicilio` (Long), `aguaConsumoDomicilio` (Long), `tipoOrigemEnergiaEletrica` (Long).

#### Famílias do domicílio (`FamiliaRow`)

| # | Campo LEDI | Descrição | Tipo | Obr. | Tam. | Domínio | Regras LEDI | Coluna DW | Uso |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `dataNascimentoResponsavel` | Data de nascimento, no formato epoch time, do cidadão responsável pela família. | Long | N |  |  | Não pode ser posterior a dataAtendimento e anterior a 130 anos a partir da dataAtendimento | `tb_fat_cad_dom_familia.dt_nascimento` | S |
| 2 | `numeroCnsResponsavel` | CNS do responsável familiar. | String | S | 15 |  | Validado por algoritmo; Não pode ser preenchido se o campo cpfResponsavel for preenchido | `tb_fat_cad_dom_familia.nu_cns_responsavel` | N·familia |
| 3 | `numeroMembrosFamilia` | Quantidade de membros do núcleo familiar. | Integer | N | 0–3 |  | Não pode ser preenchido com o valor "0" (zero) | `tb_fat_cad_dom_familia.qt_membro_familiar` | N·familia |
| 5 | `rendaFamiliar` | Código da renda familiar em salários mínimos. | Long | N |  | [RendaFamiliar](#dom-rendafamiliar) |  | `tb_fat_cad_domiciliar.ds_filtro_tipo_renda_familiar`<br>`tb_fat_cad_dom_familia.co_dim_tipo_renda_familiar` | N·familia |
| 6 | `resideDesde` | Mês e ano que a família começou a residir no domicílio, no formato epoch time. | Long | N |  |  | Não pode ser posterior à data atual | `tb_fat_cad_dom_familia.dt_inicio_residencia` | N·familia |
| 7 | `stMudanca` | Marcador que indica se a familia mudou-se. | Boolean | N |  |  |  | `tb_fat_cad_dom_familia.st_mudou` | N·familia |
| 8 | `cpfResponsavel` | CPF do responsável. | String | N | 11 |  | Somente CPF válido será aceito; Não pode ser preenchido se o campo numeroCnsResponsavel for preenchido | `tb_fat_cad_dom_familia.nu_cpf_responsavel` | N·familia |

Não gerados na v1 (permanecem nulos na *staging*): `numeroProntuario` (String).

#### Instituição de permanência (`InstituicaoPermanencia`)

Não gerados na v1 (permanecem nulos na *staging*): `nomeInstituicaoPermanencia` (String), `stOutrosProfissionaisVinculados` (Boolean), `nomeResponsavelTecnico` (String), `cnsResponsavelTecnico` (String), `cargoInstituicao` (String), `telefoneResponsavelTecnico` (String).


## 5. Ficha de Atendimento Individual (FAI)

Ficha em papel FAI/e-SUS AB v3.2. Modelo LEDI `FichaAtendimentoIndividualMaster`, com até 99 atendimentos (`Child`) por ficha. Fatos no DW: `tb_fat_atendimento_individual` e `tb_fat_atd_ind_problemas`.

Na FAI, CPF e CNS do cidadão são mutuamente exclusivos, como na FCI.

#### Ficha (lote de até 99 atendimentos) (`FichaAtendimentoIndividualMaster`)

| # | Campo LEDI | Descrição | Tipo | Obr. | Tam. | Domínio | Regras LEDI | Coluna DW | Uso |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `headerTransport` | Profissionais que realizaram o atendimento | VariasLotacoesHeader | S |  |  | Somente as CBOs apresentadas na Tabela 3 - CBOs que podem registrar o Modelo de Informação de Atendimento Individual podem ser adicionadas no campo CBO do profissional principal |  | N·(bloco) |
| 2 | `atendimentosIndividuais` | Registro individualizado dos atendimentos. | List&lt;FichaAtendimentoIndividualChild&gt; | S | 1–99 |  |  |  | N·(bloco) |
| 3 | `uuidFicha` | Código UUID para identificar o registro na base de dados nacional. | String | S | 36–44 |  | É recomendado concatenar o CNES na frente do UUID, de modo que os 7 dígitos (CNES) + 1 de hífen somados aos 36 (32 caracteres + 4 hífen) do UUID são a limitação de 44 bytes do campo. Formato canônico | `tb_fat_atendimento_individual.nu_uuid_ficha`<br>`tb_fat_atd_ind_problemas.nu_uuid_ficha` | N·atendimento_individual |
| 4 | `tpCdsOrigem` | Tipo de origem dos dados do registro. | Integer | S | 1 |  | Utilizar valor 3 (sistemas terceiros) |  | S |

#### Atendimento (`FichaAtendimentoIndividualChild`)

| # | Campo LEDI | Descrição | Tipo | Obr. | Tam. | Domínio | Regras LEDI | Coluna DW | Uso |
|---|---|---|---|---|---|---|---|---|---|
| 2 | `cnsCidadao` | CNS do cidadão. | String | N | 15 |  | CNS validado de acordo com o algoritmo de validação; Não pode ser preenchido se o campo cpfCidadao for preenchido | `tb_fat_atendimento_individual.nu_cns`<br>`tb_fat_atd_ind_problemas.nu_cns` | N·atendimento_individual |
| 3 | `dataNascimento` | Data de nascimento do cidadão. | Long | S |  |  | Não pode ser posterior à dataAtendimento e anterior à 130 anos a partir da dataAtendimento | `tb_fat_atendimento_individual.dt_nascimento` | S |
| 4 | `localDeAtendimento` | Código do local onde o atendimento foi realizado. | Long | S |  | [LocalDeAtendimento](#dom-localdeatendimento) | Apenas valores de 1 a 10 | `tb_fat_atendimento_individual.co_dim_local_atendimento` | S |
| 5 | `sexo` | Código do sexo do cidadão. | Long | S |  | [Sexo](#dom-sexo) |  | `tb_fat_atendimento_individual.co_dim_sexo` | S |
| 6 | `turno` | Código do turno em que o atendimento foi realizado. | Long | S |  | [Turno](#dom-turno) |  | `tb_fat_atendimento_individual.co_dim_turno` | S |
| 7 | `tipoAtendimento` | Código do tipo de atendimento realizado. | Long | S |  | [TipoDeAtendimento](#dom-tipodeatendimento) | Apenas as opções 1, 2, 4, 5 ou 6 são aceitas | `tb_fat_atendimento_individual.co_dim_tipo_atendimento` | N·atendimento_individual |
| 17 | `condutas` | Código das condutas adotadas no atendimento. | List&lt;Long&gt; | S | 1–12 | [CondutaEncaminhamento](#dom-condutaencaminhamento) | Não deve conter duas condutas iguais | `tb_fat_atendimento_individual.st_conduta_*` (7 colunas) | S |
| 22 | `dataHoraInicialAtendimento` | Data e hora do início do atendimento. | Long | S |  |  | Não pode ser anterior à dataAtendimento; Não pode ser posterior à dataHoraFinalAtendimento e à data atual | `tb_fat_atendimento_individual.dt_inicial_atendimento` | N·atendimento_individual |
| 23 | `dataHoraFinalAtendimento` | Data e hora do fim do atendimento. | Long | S |  |  | Não pode ser anterior à dataHoraInicialAtendimento; Não pode ser posterior à data atual | `tb_fat_atendimento_individual.dt_final_atendimento` | S |
| 24 | `cpfCidadao` | CPF do cidadão. | String | N | 11 |  | Somente CPF válido será aceito; Não pode ser preenchido se o campo cnsCidadao for preenchido | `tb_fat_atendimento_individual.nu_cpf_cidadao`<br>`tb_fat_atd_ind_problemas.nu_cpf_cidadao` | N·atendimento_individual |
| 28 | `problemasCondicoes` | Situações de saúde avaliadas no atendimento. | problemacondicao | S | 1+ |  |  |  | N·atendimento_individual |
| 33 | `stCidadaoNaoPossuiCpf` | Marcador que indica que o CPF do cidadão não existe ou não está disponível no momento do cadastro. | Boolean | S |  |  |  | `tb_fat_atendimento_individual.st_nao_possui_cpf` | S |
| 34 | `justificativaNaoPossuiCpf` | Justificativa para o cidadão não possuir ou não informar CPF. | Long | C |  | [JustificativaNaoPossuiCpf](#dom-justificativanaopossuicpf) | É permitido o envio apenas de justificativas que constam na listagem de referência; Não pode ser preenchido se o campo stCidadaoNaoPossuiCpf = false; É obrigatório se o campo stCidadaoNaoPossuiCpf = true | `tb_fat_atendimento_individual.co_dim_just_nao_possui_cpf` | S |

Não gerados na v1 (permanecem nulos na *staging*): `numeroProntuario` (String), `medicoes` (Medicoes), `aleitamentoMaterno` (Long), `dumDaGestante` (Long), `idadeGestacional` (Integer), `atencaoDomiciliarModalidade` (Long), `exame` (List&lt;exame&gt;), `vacinaEmDia` (Boolean), `ficouEmObservacao` (Boolean), `emultis` (List&lt;Long&gt;), `stGravidezPlanejada` (Boolean), `nuGestasPrevias` (Integer), `nuPartos` (Integer), `racionalidadeSaude` (Long), `Medicamentos` (List&lt;medicamentos&gt;), `Encaminhamentos` (List&lt;encaminhamentos&gt;), `resultadosExames` (List&lt;resultadosExames&gt;), `tipoParticipacaoCidadao` (Long), `tipoParticipacaoProfissionalConvidado` (Long), `ivcf` (Ivcf), `solicitacoesOci` (List&lt;solicitacoesOci&gt;).

#### Problema/condição avaliada (`ProblemaCondicao`)

| # | Campo LEDI | Descrição | Tipo | Obr. | Tam. | Domínio | Regras LEDI | Coluna DW | Uso |
|---|---|---|---|---|---|---|---|---|---|
| 4 | `ciap` | Código da CIAP registrada no atendimento. | String | C |  | CIAP2 ou [Código AB](#dom-listaciap) | Não deve repetir a mesma CIAP2 ou Código AB; Pode ser preenchido com Código AB da ListaCiapCondicaoAvaliada; Não pode conter nenhum dos itens listados no grupo Procedimentos da Tabela CIAP2; Não é permitida CIAP2 relacionada ao pré-natal com uma CID de desfecho de gestação (exemplo: CIAP2 "GRAVIDEZ DE ALTO RISCO - W84" relacionada a CID10 "PARTO ÚNICO ESPONTÂNEO - O80"); Não é permitida CIAP2 relacionada ao pré-natal caso a idade seja inferior a 9 anos; A CIAP2 "GRAVIDEZ - W78" só pode ser vinculada a uma CID10 da familia Z34; O código deve ser inserido em caracteres maiúsculos, sem espaços; Se torna obrigatório caso o campo cid10 não seja preenchido | `tb_fat_atendimento_individual.ds_filtro_ciaps`<br>`tb_fat_atd_ind_problemas.co_dim_ciap` | N·atendimento_individual |
| 5 | `cid10` | Código da CID10 registrada no atendimento. | String | C |  | CID-10 | Não deve repetir a mesma CID10; Não é permitida mais que uma CID10 da familia Z34 no mesmo registro; Se torna obrigatório caso o campo ciap não seja preenchido | `tb_fat_atendimento_individual.ds_filtro_cids`<br>`tb_fat_atd_ind_problemas.co_dim_cid` | N·atendimento_individual |
| 9 | `isAvaliado` | Indicador se o problema ou condição foi avaliado durante o atendimento. | Boolean | S |  |  |  | `tb_fat_atd_ind_problemas.st_avaliado` | S |

Não gerados na v1 (permanecem nulos na *staging*): `uuidProblema` (String), `uuidEvolucaoProblema` (String), `coSequencialEvolucao` (Long), `situacao` (String), `dataInicioProblema` (Long), `dataFimProblema` (Long).

#### Medições (`medicoes`)

Não gerados na v1 (permanecem nulos na *staging*): `circunferenciaAbdominal` (Double), `perimetroPanturrilha` (Double), `pressaoArterialSistolica` (Integer), `pressaoArterialDiastolica` (Integer), `frequenciaRespiratoria` (Integer), `frequenciaCardiaca` (Integer), `temperatura` (Double), `saturacaoO2` (Integer), `glicemiaCapilar` (Integer), `tipoGlicemiaCapilar` (Long), `peso` (Double), `altura` (Double), `perimetroCefalico` (Double).

#### Exames solicitados/avaliados (`Exame`)

Não gerados na v1 (permanecem nulos na *staging*): `codigoExame` (String), `solicitadoAvaliado` (List&lt;String&gt;).

#### Medicamentos (`Medicamentos`)

Não gerados na v1 (permanecem nulos na *staging*): `codigoCatmat` (String), `viaAdministracao` (Integer), `dose` (String), `doseUnica` (Boolean), `usoContinuo` (Boolean), `doseFrequenciaTipo` (Integer), `doseFrequencia` (Integer), `doseFrequenciaQuantidade` (Integer), `doseFrequenciaUnidadeMedida` (Integer), `dtInicioTratamento` (Long), `duracaoTratamento` (Integer), `duracaoTratamentoMedida` (Integer), `quantidadeReceitada` (Integer), `qtDoseManha` (String), `qtDoseTarde` (String), `qtDoseNoite` (String).

#### Encaminhamentos (`Encaminhamentos`)

Não gerados na v1 (permanecem nulos na *staging*): `especialidade` (Integer), `hipoteseDiagnosticoCID10` (String), `hipoteseDiagnosticoCIAP2` (String), `classificacaoRisco` (Integer).

#### Resultados de exames (`ResultadosExames`)

Não gerados na v1 (permanecem nulos na *staging*): `exame` (String), `dataSolicitacao` (Long), `dataRealizacao` (Long), `dataResultado` (Long), `resultadoExame` (List&lt;resultadoExame&gt;).

#### Resultado de exame (`resultadoExame`)

Não gerados na v1 (permanecem nulos na *staging*): `tipoResultado` (Integer), `valorResultado` (String).

#### IVCF-20 (`IVCF`)

Não gerados na v1 (permanecem nulos na *staging*): `resultado` (Integer), `hasSgIdade` (Boolean), `hasSgPercepcaoSaude` (Boolean), `hasSgAvdInstrumental` (Boolean), `hasSgAvdBasica` (Boolean), `hasSgCognicao` (Boolean), `hasSgHumor` (Boolean), `hasSgAlcancePreensaoPinca` (Boolean), `hasSgCapAerobicaMuscular` (Boolean), `hasSgMarcha` (Boolean), `hasSgContinencia` (Boolean), `hasSgVisao` (Boolean), `hasSgAudicao` (Boolean), `hasSgComorbidade` (Boolean), `dataResultado` (Long).

#### Solicitação de Oferta de Cuidado Integrado (`SolicitacoesOci`)

Não gerados na v1 (permanecem nulos na *staging*): `codigoSigtap` (String).

#### Profissional finalizador da observação (`profissionalFinalizadorObservacao`)

Não gerados na v1 (permanecem nulos na *staging*): `profissionalCNS` (String), `cboCodigo_2002` (String), `cnes` (String), `ine` (String).


## 6. Domínios (listas de valores)

Códigos copiados do Dicionário de dados do LEDI 8.7.0. Atenção: os códigos **não são sequenciais nem seguem a ordem da ficha**. Raça/cor, por exemplo, usa `4` para Parda e `3` para Amarela; sexo usa `0` para Masculino. O gerador e as tabelas de domínio devem carregar estes códigos, nunca a posição da opção na ficha.

<a id="dom-condutaencaminhamento"></a>
**CondutaEncaminhamento** — usado por `condutas`  
`1` Retorno para consulta agendada · `2` Retorno para cuidado continuado / programado · `12` Agendamento para grupos · `14` Agendamento para eMulti · `9` Alta do episódio · `11` Encaminhamento interno no dia (#ENCAMINHAMENTO) · `4` Encaminhamento para serviço especializado · `5` Encaminhamento para CAPS · `6` Encaminhamento para internação hospitalar · `7` Encaminhamento para urgência · `8` Encaminhamento para serviço de atenção domiciliar · `10` Encaminhamento intersetorial

<a id="dom-cursomaiselevado"></a>
**CursoMaisElevado** — usado por `grauInstrucaoCidadao`  
`51` Creche · `52` Pré-escola (exceto CA) · `53` Classe de alfabetização - CA · `54` Ensino fundamental 1ª a 4ª séries · `55` Ensino fundamental 5ª a 8ª séries · `56` Ensino fundamental completo · `61` Ensino fundamental especial · `58` Ensino fundamental EJA - séries iniciais (supletivo 1ª a 4ª) · `59` Ensino fundamental EJA - séries finais (supletivo 5ª a 8ª) · `60` Ensino médio, médio 2º ciclo (científico, técnico e etc) · `57` Ensino médio especial · `62` Ensino médio EJA (supletivo) · `63` Superior, aperfeiçoamento, especialização, mestrado, doutorado · `64` Alfabetização para adultos (Mobral, etc) · `65` Nenhum

<a id="dom-deficienciacidadao"></a>
**DeficienciaCidadao** — usado por `deficienciasCidadao`  
`12` Auditiva · `13` Visual · `14` Intelectual / Cognitiva · `15` Física · `232` TEA · `16` Outra

<a id="dom-etnia"></a>
**etnia** — usado por `etnia`  
406 valores; lista completa em [https://integracao.esusaps.bridge.ufsc.tech/ledi/documentacao/referencias/dicionario.html#etnia](https://integracao.esusaps.bridge.ufsc.tech/ledi/documentacao/referencias/dicionario.html#etnia).

<a id="dom-identidadegenerocidadao"></a>
**identidadeGeneroCidadao** — usado por `identidadeGeneroCidadao`  
`149` Homem transgênero · `150` Mulher transgênero · `156` Travesti · `200` Homem cisgênero · `201` Mulher cisgênero · `203` Não-binário · `151` Outro

<a id="dom-justificativanaopossuicpf"></a>
**JustificativaNaoPossuiCpf** — usado por `justificativaNaoPossuiCpf`  
`2` Paciente desacordado, sem documentos · `3` Recém-nascidos · `4` Indígenas sem CPF · `5` Pessoa em situação de rua sem documentos · `6` Recusa cultural ou religiosa · `7` Estrangeiro em trânsito (turista/visitante) · `8` Pessoa indocumentada · `9` Crianças sem documentação emitida · `10` Estrangeiro residente sem CPF · `11` Internação compulsória (saúde mental ou ordem judicial) · `12` População migrante/refugiada em processo de regularização · `13` Situações de calamidade ou desastre

<a id="dom-localdeatendimento"></a>
**LocalDeAtendimento** — usado por `localDeAtendimento`  
`1` UBS · `2` Unidade móvel · `3` Rua · `4` Domicílio · `5` Escola / Creche · `6` Outros · `7` Polo (academia da saúde) · `8` Instituição / Abrigo · `9` Unidade prisional ou congêneres · `10` Unidade socioeducativa · `11` Hospital (Utilizado apenas no Modelo de Informação de Atendimento Domiciliar) · `12` Unidade de pronto atendimento (Utilizado apenas no Modelo de Informação de Atendimento Domiciliar) · `13` CACON / UNACON (Utilizado apenas no Modelo de Informação de Atendimento Domiciliar) · `16` UBSI · `17` UBSI Fluvial · `18` Sede de polo base tipo I · `19` CASAI

<a id="dom-localizacaodamoradia"></a>
**LocalizacaoDaMoradia** — usado por `localizacao`  
`83` Urbana · `84` Rural · `205` Periurbana

<a id="dom-motivosaida"></a>
**MotivoSaida** — usado por `motivoSaidaCidadao`  
`135` Óbito · `136` Mudança de território

<a id="dom-nacionalidade"></a>
**Nacionalidade** — usado por `nacionalidadeCidadao`  
`1` Brasileira · `2` Naturalizado · `3` Estrangeiro

<a id="dom-orientacaosexual"></a>
**OrientacaoSexual** — usado por `orientacaoSexualCidadao`  
`148` Heterossexual · `154` Bissexual · `196` Gay · `197` Lésbica · `198` Assexual · `199` Panssexual · `155` Outro

<a id="dom-povocomunidadetradicional"></a>
**povoComunidadeTradicional** — usado por `coPovoComunidadeTradicional`  
`157` Agroextrativistas - Povos ou Comunidades Tradicionais · `158` Caatingueiros - Povos ou Comunidades Tradicionais · `159` Caiçaras - Povos ou Comunidades Tradicionais · `160` Cerrado - Povos ou Comunidades Tradicionais · `161` Ciganos - Povos ou Comunidades Tradicionais · `162` Comunidades de fundo e fecho de pasto - Povos ou Comunidades Tradicionais · `163` Extrativistas - Povos ou Comunidades Tradicionais · `164` Faxinalenses - Povos ou Comunidades Tradicionais · `165` Geraizeiros - Povos ou Comunidades Tradicionais · `166` Marisqueiros - Povos ou Comunidades Tradicionais · `167` Pantaneiros - Povos ou Comunidades Tradicionais · `168` Pescadores artesanais - Povos ou Comunidades Tradicionais · `169` Pomeranos - Povos ou Comunidades Tradicionais · `170` Povos indígenas - Povos ou Comunidades Tradicionais · `171` Povos quilombolas - Povos ou Comunidades Tradicionais · `172` Quebradeiras de coco babaçu - Povos ou Comunidades Tradicionais · `173` Retireiros - Povos ou Comunidades Tradicionais · `174` Ribeirinhos - Povos ou Comunidades Tradicionais · `175` Seringueiros - Povos ou Comunidades Tradicionais · `176` Povos de terreiro / Matriz africana - Povos ou Comunidades Tradicionais · `177` Vazanteiros - Povos ou Comunidades Tradicionais · `178` Outros - Povos ou Comunidades Tradicionais · `179` Acampada - População Campo, Floresta e Águas · `180` Andirobeiras - População Campo, Floresta e Águas · `182` Assentada - População Campo, Floresta e Águas · `183` Camponeses - População Campo, Floresta e Águas · `184` Castanheiras - População Campo, Floresta e Águas · `185` Catadores de mangaba - População Campo, Floresta e Águas · `186` Isqueiros - População Campo, Floresta e Águas · `187` Jangadeiros - População Campo, Floresta e Águas · `189` Morroquianos - População Campo, Floresta e Águas · `190` Populações atingidas por barragens - População Campo, Floresta e Águas · `193` Trabalhadores rurais assalariados - População Campo, Floresta e Águas · `194` Trabalhadores rurais temporários - População Campo, Floresta e Águas · `195` Varjeiros - População Campo, Floresta e Águas

<a id="dom-racacor"></a>
**RacaCor** — usado por `racaCorCidadao`  
`1` Branca · `2` Preta · `4` Parda · `3` Amarela · `5` Indígena

<a id="dom-relacaoparentesco"></a>
**RelacaoParentesco** — usado por `relacaoParentescoCidadao`  
`137` Cônjuge / Companheiro(a) · `138` Filho(a) · `139` Enteado(a) · `140` Neto(a) / Bisneto(a) · `141` Pai / Mãe · `142` Sogro(a) · `143` Irmão / Irmã · `144` Genro / Nora · `145` Outro parente · `146` Não parente

<a id="dom-rendafamiliar"></a>
**RendaFamiliar** — usado por `rendaFamiliar`  
`1` 1/4 de salário mínimo · `2` Meio salário mínimo · `3` Um salário mínimo · `4` Dois salários mínimos · `7` Três salários mínimos · `5` Quatro salários mínimos · `6` Acima de quatro salários mínimos · `8` Ausência de renda

<a id="dom-sexo"></a>
**Sexo** — usado por `sexo`, `sexoCidadao`  
`0` Masculino · `1` Feminino · `4` Ignorado (Apenas quando não foi informado o sexo do cidadão.) · `5` Indeterminado

<a id="dom-situacaodemoradia"></a>
**SituacaoDeMoradia** — usado por `situacaoMoradiaPosseTerra`  
`75` Próprio · `76` Financiado · `77` Alugado · `78` Arrendado · `79` Cedido · `80` Ocupação · `81` Situação de rua · `204` Temporária · `82` Outra

<a id="dom-situacaomercadotrabalho"></a>
**SituacaoMercadoTrabalho** — usado por `situacaoMercadoTrabalhoCidadao`  
`66` Empregador · `67` Assalariado com carteira de trabalho · `68` Assalariado sem carteira de trabalho · `69` Autônomo com previdência social · `70` Autônomo sem previdência social · `71` Aposentado / Pensionista · `72` Desempregado · `73` Não trabalha · `147` Servidor público / Militar · `74` Outro

<a id="dom-tipodeatendimento"></a>
**TipoDeAtendimento** — usado por `tipoAtendimento`  
`1` Consulta agendada programada / Cuidado continuado · `2` Consulta agendada · `4` Escuta inicial / Orientação · `5` Consulta no dia · `6` Atendimento de urgência · `7` Atendimento programado (Utilizado apenas no Modelo de Informação de Atendimento Domiciliar) · `8` Atendimento não programado (Utilizado apenas no Modelo de Informação de Atendimento Domiciliar) · `9` Visita domiciliar pós-óbito (Utilizado apenas no Modelo de Informação de Atendimento Domiciliar)

<a id="dom-tipodedomicilio"></a>
**TipoDeDomicilio** — usado por `tipoDomicilio`  
`85` Casa · `86` Apartamento · `87` Cômodo · `206` Maloca · `207` Improvisado · `88` Outro

<a id="dom-tipodeimovel"></a>
**tipoDeImovel** — usado por `tipoDeImovel`  
`1` Domicílio · `2` Comércio · `3` Terreno baldio · `4` Ponto Estratégico (cemitério, borracharia, ferro-velho, depósito de sucata ou materiais de construção, garagem de ônibus ou veículo de grande porte, casa de farinha) · `5` Escola · `6` Creche · `7` Abrigo · `8` Instituição de longa permanência para idosos · `9` Unidade prisional · `10` Unidade de medida sócio educativa · `11` Delegacia · `12` Estabelecimento religioso · `13` CASAI · `99` Outros

<a id="dom-turno"></a>
**Turno** — usado por `turno`  
`1` Manhã · `2` Tarde · `3` Noite

<a id="dom-listaciap"></a>
**ListaCiapCondicaoAvaliada (Códigos AB aceitos no campo `ciap`)**  
`ABP023` Rastreamento de Câncer de mama · `ABP022` Rastreamento de Câncer do colo do útero · `ABP015` Reabilitação · `ABP014` Saúde Mental · `ABP003` Saúde Sexual e Reprodutiva


## 7. Regras condicionais que o gerador e o banco precisam respeitar

Estas regras vêm das linhas das seções 3 a 5 e são as que mais afetam a geração e as restrições `CHECK`.

| # | Regra | Campos | Origem |
|---|---|---|---|
| R1 | Orientação sexual só existe se "Deseja informar?" = Sim e, nesse caso, é obrigatória | `statusDesejaInformarOrientacaoSexual` → `orientacaoSexualCidadao` | LEDI, FCI |
| R2 | Mesma regra para identidade de gênero | `statusDesejaInformarIdentidadeGenero` → `identidadeGeneroCidadao` | LEDI, FCI |
| R3 | Tipos de deficiência (1 a 6) só se "Tem alguma deficiência?" = Sim, e então ao menos um | `statusTemAlgumaDeficiencia` → `deficienciasCidadao` | LEDI, FCI |
| R4 | Etnia só e obrigatoriamente quando raça/cor = Indígena (`5`) | `racaCorCidadao` → `etnia` | LEDI, FCI |
| R5 | Envia-se CPF **ou** CNS, nunca os dois; CNS só quando não há CPF (`stNaoPossuiCpf = true`), com justificativa | `cpfCidadao`, `cnsCidadao`, `stNaoPossuiCpf`, `justificativaNaoPossuiCpf` | LEDI, FCI e FAI |
| R6 | CPF/CNS do responsável familiar só se o cidadão **não** for o responsável; um ou outro | `statusEhResponsavel`, `cpfResponsavelFamiliar`, `cnsResponsavelFamiliar` | LEDI, FCI |
| R7 | Microárea vazia quando o cidadão ou domicílio está fora de área (FA); na FCDT é obrigatória nos demais casos | `stForaArea`, `microarea` / `microArea` | LEDI, FCI e FCDT |
| R8 | Data e número do óbito só com motivo de saída = Óbito (`135`); data obrigatória nesse caso e entre nascimento e data da ficha | `motivoSaidaCidadao`, `dataObito`, `numeroDO` | LEDI, FCI |
| R9 | Termo de recusa assinado: a ficha não leva identificação completa, dados sociodemográficos, condições de saúde nem saída | `statusTermoRecusaCadastroIndividualAtencaoBasica` | LEDI, FCI |
| R10 | Nascimento não posterior à data da ficha nem mais de 130 anos antes dela | `dataNascimentoCidadao`, `dataNascimento` | LEDI, FCI e FAI |
| R11 | "Crianças de 0 a 9 anos, com quem fica?" só para menores de 10 anos. **Não** é a regra do "dado real", que usa 0 a 10 anos | `responsavelPorCrianca` | LEDI, FCI; plano, seção 2.2 |
| R12 | Famílias só em imóvel tipo Domicílio (`1`), sem CNS de responsável repetido e sem termo de recusa | `tipoDeImovel`, `familias` | LEDI, FCDT |
| R13 | Domicílio só pode ser inativado (`stAtivo = false`) numa atualização e quando todas as famílias se mudaram | `stAtivo`, `fichaAtualizada`, `stMudanca` | LEDI, FCDT |
| R14 | Cada problema avaliado tem CIAP2 ou CID-10 (ao menos um). Sem CIAP2 de pré-natal com idade < 9 anos; `W78` só com CID `Z34*` | `ciap`, `cid10` | LEDI, FAI |
| R15 | Tipo de atendimento na FAI só aceita `1`, `2`, `4`, `5` e `6`; local de atendimento só `1` a `10` | `tipoAtendimento`, `localDeAtendimento` | LEDI, FAI |
| R16 | Idade mínima elegível para OS/IG lida da tabela de parâmetros (11 anos; 10 a confirmar), nunca fixada em consulta | parâmetro do projeto | Plano, Tabela 6 e Tabela 9 |

## 8. Planilha da SESAU → campos de origem (regra do "dado real")

A planilha *(JUL–SET) 2025 Monitoramento Indicadores LGBT* tem uma linha por USF e vem do Relatório Consolidado de Cadastro Individual. A tabela abaixo diz de quais campos sai cada coluna, para que o banco sintético reproduza a planilha por USF e por equipe (Etapa 8, Tabela 9 do plano).

**Universo comum a todas as contagens:** a versão vigente da FCI de cada cidadão na data de corte, isto é, a de maior `dataAtendimento` até essa data dentro da cadeia `uuid`/`uuidFichaOriginadora`. Contar todas as versões infla os totais. A idade é calculada **na data de corte**.

| Col. | Cabeçalho da planilha | Campo(s) de origem (LEDI) | Regra no banco | Coluna DW correspondente |
|---|---|---|---|---|
| A | Distrito sanitário | — (não existe no e-SUS) | `equipe → unidade_saude → distrito_sanitario` | — |
| B | Dia/Mês | — | `parametro.data_corte`, única por carga | — |
| C | USF | `headerTransport.cnes` | Nome e código vêm de `unidade_saude` (CNES); não são digitados | `co_dim_unidade_saude` |
| D–G | Endereço, cidade, país, estado | — | Atributos de `unidade_saude` e do município; constantes | — |
| H | Cidadãos Ativos | Versão vigente da FCI com `motivoSaidaCidadao` nulo | Contagem de cidadãos com versão vigente sem saída até a data de corte. Termos de recusa (`statusTermoRecusa… = true`): **a confirmar** se entram | `tb_fat_cad_individual` (`co_dim_tipo_saida_cadastro`, `st_recusa_cadastro`, `st_ficha_inativa`) |
| I | Criança cadastrada | `dataNascimentoCidadao` | Entre os ativos, idade < `parametro.idade_min_elegivel` (11 → 0 a 10 anos) | `dt_nascimento` |
| J | Cidadãos Ativos / Dado real | — | H − I | — |
| K | Orientação sexual? SIM | `statusDesejaInformarOrientacaoSexual = true` | Contagem entre os ativos, **incluindo crianças** | `st_informar_orientacao_sexual` (ver D6) |
| L | Criança cadastrada (em K) | idem + `dataNascimentoCidadao` | K ∩ I | — |
| M | SIM / Dado real | — | K − L | — |
| N | SIM / % | — | M ÷ J, calculado na consulta e nunca armazenado | — |
| O–R | NÃO, Criança, Dado real, % | `statusDesejaInformarOrientacaoSexual = false` | Mesma lógica de K–N | idem |
| S–U | NÃO INFORMADO, Criança, Dado real | `statusDesejaInformarOrientacaoSexual` **nulo** | Mesma lógica. No LEDI 8.7.0 o campo é obrigatório, então o nulo só vem de **cadastros legados** ou incompletos (ver D5) | idem |
| V… | Colunas seguintes (identidade de gênero e outros marcadores) | `statusDesejaInformarIdentidadeGenero` e, possivelmente, `nomeSocial` e outros | Mesmo esquema de K–U. **Em aberto** (Apêndice A, pergunta 3) | `st_informar_identidade_genero` |
| — | Recorte por equipe | `headerTransport.ine` da versão vigente | Mesma regra, agrupando por INE em vez de CNES | `co_dim_equipe` |

Indicadores das outras duas políticas, previstos na Etapa 9 e ainda sem coluna na planilha:

| Indicador | Campos de origem | Observação |
|---|---|---|
| Distribuição de raça/cor registrada × censitária | `racaCorCidadao` (versão vigente), `etnia` | Comparar com o Censo 2022 por bairro/DS; "amarela" anômala é defeito previsto na Etapa 7 |
| Completude e prevalência de deficiência por tipo | `statusTemAlgumaDeficiencia`, `deficienciasCidadao` | Nulo em `statusTemAlgumaDeficiencia` = falha de registro (ver D4) |
| Divergência de raça/cor entre versões | `racaCorCidadao` em versões sucessivas da cadeia `uuidFichaOriginadora` | Só é possível porque o atributo fica na versão do cadastro |

## 9. Correspondência deficiência: Censo 2022 × e-SUS APS (Tabela 7 revisada)

O LEDI 8.7.0 inclui **TEA** (`232`) como tipo de deficiência, e o DW tem a coluna `st_defi_tea`. A ficha em papel v5.2 não traz essa opção. O Censo 2022 levantou o TEA numa pergunta própria ("já foi diagnosticado(a) com autismo por algum profissional de saúde?"), separada das dificuldades funcionais. Por isso a Tabela 7 do plano ganha uma linha.

| Censo 2022 (Grupo de Washington) | Recife, % (2+ anos) | e-SUS APS (`DeficienciaCidadao`) | Observação |
|---|---|---|---|
| Enxergar | 4,9 | `13` Visual | Correspondência direta |
| Ouvir | 1,4 | `12` Auditiva | Correspondência direta |
| Andar ou subir degraus | 3,1 | `15` Física | Agrupar com o item seguinte |
| Pegar pequenos objetos (membros superiores) | 1,6 | `15` Física | Idem |
| Comunicar-se / cuidados pessoais (funções mentais) | 1,6 | `14` Intelectual / Cognitiva | Aproximação; documentar a premissa |
| Diagnóstico de TEA (pergunta separada) | ≈1,4 (21.211 pessoas) | `232` TEA | Novo no LEDI 8.7.0; ausente da ficha v5.2. Sortear de forma independente das dificuldades funcionais |
| — | — | `16` Outra | Sem equivalente; usar pequena proporção residual |

Os percentuais vêm da Figura 8 do plano (SIDRA 10127). O número de TEA em Recife é o divulgado nos resultados preliminares da amostra (IBGE, 2025); o percentual foi calculado sobre a população total (1.488.920), já que a base etária da pergunta não foi confirmada. Como uma pessoa pode ter mais de uma dificuldade, os tipos somam mais que o total de 8,4%. No banco isso vira várias linhas em `cadastro_deficiencia`.

## 10. Problema/condição avaliada na FAI: ficha em papel × LEDI 8.7.0

A ficha em papel v3.2 lista condições como caixas de marcar. O LEDI 8.7.0 aceita no campo `ciap` um código CIAP2 ou um dos cinco **Códigos AB**, e no campo `cid10` um código CID-10. O gerador deve emitir códigos, não rótulos. Cada linha abaixo indica de onde vem o código.

| Item da ficha | Código no LEDI 8.7.0 | Fonte |
|---|---|---|
| Hipertensão arterial | CIAP2 `K86`, `K87`; CID-10 `I10`, `I13*`, `I15*` e outros | Oficial: agrupamento do DW (`tb_fat_consolidado_cidadao_fai`) |
| Diabetes | CIAP2 `T89`, `T90`; CID-10 `E10*`–`E14*`, `O24*` e outros | Oficial: DW |
| Obesidade | CIAP2 `T82`; CID-10 `E66*` | Oficial: DW |
| Tabagismo | CIAP2 `P17`; CID-10 `Z720` | Oficial: DW |
| Rastreamento de risco cardiovascular | CIAP2 `K22`; CID-10 `Z136`, `Z824` | Oficial: DW |
| Saúde sexual e reprodutiva | `ABP003` | Oficial: ListaCiapCondicaoAvaliada |
| Saúde mental | `ABP014` | Oficial: ListaCiapCondicaoAvaliada |
| Reabilitação | `ABP015` | Oficial: ListaCiapCondicaoAvaliada |
| Rastreamento de câncer do colo do útero | `ABP022` | Oficial: ListaCiapCondicaoAvaliada |
| Rastreamento de câncer de mama | `ABP023` | Oficial: ListaCiapCondicaoAvaliada |
| Pré-natal | CIAP2 `W78` (com CID-10 `Z34*`) ou `W84` (alto risco) | Oficial: regras do campo `ciap` no LEDI |
| Asma | CIAP2 `R96` | Sugestão do grupo; validar |
| DPOC | CIAP2 `R95` | Sugestão do grupo; validar |
| Desnutrição | CIAP2 `T91` | Sugestão do grupo; validar |
| Tuberculose | CIAP2 `A70` | Sugestão do grupo; validar |
| Hanseníase | CIAP2 `A78` | Sugestão do grupo; validar |
| Dengue | CIAP2 `A77` | Sugestão do grupo; validar |
| Usuário de álcool | CIAP2 `P15` / `P16` | Sugestão do grupo; validar |
| Usuário de outras drogas | CIAP2 `P19` | Sugestão do grupo; validar |
| Puericultura | CIAP2 `A98` | Sugestão do grupo; validar |
| Puerpério (até 42 dias) | a definir | Sem código confirmado |
| DST | a definir (CIAP2 dos capítulos X/Y) | Sem código confirmado |

As listas CID-10 completas dos agrupamentos oficiais estão no DW, em *Tabela fato com informações consolidadas sobre um cidadão gerada a partir de um atendimento individual*. Atendimentos não são necessários para o alvo principal de ML (Etapa 10); esta tabela serve ao alvo alternativo de utilização e às análises de acesso.

## 11. Atributos do projeto que não existem no e-SUS

O modelo ER (Figura 13) precisa de atributos que nenhuma ficha transmite. Eles são derivados ou sintéticos, e a carga deve deixar isso explícito.

| Atributo | Tabela | Como é obtido | Observação |
|---|---|---|---|
| `id_cidadao` | `cidadao` | Chave sintética | O LEDI não tem identificador de pessoa além de CPF/CNS; no PEC real a pessoa é `tb_fat_cidadao_pec` |
| `dt_digitacao` | `atendimento_individual`, `cadastro_individual` | Sorteado após `dataAtendimento`, com atraso por equipe | **Não existe no LEDI 8.7.0 nem no DW.** Só aparece no cabeçalho em papel ("Digitado por / Data"). No dado real, a fonte precisa ser pactuada (Apêndice A, pergunta 7) |
| `competencia` | todas as tabelas-fato analíticas | Mês ou quadrimestre de `dataAtendimento` | Unidade temporal do painel e do alvo de ML |
| `data_corte`, `idade_min_elegivel` | `parametro` | Definidos por carga | Base da regra do "dado real" |
| `idade_na_data_corte`, faixa etária | visões | `data_corte − dataNascimentoCidadao` | Nunca a idade na data da consulta |
| `id_ds` (Distrito Sanitário) | `distrito_sanitario`, `unidade_saude` | Tabela territorial da Prefeitura, ligada pelo CNES | Não é campo do PEC |
| setor censitário | `domicilio` | Atribuído na geração da população | Liga o domicílio às marginais do Censo; não é campo do PEC |
| `id_acao`, data, tipo | `acao_formativa` | Sintético, com efeito conhecido | Não existe no e-SUS; a Secretaria registra fora do sistema (Apêndice A, pergunta 13) |
| `id_defeito`, tabela, registro, tipo | `controle_defeito` | Gabarito da Etapa 7 | Não participa dos indicadores |
| versão vigente | visão sobre `cadastro_individual` | Maior `dataAtendimento` ≤ data de corte na cadeia `uuidFichaOriginadora` | Equivale a `st_ficha_inativa = 0` no DW (a confirmar) |

## 12. Divergências e pendências

| # | Divergência ou pendência | Efeito | Encaminhamento |
|---|---|---|---|
| D1 | TEA (`232`) existe no LEDI 8.7.0 e no DW (`st_defi_tea`), mas não na FCI em papel v5.2 | A ficha impressa subnotifica TEA em relação ao PEC | Gerar TEA com taxa própria (seção 9); confirmar com a Secretaria se o PEC do Recife já registra |
| D2 | A FCI em papel não tem estado civil, tipo sanguíneo, DNV nem "não possui CPF"/justificativa, que existem no LEDI. `stNaoPossuiCpf` é obrigatório | A *staging* precisa desses campos para a ficha ser válida | `stNaoPossuiCpf` e justificativa gerados como `S`; os demais ficam nulos |
| D3 | A FAI em papel usa caixas de condição; o LEDI 8.7.0 aceita só CIAP2, CID-10 e 5 Códigos AB | Rótulos da ficha não podem ir direto para o banco | Usar a seção 10; validar as sugestões antes da Sprint 3 |
| D4 | "Tem alguma deficiência?" é obrigatória na ficha em papel (`*`), mas **não obrigatória** no LEDI 8.7.0 | Nulo é possível no PEC: é falha de registro, não "Não" | Tabela 3 do plano diz "obrigatória"; ajustar o texto e permitir `NULL` no núcleo |
| D5 | "Deseja informar OS/IG?" é obrigatório no LEDI 8.7.0, mas a planilha tem a categoria "Não informado" | O nulo vem de cadastros anteriores à obrigatoriedade ou feitos sem a pergunta | O gerador cria uma fração de cadastros legados com nulo, calibrada pela coluna S da planilha |
| D6 | No DW, `st_informar_orientacao_sexual` e `st_informar_identidade_genero` são descritos como "optou por **não** informar", enquanto no LEDI `true` = **deseja** informar | Risco de inverter Sim/Não ao ler o DW real | Confirmar a semântica com uma amostra real antes de montar a *staging* a partir do DW |
| D7 | Códigos de domínio não seguem a ordem da ficha (raça/cor Parda = `4`, Amarela = `3`; sexo Masculino = `0`) | Erro silencioso se o gerador usar a posição | Carregar os domínios da seção 6; testar com `CHECK` e FK |
| D8 | Datas no LEDI são epoch em milissegundos; no DW são `DATE`/`TIMESTAMP` ou chaves de `tb_dim_tempo` | Conversão obrigatória na carga | *Staging* em `BIGINT` se imitar o LEDI; converter no núcleo |
| D9 | O LEDI envia CPF **ou** CNS por ficha; a tabela `cidadao` guarda os dois | Duplicidade realista: a mesma pessoa com uma ficha por CPF e outra por CNS | Coerente com o defeito "duplicidade" da Etapa 7 |
| D10 | Sexo no LEDI tem também `4` Ignorado e `5` Indeterminado; a ficha só tem F/M | Valores raros no dado real | Gerar só `0`/`1`; aceitar `4`/`5` no domínio |
| D11 | Se as crianças de 10 anos completos entram na exclusão do "dado real" (idade mínima 10 ou 11) | Muda H−I e todos os percentuais | Parâmetro; Apêndice A, pergunta 1 |
| D12 | Na FCDT, `numeroCnsResponsavel` aparece como obrigatório, mas não pode ser preenchido junto com `cpfResponsavel` | Leitura literal impediria famílias identificadas só por CPF | Tratar como "CPF **ou** CNS do responsável", como no campo da ficha em papel |

## Fontes

- BRASIL. Ministério da Saúde. *Layout e-SUS APS de Dados e Interface (LEDI APS)*, versão 8.7.0. <https://integracao.esusaps.bridge.ufsc.tech/ledi/index.html>. Acesso em 19 out. 2026.
- BRASIL. Ministério da Saúde. *Data Warehouse Relatórios e-SUS APS PEC*. <https://integracao.esusaps.bridge.ufsc.tech/dw/index.html>. Acesso em 19 out. 2026.
- BRASIL. Ministério da Saúde. Fichas CI/e-SUS AB v5.2, CD/e-SUS AB v3.2 e FAI/e-SUS AB v3.2.
- IBGE. *Censo 2022 contou 2,4 milhões de pessoas diagnosticadas com autismo no Brasil*. IBGE Educa. <https://educa.ibge.gov.br/jovens/materias-especiais/22700-censo-2022-contou-2-4-milhoes-de-pessoas-diagnosticadas-com-autismo-no-brasil.html>.
- DIARIO DE PERNAMBUCO. *Pernambuco é o oitavo estado com maior número de pessoas com autismo*, maio 2025 (Recife: 21.211 pessoas). <https://www.diariodepernambuco.com.br/vida-urbana/2025/05/3894175-pernambuco-e-o-oitavo-estado-com-maior-numero-de-pessoas-com-autismo.html>.
- EQUIPE 2 – NEXUS DATA. *Emulação de dados da Atenção Primária à Saúde para as políticas de equidade do Recife*, v3. 2026.

## Histórico de versões

| Versão | Data | Alteração |
|---|---|---|
| 1.0.0 | 2026-10-19 | Primeira versão: FCI, FCDT e FAI do LEDI 8.7.0 com colunas do DW, domínios, regras condicionais, mapeamento da planilha, Tabela 7 com TEA, condições da FAI, atributos do projeto e divergências |
