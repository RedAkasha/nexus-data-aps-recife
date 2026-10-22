-- =====================================================================
-- Emulação de dados da APS para as políticas de equidade do Recife
-- Etapa 4 – Modelagem física · script DDL · PostgreSQL 16
-- Projeto 3 – Dados (CESAR School, 2026.2) · Equipe 2 – Nexus Data
-- Versão 1.0.0 · 2026-10-20 · gerado a partir do modelo lógico v1.0.0
-- Ordem de execução: 01_ddl → 02_carga_dominios → 03_validacao_carga
-- =====================================================================

-- No PostgreSQL cada camada é um schema do mesmo banco (criado com ENCODING 'UTF8').
CREATE SCHEMA IF NOT EXISTS stg;
CREATE SCHEMA IF NOT EXISTS nucleo;
CREATE SCHEMA IF NOT EXISTS analitica;


-- ---------------------------------------------------------------------
-- NÚCLEO — 3FN; domínios primeiro, depois as tabelas que os referenciam
-- ---------------------------------------------------------------------

CREATE TABLE nucleo.dom_sexo (
    codigo SMALLINT NOT NULL,
    descricao VARCHAR(200) NOT NULL,
    CONSTRAINT pk_dom_sexo PRIMARY KEY (codigo)
);
COMMENT ON TABLE nucleo.dom_sexo IS 'Sexo do cidadão (0, 1, 4, 5). Origem: LEDI · Sexo';

CREATE TABLE nucleo.dom_raca_cor (
    codigo SMALLINT NOT NULL,
    descricao VARCHAR(200) NOT NULL,
    CONSTRAINT pk_dom_raca_cor PRIMARY KEY (codigo)
);
COMMENT ON TABLE nucleo.dom_raca_cor IS 'Raça/cor (1, 2, 3, 4, 5). Origem: LEDI · RacaCor';

CREATE TABLE nucleo.dom_etnia (
    codigo SMALLINT NOT NULL,
    descricao VARCHAR(200) NOT NULL,
    CONSTRAINT pk_dom_etnia PRIMARY KEY (codigo)
);
COMMENT ON TABLE nucleo.dom_etnia IS 'Etnias indígenas (406 valores). Origem: LEDI · etnia';

CREATE TABLE nucleo.dom_orientacao_sexual (
    codigo SMALLINT NOT NULL,
    descricao VARCHAR(200) NOT NULL,
    CONSTRAINT pk_dom_orientacao_sexual PRIMARY KEY (codigo)
);
COMMENT ON TABLE nucleo.dom_orientacao_sexual IS 'Orientação sexual. Origem: LEDI · OrientacaoSexual';

CREATE TABLE nucleo.dom_identidade_genero (
    codigo SMALLINT NOT NULL,
    descricao VARCHAR(200) NOT NULL,
    CONSTRAINT pk_dom_identidade_genero PRIMARY KEY (codigo)
);
COMMENT ON TABLE nucleo.dom_identidade_genero IS 'Identidade de gênero. Origem: LEDI · identidadeGeneroCidadao';

CREATE TABLE nucleo.dom_tipo_deficiencia (
    codigo SMALLINT NOT NULL,
    descricao VARCHAR(200) NOT NULL,
    CONSTRAINT pk_dom_tipo_deficiencia PRIMARY KEY (codigo)
);
COMMENT ON TABLE nucleo.dom_tipo_deficiencia IS 'Tipos de deficiência, com TEA (232). Origem: LEDI · DeficienciaCidadao (entidade TIPO_DEFICIENCIA)';

CREATE TABLE nucleo.dom_escolaridade (
    codigo SMALLINT NOT NULL,
    descricao VARCHAR(200) NOT NULL,
    CONSTRAINT pk_dom_escolaridade PRIMARY KEY (codigo)
);
COMMENT ON TABLE nucleo.dom_escolaridade IS 'Curso mais elevado. Origem: LEDI · CursoMaisElevado';

CREATE TABLE nucleo.dom_situacao_trabalho (
    codigo SMALLINT NOT NULL,
    descricao VARCHAR(200) NOT NULL,
    CONSTRAINT pk_dom_situacao_trabalho PRIMARY KEY (codigo)
);
COMMENT ON TABLE nucleo.dom_situacao_trabalho IS 'Situação no mercado de trabalho. Origem: LEDI · SituacaoMercadoTrabalho';

CREATE TABLE nucleo.dom_motivo_saida (
    codigo SMALLINT NOT NULL,
    descricao VARCHAR(200) NOT NULL,
    CONSTRAINT pk_dom_motivo_saida PRIMARY KEY (codigo)
);
COMMENT ON TABLE nucleo.dom_motivo_saida IS 'Motivo de saída (135 óbito, 136 mudança). Origem: LEDI · MotivoSaida';

CREATE TABLE nucleo.dom_tipo_imovel (
    codigo SMALLINT NOT NULL,
    descricao VARCHAR(200) NOT NULL,
    CONSTRAINT pk_dom_tipo_imovel PRIMARY KEY (codigo)
);
COMMENT ON TABLE nucleo.dom_tipo_imovel IS 'Tipo de imóvel da FCDT. Origem: LEDI · tipoDeImovel';

CREATE TABLE nucleo.dom_renda_familiar (
    codigo SMALLINT NOT NULL,
    descricao VARCHAR(200) NOT NULL,
    CONSTRAINT pk_dom_renda_familiar PRIMARY KEY (codigo)
);
COMMENT ON TABLE nucleo.dom_renda_familiar IS 'Renda familiar em salários mínimos. Origem: LEDI · RendaFamiliar';

