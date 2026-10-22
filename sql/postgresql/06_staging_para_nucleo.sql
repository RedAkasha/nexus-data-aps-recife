-- =====================================================================
-- Etapa 8 – Carga staging → núcleo · PostgreSQL 16
-- Projeto 3 – Dados (CESAR School, 2026.2) · Equipe 2 – Nexus Data
-- Transforma as fichas como chegam (leiaute LEDI, datas em ms) nas tabelas do núcleo.
-- Pré-requisitos: 01 a 05 executados; stg.* carregadas (id_carga = :carga) e, carregados
-- direto do gerador por não existirem no LEDI, nucleo.microarea, nucleo.acao_formativa,
-- nucleo.parametro e nucleo.controle_defeito.
-- Chaves substitutas = posto da chave natural (ORDER BY ... COLLATE "C"), as mesmas que o
-- gerador grava na carga direta; assim o gabarito vale para as duas rotas.
-- Uso: psql -v carga=1 -f 06_staging_para_nucleo.sql  (o carregador Python substitui :carga)
-- =====================================================================

-- ms do LEDI (meia-noite de Recife, UTC−3) → data / data-hora local
CREATE OR REPLACE FUNCTION stg.fn_ms_data(p BIGINT) RETURNS DATE
LANGUAGE sql IMMUTABLE AS $$ SELECT CAST(TIMESTAMP '1970-01-01' + p * INTERVAL '1 millisecond' - INTERVAL '3 hours' AS DATE) $$;
CREATE OR REPLACE FUNCTION stg.fn_ms_ts(p BIGINT) RETURNS TIMESTAMP
LANGUAGE sql IMMUTABLE AS $$ SELECT TIMESTAMP '1970-01-01' + p * INTERVAL '1 millisecond' - INTERVAL '3 hours' $$;
CREATE OR REPLACE FUNCTION stg.fn_chave(p_cpf VARCHAR, p_cns VARCHAR) RETURNS VARCHAR
LANGUAGE sql IMMUTABLE AS $$ SELECT COALESCE(p_cpf, 'CNS' || p_cns) $$;

-- 1. rejeições de integridade referencial mínima (o restante fica para as VC)
UPDATE stg.fci f SET st_processamento = 'R', motivo_rejeicao = 'equipe inexistente'
 WHERE f.id_carga = :carga AND NOT EXISTS (SELECT 1 FROM nucleo.equipe e WHERE e.ine = f.ine);
UPDATE stg.fai f SET st_processamento = 'R', motivo_rejeicao = 'equipe inexistente'
 WHERE f.id_carga = :carga AND NOT EXISTS (SELECT 1 FROM nucleo.equipe e WHERE e.ine = f.ine);
UPDATE stg.fci SET st_processamento = 'R', motivo_rejeicao = 'cidadão sem CPF e sem CNS'
 WHERE id_carga = :carga AND cpf_cidadao IS NULL AND cns_cidadao IS NULL;

-- 2. território sintético e profissionais
INSERT INTO nucleo.setor_censitario (cd_setor, id_bairro)
SELECT DISTINCT m.cd_setor, CAST(m.id_bairro AS SMALLINT)
  FROM stg.malha_territorial m
 WHERE m.id_carga = :carga
   AND NOT EXISTS (SELECT 1 FROM nucleo.setor_censitario s WHERE s.cd_setor = m.cd_setor);

INSERT INTO nucleo.profissional (cns_profissional, nome_profissional)
SELECT cns_profissional, MIN(nome_profissional)
  FROM stg.profissional_lotacao WHERE id_carga = :carga GROUP BY cns_profissional;

INSERT INTO nucleo.lotacao (cns_profissional, ine, cbo)
SELECT DISTINCT cns_profissional, ine, cbo FROM stg.profissional_lotacao WHERE id_carga = :carga;

-- 3. domicílios e famílias (FCDT)
INSERT INTO nucleo.domicilio (id_domicilio, uuid_ficha, tipo_imovel, cd_setor, id_microarea, fora_area, ativo)
SELECT ROW_NUMBER() OVER (ORDER BY d.uuid COLLATE "C"), d.uuid, CAST(d.tipo_de_imovel AS SMALLINT), d.cd_setor,
       m.id_microarea, COALESCE(d.st_fora_area, FALSE), COALESCE(d.st_ativo, TRUE)
  FROM stg.fcdt d
  LEFT JOIN nucleo.microarea m ON m.ine = d.ine AND m.codigo_microarea = d.micro_area
 WHERE d.id_carga = :carga AND d.st_processamento = 'P';

