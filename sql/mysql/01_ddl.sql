-- =====================================================================
-- Emulação de dados da APS para as políticas de equidade do Recife
-- Etapa 4 – Modelagem física · script DDL · MySQL 8.0.16 ou superior
-- Projeto 3 – Dados (CESAR School, 2026.2) · Equipe 2 – Nexus Data
-- Versão 1.0.0 · 2026-10-20 · gerado a partir do modelo lógico v1.0.0
-- Ordem de execução: 01_ddl → 02_carga_dominios → 03_validacao_carga
-- =====================================================================

SET NAMES utf8mb4;
SET SESSION sql_mode = 'STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION,ONLY_FULL_GROUP_BY';

-- No MySQL cada camada é um database no mesmo servidor.
CREATE DATABASE IF NOT EXISTS stg       DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE DATABASE IF NOT EXISTS nucleo    DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE DATABASE IF NOT EXISTS analitica DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;


-- ---------------------------------------------------------------------
-- NÚCLEO — 3FN; domínios primeiro, depois as tabelas que os referenciam
-- ---------------------------------------------------------------------

CREATE TABLE nucleo.dom_sexo (
    codigo SMALLINT NOT NULL COMMENT 'Código do LEDI ou da fonte, nunca a posição na ficha',
    descricao VARCHAR(200) NOT NULL COMMENT 'Rótulo',
    CONSTRAINT pk_dom_sexo PRIMARY KEY (codigo)
) ENGINE=InnoDB COMMENT='Sexo do cidadão (0, 1, 4, 5). Origem: LEDI · Sexo';

CREATE TABLE nucleo.dom_raca_cor (
    codigo SMALLINT NOT NULL COMMENT 'Código do LEDI ou da fonte, nunca a posição na ficha',
    descricao VARCHAR(200) NOT NULL COMMENT 'Rótulo',
    CONSTRAINT pk_dom_raca_cor PRIMARY KEY (codigo)
) ENGINE=InnoDB COMMENT='Raça/cor (1, 2, 3, 4, 5). Origem: LEDI · RacaCor';

CREATE TABLE nucleo.dom_etnia (
    codigo SMALLINT NOT NULL COMMENT 'Código do LEDI ou da fonte, nunca a posição na ficha',
    descricao VARCHAR(200) NOT NULL COMMENT 'Rótulo',
    CONSTRAINT pk_dom_etnia PRIMARY KEY (codigo)
) ENGINE=InnoDB COMMENT='Etnias indígenas (406 valores). Origem: LEDI · etnia';

CREATE TABLE nucleo.dom_orientacao_sexual (
    codigo SMALLINT NOT NULL COMMENT 'Código do LEDI ou da fonte, nunca a posição na ficha',
    descricao VARCHAR(200) NOT NULL COMMENT 'Rótulo',
    CONSTRAINT pk_dom_orientacao_sexual PRIMARY KEY (codigo)
) ENGINE=InnoDB COMMENT='Orientação sexual. Origem: LEDI · OrientacaoSexual';

CREATE TABLE nucleo.dom_identidade_genero (
    codigo SMALLINT NOT NULL COMMENT 'Código do LEDI ou da fonte, nunca a posição na ficha',
    descricao VARCHAR(200) NOT NULL COMMENT 'Rótulo',
    CONSTRAINT pk_dom_identidade_genero PRIMARY KEY (codigo)
) ENGINE=InnoDB COMMENT='Identidade de gênero. Origem: LEDI · identidadeGeneroCidadao';

CREATE TABLE nucleo.dom_tipo_deficiencia (
    codigo SMALLINT NOT NULL COMMENT 'Código do LEDI ou da fonte, nunca a posição na ficha',
    descricao VARCHAR(200) NOT NULL COMMENT 'Rótulo',
    CONSTRAINT pk_dom_tipo_deficiencia PRIMARY KEY (codigo)
) ENGINE=InnoDB COMMENT='Tipos de deficiência, com TEA (232). Origem: LEDI · DeficienciaCidadao (entidade TIPO_DEFICIENCIA)';

CREATE TABLE nucleo.dom_escolaridade (
    codigo SMALLINT NOT NULL COMMENT 'Código do LEDI ou da fonte, nunca a posição na ficha',
    descricao VARCHAR(200) NOT NULL COMMENT 'Rótulo',
    CONSTRAINT pk_dom_escolaridade PRIMARY KEY (codigo)
) ENGINE=InnoDB COMMENT='Curso mais elevado. Origem: LEDI · CursoMaisElevado';

CREATE TABLE nucleo.dom_situacao_trabalho (
    codigo SMALLINT NOT NULL COMMENT 'Código do LEDI ou da fonte, nunca a posição na ficha',
    descricao VARCHAR(200) NOT NULL COMMENT 'Rótulo',
    CONSTRAINT pk_dom_situacao_trabalho PRIMARY KEY (codigo)
) ENGINE=InnoDB COMMENT='Situação no mercado de trabalho. Origem: LEDI · SituacaoMercadoTrabalho';

CREATE TABLE nucleo.dom_motivo_saida (
    codigo SMALLINT NOT NULL COMMENT 'Código do LEDI ou da fonte, nunca a posição na ficha',
    descricao VARCHAR(200) NOT NULL COMMENT 'Rótulo',
    CONSTRAINT pk_dom_motivo_saida PRIMARY KEY (codigo)
) ENGINE=InnoDB COMMENT='Motivo de saída (135 óbito, 136 mudança). Origem: LEDI · MotivoSaida';

CREATE TABLE nucleo.dom_tipo_imovel (
    codigo SMALLINT NOT NULL COMMENT 'Código do LEDI ou da fonte, nunca a posição na ficha',
    descricao VARCHAR(200) NOT NULL COMMENT 'Rótulo',
    CONSTRAINT pk_dom_tipo_imovel PRIMARY KEY (codigo)
) ENGINE=InnoDB COMMENT='Tipo de imóvel da FCDT. Origem: LEDI · tipoDeImovel';

CREATE TABLE nucleo.dom_renda_familiar (
    codigo SMALLINT NOT NULL COMMENT 'Código do LEDI ou da fonte, nunca a posição na ficha',
    descricao VARCHAR(200) NOT NULL COMMENT 'Rótulo',
    CONSTRAINT pk_dom_renda_familiar PRIMARY KEY (codigo)
) ENGINE=InnoDB COMMENT='Renda familiar em salários mínimos. Origem: LEDI · RendaFamiliar';

CREATE TABLE nucleo.dom_tipo_atendimento (
    codigo SMALLINT NOT NULL COMMENT 'Código do LEDI ou da fonte, nunca a posição na ficha',
    descricao VARCHAR(200) NOT NULL COMMENT 'Rótulo',
    CONSTRAINT pk_dom_tipo_atendimento PRIMARY KEY (codigo)
) ENGINE=InnoDB COMMENT='Tipo de atendimento (todos os códigos do LEDI). Origem: LEDI · TipoDeAtendimento';

CREATE TABLE nucleo.dom_local_atendimento (
    codigo SMALLINT NOT NULL COMMENT 'Código do LEDI ou da fonte, nunca a posição na ficha',
    descricao VARCHAR(200) NOT NULL COMMENT 'Rótulo',
    CONSTRAINT pk_dom_local_atendimento PRIMARY KEY (codigo)
) ENGINE=InnoDB COMMENT='Local de atendimento. Origem: LEDI · LocalDeAtendimento';

CREATE TABLE nucleo.dom_turno (
    codigo SMALLINT NOT NULL COMMENT 'Código do LEDI ou da fonte, nunca a posição na ficha',
    descricao VARCHAR(200) NOT NULL COMMENT 'Rótulo',
    CONSTRAINT pk_dom_turno PRIMARY KEY (codigo)
) ENGINE=InnoDB COMMENT='Turno do atendimento. Origem: LEDI · Turno';

CREATE TABLE nucleo.dom_ciap (
    codigo VARCHAR(6) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'Código do LEDI ou da fonte, nunca a posição na ficha',
    descricao VARCHAR(200) NOT NULL COMMENT 'Rótulo',
    tipo CHAR(5) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'CIAP2 ou AB',
    pre_natal BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Código de pré-natal (regra de idade ≥ 9 anos)',
    procedimento BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Componente de procedimento, proibido no campo ciap',
    CONSTRAINT pk_dom_ciap PRIMARY KEY (codigo),
    CONSTRAINT ck_dom_ciap_tipo CHECK (tipo IN ('CIAP2','AB'))
) ENGINE=InnoDB COMMENT='CIAP2 e os cinco Códigos AB aceitos no campo ciap. Origem: CIAP2 + LEDI · ListaCiapCondicaoAvaliada (entidade CODIGO_CLINICO)';

CREATE TABLE nucleo.dom_cid10 (
    codigo VARCHAR(4) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'Código do LEDI ou da fonte, nunca a posição na ficha',
    descricao VARCHAR(200) NOT NULL COMMENT 'Rótulo',
    CONSTRAINT pk_dom_cid10 PRIMARY KEY (codigo)
) ENGINE=InnoDB COMMENT='CID-10 sem ponto (ex.: Z340). Origem: CID-10 (entidade CODIGO_CLINICO)';

CREATE TABLE nucleo.dom_cbo (
    codigo CHAR(6) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'Código do LEDI ou da fonte, nunca a posição na ficha',
    descricao VARCHAR(200) NOT NULL COMMENT 'Rótulo',
    CONSTRAINT pk_dom_cbo PRIMARY KEY (codigo)
) ENGINE=InnoDB COMMENT='Ocupações. Origem: CBO 2002 (LEDI, anexos)';