CREATE TABLE nucleo.dom_tipo_atendimento (
    codigo SMALLINT NOT NULL,
    descricao VARCHAR(200) NOT NULL,
    CONSTRAINT pk_dom_tipo_atendimento PRIMARY KEY (codigo)
);
COMMENT ON TABLE nucleo.dom_tipo_atendimento IS 'Tipo de atendimento (todos os códigos do LEDI). Origem: LEDI · TipoDeAtendimento';

CREATE TABLE nucleo.dom_local_atendimento (
    codigo SMALLINT NOT NULL,
    descricao VARCHAR(200) NOT NULL,
    CONSTRAINT pk_dom_local_atendimento PRIMARY KEY (codigo)
);
COMMENT ON TABLE nucleo.dom_local_atendimento IS 'Local de atendimento. Origem: LEDI · LocalDeAtendimento';

CREATE TABLE nucleo.dom_turno (
    codigo SMALLINT NOT NULL,
    descricao VARCHAR(200) NOT NULL,
    CONSTRAINT pk_dom_turno PRIMARY KEY (codigo)
);
COMMENT ON TABLE nucleo.dom_turno IS 'Turno do atendimento. Origem: LEDI · Turno';

CREATE TABLE nucleo.dom_ciap (
    codigo VARCHAR(6) NOT NULL,
    descricao VARCHAR(200) NOT NULL,
    tipo CHAR(5) NOT NULL,
    pre_natal BOOLEAN NOT NULL DEFAULT FALSE,
    procedimento BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT pk_dom_ciap PRIMARY KEY (codigo),
    CONSTRAINT ck_dom_ciap_tipo CHECK (tipo IN ('CIAP2','AB'))
);
COMMENT ON TABLE nucleo.dom_ciap IS 'CIAP2 e os cinco Códigos AB aceitos no campo ciap. Origem: CIAP2 + LEDI · ListaCiapCondicaoAvaliada (entidade CODIGO_CLINICO)';

CREATE TABLE nucleo.dom_cid10 (
    codigo VARCHAR(4) NOT NULL,
    descricao VARCHAR(200) NOT NULL,
    CONSTRAINT pk_dom_cid10 PRIMARY KEY (codigo)
);
COMMENT ON TABLE nucleo.dom_cid10 IS 'CID-10 sem ponto (ex.: Z340). Origem: CID-10 (entidade CODIGO_CLINICO)';

CREATE TABLE nucleo.dom_cbo (
    codigo CHAR(6) NOT NULL,
    descricao VARCHAR(200) NOT NULL,
    CONSTRAINT pk_dom_cbo PRIMARY KEY (codigo)
);
COMMENT ON TABLE nucleo.dom_cbo IS 'Ocupações. Origem: CBO 2002 (LEDI, anexos)';

CREATE TABLE nucleo.dom_tipo_unidade (
    codigo SMALLINT NOT NULL,
    descricao VARCHAR(200) NOT NULL,
    CONSTRAINT pk_dom_tipo_unidade PRIMARY KEY (codigo)
);
COMMENT ON TABLE nucleo.dom_tipo_unidade IS 'Tipo de unidade (USF, eCR, CAI…). Origem: CNES · tipo de estabelecimento';

CREATE TABLE nucleo.dom_tipo_equipe (
    codigo SMALLINT NOT NULL,
    descricao VARCHAR(200) NOT NULL,
    CONSTRAINT pk_dom_tipo_equipe PRIMARY KEY (codigo)
);
COMMENT ON TABLE nucleo.dom_tipo_equipe IS 'Tipo de equipe (eSF, eAP, eCR…). Origem: CNES · tipo de equipe';

CREATE TABLE nucleo.dom_tipo_acao (
    codigo SMALLINT NOT NULL,
    descricao VARCHAR(200) NOT NULL,
    CONSTRAINT pk_dom_tipo_acao PRIMARY KEY (codigo)
);
COMMENT ON TABLE nucleo.dom_tipo_acao IS 'Tipo de ação formativa (oficina, material…). Origem: Projeto';

CREATE TABLE nucleo.dom_tipo_defeito (
    codigo SMALLINT NOT NULL,
    descricao VARCHAR(200) NOT NULL,
    CONSTRAINT pk_dom_tipo_defeito PRIMARY KEY (codigo)
);
COMMENT ON TABLE nucleo.dom_tipo_defeito IS 'Tipos de defeito injetado. Origem: Projeto (Etapa 7)';

CREATE TABLE nucleo.dom_cbo_ficha (
    cbo CHAR(6) NOT NULL,
    ficha CHAR(4) NOT NULL,
    CONSTRAINT pk_dom_cbo_ficha PRIMARY KEY (cbo, ficha),
    CONSTRAINT fk_dom_cbo_ficha_cbo FOREIGN KEY (cbo) REFERENCES nucleo.dom_cbo (codigo),
    CONSTRAINT ck_cbo_ficha CHECK (ficha IN ('FCI','FCDT','FAI'))
);
COMMENT ON TABLE nucleo.dom_cbo_ficha IS 'CBO que pode registrar cada modelo de informação. Origem: LEDI · Grupos de CBO por modelo de informação';

CREATE TABLE nucleo.distrito_sanitario (
    id_ds SMALLINT NOT NULL,
    nome_ds VARCHAR(10) NOT NULL,
    CONSTRAINT pk_distrito_sanitario PRIMARY KEY (id_ds),
    CONSTRAINT uq_distrito_sanitario_nome_ds UNIQUE (nome_ds),
    CONSTRAINT ck_ds_faixa CHECK (id_ds BETWEEN 1 AND 8)
);
COMMENT ON TABLE nucleo.distrito_sanitario IS 'Distritos Sanitários I a VIII. Origem: Prefeitura do Recife';

