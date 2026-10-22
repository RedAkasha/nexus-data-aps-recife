---
documento: Modelo físico — Emulação de dados da APS para as políticas de equidade do Recife
projeto: Projeto 3 – Dados (CESAR School, 2026.2) · Equipe 2 – Nexus Data
etapa: Etapa 4 – Modelagem física
versao: 1.0.0
data: 2026-10-20
status: rascunho para revisão do grupo
arquivos:
  - 01_ddl_mysql.sql (MySQL 8.0.16 ou superior)
  - 01_ddl_postgresql.sql (PostgreSQL 16)
  - 02_carga_dominios.sql (os dois SGBD)
  - 03_validacao_carga_mysql.sql
  - 03_validacao_carga_postgresql.sql
base: modelo_logico.md v1.0.0; dicionario_dados.md v1.0.0; LEDI APS 8.7.0; Emulacao_Dados_APS_Recife_Projeto3_v3 (Etapa 4, Tabelas 6 e 8)
---

# Modelo físico — Etapa 4

Este documento acompanha os três produtos da Etapa 4 do plano de emulação: o **script DDL**, o **script de carga de domínios** e esta **documentação física** (tipos, índices e volumes estimados). Acrescenta um quarto script, de **validação de carga**, que o modelo lógico deixou para esta etapa (seção 6.3 de `modelo_logico.md`).

O plano admite dois SGBD: o MySQL 8, adotado na disciplina, e o PostgreSQL, que é o SGBD do PEC. Os scripts saem para os dois, a partir da mesma especificação usada no modelo lógico, então as tabelas, colunas, chaves e restrições são as mesmas. Os dois foram executados e testados com os mesmos casos, e os resultados foram idênticos (seção 9).

## 1. Como executar

Ordem obrigatória: `01_ddl` → `02_carga_dominios` → `03_validacao_carga`.

**MySQL 8.0.16 ou superior** (abaixo dessa versão o MySQL aceita, mas não aplica, as restrições `CHECK`):

```
mysql -u <usuario> -p --default-character-set=utf8mb4 < 01_ddl_mysql.sql
mysql -u <usuario> -p --default-character-set=utf8mb4 < 02_carga_dominios.sql
mysql -u <usuario> -p --default-character-set=utf8mb4 < 03_validacao_carga_mysql.sql
```

O script cria três *databases*, `stg`, `nucleo` e `analitica`. O usuário precisa de permissão para criar *database*, tabela, visão e função. Para a carga em massa da Etapa 8 com `LOAD DATA LOCAL INFILE`, o servidor precisa de `local_infile = 1`.

**PostgreSQL 16:**

```
createdb -E UTF8 -T template0 aps_recife
psql -d aps_recife -v ON_ERROR_STOP=1 -f 01_ddl_postgresql.sql
psql -d aps_recife -v ON_ERROR_STOP=1 -f 02_carga_dominios.sql
psql -d aps_recife -v ON_ERROR_STOP=1 -f 03_validacao_carga_postgresql.sql
```

O script cria três *schemas* no mesmo banco, com os mesmos nomes.

O `--default-character-set=utf8mb4` no MySQL importa: sem ele, o cliente pode ler o arquivo como `latin1` e gravar errado as descrições acentuadas dos domínios. Aconteceu no teste: sem a opção, "Indígena" foi gravado como "IndÃ­gena".

**Recriar do zero.** No MySQL, apague na ordem `analitica`, `nucleo`, `stg`, porque há FKs da analítica para o núcleo. A carga de domínios apaga e recarrega cada domínio, então só pode ser repetida com o núcleo vazio.

## 2. Decisões de implementação