CREATE TABLE nucleo.dom_tipo_unidade (
    codigo SMALLINT NOT NULL COMMENT 'Código do LEDI ou da fonte, nunca a posição na ficha',
    descricao VARCHAR(200) NOT NULL COMMENT 'Rótulo',
    CONSTRAINT pk_dom_tipo_unidade PRIMARY KEY (codigo)
) ENGINE=InnoDB COMMENT='Tipo de unidade (USF, eCR, CAI…). Origem: CNES · tipo de estabelecimento';

CREATE TABLE nucleo.dom_tipo_equipe (
    codigo SMALLINT NOT NULL COMMENT 'Código do LEDI ou da fonte, nunca a posição na ficha',
    descricao VARCHAR(200) NOT NULL COMMENT 'Rótulo',
    CONSTRAINT pk_dom_tipo_equipe PRIMARY KEY (codigo)
) ENGINE=InnoDB COMMENT='Tipo de equipe (eSF, eAP, eCR…). Origem: CNES · tipo de equipe';

CREATE TABLE nucleo.dom_tipo_acao (
    codigo SMALLINT NOT NULL COMMENT 'Código do LEDI ou da fonte, nunca a posição na ficha',
    descricao VARCHAR(200) NOT NULL COMMENT 'Rótulo',
    CONSTRAINT pk_dom_tipo_acao PRIMARY KEY (codigo)
) ENGINE=InnoDB COMMENT='Tipo de ação formativa (oficina, material…). Origem: Projeto';

CREATE TABLE nucleo.dom_tipo_defeito (
    codigo SMALLINT NOT NULL COMMENT 'Código do LEDI ou da fonte, nunca a posição na ficha',
    descricao VARCHAR(200) NOT NULL COMMENT 'Rótulo',
    CONSTRAINT pk_dom_tipo_defeito PRIMARY KEY (codigo)
) ENGINE=InnoDB COMMENT='Tipos de defeito injetado. Origem: Projeto (Etapa 7)';

CREATE TABLE nucleo.dom_cbo_ficha (
    cbo CHAR(6) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    ficha CHAR(4) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'FCI, FCDT ou FAI',
    CONSTRAINT pk_dom_cbo_ficha PRIMARY KEY (cbo, ficha),
    CONSTRAINT fk_dom_cbo_ficha_cbo FOREIGN KEY (cbo) REFERENCES nucleo.dom_cbo (codigo),
    CONSTRAINT ck_cbo_ficha CHECK (ficha IN ('FCI','FCDT','FAI'))
) ENGINE=InnoDB COMMENT='CBO que pode registrar cada modelo de informação. Origem: LEDI · Grupos de CBO por modelo de informação';

CREATE TABLE nucleo.distrito_sanitario (
    id_ds SMALLINT NOT NULL COMMENT 'DISTRITO_SANITARIO.id_ds',
    nome_ds VARCHAR(10) NOT NULL COMMENT 'DS I a DS VIII',
    CONSTRAINT pk_distrito_sanitario PRIMARY KEY (id_ds),
    CONSTRAINT uq_distrito_sanitario_nome_ds UNIQUE (nome_ds),
    CONSTRAINT ck_ds_faixa CHECK (id_ds BETWEEN 1 AND 8)
) ENGINE=InnoDB COMMENT='Distritos Sanitários I a VIII. Origem: Prefeitura do Recife';

CREATE TABLE nucleo.bairro (
    id_bairro SMALLINT NOT NULL COMMENT 'Código do bairro na malha da Prefeitura',
    nome_bairro VARCHAR(72) NOT NULL COMMENT 'UNIDADE_SAUDE.bairro, DOMICILIO.bairro',
    id_ds SMALLINT NOT NULL,
    CONSTRAINT pk_bairro PRIMARY KEY (id_bairro),
    CONSTRAINT uq_bairro_nome_bairro UNIQUE (nome_bairro),
    CONSTRAINT fk_bairro_id_ds FOREIGN KEY (id_ds) REFERENCES nucleo.distrito_sanitario (id_ds)
) ENGINE=InnoDB COMMENT='Bairros oficiais do Recife e o distrito a que pertencem. Origem: Prefeitura do Recife (malhas territoriais) — tabela nova, 3FN';

CREATE TABLE nucleo.setor_censitario (
    cd_setor CHAR(15) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'DOMICILIO.setor_censitario',
    id_bairro SMALLINT NOT NULL,
    CONSTRAINT pk_setor_censitario PRIMARY KEY (cd_setor),
    CONSTRAINT fk_setor_censitario_id_bairro FOREIGN KEY (id_bairro) REFERENCES nucleo.bairro (id_bairro),
    CONSTRAINT ck_setor_recife CHECK (cd_setor LIKE '2611606%')
) ENGINE=InnoDB COMMENT='Setores censitários do Censo 2022 no Recife. Origem: IBGE, malha de setores 2022 — tabela nova, 3FN';

CREATE TABLE nucleo.unidade_saude (
    cnes CHAR(7) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'UNIDADE_SAUDE.cnes',
    nome_unidade VARCHAR(100) NOT NULL COMMENT 'UNIDADE_SAUDE.nome_unidade',
    tipo_unidade SMALLINT NOT NULL COMMENT 'UNIDADE_SAUDE.tipo_unidade',
    id_bairro SMALLINT NOT NULL COMMENT 'O distrito vem pelo bairro',
    CONSTRAINT pk_unidade_saude PRIMARY KEY (cnes),
    CONSTRAINT fk_unidade_saude_tipo_unidade FOREIGN KEY (tipo_unidade) REFERENCES nucleo.dom_tipo_unidade (codigo),
    CONSTRAINT fk_unidade_saude_id_bairro FOREIGN KEY (id_bairro) REFERENCES nucleo.bairro (id_bairro),
    CONSTRAINT ck_cnes_formato CHECK (cnes REGEXP '^[0-9]{7}$')
) ENGINE=InnoDB COMMENT='Estabelecimentos do CNES (USF, eCR, CAI…). Origem: CNES';

CREATE TABLE nucleo.equipe (
    ine CHAR(10) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'EQUIPE.ine',
    nome_equipe VARCHAR(60) NOT NULL COMMENT 'EQUIPE.nome_equipe',
    tipo_equipe SMALLINT NOT NULL COMMENT 'EQUIPE.tipo_equipe',
    cnes CHAR(7) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'abriga (1,1)',
    CONSTRAINT pk_equipe PRIMARY KEY (ine),
    CONSTRAINT fk_equipe_tipo_equipe FOREIGN KEY (tipo_equipe) REFERENCES nucleo.dom_tipo_equipe (codigo),
    CONSTRAINT fk_equipe_cnes FOREIGN KEY (cnes) REFERENCES nucleo.unidade_saude (cnes),
    CONSTRAINT ck_ine_formato CHECK (ine REGEXP '^[0-9]{10}$')
) ENGINE=InnoDB COMMENT='Equipes identificadas pelo INE. Origem: CNES';

CREATE TABLE nucleo.microarea (
    id_microarea INT NOT NULL COMMENT 'MICROAREA.id_microarea',
    ine CHAR(10) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'abrange (1,1)',
    codigo_microarea CHAR(2) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'MICROAREA.codigo_microarea',
    CONSTRAINT pk_microarea PRIMARY KEY (id_microarea),
    CONSTRAINT uq_microarea_equipe UNIQUE (ine, codigo_microarea),
    CONSTRAINT fk_microarea_ine FOREIGN KEY (ine) REFERENCES nucleo.equipe (ine),
    CONSTRAINT ck_microarea_codigo CHECK (codigo_microarea REGEXP '^[0-9]{2}$' AND codigo_microarea <> '00')
) ENGINE=InnoDB COMMENT='Microáreas de cada equipe. Origem: FCI/FCDT';

CREATE TABLE nucleo.profissional (
    cns_profissional CHAR(15) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'PROFISSIONAL.cns_profissional',
    nome_profissional VARCHAR(70) NOT NULL COMMENT 'Gerado pelo Faker',
    CONSTRAINT pk_profissional PRIMARY KEY (cns_profissional),
    CONSTRAINT ck_prof_cns CHECK (cns_profissional REGEXP '^[0-9]{15}$')
) ENGINE=InnoDB COMMENT='Profissional fictício. Origem: headerTransport.profissionalCNS';

CREATE TABLE nucleo.lotacao (
    cns_profissional CHAR(15) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'lota',
    ine CHAR(10) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'lota',
    cbo CHAR(6) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'PROFISSIONAL.cbo → headerTransport.cboCodigo_2002',
    CONSTRAINT pk_lotacao PRIMARY KEY (cns_profissional, ine),
    CONSTRAINT fk_lotacao_cns_profissional FOREIGN KEY (cns_profissional) REFERENCES nucleo.profissional (cns_profissional),
    CONSTRAINT fk_lotacao_ine FOREIGN KEY (ine) REFERENCES nucleo.equipe (ine),
    CONSTRAINT fk_lotacao_cbo FOREIGN KEY (cbo) REFERENCES nucleo.dom_cbo (codigo)
) ENGINE=InnoDB COMMENT='Lotação do profissional numa equipe, com a CBO exercida (relacionamento lota, agora N:N). Origem: headerTransport (profissionalCNS, cboCodigo_2002, cnes, ine)';

CREATE TABLE nucleo.acao_formativa (
    id_acao INT NOT NULL COMMENT 'ACAO_FORMATIVA.id_acao',
    ine CHAR(10) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'recebe (1,1)',
    dt_acao DATE NOT NULL COMMENT 'ACAO_FORMATIVA.dt_acao',
    tipo_acao SMALLINT NOT NULL COMMENT 'ACAO_FORMATIVA.tipo_acao',
    tema VARCHAR(100) COMMENT 'ACAO_FORMATIVA.tema',
    CONSTRAINT pk_acao_formativa PRIMARY KEY (id_acao),
    CONSTRAINT fk_acao_formativa_ine FOREIGN KEY (ine) REFERENCES nucleo.equipe (ine),
    CONSTRAINT fk_acao_formativa_tipo_acao FOREIGN KEY (tipo_acao) REFERENCES nucleo.dom_tipo_acao (codigo)
) ENGINE=InnoDB COMMENT='Oficina ou material recebido por uma equipe. Origem: Projeto';