CREATE TABLE nucleo.bairro (
    id_bairro SMALLINT NOT NULL,
    nome_bairro VARCHAR(72) NOT NULL,
    id_ds SMALLINT NOT NULL,
    CONSTRAINT pk_bairro PRIMARY KEY (id_bairro),
    CONSTRAINT uq_bairro_nome_bairro UNIQUE (nome_bairro),
    CONSTRAINT fk_bairro_id_ds FOREIGN KEY (id_ds) REFERENCES nucleo.distrito_sanitario (id_ds)
);
COMMENT ON TABLE nucleo.bairro IS 'Bairros oficiais do Recife e o distrito a que pertencem. Origem: Prefeitura do Recife (malhas territoriais) — tabela nova, 3FN';

CREATE TABLE nucleo.setor_censitario (
    cd_setor CHAR(15) NOT NULL,
    id_bairro SMALLINT NOT NULL,
    CONSTRAINT pk_setor_censitario PRIMARY KEY (cd_setor),
    CONSTRAINT fk_setor_censitario_id_bairro FOREIGN KEY (id_bairro) REFERENCES nucleo.bairro (id_bairro),
    CONSTRAINT ck_setor_recife CHECK (cd_setor LIKE '2611606%')
);
COMMENT ON TABLE nucleo.setor_censitario IS 'Setores censitários do Censo 2022 no Recife. Origem: IBGE, malha de setores 2022 — tabela nova, 3FN';

CREATE TABLE nucleo.unidade_saude (
    cnes CHAR(7) NOT NULL,
    nome_unidade VARCHAR(100) NOT NULL,
    tipo_unidade SMALLINT NOT NULL,
    id_bairro SMALLINT NOT NULL,
    CONSTRAINT pk_unidade_saude PRIMARY KEY (cnes),
    CONSTRAINT fk_unidade_saude_tipo_unidade FOREIGN KEY (tipo_unidade) REFERENCES nucleo.dom_tipo_unidade (codigo),
    CONSTRAINT fk_unidade_saude_id_bairro FOREIGN KEY (id_bairro) REFERENCES nucleo.bairro (id_bairro),
    CONSTRAINT ck_cnes_formato CHECK (cnes ~ '^[0-9]{7}$')
);
COMMENT ON TABLE nucleo.unidade_saude IS 'Estabelecimentos do CNES (USF, eCR, CAI…). Origem: CNES';

CREATE TABLE nucleo.equipe (
    ine CHAR(10) NOT NULL,
    nome_equipe VARCHAR(60) NOT NULL,
    tipo_equipe SMALLINT NOT NULL,
    cnes CHAR(7) NOT NULL,
    CONSTRAINT pk_equipe PRIMARY KEY (ine),
    CONSTRAINT fk_equipe_tipo_equipe FOREIGN KEY (tipo_equipe) REFERENCES nucleo.dom_tipo_equipe (codigo),
    CONSTRAINT fk_equipe_cnes FOREIGN KEY (cnes) REFERENCES nucleo.unidade_saude (cnes),
    CONSTRAINT ck_ine_formato CHECK (ine ~ '^[0-9]{10}$')
);
COMMENT ON TABLE nucleo.equipe IS 'Equipes identificadas pelo INE. Origem: CNES';

CREATE TABLE nucleo.microarea (
    id_microarea INT NOT NULL,
    ine CHAR(10) NOT NULL,
    codigo_microarea CHAR(2) NOT NULL,
    CONSTRAINT pk_microarea PRIMARY KEY (id_microarea),
    CONSTRAINT uq_microarea_equipe UNIQUE (ine, codigo_microarea),
    CONSTRAINT fk_microarea_ine FOREIGN KEY (ine) REFERENCES nucleo.equipe (ine),
    CONSTRAINT ck_microarea_codigo CHECK (codigo_microarea ~ '^[0-9]{2}$' AND codigo_microarea <> '00')
);
COMMENT ON TABLE nucleo.microarea IS 'Microáreas de cada equipe. Origem: FCI/FCDT';

CREATE TABLE nucleo.profissional (
    cns_profissional CHAR(15) NOT NULL,
    nome_profissional VARCHAR(70) NOT NULL,
    CONSTRAINT pk_profissional PRIMARY KEY (cns_profissional),
    CONSTRAINT ck_prof_cns CHECK (cns_profissional ~ '^[0-9]{15}$')
);
COMMENT ON TABLE nucleo.profissional IS 'Profissional fictício. Origem: headerTransport.profissionalCNS';

CREATE TABLE nucleo.lotacao (
    cns_profissional CHAR(15) NOT NULL,
    ine CHAR(10) NOT NULL,
    cbo CHAR(6) NOT NULL,
    CONSTRAINT pk_lotacao PRIMARY KEY (cns_profissional, ine),
    CONSTRAINT fk_lotacao_cns_profissional FOREIGN KEY (cns_profissional) REFERENCES nucleo.profissional (cns_profissional),
    CONSTRAINT fk_lotacao_ine FOREIGN KEY (ine) REFERENCES nucleo.equipe (ine),
    CONSTRAINT fk_lotacao_cbo FOREIGN KEY (cbo) REFERENCES nucleo.dom_cbo (codigo)
);
COMMENT ON TABLE nucleo.lotacao IS 'Lotação do profissional numa equipe, com a CBO exercida (relacionamento lota, agora N:N). Origem: headerTransport (profissionalCNS, cboCodigo_2002, cnes, ine)';

CREATE TABLE nucleo.acao_formativa (
    id_acao INT NOT NULL,
    ine CHAR(10) NOT NULL,
    dt_acao DATE NOT NULL,
    tipo_acao SMALLINT NOT NULL,
    tema VARCHAR(100),
    CONSTRAINT pk_acao_formativa PRIMARY KEY (id_acao),
    CONSTRAINT fk_acao_formativa_ine FOREIGN KEY (ine) REFERENCES nucleo.equipe (ine),
    CONSTRAINT fk_acao_formativa_tipo_acao FOREIGN KEY (tipo_acao) REFERENCES nucleo.dom_tipo_acao (codigo)
);
COMMENT ON TABLE nucleo.acao_formativa IS 'Oficina ou material recebido por uma equipe. Origem: Projeto';

