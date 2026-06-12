"""Q.174 — RLS tenant_isolation em plan.worker_absence.

A q174a criou a tabela de overrides de ausência mas sem `ENABLE ROW
LEVEL SECURITY` + policy `tenant_isolation` — o gate
test_rls_table_coverage_q62_b apanhou-a. Mesmo padrão da 056/065
(USING/WITH CHECK em `current_setting('app.tenant_id', true)::uuid`,
ENABLE sem FORCE).

Revision ID: q174b_worker_absence_rls
Revises: q174a_worker_absence
Create Date: 2026-06-12
"""
from alembic import op


revision = "q174b_worker_absence_rls"
down_revision = "q174a_worker_absence"
branch_labels = None
depends_on = None

_SCHEMA, _TABLE = "plan", "worker_absence"


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF to_regclass('{_SCHEMA}.{_TABLE}') IS NOT NULL THEN
                EXECUTE 'ALTER TABLE {_SCHEMA}.{_TABLE} '
                      || 'ENABLE ROW LEVEL SECURITY';
                EXECUTE 'DROP POLICY IF EXISTS tenant_isolation '
                      || 'ON {_SCHEMA}.{_TABLE}';
                EXECUTE 'CREATE POLICY tenant_isolation ON {_SCHEMA}.{_TABLE} '
                      || 'USING (tenant_id = '
                      || 'current_setting(''app.tenant_id'', true)::uuid) '
                      || 'WITH CHECK (tenant_id = '
                      || 'current_setting(''app.tenant_id'', true)::uuid)';
            END IF;
        END $$
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF to_regclass('{_SCHEMA}.{_TABLE}') IS NOT NULL THEN
                EXECUTE 'DROP POLICY IF EXISTS tenant_isolation '
                      || 'ON {_SCHEMA}.{_TABLE}';
                EXECUTE 'ALTER TABLE {_SCHEMA}.{_TABLE} '
                      || 'DISABLE ROW LEVEL SECURITY';
            END IF;
        END $$
        """
    )
