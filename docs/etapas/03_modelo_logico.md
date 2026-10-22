---
documento: Modelo lógico — Emulação de dados da APS para as políticas de equidade do Recife
projeto: Projeto 3 – Dados (CESAR School, 2026.2) · Equipe 2 – Nexus Data
etapa: Etapa 3 – Modelagem lógica
versao: 1.0.0
data: 2026-10-20
status: rascunho para revisão do grupo
arquivos:
  - modelo_logico_aps_recife.brM3 (brModelo 3.2, camada núcleo)
  - modelo_logico_aps_recife.xml (mesmo diagrama no formato XML do brModelo)
  - modelo_logico_aps_recife.png (imagem exportada pelo próprio brModelo)
base: dicionario_dados.md v1.0.0; modelo_conceitual_aps_recife v1.0.0 e regras_de_negocio.md v1.0.0; Emulacao_Dados_APS_Recife_Projeto3_v3 (Etapa 3, Tabelas 8 e 9)
---

# Modelo lógico — Etapa 3

Este documento cumpre os quatro itens da Etapa 3 do plano de emulação:

1. converter o modelo ER em modelo relacional, com chaves primárias, estrangeiras e tabelas associativas (seções 2 a 4);
2. normalizar até a 3ª forma normal e documentar as desnormalizações da camada analítica (seção 5);
3. definir domínios e restrições: `CHECK`, `NOT NULL`, `UNIQUE` e regras condicionais (seção 6);
4. organizar o banco em três camadas: *staging*, núcleo e analítica (seção 7).

A camada núcleo tem **41 tabelas** (19 de dados e 22 de domínio), **155 colunas**, **43 chaves estrangeiras**, **10 restrições UNIQUE** e **32 restrições CHECK**. A *staging* tem 9 tabelas e a analítica, 5 tabelas e 5 visões.

O modelo foi carregado num PostgreSQL 16 e testado com casos válidos e inválidos antes de ser documentado (seção 6.5). O diagrama do brModelo foi gerado a partir da mesma especificação usada no teste, então diagrama, teste e este texto descrevem o mesmo esquema.

## 1. Como ler

**Arquivos.** No brModelo, use **Arquivo → Abrir** e escolha `modelo_logico_aps_recife.brM3`. Se o Java recusar o binário, abra o `.xml` pela mesma opção. O diagrama mostra só a camada núcleo, que é a que tem chaves estrangeiras. A *staging* e a analítica estão neste documento (seção 7). Cada tabela traz no campo *Dicionário* do brModelo a descrição, a origem e as restrições `CHECK`, que o brModelo não desenha.

**Cores do diagrama.** Azul: território e equipes. Verde: domicílio, família, cidadão e cadastro. Laranja: atendimentos. Roxo: controle da carga. Cinza: domínios.

**Cardinalidade.** Mesma leitura do conceitual (Heuser): o par escrito junto a uma tabela diz quantas linhas **dela** se ligam a **uma** linha da outra. Junto à tabela referenciada aparece `(1,1)` quando a chave estrangeira é obrigatória e `(0,1)` quando aceita nulo.

**Notação textual** (seção 4.1). Cada tabela aparece como `tabela (colunas)`. O asterisco marca a chave primária. As linhas recuadas listam as chaves estrangeiras (`(colunas) → tabela (colunas)`) e as chaves alternativas (`único`).

**Tipos.** Os tipos são os do padrão SQL e existem no MySQL 8 e no PostgreSQL: `SMALLINT`, `INT`, `BIGINT`, `CHAR(n)`, `VARCHAR(n)`, `DATE`, `TIMESTAMP`, `BOOLEAN` e `DECIMAL(p,s)`. As diferenças de sintaxe entre os dois SGBD ficam para a Etapa 4 (seção 6.1).

**Três tipos de regra.** O ponto central desta etapa é decidir **onde** cada regra de negócio é garantida:

| Sigla | O que é | Onde vive | Exemplo |
|---|---|---|---|
| R | Restrição declarativa: chave, `NOT NULL`, `UNIQUE`, `CHECK` ou FK | DDL do núcleo | Orientação sexual só com "Deseja informar" = Sim |
| VC | Validação de carga: regra que envolve mais de uma linha ou tabela e que o SQL padrão não expressa como `CHECK` | Procedimento *staging* → núcleo (Etapa 8) ou gatilho (Etapa 4) | Versão com "Tem deficiência" = Sim precisa de ao menos um tipo |
| RQ | Regra de qualidade: o que o dado **deveria** respeitar, mas o PEC real não impõe | Visão `vw_qualidade_registro`; nunca bloqueia a carga | OS/IG registrada para criança |

O critério de separação é simples: **o núcleo aceita tudo o que o PEC aceita e recusa o que o PEC recusa**. Se uma regra fosse imposta como `CHECK` e o plano mandasse injetar exatamente a sua violação (Etapa 7), o defeito não entraria no banco e o desafio de qualidade sumiria. Por isso raça/cor vazia, OS/IG para criança, duplicidade e divergência entre versões são RQ, e não R.

## 2. Do conceitual ao relacional

Regras de mapeamento aplicadas (Heuser, cap. 5):

| Elemento do conceitual | Regra | Resultado no lógico |
|---|---|---|
| Entidade | Vira tabela; o identificador vira chave primária | 15 entidades → 13 tabelas de dados e 3 de domínio (TIPO_DEFICIENCIA; CODIGO_CLINICO dividida em duas, L3). Entram mais 3 tabelas por normalização (`bairro`, `setor_censitario`, `ficha_atendimento`) |
| Relacionamento 1:N | Chave estrangeira no lado N | contém, abriga, abrange, recebe, registra, possui, localiza, reside em, compõe, é atendido em |
| Relacionamento N:N | Tabela associativa com chave composta | declara → `cadastro_deficiencia`; avalia → `atendimento_problema`; lota → `lotacao` |
| Autorrelacionamento | Chave estrangeira para a própria tabela | atualiza → `cadastro_individual.uuid_originadora` |
| Atributo opcional `(0,1)` | Coluna que aceita nulo | `nome_social`, `orientacao_sexual`, `dt_obito`… |
| Atributo codificado | Coluna com FK para tabela de domínio | 21 tabelas `dom_*` de códigos, mais `dom_cbo_ficha`, carregadas antes das demais |
| Cardinalidade mínima 1 do lado N | Não cabe em FK; vira validação de carga | VC09, VC10, VC12 |

Destino de cada relacionamento do conceitual:

| Relacionamento (conceitual) | Implementação | Observação |
|---|---|---|
| contém | `unidade_saude.id_bairro → bairro`, `bairro.id_ds → distrito_sanitario` | O distrito da unidade passa a vir pelo bairro (L4) |
| abriga | `equipe.cnes → unidade_saude` | — |
| abrange | `microarea.ine → equipe` | Chave alternativa `(ine, codigo_microarea)` |
| lota | Tabela `lotacao (cns_profissional, ine, cbo)` | Virou N:N (L1) |
| recebe | `acao_formativa.ine → equipe` | — |
| responde por | `cadastro_individual (cns_profissional, ine) → lotacao` | Agora obrigatório (L1, L10) |
| registra | Idem, pela mesma FK composta | O profissional só registra na equipe em que está lotado |
| possui | `cadastro_individual.id_cidadao → cidadao` | — |
| atualiza | `cadastro_individual (uuid_originadora, id_cidadao) → cadastro_individual (uuid, id_cidadao)` | Garante "mesmo cidadão" sem gatilho (L6) |
| declara | `cadastro_deficiencia (uuid, codigo_deficiencia)` | PK composta impede tipo repetido e limita a 6 tipos |
| localiza | `domicilio.id_microarea → microarea` | Nula fora de área |
| reside em | `familia.id_domicilio → domicilio` | — |
| compõe | `cidadao.id_familia → familia` | Nula quando não há vínculo familiar |
| realiza | `ficha_atendimento (cns_profissional, ine) → lotacao` | O profissional fica na ficha, não no atendimento (L2) |
| é atendido em | `atendimento_individual.id_cidadao → cidadao` | — |
| avalia | Tabela `atendimento_problema` com `ciap` e `cid10` no mesmo item | Substitui CODIGO_CLINICO (L3) |

## 3. Decisões que alteram o modelo conceitual

Cada decisão tem um motivo de normalização, de fidelidade ao LEDI/DW ou de integridade. As que mudam o diagrama ER ou o texto das regras estão reunidas na seção 9, para o grupo aprovar antes de atualizar a Etapa 2.

**L1 — Lotação N:N.** No conceitual, cada profissional está em uma equipe `(1,1)` e cada versão do cadastro aponta, ao mesmo tempo, o profissional e a equipe. Isso cria a dependência transitiva `uuid → cns_profissional → ine` em `cadastro_individual`, uma violação da 3FN. A saída é a mesma do PEC: a **lotação** (profissional × equipe, com a CBO exercida) vira tabela, e cada ficha aponta uma lotação pela FK composta `(cns_profissional, ine)`. Assim o profissional pode ter mais de uma lotação, o cabeçalho da ficha (`profissionalCNS`, `cboCodigo_2002`, `ine`) fica representado tal como no LEDI, e a regra "o profissional só registra na equipe em que está lotado" vira chave estrangeira. Resolve também a pendência 4 de `regras_de_negocio.md`.

**L2 — Ficha de atendimento separada do atendimento.** Na FAI, uma ficha reúne até 99 atendimentos, e profissional, equipe, data do atendimento e data de digitação estão no cabeçalho da ficha (`VariasLotacoesHeader`). Com tudo numa tabela só, `uuid_ficha → (profissional, equipe, datas)` seria dependência parcial da chave alternativa `(uuid_ficha, nu_atendimento)`, o que viola a 2FN. Por isso entra `ficha_atendimento`, e `atendimento_individual` guarda só o que é de cada atendimento. A coluna `nu_atendimento` vem do DW (`tb_fat_atd_ind_problemas.nu_atendimento`).

**L3 — CIAP2 e CID-10 no mesmo item avaliado.** A entidade CODIGO_CLINICO tinha `codigo` como identificador, mas CIAP2 e CID-10 compartilham códigos: `A01` é "dor generalizada" na CIAP2 e "febre tifoide" na CID-10. Além disso, o LEDI (`ProblemaCondicao`) e o DW (`tb_fat_atd_ind_problemas`, com `co_dim_ciap` e `co_dim_cid` na mesma linha) registram CIAP2 e CID-10 **juntos** em cada item, e a regra "W78 só com CID Z34" depende desse par. Solução: `atendimento_problema (id_atendimento, nu_item, ciap, cid10)`, com FK para dois domínios, `dom_ciap` (CIAP2 e os cinco Códigos AB) e `dom_cid10`. O teste confirmou que `A01` como CIAP e `A01` como CID entram no mesmo atendimento sem conflito.

**L4 — Bairro e setor censitário viram tabelas.** O plano liga setor censitário → bairro → Distrito Sanitário (Tabela 5). Guardados como texto em `domicilio` e `unidade_saude`, bairro e distrito ficariam determinados pelo setor (dependência transitiva) e repetidos milhares de vezes. Entram `setor_censitario (cd_setor, id_bairro)` e `bairro (id_bairro, nome_bairro, id_ds)`. O domicílio guarda só o setor; a unidade guarda o bairro; o distrito vem pela junção. A premissa de que cada setor está contido num único bairro, e de que a unidade pertence ao distrito do seu bairro, é conferida na Etapa 5 (pendências P4 e P5).