| Decisão | MySQL 8 | PostgreSQL 16 | Motivo |
|---|---|---|---|
| Camadas | Três *databases* no mesmo servidor | Três *schemas* no mesmo banco | O MySQL não tem *schema* dentro de *database*; nos dois casos o nome qualificado é `camada.tabela`, e as visões e FKs entre camadas funcionam |
| Motor e codificação | InnoDB; `utf8mb4` com `utf8mb4_0900_ai_ci` | Banco `UTF8` | InnoDB é o único motor do MySQL com FK e transação; `utf8mb4` guarda qualquer acento e símbolo |
| Colunas de código | `CHARACTER SET ascii COLLATE ascii_bin` nas colunas `CHAR(n)`, nos `uuid` e em CIAP/CID (núcleo e analítica) | Sem ajuste | Códigos só têm dígitos, letras e hífen. Em ASCII ocupam 1 byte por caractere e a comparação binária diferencia maiúsculas, que o LEDI exige na CIAP2 |
| Chaves substitutas | Sem `AUTO_INCREMENT` | Sem `IDENTITY` | Os identificadores vêm do gerador com semente fixa; assim o mesmo parâmetro gera banco idêntico (RN26) |
| Ações referenciais | Nenhuma (`RESTRICT` implícito) | Nenhuma (`NO ACTION`) | Ninguém apaga dado do núcleo; a carga é refeita inteira. Além disso, o MySQL proíbe `CHECK` em coluna que tenha `ON DELETE/UPDATE CASCADE` |
| Nomes de restrição | Todas nomeadas, com prefixo `pk_`, `uq_`, `fk_`, `ck_`, `ix_` | Idem | A mensagem de erro da carga diz qual regra foi violada; foi assim que o teste conferiu cada caso |
| Comentários | `COMMENT` em cada coluna e tabela, com a origem no LEDI | `COMMENT ON TABLE` | O dicionário fica no próprio banco |
| Regras entre linhas | Visão `vw_validacao_carga`, rodada depois da carga | Idem | Ver seção 6 |

**Ordem de criação.** Uma tabela só é criada depois das que ela referencia. No núcleo:

`dom_sexo` → `dom_raca_cor` → `dom_etnia` → `dom_orientacao_sexual` → `dom_identidade_genero` → `dom_tipo_deficiencia` → `dom_escolaridade` → `dom_situacao_trabalho` → `dom_motivo_saida` → `dom_tipo_imovel` → `dom_renda_familiar` → `dom_tipo_atendimento` → `dom_local_atendimento` → `dom_turno` → `dom_ciap` → `dom_cid10` → `dom_cbo` → `dom_tipo_unidade` → `dom_tipo_equipe` → `dom_tipo_acao` → `dom_tipo_defeito` → `dom_cbo_ficha` → `distrito_sanitario` → `bairro` → `setor_censitario` → `unidade_saude` → `equipe` → `microarea` → `profissional` → `lotacao` → `acao_formativa` → `domicilio` → `familia` → `cidadao` → `cadastro_individual` → `cadastro_deficiencia` → `ficha_atendimento` → `atendimento_individual` → `atendimento_problema` → `parametro` → `controle_defeito`

## 3. Tipos físicos

| Tipo lógico | MySQL 8 | PostgreSQL 16 | Observação |
|---|---|---|---|
| `SMALLINT`, `INT`, `BIGINT` | Igual | Igual | `BIGINT` só onde o volume pede (`id_cidadao`, `id_atendimento`) ou onde o LEDI já usa (datas em epoch na *staging*) |
| `CHAR(n)` de código | `CHAR(n)` ASCII binário | `CHAR(n)` | CPF 11, CNS 15, CNES 7, INE 10, CBO 6, setor 15, microárea 2 |
| `VARCHAR(44)` de UUID | ASCII binário | `VARCHAR(44)` | 7 dígitos do CNES + hífen + 36 do UUID, como o LEDI recomenda |
| `VARCHAR(n)` de texto | `utf8mb4` | `VARCHAR(n)` | Nomes, descrições, bairro |
| `DATE` | `DATE` | `DATE` | Todas as datas do núcleo |
| `TIMESTAMP` | **`DATETIME`** | `TIMESTAMP` | O `TIMESTAMP` do MySQL converte fuso e só vai até 2038; `DATETIME` guarda a hora do atendimento como foi registrada |
| `BOOLEAN` | `TINYINT(1)` (sinônimo) | `BOOLEAN` | `IS TRUE` e `IS NOT TRUE` funcionam nos dois |
| `DECIMAL(p,s)` | Igual | Igual | Proporções e fator de escala |

