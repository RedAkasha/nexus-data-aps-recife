-- =====================================================================
-- Etapa 4 – Modelagem física · validações de carga (VC01–VC15) · MySQL 8.0.16 ou superior
-- Projeto 3 – Dados (CESAR School, 2026.2) · Equipe 2 – Nexus Data · v1.0.0 · 2026-10-20
-- Regras que envolvem mais de uma linha ou tabela e não cabem em CHECK.
-- São consultas de conjunto, rodadas depois de cada carga (Etapa 8); gatilhos
-- linha a linha deixariam a carga de milhões de linhas lenta e dependeriam da
-- ordem de inserção (ex.: VC01 só pode ser avaliada depois dos tipos de deficiência).
-- Uso: SELECT regra, COUNT(*) FROM analitica.vw_validacao_carga GROUP BY regra;
--      (resultado vazio = carga íntegra)
-- =====================================================================

DELIMITER $$

-- VC14: dígito verificador do CPF (11 dígitos; rejeita sequências repetidas).
DROP FUNCTION IF EXISTS nucleo.fn_cpf_valido $$
CREATE FUNCTION nucleo.fn_cpf_valido(p_cpf CHAR(11)) RETURNS BOOLEAN DETERMINISTIC NO SQL
BEGIN
    DECLARE i INT DEFAULT 1; DECLARE s1 INT DEFAULT 0; DECLARE s2 INT DEFAULT 0; DECLARE d1 INT; DECLARE d2 INT;
    IF p_cpf IS NULL THEN RETURN NULL; END IF;
    -- Sequências repetidas por expressão regular: no MySQL 8.0, comparar o parâmetro com
    -- REPEAT(SUBSTRING(p_cpf, 1, 1), 11) dá "igual" para qualquer CPF (testado no 8.0.46).
    IF p_cpf NOT REGEXP '^[0-9]{11}$'
       OR p_cpf REGEXP '^(0{11}|1{11}|2{11}|3{11}|4{11}|5{11}|6{11}|7{11}|8{11}|9{11})$' THEN RETURN FALSE; END IF;
    WHILE i <= 9 DO
        SET s1 = s1 + CAST(SUBSTRING(p_cpf, i, 1) AS UNSIGNED) * (11 - i);
        SET s2 = s2 + CAST(SUBSTRING(p_cpf, i, 1) AS UNSIGNED) * (12 - i);
        SET i = i + 1;
    END WHILE;
    SET d1 = (s1 * 10) % 11; IF d1 = 10 THEN SET d1 = 0; END IF;
    SET s2 = s2 + d1 * 2;
    SET d2 = (s2 * 10) % 11; IF d2 = 10 THEN SET d2 = 0; END IF;
    RETURN d1 = CAST(SUBSTRING(p_cpf, 10, 1) AS UNSIGNED) AND d2 = CAST(SUBSTRING(p_cpf, 11, 1) AS UNSIGNED);
END $$

-- VC14: CNS (definitivo começa com 1 ou 2; provisório com 7, 8 ou 9); soma ponderada múltipla de 11.
DROP FUNCTION IF EXISTS nucleo.fn_cns_valido $$
CREATE FUNCTION nucleo.fn_cns_valido(p_cns CHAR(15)) RETURNS BOOLEAN DETERMINISTIC NO SQL
BEGIN
    DECLARE i INT DEFAULT 1; DECLARE s INT DEFAULT 0;
    IF p_cns IS NULL THEN RETURN NULL; END IF;
    IF p_cns NOT REGEXP '^[12789][0-9]{14}$' THEN RETURN FALSE; END IF;
    WHILE i <= 15 DO
        SET s = s + CAST(SUBSTRING(p_cns, i, 1) AS UNSIGNED) * (16 - i);
        SET i = i + 1;
    END WHILE;
    RETURN s % 11 = 0;
END $$

DELIMITER ;

DROP VIEW IF EXISTS analitica.vw_validacao_carga;
CREATE VIEW analitica.vw_validacao_carga AS
-- VC01: "Tem deficiência" = Sim exige 1 a 6 tipos; Não ou nulo exige nenhum
SELECT 'VC01' AS regra, 'cadastro_individual' AS tabela, ci.uuid AS id_registro
  FROM nucleo.cadastro_individual ci
  LEFT JOIN (SELECT uuid, COUNT(*) AS n FROM nucleo.cadastro_deficiencia GROUP BY uuid) t ON t.uuid = ci.uuid
 WHERE (ci.tem_deficiencia IS TRUE AND COALESCE(t.n, 0) = 0)
    OR (ci.tem_deficiencia IS NOT TRUE AND COALESCE(t.n, 0) > 0)