CREATE TABLE nucleo.domicilio (
    id_domicilio INT NOT NULL,
    uuid_ficha VARCHAR(44) NOT NULL,
    tipo_imovel SMALLINT NOT NULL,
    cd_setor CHAR(15) NOT NULL,
    id_microarea INT,
    fora_area BOOLEAN NOT NULL DEFAULT FALSE,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT pk_domicilio PRIMARY KEY (id_domicilio),
    CONSTRAINT uq_domicilio_uuid_ficha UNIQUE (uuid_ficha),
    CONSTRAINT fk_domicilio_tipo_imovel FOREIGN KEY (tipo_imovel) REFERENCES nucleo.dom_tipo_imovel (codigo),
    CONSTRAINT fk_domicilio_cd_setor FOREIGN KEY (cd_setor) REFERENCES nucleo.setor_censitario (cd_setor),
    CONSTRAINT fk_domicilio_id_microarea FOREIGN KEY (id_microarea) REFERENCES nucleo.microarea (id_microarea),
    CONSTRAINT ck_dom_fora_area CHECK ((fora_area AND id_microarea IS NULL) OR (NOT fora_area AND id_microarea IS NOT NULL))
);
COMMENT ON TABLE nucleo.domicilio IS 'Imóvel cadastrado na FCDT (estado mais recente). Origem: FCDT';

CREATE TABLE nucleo.familia (
    id_familia INT NOT NULL,
    id_domicilio INT NOT NULL,
    renda_familiar SMALLINT,
    num_membros SMALLINT,
    reside_desde DATE,
    mudou_se BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT pk_familia PRIMARY KEY (id_familia),
    CONSTRAINT fk_familia_id_domicilio FOREIGN KEY (id_domicilio) REFERENCES nucleo.domicilio (id_domicilio),
    CONSTRAINT fk_familia_renda_familiar FOREIGN KEY (renda_familiar) REFERENCES nucleo.dom_renda_familiar (codigo),
    CONSTRAINT ck_fam_membros CHECK (num_membros IS NULL OR num_membros BETWEEN 1 AND 999)
);
COMMENT ON TABLE nucleo.familia IS 'Família de um domicílio. Origem: FCDT · FamiliaRow';

CREATE TABLE nucleo.cidadao (
    id_cidadao BIGINT NOT NULL,
    cpf CHAR(11),
    cns CHAR(15),
    nome VARCHAR(70) NOT NULL,
    dt_nascimento DATE NOT NULL,
    sexo SMALLINT NOT NULL,
    id_familia INT,
    CONSTRAINT pk_cidadao PRIMARY KEY (id_cidadao),
    CONSTRAINT uq_cidadao_cpf UNIQUE (cpf),
    CONSTRAINT uq_cidadao_cns UNIQUE (cns),
    CONSTRAINT fk_cidadao_sexo FOREIGN KEY (sexo) REFERENCES nucleo.dom_sexo (codigo),
    CONSTRAINT fk_cidadao_id_familia FOREIGN KEY (id_familia) REFERENCES nucleo.familia (id_familia),
    CONSTRAINT ck_cid_ident CHECK (cpf IS NOT NULL OR cns IS NOT NULL),
    CONSTRAINT ck_cid_cpf CHECK (cpf IS NULL OR cpf ~ '^[0-9]{11}$'),
    CONSTRAINT ck_cid_cns CHECK (cns IS NULL OR cns ~ '^[0-9]{15}$')
);
COMMENT ON TABLE nucleo.cidadao IS 'Pessoa sintética: só atributos estáveis. Origem: FCI · IdentificacaoUsuarioCidadao';

CREATE TABLE nucleo.cadastro_individual (
    uuid VARCHAR(44) NOT NULL,
    id_cidadao BIGINT NOT NULL,
    uuid_originadora VARCHAR(44),
    cns_profissional CHAR(15) NOT NULL,
    ine CHAR(10) NOT NULL,
    dt_cadastro DATE NOT NULL,
    dt_digitacao DATE NOT NULL,
    ficha_atualizada BOOLEAN NOT NULL,
    recusa_cadastro BOOLEAN NOT NULL DEFAULT FALSE,
    responsavel_familiar BOOLEAN,
    microarea CHAR(2),
    fora_area BOOLEAN,
    raca_cor SMALLINT,
    etnia SMALLINT,
    nome_social VARCHAR(70),
    deseja_informar_os BOOLEAN,
    orientacao_sexual SMALLINT,
    deseja_informar_ig BOOLEAN,
    identidade_genero SMALLINT,
    tem_deficiencia BOOLEAN,
    escolaridade SMALLINT,
    situacao_trabalho SMALLINT,
    motivo_saida SMALLINT,
    dt_obito DATE,
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
);
COMMENT ON TABLE nucleo.cadastro_individual IS 'Uma versão da FCI; guarda os atributos autodeclarados. Origem: FCI · CadastroIndividual';

CREATE TABLE nucleo.cadastro_deficiencia (
    uuid VARCHAR(44) NOT NULL,
    codigo_deficiencia SMALLINT NOT NULL,
    CONSTRAINT pk_cadastro_deficiencia PRIMARY KEY (uuid, codigo_deficiencia),
    CONSTRAINT fk_cadastro_deficiencia_uuid FOREIGN KEY (uuid) REFERENCES nucleo.cadastro_individual (uuid),
    CONSTRAINT fk_cadastro_deficiencia_codigo_deficiencia FOREIGN KEY (codigo_deficiencia) REFERENCES nucleo.dom_tipo_deficiencia (codigo)
);
COMMENT ON TABLE nucleo.cadastro_deficiencia IS 'Tipos de deficiência declarados numa versão (relacionamento declara, N:N). Origem: FCI · deficienciasCidadao';