CREATE TABLE nucleo.domicilio (
    id_domicilio INT NOT NULL COMMENT 'DOMICILIO.id_domicilio',
    uuid_ficha VARCHAR(44) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'DOMICILIO.uuid_ficha',
    tipo_imovel SMALLINT NOT NULL COMMENT 'DOMICILIO.tipo_imovel',
    cd_setor CHAR(15) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'Bairro e distrito vêm pelo setor',
    id_microarea INT COMMENT 'localiza (0,1)',
    fora_area BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'DOMICILIO.fora_area',
    ativo BOOLEAN NOT NULL DEFAULT TRUE COMMENT 'DOMICILIO.ativo',
    CONSTRAINT pk_domicilio PRIMARY KEY (id_domicilio),
    CONSTRAINT uq_domicilio_uuid_ficha UNIQUE (uuid_ficha),
    CONSTRAINT fk_domicilio_tipo_imovel FOREIGN KEY (tipo_imovel) REFERENCES nucleo.dom_tipo_imovel (codigo),
    CONSTRAINT fk_domicilio_cd_setor FOREIGN KEY (cd_setor) REFERENCES nucleo.setor_censitario (cd_setor),
    CONSTRAINT fk_domicilio_id_microarea FOREIGN KEY (id_microarea) REFERENCES nucleo.microarea (id_microarea),
    CONSTRAINT ck_dom_fora_area CHECK ((fora_area AND id_microarea IS NULL) OR (NOT fora_area AND id_microarea IS NOT NULL))
) ENGINE=InnoDB COMMENT='Imóvel cadastrado na FCDT (estado mais recente). Origem: FCDT';

CREATE TABLE nucleo.familia (
    id_familia INT NOT NULL COMMENT 'FAMILIA.id_familia',
    id_domicilio INT NOT NULL COMMENT 'reside em (1,1)',
    renda_familiar SMALLINT COMMENT 'FAMILIA.renda_familiar',
    num_membros SMALLINT COMMENT 'FAMILIA.num_membros',
    reside_desde DATE COMMENT 'FAMILIA.reside_desde',
    mudou_se BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'FAMILIA.mudou_se',
    CONSTRAINT pk_familia PRIMARY KEY (id_familia),
    CONSTRAINT fk_familia_id_domicilio FOREIGN KEY (id_domicilio) REFERENCES nucleo.domicilio (id_domicilio),
    CONSTRAINT fk_familia_renda_familiar FOREIGN KEY (renda_familiar) REFERENCES nucleo.dom_renda_familiar (codigo),
    CONSTRAINT ck_fam_membros CHECK (num_membros IS NULL OR num_membros BETWEEN 1 AND 999)
) ENGINE=InnoDB COMMENT='Família de um domicílio. Origem: FCDT · FamiliaRow';

CREATE TABLE nucleo.cidadao (
    id_cidadao BIGINT NOT NULL COMMENT 'CIDADAO.id_cidadao',
    cpf CHAR(11) CHARACTER SET ascii COLLATE ascii_bin COMMENT 'CIDADAO.cpf',
    cns CHAR(15) CHARACTER SET ascii COLLATE ascii_bin COMMENT 'CIDADAO.cns',
    nome VARCHAR(70) NOT NULL COMMENT 'Sintético; nunca entra em análise',
    dt_nascimento DATE NOT NULL COMMENT 'CIDADAO.dt_nascimento',
    sexo SMALLINT NOT NULL COMMENT 'CIDADAO.sexo',
    id_familia INT COMMENT 'compõe (0,1)',
    CONSTRAINT pk_cidadao PRIMARY KEY (id_cidadao),
    CONSTRAINT uq_cidadao_cpf UNIQUE (cpf),
    CONSTRAINT uq_cidadao_cns UNIQUE (cns),
    CONSTRAINT fk_cidadao_sexo FOREIGN KEY (sexo) REFERENCES nucleo.dom_sexo (codigo),
    CONSTRAINT fk_cidadao_id_familia FOREIGN KEY (id_familia) REFERENCES nucleo.familia (id_familia),
    CONSTRAINT ck_cid_ident CHECK (cpf IS NOT NULL OR cns IS NOT NULL),
    CONSTRAINT ck_cid_cpf CHECK (cpf IS NULL OR cpf REGEXP '^[0-9]{11}$'),
    CONSTRAINT ck_cid_cns CHECK (cns IS NULL OR cns REGEXP '^[0-9]{15}$')
) ENGINE=InnoDB COMMENT='Pessoa sintética: só atributos estáveis. Origem: FCI · IdentificacaoUsuarioCidadao';

CREATE TABLE nucleo.cadastro_individual (
    uuid VARCHAR(44) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'CADASTRO_INDIVIDUAL.uuid',
    id_cidadao BIGINT NOT NULL COMMENT 'possui (1,1)',
    uuid_originadora VARCHAR(44) CHARACTER SET ascii COLLATE ascii_bin COMMENT 'Nula na primeira versão',
    cns_profissional CHAR(15) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'FK composta para lotacao',
    ine CHAR(10) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'FK composta para lotacao e microarea',
    dt_cadastro DATE NOT NULL COMMENT 'CADASTRO_INDIVIDUAL.dt_cadastro',
    dt_digitacao DATE NOT NULL COMMENT 'CADASTRO_INDIVIDUAL.dt_digitacao',
    ficha_atualizada BOOLEAN NOT NULL COMMENT 'CADASTRO_INDIVIDUAL.ficha_atualizada',
    recusa_cadastro BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'CADASTRO_INDIVIDUAL.recusa_cadastro',
    responsavel_familiar BOOLEAN COMMENT 'CADASTRO_INDIVIDUAL.responsavel_familiar',
    microarea CHAR(2) CHARACTER SET ascii COLLATE ascii_bin COMMENT 'CADASTRO_INDIVIDUAL.microarea',
    fora_area BOOLEAN COMMENT 'CADASTRO_INDIVIDUAL.fora_area',
    raca_cor SMALLINT COMMENT 'Nula só em cadastro legado (regra de qualidade)',
    etnia SMALLINT COMMENT 'CADASTRO_INDIVIDUAL.etnia',
    nome_social VARCHAR(70) COMMENT 'CADASTRO_INDIVIDUAL.nome_social',
    deseja_informar_os BOOLEAN COMMENT 'Nulo = não informado',
    orientacao_sexual SMALLINT COMMENT 'CADASTRO_INDIVIDUAL.orientacao_sexual',
    deseja_informar_ig BOOLEAN COMMENT 'Nulo = não informado',
    identidade_genero SMALLINT COMMENT 'CADASTRO_INDIVIDUAL.identidade_genero',
    tem_deficiencia BOOLEAN COMMENT 'Nulo = falha de registro',
    escolaridade SMALLINT COMMENT 'CADASTRO_INDIVIDUAL.escolaridade',
    situacao_trabalho SMALLINT COMMENT 'CADASTRO_INDIVIDUAL.situacao_trabalho',
    motivo_saida SMALLINT COMMENT 'CADASTRO_INDIVIDUAL.motivo_saida',
    dt_obito DATE COMMENT 'CADASTRO_INDIVIDUAL.dt_obito',
    CONSTRAINT pk_cadastro_individual PRIMARY KEY (uuid),
    CONSTRAINT uq_ci_uuid_cidadao UNIQUE (uuid, id_cidadao),
    CONSTRAINT fk_cadastro_individual_id_cidadao FOREIGN KEY (id_cidadao) REFERENCES nucleo.cidadao (id_cidadao),
    CONSTRAINT fk_cadastro_individual_raca_cor FOREIGN KEY (raca_cor) REFERENCES nucleo.dom_raca_cor (codigo),
    CONSTRAINT fk_cadastro_individual_etnia FOREIGN KEY (etnia) REFERENCES nucleo.dom_etnia (codigo),
    CONSTRAINT fk_cadastro_individual_orientacao_sexual FOREIGN KEY (orientacao_sexual) REFERENCES nucleo.dom_orientacao_sexual (codigo),
    CONSTRAINT fk_cadastro_individual_identidade_genero FOREIGN KEY (identidade_genero) REFERENCES nucleo.dom_identidade_genero (codigo),
    CONSTRAINT fk_cadastro_individual_escolaridade FOREIGN KEY (escolaridade) REFERENCES nucleo.dom_escolaridade (codigo),
    CONSTRAINT fk_cadastro_individual_situacao_trabalho FOREIGN KEY (situacao_trabalho) REFERENCES nucleo.dom_situacao_trabalho (codigo),
    CONSTRAINT fk_cadastro_individual_motivo_saida FOREIGN KEY (motivo_saida) REFERENCES nucleo.dom_motivo_saida (codigo),
    CONSTRAINT fk_ci_originadora FOREIGN KEY (uuid_originadora, id_cidadao) REFERENCES nucleo.cadastro_individual (uuid, id_cidadao),
    CONSTRAINT fk_ci_lotacao FOREIGN KEY (cns_profissional, ine) REFERENCES nucleo.lotacao (cns_profissional, ine),
    CONSTRAINT fk_ci_microarea FOREIGN KEY (ine, microarea) REFERENCES nucleo.microarea (ine, codigo_microarea),
    CONSTRAINT ck_ci_cadeia CHECK ((ficha_atualizada AND uuid_originadora IS NOT NULL AND uuid_originadora <> uuid) OR (NOT ficha_atualizada AND uuid_originadora IS NULL)),
    CONSTRAINT ck_ci_digitacao CHECK (dt_digitacao >= dt_cadastro),
    CONSTRAINT ck_ci_fora_area CHECK (fora_area IS NOT TRUE OR microarea IS NULL),
    CONSTRAINT ck_ci_os CHECK ((deseja_informar_os IS TRUE AND orientacao_sexual IS NOT NULL) OR (deseja_informar_os IS NOT TRUE AND orientacao_sexual IS NULL)),
    CONSTRAINT ck_ci_ig CHECK ((deseja_informar_ig IS TRUE AND identidade_genero IS NOT NULL) OR (deseja_informar_ig IS NOT TRUE AND identidade_genero IS NULL)),
    CONSTRAINT ck_ci_etnia CHECK ((COALESCE(raca_cor, 0) = 5 AND etnia IS NOT NULL) OR (COALESCE(raca_cor, 0) <> 5 AND etnia IS NULL)),
    CONSTRAINT ck_ci_obito CHECK ((COALESCE(motivo_saida, 0) = 135 AND dt_obito IS NOT NULL AND dt_obito <= dt_cadastro) OR (COALESCE(motivo_saida, 0) <> 135 AND dt_obito IS NULL)),
    CONSTRAINT ck_ci_recusa CHECK (NOT recusa_cadastro OR (deseja_informar_os IS NULL AND orientacao_sexual IS NULL AND deseja_informar_ig IS NULL AND identidade_genero IS NULL AND tem_deficiencia IS NULL AND escolaridade IS NULL AND situacao_trabalho IS NULL AND motivo_saida IS NULL AND dt_obito IS NULL))
) ENGINE=InnoDB COMMENT='Uma versão da FCI; guarda os atributos autodeclarados. Origem: FCI · CadastroIndividual';