**L5 — Microárea do cadastro por FK composta.** A RN11 pedia gatilho para garantir que a microárea da versão existe na equipe. Com a chave alternativa `UNIQUE (ine, codigo_microarea)` em `microarea`, a FK `(ine, microarea) → microarea (ine, codigo_microarea)` resolve sem gatilho. Quando `microarea` é nula (fora de área), a FK não é verificada, que é o comportamento desejado.

**L6 — Cadeia de versões do mesmo cidadão por FK composta.** Pelo mesmo mecanismo, `UNIQUE (uuid, id_cidadao)` e a FK `(uuid_originadora, id_cidadao) → cadastro_individual (uuid, id_cidadao)` garantem que uma atualização só aponta versão do mesmo cidadão. A RN08 também deixa de depender de gatilho.

**L7 — A família não guarda CPF/CNS do responsável.** Esses identificadores já estão em `cidadao`; repeti-los em `familia` criaria redundância e anomalia de atualização. O responsável é o membro cuja versão vigente tem `responsavel_familiar = true`. Os campos do LEDI (`numeroCnsResponsavel`, `cpfResponsavel`) ficam na *staging* e são usados na carga para localizar o cidadão.

**L8 — Correção da RN16 (recusa).** No LEDI, raça/cor, etnia e nome social pertencem ao bloco de **identificação**, que é opcional, mas não proibido, quando há termo de recusa. O que o LEDI proíbe é o bloco **sociodemográfico** (OS, IG, deficiência, escolaridade, trabalho) e a saída. A restrição `ck_ci_recusa` segue o LEDI; a RN16 precisa ser ajustada no texto.

**L9 — Equipe obrigatória no núcleo.** O conceitual deixou "responde por" como `(0,1)` porque `ine` é opcional no LEDI. No núcleo a equipe passa a ser obrigatória, porque sem ela a versão não teria unidade (o CNES vem pela equipe) nem lotação. O gerador sempre emite equipe. Se o dado real trouxer fichas sem INE em volume relevante, a lotação ganha a unidade como coluna própria (pendência P3); até lá, essas linhas ficam rejeitadas na *staging* com motivo registrado.

**L10 — Colunas novas.** Nenhuma muda o significado do conceitual:

| Tabela | Coluna | Motivo |
|---|---|---|
| `lotacao` | `cbo` | Vem de PROFISSIONAL: no LEDI a CBO é da lotação, não da pessoa |
| `atendimento_individual` | `nu_atendimento` | Ordem do atendimento na ficha (DW) |
| `atendimento_problema` | `nu_item` | Ordem do item na lista `problemasCondicoes` |
| `parametro` | `recusa_conta_ativo`, `meses_desatualizado`, `dt_geracao` | Tornam parâmetro a pendência da RN10 e o limite da RQ06, em vez de fixá-los em visão (RN26) |
| `controle_defeito` | `campo`, `id_registro_par`, `valor_original` | Sem elas o gabarito não serve de rótulo: a duplicidade precisa do par, e o defeito de raça/cor precisa do valor verdadeiro |
| `dom_ciap` | `tipo`, `pre_natal`, `procedimento` | Sustentam as validações da RN21 (VC07) |

## 4. Esquema relacional da camada núcleo

### 4.1 Notação textual

```
distrito_sanitario (id_ds*, nome_ds)
    único (nome_ds)

bairro (id_bairro*, nome_bairro, id_ds)
    (id_ds) → distrito_sanitario (id_ds)
    único (nome_bairro)

setor_censitario (cd_setor*, id_bairro)
    (id_bairro) → bairro (id_bairro)

unidade_saude (cnes*, nome_unidade, tipo_unidade, id_bairro)
    (tipo_unidade) → dom_tipo_unidade (codigo)
    (id_bairro) → bairro (id_bairro)

equipe (ine*, nome_equipe, tipo_equipe, cnes)
    (tipo_equipe) → dom_tipo_equipe (codigo)
    (cnes) → unidade_saude (cnes)

microarea (id_microarea*, ine, codigo_microarea)
    (ine) → equipe (ine)
    único (ine, codigo_microarea)

profissional (cns_profissional*, nome_profissional)

lotacao (cns_profissional*, ine*, cbo)
    (cns_profissional) → profissional (cns_profissional)
    (ine) → equipe (ine)
    (cbo) → dom_cbo (codigo)

acao_formativa (id_acao*, ine, dt_acao, tipo_acao, tema)
    (ine) → equipe (ine)
    (tipo_acao) → dom_tipo_acao (codigo)

domicilio (id_domicilio*, uuid_ficha, tipo_imovel, cd_setor, id_microarea, fora_area, ativo)
    (tipo_imovel) → dom_tipo_imovel (codigo)
    (cd_setor) → setor_censitario (cd_setor)
    (id_microarea) → microarea (id_microarea)
    único (uuid_ficha)

familia (id_familia*, id_domicilio, renda_familiar, num_membros, reside_desde, mudou_se)
    (id_domicilio) → domicilio (id_domicilio)
    (renda_familiar) → dom_renda_familiar (codigo)

cidadao (id_cidadao*, cpf, cns, nome, dt_nascimento, sexo, id_familia)
    (sexo) → dom_sexo (codigo)
    (id_familia) → familia (id_familia)
    único (cpf)
    único (cns)

cadastro_individual (uuid*, id_cidadao, uuid_originadora, cns_profissional, ine, dt_cadastro, dt_digitacao, ficha_atualizada, recusa_cadastro, responsavel_familiar, microarea, fora_area, raca_cor, etnia, nome_social, deseja_informar_os, orientacao_sexual, deseja_informar_ig, identidade_genero, tem_deficiencia, escolaridade, situacao_trabalho, motivo_saida, dt_obito)
    (id_cidadao) → cidadao (id_cidadao)
    (raca_cor) → dom_raca_cor (codigo)
    (etnia) → dom_etnia (codigo)
    (orientacao_sexual) → dom_orientacao_sexual (codigo)
    (identidade_genero) → dom_identidade_genero (codigo)
    (escolaridade) → dom_escolaridade (codigo)
    (situacao_trabalho) → dom_situacao_trabalho (codigo)
    (motivo_saida) → dom_motivo_saida (codigo)
    (uuid_originadora, id_cidadao) → cadastro_individual (uuid, id_cidadao)
    (cns_profissional, ine) → lotacao (cns_profissional, ine)
    (ine, microarea) → microarea (ine, codigo_microarea)
    único (uuid, id_cidadao)

cadastro_deficiencia (uuid*, codigo_deficiencia*)
    (uuid) → cadastro_individual (uuid)
    (codigo_deficiencia) → dom_tipo_deficiencia (codigo)

ficha_atendimento (uuid_ficha*, cns_profissional, ine, dt_atendimento, dt_digitacao)
    (cns_profissional, ine) → lotacao (cns_profissional, ine)

atendimento_individual (id_atendimento*, uuid_ficha, nu_atendimento, id_cidadao, dt_hora_inicio, tipo_atendimento, local_atendimento, turno)
    (uuid_ficha) → ficha_atendimento (uuid_ficha)
    (id_cidadao) → cidadao (id_cidadao)
    (tipo_atendimento) → dom_tipo_atendimento (codigo)
    (local_atendimento) → dom_local_atendimento (codigo)
    (turno) → dom_turno (codigo)
    único (uuid_ficha, nu_atendimento)

atendimento_problema (id_atendimento*, nu_item*, ciap, cid10)
    (id_atendimento) → atendimento_individual (id_atendimento)
    (ciap) → dom_ciap (codigo)
    (cid10) → dom_cid10 (codigo)
    único (id_atendimento, ciap)
    único (id_atendimento, cid10)

parametro (id_carga*, data_corte, idade_min_elegivel, recusa_conta_ativo, meses_desatualizado, semente, fator_escala, versao_gerador, dt_geracao)

controle_defeito (id_defeito*, tabela, id_registro, tipo_defeito, etapa, campo, id_registro_par, valor_original)
    (tipo_defeito) → dom_tipo_defeito (codigo)
```

As 22 tabelas de domínio seguem o mesmo padrão, `dom_x (codigo*, descricao)`, e estão na seção 4.3.

### 4.2 Tabelas de dados

#### `distrito_sanitario`

Distritos Sanitários I a VIII. Origem: Prefeitura do Recife.

| Coluna | Tipo | Nulo | Chave | Referência | Origem / observação |
|---|---|---|---|---|---|
| `id_ds` | SMALLINT | não | PK |  | DISTRITO_SANITARIO.id_ds |
| `nome_ds` | VARCHAR(10) | não | UQ |  | DISTRITO_SANITARIO.nome_ds — DS I a DS VIII |

#### `bairro`

Bairros oficiais do Recife e o distrito a que pertencem. Origem: Prefeitura do Recife (malhas territoriais) — tabela nova, 3FN.

| Coluna | Tipo | Nulo | Chave | Referência | Origem / observação |
|---|---|---|---|---|---|
| `id_bairro` | SMALLINT | não | PK |  | Código do bairro na malha da Prefeitura |
| `nome_bairro` | VARCHAR(72) | não | UQ |  | UNIDADE_SAUDE.bairro, DOMICILIO.bairro |
| `id_ds` | SMALLINT | não | FK | distrito_sanitario.id_ds |  |

#### `setor_censitario`

Setores censitários do Censo 2022 no Recife. Origem: IBGE, malha de setores 2022 — tabela nova, 3FN.

| Coluna | Tipo | Nulo | Chave | Referência | Origem / observação |
|---|---|---|---|---|---|
| `cd_setor` | CHAR(15) | não | PK |  | DOMICILIO.setor_censitario |
| `id_bairro` | SMALLINT | não | FK | bairro.id_bairro |  |

#### `unidade_saude`

Estabelecimentos do CNES (USF, eCR, CAI…). Origem: CNES.

| Coluna | Tipo | Nulo | Chave | Referência | Origem / observação |
|---|---|---|---|---|---|
| `cnes` | CHAR(7) | não | PK |  | UNIDADE_SAUDE.cnes |
| `nome_unidade` | VARCHAR(100) | não |  |  | UNIDADE_SAUDE.nome_unidade |
| `tipo_unidade` | SMALLINT | não | FK | dom_tipo_unidade.codigo | UNIDADE_SAUDE.tipo_unidade |
| `id_bairro` | SMALLINT | não | FK | bairro.id_bairro | UNIDADE_SAUDE.bairro — O distrito vem pelo bairro |

#### `equipe`

Equipes identificadas pelo INE. Origem: CNES.

| Coluna | Tipo | Nulo | Chave | Referência | Origem / observação |
|---|---|---|---|---|---|
| `ine` | CHAR(10) | não | PK |  | EQUIPE.ine |
| `nome_equipe` | VARCHAR(60) | não |  |  | EQUIPE.nome_equipe |
| `tipo_equipe` | SMALLINT | não | FK | dom_tipo_equipe.codigo | EQUIPE.tipo_equipe |
| `cnes` | CHAR(7) | não | FK | unidade_saude.cnes | abriga (1,1) |

#### `microarea`