CREATE TABLE nucleo.ficha_atendimento (
    uuid_ficha VARCHAR(44) NOT NULL,
    cns_profissional CHAR(15) NOT NULL,
    ine CHAR(10) NOT NULL,
    dt_atendimento DATE NOT NULL,
    dt_digitacao DATE NOT NULL,
    CONSTRAINT pk_ficha_atendimento PRIMARY KEY (uuid_ficha),
    CONSTRAINT fk_fa_lotacao FOREIGN KEY (cns_profissional, ine) REFERENCES nucleo.lotacao (cns_profissional, ine),
    CONSTRAINT ck_fa_digitacao CHECK (dt_digitacao >= dt_atendimento)
);
COMMENT ON TABLE nucleo.ficha_atendimento IS 'Ficha da FAI (lote de até 99 atendimentos): profissional, equipe e datas comuns. Origem: FAI · FichaAtendimentoIndividualMaster + VariasLotacoesHeader';

CREATE TABLE nucleo.atendimento_individual (
    id_atendimento BIGINT NOT NULL,
    uuid_ficha VARCHAR(44) NOT NULL,
    nu_atendimento SMALLINT NOT NULL,
    id_cidadao BIGINT NOT NULL,
    dt_hora_inicio TIMESTAMP NOT NULL,
    tipo_atendimento SMALLINT NOT NULL,
    local_atendimento SMALLINT NOT NULL,
    turno SMALLINT NOT NULL,
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
);
COMMENT ON TABLE nucleo.atendimento_individual IS 'Um atendimento da FAI. Origem: FAI · FichaAtendimentoIndividualChild';

CREATE TABLE nucleo.atendimento_problema (
    id_atendimento BIGINT NOT NULL,
    nu_item SMALLINT NOT NULL,
    ciap VARCHAR(6),
    cid10 VARCHAR(4),
    CONSTRAINT pk_atendimento_problema PRIMARY KEY (id_atendimento, nu_item),
    CONSTRAINT uq_ap_ciap UNIQUE (id_atendimento, ciap),
    CONSTRAINT uq_ap_cid10 UNIQUE (id_atendimento, cid10),
    CONSTRAINT fk_atendimento_problema_id_atendimento FOREIGN KEY (id_atendimento) REFERENCES nucleo.atendimento_individual (id_atendimento),
    CONSTRAINT fk_atendimento_problema_ciap FOREIGN KEY (ciap) REFERENCES nucleo.dom_ciap (codigo),
    CONSTRAINT fk_atendimento_problema_cid10 FOREIGN KEY (cid10) REFERENCES nucleo.dom_cid10 (codigo),
    CONSTRAINT ck_ap_codigo CHECK (ciap IS NOT NULL OR cid10 IS NOT NULL),
    CONSTRAINT ck_ap_w78 CHECK (COALESCE(ciap, '') <> 'W78' OR cid10 IS NULL OR cid10 LIKE 'Z34%')
);
COMMENT ON TABLE nucleo.atendimento_problema IS 'Problema ou condição avaliada (relacionamento avalia): CIAP2 e/ou CID-10 no mesmo item. Origem: FAI · ProblemaCondicao';

CREATE TABLE nucleo.parametro (
    id_carga INT NOT NULL,
    data_corte DATE NOT NULL,
    idade_min_elegivel SMALLINT NOT NULL DEFAULT 11,
    recusa_conta_ativo BOOLEAN NOT NULL DEFAULT TRUE,
    meses_desatualizado SMALLINT NOT NULL DEFAULT 24,
    semente INT NOT NULL,
    fator_escala DECIMAL(5,4) NOT NULL,
    versao_gerador VARCHAR(20) NOT NULL,
    dt_geracao TIMESTAMP NOT NULL,
    CONSTRAINT pk_parametro PRIMARY KEY (id_carga),
    CONSTRAINT ck_par_idade CHECK (idade_min_elegivel BETWEEN 0 AND 17),
    CONSTRAINT ck_par_escala CHECK (fator_escala > 0 AND fator_escala <= 1),
    CONSTRAINT ck_par_meses CHECK (meses_desatualizado > 0)
);
COMMENT ON TABLE nucleo.parametro IS 'Parâmetros de cada carga; fonte da regra do “dado real”. Origem: Projeto';

CREATE TABLE nucleo.controle_defeito (
    id_defeito INT NOT NULL,
    tabela VARCHAR(40) NOT NULL,
    id_registro VARCHAR(44) NOT NULL,
    tipo_defeito SMALLINT NOT NULL,
    etapa SMALLINT NOT NULL,
    campo VARCHAR(40),
    id_registro_par VARCHAR(44),
    valor_original VARCHAR(70),
    CONSTRAINT pk_controle_defeito PRIMARY KEY (id_defeito),
    CONSTRAINT fk_controle_defeito_tipo_defeito FOREIGN KEY (tipo_defeito) REFERENCES nucleo.dom_tipo_defeito (codigo),
    CONSTRAINT ck_def_tabela CHECK (tabela IN ('cidadao','cadastro_individual','cadastro_deficiencia','domicilio','familia','ficha_atendimento','atendimento_individual','atendimento_problema')),
    CONSTRAINT ck_def_etapa CHECK (etapa IN (6, 7))
);
COMMENT ON TABLE nucleo.controle_defeito IS 'Gabarito dos defeitos injetados (Etapa 7); referência polimórfica, sem FK por desenho. Origem: Projeto (Etapa 7)';