CREATE TABLE nucleo.cadastro_deficiencia (
    uuid VARCHAR(44) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'declara',
    codigo_deficiencia SMALLINT NOT NULL COMMENT 'declara',
    CONSTRAINT pk_cadastro_deficiencia PRIMARY KEY (uuid, codigo_deficiencia),
    CONSTRAINT fk_cadastro_deficiencia_uuid FOREIGN KEY (uuid) REFERENCES nucleo.cadastro_individual (uuid),
    CONSTRAINT fk_cadastro_deficiencia_codigo_deficiencia FOREIGN KEY (codigo_deficiencia) REFERENCES nucleo.dom_tipo_deficiencia (codigo)
) ENGINE=InnoDB COMMENT='Tipos de deficiência declarados numa versão (relacionamento declara, N:N). Origem: FCI · deficienciasCidadao';

CREATE TABLE nucleo.ficha_atendimento (
    uuid_ficha VARCHAR(44) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'ATENDIMENTO_INDIVIDUAL.uuid_ficha',
    cns_profissional CHAR(15) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'FK composta para lotacao',
    ine CHAR(10) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'FK composta para lotacao',
    dt_atendimento DATE NOT NULL COMMENT 'ATENDIMENTO_INDIVIDUAL.dt_atendimento',
    dt_digitacao DATE NOT NULL COMMENT 'ATENDIMENTO_INDIVIDUAL.dt_digitacao',
    CONSTRAINT pk_ficha_atendimento PRIMARY KEY (uuid_ficha),
    CONSTRAINT fk_fa_lotacao FOREIGN KEY (cns_profissional, ine) REFERENCES nucleo.lotacao (cns_profissional, ine),
    CONSTRAINT ck_fa_digitacao CHECK (dt_digitacao >= dt_atendimento)
) ENGINE=InnoDB COMMENT='Ficha da FAI (lote de até 99 atendimentos): profissional, equipe e datas comuns. Origem: FAI · FichaAtendimentoIndividualMaster + VariasLotacoesHeader';

CREATE TABLE nucleo.atendimento_individual (
    id_atendimento BIGINT NOT NULL COMMENT 'ATENDIMENTO_INDIVIDUAL.id_atendimento',
    uuid_ficha VARCHAR(44) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    nu_atendimento SMALLINT NOT NULL COMMENT 'Ordem do atendimento na ficha (DW: nu_atendimento)',
    id_cidadao BIGINT NOT NULL COMMENT 'é atendido em (1,1)',
    dt_hora_inicio DATETIME NOT NULL COMMENT 'ATENDIMENTO_INDIVIDUAL.dt_hora_inicio',
    tipo_atendimento SMALLINT NOT NULL COMMENT 'ATENDIMENTO_INDIVIDUAL.tipo_atendimento',
    local_atendimento SMALLINT NOT NULL COMMENT 'ATENDIMENTO_INDIVIDUAL.local_atendimento',
    turno SMALLINT NOT NULL COMMENT 'ATENDIMENTO_INDIVIDUAL.turno',
    CONSTRAINT pk_atendimento_individual PRIMARY KEY (id_atendimento),
    CONSTRAINT uq_ai_ficha_ordem UNIQUE (uuid_ficha, nu_atendimento),
    CONSTRAINT fk_atendimento_individual_uuid_ficha FOREIGN KEY (uuid_ficha) REFERENCES nucleo.ficha_atendimento (uuid_ficha),
    CONSTRAINT fk_atendimento_individual_id_cidadao FOREIGN KEY (id_cidadao) REFERENCES nucleo.cidadao (id_cidadao),
    CONSTRAINT fk_atendimento_individual_tipo_atendimento FOREIGN KEY (tipo_atendimento) REFERENCES nucleo.dom_tipo_atendimento (codigo),
    CONSTRAINT fk_atendimento_individual_local_atendimento FOREIGN KEY (local_atendimento) REFERENCES nucleo.dom_local_atendimento (codigo),
    CONSTRAINT fk_atendimento_individual_turno FOREIGN KEY (turno) REFERENCES nucleo.dom_turno (codigo),
    CONSTRAINT ck_ai_ordem CHECK (nu_atendimento BETWEEN 1 AND 99),
    CONSTRAINT ck_ai_tipo CHECK (tipo_atendimento IN (1, 2, 4, 5, 6)),
    CONSTRAINT ck_ai_local CHECK (local_atendimento BETWEEN 1 AND 10)
) ENGINE=InnoDB COMMENT='Um atendimento da FAI. Origem: FAI · FichaAtendimentoIndividualChild';

CREATE TABLE nucleo.atendimento_problema (
    id_atendimento BIGINT NOT NULL COMMENT 'avalia',
    nu_item SMALLINT NOT NULL COMMENT 'Ordem do item no atendimento',
    ciap VARCHAR(6) CHARACTER SET ascii COLLATE ascii_bin COMMENT 'ProblemaCondicao.ciap',
    cid10 VARCHAR(4) CHARACTER SET ascii COLLATE ascii_bin COMMENT 'ProblemaCondicao.cid10',
    CONSTRAINT pk_atendimento_problema PRIMARY KEY (id_atendimento, nu_item),
    CONSTRAINT uq_ap_ciap UNIQUE (id_atendimento, ciap),
    CONSTRAINT uq_ap_cid10 UNIQUE (id_atendimento, cid10),
    CONSTRAINT fk_atendimento_problema_id_atendimento FOREIGN KEY (id_atendimento) REFERENCES nucleo.atendimento_individual (id_atendimento),
    CONSTRAINT fk_atendimento_problema_ciap FOREIGN KEY (ciap) REFERENCES nucleo.dom_ciap (codigo),
    CONSTRAINT fk_atendimento_problema_cid10 FOREIGN KEY (cid10) REFERENCES nucleo.dom_cid10 (codigo),
    CONSTRAINT ck_ap_codigo CHECK (ciap IS NOT NULL OR cid10 IS NOT NULL),
    CONSTRAINT ck_ap_w78 CHECK (COALESCE(ciap, '') <> 'W78' OR cid10 IS NULL OR cid10 LIKE 'Z34%')
) ENGINE=InnoDB COMMENT='Problema ou condição avaliada (relacionamento avalia): CIAP2 e/ou CID-10 no mesmo item. Origem: FAI · ProblemaCondicao';

CREATE TABLE nucleo.parametro (
    id_carga INT NOT NULL COMMENT 'PARAMETRO.id_carga',
    data_corte DATE NOT NULL COMMENT 'PARAMETRO.data_corte',
    idade_min_elegivel SMALLINT NOT NULL DEFAULT 11 COMMENT 'PARAMETRO.idade_min_elegivel',
    recusa_conta_ativo BOOLEAN NOT NULL DEFAULT TRUE COMMENT 'Pendência P1: termo de recusa entra em “ativos”?',
    meses_desatualizado SMALLINT NOT NULL DEFAULT 24 COMMENT 'Limite da regra de qualidade RQ06',
    semente INT NOT NULL COMMENT 'PARAMETRO.semente',
    fator_escala DECIMAL(5,4) NOT NULL COMMENT 'PARAMETRO.fator_escala',
    versao_gerador VARCHAR(20) NOT NULL COMMENT 'PARAMETRO.versao_gerador',
    dt_geracao DATETIME NOT NULL COMMENT 'Momento da geração',
    CONSTRAINT pk_parametro PRIMARY KEY (id_carga),
    CONSTRAINT ck_par_idade CHECK (idade_min_elegivel BETWEEN 0 AND 17),
    CONSTRAINT ck_par_escala CHECK (fator_escala > 0 AND fator_escala <= 1),
    CONSTRAINT ck_par_meses CHECK (meses_desatualizado > 0)
) ENGINE=InnoDB COMMENT='Parâmetros de cada carga; fonte da regra do “dado real”. Origem: Projeto';