Microáreas de cada equipe. Origem: FCI/FCDT.

| Coluna | Tipo | Nulo | Chave | Referência | Origem / observação |
|---|---|---|---|---|---|
| `id_microarea` | INT | não | PK |  | MICROAREA.id_microarea |
| `ine` | CHAR(10) | não | FK | equipe.ine | abrange (1,1) |
| `codigo_microarea` | CHAR(2) | não |  |  | MICROAREA.codigo_microarea |

#### `profissional`

Profissional fictício. Origem: headerTransport.profissionalCNS.

| Coluna | Tipo | Nulo | Chave | Referência | Origem / observação |
|---|---|---|---|---|---|
| `cns_profissional` | CHAR(15) | não | PK |  | PROFISSIONAL.cns_profissional |
| `nome_profissional` | VARCHAR(70) | não |  |  | PROFISSIONAL.nome_profissional — Gerado pelo Faker |

#### `lotacao`

Lotação do profissional numa equipe, com a CBO exercida (relacionamento lota, agora N:N). Origem: headerTransport (profissionalCNS, cboCodigo_2002, cnes, ine).

| Coluna | Tipo | Nulo | Chave | Referência | Origem / observação |
|---|---|---|---|---|---|
| `cns_profissional` | CHAR(15) | não | PK FK | profissional.cns_profissional | lota |
| `ine` | CHAR(10) | não | PK FK | equipe.ine | lota |
| `cbo` | CHAR(6) | não | FK | dom_cbo.codigo | PROFISSIONAL.cbo → headerTransport.cboCodigo_2002 |

#### `acao_formativa`

Oficina ou material recebido por uma equipe. Origem: Projeto.

| Coluna | Tipo | Nulo | Chave | Referência | Origem / observação |
|---|---|---|---|---|---|
| `id_acao` | INT | não | PK |  | ACAO_FORMATIVA.id_acao |
| `ine` | CHAR(10) | não | FK | equipe.ine | recebe (1,1) |
| `dt_acao` | DATE | não |  |  | ACAO_FORMATIVA.dt_acao |
| `tipo_acao` | SMALLINT | não | FK | dom_tipo_acao.codigo | ACAO_FORMATIVA.tipo_acao |
| `tema` | VARCHAR(100) | sim |  |  | ACAO_FORMATIVA.tema |

#### `domicilio`

Imóvel cadastrado na FCDT (estado mais recente). Origem: FCDT.

| Coluna | Tipo | Nulo | Chave | Referência | Origem / observação |
|---|---|---|---|---|---|
| `id_domicilio` | INT | não | PK |  | DOMICILIO.id_domicilio |
| `uuid_ficha` | VARCHAR(44) | não | UQ |  | DOMICILIO.uuid_ficha |
| `tipo_imovel` | SMALLINT | não | FK | dom_tipo_imovel.codigo | DOMICILIO.tipo_imovel |
| `cd_setor` | CHAR(15) | não | FK | setor_censitario.cd_setor | DOMICILIO.setor_censitario — Bairro e distrito vêm pelo setor |
| `id_microarea` | INT | sim | FK | microarea.id_microarea | localiza (0,1) |
| `fora_area` | BOOLEAN | não |  |  | DOMICILIO.fora_area; padrão FALSE |
| `ativo` | BOOLEAN | não |  |  | DOMICILIO.ativo; padrão TRUE |

#### `familia`

Família de um domicílio. Origem: FCDT · FamiliaRow.

| Coluna | Tipo | Nulo | Chave | Referência | Origem / observação |
|---|---|---|---|---|---|
| `id_familia` | INT | não | PK |  | FAMILIA.id_familia |
| `id_domicilio` | INT | não | FK | domicilio.id_domicilio | reside em (1,1) |
| `renda_familiar` | SMALLINT | sim | FK | dom_renda_familiar.codigo | FAMILIA.renda_familiar |
| `num_membros` | SMALLINT | sim |  |  | FAMILIA.num_membros |
| `reside_desde` | DATE | sim |  |  | FAMILIA.reside_desde |
| `mudou_se` | BOOLEAN | não |  |  | FAMILIA.mudou_se; padrão FALSE |

#### `cidadao`

Pessoa sintética: só atributos estáveis. Origem: FCI · IdentificacaoUsuarioCidadao.

| Coluna | Tipo | Nulo | Chave | Referência | Origem / observação |
|---|---|---|---|---|---|
| `id_cidadao` | BIGINT | não | PK |  | CIDADAO.id_cidadao |
| `cpf` | CHAR(11) | sim | UQ |  | CIDADAO.cpf |
| `cns` | CHAR(15) | sim | UQ |  | CIDADAO.cns |
| `nome` | VARCHAR(70) | não |  |  | CIDADAO.nome — Sintético; nunca entra em análise |
| `dt_nascimento` | DATE | não |  |  | CIDADAO.dt_nascimento |
| `sexo` | SMALLINT | não | FK | dom_sexo.codigo | CIDADAO.sexo |
| `id_familia` | INT | sim | FK | familia.id_familia | compõe (0,1) |

#### `cadastro_individual`

Uma versão da FCI; guarda os atributos autodeclarados. Origem: FCI · CadastroIndividual.

| Coluna | Tipo | Nulo | Chave | Referência | Origem / observação |
|---|---|---|---|---|---|
| `uuid` | VARCHAR(44) | não | PK |  | CADASTRO_INDIVIDUAL.uuid |
| `id_cidadao` | BIGINT | não | FK | cidadao.id_cidadao, cadastro_individual.id_cidadao | possui (1,1) |
| `uuid_originadora` | VARCHAR(44) | sim | FK | cadastro_individual.uuid | atualiza (0,1) · uuidFichaOriginadora — Nula na primeira versão |
| `cns_profissional` | CHAR(15) | não | FK | lotacao.cns_profissional | registra (1,1) — FK composta para lotacao |
| `ine` | CHAR(10) | não | FK | lotacao.ine, microarea.ine | responde por (1,1) — FK composta para lotacao e microarea |
| `dt_cadastro` | DATE | não |  |  | CADASTRO_INDIVIDUAL.dt_cadastro |
| `dt_digitacao` | DATE | não |  |  | CADASTRO_INDIVIDUAL.dt_digitacao |
| `ficha_atualizada` | BOOLEAN | não |  |  | CADASTRO_INDIVIDUAL.ficha_atualizada |
| `recusa_cadastro` | BOOLEAN | não |  |  | CADASTRO_INDIVIDUAL.recusa_cadastro; padrão FALSE |
| `responsavel_familiar` | BOOLEAN | sim |  |  | CADASTRO_INDIVIDUAL.responsavel_familiar |
| `microarea` | CHAR(2) | sim | FK | microarea.codigo_microarea | CADASTRO_INDIVIDUAL.microarea |
| `fora_area` | BOOLEAN | sim |  |  | CADASTRO_INDIVIDUAL.fora_area |
| `raca_cor` | SMALLINT | sim | FK | dom_raca_cor.codigo | CADASTRO_INDIVIDUAL.raca_cor — Nula só em cadastro legado (regra de qualidade) |
| `etnia` | SMALLINT | sim | FK | dom_etnia.codigo | CADASTRO_INDIVIDUAL.etnia |
| `nome_social` | VARCHAR(70) | sim |  |  | CADASTRO_INDIVIDUAL.nome_social |
| `deseja_informar_os` | BOOLEAN | sim |  |  | CADASTRO_INDIVIDUAL.deseja_informar_os — Nulo = não informado |
| `orientacao_sexual` | SMALLINT | sim | FK | dom_orientacao_sexual.codigo | CADASTRO_INDIVIDUAL.orientacao_sexual |
| `deseja_informar_ig` | BOOLEAN | sim |  |  | CADASTRO_INDIVIDUAL.deseja_informar_ig — Nulo = não informado |
| `identidade_genero` | SMALLINT | sim | FK | dom_identidade_genero.codigo | CADASTRO_INDIVIDUAL.identidade_genero |
| `tem_deficiencia` | BOOLEAN | sim |  |  | CADASTRO_INDIVIDUAL.tem_deficiencia — Nulo = falha de registro |
| `escolaridade` | SMALLINT | sim | FK | dom_escolaridade.codigo | CADASTRO_INDIVIDUAL.escolaridade |
| `situacao_trabalho` | SMALLINT | sim | FK | dom_situacao_trabalho.codigo | CADASTRO_INDIVIDUAL.situacao_trabalho |
| `motivo_saida` | SMALLINT | sim | FK | dom_motivo_saida.codigo | CADASTRO_INDIVIDUAL.motivo_saida |
| `dt_obito` | DATE | sim |  |  | CADASTRO_INDIVIDUAL.dt_obito |

#### `cadastro_deficiencia`

Tipos de deficiência declarados numa versão (relacionamento declara, N:N). Origem: FCI · deficienciasCidadao.

| Coluna | Tipo | Nulo | Chave | Referência | Origem / observação |
|---|---|---|---|---|---|
| `uuid` | VARCHAR(44) | não | PK FK | cadastro_individual.uuid | declara |
| `codigo_deficiencia` | SMALLINT | não | PK FK | dom_tipo_deficiencia.codigo | declara |

#### `ficha_atendimento`

Ficha da FAI (lote de até 99 atendimentos): profissional, equipe e datas comuns. Origem: FAI · FichaAtendimentoIndividualMaster + VariasLotacoesHeader.

| Coluna | Tipo | Nulo | Chave | Referência | Origem / observação |
|---|---|---|---|---|---|
| `uuid_ficha` | VARCHAR(44) | não | PK |  | ATENDIMENTO_INDIVIDUAL.uuid_ficha |
| `cns_profissional` | CHAR(15) | não | FK | lotacao.cns_profissional | realiza (1,1) — FK composta para lotacao |
| `ine` | CHAR(10) | não | FK | lotacao.ine | lotacaoFormPrincipal.ine — FK composta para lotacao |
| `dt_atendimento` | DATE | não |  |  | ATENDIMENTO_INDIVIDUAL.dt_atendimento |
| `dt_digitacao` | DATE | não |  |  | ATENDIMENTO_INDIVIDUAL.dt_digitacao |

#### `atendimento_individual`

Um atendimento da FAI. Origem: FAI · FichaAtendimentoIndividualChild.

| Coluna | Tipo | Nulo | Chave | Referência | Origem / observação |
|---|---|---|---|---|---|
| `id_atendimento` | BIGINT | não | PK |  | ATENDIMENTO_INDIVIDUAL.id_atendimento |
| `uuid_ficha` | VARCHAR(44) | não | FK | ficha_atendimento.uuid_ficha |  |
| `nu_atendimento` | SMALLINT | não |  |  | Ordem do atendimento na ficha (DW: nu_atendimento) |
| `id_cidadao` | BIGINT | não | FK | cidadao.id_cidadao | é atendido em (1,1) |
| `dt_hora_inicio` | TIMESTAMP | não |  |  | ATENDIMENTO_INDIVIDUAL.dt_hora_inicio |
| `tipo_atendimento` | SMALLINT | não | FK | dom_tipo_atendimento.codigo | ATENDIMENTO_INDIVIDUAL.tipo_atendimento |
| `local_atendimento` | SMALLINT | não | FK | dom_local_atendimento.codigo | ATENDIMENTO_INDIVIDUAL.local_atendimento |
| `turno` | SMALLINT | não | FK | dom_turno.codigo | ATENDIMENTO_INDIVIDUAL.turno |

