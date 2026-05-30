"""Q.R-audit — RLS tenant_isolation nas 7 tabelas em falta.

Auditoria 2026-05-30 (§7): tabelas tenant criadas DEPOIS da 056_q62_b_rls_enable
ficaram sem `ENABLE ROW LEVEL SECURITY` + policy `tenant_isolation`, deixando o
isolamento RLS inerte para elas. Esta migração fecha o buraco com o MESMO padrão
da 056 (USING/WITH CHECK em `current_setting('app.tenant_id', true)::uuid`).

POSTURA: `ENABLE` sem `FORCE` (espelha a 056, confirmado com o utilizador).
No dev o `postgres` é superuser → RLS inerte (não parte o dev de 1 tenant). Em
prod a app corre como role non-superuser (`nelinho_app`, ver
deploy/postgres/q62_rls_prod_role.sql) e a policy aplica-se sem precisar de FORCE.
Se algum dia a app ligar como OWNER da tabela, será preciso adicionar
`ALTER TABLE ... FORCE ROW LEVEL SECURITY` — deixado como follow-up de deploy.

As 7 tabelas (todas com coluna `tenant_id`):
  * core.encomendas_cancelled
  * plan.boat_boost
  * plan.order_boost
  * plan.phase_duration_calibration
  * plan.plan_execution_observed
  * plan.work_order_override
  * profit.kpi_snapshot

Revision ID: 065_qr_audit_rls
Revises: 064_qr_audit_drift
Create Date: 2026-05-30
"""
from alembic import op


revision = "065_qr_audit_rls"
down_revision = "064_qr_audit_drift"
branch_labels = None
depends_on = None


# (schema, table) — tenant tables que faltavam na 056. Manter sincronizado
# com Base.metadata (test_rls_table_coverage_q62_b pina a cobertura total).
TABLES_WITH_TENANT_ID = [
    ("core", "encomendas_cancelled"),
    ("plan", "boat_boost"),
    ("plan", "order_boost"),
    ("plan", "phase_duration_calibration"),
    ("plan", "plan_execution_observed"),
    ("plan", "work_order_override"),
    ("profit", "kpi_snapshot"),
]


def upgrade() -> None:
    for schema, table in TABLES_WITH_TENANT_ID:
        op.execute(
            f"ALTER TABLE {schema}.{table} ENABLE ROW LEVEL SECURITY"
        )
        # DROP primeiro para idempotency (re-run não falha).
        op.execute(
            f"DROP POLICY IF EXISTS tenant_isolation ON {schema}.{table}"
        )
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {schema}.{table}
                USING (
                    tenant_id = current_setting('app.tenant_id', true)::uuid
                )
                WITH CHECK (
                    tenant_id = current_setting('app.tenant_id', true)::uuid
                )
            """
        )


def downgrade() -> None:
    for schema, table in reversed(TABLES_WITH_TENANT_ID):
        op.execute(
            f"DROP POLICY IF EXISTS tenant_isolation ON {schema}.{table}"
        )
        op.execute(
            f"ALTER TABLE {schema}.{table} DISABLE ROW LEVEL SECURITY"
        )