-- ---------------------------------------------------------------------
-- STAGING — dado como chega, sem restrições além da chave técnica
-- ---------------------------------------------------------------------

CREATE TABLE stg.fci (
    id_carga INT NOT NULL,
    nu_linha BIGINT NOT NULL,
    st_processamento CHAR(1) NOT NULL DEFAULT 'P',
    motivo_rejeicao VARCHAR(200),
    profissional_cns VARCHAR(15),
    cbo_codigo_2002 VARCHAR(6),
    cnes VARCHAR(7),
    ine VARCHAR(10),
    data_atendimento BIGINT,
    codigo_ibge_municipio VARCHAR(7),
    uuid VARCHAR(44),
    uuid_ficha_originadora VARCHAR(44),
    ficha_atualizada BOOLEAN,
    tp_cds_origem INT,
    status_termo_recusa_cadastro_individual_atencao_basica BOOLEAN,
    cpf_cidadao VARCHAR(11),
    cns_cidadao VARCHAR(15),
    st_nao_possui_cpf BOOLEAN,
    justificativa_nao_possui_cpf INT,
    nome_cidadao VARCHAR(70),
    nome_social VARCHAR(70),
    data_nascimento_cidadao BIGINT,
    sexo_cidadao INT,
    raca_cor_cidadao INT,
    etnia INT,
    nacionalidade_cidadao INT,
    pais_nascimento INT,
    codigo_ibge_municipio_nascimento VARCHAR(7),
    nome_mae_cidadao VARCHAR(70),
    desconhece_nome_mae BOOLEAN,
    nome_pai_cidadao VARCHAR(70),
    desconhece_nome_pai BOOLEAN,
    status_eh_responsavel BOOLEAN,
    cpf_responsavel_familiar VARCHAR(11),
    cns_responsavel_familiar VARCHAR(15),
    microarea VARCHAR(2),
    st_fora_area BOOLEAN,
    status_deseja_informar_orientacao_sexual BOOLEAN,
    orientacao_sexual_cidadao INT,
    status_deseja_informar_identidade_genero BOOLEAN,
    identidade_genero_cidadao INT,
    status_tem_alguma_deficiencia BOOLEAN,
    deficiencias_cidadao VARCHAR(40),
    grau_instrucao_cidadao INT,
    situacao_mercado_trabalho_cidadao INT,
    relacao_parentesco_cidadao INT,
    status_frequenta_escola BOOLEAN,
    status_membro_povo_comunidade_tradicional BOOLEAN,
    co_povo_comunidade_tradicional INT,
    motivo_saida_cidadao INT,
    data_obito BIGINT,
    numero_do VARCHAR(9),
    dt_digitacao DATE,
    CONSTRAINT pk_fci PRIMARY KEY (id_carga, nu_linha)
);
COMMENT ON TABLE stg.fci IS 'FCI como chega (uma linha por ficha). Origem: LEDI · CadastroIndividual (ver dicionário, seção 3)';

CREATE TABLE stg.fcdt (
    id_carga INT NOT NULL,
    nu_linha BIGINT NOT NULL,
    st_processamento CHAR(1) NOT NULL DEFAULT 'P',
    motivo_rejeicao VARCHAR(200),
    profissional_cns VARCHAR(15),
    cbo_codigo_2002 VARCHAR(6),
    cnes VARCHAR(7),
    ine VARCHAR(10),
    data_atendimento BIGINT,
    codigo_ibge_municipio VARCHAR(7),
    uuid VARCHAR(44),
    uuid_ficha_originadora VARCHAR(44),
    ficha_atualizada BOOLEAN,
    tp_cds_origem INT,
    status_termo_recusa BOOLEAN,
    tipo_de_imovel INT,
    tipo_endereco INT,
    st_ativo BOOLEAN,
    bairro VARCHAR(72),
    cep VARCHAR(8),
    codigo_ibge_municipio_endereco VARCHAR(7),
    nome_logradouro VARCHAR(72),
    numero VARCHAR(10),
    numero_dne_uf VARCHAR(2),
    tipo_logradouro_numero_dne VARCHAR(5),
    micro_area VARCHAR(2),
    st_fora_area BOOLEAN,
    localizacao INT,
    situacao_moradia_posse_terra INT,
    tipo_domicilio INT,
    cd_setor VARCHAR(15),
    CONSTRAINT pk_fcdt PRIMARY KEY (id_carga, nu_linha)
);
COMMENT ON TABLE stg.fcdt IS 'FCDT como chega (uma linha por ficha). Origem: LEDI · CadastroDomiciliar (dicionário, seção 4)';

CREATE TABLE stg.fcdt_familia (
    id_carga INT NOT NULL,
    nu_linha BIGINT NOT NULL,
    st_processamento CHAR(1) NOT NULL DEFAULT 'P',
    motivo_rejeicao VARCHAR(200),
    uuid VARCHAR(44),
    nu_familia INT,
    numero_cns_responsavel VARCHAR(15),
    cpf_responsavel VARCHAR(11),
    data_nascimento_responsavel BIGINT,
    numero_membros_familia INT,
    renda_familiar INT,
    reside_desde BIGINT,
    st_mudanca BOOLEAN,
    CONSTRAINT pk_fcdt_familia PRIMARY KEY (id_carga, nu_linha)
);
COMMENT ON TABLE stg.fcdt_familia IS 'Famílias de cada FCDT (uma linha por FamiliaRow). Origem: LEDI · FamiliaRow';