#### `atendimento_problema`

Problema ou condição avaliada (relacionamento avalia): CIAP2 e/ou CID-10 no mesmo item. Origem: FAI · ProblemaCondicao.

| Coluna | Tipo | Nulo | Chave | Referência | Origem / observação |
|---|---|---|---|---|---|
| `id_atendimento` | BIGINT | não | PK FK | atendimento_individual.id_atendimento | avalia |
| `nu_item` | SMALLINT | não | PK |  | Ordem do item no atendimento |
| `ciap` | VARCHAR(6) | sim | FK | dom_ciap.codigo | ProblemaCondicao.ciap |
| `cid10` | VARCHAR(4) | sim | FK | dom_cid10.codigo | ProblemaCondicao.cid10 |

#### `parametro`

Parâmetros de cada carga; fonte da regra do “dado real”. Origem: Projeto.

| Coluna | Tipo | Nulo | Chave | Referência | Origem / observação |
|---|---|---|---|---|---|
| `id_carga` | INT | não | PK |  | PARAMETRO.id_carga |
| `data_corte` | DATE | não |  |  | PARAMETRO.data_corte |
| `idade_min_elegivel` | SMALLINT | não |  |  | PARAMETRO.idade_min_elegivel; padrão 11 |
| `recusa_conta_ativo` | BOOLEAN | não |  |  | Pendência P1: termo de recusa entra em “ativos”?; padrão TRUE |
| `meses_desatualizado` | SMALLINT | não |  |  | Limite da regra de qualidade RQ06; padrão 24 |
| `semente` | INT | não |  |  | PARAMETRO.semente |
| `fator_escala` | DECIMAL(5,4) | não |  |  | PARAMETRO.fator_escala |
| `versao_gerador` | VARCHAR(20) | não |  |  | PARAMETRO.versao_gerador |
| `dt_geracao` | TIMESTAMP | não |  |  | Momento da geração |

#### `controle_defeito`

Gabarito dos defeitos injetados (Etapa 7); referência polimórfica, sem FK por desenho. Origem: Projeto (Etapa 7).

| Coluna | Tipo | Nulo | Chave | Referência | Origem / observação |
|---|---|---|---|---|---|
| `id_defeito` | INT | não | PK |  | CONTROLE_DEFEITO.id_defeito |
| `tabela` | VARCHAR(40) | não |  |  | CONTROLE_DEFEITO.tabela |
| `id_registro` | VARCHAR(44) | não |  |  | CONTROLE_DEFEITO.id_registro |
| `tipo_defeito` | SMALLINT | não | FK | dom_tipo_defeito.codigo | CONTROLE_DEFEITO.tipo_defeito |
| `etapa` | SMALLINT | não |  |  | CONTROLE_DEFEITO.etapa — Etapa do gerador que produziu o defeito (6 ou 7) |
| `campo` | VARCHAR(40) | sim |  |  | Coluna afetada |
| `id_registro_par` | VARCHAR(44) | sim |  |  | Par da duplicidade ou versão divergente |
| `valor_original` | VARCHAR(70) | sim |  |  | Valor antes da corrupção (verdade conhecida) |

### 4.3 Tabelas de domínio

Cada domínio guarda os **códigos do LEDI ou da fonte**, nunca a posição da opção na ficha (dicionário, D7). Os valores estão na seção 6 do dicionário e são carregados antes de qualquer outra tabela.

| Tabela | Código | Colunas além de `codigo` e `descricao` | Fonte | Usada por |
|---|---|---|---|---|
| `dom_sexo` | SMALLINT | — | LEDI · Sexo | cidadao.sexo |
| `dom_raca_cor` | SMALLINT | — | LEDI · RacaCor | cadastro_individual.raca_cor |
| `dom_etnia` | SMALLINT | — | LEDI · etnia | cadastro_individual.etnia |
| `dom_orientacao_sexual` | SMALLINT | — | LEDI · OrientacaoSexual | cadastro_individual.orientacao_sexual |
| `dom_identidade_genero` | SMALLINT | — | LEDI · identidadeGeneroCidadao | cadastro_individual.identidade_genero |
| `dom_tipo_deficiencia` | SMALLINT | — | LEDI · DeficienciaCidadao (entidade TIPO_DEFICIENCIA) | cadastro_deficiencia.codigo_deficiencia |
| `dom_escolaridade` | SMALLINT | — | LEDI · CursoMaisElevado | cadastro_individual.escolaridade |
| `dom_situacao_trabalho` | SMALLINT | — | LEDI · SituacaoMercadoTrabalho | cadastro_individual.situacao_trabalho |
| `dom_motivo_saida` | SMALLINT | — | LEDI · MotivoSaida | cadastro_individual.motivo_saida |
| `dom_tipo_imovel` | SMALLINT | — | LEDI · tipoDeImovel | domicilio.tipo_imovel |
| `dom_renda_familiar` | SMALLINT | — | LEDI · RendaFamiliar | familia.renda_familiar |
| `dom_tipo_atendimento` | SMALLINT | — | LEDI · TipoDeAtendimento | atendimento_individual.tipo_atendimento |
| `dom_local_atendimento` | SMALLINT | — | LEDI · LocalDeAtendimento | atendimento_individual.local_atendimento |
| `dom_turno` | SMALLINT | — | LEDI · Turno | atendimento_individual.turno |
| `dom_ciap` | VARCHAR(6) | `tipo` CHAR(5), `pre_natal` BOOLEAN, `procedimento` BOOLEAN | CIAP2 + LEDI · ListaCiapCondicaoAvaliada (entidade CODIGO_CLINICO) | atendimento_problema.ciap |
| `dom_cid10` | VARCHAR(4) | — | CID-10 (entidade CODIGO_CLINICO) | atendimento_problema.cid10 |
| `dom_cbo` | CHAR(6) | — | CBO 2002 (LEDI, anexos) | dom_cbo_ficha.cbo, lotacao.cbo |
| `dom_tipo_unidade` | SMALLINT | — | CNES · tipo de estabelecimento | unidade_saude.tipo_unidade |
| `dom_tipo_equipe` | SMALLINT | — | CNES · tipo de equipe | equipe.tipo_equipe |
| `dom_tipo_acao` | SMALLINT | — | Projeto | acao_formativa.tipo_acao |
| `dom_tipo_defeito` | SMALLINT | — | Projeto (Etapa 7) | controle_defeito.tipo_defeito |
| `dom_cbo_ficha` | (cbo, ficha) | — | LEDI · Grupos de CBO por modelo de informação | validação VC11 |

Códigos do domínio do projeto `dom_tipo_defeito` (Etapa 7), usados em `controle_defeito`:

| Código | Defeito | Regra de qualidade |
|---|---|---|
| 1 | Duplicidade de cidadão (mesma pessoa com CPF num registro e só CNS no outro, nome com variação) | RQ05 |
| 2 | Raça/cor em categoria errada, concentrada em algumas equipes | RQ04 |
| 3 | Raça/cor divergente entre versões do mesmo cidadão | RQ03 |
| 4 | Raça/cor vazia em cadastro legado | RQ01 |
| 5 | Cadastro desatualizado (mudou sem registro de saída) | RQ06 |
| 6 | OS/IG registrada para criança | RQ02 |
| 7 | Erro de digitação em nome ou endereço | RQ09 |
| 8 | Data implausível, mas aceita pelo PEC | RQ12 |
| 9 | Escolaridade incompatível com a idade | RQ10 |
| 10 | Atraso entre atendimento e digitação | RQ08 |
| 11 | Pergunta de OS/IG não feita (fica "não informado") | RQ07 |
| 12 | "Não" registrado sem a pergunta ter sido feita (cenário da pergunta 10 do Apêndice A) | RQ07 |
| 13 | "Tem deficiência" sem registro | RQ11 |

## 5. Normalização

### 5.1 Primeira forma normal

Todo atributo é atômico e não há grupos repetidos. Os pontos que exigiram decisão:

| Origem | Problema | Solução |
|---|---|---|
| `deficienciasCidadao` (lista de 1 a 6 códigos) | Grupo repetido | Tabela `cadastro_deficiencia` |
| `problemasCondicoes` (lista) | Grupo repetido | Tabela `atendimento_problema` |
| `condutas` da FAI (lista) | Grupo repetido | Fica só na *staging* (fora do escopo da v1) |
| Planilha: "US 302 USF BYRON SARINHO" | Código e nome no mesmo campo | `unidade_saude.cnes` e `nome_unidade` |
| Planilha: endereço em texto livre | Não atômico | Território por setor e bairro; logradouro só na *staging* |
| Planilha: quatro colunas novas por marcador | Esquema largo | Formato longo em `fato_indicador_equipe` |

### 5.2 Segunda forma normal

Só tabelas com chave composta podem violar a 2FN. Em todas elas o atributo não chave depende da chave inteira:

| Tabela | Chave | Atributos não chave | Situação |
|---|---|---|---|
| `lotacao` | (cns_profissional, ine) | `cbo` | A CBO é da lotação, não só do profissional nem só da equipe |
| `cadastro_deficiencia` | (uuid, codigo_deficiencia) | — | Só chave |
| `atendimento_problema` | (id_atendimento, nu_item) | `ciap`, `cid10` | Dependem do item |
| `dom_cbo_ficha` | (cbo, ficha) | — | Só chave |
| `atendimento_individual` | id_atendimento; alternativa (uuid_ficha, nu_atendimento) | demais | O cabeçalho da ficha saiu para `ficha_atendimento` (L2); antes, dependia só de `uuid_ficha` |

### 5.3 Terceira forma normal

Nenhum atributo não chave depende de outro atributo não chave:

| Dependência que existiria | Onde | Como foi removida |
|---|---|---|
| uuid → cns_profissional → ine | `cadastro_individual` | Lotação N:N; `(cns_profissional, ine)` passa a ser uma lotação, não um fato do profissional (L1) |
| cd_setor → bairro → distrito | `domicilio` | Tabelas `setor_censitario` e `bairro` (L4) |
| cnes → bairro → distrito | `unidade_saude` | A unidade guarda só o bairro (L4) |
| id_familia → CPF/CNS do responsável | `familia` | Responsável derivado do cadastro (L7) |
| ine → cnes, cnes → distrito | `cadastro_individual`, `acao_formativa`, `microarea` | Só o INE é guardado; unidade e distrito vêm pela junção |
| código → descrição | todas | Descrições só nas tabelas `dom_*` |

Três exceções são deliberadas e não comprometem a 3FN:

- **Referência polimórfica em `controle_defeito`.** `(tabela, id_registro)` aponta registros de oito tabelas diferentes; uma FK não expressa isso. O `CHECK` limita `tabela` às tabelas que podem receber defeito. A tabela é gabarito e não entra nos indicadores (RN27).
- **Estado mais recente em `domicilio` e `cidadao.id_familia`.** O conceitual não modela versões da FCDT. O vínculo **temporal** do cidadão com a equipe vem das versões da FCI, que é o que os indicadores usam; família e domicílio descrevem a situação mais recente.
- **`cidadao.sexo`.** No LEDI o sexo é enviado em cada ficha. O modelo o trata como atributo estável da pessoa, como no conceitual; uma divergência entre fichas seria resolvida na carga.