UNION ALL
-- VC02: atualização não é anterior à versão que a originou
SELECT 'VC02', 'cadastro_individual', b.uuid
  FROM nucleo.cadastro_individual b
  JOIN nucleo.cadastro_individual a ON a.uuid = b.uuid_originadora
 WHERE b.dt_cadastro < a.dt_cadastro
UNION ALL
-- VC03: nascimento até a data da ficha e no máximo 130 anos antes; óbito não anterior ao nascimento
SELECT 'VC03', 'cadastro_individual', ci.uuid
  FROM nucleo.cadastro_individual ci
  JOIN nucleo.cidadao c ON c.id_cidadao = ci.id_cidadao
 WHERE c.dt_nascimento > ci.dt_cadastro
    OR c.dt_nascimento < DATE_SUB(ci.dt_cadastro, INTERVAL 130 YEAR)
    OR ci.dt_obito < c.dt_nascimento
UNION ALL
-- VC04: mesma regra de nascimento para a data do atendimento
SELECT 'VC04', 'atendimento_individual', CAST(ai.id_atendimento AS CHAR(44))
  FROM nucleo.atendimento_individual ai
  JOIN nucleo.ficha_atendimento fa ON fa.uuid_ficha = ai.uuid_ficha
  JOIN nucleo.cidadao c ON c.id_cidadao = ai.id_cidadao
 WHERE c.dt_nascimento > fa.dt_atendimento OR c.dt_nascimento < DATE_SUB(fa.dt_atendimento, INTERVAL 130 YEAR)
UNION ALL
-- VC05: início do atendimento não anterior à data da ficha
SELECT 'VC05', 'atendimento_individual', CAST(ai.id_atendimento AS CHAR(44))
  FROM nucleo.atendimento_individual ai
  JOIN nucleo.ficha_atendimento fa ON fa.uuid_ficha = ai.uuid_ficha
 WHERE DATE(ai.dt_hora_inicio) < fa.dt_atendimento
UNION ALL
-- VC06: todo atendimento avalia ao menos um problema
SELECT 'VC06', 'atendimento_individual', CAST(ai.id_atendimento AS CHAR(44))
  FROM nucleo.atendimento_individual ai
 WHERE NOT EXISTS (SELECT 1 FROM nucleo.atendimento_problema ap WHERE ap.id_atendimento = ai.id_atendimento)
UNION ALL
-- VC07a: CIAP2 de pré-natal antes dos 9 anos
SELECT 'VC07', 'atendimento_problema', CAST(ap.id_atendimento AS CHAR(44))
  FROM nucleo.atendimento_problema ap
  JOIN nucleo.dom_ciap dc ON dc.codigo = ap.ciap AND dc.pre_natal
  JOIN nucleo.atendimento_individual ai ON ai.id_atendimento = ap.id_atendimento
  JOIN nucleo.ficha_atendimento fa ON fa.uuid_ficha = ai.uuid_ficha
  JOIN nucleo.cidadao c ON c.id_cidadao = ai.id_cidadao
 WHERE TIMESTAMPDIFF(YEAR, c.dt_nascimento, fa.dt_atendimento) < 9
UNION ALL
-- VC07b: mais de uma CID-10 da família Z34 no mesmo atendimento
SELECT 'VC07', 'atendimento_individual', CAST(ap.id_atendimento AS CHAR(44))
  FROM nucleo.atendimento_problema ap
 WHERE ap.cid10 LIKE 'Z34%'
 GROUP BY ap.id_atendimento
HAVING COUNT(*) > 1
UNION ALL
-- VC07c: componente de procedimento da CIAP2 no campo ciap
SELECT 'VC07', 'atendimento_problema', CAST(ap.id_atendimento AS CHAR(44))
  FROM nucleo.atendimento_problema ap
  JOIN nucleo.dom_ciap dc ON dc.codigo = ap.ciap
 WHERE dc.procedimento
UNION ALL
-- VC08a: família só em imóvel do tipo Domicílio (1)
SELECT 'VC08', 'familia', CAST(f.id_familia AS CHAR(44))
  FROM nucleo.familia f
  JOIN nucleo.domicilio dm ON dm.id_domicilio = f.id_domicilio
 WHERE dm.tipo_imovel <> 1
UNION ALL
-- VC08b: domicílio inativo com família que não se mudou
SELECT 'VC08', 'domicilio', CAST(dm.id_domicilio AS CHAR(44))
  FROM nucleo.domicilio dm
 WHERE NOT dm.ativo
   AND EXISTS (SELECT 1 FROM nucleo.familia f WHERE f.id_domicilio = dm.id_domicilio AND NOT f.mudou_se)
