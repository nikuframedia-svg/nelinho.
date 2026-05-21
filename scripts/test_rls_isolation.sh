#!/usr/bin/env bash
# Q.68.6.A — RLS isolation smoke (prod-like, requires `nelinho_app` role).
#
# Prova ponta-a-ponta que o RLS criado em migration 056_q62_b_rls_enable é
# ACTIVO: tenant A não vê linhas de tenant B, e uma sessão sem
# `SET LOCAL app.tenant_id` é fail-closed (0 rows). Em dev o user é
# superuser por design — RLS está aplicado mas inerte (ver
# `agent_docs/multi_tenant_architecture.md`). Este script só corre verde
# em prod ou num dev onde `deploy/postgres/q62_rls_prod_role.sql` foi
# aplicado.
#
# PRÉ-REQUISITOS:
#   - Postgres 16 up, role `nelinho_app` criada via
#     `deploy/postgres/q62_rls_prod_role.sql` (passo 1× por máquina).
#   - Alembic upgrade head já corrido (RLS policies em 87 tabelas).
#   - `nelinho_app` tem password configurável via NELINHO_APP_PASSWORD
#     (default = "nelinho_app_dev"; em prod, vault).
#
# USO:
#   bash scripts/test_rls_isolation.sh
#   bash scripts/test_rls_isolation.sh --report agent_docs/q68_rls_smoke_results.md
#
# EXIT CODES:
#   0 = isolation provada (A=1, B=1, none=0)
#   1 = isolation falhou OU pré-requisito em falta
#
# CARRY-FORWARD:
#   Quando este script correr verde na máquina NELO (Q.69), copiar output
#   para `agent_docs/q68_rls_smoke_results.md` secção "Run real".

set -euo pipefail

# ---------------------------------------------------------------------------
# Config (override via env)
# ---------------------------------------------------------------------------
PG_SUPERUSER="${POSTGRES_USER:-postgres}"
PG_HOST="${POSTGRES_HOST:-localhost}"
PG_PORT="${POSTGRES_PORT:-5432}"
PG_DB="${POSTGRES_DB:-prodplan_one}"
APP_USER="nelinho_app"
APP_PASSWORD="${NELINHO_APP_PASSWORD:-nelinho_app_dev}"

TENANT_A="11111111-1111-1111-1111-111111111111"
TENANT_B="22222222-2222-2222-2222-222222222222"

REPORT_FILE=""
if [[ "${1:-}" == "--report" && -n "${2:-}" ]]; then
    REPORT_FILE="$2"
fi

# Helpers ------------------------------------------------------------------
psql_super() {
    psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_SUPERUSER" -d "$PG_DB" \
         -v ON_ERROR_STOP=1 "$@"
}

psql_app() {
    PGPASSWORD="$APP_PASSWORD" psql -h "$PG_HOST" -p "$PG_PORT" \
        -U "$APP_USER" -d "$PG_DB" -v ON_ERROR_STOP=1 -t -A "$@"
}

log() {
    echo "[$(date +%H:%M:%S)] $*"
}