### 5.4 Desnormalizações da camada analítica

As tabelas da camada analítica são **derivadas**: são reconstruídas a cada carga a partir do núcleo e nunca recebem escrita direta. A redundância é aceita para que o painel e os modelos leiam uma tabela só.

| # | Onde | Redundância | Motivo | Como se mantém correta |
|---|---|---|---|---|
| D1 | `fato_indicador_equipe` | `cnes` e `id_ds` junto do `ine` | Filtros e mapa por distrito no Power BI sem junção | Recalculada inteira a cada carga |
| D2 | `fato_atendimento_equipe` | `n_cadastrados` | Denominador do alvo alternativo (contatos por cem cadastrados) | Idem |
| D3 | `fato_painel_ml` | `id_ds`, `tipo_equipe`, defasagens do alvo | Uma linha por equipe × período é a entrada pronta do modelo (Tabela 10 do plano) | Idem; as defasagens usam só períodos anteriores (sem vazamento) |
| D4 | `fato_indicador_equipe` | Formato longo com `marcador` e `categoria` em texto | O esquema não cresce quando entra um marcador novo (Tabela 2 do plano) | Valores de `marcador` e `categoria` documentados na seção 7.3 |

## 6. Domínios e restrições

### 6.1 Tipos

| Tipo no LEDI | *Staging* (como chega) | Núcleo |
|---|---|---|
| `Long` de data (epoch em ms) | `BIGINT` | `DATE` |
| `Long` de data e hora | `BIGINT` | `TIMESTAMP` |
| `Long`/`Integer` de código | `INT` | `SMALLINT` com FK para `dom_*` (exceto CIAP, CID e CBO, que são texto) |
| `String` de tamanho fixo | `VARCHAR(n)` | `CHAR(n)` com `CHECK` de formato (CPF 11, CNS 15, CNES 7, INE 10, CBO 6, setor 15, microárea 2) |
| `String` livre | `VARCHAR(máx)` | `VARCHAR(máx)` |
| `Boolean` | `BOOLEAN` | `BOOLEAN`; nulo só onde a ausência tem significado (OS, IG, deficiência) |
| `List<Long>` | `VARCHAR` com lista JSON | Tabela associativa |

Para a Etapa 4: o `CHECK` de formato usa expressão regular, que é `~` no PostgreSQL e `REGEXP` no MySQL; o MySQL só aplica `CHECK` a partir da versão 8.0.16 e não aceita `CHECK` em coluna que tenha ação referencial (`ON DELETE CASCADE`); nenhuma das restrições usa `IS DISTINCT FROM`, que o MySQL não tem (seção 6.5).

### 6.2 Restrições declarativas (R)

Além das chaves e do `NOT NULL` listados na seção 4.2, o núcleo tem as restrições abaixo. As FKs compostas e as chaves alternativas aparecem também no diagrama.

| Restrição | Tabela | Tipo | Regra | RN |
|---|---|---|---|---|
| `ck_dom_ciap_tipo` | dom_ciap | CHECK | `tipo IN ('CIAP2','AB')` | RN21 |
| `ck_cbo_ficha` | dom_cbo_ficha | CHECK | `ficha IN ('FCI','FCDT','FAI')` | RN04 |
| `ck_ds_faixa` | distrito_sanitario | CHECK | `id_ds BETWEEN 1 AND 8` | RN01 |
| `ck_setor_recife` | setor_censitario | CHECK | `cd_setor LIKE '2611606%'` | RN23 |
| `ck_cnes_formato` | unidade_saude | CHECK | `cnes ~ '^[0-9]{7}$'` | RN02 |
| `ck_ine_formato` | equipe | CHECK | `ine ~ '^[0-9]{10}$'` | RN03 |
| `uq_microarea_equipe` | microarea | UNIQUE | `(ine, codigo_microarea)` | RN05 |
| `ck_microarea_codigo` | microarea | CHECK | `codigo_microarea ~ '^[0-9]{2}$' AND codigo_microarea <> '00'` | RN05 |
| `ck_prof_cns` | profissional | CHECK | `cns_profissional ~ '^[0-9]{15}$'` | RN04 |
| `ck_dom_fora_area` | domicilio | CHECK | `(fora_area AND id_microarea IS NULL) OR (NOT fora_area AND id_microarea IS NOT NULL)` | RN23 / R7 |
| `ck_fam_membros` | familia | CHECK | `num_membros IS NULL OR num_membros BETWEEN 1 AND 999` | RN25 |
| `ck_cid_ident` | cidadao | CHECK | `cpf IS NOT NULL OR cns IS NOT NULL` | RN06 |
| `ck_cid_cpf` | cidadao | CHECK | `cpf IS NULL OR cpf ~ '^[0-9]{11}$'` | RN06 |
| `ck_cid_cns` | cidadao | CHECK | `cns IS NULL OR cns ~ '^[0-9]{15}$'` | RN06 |
| `uq_ci_uuid_cidadao` | cadastro_individual | UNIQUE | `(uuid, id_cidadao)` | RN08 |
| `fk_ci_originadora` | cadastro_individual | FK | `FK (uuid_originadora, id_cidadao) REFERENCES cadastro_individual (uuid, id_cidadao)` | RN08 |
| `fk_ci_lotacao` | cadastro_individual | FK | `FK (cns_profissional, ine) REFERENCES lotacao (cns_profissional, ine)` | RN04, RN11 |
| `fk_ci_microarea` | cadastro_individual | FK | `FK (ine, microarea) REFERENCES microarea (ine, codigo_microarea)` | RN11 |
| `ck_ci_cadeia` | cadastro_individual | CHECK | `(ficha_atualizada AND uuid_originadora IS NOT NULL AND uuid_originadora <> uuid) OR (NOT ficha_atualizada AND uuid_originadora IS NULL)` | RN08 |
| `ck_ci_digitacao` | cadastro_individual | CHECK | `dt_digitacao >= dt_cadastro` | RN20 |
| `ck_ci_fora_area` | cadastro_individual | CHECK | `fora_area IS NOT TRUE OR microarea IS NULL` | RN11 / R7 |
| `ck_ci_os` | cadastro_individual | CHECK | `(deseja_informar_os IS TRUE AND orientacao_sexual IS NOT NULL) OR (deseja_informar_os IS NOT TRUE AND orientacao_sexual IS NULL)` | RN13 |
| `ck_ci_ig` | cadastro_individual | CHECK | `(deseja_informar_ig IS TRUE AND identidade_genero IS NOT NULL) OR (deseja_informar_ig IS NOT TRUE AND identidade_genero IS NULL)` | RN14 |
| `ck_ci_etnia` | cadastro_individual | CHECK | `(COALESCE(raca_cor, 0) = 5 AND etnia IS NOT NULL) OR (COALESCE(raca_cor, 0) <> 5 AND etnia IS NULL)` | RN15 |
| `ck_ci_obito` | cadastro_individual | CHECK | `(COALESCE(motivo_saida, 0) = 135 AND dt_obito IS NOT NULL AND dt_obito <= dt_cadastro) OR (COALESCE(motivo_saida, 0) <> 135 AND dt_obito IS NULL)` | RN10 |
| `ck_ci_recusa` | cadastro_individual | CHECK | `NOT recusa_cadastro OR (deseja_informar_os IS NULL AND orientacao_sexual IS NULL AND deseja_informar_ig IS NULL AND identidade_genero IS NULL AND tem_deficiencia IS NULL AND escolaridade IS NULL AND situacao_trabalho IS NULL AND motivo_saida IS NULL AND dt_obito IS NULL)` | RN16 |
| `fk_fa_lotacao` | ficha_atendimento | FK | `FK (cns_profissional, ine) REFERENCES lotacao (cns_profissional, ine)` | RN19 |
| `ck_fa_digitacao` | ficha_atendimento | CHECK | `dt_digitacao >= dt_atendimento` | RN20 |
| `uq_ai_ficha_ordem` | atendimento_individual | UNIQUE | `(uuid_ficha, nu_atendimento)` | RN19 |
| `ck_ai_ordem` | atendimento_individual | CHECK | `nu_atendimento BETWEEN 1 AND 99` | RN19 |
| `ck_ai_tipo` | atendimento_individual | CHECK | `tipo_atendimento IN (1, 2, 4, 5, 6)` | RN22 |
| `ck_ai_local` | atendimento_individual | CHECK | `local_atendimento BETWEEN 1 AND 10` | RN22 |
| `uq_ap_ciap` | atendimento_problema | UNIQUE | `(id_atendimento, ciap)` | RN21 |
| `uq_ap_cid10` | atendimento_problema | UNIQUE | `(id_atendimento, cid10)` | RN21 |
| `ck_ap_codigo` | atendimento_problema | CHECK | `ciap IS NOT NULL OR cid10 IS NOT NULL` | RN21 |
| `ck_ap_w78` | atendimento_problema | CHECK | `COALESCE(ciap, '') <> 'W78' OR cid10 IS NULL OR cid10 LIKE 'Z34%'` | RN21 |
| `ck_par_idade` | parametro | CHECK | `idade_min_elegivel BETWEEN 0 AND 17` | RN26 |
| `ck_par_escala` | parametro | CHECK | `fator_escala > 0 AND fator_escala <= 1` | RN26 |
| `ck_par_meses` | parametro | CHECK | `meses_desatualizado > 0` | RN26 |
| `ck_def_tabela` | controle_defeito | CHECK | `tabela IN ('cidadao','cadastro_individual','cadastro_deficiencia','domicilio','familia','ficha_atendimento','atendimento_individual','atendimento_problema')` | RN27 |
| `ck_def_etapa` | controle_defeito | CHECK | `etapa IN (6, 7)` | RN27 |

### 6.3 Validações de carga (VC)

Regras que envolvem mais de uma linha ou tabela. Na Etapa 4 cada uma vira gatilho ou consulta de verificação; na Etapa 8, o procedimento *staging* → núcleo rejeita a linha e grava o motivo em `motivo_rejeicao`.

| # | Regra | Tabelas | RN |
|---|---|---|---|
| VC01 | "Tem deficiência" = Sim exige de 1 a 6 tipos; Não ou nulo exige nenhum | `cadastro_individual`, `cadastro_deficiencia` | RN12 |
| VC02 | Uma atualização não é anterior à versão que a originou | `cadastro_individual` | RN08 |
| VC03 | Nascimento não posterior à data da ficha nem mais de 130 anos antes; óbito não anterior ao nascimento | `cidadao`, `cadastro_individual` | RN10, R10 |
| VC04 | A mesma regra de nascimento vale para a data do atendimento | `cidadao`, `ficha_atendimento` | RN20 |
| VC05 | O início do atendimento não é anterior à data da ficha | `atendimento_individual`, `ficha_atendimento` | RN20 |
| VC06 | Todo atendimento avalia ao menos um problema | `atendimento_problema` | RN21 |
| VC07 | Sem CIAP de pré-natal antes dos 9 anos; no máximo uma CID Z34 por atendimento; sem CIAP de procedimento | `atendimento_problema`, `dom_ciap`, `cidadao` | RN21 |
| VC08 | Família só em imóvel do tipo Domicílio; domicílio só fica inativo se todas as famílias se mudaram | `familia`, `domicilio` | RN24 |
| VC09 | Toda família tem ao menos um membro | `cidadao`, `familia` | RN25 |
| VC10 | Todo cidadão tem ao menos uma versão do cadastro | `cidadao`, `cadastro_individual` | RN07 |
| VC11 | A CBO da lotação pode registrar a ficha (FCI, FCDT ou FAI) | `lotacao`, `dom_cbo_ficha` | RN04 |
| VC12 | Cardinalidades mínimas do território: distrito com bairro, unidade com equipe, equipe com microárea e com lotação | território | RN01–RN05 |
| VC13 | Nenhuma data posterior a `parametro.dt_geracao` | todas as datas | RN20 |
| VC14 | CPF e CNS com dígito verificador válido (o `CHECK` só confere tamanho e dígitos) | `cidadao`, `profissional` | RN04, RN06 |
| VC15 | Famílias da mesma FCDT sem responsável repetido | `stg.fcdt_familia` | RN25, R12 |

