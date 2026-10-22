-- =====================================================================
-- Etapa 9 – Camada analítica (reconstruída a cada carga) · PostgreSQL 16
-- Projeto 3 – Dados (CESAR School, 2026.2) · Equipe 2 – Nexus Data
-- Preenche dim_competencia, fato_indicador_equipe, fato_atendimento_equipe e fato_painel_ml.
-- Regra da versão vigente por competência = a de vw_cadastro_vigente aplicada ao fim de cada
-- mês (modelo lógico, seção 7): maior dt_cadastro até dt_fim; desempate por dt_digitacao e uuid.
-- Parâmetros (data de corte, idade mínima, recusa) só vêm de vw_parametro_vigente (RN26).
-- A distância de Hellinger usa a referência bairro × raça/cor carregada em ref_parametro_oficial
-- (fonte 'Gerador IPF': o Censo 2022 não publica raça por bairro; pendência E6).
-- O mesmo cálculo existe em Python (src/aps_sintetico/analitica.py) e o teste confere os dois.
-- =====================================================================

DELETE FROM analitica.fato_painel_ml;
DELETE FROM analitica.fato_atendimento_equipe;
DELETE FROM analitica.fato_indicador_equipe;
DELETE FROM analitica.dim_competencia;

-- 1. calendário: do primeiro mês com atendimento ou cadastro na série até a data de corte
INSERT INTO analitica.dim_competencia (competencia, dt_inicio, dt_fim, ano, mes, quadrimestre, semestre)
SELECT CAST(to_char(m, 'YYYYMM') AS INT), CAST(m AS DATE), CAST(m + INTERVAL '1 month' - INTERVAL '1 day' AS DATE),
       CAST(EXTRACT(YEAR FROM m) AS SMALLINT), CAST(EXTRACT(MONTH FROM m) AS SMALLINT),
       CAST(EXTRACT(YEAR FROM m) AS INT) * 10 + (CAST(EXTRACT(MONTH FROM m) AS INT) - 1) / 4 + 1,
       CAST(EXTRACT(YEAR FROM m) AS INT) * 10 + (CAST(EXTRACT(MONTH FROM m) AS INT) - 1) / 6 + 1
  FROM generate_series(
         (SELECT date_trunc('month', MIN(dt_atendimento)) FROM nucleo.ficha_atendimento),
         (SELECT date_trunc('month', data_corte) FROM analitica.vw_parametro_vigente),
         INTERVAL '1 month') AS g(m);

-- 2. intervalos de validade das versões e versão vigente em cada competência
CREATE TEMPORARY TABLE tmp_versao AS
SELECT ci.*, LEAD(ci.dt_cadastro) OVER (PARTITION BY ci.id_cidadao
                                         ORDER BY ci.dt_cadastro, ci.dt_digitacao, ci.uuid COLLATE "C") AS dt_proxima
  FROM nucleo.cadastro_individual ci;

CREATE TEMPORARY TABLE tmp_vig AS
SELECT d.competencia, d.dt_fim, d.quadrimestre, v.uuid, v.id_cidadao, v.ine, e.cnes, b.id_ds,
       v.raca_cor, v.deseja_informar_os, v.orientacao_sexual, v.deseja_informar_ig, v.identidade_genero,
       v.tem_deficiencia, v.nome_social,
       CAST(date_part('year', age(d.dt_fim, c.dt_nascimento)) AS INT) AS idade,
       (CAST(date_part('year', age(d.dt_fim, c.dt_nascimento)) AS INT) >= p.idade_min_elegivel) AS elegivel
  FROM analitica.dim_competencia d
  JOIN tmp_versao v ON v.dt_cadastro <= d.dt_fim AND (v.dt_proxima IS NULL OR v.dt_proxima > d.dt_fim)
  JOIN analitica.vw_parametro_vigente p ON 1 = 1
  JOIN nucleo.cidadao c       ON c.id_cidadao = v.id_cidadao
  JOIN nucleo.equipe e        ON e.ine = v.ine
  JOIN nucleo.unidade_saude u ON u.cnes = e.cnes
  JOIN nucleo.bairro b        ON b.id_bairro = u.id_bairro
 WHERE v.motivo_saida IS NULL AND (p.recusa_conta_ativo OR NOT v.recusa_cadastro);