Nas restrições, a única diferença de sintaxe é a expressão regular: `~` no PostgreSQL e `REGEXP` no MySQL. Nenhuma restrição usa `IS DISTINCT FROM`, que o MySQL não tem; as três que precisavam tratar nulo usam `COALESCE` (modelo lógico, seção 6.5).

## 4. Restrições

| Tipo | Núcleo | Analítica | *Staging* | Total |
|---|--:|--:|--:|--:|
| Chave primária | 41 | 5 | 9 | 55 |
| `UNIQUE` | 10 | — | — | 10 |
| Chave estrangeira | 43 | 5 | — | 48 |
| `CHECK` | 32 | 3 | — | 35 |

Os números são os do catálogo dos dois SGBD depois da execução (`information_schema` no MySQL, `pg_constraint` no PostgreSQL), e coincidem. A *staging* só tem a chave técnica `(id_carga, nu_linha)`: todo o resto entra como chegou e é validado na passagem para o núcleo.

No MySQL, nomes de `CHECK` e de FK são únicos por *database*, e não por tabela. Todos os nomes do modelo já eram únicos, então nada precisou mudar.

## 5. Índices

Toda chave primária e toda restrição `UNIQUE` criam o seu índice. Além delas, o DDL declara **35 índices** de filtro e junção. A regra foi:

1. **Toda FK entre tabelas de dados tem índice** cujo início coincide com as colunas da FK. Sem ele, cada verificação de integridade e cada junção percorre a tabela inteira. Quando a PK ou um `UNIQUE` já começa pelas colunas da FK, não há índice extra.
2. **FKs para tabelas de domínio não recebem índice no PostgreSQL.** Os domínios têm poucos valores (raça/cor tem 5), nunca são apagados e as consultas filtram por eles junto com equipe e período. No MySQL o InnoDB cria esses índices sozinho, porque exige índice em toda coluna de FK. Por isso o MySQL tem 117 índices e o PostgreSQL, 100.
3. **As colunas de filtro do plano** (CNES, INE e data de cadastro) aparecem como primeira ou segunda coluna dos índices de equipe e período.