### 6.4 Regras de qualidade (RQ)

Não bloqueiam a carga. São medidas pela visão `vw_qualidade_registro`, uma linha por ocorrência (regra, tabela, registro), e comparadas com o gabarito de `controle_defeito`.

| # | Regra | Como é detectada | Defeito (Etapa 7) |
|---|---|---|---|
| RQ01 | Raça/cor preenchida em toda versão sem recusa | `raca_cor` nula com `recusa_cadastro` falso | 4 |
| RQ02 | OS/IG não registradas para crianças | Versão vigente com idade < `idade_min_elegivel` e "Deseja informar" preenchido | 6 |
| RQ03 | Raça/cor estável entre versões | Valor diferente da versão originadora | 3 |
| RQ04 | Raça/cor da equipe compatível com o território | Distância de Hellinger entre a distribuição da equipe e a do Censo nos setores atendidos | 2 |
| RQ05 | Um registro por pessoa | Nome normalizado + nascimento + sexo iguais em cidadãos diferentes | 1 |
| RQ06 | Cadastro atualizado | Versão vigente mais antiga que `meses_desatualizado` | 5 |
| RQ07 | Pergunta de OS/IG feita | "Deseja informar" nulo (não informado) | 11, 12 |
| RQ08 | Digitação em dia | Distribuição de `dt_digitacao − dt_cadastro` e `− dt_atendimento` por equipe | 10 |
| RQ09 | Nome sem erro de digitação | Só pelo gabarito; detectar é tarefa do modelo de classificação | 7 |
| RQ10 | Escolaridade compatível com a idade | Idade na data da ficha × curso | 9 |
| RQ11 | "Tem deficiência" registrado | Nulo com `recusa_cadastro` falso (dicionário, D4) | 13 |
| RQ12 | Datas plausíveis | Nascimento em data-padrão (ex.: 01/01) ou idade acima de 110 anos | 8 |

O plano fala em injetar "datas inválidas". Uma data que viola o LEDI (nascimento futuro, óbito antes do nascimento) seria recusada pelo PEC e, aqui, pela carga. Por isso o gerador deve injetar só datas **implausíveis e aceitas** (RQ12); datas impossíveis, se injetadas, aparecem como linhas rejeitadas na *staging*, que também é um resultado mensurável.

### 6.5 Teste do esquema

O esquema foi criado num PostgreSQL 16 com as três camadas e testado com:

- **10 casos válidos**, que precisam entrar: adulto com OS e IG informadas e dois tipos de deficiência; criança com "Deseja informar OS" = Sim (RQ02); cidadão com duas versões, raça/cor divergente e mudança de equipe (RQ03); óbito; duplicidade da mesma pessoa só com CNS (RQ05); cadastro legado com raça/cor, OS e deficiência vazias (RQ01, RQ11); termo de recusa com raça/cor; indígena com etnia, fora de área; versão posterior à data de corte; ficha da FAI com dois atendimentos, W78 + Z340 e o código `A01` como CIAP e como CID.
- **49 casos inválidos**, que precisam ser recusados **pela restrição esperada**: um ou mais para cada `CHECK`, `UNIQUE` e FK composta da seção 6.2.

Resultado: 10 de 10 válidos aceitos e 49 de 49 inválidos recusados pela restrição certa. As visões também foram conferidas: `vw_cadastro_vigente` escolheu a versão certa de cada cidadão (inclusive ignorando a versão posterior à data de corte), tirou o óbito dos ativos e marcou a criança; `vw_monitoramento_equipe` e `vw_monitoramento_usf` fecharam H − I = J e M ÷ J; e a versão vigente por competência acompanhou a mudança de equipe e a saída por mudança de território mês a mês.

Uma lição do teste: na primeira rodada, a restrição da etnia aceitou etnia sem raça/cor. Com `raca_cor` nulo, a expressão `raca_cor = 5` dá *desconhecido*, e um `CHECK` desconhecido **passa**. As três restrições com esse risco (`ck_ci_etnia`, `ck_ci_obito`, `ck_ap_w78`) foram reescritas com `COALESCE`, que também funciona no MySQL. As demais usam `IS TRUE`/`IS NOT TRUE` ou testam o nulo explicitamente.

## 7. Camadas

| Camada | Esquema | Função | Restrições | Quem escreve |
|---|---|---|---|---|
| *Staging* | `stg` | Recebe o dado como chega: fichas no formato do LEDI e arquivos do CNES e da Prefeitura | Só a chave técnica (carga, linha); todas as colunas aceitam nulo | Gerador (Etapa 6) ou extração real |
| Núcleo | `nucleo` | Banco normalizado (3FN), fonte única da verdade | Todas as R; VC na carga | Procedimento de carga (Etapa 8) |
| Analítica | `analitica` | Visões e tabelas-fato para planilha, painel e modelos | Chaves das tabelas-fato | Procedimento de atualização após cada carga |

No MySQL, cada esquema é um *database* (`stg`, `nucleo`, `analitica`) no mesmo servidor; no PostgreSQL, três *schemas* do mesmo banco.

### 7.1 *Staging*

A *staging* imita o formato em que o dado real chegará. Como a forma de acesso ainda não foi pactuada (Apêndice A, pergunta 7), ela segue o **LEDI**, que é o formato que o gerador emite; a coluna DW de cada campo está no dicionário, seção 3 a 5, para o caso de o dado real vir do Data Warehouse. Os nomes das colunas são os do LEDI em `snake_case` (`statusDesejaInformarOrientacaoSexual` → `status_deseja_informar_orientacao_sexual`).

Toda tabela da *staging* tem as mesmas quatro colunas de controle: `id_carga` e `nu_linha` (chave), `st_processamento` (`P` pendente, `C` carregada, `R` rejeitada) e `motivo_rejeicao`. Datas ficam em `BIGINT` (epoch em ms) e listas em texto JSON, como no LEDI. Os campos marcados como "S" no dicionário (obrigatórios no LEDI, mas não analisados) estão aqui e não passam ao núcleo.

#### `stg.fci`

FCI como chega (uma linha por ficha). Fonte: LEDI · CadastroIndividual (ver dicionário, seção 3).

| Coluna | Tipo | Campo LEDI / origem |
|---|---|---|
| `id_carga` | INT | Carga que trouxe a linha |
| `nu_linha` | BIGINT | Linha no arquivo de origem |
| `st_processamento` | CHAR(1) | P pendente, C carregada, R rejeitada |
| `motivo_rejeicao` | VARCHAR(200) | Restrição violada, se rejeitada |
| `profissional_cns` | VARCHAR(15) | headerTransport.profissionalCNS |
| `cbo_codigo_2002` | VARCHAR(6) | headerTransport.cboCodigo_2002 |
| `cnes` | VARCHAR(7) | headerTransport.cnes |
| `ine` | VARCHAR(10) | headerTransport.ine |
| `data_atendimento` | BIGINT | headerTransport.dataAtendimento (epoch ms) |
| `codigo_ibge_municipio` | VARCHAR(7) | headerTransport.codigoIbgeMunicipio |
| `uuid` | VARCHAR(44) | uuid |
| `uuid_ficha_originadora` | VARCHAR(44) | uuidFichaOriginadora |
| `ficha_atualizada` | BOOLEAN | fichaAtualizada |
| `tp_cds_origem` | INT | tpCdsOrigem |
| `status_termo_recusa_cadastro_individual_atencao_basica` | BOOLEAN | statusTermoRecusa… |
| `cpf_cidadao` | VARCHAR(11) | cpfCidadao |
| `cns_cidadao` | VARCHAR(15) | cnsCidadao |
| `st_nao_possui_cpf` | BOOLEAN | stNaoPossuiCpf |
| `justificativa_nao_possui_cpf` | INT | justificativaNaoPossuiCpf |
| `nome_cidadao` | VARCHAR(70) | nomeCidadao |
| `nome_social` | VARCHAR(70) | nomeSocial |
| `data_nascimento_cidadao` | BIGINT | dataNascimentoCidadao |
| `sexo_cidadao` | INT | sexoCidadao |
| `raca_cor_cidadao` | INT | racaCorCidadao |
| `etnia` | INT | etnia |
| `nacionalidade_cidadao` | INT | nacionalidadeCidadao |
| `pais_nascimento` | INT | paisNascimento |
| `codigo_ibge_municipio_nascimento` | VARCHAR(7) | codigoIbgeMunicipioNascimento |
| `nome_mae_cidadao` | VARCHAR(70) | nomeMaeCidadao |
| `desconhece_nome_mae` | BOOLEAN | desconheceNomeMae |
| `nome_pai_cidadao` | VARCHAR(70) | nomePaiCidadao |
| `desconhece_nome_pai` | BOOLEAN | desconheceNomePai |
| `status_eh_responsavel` | BOOLEAN | statusEhResponsavel |
| `cpf_responsavel_familiar` | VARCHAR(11) | cpfResponsavelFamiliar |
| `cns_responsavel_familiar` | VARCHAR(15) | cnsResponsavelFamiliar |
| `microarea` | VARCHAR(2) | microarea |
| `st_fora_area` | BOOLEAN | stForaArea |
| `status_deseja_informar_orientacao_sexual` | BOOLEAN | statusDesejaInformarOrientacaoSexual |
| `orientacao_sexual_cidadao` | INT | orientacaoSexualCidadao |
| `status_deseja_informar_identidade_genero` | BOOLEAN | statusDesejaInformarIdentidadeGenero |
| `identidade_genero_cidadao` | INT | identidadeGeneroCidadao |
| `status_tem_alguma_deficiencia` | BOOLEAN | statusTemAlgumaDeficiencia |
| `deficiencias_cidadao` | VARCHAR(40) | deficienciasCidadao (lista JSON) |
| `grau_instrucao_cidadao` | INT | grauInstrucaoCidadao |
| `situacao_mercado_trabalho_cidadao` | INT | situacaoMercadoTrabalhoCidadao |
| `relacao_parentesco_cidadao` | INT | relacaoParentescoCidadao |
| `status_frequenta_escola` | BOOLEAN | statusFrequentaEscola |
| `status_membro_povo_comunidade_tradicional` | BOOLEAN | statusMembroPovoComunidadeTradicional |
| `co_povo_comunidade_tradicional` | INT | coPovoComunidadeTradicional |
| `motivo_saida_cidadao` | INT | motivoSaidaCidadao |
| `data_obito` | BIGINT | dataObito |
| `numero_do` | VARCHAR(9) | numeroDO |
| `dt_digitacao` | DATE | projeto (não existe no LEDI) |