CREATE INDEX ix_tmp_vig ON tmp_vig (competencia, ine);
ALTER TABLE tmp_vig ADD COLUMN faixa_etaria VARCHAR(10);
UPDATE tmp_vig SET faixa_etaria = CASE WHEN idade <= 10 THEN '00-10' WHEN idade <= 17 THEN '11-17'
                                        WHEN idade <= 29 THEN '18-29' WHEN idade <= 39 THEN '30-39'
                                        WHEN idade <= 59 THEN '40-59' ELSE '60+' END;

-- 3. indicadores em formato longo
INSERT INTO analitica.fato_indicador_equipe (competencia, ine, cnes, id_ds, marcador, categoria, faixa_etaria, elegivel, n)
SELECT competencia, ine, cnes, id_ds, marcador, categoria, faixa_etaria, elegivel, COUNT(*)
  FROM (
    SELECT t.*, 'OS' AS marcador,
           CASE WHEN deseja_informar_os IS TRUE THEN 'SIM' WHEN deseja_informar_os IS FALSE THEN 'NAO'
                ELSE 'NAO_INFORMADO' END AS categoria FROM tmp_vig t
    UNION ALL
    SELECT t.*, 'OS', CAST(orientacao_sexual AS VARCHAR(30)) FROM tmp_vig t WHERE orientacao_sexual IS NOT NULL
    UNION ALL
    SELECT t.*, 'IG', CASE WHEN deseja_informar_ig IS TRUE THEN 'SIM' WHEN deseja_informar_ig IS FALSE THEN 'NAO'
                           ELSE 'NAO_INFORMADO' END FROM tmp_vig t
    UNION ALL
    SELECT t.*, 'IG', CAST(identidade_genero AS VARCHAR(30)) FROM tmp_vig t WHERE identidade_genero IS NOT NULL
    UNION ALL
    SELECT t.*, 'RACA_COR', COALESCE(CAST(raca_cor AS VARCHAR(30)), 'VAZIO') FROM tmp_vig t
    UNION ALL
    SELECT t.*, 'DEFICIENCIA', CASE WHEN tem_deficiencia IS TRUE THEN 'SIM' WHEN tem_deficiencia IS FALSE THEN 'NAO'
                                    ELSE 'SEM_REGISTRO' END FROM tmp_vig t
    UNION ALL
    SELECT t.*, 'DEFICIENCIA', CAST(cd.codigo_deficiencia AS VARCHAR(30))
      FROM tmp_vig t JOIN nucleo.cadastro_deficiencia cd ON cd.uuid = t.uuid
    UNION ALL
    SELECT t.*, 'NOME_SOCIAL', CASE WHEN nome_social IS NOT NULL THEN 'PREENCHIDO' ELSE 'VAZIO' END FROM tmp_vig t
  ) x
 GROUP BY competencia, ine, cnes, id_ds, marcador, categoria, faixa_etaria, elegivel;

-- 4. produção por competência e equipe (com o denominador de cadastrados ativos)
INSERT INTO analitica.fato_atendimento_equipe (competencia, ine, n_atendimentos, n_cidadaos_atendidos, n_cadastrados,
                                               atraso_medio_digitacao)