| Tabela | Índice | Colunas | Uso |
|---|---|---|---|
| `nucleo.bairro` | `ix_bairro_ds` | id_ds | FK; filtro por distrito |
| `nucleo.setor_censitario` | `ix_setor_bairro` | id_bairro | FK; setor → bairro |
| `nucleo.unidade_saude` | `ix_unidade_bairro` | id_bairro | FK; unidade → bairro → distrito |
| `nucleo.equipe` | `ix_equipe_cnes` | cnes | FK; agregação equipe → unidade (planilha por USF) |
| `nucleo.lotacao` | `ix_lotacao_ine` | ine | FK; profissionais da equipe |
| `nucleo.acao_formativa` | `ix_acao_ine_data` | ine, dt_acao | FK; ações até o fim do período (RN18) |
| `nucleo.domicilio` | `ix_domicilio_setor` | cd_setor | FK; calibração por setor e mapa por distrito |
| `nucleo.domicilio` | `ix_domicilio_microarea` | id_microarea | FK |
| `nucleo.familia` | `ix_familia_domicilio` | id_domicilio | FK |
| `nucleo.cidadao` | `ix_cidadao_familia` | id_familia | FK |
| `nucleo.cidadao` | `ix_cidadao_nasc_sexo` | dt_nascimento, sexo | Busca de duplicidade (RQ05) e faixa etária |
| `nucleo.cadastro_individual` | `ix_ci_vigente` | id_cidadao, dt_cadastro, dt_digitacao, uuid | FK; versão vigente (RN09): partição por cidadão ordenada por data |
| `nucleo.cadastro_individual` | `ix_ci_equipe_data` | ine, dt_cadastro | Indicadores por equipe e competência |
| `nucleo.cadastro_individual` | `ix_ci_lotacao` | cns_profissional, ine | FK composta para lotacao |
| `nucleo.cadastro_individual` | `ix_ci_microarea` | ine, microarea | FK composta para microarea |
| `nucleo.cadastro_individual` | `ix_ci_originadora` | uuid_originadora, id_cidadao | FK composta da cadeia de versões |
| `nucleo.cadastro_deficiencia` | `ix_cd_tipo` | codigo_deficiencia, uuid | Prevalência por tipo de deficiência |
| `nucleo.ficha_atendimento` | `ix_fa_equipe_data` | ine, dt_atendimento | Produção por equipe e competência |
| `nucleo.ficha_atendimento` | `ix_fa_lotacao` | cns_profissional, ine | FK composta para lotacao |
| `nucleo.atendimento_individual` | `ix_ai_cidadao` | id_cidadao | FK; atendimentos do cidadão |
| `nucleo.atendimento_problema` | `ix_ap_ciap` | ciap | FK; atendimentos por condição (CIAP2) |
| `nucleo.atendimento_problema` | `ix_ap_cid10` | cid10 | FK; atendimentos por condição (CID-10) |
| `nucleo.controle_defeito` | `ix_def_registro` | tabela, id_registro | Cruzar gabarito com registros |
| `nucleo.controle_defeito` | `ix_def_tipo` | tipo_defeito | Contagem por tipo de defeito |
| `analitica.fato_indicador_equipe` | `ix_fie_equipe` | ine, competencia | FK; série de uma equipe |
| `analitica.fato_indicador_equipe` | `ix_fie_ds` | id_ds, competencia, marcador | Filtro do painel por distrito |
| `analitica.fato_atendimento_equipe` | `ix_fae_equipe` | ine, competencia | FK; série de uma equipe |
| `analitica.fato_painel_ml` | `ix_pml_periodo` | periodo | Partição temporal treino/teste |
| `stg.fci` | `ix_stg_fci_proc` | id_carga, st_processamento | Linhas pendentes de uma carga |
| `stg.fci` | `ix_stg_fci_uuid` | uuid | Resolver a cadeia uuid → originadora |
| `stg.fcdt` | `ix_stg_fcdt_proc` | id_carga, st_processamento | Linhas pendentes de uma carga |
| `stg.fcdt_familia` | `ix_stg_fam_uuid` | uuid | Famílias de cada FCDT |
| `stg.fai` | `ix_stg_fai_proc` | id_carga, st_processamento | Linhas pendentes de uma carga |
| `stg.fai` | `ix_stg_fai_ficha` | uuid_ficha, nu_atendimento | Juntar atendimento e problemas |
| `stg.fai_problema` | `ix_stg_faip_ficha` | uuid_ficha, nu_atendimento | Juntar atendimento e problemas |

Duas observações de desenho:

- `ix_ci_vigente (id_cidadao, dt_cadastro, dt_digitacao, uuid)` segue a mesma ordem da regra da versão vigente (RN09). Quando a consulta pede a versão de um cidadão ou de um grupo de cidadãos, o SGBD lê o índice já ordenado, sem ordenar de novo.
- `cadastro_individual` tem sete índices além da PK e do `UNIQUE`, e é a tabela mais escrita da carga. O custo é aceitável porque a carga é em lote e as consultas da camada analítica dependem deles. Na Etapa 8, a carga em massa pode desligar a verificação de FK e recriar os índices no fim, se o tempo de carga for um problema.

## 6. Validações de carga

O script `03_validacao_carga` cria duas funções e uma visão:

| Objeto | O que faz |
|---|---|
| `nucleo.fn_cpf_valido(cpf)` | Confere os dois dígitos verificadores do CPF e rejeita sequências repetidas (`111.111.111-11`) |
| `nucleo.fn_cns_valido(cns)` | Confere o CNS: começa com 1 ou 2 (definitivo) ou 7, 8 ou 9 (provisório), e a soma dos dígitos ponderados de 15 a 1 é múltipla de 11 |
| `analitica.vw_validacao_carga` | Uma linha por violação das regras VC01 a VC15, com regra, tabela e registro. Resultado vazio = carga íntegra |

As validações são **consultas de conjunto, rodadas depois da carga**, e não gatilhos. Há dois motivos. Primeiro, várias regras só podem ser avaliadas depois que todas as linhas chegaram: a VC01 (versão com deficiência precisa de ao menos um tipo) falharia num gatilho, porque a versão é inserida antes dos seus tipos. Segundo, um gatilho roda uma vez por linha; com milhões de linhas por carga, isso multiplicaria o tempo de carga. Na Etapa 8, o procedimento de carga lê a visão e marca as linhas de origem como rejeitadas na *staging*.