CREATE TABLE nucleo.controle_defeito (
    id_defeito INT NOT NULL COMMENT 'CONTROLE_DEFEITO.id_defeito',
    tabela VARCHAR(40) NOT NULL COMMENT 'CONTROLE_DEFEITO.tabela',
    id_registro VARCHAR(44) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'CONTROLE_DEFEITO.id_registro',
    tipo_defeito SMALLINT NOT NULL COMMENT 'CONTROLE_DEFEITO.tipo_defeito',
    etapa SMALLINT NOT NULL COMMENT 'Etapa do gerador que produziu o defeito (6 ou 7)',
    campo VARCHAR(40) COMMENT 'Coluna afetada',
    id_registro_par VARCHAR(44) CHARACTER SET ascii COLLATE ascii_bin COMMENT 'Par da duplicidade ou versão divergente',
    valor_original VARCHAR(70) COMMENT 'Valor antes da corrupção (verdade conhecida)',
    CONSTRAINT pk_controle_defeito PRIMARY KEY (id_defeito),
    CONSTRAINT fk_controle_defeito_tipo_defeito FOREIGN KEY (tipo_defeito) REFERENCES nucleo.dom_tipo_defeito (codigo),
    CONSTRAINT ck_def_tabela CHECK (tabela IN ('cidadao','cadastro_individual','cadastro_deficiencia','domicilio','familia','ficha_atendimento','atendimento_individual','atendimento_problema')),
    CONSTRAINT ck_def_etapa CHECK (etapa IN (6, 7))
) ENGINE=InnoDB COMMENT='Gabarito dos defeitos injetados (Etapa 7); referência polimórfica, sem FK por desenho. Origem: Projeto (Etapa 7)';

-- ---------------------------------------------------------------------
-- STAGING — dado como chega, sem restrições além da chave técnica
-- ---------------------------------------------------------------------

CREATE TABLE stg.fci (
    id_carga INT NOT NULL COMMENT 'Carga que trouxe a linha',
    nu_linha BIGINT NOT NULL COMMENT 'Linha no arquivo de origem',
    st_processamento CHAR(1) NOT NULL DEFAULT 'P' COMMENT 'P pendente, C carregada, R rejeitada',
    motivo_rejeicao VARCHAR(200) COMMENT 'Restrição violada, se rejeitada',
    profissional_cns VARCHAR(15) COMMENT 'headerTransport.profissionalCNS',
    cbo_codigo_2002 VARCHAR(6) COMMENT 'headerTransport.cboCodigo_2002',
    cnes VARCHAR(7) COMMENT 'headerTransport.cnes',
    ine VARCHAR(10) COMMENT 'headerTransport.ine',
    data_atendimento BIGINT COMMENT 'headerTransport.dataAtendimento (epoch ms)',
    codigo_ibge_municipio VARCHAR(7) COMMENT 'headerTransport.codigoIbgeMunicipio',
    uuid VARCHAR(44) COMMENT 'uuid',
    uuid_ficha_originadora VARCHAR(44) COMMENT 'uuidFichaOriginadora',
    ficha_atualizada BOOLEAN COMMENT 'fichaAtualizada',
    tp_cds_origem INT COMMENT 'tpCdsOrigem',
    status_termo_recusa_cadastro_individual_atencao_basica BOOLEAN COMMENT 'statusTermoRecusa…',
    cpf_cidadao VARCHAR(11) COMMENT 'cpfCidadao',
    cns_cidadao VARCHAR(15) COMMENT 'cnsCidadao',
    st_nao_possui_cpf BOOLEAN COMMENT 'stNaoPossuiCpf',
    justificativa_nao_possui_cpf INT COMMENT 'justificativaNaoPossuiCpf',
    nome_cidadao VARCHAR(70) COMMENT 'nomeCidadao',
    nome_social VARCHAR(70) COMMENT 'nomeSocial',
    data_nascimento_cidadao BIGINT COMMENT 'dataNascimentoCidadao',
    sexo_cidadao INT COMMENT 'sexoCidadao',
    raca_cor_cidadao INT COMMENT 'racaCorCidadao',
    etnia INT COMMENT 'etnia',
    nacionalidade_cidadao INT COMMENT 'nacionalidadeCidadao',
    pais_nascimento INT COMMENT 'paisNascimento',
    codigo_ibge_municipio_nascimento VARCHAR(7) COMMENT 'codigoIbgeMunicipioNascimento',
    nome_mae_cidadao VARCHAR(70) COMMENT 'nomeMaeCidadao',
    desconhece_nome_mae BOOLEAN COMMENT 'desconheceNomeMae',
    nome_pai_cidadao VARCHAR(70) COMMENT 'nomePaiCidadao',
    desconhece_nome_pai BOOLEAN COMMENT 'desconheceNomePai',
    status_eh_responsavel BOOLEAN COMMENT 'statusEhResponsavel',
    cpf_responsavel_familiar VARCHAR(11) COMMENT 'cpfResponsavelFamiliar',
    cns_responsavel_familiar VARCHAR(15) COMMENT 'cnsResponsavelFamiliar',
    microarea VARCHAR(2) COMMENT 'microarea',
    st_fora_area BOOLEAN COMMENT 'stForaArea',
    status_deseja_informar_orientacao_sexual BOOLEAN COMMENT 'statusDesejaInformarOrientacaoSexual',
    orientacao_sexual_cidadao INT COMMENT 'orientacaoSexualCidadao',
    status_deseja_informar_identidade_genero BOOLEAN COMMENT 'statusDesejaInformarIdentidadeGenero',
    identidade_genero_cidadao INT COMMENT 'identidadeGeneroCidadao',
    status_tem_alguma_deficiencia BOOLEAN COMMENT 'statusTemAlgumaDeficiencia',
    deficiencias_cidadao VARCHAR(40) COMMENT 'deficienciasCidadao (lista JSON)',
    grau_instrucao_cidadao INT COMMENT 'grauInstrucaoCidadao',
    situacao_mercado_trabalho_cidadao INT COMMENT 'situacaoMercadoTrabalhoCidadao',
    relacao_parentesco_cidadao INT COMMENT 'relacaoParentescoCidadao',
    status_frequenta_escola BOOLEAN COMMENT 'statusFrequentaEscola',
    status_membro_povo_comunidade_tradicional BOOLEAN COMMENT 'statusMembroPovoComunidadeTradicional',
    co_povo_comunidade_tradicional INT COMMENT 'coPovoComunidadeTradicional',
    motivo_saida_cidadao INT COMMENT 'motivoSaidaCidadao',
    data_obito BIGINT COMMENT 'dataObito',
    numero_do VARCHAR(9) COMMENT 'numeroDO',
    dt_digitacao DATE COMMENT 'projeto (não existe no LEDI)',
    CONSTRAINT pk_fci PRIMARY KEY (id_carga, nu_linha)
) ENGINE=InnoDB COMMENT='FCI como chega (uma linha por ficha). Origem: LEDI · CadastroIndividual (ver dicionário, seção 3)';

CREATE TABLE stg.fcdt (
    id_carga INT NOT NULL COMMENT 'Carga que trouxe a linha',
    nu_linha BIGINT NOT NULL COMMENT 'Linha no arquivo de origem',
    st_processamento CHAR(1) NOT NULL DEFAULT 'P' COMMENT 'P pendente, C carregada, R rejeitada',
    motivo_rejeicao VARCHAR(200) COMMENT 'Restrição violada, se rejeitada',
    profissional_cns VARCHAR(15) COMMENT 'headerTransport.profissionalCNS',
    cbo_codigo_2002 VARCHAR(6) COMMENT 'headerTransport.cboCodigo_2002',
    cnes VARCHAR(7) COMMENT 'headerTransport.cnes',
    ine VARCHAR(10) COMMENT 'headerTransport.ine',
    data_atendimento BIGINT COMMENT 'headerTransport.dataAtendimento (epoch ms)',
    codigo_ibge_municipio VARCHAR(7) COMMENT 'headerTransport.codigoIbgeMunicipio',
    uuid VARCHAR(44) COMMENT 'uuid',
    uuid_ficha_originadora VARCHAR(44) COMMENT 'uuidFichaOriginadora',
    ficha_atualizada BOOLEAN COMMENT 'fichaAtualizada',
    tp_cds_origem INT COMMENT 'tpCdsOrigem',
    status_termo_recusa BOOLEAN COMMENT 'statusTermoRecusa',
    tipo_de_imovel INT COMMENT 'tipoDeImovel',
    tipo_endereco INT COMMENT 'tipoEndereco',
    st_ativo BOOLEAN COMMENT 'stAtivo',
    bairro VARCHAR(72) COMMENT 'enderecoLocalPermanencia.bairro',
    cep VARCHAR(8) COMMENT 'cep',
    codigo_ibge_municipio_endereco VARCHAR(7) COMMENT 'enderecoLocalPermanencia.codigoIbgeMunicipio',
    nome_logradouro VARCHAR(72) COMMENT 'nomeLogradouro',
    numero VARCHAR(10) COMMENT 'numero',
    numero_dne_uf VARCHAR(2) COMMENT 'numeroDneUf',
    tipo_logradouro_numero_dne VARCHAR(5) COMMENT 'tipoLogradouroNumeroDne',
    micro_area VARCHAR(2) COMMENT 'microArea',
    st_fora_area BOOLEAN COMMENT 'stForaArea',
    localizacao INT COMMENT 'condicaoMoradia.localizacao',
    situacao_moradia_posse_terra INT COMMENT 'situacaoMoradiaPosseTerra',
    tipo_domicilio INT COMMENT 'tipoDomicilio',
    cd_setor VARCHAR(15) COMMENT 'projeto (no dado real viria de geocodificação)',
    CONSTRAINT pk_fcdt PRIMARY KEY (id_carga, nu_linha)
) ENGINE=InnoDB COMMENT='FCDT como chega (uma linha por ficha). Origem: LEDI · CadastroDomiciliar (dicionário, seção 4)';