SELECT COALESCE(a.competencia, c.competencia), COALESCE(a.ine, c.ine), COALESCE(a.n_at, 0), COALESCE(a.n_cid, 0),
       COALESCE(c.n_cad, 0), a.atraso
  FROM (SELECT CAST(to_char(fa.dt_atendimento, 'YYYYMM') AS INT) AS competencia, fa.ine,
               COUNT(*) AS n_at, COUNT(DISTINCT ai.id_cidadao) AS n_cid,
               ROUND(AVG(fa.dt_digitacao - fa.dt_atendimento), 2) AS atraso
          FROM nucleo.ficha_atendimento fa
          JOIN nucleo.atendimento_individual ai ON ai.uuid_ficha = fa.uuid_ficha
          JOIN analitica.dim_competencia d ON d.competencia = CAST(to_char(fa.dt_atendimento, 'YYYYMM') AS INT)
         GROUP BY 1, 2) a
  FULL JOIN (SELECT competencia, ine, COUNT(*) AS n_cad FROM tmp_vig GROUP BY 1, 2) c
    ON c.competencia = a.competencia AND c.ine = a.ine;

-- 5. painel equipe × quadrimestre do problema supervisionado (Tabela 10 do plano)
CREATE TEMPORARY TABLE tmp_fim_periodo AS
SELECT quadrimestre AS periodo, MAX(competencia) AS competencia, MAX(dt_fim) AS dt_fim, MIN(dt_inicio) AS dt_inicio
  FROM analitica.dim_competencia GROUP BY quadrimestre;

-- referência de raça/cor da equipe: bairros dos domicílios adscritos, ponderados pelo nº de domicílios
CREATE TEMPORARY TABLE tmp_ref_raca AS
SELECT x.ine, CAST(r.categoria AS SMALLINT) AS raca_cor, SUM(x.peso * r.valor) / SUM(x.peso) AS q
  FROM (SELECT m.ine, s.id_bairro, COUNT(*) AS peso
          FROM nucleo.domicilio dm
          JOIN nucleo.microarea m ON m.id_microarea = dm.id_microarea
          JOIN nucleo.setor_censitario s ON s.cd_setor = dm.cd_setor
         GROUP BY m.ine, s.id_bairro) x
  JOIN analitica.ref_parametro_oficial r
    ON r.fonte = 'Gerador IPF' AND r.variavel = 'prop_raca_cor' AND r.nivel = 'bairro'
   AND r.cd_territorio = '2611606' || lpad(CAST(x.id_bairro AS VARCHAR(3)), 3, '0')
 GROUP BY x.ine, r.categoria;

CREATE TEMPORARY TABLE tmp_painel AS
SELECT f.periodo, f.dt_fim, t.ine,
       SUM(CASE WHEN t.elegivel THEN 1 ELSE 0 END) AS n_dado_real,
       SUM(CASE WHEN t.elegivel AND t.deseja_informar_os IS TRUE THEN 1 ELSE 0 END) AS n_sim_os,
       SUM(CASE WHEN t.elegivel AND t.deseja_informar_os IS FALSE THEN 1 ELSE 0 END) AS n_nao_os,
       SUM(CASE WHEN t.elegivel AND t.deseja_informar_os IS NULL THEN 1 ELSE 0 END) AS n_ni_os,
       SUM(CASE WHEN t.elegivel AND t.deseja_informar_ig IS TRUE THEN 1 ELSE 0 END) AS n_sim_ig,
       SUM(CASE WHEN NOT t.elegivel THEN 1 ELSE 0 END) AS n_criancas,
       SUM(CASE WHEN t.idade >= 60 THEN 1 ELSE 0 END) AS n_60,
       COUNT(*) AS n_ativos
  FROM tmp_fim_periodo f
  JOIN tmp_vig t ON t.competencia = f.competencia
 GROUP BY f.periodo, f.dt_fim, t.ine;

CREATE TEMPORARY TABLE tmp_hellinger AS
SELECT o.periodo, o.ine, SQRT(GREATEST(1 - SUM(SQRT(o.p * COALESCE(r.q, 0))), 0)) AS h
  FROM (SELECT f.periodo, t.ine, t.raca_cor,
               1.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY f.periodo, t.ine) AS p
          FROM tmp_fim_periodo f
          JOIN tmp_vig t ON t.competencia = f.competencia AND t.raca_cor IS NOT NULL
         GROUP BY f.periodo, t.ine, t.raca_cor) o
  LEFT JOIN tmp_ref_raca r ON r.ine = o.ine AND r.raca_cor = o.raca_cor
 WHERE EXISTS (SELECT 1 FROM tmp_ref_raca r2 WHERE r2.ine = o.ine)
 GROUP BY o.periodo, o.ine;