As duas funções foram conferidas contra uma implementação de referência em Python, com 6.010 casos (CPF e CNS válidos e inválidos, mais as dez sequências repetidas): zero divergência nos dois SGBD.

**Um defeito do MySQL encontrado no teste.** Na primeira versão, a função de CPF do MySQL dizia que **todo** CPF era inválido. A causa: dentro de uma função armazenada do MySQL 8.0 (testado no 8.0.46), a comparação `p_cpf = REPEAT(SUBSTRING(p_cpf, 1, 1), 11)` dá verdadeiro para qualquer valor de `p_cpf`, como se a expressão alterasse o próprio parâmetro. A mesma expressão fora da função dá o resultado certo. A checagem de dígitos repetidos passou a usar expressão regular, que funciona igual nos dois SGBD. Fica o registro para quem escrever funções no MySQL nas próximas etapas: não derivar strings do próprio parâmetro dentro da função sem testar.

## 7. Carga de domínios

`02_carga_dominios.sql` usa só SQL padrão e roda sem mudança nos dois SGBD. Cada domínio é apagado e recarregado, então o script pode ser executado de novo enquanto o núcleo estiver vazio.

| Tabela | Valores | Fonte |
|---|--:|---|
| `dom_sexo` | 4 | LEDI · Sexo |
| `dom_raca_cor` | 5 | LEDI · RacaCor |
| `dom_etnia` | 406 | LEDI · etnia |
| `dom_orientacao_sexual` | 7 | LEDI · OrientacaoSexual |
| `dom_identidade_genero` | 7 | LEDI · identidadeGeneroCidadao |
| `dom_tipo_deficiencia` | 6 | LEDI · DeficienciaCidadao (com TEA, 232) |
| `dom_escolaridade` | 15 | LEDI · CursoMaisElevado |
| `dom_situacao_trabalho` | 10 | LEDI · SituacaoMercadoTrabalho |
| `dom_motivo_saida` | 2 | LEDI · MotivoSaida |
| `dom_tipo_imovel` | 14 | LEDI · tipoDeImovel |
| `dom_renda_familiar` | 8 | LEDI · RendaFamiliar |
| `dom_tipo_atendimento` | 8 | LEDI · TipoDeAtendimento (todos; a FAI aceita 1, 2, 4, 5 e 6) |
| `dom_local_atendimento` | 17 | LEDI · LocalDeAtendimento (todos; a FAI aceita 1 a 10) |
| `dom_turno` | 3 | LEDI · Turno |
| `dom_ciap` | 691 | 686 CIAP2 da relação oficial CIAP2 × CID10 do LEDI e os 5 Códigos AB da `ListaCiapCondicaoAvaliada` |
| `dom_cid10` | 554 | CID-10 da relação oficial CIAP2 × CID10 do LEDI (subconjunto) |
| `dom_cbo` | 2709 | Lista de CBOs do LEDI, mais 515124 (Agente indígena de saúde), que está no grupo da FCI mas falta na lista geral |
| `dom_cbo_ficha` | 298 | Grupos de CBO do LEDI: 122 para a FCI, 113 para a FCDT e 63 para a FAI |
| `dom_tipo_acao` | 3 | Projeto: oficina, material formativo, outra |
| `dom_tipo_defeito` | 13 | Projeto (modelo lógico, seção 4.3) |
| `dom_tipo_unidade`, `dom_tipo_equipe` | 0 | CNES, na Etapa 5 |

O que fica para a Etapa 5:

- **`dom_tipo_unidade` e `dom_tipo_equipe`** ficam vazias. Os códigos de tipo de estabelecimento e de tipo de equipe vêm do CNES, que é a fonte prevista para unidades e equipes (pendência P7 do modelo lógico). Até lá, `unidade_saude` e `equipe` não podem ser carregadas.
- **CID-10 completa.** `dom_cid10` traz as 554 CID-10 da relação oficial CIAP2 × CID10 do LEDI, o que basta para o gerador. A CID-10 completa do DATASUS, com milhares de subcategorias, é necessária quando o banco receber dado real, e também para expandir os agrupamentos do DW escritos como "que contenha o código I13".
- **CIAP2 de pré-natal.** O LEDI proíbe "CIAP2 relacionada ao pré-natal" antes dos 9 anos, mas não lista quais são. Só `W78` e `W84`, os dois exemplos citados pelo LEDI, estão marcados em `dom_ciap.pre_natal`. É preciso confirmar se outros códigos do capítulo W entram na regra.

