"""Q.62.B.1 — Postgres RLS enable + tenant_isolation policies.

Defense in depth: a app ja filtra `tenant_id = current_tenant_id()`
manualmente em todos os call-sites (Q.12 Onda 0.1 require_tenant_header),
mas qualquer bug que esqueca o filtro deixaria vazar dados cross-tenant.
RLS no Postgres torna o filtro automatico ao nivel da DB.

Cada query corre com `current_setting('app.tenant_id')` setado pelo
event listener (Q.62.B.2 em src/shared/database.py). RLS rejeita rows
onde `tenant_id != current_setting('app.tenant_id')`.

NOTA: superuser bypassa RLS. App tem de correr como utilizador
non-superuser. No dev (utilizador `postgres`), policies estao
configuradas mas inertes ate o app correr como role apropriado.
Q.62.B.2 documenta o setup de role + grants.

Tabelas alvo: 87 tabelas com coluna `tenant_id`, distribuidas por 14
schemas (plan/core/governance/supply/hr/profit/quality/dqa/twin/reports/
shared/improve/sandbox/public).

Tabelas EXCLUIDAS (nao tem tenant_id):
  * core.tenants (tabela DOS tenants)
  * factory_curated.* (curated layer — tenant-agnostic)
  * factory_meta.* (ingestion meta — tenant-agnostic)
  * factory_raw.* (raw layer — tenant-agnostic)
  * public.event_dlq (DLQ global)
  * shared.decision_approvals (legacy, tenant_id via JOIN)

Revision ID: 056_q62_b_rls_enable
Revises: 055a_q62_a3_orphans
Create Date: 2026-05-20
"""
from alembic import op


revision = "056_q62_b_rls_enable"
down_revision = "055a_q62_a3_orphans"
branch_labels = None
depends_on = None


# 87 tables with tenant_id column. Gerado via introspecao de
# Base.metadata em Q.62.B.1 setup. Manter sincronizado com novos
# modelos (test_rls_table_coverage_q62_b vai pinar).
TABLES_WITH_TENANT_ID = [
    ("public", "copilot_action_logs"),
    ("public", "copilot_alerts"),
    ("public", "copilot_conversation"),
    ("public", "copilot_daily_feedback"),
    ("public", "copilot_decision_pr"),
    ("public", "copilot_message"),
    ("public", "copilot_rag_chunk"),
    ("public", "copilot_suggestion"),
    ("public", "copilot_user_feedback"),
    ("public", "event_outbox"),
    ("public", "ml_model_artifact"),
    ("public", "plan_schedule_commits"),
    ("core", "audit_log"),
    ("core", "bom_items"),
    ("core", "customers"),
    ("core", "employees"),
    ("core", "etl_run"),
    ("core", "labor_rates"),
    ("core", "machine_rates"),
    ("core", "machines"),
    ("core", "operations"),
    ("core", "overhead_rates"),
    ("core", "products"),
    ("core", "suppliers"),
    ("core", "tenant_configuration"),
    ("dqa", "auto_repair_logs"),
    ("dqa", "data_quality_issues"),
    ("dqa", "trust_index_snapshots"),
    ("governance", "approval"),
    ("governance", "causal_discovery_report"),
    ("governance", "decision_policy"),
    ("governance", "decision_run"),
    ("governance", "kill_switch_active"),
    ("governance", "preference_rule"),
    ("governance", "rule_firing"),
    ("governance", "yaml_policy_rule"),
    ("governance", "yaml_policy_rule_revision"),
    ("hr", "employee_productivity"),
    ("hr", "employee_skills"),
    ("hr", "hr_allocations"),
    ("hr", "legacy_allocations"),
    ("hr", "monthly_payroll_summary"),
    ("hr", "shift_schedules"),
    ("hr", "skills"),
    ("improve", "improvement_suggestions"),
    ("plan", "factory_calendar_day"),
    ("plan", "material_requirements"),
    ("plan", "model_routing_assignment"),
    ("plan", "mold"),
    ("plan", "mold_defect_log"),
    ("plan", "mold_health"),
    ("plan", "mold_maintenance_event"),
    ("plan", "mold_usage_counter"),
    ("plan", "phase_transition_gap"),
    ("plan", "production_errors"),
    ("plan", "production_orders"),
    ("plan", "production_schedules"),
    ("plan", "purchase_orders"),
    ("plan", "routing_template"),
    ("plan", "routing_template_phase"),
    ("plan", "transport_batch"),
    ("plan", "transport_batch_assignment"),
    ("profit", "cost_calculations"),
    ("profit", "order_revenue"),
    ("profit", "phase_bonus_payout"),
    ("profit", "pricing_recommendations"),
    ("profit", "product_pricing"),
    ("profit", "profit_scenarios"),
    ("profit", "shipping_rate"),
    ("quality", "error_catalog"),
    ("quality", "rework_entry"),
    ("reports", "report_run"),
    ("reports", "report_schedule"),
    ("sandbox", "sandbox_scenarios"),
    ("shared", "decision_runs"),
    ("shared", "users"),
    ("supply", "inventory_ledger_entries"),
    ("supply", "purchase_orders"),
    ("supply", "supply_forecasts"),
    ("supply", "supply_material_in_transit"),
    ("supply", "supply_material_master"),
    ("supply", "supply_rop_configs"),
    ("supply", "supply_stock_reconciliation"),
    ("supply", "warehouse_stock"),
    ("twin", "twin_scenario_comparisons"),
    ("twin", "twin_scenario_deltas"),
    ("twin", "twin_scenarios"),
]


def upgrade() -> None:
    for schema, table in TABLES_WITH_TENANT_ID:
        # ENABLE ROW LEVEL SECURITY (idempotent via IF EXISTS check
        # implicito do erro — sem `IF NOT EXISTS` em ALTER TABLE).
        op.execute(
            f"ALTER TABLE {schema}.{table} ENABLE ROW LEVEL SECURITY"
        )
        # DROP policy primeiro para idempotency (re-running esta migration
        # em DB ja tratada nao falha).
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