CREATE TABLE stg.fai (
    id_carga INT NOT NULL,
    nu_linha BIGINT NOT NULL,
    st_processamento CHAR(1) NOT NULL DEFAULT 'P',
    motivo_rejeicao VARCHAR(200),
    uuid_ficha VARCHAR(44),
    tp_cds_origem INT,
    profissional_cns VARCHAR(15),
    cbo_codigo_2002 VARCHAR(6),
    cnes VARCHAR(7),
    ine VARCHAR(10),
    data_atendimento BIGINT,
    codigo_ibge_municipio VARCHAR(7),
    nu_atendimento INT,
    cpf_cidadao VARCHAR(11),
    cns_cidadao VARCHAR(15),
    st_cidadao_nao_possui_cpf BOOLEAN,
    justificativa_nao_possui_cpf INT,
    data_nascimento BIGINT,
    sexo INT,
    local_de_atendimento INT,
    turno INT,
    tipo_atendimento INT,
    condutas VARCHAR(60),
    data_hora_inicial_atendimento BIGINT,
    data_hora_final_atendimento BIGINT,
    dt_digitacao DATE,
    CONSTRAINT pk_fai PRIMARY KEY (id_carga, nu_linha)
);
COMMENT ON TABLE stg.fai IS 'FAI como chega (uma linha por atendimento, com o cabeçalho da ficha repetido). Origem: LEDI · FichaAtendimentoIndividualMaster/Child (dicionário, seção 5)';

CREATE TABLE stg.fai_problema (
    id_carga INT NOT NULL,
    nu_linha BIGINT NOT NULL,
    st_processamento CHAR(1) NOT NULL DEFAULT 'P',
    motivo_rejeicao VARCHAR(200),
    uuid_ficha VARCHAR(44),
    nu_atendimento INT,
    nu_item INT,
    ciap VARCHAR(6),
    cid10 VARCHAR(4),
    is_avaliado BOOLEAN,
    CONSTRAINT pk_fai_problema PRIMARY KEY (id_carga, nu_linha)
);
COMMENT ON TABLE stg.fai_problema IS 'Problemas e condições de cada atendimento. Origem: LEDI · ProblemaCondicao';

CREATE TABLE stg.cnes_estabelecimento (
    id_carga INT NOT NULL,
    nu_linha BIGINT NOT NULL,
    st_processamento CHAR(1) NOT NULL DEFAULT 'P',
    motivo_rejeicao VARCHAR(200),
    cnes VARCHAR(7),
    nome_fantasia VARCHAR(100),
    tipo_unidade INT,
    bairro VARCHAR(72),
    CONSTRAINT pk_cnes_estabelecimento PRIMARY KEY (id_carga, nu_linha)
);
COMMENT ON TABLE stg.cnes_estabelecimento IS 'Estabelecimentos do CNES no Recife (Etapa 5). Origem: DATASUS · CNES';

CREATE TABLE stg.cnes_equipe (
    id_carga INT NOT NULL,
    nu_linha BIGINT NOT NULL,
    st_processamento CHAR(1) NOT NULL DEFAULT 'P',
    motivo_rejeicao VARCHAR(200),
    ine VARCHAR(10),
    cnes VARCHAR(7),
    nome_equipe VARCHAR(60),
    tipo_equipe INT,
    CONSTRAINT pk_cnes_equipe PRIMARY KEY (id_carga, nu_linha)
);
COMMENT ON TABLE stg.cnes_equipe IS 'Equipes do CNES no Recife (Etapa 5). Origem: DATASUS · CNES';

CREATE TABLE stg.malha_territorial (
    id_carga INT NOT NULL,
    nu_linha BIGINT NOT NULL,
    st_processamento CHAR(1) NOT NULL DEFAULT 'P',
    motivo_rejeicao VARCHAR(200),
    cd_setor VARCHAR(15),
    nome_bairro VARCHAR(72),
    id_bairro INT,
    nome_ds VARCHAR(10),
    CONSTRAINT pk_malha_territorial PRIMARY KEY (id_carga, nu_linha)
);
COMMENT ON TABLE stg.malha_territorial IS 'Setor censitário → bairro → distrito (Etapa 5). Origem: IBGE e Prefeitura do Recife';

CREATE TABLE stg.profissional_lotacao (
    id_carga INT NOT NULL,
    nu_linha BIGINT NOT NULL,
    st_processamento CHAR(1) NOT NULL DEFAULT 'P',
    motivo_rejeicao VARCHAR(200),
    cns_profissional VARCHAR(15),
    nome_profissional VARCHAR(70),
    ine VARCHAR(10),
    cbo VARCHAR(6),
    CONSTRAINT pk_profissional_lotacao PRIMARY KEY (id_carga, nu_linha)
);
COMMENT ON TABLE stg.profissional_lotacao IS 'Profissionais fictícios e lotações emitidos pelo gerador. Origem: Gerador (Etapa 6)';

-- ---------------------------------------------------------------------
-- ANALÍTICA — tabelas derivadas, reconstruídas a cada carga
-- ---------------------------------------------------------------------

CREATE TABLE analitica.dim_competencia (
    competencia INT NOT NULL,
    dt_inicio DATE NOT NULL,
    dt_fim DATE NOT NULL,
    ano SMALLINT NOT NULL,
    mes SMALLINT NOT NULL,
    quadrimestre INT NOT NULL,
    semestre INT NOT NULL,
    CONSTRAINT pk_dim_competencia PRIMARY KEY (competencia),
    CONSTRAINT ck_comp_mes CHECK (mes BETWEEN 1 AND 12 AND dt_fim >= dt_inicio)
);
COMMENT ON TABLE analitica.dim_competencia IS 'Calendário das competências mensais. Origem: Projeto';