INSERT INTO analitica.fato_painel_ml (ine, periodo, id_ds, tipo_equipe, n_dado_real, prop_sim_os, prop_nao_os,
                                      prop_ni_os, prop_sim_ig, prop_sim_os_lag1, prop_sim_os_lag2, prop_criancas,
                                      prop_60_mais, dist_raca_cor_censo, atraso_medio_digitacao, n_acoes_ate_periodo,
                                      alvo_prop_sim_os, alvo_prop_sim_ig)
SELECT z.ine, z.periodo, z.id_ds, z.tipo_equipe, z.n_dado_real, z.p_sim, z.p_nao, z.p_ni, z.p_sim_ig,
       LAG(z.p_sim, 1) OVER w, LAG(z.p_sim, 2) OVER w, z.p_cri, z.p_60, z.h, z.atraso, z.n_acoes,
       LEAD(z.p_sim, 1) OVER w, LEAD(z.p_sim_ig, 1) OVER w
  FROM (SELECT pn.ine, pn.periodo, b.id_ds, e.tipo_equipe, pn.n_dado_real,
               ROUND(1.0 * pn.n_sim_os / NULLIF(pn.n_dado_real, 0), 5) AS p_sim,
               ROUND(1.0 * pn.n_nao_os / NULLIF(pn.n_dado_real, 0), 5) AS p_nao,
               ROUND(1.0 * pn.n_ni_os / NULLIF(pn.n_dado_real, 0), 5) AS p_ni,
               ROUND(1.0 * pn.n_sim_ig / NULLIF(pn.n_dado_real, 0), 5) AS p_sim_ig,
               ROUND(1.0 * pn.n_criancas / NULLIF(pn.n_ativos, 0), 5) AS p_cri,
               ROUND(1.0 * pn.n_60 / NULLIF(pn.n_ativos, 0), 5) AS p_60,
               ROUND(CAST(h.h AS NUMERIC), 5) AS h,
               (SELECT ROUND(AVG(ci.dt_digitacao - ci.dt_cadastro), 2)
                  FROM nucleo.cadastro_individual ci
                  JOIN tmp_fim_periodo f2 ON f2.periodo = pn.periodo
                 WHERE ci.ine = pn.ine AND ci.dt_cadastro BETWEEN f2.dt_inicio AND f2.dt_fim) AS atraso,
               (SELECT COUNT(*) FROM nucleo.acao_formativa a WHERE a.ine = pn.ine AND a.dt_acao <= pn.dt_fim) AS n_acoes
          FROM tmp_painel pn
          JOIN nucleo.equipe e        ON e.ine = pn.ine
          JOIN nucleo.unidade_saude u ON u.cnes = e.cnes
          JOIN nucleo.bairro b        ON b.id_bairro = u.id_bairro
          LEFT JOIN tmp_hellinger h   ON h.ine = pn.ine AND h.periodo = pn.periodo) z
WINDOW w AS (PARTITION BY z.ine ORDER BY z.periodo);

DROP TABLE tmp_versao, tmp_vig, tmp_fim_periodo, tmp_ref_raca, tmp_painel, tmp_hellinger;

-- RQ04 (modelo lógico, seção 6.4): distância de Hellinger entre a raça/cor registrada na equipe e
-- a referência do território, na data de corte. Limiar de alerta a calibrar com o gabarito.
CREATE OR REPLACE VIEW analitica.vw_rq04_raca_equipe AS
SELECT pm.ine, pm.id_ds, pm.dist_raca_cor_censo AS hellinger, pm.n_dado_real
  FROM analitica.fato_painel_ml pm
 WHERE pm.periodo = (SELECT MAX(periodo) FROM analitica.fato_painel_ml);