#### `stg.fcdt`

FCDT como chega (uma linha por ficha). Fonte: LEDI · CadastroDomiciliar (dicionário, seção 4).

| Coluna | Tipo | Campo LEDI / origem |
|---|---|---|
| `id_carga` | INT | Carga que trouxe a linha |
| `nu_linha` | BIGINT | Linha no arquivo de origem |
| `st_processamento` | CHAR(1) | P pendente, C carregada, R rejeitada |
| `motivo_rejeicao` | VARCHAR(200) | Restrição violada, se rejeitada |
| `profissional_cns` | VARCHAR(15) | headerTransport.profissionalCNS |
| `cbo_codigo_2002` | VARCHAR(6) | headerTransport.cboCodigo_2002 |
| `cnes` | VARCHAR(7) | headerTransport.cnes |
| `ine` | VARCHAR(10) | headerTransport.ine |
| `data_atendimento` | BIGINT | headerTransport.dataAtendimento (epoch ms) |
| `codigo_ibge_municipio` | VARCHAR(7) | headerTransport.codigoIbgeMunicipio |
| `uuid` | VARCHAR(44) | uuid |
| `uuid_ficha_originadora` | VARCHAR(44) | uuidFichaOriginadora |
| `ficha_atualizada` | BOOLEAN | fichaAtualizada |
| `tp_cds_origem` | INT | tpCdsOrigem |
| `status_termo_recusa` | BOOLEAN | statusTermoRecusa |
| `tipo_de_imovel` | INT | tipoDeImovel |
| `tipo_endereco` | INT | tipoEndereco |
| `st_ativo` | BOOLEAN | stAtivo |
| `bairro` | VARCHAR(72) | enderecoLocalPermanencia.bairro |
| `cep` | VARCHAR(8) | cep |
| `codigo_ibge_municipio_endereco` | VARCHAR(7) | enderecoLocalPermanencia.codigoIbgeMunicipio |
| `nome_logradouro` | VARCHAR(72) | nomeLogradouro |
| `numero` | VARCHAR(10) | numero |
| `numero_dne_uf` | VARCHAR(2) | numeroDneUf |
| `tipo_logradouro_numero_dne` | VARCHAR(5) | tipoLogradouroNumeroDne |
| `micro_area` | VARCHAR(2) | microArea |
| `st_fora_area` | BOOLEAN | stForaArea |
| `localizacao` | INT | condicaoMoradia.localizacao |
| `situacao_moradia_posse_terra` | INT | situacaoMoradiaPosseTerra |
| `tipo_domicilio` | INT | tipoDomicilio |
| `cd_setor` | VARCHAR(15) | projeto (no dado real viria de geocodificação) |

#### `stg.fcdt_familia`

Famílias de cada FCDT (uma linha por FamiliaRow). Fonte: LEDI · FamiliaRow.

| Coluna | Tipo | Campo LEDI / origem |
|---|---|---|
| `id_carga` | INT | Carga que trouxe a linha |
| `nu_linha` | BIGINT | Linha no arquivo de origem |
| `st_processamento` | CHAR(1) | P pendente, C carregada, R rejeitada |
| `motivo_rejeicao` | VARCHAR(200) | Restrição violada, se rejeitada |
| `uuid` | VARCHAR(44) | uuid da FCDT |
| `nu_familia` | INT | ordem na lista familias |
| `numero_cns_responsavel` | VARCHAR(15) | numeroCnsResponsavel |
| `cpf_responsavel` | VARCHAR(11) | cpfResponsavel |
| `data_nascimento_responsavel` | BIGINT | dataNascimentoResponsavel |
| `numero_membros_familia` | INT | numeroMembrosFamilia |
| `renda_familiar` | INT | rendaFamiliar |
| `reside_desde` | BIGINT | resideDesde |
| `st_mudanca` | BOOLEAN | stMudanca |

#### `stg.fai`

FAI como chega (uma linha por atendimento, com o cabeçalho da ficha repetido). Fonte: LEDI · FichaAtendimentoIndividualMaster/Child (dicionário, seção 5).

| Coluna | Tipo | Campo LEDI / origem |
|---|---|---|
| `id_carga` | INT | Carga que trouxe a linha |
| `nu_linha` | BIGINT | Linha no arquivo de origem |
| `st_processamento` | CHAR(1) | P pendente, C carregada, R rejeitada |
| `motivo_rejeicao` | VARCHAR(200) | Restrição violada, se rejeitada |
| `uuid_ficha` | VARCHAR(44) | uuidFicha |
| `tp_cds_origem` | INT | tpCdsOrigem |
| `profissional_cns` | VARCHAR(15) | lotacaoFormPrincipal.profissionalCNS |
| `cbo_codigo_2002` | VARCHAR(6) | lotacaoFormPrincipal.cboCodigo_2002 |
| `cnes` | VARCHAR(7) | lotacaoFormPrincipal.cnes |
| `ine` | VARCHAR(10) | lotacaoFormPrincipal.ine |
| `data_atendimento` | BIGINT | headerTransport.dataAtendimento |
| `codigo_ibge_municipio` | VARCHAR(7) | headerTransport.codigoIbgeMunicipio |
| `nu_atendimento` | INT | posição em atendimentosIndividuais |
| `cpf_cidadao` | VARCHAR(11) | cpfCidadao |
| `cns_cidadao` | VARCHAR(15) | cnsCidadao |
| `st_cidadao_nao_possui_cpf` | BOOLEAN | stCidadaoNaoPossuiCpf |
| `justificativa_nao_possui_cpf` | INT | justificativaNaoPossuiCpf |
| `data_nascimento` | BIGINT | dataNascimento |
| `sexo` | INT | sexo |
| `local_de_atendimento` | INT | localDeAtendimento |
| `turno` | INT | turno |
| `tipo_atendimento` | INT | tipoAtendimento |
| `condutas` | VARCHAR(60) | condutas (lista JSON) |
| `data_hora_inicial_atendimento` | BIGINT | dataHoraInicialAtendimento |
| `data_hora_final_atendimento` | BIGINT | dataHoraFinalAtendimento |
| `dt_digitacao` | DATE | projeto (não existe no LEDI) |

#### `stg.fai_problema`

Problemas e condições de cada atendimento. Fonte: LEDI · ProblemaCondicao.

| Coluna | Tipo | Campo LEDI / origem |
|---|---|---|
| `id_carga` | INT | Carga que trouxe a linha |
| `nu_linha` | BIGINT | Linha no arquivo de origem |
| `st_processamento` | CHAR(1) | P pendente, C carregada, R rejeitada |
| `motivo_rejeicao` | VARCHAR(200) | Restrição violada, se rejeitada |
| `uuid_ficha` | VARCHAR(44) | uuidFicha |
| `nu_atendimento` | INT | posição do atendimento |
| `nu_item` | INT | posição em problemasCondicoes |
| `ciap` | VARCHAR(6) | ciap |
| `cid10` | VARCHAR(4) | cid10 |
| `is_avaliado` | BOOLEAN | isAvaliado |

Tabelas auxiliares, carregadas na Etapa 5 (estrutura real) e na Etapa 6 (profissionais fictícios):

| Tabela | Conteúdo | Colunas |
|---|---|---|
| `stg.cnes_estabelecimento` | Estabelecimentos do CNES no Recife (Etapa 5) | `cnes`, `nome_fantasia`, `tipo_unidade`, `bairro` |
| `stg.cnes_equipe` | Equipes do CNES no Recife (Etapa 5) | `ine`, `cnes`, `nome_equipe`, `tipo_equipe` |
| `stg.malha_territorial` | Setor censitário → bairro → distrito (Etapa 5) | `cd_setor`, `nome_bairro`, `id_bairro`, `nome_ds` |
| `stg.profissional_lotacao` | Profissionais fictícios e lotações emitidos pelo gerador | `cns_profissional`, `nome_profissional`, `ine`, `cbo` |

**Transformação *staging* → núcleo** (detalhada na Etapa 8):

| Regra | Exemplo |
|---|---|
| Epoch em ms → `DATE`/`TIMESTAMP` | `data_atendimento` → `dt_cadastro` |
| `uuid_ficha_originadora = uuid` → nula | Primeira versão (RN08) |
| CPF ou CNS da ficha → `id_cidadao` | Busca por CPF; sem CPF, por CNS; sem nenhum dos dois, cria cidadão |
| Lista JSON → linhas | `deficiencias_cidadao` → `cadastro_deficiencia` |
| `status_termo_recusa… = nulo` → falso | `recusa_cadastro` é `NOT NULL` |
| Responsável da família (CPF/CNS) → `responsavel_familiar` na versão do cidadão | L7 |
| Violação de R ou VC → `st_processamento = 'R'` | A linha fica na *staging* com o motivo |

### 7.2 Núcleo

Descrito nas seções 4 a 6 e desenhado no brModelo.

### 7.3 Analítica

#### `analitica.dim_competencia`

Calendário das competências mensais. Origem: Projeto.

| Coluna | Tipo | Nulo | Chave | Referência | Origem / observação |
|---|---|---|---|---|---|
| `competencia` | INT | não | PK |  | AAAAMM |
| `dt_inicio` | DATE | não |  |  |  |
| `dt_fim` | DATE | não |  |  |  |
| `ano` | SMALLINT | não |  |  |  |
| `mes` | SMALLINT | não |  |  |  |
| `quadrimestre` | INT | não |  |  | AAAAQ (Q = 1, 2, 3) |
| `semestre` | INT | não |  |  | AAAAS (S = 1, 2) |

#### `analitica.ref_parametro_oficial`

Parâmetros oficiais da Etapa 5 em formato longo (metas de calibração). Origem: CSV versionados da Etapa 5.

| Coluna | Tipo | Nulo | Chave | Referência | Origem / observação |
|---|---|---|---|---|---|
| `fonte` | VARCHAR(30) | não | PK |  | Censo 2022, PNS 2019, SISAB… |
| `tabela_fonte` | VARCHAR(30) | não | PK |  | Ex.: SIDRA 9605 |
| `nivel` | VARCHAR(12) | não | PK |  | municipio, ds, bairro, setor, usf, equipe |
| `cd_territorio` | VARCHAR(15) | não | PK |  |  |
| `variavel` | VARCHAR(40) | não | PK |  |  |
| `categoria` | VARCHAR(40) | não | PK |  |  |
| `valor` | DECIMAL(14,6) | não |  |  |  |
| `ic_inferior` | DECIMAL(14,6) | sim |  |  |  |
| `ic_superior` | DECIMAL(14,6) | sim |  |  |  |
| `dt_acesso` | DATE | não |  |  |  |

#### `analitica.fato_indicador_equipe`

Indicadores em formato longo por competência e equipe (painel). Origem: Derivada do núcleo.