cleanup() {
    log "→ Cleanup: remove test rows + tenants"
    psql_super -c "
        DELETE FROM plan.production_orders
         WHERE tenant_id IN ('$TENANT_A', '$TENANT_B');
        DELETE FROM core.tenants
         WHERE id IN ('$TENANT_A', '$TENANT_B');
    " >/dev/null || log "  (cleanup warning — continuar)"
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Step 1 — verify nelinho_app role exists (fail-closed para dev superuser)
# ---------------------------------------------------------------------------
log "→ Step 1: Verify nelinho_app role exists"
ROLE_EXISTS=$(psql_super -t -A -c \
    "SELECT 1 FROM pg_roles WHERE rolname='$APP_USER';")
if [[ "$ROLE_EXISTS" != "1" ]]; then
    cat <<EOF
ERROR: role '$APP_USER' não existe.

Este smoke prova RLS prod-like — precisa do role non-superuser.
Em dev (superuser), o RLS está aplicado mas inerte by design.

Para correr:
    psql -U postgres -d $PG_DB -f deploy/postgres/q62_rls_prod_role.sql

Depois volta a correr este script.
EOF
    exit 1
fi
log "   OK — role '$APP_USER' presente"

# ---------------------------------------------------------------------------
# Step 2 — verify RLS está enabled em plan.production_orders
# ---------------------------------------------------------------------------
log "→ Step 2: Verify RLS enabled em plan.production_orders"
RLS_ENABLED=$(psql_super -t -A -c "
    SELECT relrowsecurity::int
      FROM pg_class
      JOIN pg_namespace ON pg_namespace.oid = pg_class.relnamespace
     WHERE nspname='plan' AND relname='production_orders';
")
if [[ "$RLS_ENABLED" != "1" ]]; then
    echo "ERROR: RLS não está enabled em plan.production_orders."
    echo "Corre 'alembic upgrade head' (migration 056_q62_b_rls_enable)."
    exit 1
fi
log "   OK — relrowsecurity=1"

# ---------------------------------------------------------------------------
# Step 3 — criar 2 tenants (idempotente)
# ---------------------------------------------------------------------------
log "→ Step 3: Create tenants A + B"
psql_super -c "
    INSERT INTO core.tenants (
        id, tenant_name, tenant_code, status, subscription_level,
        timezone, currency_code, locale, created_at, updated_at
    ) VALUES
        ('$TENANT_A', 'Tenant A — RLS smoke', 'RLS_SMOKE_A',
         'ACTIVE', 'STARTER', 'Europe/Lisbon', 'EUR', 'pt-PT',
         now(), now()),
        ('$TENANT_B', 'Tenant B — RLS smoke', 'RLS_SMOKE_B',
         'ACTIVE', 'STARTER', 'Europe/Lisbon', 'EUR', 'pt-PT',
         now(), now())
    ON CONFLICT (id) DO NOTHING;
" >/dev/null
log "   OK — 2 tenants em core.tenants"

# ---------------------------------------------------------------------------
# Step 4 — popular 1 production_order por tenant (via superuser, bypass RLS)
# ---------------------------------------------------------------------------
log "→ Step 4: Populate 1 production_order por tenant"
psql_super -c "
    INSERT INTO plan.production_orders (
        id, tenant_id, legacy_id, product_name, product_type,
        current_phase_name, status, created_at, updated_at
    ) VALUES
        (gen_random_uuid(), '$TENANT_A', 999001, 'Kayak Smoke A', 'K1',
         'Fase 01', 'IN_PROGRESS', now(), now()),
        (gen_random_uuid(), '$TENANT_B', 999002, 'Kayak Smoke B', 'K1',
         'Fase 01', 'IN_PROGRESS', now(), now())
    ON CONFLICT (legacy_id) DO NOTHING;
" >/dev/null
log "   OK — 2 linhas (1 por tenant)"

# ---------------------------------------------------------------------------
# Step 5 — SET LOCAL tenant_id=A → expect 1
# ---------------------------------------------------------------------------
log "→ Step 5: Login as nelinho_app, SET LOCAL tenant_id=A"
COUNT_A=$(psql_app -c "
    BEGIN;
    SET LOCAL app.tenant_id = '$TENANT_A';
    SELECT count(*) FROM plan.production_orders
     WHERE legacy_id IN (999001, 999002);
    COMMIT;
")
COUNT_A="${COUNT_A//[$'\t\r\n ']/}"
log "   Tenant A sees: $COUNT_A row(s) (expected: 1)"

# ---------------------------------------------------------------------------
# Step 6 — SET LOCAL tenant_id=B → expect 1
# ---------------------------------------------------------------------------
log "→ Step 6: SET LOCAL tenant_id=B"
COUNT_B=$(psql_app -c "
    BEGIN;
    SET LOCAL app.tenant_id = '$TENANT_B';
    SELECT count(*) FROM plan.production_orders
     WHERE legacy_id IN (999001, 999002);
    COMMIT;
")
COUNT_B="${COUNT_B//[$'\t\r\n ']/}"
log "   Tenant B sees: $COUNT_B row(s) (expected: 1)"

# ---------------------------------------------------------------------------
# Step 7 — sem SET LOCAL → expect 0 (fail-closed)
# ---------------------------------------------------------------------------
log "→ Step 7: Sem SET LOCAL (fail-closed)"
COUNT_NONE=$(psql_app -c "
    SELECT count(*) FROM plan.production_orders
     WHERE legacy_id IN (999001, 999002);
")
COUNT_NONE="${COUNT_NONE//[$'\t\r\n ']/}"
log "   Sem SET LOCAL: $COUNT_NONE row(s) (expected: 0)"

# ---------------------------------------------------------------------------
# Step 8 — cross-tenant write attempt: tenant A tenta INSERT como tenant B
# ---------------------------------------------------------------------------
log "→ Step 8: Cross-tenant write — A tenta INSERT como B"
set +e
CROSS_WRITE_OUT=$(PGPASSWORD="$APP_PASSWORD" psql -h "$PG_HOST" -p "$PG_PORT" \
    -U "$APP_USER" -d "$PG_DB" -v ON_ERROR_STOP=1 -t -A -c "
    BEGIN;
    SET LOCAL app.tenant_id = '$TENANT_A';
    INSERT INTO plan.production_orders (
        id, tenant_id, legacy_id, product_name, product_type,
        current_phase_name, status, created_at, updated_at
    ) VALUES (
        gen_random_uuid(), '$TENANT_B', 999003, 'Cross-tenant attack',
        'K1', 'Fase 01', 'IN_PROGRESS', now(), now()
    );
    COMMIT;
" 2>&1)
CROSS_WRITE_RC=$?
set -e
if [[ $CROSS_WRITE_RC -eq 0 ]]; then
    log "   FAIL — INSERT cross-tenant foi aceite (RLS partido)"
    CROSS_WRITE_BLOCKED=0
else
    log "   OK — INSERT cross-tenant rejeitado pelo RLS"
    CROSS_WRITE_BLOCKED=1
fi

# ---------------------------------------------------------------------------
# Pass/fail
# ---------------------------------------------------------------------------
PASS=1
[[ "$COUNT_A" == "1" ]] || PASS=0
[[ "$COUNT_B" == "1" ]] || PASS=0
[[ "$COUNT_NONE" == "0" ]] || PASS=0
[[ "$CROSS_WRITE_BLOCKED" == "1" ]] || PASS=0

echo
if [[ $PASS -eq 1 ]]; then
    echo "RLS isolation PASSED"
    echo "  - Tenant A: $COUNT_A (esperado 1)"
    echo "  - Tenant B: $COUNT_B (esperado 1)"
    echo "  - Sem SET LOCAL: $COUNT_NONE (esperado 0)"
    echo "  - Cross-tenant INSERT bloqueado: sim"
    RESULT="PASSED"
else
    echo "RLS isolation FAILED"
    echo "  - Tenant A: $COUNT_A (esperado 1)"
    echo "  - Tenant B: $COUNT_B (esperado 1)"
    echo "  - Sem SET LOCAL: $COUNT_NONE (esperado 0)"
    echo "  - Cross-tenant INSERT bloqueado: $CROSS_WRITE_BLOCKED (esperado 1)"
    RESULT="FAILED"
fi

if [[ -n "$REPORT_FILE" ]]; then
    log "→ Append run summary to $REPORT_FILE"
    {
        echo
        echo "## Run $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
        echo
        echo "- Host: $PG_HOST:$PG_PORT  DB: $PG_DB"
        echo "- Tenant A count: $COUNT_A"
        echo "- Tenant B count: $COUNT_B"
        echo "- No-tenant count: $COUNT_NONE"
        echo "- Cross-tenant INSERT blocked: $CROSS_WRITE_BLOCKED"
        echo "- Result: **$RESULT**"
    } >> "$REPORT_FILE"
fi

[[ $PASS -eq 1 ]] && exit 0 || exit 1
