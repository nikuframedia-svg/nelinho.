-- Q.67.4.A — Postgres role read-only para o copilot SQL livre.
--
-- O copiloto (Ollama on-prem) ganha capacidade de gerar SQL SELECT
-- contra a BD inteira via o tool `run_sql` (src/copilot/tools/sql_runner.py).
-- Esta capacidade requer uma conexão Postgres separada que NÃO consegue
-- escrever, drop tables, ou criar objects — defense-in-depth contra
-- prompt injection que tente forçar INSERT/UPDATE/DELETE.
--
-- O sql_runner.py também faz regex SELECT-only check + statement_timeout
-- 5s + cap de 200 rows. Este role é a 3ª camada de segurança (RBAC DB).
--
-- COMO APLICAR (production):
--
--   psql -U postgres -h <host> -d <db> -f deploy/postgres/q67_copilot_role.sql
--
-- Depois, set COPILOT_DATABASE_URL em .env / systemd unit:
--   COPILOT_DATABASE_URL=postgresql+asyncpg://nelinho_copilot:<senha>@<host>:5432/prodplan_one
--
-- DEV/TEST: NÃO aplicar. Em dev, COPILOT_DATABASE_URL fica unset; o
-- sql_runner cai-back para `database_url` (regex protege na mesma).
--
-- ROLLBACK:
--   DROP ROLE nelinho_copilot;
--
-- VERIFICAÇÃO POST-APPLY:
--   1. `\du nelinho_copilot`  -- mostra "Cannot login" como FALSE
--   2. Login como nelinho_copilot:
--        psql -h localhost -U nelinho_copilot -d prodplan_one
--   3. `SELECT 1;`              -- 200 OK
--   4. `INSERT INTO plan.production_orders VALUES (...);`
--        -- ERROR: permission denied for table production_orders
--   5. `CREATE TABLE t (id int);`
--        -- ERROR: permission denied for schema public
--   6. `DROP TABLE plan.production_orders;`
--        -- ERROR: must be owner of table production_orders

-- ===========================================================================
-- 1) Criar role nelinho_copilot (LOGIN, SELECT-only).
-- ===========================================================================

CREATE ROLE nelinho_copilot WITH
    LOGIN
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOREPLICATION
    PASSWORD 'change-me-via-env-var';

-- Em prod, mudar a senha pós-create:
--   ALTER ROLE nelinho_copilot WITH PASSWORD '<senha-forte-do-env>';

-- ===========================================================================
-- 2) GRANT SELECT em todas as schemas do nelinho.
-- ===========================================================================

DO $$
DECLARE
    schema_name text;
BEGIN
    FOR schema_name IN
        SELECT nspname
        FROM pg_namespace
        WHERE nspname IN (
            'plan', 'core', 'supply', 'hr', 'quality', 'profit', 'governance',
            'dqa', 'twin', 'factory_curated', 'factory_meta', 'factory_raw',
            'reports', 'shared', 'improve', 'sandbox', 'public'
        )
    LOOP
        EXECUTE format('GRANT USAGE ON SCHEMA %I TO nelinho_copilot', schema_name);
        EXECUTE format('GRANT SELECT ON ALL TABLES IN SCHEMA %I TO nelinho_copilot', schema_name);
        EXECUTE format('GRANT SELECT ON ALL SEQUENCES IN SCHEMA %I TO nelinho_copilot', schema_name);
        -- Para tabelas criadas no futuro, default grant.
        EXECUTE format(
            'ALTER DEFAULT PRIVILEGES IN SCHEMA %I '
            'GRANT SELECT ON TABLES TO nelinho_copilot', schema_name);
        EXECUTE format(
            'ALTER DEFAULT PRIVILEGES IN SCHEMA %I '
            'GRANT SELECT ON SEQUENCES TO nelinho_copilot', schema_name);
    END LOOP;
END $$;

-- ===========================================================================
-- 3) Verificação inline (não falha se 0 rows; só informativo).
-- ===========================================================================

DO $$
DECLARE
    granted_tables int;
BEGIN
    SELECT count(*) INTO granted_tables
    FROM information_schema.table_privileges
    WHERE grantee = 'nelinho_copilot' AND privilege_type = 'SELECT';
    RAISE NOTICE 'nelinho_copilot can SELECT from % tables', granted_tables;
END $$;

-- ===========================================================================
-- 4) Notas de operacao.
-- ===========================================================================

-- RLS (Row-Level Security):
--   Q.62.B (migration 056) activou RLS em 87 tabelas. nelinho_copilot
--   herda essas policies — não bypassa. Logo, o copiloto SÓ vê dados do
--   tenant configurado via SET LOCAL app.tenant_id (TenantContextMiddleware).
--
-- Audit log:
--   Cada query do copilot é loggada em core.audit_log com
--   subject_type='copilot_query', payload={sql, rows_returned, elapsed_ms}.
--   Permite forensics se houver prompt injection bem-sucedida.
--
-- Cleanup:
--   Retention: cleanup nightly de copilot_query audit_log >30 dias
--   (scheduler job a configurar em Q.67.4.E).
