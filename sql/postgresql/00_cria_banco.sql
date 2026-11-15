-- =====================================================================
-- Emulação de dados da APS para as políticas de equidade do Recife
-- 00 – Criação do usuário e do banco (rodar UMA vez, como superusuário "postgres")
-- Projeto 3 – Dados (CESAR School, 2026.2) · Equipe 2 – Nexus Data
--
-- Cria o usuário "aps" (senha "aps") e o banco "aps_recife", que batem com o DSN padrão do
-- carregador (postgresql://aps:aps@localhost:5432/aps_recife). Assim APS_DSN é opcional.
-- O usuário "aps" é dono do banco: o carregador recria os esquemas stg, nucleo e analitica
-- a cada carga (DROP/CREATE SCHEMA) e não precisa de superusuário nem de extensões.
--
-- Uso (Windows, PowerShell, na raiz do repositório):
--   & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -h localhost -f sql\postgresql\00_cria_banco.sql
-- Em equipe/rede, troque a senha abaixo e ajuste APS_DSN no .env.
-- =====================================================================

\set ON_ERROR_STOP on

-- 1. usuário da aplicação (só cria se não existir)
SELECT 'CREATE ROLE aps LOGIN PASSWORD ''aps'''
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'aps') \gexec

-- 2. banco em UTF-8, independente da página de código do Windows (WIN1252).
--    O provedor "builtin" com C.UTF-8 (PostgreSQL 17 ou superior) dá ordenação estável,
--    igual em Windows e Linux. As chaves substitutas usam COLLATE "C" de qualquer forma.
SELECT 'CREATE DATABASE aps_recife OWNER aps ENCODING ''UTF8'' TEMPLATE template0 '
       || CASE WHEN current_setting('server_version_num')::int >= 170000
               THEN 'LOCALE_PROVIDER builtin BUILTIN_LOCALE ''C.UTF-8'' LOCALE ''C'''
               ELSE 'LOCALE ''C''' END
 WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'aps_recife') \gexec

-- 3. parâmetros da sessão do banco (valem para qualquer cliente: Python, psql, pgAdmin, Power BI)
ALTER DATABASE aps_recife SET client_encoding = 'UTF8';
ALTER DATABASE aps_recife SET datestyle = 'ISO, DMY';
ALTER DATABASE aps_recife SET timezone = 'America/Recife';

-- 4. só o dono conecta e cria objetos; o resto do servidor não enxerga o banco
REVOKE ALL ON DATABASE aps_recife FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE aps_recife TO aps;

\echo 'Pronto: banco aps_recife (dono aps). Teste com: psql -U aps -h localhost -d aps_recife -c "SELECT version();"'