CREATE TABLE stg.fcdt_familia (
    id_carga INT NOT NULL COMMENT 'Carga que trouxe a linha',
    nu_linha BIGINT NOT NULL COMMENT 'Linha no arquivo de origem',
    st_processamento CHAR(1) NOT NULL DEFAULT 'P' COMMENT 'P pendente, C carregada, R rejeitada',
    motivo_rejeicao VARCHAR(200) COMMENT 'Restrição violada, se rejeitada',
    uuid VARCHAR(44) COMMENT 'uuid da FCDT',
    nu_familia INT COMMENT 'ordem na lista familias',
    numero_cns_responsavel VARCHAR(15) COMMENT 'numeroCnsResponsavel',
    cpf_responsavel VARCHAR(11) COMMENT 'cpfResponsavel',
    data_nascimento_responsavel BIGINT COMMENT 'dataNascimentoResponsavel',
    numero_membros_familia INT COMMENT 'numeroMembrosFamilia',
    renda_familiar INT COMMENT 'rendaFamiliar',
    reside_desde BIGINT COMMENT 'resideDesde',
    st_mudanca BOOLEAN COMMENT 'stMudanca',
    CONSTRAINT pk_fcdt_familia PRIMARY KEY (id_carga, nu_linha)
) ENGINE=InnoDB COMMENT='Famílias de cada FCDT (uma linha por FamiliaRow). Origem: LEDI · FamiliaRow';

CREATE TABLE stg.fai (
    id_carga INT NOT NULL COMMENT 'Carga que trouxe a linha',
    nu_linha BIGINT NOT NULL COMMENT 'Linha no arquivo de origem',
    st_processamento CHAR(1) NOT NULL DEFAULT 'P' COMMENT 'P pendente, C carregada, R rejeitada',
    motivo_rejeicao VARCHAR(200) COMMENT 'Restrição violada, se rejeitada',
    uuid_ficha VARCHAR(44) COMMENT 'uuidFicha',
    tp_cds_origem INT COMMENT 'tpCdsOrigem',
    profissional_cns VARCHAR(15) COMMENT 'lotacaoFormPrincipal.profissionalCNS',
    cbo_codigo_2002 VARCHAR(6) COMMENT 'lotacaoFormPrincipal.cboCodigo_2002',
    cnes VARCHAR(7) COMMENT 'lotacaoFormPrincipal.cnes',
    ine VARCHAR(10) COMMENT 'lotacaoFormPrincipal.ine',
    data_atendimento BIGINT COMMENT 'headerTransport.dataAtendimento',
    codigo_ibge_municipio VARCHAR(7) COMMENT 'headerTransport.codigoIbgeMunicipio',
    nu_atendimento INT COMMENT 'posição em atendimentosIndividuais',
    cpf_cidadao VARCHAR(11) COMMENT 'cpfCidadao',
    cns_cidadao VARCHAR(15) COMMENT 'cnsCidadao',
    st_cidadao_nao_possui_cpf BOOLEAN COMMENT 'stCidadaoNaoPossuiCpf',
    justificativa_nao_possui_cpf INT COMMENT 'justificativaNaoPossuiCpf',
    data_nascimento BIGINT COMMENT 'dataNascimento',
    sexo INT COMMENT 'sexo',
    local_de_atendimento INT COMMENT 'localDeAtendimento',
    turno INT COMMENT 'turno',
    tipo_atendimento INT COMMENT 'tipoAtendimento',
    condutas VARCHAR(60) COMMENT 'condutas (lista JSON)',
    data_hora_inicial_atendimento BIGINT COMMENT 'dataHoraInicialAtendimento',
    data_hora_final_atendimento BIGINT COMMENT 'dataHoraFinalAtendimento',
    dt_digitacao DATE COMMENT 'projeto (não existe no LEDI)',
    CONSTRAINT pk_fai PRIMARY KEY (id_carga, nu_linha)
) ENGINE=InnoDB COMMENT='FAI como chega (uma linha por atendimento, com o cabeçalho da ficha repetido). Origem: LEDI · FichaAtendimentoIndividualMaster/Child (dicionário, seção 5)';

CREATE TABLE stg.fai_problema (
    id_carga INT NOT NULL COMMENT 'Carga que trouxe a linha',
    nu_linha BIGINT NOT NULL COMMENT 'Linha no arquivo de origem',
    st_processamento CHAR(1) NOT NULL DEFAULT 'P' COMMENT 'P pendente, C carregada, R rejeitada',
    motivo_rejeicao VARCHAR(200) COMMENT 'Restrição violada, se rejeitada',
    uuid_ficha VARCHAR(44) COMMENT 'uuidFicha',
    nu_atendimento INT COMMENT 'posição do atendimento',
    nu_item INT COMMENT 'posição em problemasCondicoes',
    ciap VARCHAR(6) COMMENT 'ciap',
    cid10 VARCHAR(4) COMMENT 'cid10',
    is_avaliado BOOLEAN COMMENT 'isAvaliado',
    CONSTRAINT pk_fai_problema PRIMARY KEY (id_carga, nu_linha)
) ENGINE=InnoDB COMMENT='Problemas e condições de cada atendimento. Origem: LEDI · ProblemaCondicao';

CREATE TABLE stg.cnes_estabelecimento (
    id_carga INT NOT NULL COMMENT 'Carga que trouxe a linha',
    nu_linha BIGINT NOT NULL COMMENT 'Linha no arquivo de origem',
    st_processamento CHAR(1) NOT NULL DEFAULT 'P' COMMENT 'P pendente, C carregada, R rejeitada',
    motivo_rejeicao VARCHAR(200) COMMENT 'Restrição violada, se rejeitada',
    cnes VARCHAR(7),
    nome_fantasia VARCHAR(100),
    tipo_unidade INT,
    bairro VARCHAR(72),
    CONSTRAINT pk_cnes_estabelecimento PRIMARY KEY (id_carga, nu_linha)
) ENGINE=InnoDB COMMENT='Estabelecimentos do CNES no Recife (Etapa 5). Origem: DATASUS · CNES';

CREATE TABLE stg.cnes_equipe (
    id_carga INT NOT NULL COMMENT 'Carga que trouxe a linha',
    nu_linha BIGINT NOT NULL COMMENT 'Linha no arquivo de origem',
    st_processamento CHAR(1) NOT NULL DEFAULT 'P' COMMENT 'P pendente, C carregada, R rejeitada',
    motivo_rejeicao VARCHAR(200) COMMENT 'Restrição violada, se rejeitada',
    ine VARCHAR(10),
    cnes VARCHAR(7),
    nome_equipe VARCHAR(60),
    tipo_equipe INT,
    CONSTRAINT pk_cnes_equipe PRIMARY KEY (id_carga, nu_linha)
) ENGINE=InnoDB COMMENT='Equipes do CNES no Recife (Etapa 5). Origem: DATASUS · CNES';

CREATE TABLE stg.malha_territorial (
    id_carga INT NOT NULL COMMENT 'Carga que trouxe a linha',
    nu_linha BIGINT NOT NULL COMMENT 'Linha no arquivo de origem',
    st_processamento CHAR(1) NOT NULL DEFAULT 'P' COMMENT 'P pendente, C carregada, R rejeitada',
    motivo_rejeicao VARCHAR(200) COMMENT 'Restrição violada, se rejeitada',
    cd_setor VARCHAR(15),
    nome_bairro VARCHAR(72),
    id_bairro INT,
    nome_ds VARCHAR(10),
    CONSTRAINT pk_malha_territorial PRIMARY KEY (id_carga, nu_linha)
) ENGINE=InnoDB COMMENT='Setor censitário → bairro → distrito (Etapa 5). Origem: IBGE e Prefeitura do Recife';

CREATE TABLE stg.profissional_lotacao (
    id_carga INT NOT NULL COMMENT 'Carga que trouxe a linha',
    nu_linha BIGINT NOT NULL COMMENT 'Linha no arquivo de origem',
    st_processamento CHAR(1) NOT NULL DEFAULT 'P' COMMENT 'P pendente, C carregada, R rejeitada',
    motivo_rejeicao VARCHAR(200) COMMENT 'Restrição violada, se rejeitada',
    cns_profissional VARCHAR(15),
    nome_profissional VARCHAR(70),
    ine VARCHAR(10),
    cbo VARCHAR(6),
    CONSTRAINT pk_profissional_lotacao PRIMARY KEY (id_carga, nu_linha)
) ENGINE=InnoDB COMMENT='Profissionais fictícios e lotações emitidos pelo gerador. Origem: Gerador (Etapa 6)';

-- ---------------------------------------------------------------------
-- ANALÍTICA — tabelas derivadas, reconstruídas a cada carga
-- ---------------------------------------------------------------------

CREATE TABLE analitica.dim_competencia (
    competencia INT NOT NULL COMMENT 'AAAAMM',
    dt_inicio DATE NOT NULL,
    dt_fim DATE NOT NULL,
    ano SMALLINT NOT NULL,
    mes SMALLINT NOT NULL,
    quadrimestre INT NOT NULL COMMENT 'AAAAQ (Q = 1, 2, 3)',
    semestre INT NOT NULL COMMENT 'AAAAS (S = 1, 2)',
    CONSTRAINT pk_dim_competencia PRIMARY KEY (competencia),
    CONSTRAINT ck_comp_mes CHECK (mes BETWEEN 1 AND 12 AND dt_fim >= dt_inicio)
) ENGINE=InnoDB COMMENT='Calendário das competências mensais. Origem: Projeto';