CREATE TABLE analitica.ref_parametro_oficial (
    fonte VARCHAR(30) NOT NULL,
    tabela_fonte VARCHAR(30) NOT NULL,
    nivel VARCHAR(12) NOT NULL,
    cd_territorio VARCHAR(15) NOT NULL,
    variavel VARCHAR(40) NOT NULL,
    categoria VARCHAR(40) NOT NULL,
    valor DECIMAL(14,6) NOT NULL,
    ic_inferior DECIMAL(14,6),
    ic_superior DECIMAL(14,6),
    dt_acesso DATE NOT NULL,
    CONSTRAINT pk_ref_parametro_oficial PRIMARY KEY (fonte, tabela_fonte, nivel, cd_territorio, variavel, categoria)
);
COMMENT ON TABLE analitica.ref_parametro_oficial IS 'Parâmetros oficiais da Etapa 5 em formato longo (metas de calibração). Origem: CSV versionados da Etapa 5';

CREATE TABLE analitica.fato_indicador_equipe (
    competencia INT NOT NULL,
    ine CHAR(10) NOT NULL,
    cnes CHAR(7) NOT NULL,
    id_ds SMALLINT NOT NULL,
    marcador VARCHAR(20) NOT NULL,
    categoria VARCHAR(30) NOT NULL,
    faixa_etaria VARCHAR(10) NOT NULL,
    elegivel BOOLEAN NOT NULL,
    n INT NOT NULL,
    CONSTRAINT pk_fato_indicador_equipe PRIMARY KEY (competencia, ine, marcador, categoria, faixa_etaria, elegivel),
    CONSTRAINT fk_fato_indicador_equipe_competencia FOREIGN KEY (competencia) REFERENCES analitica.dim_competencia (competencia),
    CONSTRAINT fk_fato_indicador_equipe_ine FOREIGN KEY (ine) REFERENCES nucleo.equipe (ine),
    CONSTRAINT ck_fie_n CHECK (n >= 0)
);
COMMENT ON TABLE analitica.fato_indicador_equipe IS 'Indicadores em formato longo por competência e equipe (painel). Origem: Derivada do núcleo';

CREATE TABLE analitica.fato_atendimento_equipe (
    competencia INT NOT NULL,
    ine CHAR(10) NOT NULL,
    n_atendimentos INT NOT NULL,
    n_cidadaos_atendidos INT NOT NULL,
    n_cadastrados INT NOT NULL,
    atraso_medio_digitacao DECIMAL(7,2),
    CONSTRAINT pk_fato_atendimento_equipe PRIMARY KEY (competencia, ine),
    CONSTRAINT fk_fato_atendimento_equipe_competencia FOREIGN KEY (competencia) REFERENCES analitica.dim_competencia (competencia),
    CONSTRAINT fk_fato_atendimento_equipe_ine FOREIGN KEY (ine) REFERENCES nucleo.equipe (ine)
);
COMMENT ON TABLE analitica.fato_atendimento_equipe IS 'Atendimentos por competência e equipe (alvo alternativo de utilização). Origem: Derivada do núcleo';

CREATE TABLE analitica.fato_painel_ml (
    ine CHAR(10) NOT NULL,
    periodo INT NOT NULL,
    id_ds SMALLINT NOT NULL,
    tipo_equipe SMALLINT NOT NULL,
    n_dado_real INT NOT NULL,
    prop_sim_os DECIMAL(6,5),
    prop_nao_os DECIMAL(6,5),
    prop_ni_os DECIMAL(6,5),
    prop_sim_ig DECIMAL(6,5),
    prop_sim_os_lag1 DECIMAL(6,5),
    prop_sim_os_lag2 DECIMAL(6,5),
    prop_criancas DECIMAL(6,5),
    prop_60_mais DECIMAL(6,5),
    dist_raca_cor_censo DECIMAL(6,5),
    atraso_medio_digitacao DECIMAL(7,2),
    n_acoes_ate_periodo SMALLINT NOT NULL DEFAULT 0,
    alvo_prop_sim_os DECIMAL(6,5),
    alvo_prop_sim_ig DECIMAL(6,5),
    CONSTRAINT pk_fato_painel_ml PRIMARY KEY (ine, periodo),
    CONSTRAINT fk_fato_painel_ml_ine FOREIGN KEY (ine) REFERENCES nucleo.equipe (ine),
    CONSTRAINT ck_pml_alvo CHECK (alvo_prop_sim_os IS NULL OR alvo_prop_sim_os BETWEEN 0 AND 1)
);
COMMENT ON TABLE analitica.fato_painel_ml IS 'Painel equipe × período do problema supervisionado (Tabela 10 do plano). Origem: Derivada do núcleo';

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
       CAST(date_part('year', age(p.data_corte, c.dt_nascimento)) AS INT) AS idade_na_data_corte,
       (CAST(date_part('year', age(p.data_corte, c.dt_nascimento)) AS INT) < p.idade_min_elegivel) AS crianca,
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
SELECT 'RQ05', 'cidadao', CAST(b.id_cidadao AS VARCHAR(44))
  FROM nucleo.cidadao a
  JOIN nucleo.cidadao b ON a.id_cidadao < b.id_cidadao AND a.dt_nascimento = b.dt_nascimento
                       AND a.sexo = b.sexo AND LOWER(a.nome) = LOWER(b.nome)
UNION ALL
SELECT 'RQ06', 'cadastro_individual', v.uuid
  FROM analitica.vw_cadastro_vigente v
  JOIN analitica.vw_parametro_vigente p ON 1 = 1
 WHERE v.ativo AND v.dt_cadastro < CAST(p.data_corte - make_interval(months => p.meses_desatualizado) AS DATE)
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
SELECT 'RQ12', 'cidadao', CAST(c.id_cidadao AS VARCHAR(44))
  FROM nucleo.cidadao c
  JOIN analitica.vw_parametro_vigente p ON 1 = 1
 WHERE CAST(date_part('year', age(p.data_corte, c.dt_nascimento)) AS INT) > 110 OR c.dt_nascimento = DATE '1900-01-01';