INSERT INTO nucleo.familia (id_familia, id_domicilio, renda_familiar, num_membros, reside_desde, mudou_se)
SELECT ROW_NUMBER() OVER (ORDER BY f.uuid COLLATE "C", f.nu_familia), dm.id_domicilio,
       CAST(f.renda_familiar AS SMALLINT), CAST(f.numero_membros_familia AS SMALLINT),
       stg.fn_ms_data(f.reside_desde), COALESCE(f.st_mudanca, FALSE)
  FROM stg.fcdt_familia f
  JOIN nucleo.domicilio dm ON dm.uuid_ficha = f.uuid
 WHERE f.id_carga = :carga;

-- 4. cidadãos: identidade da versão mais recente; família = a do responsável indicado nela,
--    escolhendo a FCDT mais recente desse responsável
ANALYZE stg.fci; ANALYZE stg.fcdt; ANALYZE stg.fcdt_familia; ANALYZE stg.fai; ANALYZE stg.fai_problema;
ANALYZE nucleo.domicilio; ANALYZE nucleo.familia;

CREATE TEMPORARY TABLE tmp_fci_vigente ON COMMIT DROP AS
SELECT *
  FROM (SELECT f.*, stg.fn_chave(f.cpf_cidadao, f.cns_cidadao) AS chave,
               ROW_NUMBER() OVER (PARTITION BY stg.fn_chave(f.cpf_cidadao, f.cns_cidadao)
                                  ORDER BY f.data_atendimento DESC, f.dt_digitacao DESC, f.uuid COLLATE "C" DESC) AS rn
          FROM stg.fci f
         WHERE f.id_carga = :carga AND f.st_processamento = 'P') x
 WHERE rn = 1;

CREATE TEMPORARY TABLE tmp_familia_resp ON COMMIT DROP AS
SELECT chave, id_familia
  FROM (SELECT stg.fn_chave(f.cpf_responsavel, f.numero_cns_responsavel) AS chave, fa.id_familia,
               ROW_NUMBER() OVER (PARTITION BY stg.fn_chave(f.cpf_responsavel, f.numero_cns_responsavel)
                                  ORDER BY d.data_atendimento DESC, f.uuid COLLATE "C" DESC) AS rn
          FROM stg.fcdt_familia f
          JOIN stg.fcdt d ON d.id_carga = f.id_carga AND d.uuid = f.uuid
          JOIN nucleo.domicilio dm ON dm.uuid_ficha = f.uuid
          JOIN nucleo.familia fa ON fa.id_domicilio = dm.id_domicilio
         WHERE f.id_carga = :carga
           AND stg.fn_chave(f.cpf_responsavel, f.numero_cns_responsavel) IS NOT NULL) x
 WHERE rn = 1;

INSERT INTO nucleo.cidadao (id_cidadao, cpf, cns, nome, dt_nascimento, sexo, id_familia)
SELECT ROW_NUMBER() OVER (ORDER BY v.chave COLLATE "C"), v.cpf_cidadao, v.cns_cidadao, v.nome_cidadao,
       stg.fn_ms_data(v.data_nascimento_cidadao), CAST(v.sexo_cidadao AS SMALLINT), fr.id_familia
  FROM tmp_fci_vigente v
  LEFT JOIN tmp_familia_resp fr
         ON fr.chave = CASE WHEN v.status_eh_responsavel THEN v.chave
                            ELSE stg.fn_chave(v.cpf_responsavel_familiar, v.cns_responsavel_familiar) END;

-- chave natural → id (índice para as junções das fichas)
CREATE TEMPORARY TABLE tmp_chave ON COMMIT DROP AS
SELECT stg.fn_chave(cpf, cns) AS chave, id_cidadao FROM nucleo.cidadao;
CREATE UNIQUE INDEX ix_tmp_chave ON tmp_chave (chave);
ANALYZE tmp_chave;

-- 5. versões da FCI e tipos de deficiência
INSERT INTO nucleo.cadastro_individual (
    uuid, id_cidadao, uuid_originadora, cns_profissional, ine, dt_cadastro, dt_digitacao, ficha_atualizada,
    recusa_cadastro, responsavel_familiar, microarea, fora_area, raca_cor, etnia, nome_social,
    deseja_informar_os, orientacao_sexual, deseja_informar_ig, identidade_genero, tem_deficiencia,
    escolaridade, situacao_trabalho, motivo_saida, dt_obito)