CREATE TABLE analitica.ref_parametro_oficial (
    fonte VARCHAR(30) NOT NULL COMMENT 'Censo 2022, PNS 2019, SISAB…',
    tabela_fonte VARCHAR(30) NOT NULL COMMENT 'Ex.: SIDRA 9605',
    nivel VARCHAR(12) NOT NULL COMMENT 'municipio, ds, bairro, setor, usf, equipe',
    cd_territorio VARCHAR(15) NOT NULL,
    variavel VARCHAR(40) NOT NULL,
    categoria VARCHAR(40) NOT NULL,
    valor DECIMAL(14,6) NOT NULL,
    ic_inferior DECIMAL(14,6),
    ic_superior DECIMAL(14,6),
    dt_acesso DATE NOT NULL,
    CONSTRAINT pk_ref_parametro_oficial PRIMARY KEY (fonte, tabela_fonte, nivel, cd_territorio, variavel, categoria)
) ENGINE=InnoDB COMMENT='Parâmetros oficiais da Etapa 5 em formato longo (metas de calibração). Origem: CSV versionados da Etapa 5';

CREATE TABLE analitica.fato_indicador_equipe (
    competencia INT NOT NULL,
    ine CHAR(10) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    cnes CHAR(7) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'Redundante (desnormalização D1)',
    id_ds SMALLINT NOT NULL COMMENT 'Redundante (desnormalização D1)',
    marcador VARCHAR(20) NOT NULL COMMENT 'OS, IG, RACA_COR, DEFICIENCIA…',
    categoria VARCHAR(30) NOT NULL COMMENT 'SIM, NAO, NAO_INFORMADO, código…',
    faixa_etaria VARCHAR(10) NOT NULL,
    elegivel BOOLEAN NOT NULL COMMENT 'Idade ≥ idade_min_elegivel no fim da competência',
    n INT NOT NULL,
    CONSTRAINT pk_fato_indicador_equipe PRIMARY KEY (competencia, ine, marcador, categoria, faixa_etaria, elegivel),
    CONSTRAINT fk_fato_indicador_equipe_competencia FOREIGN KEY (competencia) REFERENCES analitica.dim_competencia (competencia),
    CONSTRAINT fk_fato_indicador_equipe_ine FOREIGN KEY (ine) REFERENCES nucleo.equipe (ine),
    CONSTRAINT ck_fie_n CHECK (n >= 0)
) ENGINE=InnoDB COMMENT='Indicadores em formato longo por competência e equipe (painel). Origem: Derivada do núcleo';

CREATE TABLE analitica.fato_atendimento_equipe (
    competencia INT NOT NULL,
    ine CHAR(10) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    n_atendimentos INT NOT NULL,
    n_cidadaos_atendidos INT NOT NULL,
    n_cadastrados INT NOT NULL COMMENT 'Denominador, redundante (D2)',
    atraso_medio_digitacao DECIMAL(7,2) COMMENT 'Dias',
    CONSTRAINT pk_fato_atendimento_equipe PRIMARY KEY (competencia, ine),
    CONSTRAINT fk_fato_atendimento_equipe_competencia FOREIGN KEY (competencia) REFERENCES analitica.dim_competencia (competencia),
    CONSTRAINT fk_fato_atendimento_equipe_ine FOREIGN KEY (ine) REFERENCES nucleo.equipe (ine)
) ENGINE=InnoDB COMMENT='Atendimentos por competência e equipe (alvo alternativo de utilização). Origem: Derivada do núcleo';

CREATE TABLE analitica.fato_painel_ml (
    ine CHAR(10) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    periodo INT NOT NULL COMMENT 'Quadrimestre AAAAQ (parametrizável)',
    id_ds SMALLINT NOT NULL COMMENT 'Redundante (D3)',
    tipo_equipe SMALLINT NOT NULL COMMENT 'Redundante (D3)',
    n_dado_real INT NOT NULL COMMENT 'Ativos elegíveis no fim do período',
    prop_sim_os DECIMAL(6,5),
    prop_nao_os DECIMAL(6,5),
    prop_ni_os DECIMAL(6,5),
    prop_sim_ig DECIMAL(6,5),
    prop_sim_os_lag1 DECIMAL(6,5),
    prop_sim_os_lag2 DECIMAL(6,5),
    prop_criancas DECIMAL(6,5),
    prop_60_mais DECIMAL(6,5),
    dist_raca_cor_censo DECIMAL(6,5) COMMENT 'Distância de Hellinger',
    atraso_medio_digitacao DECIMAL(7,2),
    n_acoes_ate_periodo SMALLINT NOT NULL DEFAULT 0 COMMENT 'Só ações até o fim do período (RN18)',
    alvo_prop_sim_os DECIMAL(6,5) COMMENT 'Alvo: proporção Sim no período seguinte',
    alvo_prop_sim_ig DECIMAL(6,5) COMMENT 'Alvo do segundo modelo',
    CONSTRAINT pk_fato_painel_ml PRIMARY KEY (ine, periodo),
    CONSTRAINT fk_fato_painel_ml_ine FOREIGN KEY (ine) REFERENCES nucleo.equipe (ine),
    CONSTRAINT ck_pml_alvo CHECK (alvo_prop_sim_os IS NULL OR alvo_prop_sim_os BETWEEN 0 AND 1)
) ENGINE=InnoDB COMMENT='Painel equipe × período do problema supervisionado (Tabela 10 do plano). Origem: Derivada do núcleo';

-- ---------------------------------------------------------------------
-- ÍNDICES de filtro e junção (as PKs e UNIQUEs já criam os seus)
-- ---------------------------------------------------------------------
CREATE INDEX ix_bairro_ds ON nucleo.bairro (id_ds);  -- FK; filtro por distrito
CREATE INDEX ix_setor_bairro ON nucleo.setor_censitario (id_bairro);  -- FK; setor → bairro
CREATE INDEX ix_unidade_bairro ON nucleo.unidade_saude (id_bairro);  -- FK; unidade → bairro → distrito
CREATE INDEX ix_equipe_cnes ON nucleo.equipe (cnes);  -- FK; agregação equipe → unidade (planilha por USF)
CREATE INDEX ix_lotacao_ine ON nucleo.lotacao (ine);  -- FK; profissionais da equipe
CREATE INDEX ix_acao_ine_data ON nucleo.acao_formativa (ine, dt_acao);  -- FK; ações até o fim do período (RN18)
CREATE INDEX ix_domicilio_setor ON nucleo.domicilio (cd_setor);  -- FK; calibração por setor e mapa por distrito
CREATE INDEX ix_domicilio_microarea ON nucleo.domicilio (id_microarea);  -- FK
CREATE INDEX ix_familia_domicilio ON nucleo.familia (id_domicilio);  -- FK
CREATE INDEX ix_cidadao_familia ON nucleo.cidadao (id_familia);  -- FK
CREATE INDEX ix_cidadao_nasc_sexo ON nucleo.cidadao (dt_nascimento, sexo);  -- Busca de duplicidade (RQ05) e faixa etária
CREATE INDEX ix_ci_vigente ON nucleo.cadastro_individual (id_cidadao, dt_cadastro, dt_digitacao, uuid);  -- FK; versão vigente (RN09): partição por cidadão ordenada por data
CREATE INDEX ix_ci_equipe_data ON nucleo.cadastro_individual (ine, dt_cadastro);  -- Indicadores por equipe e competência
CREATE INDEX ix_ci_lotacao ON nucleo.cadastro_individual (cns_profissional, ine);  -- FK composta para lotacao
CREATE INDEX ix_ci_microarea ON nucleo.cadastro_individual (ine, microarea);  -- FK composta para microarea
CREATE INDEX ix_ci_originadora ON nucleo.cadastro_individual (uuid_originadora, id_cidadao);  -- FK composta da cadeia de versões
CREATE INDEX ix_cd_tipo ON nucleo.cadastro_deficiencia (codigo_deficiencia, uuid);  -- Prevalência por tipo de deficiência
CREATE INDEX ix_fa_equipe_data ON nucleo.ficha_atendimento (ine, dt_atendimento);  -- Produção por equipe e competência
CREATE INDEX ix_fa_lotacao ON nucleo.ficha_atendimento (cns_profissional, ine);  -- FK composta para lotacao
CREATE INDEX ix_ai_cidadao ON nucleo.atendimento_individual (id_cidadao);  -- FK; atendimentos do cidadão
CREATE INDEX ix_ap_ciap ON nucleo.atendimento_problema (ciap);  -- FK; atendimentos por condição (CIAP2)
CREATE INDEX ix_ap_cid10 ON nucleo.atendimento_problema (cid10);  -- FK; atendimentos por condição (CID-10)
CREATE INDEX ix_def_registro ON nucleo.controle_defeito (tabela, id_registro);  -- Cruzar gabarito com registros
CREATE INDEX ix_def_tipo ON nucleo.controle_defeito (tipo_defeito);  -- Contagem por tipo de defeito
CREATE INDEX ix_fie_equipe ON analitica.fato_indicador_equipe (ine, competencia);  -- FK; série de uma equipe
CREATE INDEX ix_fie_ds ON analitica.fato_indicador_equipe (id_ds, competencia, marcador);  -- Filtro do painel por distrito
CREATE INDEX ix_fae_equipe ON analitica.fato_atendimento_equipe (ine, competencia);  -- FK; série de uma equipe
CREATE INDEX ix_pml_periodo ON analitica.fato_painel_ml (periodo);  -- Partição temporal treino/teste
CREATE INDEX ix_stg_fci_proc ON stg.fci (id_carga, st_processamento);  -- Linhas pendentes de uma carga
CREATE INDEX ix_stg_fci_uuid ON stg.fci (uuid);  -- Resolver a cadeia uuid → originadora
CREATE INDEX ix_stg_fcdt_proc ON stg.fcdt (id_carga, st_processamento);  -- Linhas pendentes de uma carga
CREATE INDEX ix_stg_fam_uuid ON stg.fcdt_familia (uuid);  -- Famílias de cada FCDT
CREATE INDEX ix_stg_fai_proc ON stg.fai (id_carga, st_processamento);  -- Linhas pendentes de uma carga
CREATE INDEX ix_stg_fai_ficha ON stg.fai (uuid_ficha, nu_atendimento);  -- Juntar atendimento e problemas
CREATE INDEX ix_stg_faip_ficha ON stg.fai_problema (uuid_ficha, nu_atendimento);  -- Juntar atendimento e problemas