UNION ALL
-- VC09: toda família tem ao menos um membro
SELECT 'VC09', 'familia', CAST(f.id_familia AS CHAR(44))
  FROM nucleo.familia f
 WHERE NOT EXISTS (SELECT 1 FROM nucleo.cidadao c WHERE c.id_familia = f.id_familia)
UNION ALL
-- VC10: todo cidadão tem ao menos uma versão do cadastro
SELECT 'VC10', 'cidadao', CAST(c.id_cidadao AS CHAR(44))
  FROM nucleo.cidadao c
 WHERE NOT EXISTS (SELECT 1 FROM nucleo.cadastro_individual ci WHERE ci.id_cidadao = c.id_cidadao)
UNION ALL
-- VC11: a CBO da lotação pode registrar a ficha (FCI ou FAI)
SELECT 'VC11', 'cadastro_individual', ci.uuid
  FROM nucleo.cadastro_individual ci
  JOIN nucleo.lotacao l ON l.cns_profissional = ci.cns_profissional AND l.ine = ci.ine
 WHERE NOT EXISTS (SELECT 1 FROM nucleo.dom_cbo_ficha g WHERE g.cbo = l.cbo AND g.ficha = 'FCI')
UNION ALL
SELECT 'VC11', 'ficha_atendimento', fa.uuid_ficha
  FROM nucleo.ficha_atendimento fa
  JOIN nucleo.lotacao l ON l.cns_profissional = fa.cns_profissional AND l.ine = fa.ine
 WHERE NOT EXISTS (SELECT 1 FROM nucleo.dom_cbo_ficha g WHERE g.cbo = l.cbo AND g.ficha = 'FAI')
UNION ALL
-- VC12: cardinalidades mínimas do território
SELECT 'VC12', 'distrito_sanitario', CAST(ds.id_ds AS CHAR(44))
  FROM nucleo.distrito_sanitario ds
 WHERE NOT EXISTS (SELECT 1 FROM nucleo.bairro b WHERE b.id_ds = ds.id_ds)
UNION ALL
SELECT 'VC12', 'unidade_saude', u.cnes
  FROM nucleo.unidade_saude u
 WHERE NOT EXISTS (SELECT 1 FROM nucleo.equipe e WHERE e.cnes = u.cnes)
UNION ALL
SELECT 'VC12', 'equipe', e.ine
  FROM nucleo.equipe e
 WHERE NOT EXISTS (SELECT 1 FROM nucleo.microarea m WHERE m.ine = e.ine)
    OR NOT EXISTS (SELECT 1 FROM nucleo.lotacao l WHERE l.ine = e.ine)
UNION ALL
-- VC13: nenhuma data posterior à geração da carga
SELECT 'VC13', 'cadastro_individual', ci.uuid
  FROM nucleo.cadastro_individual ci
  JOIN analitica.vw_parametro_vigente p ON 1 = 1
 WHERE ci.dt_cadastro > DATE(p.dt_geracao) OR ci.dt_digitacao > DATE(p.dt_geracao)
UNION ALL
SELECT 'VC13', 'ficha_atendimento', fa.uuid_ficha
  FROM nucleo.ficha_atendimento fa
  JOIN analitica.vw_parametro_vigente p ON 1 = 1
 WHERE fa.dt_atendimento > DATE(p.dt_geracao) OR fa.dt_digitacao > DATE(p.dt_geracao)
UNION ALL
-- VC14: CPF e CNS com dígito verificador válido
SELECT 'VC14', 'cidadao', CAST(c.id_cidadao AS CHAR(44))
  FROM nucleo.cidadao c
 WHERE (c.cpf IS NOT NULL AND NOT nucleo.fn_cpf_valido(c.cpf))
    OR (c.cns IS NOT NULL AND NOT nucleo.fn_cns_valido(c.cns))
UNION ALL
SELECT 'VC14', 'profissional', p.cns_profissional
  FROM nucleo.profissional p
 WHERE NOT nucleo.fn_cns_valido(p.cns_profissional)
UNION ALL
-- VC15: famílias da mesma FCDT sem responsável repetido (na staging)
SELECT 'VC15', 'stg.fcdt_familia', MIN(f.uuid)
  FROM stg.fcdt_familia f
 WHERE COALESCE(f.numero_cns_responsavel, f.cpf_responsavel) IS NOT NULL
 GROUP BY f.id_carga, f.uuid, COALESCE(f.numero_cns_responsavel, f.cpf_responsavel)
HAVING COUNT(*) > 1;