SELECT f.uuid, c.id_cidadao, NULLIF(f.uuid_ficha_originadora, f.uuid), f.profissional_cns, f.ine,
       stg.fn_ms_data(f.data_atendimento), f.dt_digitacao, f.ficha_atualizada,
       COALESCE(f.status_termo_recusa_cadastro_individual_atencao_basica, FALSE), f.status_eh_responsavel,
       f.microarea, f.st_fora_area, CAST(f.raca_cor_cidadao AS SMALLINT), CAST(f.etnia AS SMALLINT), f.nome_social,
       f.status_deseja_informar_orientacao_sexual, CAST(f.orientacao_sexual_cidadao AS SMALLINT),
       f.status_deseja_informar_identidade_genero, CAST(f.identidade_genero_cidadao AS SMALLINT),
       f.status_tem_alguma_deficiencia, CAST(f.grau_instrucao_cidadao AS SMALLINT),
       CAST(f.situacao_mercado_trabalho_cidadao AS SMALLINT), CAST(f.motivo_saida_cidadao AS SMALLINT),
       stg.fn_ms_data(f.data_obito)
  FROM stg.fci f
  JOIN tmp_chave c ON c.chave = stg.fn_chave(f.cpf_cidadao, f.cns_cidadao)
 WHERE f.id_carga = :carga AND f.st_processamento = 'P';

INSERT INTO nucleo.cadastro_deficiencia (uuid, codigo_deficiencia)
SELECT DISTINCT f.uuid, CAST(t.cod AS SMALLINT)
  FROM stg.fci f
 CROSS JOIN LATERAL regexp_split_to_table(f.deficiencias_cidadao, ',') AS t(cod)
 WHERE f.id_carga = :carga AND f.st_processamento = 'P' AND f.deficiencias_cidadao IS NOT NULL;

-- 6. FAI: ficha (cabeçalho), atendimentos e problemas
INSERT INTO nucleo.ficha_atendimento (uuid_ficha, cns_profissional, ine, dt_atendimento, dt_digitacao)
SELECT uuid_ficha, MIN(profissional_cns), MIN(ine), stg.fn_ms_data(MIN(data_atendimento)), MIN(dt_digitacao)
  FROM stg.fai WHERE id_carga = :carga AND st_processamento = 'P' GROUP BY uuid_ficha;

INSERT INTO nucleo.atendimento_individual (id_atendimento, uuid_ficha, nu_atendimento, id_cidadao, dt_hora_inicio,
                                           tipo_atendimento, local_atendimento, turno)
SELECT ROW_NUMBER() OVER (ORDER BY a.uuid_ficha COLLATE "C", a.nu_atendimento), a.uuid_ficha,
       CAST(a.nu_atendimento AS SMALLINT), c.id_cidadao, stg.fn_ms_ts(a.data_hora_inicial_atendimento),
       CAST(a.tipo_atendimento AS SMALLINT), CAST(a.local_de_atendimento AS SMALLINT), CAST(a.turno AS SMALLINT)
  FROM stg.fai a
  JOIN tmp_chave c ON c.chave = stg.fn_chave(a.cpf_cidadao, a.cns_cidadao)
 WHERE a.id_carga = :carga AND a.st_processamento = 'P';

INSERT INTO nucleo.atendimento_problema (id_atendimento, nu_item, ciap, cid10)
SELECT ai.id_atendimento, CAST(p.nu_item AS SMALLINT), p.ciap, p.cid10
  FROM stg.fai_problema p
  JOIN nucleo.atendimento_individual ai ON ai.uuid_ficha = p.uuid_ficha AND ai.nu_atendimento = p.nu_atendimento
 WHERE p.id_carga = :carga;

-- 7. marca o que foi processado
UPDATE stg.fci          SET st_processamento = 'A' WHERE id_carga = :carga AND st_processamento = 'P';
UPDATE stg.fcdt         SET st_processamento = 'A' WHERE id_carga = :carga AND st_processamento = 'P';
UPDATE stg.fcdt_familia SET st_processamento = 'A' WHERE id_carga = :carga AND st_processamento = 'P';
UPDATE stg.fai          SET st_processamento = 'A' WHERE id_carga = :carga AND st_processamento = 'P';
UPDATE stg.fai_problema SET st_processamento = 'A' WHERE id_carga = :carga AND st_processamento = 'P';