## 8. Volumes estimados

### 8.1 Premissas da escala completa

| Premissa | Valor | Fonte |
|---|--:|---|
| População residente do Recife | 1.488.920 | Censo 2022 (plano, Tabela 6) |
| Cobertura da ESF | 80% | SESAU, reunião de 01/09 (plano, Tabela 6) |
| Cidadãos cadastrados | 1.191.136 | População × cobertura |
| Duplicidade de cidadão | 2% | Premissa do grupo (Etapa 7) |
| Versões da FCI por cidadão | 3,0 | Premissa: cadastro inicial mais cerca de uma atualização a cada 1,5 ano em 3,75 anos de série |
| Moradores por domicílio | 2,79 | Média nacional do Censo 2022 ([O Povo, 28/06/2023](https://www.opovo.com.br/noticias/economia/2023/06/28/amp/populacao-do-brasil-passa-de-203-milhoes-mostra-censo-2022.html)); a média do Recife entra na Etapa 5 |
| Imóveis não residenciais na FCDT | 10% dos domicílios | Premissa |
| Famílias por domicílio | 1,05 | Premissa |
| Pessoas com deficiência | 8,4%, com 1,3 tipo por pessoa | Censo 2022 (plano, Tabela 6); tipos por pessoa é premissa |
| Atendimentos individuais | 1,5 por cadastrado por ano, em 3,75 anos | Premissa, a calibrar com a produção do SISAB na Etapa 5 |
| Atendimentos por ficha da FAI | 10 | Premissa (a FAI admite até 99) |
| Problemas avaliados por atendimento | 1,3 | Premissa |
| Defeitos no gabarito | 5% das versões | Premissa (Etapa 7) |
| Território | 8 distritos, 94 bairros, cerca de 1.800 setores, 144 unidades, 400 equipes, 2.000 microáreas | Plano e planilha da SESAU; setores e microáreas são ordem de grandeza (cerca de 300 domicílios por setor e 600 cadastrados por ACS), a conferir na Etapa 5 |
| Indicadores no formato longo | 45 competências × 400 equipes × 290 combinações não vazias | Seção 7.3 do modelo lógico |

### 8.2 Método

Os bytes por linha não foram calculados pelo tamanho teórico dos tipos, que ignora cabeçalho de linha, páginas e índices. Foram **medidos**: os scripts desta etapa foram executados nos dois SGBD, e as tabelas foram carregadas com dados de enchimento a **5% da escala completa** (2.348.953 linhas), com chaves, restrições e índices ativos. O enchimento é aleatório e só serve para medir: respeita todas as restrições do DDL, mas não tem as distribuições do Censo, que são trabalho do gerador (Etapa 6). Depois da carga, o PostgreSQL mediu com `pg_relation_size` e `pg_indexes_size` (após `VACUUM ANALYZE`) e o MySQL com `data_length` e `index_length` (após `ANALYZE TABLE`). Os bytes por linha medidos foram multiplicados pelo número de linhas da escala completa.

### 8.3 Resultado

| Camada | Tabela | Linhas (100%) | PG bytes/linha (dados + índices) | PG MB | MySQL bytes/linha (dados + índices) | MySQL MB |
|---|---|--:|--:|--:|--:|--:|
| núcleo | `distrito_sanitario` | 8 | — | < 1 | — | < 1 |
| núcleo | `bairro` | 94 | — | < 1 | — | < 1 |
| núcleo | `setor_censitario` | 1.800 | 55 + 64 | < 1 | 55 + 46 | < 1 |
| núcleo | `unidade_saude` | 144 | — | < 1 | — | < 1 |
| núcleo | `equipe` | 400 | — | < 1 | — | < 1 |
| núcleo | `microarea` | 2.000 | 53 + 86 | < 1 | 57 + 41 | < 1 |
| núcleo | `profissional` | 3.200 | 69 + 51 | < 1 | 92 + 0 | < 1 |
| núcleo | `lotacao` | 3.300 | 70 + 92 | < 1 | 84 + 124 | < 1 |
| núcleo | `acao_formativa` | 1.152 | 71 + 107 | < 1 | 85 + 57 | < 1 |
| núcleo | `domicilio` | 469.624 | 109 + 143 | 114 | 112 + 216 | 147 |
| núcleo | `familia` | 448.277 | 48 + 47 | 41 | 71 + 36 | 46 |
| núcleo | `cidadao` | 1.214.959 | 90 + 124 | 248 | 78 + 200 | 322 |
| núcleo | `cadastro_individual` | 3.644.877 | 184 + 409 | 2.061 | 268 + 1340 | 5.590 |
| núcleo | `cadastro_deficiencia` | 398.021 | 77 + 179 | 98 | 194 + 139 | 126 |
| núcleo | `ficha_atendimento` | 670.014 | 113 + 137 | 161 | 173 + 284 | 292 |
| núcleo | `atendimento_individual` | 6.700.140 | 110 + 126 | 1.511 | 102 + 228 | 2.108 |
| núcleo | `atendimento_problema` | 8.710.182 | 49 + 107 | 1.295 | 40 + 99 | 1.152 |
| núcleo | `controle_defeito` | 182.244 | 117 + 158 | 48 | 174 + 195 | 64 |
| núcleo | `parametro` | 10 | — | < 1 | — | < 1 |
| staging | `stg.fci` | 3.644.877 | 344 + 127 | 1.638 | 336 + 133 | 1.629 |
| staging | `stg.fai` | 6.700.140 | 249 + 144 | 2.514 | 230 + 157 | 2.478 |
| staging | `stg.fai_problema` | 8.710.182 | 121 + 114 | 1.957 | 102 + 151 | 2.108 |
| analítica | `dim_competencia` | 45 | — | < 1 | — | < 1 |
| analítica | `fato_indicador_equipe` | 5.220.000 | 81 + 79 | 796 | 111 + 157 | 1.335 |

`stg.fcdt` e `stg.fcdt_familia` não foram medidas; têm cerca de 0,9 milhão de linhas cada por carga (premissa de duas versões por domicílio), menos que `stg.fci`. As tabelas de domínio somam menos de 2 MB.

| Camada | PostgreSQL 16 | MySQL 8 |
|---|--:|--:|
| Núcleo | 5,4 GB | 9,6 GB |
| Analítica | 0,8 GB | 1,3 GB |
| *Staging* (por carga) | 6,0 GB | 6,1 GB |

**Por que o MySQL ocupa mais.** A diferença está quase toda em `cadastro_individual` (1.340 bytes de índice por linha no MySQL, contra 409 no PostgreSQL). No InnoDB, cada índice secundário guarda também a chave primária, e a PK dessa tabela é o `uuid` de 44 caracteres. Além disso, o InnoDB cria um índice para cada uma das sete FKs de domínio da tabela, que o PostgreSQL não precisa ter. Trocar o `uuid` por uma chave numérica reduziria o tamanho, mas afastaria o núcleo do identificador do LEDI. Como o volume cabe numa máquina de desenvolvimento, a troca não foi feita.

**Recomendações.**

- **Desenvolver com fator de escala de 10%** (`parametro.fator_escala = 0,1`), que dá cerca de 1,2 GB no PostgreSQL e 1,7 GB no MySQL, somando todas as camadas. A escala completa fica para a validação final (Etapa 8).
- **Esvaziar a *staging* depois de cada carga bem-sucedida**, guardando só as linhas rejeitadas. Ela é tão grande quanto o núcleo e não é usada nas análises.
- **Guardar o espaço da camada analítica como materialização.** `fato_indicador_equipe` é a tabela que o painel lê; as visões sobre o núcleo servem para conferir a planilha.

### 8.4 Tempos na escala medida (5%)

| Operação | PostgreSQL 16 | MySQL 8 |
|---|--:|--:|
| Carga das 2.348.953 linhas (`COPY` / `LOAD DATA`), com FKs e índices ativos | 55,8 s | 99,1 s |
| `vw_monitoramento_equipe` (planilha por equipe, 400 linhas) | 0,35 s | 1,95 s |
| `vw_qualidade_registro` | 1,56 s | 5,44 s |
| `vw_validacao_carga` | 4,52 s | 15,6 s |

O PostgreSQL foi mais rápido em todas as operações. Na escala completa, os tempos devem crescer perto de 20 vezes, o que ainda é aceitável para processamento em lote, mas confirma que o painel deve ler a tabela materializada, e não a visão.

Como o enchimento é aleatório, ele violou três validações de carga: nascimento posterior ao atendimento (VC04), CIAP2 de pré-natal em criança (VC07) e família sem membro (VC09). Os dois SGBD apontaram o mesmo número de violações, o que é outra prova de que as visões se comportam igual.

## 9. Testes

| Teste | MySQL 8.0.46 | PostgreSQL 16.15 |
|---|---|---|
| Execução dos três scripts num banco vazio | Sem erro | Sem erro |
| Objetos criados | 41 tabelas no núcleo, 9 na *staging*, 5 tabelas e 6 visões na analítica | Idem |
| Casos válidos da Etapa 3 (incluindo os defeitos da Etapa 7) | 10 de 10 aceitos | 10 de 10 aceitos |
| Casos inválidos da Etapa 3 | 49 de 49 recusados pela restrição esperada | 49 de 49 recusados pela restrição esperada |
| Visões `vw_cadastro_vigente`, `vw_monitoramento_usf` e `vw_qualidade_registro` | Mesmo resultado nos dois | Mesmo resultado nos dois |
| `vw_validacao_carga` sem violações nos dados de teste | Vazia | Vazia |
| Oito violações provocadas de propósito (VC01, VC02, VC03, VC06, VC07, VC09, VC10, VC14) | Todas detectadas na regra certa | Todas detectadas na regra certa |
| Funções de CPF e CNS contra a referência em Python | 6.010 casos, 0 divergência | 6.010 casos, 0 divergência |
| Carga de 5% da escala | Concluída com todas as restrições ativas | Concluída com todas as restrições ativas |

Os casos de teste usam os domínios reais de `02_carga_dominios.sql`. Dois códigos dos testes da Etapa 3 foram ajustados por isso: `Z340` virou `Z34`, que é a forma presente na relação oficial do LEDI, e o par CIAP2/CID-10 com o mesmo código passou a ser `R07`, que existe nas duas tabelas.

## 10. Pendências

| # | Pendência | Efeito | Encaminhamento |
|---|---|---|---|
| F1 | Carregar `dom_tipo_unidade` e `dom_tipo_equipe` do CNES | Sem elas, unidades e equipes não entram | Etapa 5 (P7 do modelo lógico) |
| F2 | Carregar a CID-10 completa do DATASUS | Necessária para dado real e para expandir os agrupamentos do DW | Etapa 5 |
| F3 | Confirmar a lista de CIAP2 de pré-natal | Afeta a VC07 | Consultar a equipe técnica do e-SUS ou o manual do PEC |
| F4 | Conferir setores, microáreas e moradores por domicílio do Recife | Ajusta as linhas da seção 8 | Etapa 5 (SIDRA e CNES) |
| F5 | Calibrar atendimentos por cadastrado com a produção do SISAB | Ajusta o maior volume do núcleo | Etapa 5 |
| F6 | Decidir o SGBD do produto final | O núcleo no MySQL ocupa cerca de 1,8 vez o do PostgreSQL, e o MySQL foi mais lento; PostgreSQL é o SGBD do PEC | Grupo, com o Prof. Lucas Farias |
| F7 | Ajustes da Etapa 2 propostos no modelo lógico (seção 9) | O físico já segue o lógico; o conceitual ainda não | Aprovação do grupo |

## Histórico de versões

| Versão | Data | Alteração |
|---|---|---|
| 1.0.0 | 2026-10-20 | Primeira versão: DDL para MySQL 8 e PostgreSQL 16, carga de domínios do LEDI 8.7.0, validações de carga, índices e volumes medidos a 5% da escala |