| Coluna | Tipo | Nulo | Chave | Referência | Origem / observação |
|---|---|---|---|---|---|
| `competencia` | INT | não | PK FK | dim_competencia.competencia |  |
| `ine` | CHAR(10) | não | PK FK | equipe.ine |  |
| `cnes` | CHAR(7) | não |  |  | Redundante (desnormalização D1) |
| `id_ds` | SMALLINT | não |  |  | Redundante (desnormalização D1) |
| `marcador` | VARCHAR(20) | não | PK |  | OS, IG, RACA_COR, DEFICIENCIA… |
| `categoria` | VARCHAR(30) | não | PK |  | SIM, NAO, NAO_INFORMADO, código… |
| `faixa_etaria` | VARCHAR(10) | não | PK |  |  |
| `elegivel` | BOOLEAN | não | PK |  | Idade ≥ idade_min_elegivel no fim da competência |
| `n` | INT | não |  |  |  |

#### `analitica.fato_atendimento_equipe`

Atendimentos por competência e equipe (alvo alternativo de utilização). Origem: Derivada do núcleo.

| Coluna | Tipo | Nulo | Chave | Referência | Origem / observação |
|---|---|---|---|---|---|
| `competencia` | INT | não | PK FK | dim_competencia.competencia |  |
| `ine` | CHAR(10) | não | PK FK | equipe.ine |  |
| `n_atendimentos` | INT | não |  |  |  |
| `n_cidadaos_atendidos` | INT | não |  |  |  |
| `n_cadastrados` | INT | não |  |  | Denominador, redundante (D2) |
| `atraso_medio_digitacao` | DECIMAL(7,2) | sim |  |  | Dias |

#### `analitica.fato_painel_ml`

Painel equipe × período do problema supervisionado (Tabela 10 do plano). Origem: Derivada do núcleo.

| Coluna | Tipo | Nulo | Chave | Referência | Origem / observação |
|---|---|---|---|---|---|
| `ine` | CHAR(10) | não | PK FK | equipe.ine |  |
| `periodo` | INT | não | PK |  | Quadrimestre AAAAQ (parametrizável) |
| `id_ds` | SMALLINT | não |  |  | Redundante (D3) |
| `tipo_equipe` | SMALLINT | não |  |  | Redundante (D3) |
| `n_dado_real` | INT | não |  |  | Ativos elegíveis no fim do período |
| `prop_sim_os` | DECIMAL(6,5) | sim |  |  |  |
| `prop_nao_os` | DECIMAL(6,5) | sim |  |  |  |
| `prop_ni_os` | DECIMAL(6,5) | sim |  |  |  |
| `prop_sim_ig` | DECIMAL(6,5) | sim |  |  |  |
| `prop_sim_os_lag1` | DECIMAL(6,5) | sim |  |  |  |
| `prop_sim_os_lag2` | DECIMAL(6,5) | sim |  |  |  |
| `prop_criancas` | DECIMAL(6,5) | sim |  |  |  |
| `prop_60_mais` | DECIMAL(6,5) | sim |  |  |  |
| `dist_raca_cor_censo` | DECIMAL(6,5) | sim |  |  | Distância de Hellinger |
| `atraso_medio_digitacao` | DECIMAL(7,2) | sim |  |  |  |
| `n_acoes_ate_periodo` | SMALLINT | não |  |  | Só ações até o fim do período (RN18); padrão 0 |
| `alvo_prop_sim_os` | DECIMAL(6,5) | sim |  |  | Alvo: proporção Sim no período seguinte |
| `alvo_prop_sim_ig` | DECIMAL(6,5) | sim |  |  | Alvo do segundo modelo |

Valores de `marcador` e `categoria` em `fato_indicador_equipe`:

| `marcador` | `categoria` |
|---|---|
| `OS` | `SIM`, `NAO`, `NAO_INFORMADO` (o "Deseja informar"), e o código da orientação para quem respondeu |
| `IG` | Mesma lógica, com o código da identidade de gênero |
| `RACA_COR` | Código de `dom_raca_cor` ou `VAZIO` |
| `DEFICIENCIA` | `SIM`, `NAO`, `SEM_REGISTRO` e o código de cada tipo |
| `NOME_SOCIAL` | `PREENCHIDO`, `VAZIO` (a confirmar com a Secretaria, Apêndice A, pergunta 3) |

Visões:

| Visão | O que entrega | Regra principal |
|---|---|---|
| `vw_parametro_vigente` | A linha de `parametro` da carga mais recente | Toda visão lê os parâmetros daqui (RN26) |
| `vw_cadastro_vigente` | Uma linha por cidadão: versão vigente, equipe, unidade, distrito, idade na data de corte, `crianca`, `ativo` | Maior `dt_cadastro` ≤ `data_corte`; desempate por `dt_digitacao` e `uuid` (RN09). Idade calculada na data de corte. Ativo = sem saída e, se `recusa_conta_ativo` for falso, sem recusa |
| `vw_monitoramento_usf` | Colunas H a U da planilha da SESAU por USF | Tabela 9 do plano; percentuais calculados na consulta |
| `vw_monitoramento_equipe` | Mesmas colunas por INE | Granularidade pedida pela Secretaria |
| `vw_qualidade_registro` | Ocorrências das RQ01–RQ12 em formato longo | Seção 6.4 |

`fato_indicador_equipe` aplica a mesma regra de versão vigente da `vw_cadastro_vigente`, mas para cada competência: a versão vigente no mês é a de maior `dt_cadastro` até `dim_competencia.dt_fim`. Foi essa variante que o teste usou para conferir a mudança de equipe e a saída mês a mês. `fato_painel_ml` agrega as competências no período escolhido (quadrimestre, por padrão) e calcula o alvo no período **seguinte**, usando como entradas só o que existe até o fim do período de referência (RN18; Tabela 10 do plano).

## 8. Rastreabilidade das regras de negócio

| Regra | Implementação no lógico | Tipo |
|---|---|---|
| RN01 | `bairro.id_ds`, `unidade_saude.id_bairro`, `ck_ds_faixa` | R, VC12 |
| RN02 | `unidade_saude.cnes` `CHAR(7)`, `ck_cnes_formato` | R |
| RN03 | `equipe.ine` `CHAR(10)`, `ck_ine_formato` | R |
| RN04 | `lotacao`, `dom_cbo_ficha`, `ck_prof_cns` | R, VC11, VC14 |
| RN05 | `uq_microarea_equipe`, `ck_microarea_codigo` | R |
| RN06 | `ck_cid_ident`, `ck_cid_cpf`, `ck_cid_cns`, `UNIQUE` em CPF e CNS | R, VC14 |
| RN07 | `cadastro_individual.uuid`, FK para `cidadao` | R, VC10 |
| RN08 | `fk_ci_originadora`, `uq_ci_uuid_cidadao`, `ck_ci_cadeia` | R, VC02 |
| RN09 | `vw_cadastro_vigente` | Derivação |
| RN10 | `ck_ci_obito`; `parametro.recusa_conta_ativo` | R, VC03, derivação |
| RN11 | `fk_ci_microarea`, `ck_ci_fora_area`, `fk_ci_lotacao` | R |
| RN12 | `cadastro_deficiencia` (PK composta) | R, VC01 |
| RN13, RN14 | `ck_ci_os`, `ck_ci_ig` | R |
| RN15 | `ck_ci_etnia`; raça/cor nula medida em RQ01 | R, RQ |
| RN16 | `ck_ci_recusa` (corrigida, L8) | R |
| RN17, RN18 | `acao_formativa`; `fato_painel_ml.n_acoes_ate_periodo` | R, derivação |
| RN19 | `ficha_atendimento`, `fk_fa_lotacao`, `uq_ai_ficha_ordem` | R |
| RN20 | `ck_ci_digitacao`, `ck_fa_digitacao` | R, VC04, VC05, VC13 |
| RN21 | `atendimento_problema`, `uq_ap_ciap`, `uq_ap_cid10`, `ck_ap_codigo`, `ck_ap_w78` | R, VC06, VC07 |
| RN22 | `ck_ai_tipo`, `ck_ai_local` | R |
| RN23 | `ck_dom_fora_area`, `ck_setor_recife`; endereço só na *staging* | R |
| RN24 | — | VC08 |
| RN25 | `ck_fam_membros`; responsável derivado (L7) | R, VC09, VC15 |
| RN26 | `parametro` e `vw_parametro_vigente` | R, derivação |
| RN27 | `controle_defeito`, `ck_def_tabela`, `ck_def_etapa` | R |
| RN28 | Nenhuma coluna de geolocalização no núcleo; nome só em `cidadao` e `profissional`, fora das visões | Estrutura |

## 9. Ajustes propostos para a Etapa 2

Para manter conceitual, regras e lógico coerentes, o grupo precisa aprovar estes ajustes, que levariam `modelo_conceitual_aps_recife` e `regras_de_negocio.md` à versão 1.1.0:

| Item | Ajuste | Decisão |
|---|---|---|
| Relacionamento **lota** | De `(1,1)` para N:N, com o atributo `cbo` (sai de PROFISSIONAL) | L1 |
| **responde por** | De `(0,1)` para `(1,1)` no lado da equipe | L9 |
| ATENDIMENTO_INDIVIDUAL | Separar FICHA_ATENDIMENTO (1:N) com profissional, equipe e datas | L2 |
| CODIGO_CLINICO e **avalia** | Trocar por entidade fraca PROBLEMA_AVALIADO ligada a CIAP2 e CID-10 | L3 |
| Território | Incluir BAIRRO e SETOR_CENSITARIO; unidade e domicílio deixam de ter `bairro` e `setor` como atributos | L4 |
| RN11 e RN08 | Trocar "gatilho" por "FK composta" na garantia | L5, L6 |
| RN16 | Raça/cor, etnia e nome social podem vir com recusa | L8 |
| RN25 | Responsável familiar derivado do cadastro | L7 |
| Seção 7 das regras | Pendência 4 (lotação N:N) resolvida | L1 |

## 10. Pendências

| # | Pendência | Efeito | Encaminhamento |
|---|---|---|---|
| P1 | Termo de recusa conta entre os "cidadãos ativos"? | Muda a coluna H da planilha | Parâmetro `recusa_conta_ativo` (valor inicial `TRUE`, a confirmar); Apêndice A |
| P2 | Idade mínima elegível: 10 ou 11 anos | Muda I, J e todos os percentuais | Parâmetro `idade_min_elegivel`; Apêndice A, pergunta 1 |
| P3 | O dado real terá fichas sem INE? | Linhas rejeitadas na *staging* (L9) | Se houver volume, a lotação ganha `cnes` próprio |
| P4 | A unidade pertence ao distrito do seu bairro? | Se não, `unidade_saude` volta a ter `id_ds` | Conferir na Etapa 5 contra as abas da planilha e a tabela da Prefeitura |
| P5 | Cada setor censitário está contido num único bairro? | Se não, `setor_censitario` precisa de tabela de correspondência | Conferir na Etapa 5 com as malhas do IBGE e da Prefeitura |
| P6 | Semântica de `st_informar_orientacao_sexual` no DW (dicionário, D6) | Inversão de Sim/Não se a *staging* vier do DW | Confirmar com amostra real |
| P7 | Códigos do CNES para tipo de unidade e de equipe | Conteúdo de `dom_tipo_unidade` e `dom_tipo_equipe` | Carregar na Etapa 5 a partir do CNES |

## Histórico de versões

| Versão | Data | Alteração |
|---|---|---|
| 1.0.0 | 2026-10-20 | Primeira versão: esquema relacional das três camadas, normalização, restrições R/VC/RQ, teste em PostgreSQL 16 e diagrama lógico no brModelo |