-- ---------------------------------------------------------------------
-- VISÕES da camada analítica
-- ---------------------------------------------------------------------

-- RN26: parâmetros da carga mais recente; nenhuma visão fixa data de corte ou idade.
CREATE VIEW analitica.vw_parametro_vigente AS
SELECT p.*
FROM nucleo.parametro p
WHERE p.id_carga = (SELECT MAX(id_carga) FROM nucleo.parametro);

-- RN09/RN10: versão vigente de cada cidadão na data de corte (desempate: digitação, uuid).
CREATE VIEW analitica.vw_cadastro_vigente AS
WITH p AS (SELECT * FROM analitica.vw_parametro_vigente),
v AS (
    SELECT ci.*,
           ROW_NUMBER() OVER (PARTITION BY ci.id_cidadao
                              ORDER BY ci.dt_cadastro DESC, ci.dt_digitacao DESC, ci.uuid DESC) AS rn
    FROM nucleo.cadastro_individual ci
    JOIN p ON ci.dt_cadastro <= p.data_corte)
SELECT v.uuid, v.id_cidadao, v.ine, e.cnes, b.id_ds,
       v.dt_cadastro, v.recusa_cadastro, v.raca_cor, v.nome_social,
       v.deseja_informar_os, v.orientacao_sexual, v.deseja_informar_ig, v.identidade_genero,
       v.tem_deficiencia, v.escolaridade, v.motivo_saida,
       TIMESTAMPDIFF(YEAR, c.dt_nascimento, p.data_corte) AS idade_na_data_corte,
       (TIMESTAMPDIFF(YEAR, c.dt_nascimento, p.data_corte) < p.idade_min_elegivel) AS crianca,
       (v.motivo_saida IS NULL AND (p.recusa_conta_ativo OR NOT v.recusa_cadastro)) AS ativo
FROM v
JOIN p ON 1 = 1
JOIN nucleo.cidadao c       ON c.id_cidadao = v.id_cidadao
JOIN nucleo.equipe e        ON e.ine = v.ine
JOIN nucleo.unidade_saude u ON u.cnes = e.cnes
JOIN nucleo.bairro b        ON b.id_bairro = u.id_bairro
WHERE v.rn = 1;

-- Tabela 9 do plano, por equipe: colunas H a U da planilha da SESAU (orientação sexual).
CREATE VIEW analitica.vw_monitoramento_equipe AS
SELECT id_ds, cnes, ine,
       COUNT(*)                                                                   AS h_ativos,
       SUM(CASE WHEN crianca THEN 1 ELSE 0 END)                                   AS i_criancas,
       SUM(CASE WHEN NOT crianca THEN 1 ELSE 0 END)                               AS j_dado_real,
       SUM(CASE WHEN deseja_informar_os IS TRUE THEN 1 ELSE 0 END)                AS k_os_sim,
       SUM(CASE WHEN deseja_informar_os IS TRUE AND crianca THEN 1 ELSE 0 END)    AS l_os_sim_crianca,
       SUM(CASE WHEN deseja_informar_os IS TRUE AND NOT crianca THEN 1 ELSE 0 END) AS m_os_sim_dado_real,
       ROUND(1.0 * SUM(CASE WHEN deseja_informar_os IS TRUE AND NOT crianca THEN 1 ELSE 0 END)
             / NULLIF(SUM(CASE WHEN NOT crianca THEN 1 ELSE 0 END), 0), 4)     AS n_os_sim_pct,
       SUM(CASE WHEN deseja_informar_os IS FALSE THEN 1 ELSE 0 END)               AS o_os_nao,
       SUM(CASE WHEN deseja_informar_os IS FALSE AND NOT crianca THEN 1 ELSE 0 END) AS q_os_nao_dado_real,
       ROUND(1.0 * SUM(CASE WHEN deseja_informar_os IS FALSE AND NOT crianca THEN 1 ELSE 0 END)
             / NULLIF(SUM(CASE WHEN NOT crianca THEN 1 ELSE 0 END), 0), 4)     AS r_os_nao_pct,
       SUM(CASE WHEN deseja_informar_os IS NULL THEN 1 ELSE 0 END)                AS s_os_ni,
       SUM(CASE WHEN deseja_informar_os IS NULL AND NOT crianca THEN 1 ELSE 0 END) AS u_os_ni_dado_real,
       SUM(CASE WHEN deseja_informar_ig IS TRUE AND NOT crianca THEN 1 ELSE 0 END) AS ig_sim_dado_real,
       SUM(CASE WHEN deseja_informar_ig IS FALSE AND NOT crianca THEN 1 ELSE 0 END) AS ig_nao_dado_real,
       SUM(CASE WHEN deseja_informar_ig IS NULL AND NOT crianca THEN 1 ELSE 0 END) AS ig_ni_dado_real
FROM analitica.vw_cadastro_vigente
WHERE ativo
GROUP BY id_ds, cnes, ine;

-- Mesma regra por USF (granularidade da planilha atual).
CREATE VIEW analitica.vw_monitoramento_usf AS
SELECT id_ds, cnes,
       SUM(h_ativos) AS h_ativos, SUM(i_criancas) AS i_criancas, SUM(j_dado_real) AS j_dado_real,
       SUM(k_os_sim) AS k_os_sim, SUM(l_os_sim_crianca) AS l_os_sim_crianca,
       SUM(m_os_sim_dado_real) AS m_os_sim_dado_real,
       ROUND(1.0 * SUM(m_os_sim_dado_real) / NULLIF(SUM(j_dado_real), 0), 4) AS n_os_sim_pct,
       SUM(o_os_nao) AS o_os_nao, SUM(q_os_nao_dado_real) AS q_os_nao_dado_real,
       ROUND(1.0 * SUM(q_os_nao_dado_real) / NULLIF(SUM(j_dado_real), 0), 4) AS r_os_nao_pct,
       SUM(s_os_ni) AS s_os_ni, SUM(u_os_ni_dado_real) AS u_os_ni_dado_real,
       SUM(ig_sim_dado_real) AS ig_sim_dado_real, SUM(ig_nao_dado_real) AS ig_nao_dado_real,
       SUM(ig_ni_dado_real) AS ig_ni_dado_real
FROM analitica.vw_monitoramento_equipe
GROUP BY id_ds, cnes;

-- Regras de qualidade (seção 6.4 do modelo lógico). RQ04 depende de ref_parametro_oficial
-- (Etapa 5), RQ08 é distribuição (atraso) e RQ09 só existe no gabarito.
CREATE VIEW analitica.vw_qualidade_registro AS
SELECT 'RQ01' AS regra, 'cadastro_individual' AS tabela, ci.uuid AS id_registro
  FROM nucleo.cadastro_individual ci
 WHERE ci.raca_cor IS NULL AND NOT ci.recusa_cadastro
UNION ALL
SELECT 'RQ02', 'cadastro_individual', v.uuid
  FROM analitica.vw_cadastro_vigente v
 WHERE v.crianca AND (v.deseja_informar_os IS NOT NULL OR v.deseja_informar_ig IS NOT NULL)
UNION ALL
SELECT 'RQ03', 'cadastro_individual', b.uuid
  FROM nucleo.cadastro_individual a
  JOIN nucleo.cadastro_individual b ON b.uuid_originadora = a.uuid AND b.id_cidadao = a.id_cidadao
 WHERE a.raca_cor IS NOT NULL AND b.raca_cor IS NOT NULL AND a.raca_cor <> b.raca_cor
UNION ALL
SELECT 'RQ05', 'cidadao', CAST(b.id_cidadao AS CHAR(44))
  FROM nucleo.cidadao a
  JOIN nucleo.cidadao b ON a.id_cidadao < b.id_cidadao AND a.dt_nascimento = b.dt_nascimento
                       AND a.sexo = b.sexo AND LOWER(a.nome) = LOWER(b.nome)
UNION ALL
SELECT 'RQ06', 'cadastro_individual', v.uuid
  FROM analitica.vw_cadastro_vigente v
  JOIN analitica.vw_parametro_vigente p ON 1 = 1
 WHERE v.ativo AND v.dt_cadastro < DATE_SUB(p.data_corte, INTERVAL p.meses_desatualizado MONTH)
UNION ALL
SELECT 'RQ07', 'cadastro_individual', v.uuid
  FROM analitica.vw_cadastro_vigente v
 WHERE v.ativo AND NOT v.crianca AND NOT v.recusa_cadastro
   AND (v.deseja_informar_os IS NULL OR v.deseja_informar_ig IS NULL)
UNION ALL
SELECT 'RQ10', 'cadastro_individual', v.uuid
  FROM analitica.vw_cadastro_vigente v
 WHERE (v.idade_na_data_corte < 15 AND v.escolaridade = 63)
    OR (v.idade_na_data_corte < 10 AND v.escolaridade IN (55, 56, 57, 59, 60, 62))
UNION ALL
SELECT 'RQ11', 'cadastro_individual', ci.uuid
  FROM nucleo.cadastro_individual ci
 WHERE ci.tem_deficiencia IS NULL AND NOT ci.recusa_cadastro
UNION ALL
SELECT 'RQ12', 'cidadao', CAST(c.id_cidadao AS CHAR(44))
  FROM nucleo.cidadao c
  JOIN analitica.vw_parametro_vigente p ON 1 = 1
 WHERE TIMESTAMPDIFF(YEAR, c.dt_nascimento, p.data_corte) > 110 OR c.dt_nascimento = DATE '1900-01-01';

