"""BUGFIX — RLS em falta na plan.plan_exclusion (criada na Q.153.C1 sem policy).

A tabela tem `tenant_id` mas a Q.153.C1 não activou Row Level Security, o que
deixava o canary `test_rls_table_coverage_q62_b` vermelho (toda a tabela tenant
tem de ter policy `tenant_isolation`). Fix mínimo: ENABLE RLS + policy padrão.

Revision ID: q155c_plan_exclusion_rls
Revises: q155b_phase_preferred_operator
Create Date: 2026-06-01
"""
from alembic import op

revision = "q155c_plan_exclusion_rls"
down_revision = "q155b_phase_preferred_operator"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # RLS — padrão Q.62.B (igual às restantes tabelas tenant).
    op.execute("ALTER TABLE plan.plan_exclusion ENABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON plan.plan_exclusion")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON plan.plan_exclusion
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON plan.plan_exclusion")
    op.execute("ALTER TABLE plan.plan_exclusion DISABLE ROW LEVEL SECURITY")
