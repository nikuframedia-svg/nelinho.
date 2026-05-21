-- Q.62.E.8 — Postgres RLS prod role provisioning.
--
-- Activa o RLS (criado em migration 056_q62_b_rls_enable) ao trocar o
-- DB user da app para um role non-superuser. Sem este passo, o RLS está
-- aplicado mas inerte: superuser bypassa policies por design.
--
-- COMO APLICAR (production):
--
--   psql -U postgres -h <host> -d <db> -f deploy/postgres/q62_rls_prod_role.sql
--
-- DEV/TEST: NÃO aplicar — o utilizador postgres é superuser por padrão
-- e o stack dev continua a funcionar sem o RLS efectivo. Aplicar só em
-- prod onde a fail-closed isolation é critical.
--
-- ROLLBACK (raro):
--   REVOKE nelinho_app FROM nelinho_user;
--   DROP ROLE nelinho_app;
--   ALTER USER nelinho_user WITH SUPERUSER;  -- só se necessario reverter
--
-- VERIFICAÇÃO POST-APPLY:
--   1. \du nelinho_user        -- deve mostrar "Cannot login" como FALSE
--   2. \du nelinho_app         -- deve mostrar "Cannot login" como TRUE
--   3. Login como nelinho_user; SELECT current_setting('app.tenant_id', true)
--      retorna '' (vazio) sem SET LOCAL — confirma que o ContextVar
--      middleware é necessário.
--   4. Tentar SELECT como tenant A (SET LOCAL) num row de tenant B → 0 rows.

-- ===========================================================================
-- 1) ROLE NON-SUPERUSER que será o EFFECTIVE role do nelinho_user
-- ===========================================================================

CREATE ROLE nelinho_app NOLOGIN;

-- Grants nos schemas que têm tabelas tenant-scoped (lista vem da
-- migration 056 + factory_curated/factory_meta para ETL).
GRANT USAGE ON SCHEMA
    plan, governance, quality, workforce, supply, core, hr, profit,
    dqa, twin, reports, shared, improve, sandbox,
    factory_curated, factory_meta, factory_raw
TO nelinho_app;

-- Permissões de DML em todas as tabelas existentes.
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA
    plan, governance, quality, workforce, supply, core, hr, profit,
    dqa, twin, reports, shared, improve, sandbox,
    factory_curated, factory_meta, factory_raw
TO nelinho_app;

-- Permissões nas sequences (IDs autoincremento etc).
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA
    plan, governance, quality, workforce, supply, core, hr, profit,
    dqa, twin, reports, shared, improve, sandbox,
    factory_curated, factory_meta, factory_raw
TO nelinho_app;

-- Tabelas futuras (criadas por novas migrations) herdam permissões.
ALTER DEFAULT PRIVILEGES IN SCHEMA
    plan, governance, quality, workforce, supply, core, hr, profit,
    dqa, twin, reports, shared, improve, sandbox,
    factory_curated, factory_meta, factory_raw
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO nelinho_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA
    plan, governance, quality, workforce, supply, core, hr, profit,
    dqa, twin, reports, shared, improve, sandbox,
    factory_curated, factory_meta, factory_raw
GRANT USAGE, SELECT ON SEQUENCES TO nelinho_app;

-- ===========================================================================
-- 2) APP USER inherits do nelinho_app
-- ===========================================================================

-- Tornar nelinho_user membro de nelinho_app (inherits permissions).
GRANT nelinho_app TO nelinho_user;

-- Force nelinho_user a correr SEMPRE como nelinho_app (não como superuser).
-- Critical: sem isto, mesmo membro de nelinho_app, queries correm como o
-- role do utilizador (superuser bypassa RLS).
ALTER USER nelinho_user SET ROLE nelinho_app;

-- Remove superuser flag se aplicável (idempotent; falha silencioso se
-- já é non-superuser).
ALTER USER nelinho_user WITH NOSUPERUSER;
