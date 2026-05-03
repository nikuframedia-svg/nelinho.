"""Sprint Q.13.F F.3 — composite indexes for the dashboard hot path.

The CEO dashboard, capacity views, and the worker tablet queue all
filter ``ProductionSchedule`` by ``(tenant_id, ...)`` plus a date range
or a foreign-key column. With only the existing per-column indexes,
Postgres falls back to scanning the leading-column index then
filtering — fine at 50k rows, painful past 500k.

Five composite indexes added:

1. ``(tenant_id, scheduled_start_date)``  — backbone for every date-
   range query (dashboard tiles, weekly capacity panel).
2. ``(tenant_id, machine_id, scheduled_start_date)`` — capacity per
   machine across a window.
3. ``(tenant_id, assigned_employee_id, scheduled_start_date)`` —
   worker queue and "operations today" tablet endpoint.
4. ``(tenant_id, status)`` — status-filtered dashboards (planned vs
   executed vs cancelled).
5. ``(tenant_id, status, executed_at)`` on ``governance.decision_run``
   so the daily ``improve_adoption_signal`` job (Sprint Q.13.D D.3)
   doesn't full-scan the table.

Postgres ``CREATE INDEX IF NOT EXISTS`` for safety: re-running the
migration on an already-indexed DB is a no-op rather than an error.

Revision ID: 042_hot_query_indexes
Revises: 041_causal_discovery_report
Create Date: 2026-05-03
"""

from alembic import op


revision = "042_hot_query_indexes"
down_revision = "041_causal_discovery_report"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── plan.production_schedules ────────────────────────────────────
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_prod_sched_tenant_start_date
        ON plan.production_schedules (tenant_id, scheduled_start_date)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_prod_sched_tenant_machine_date
        ON plan.production_schedules (tenant_id, machine_id, scheduled_start_date)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_prod_sched_tenant_employee_date
        ON plan.production_schedules (tenant_id, assigned_employee_id, scheduled_start_date)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_prod_sched_tenant_status
        ON plan.production_schedules (tenant_id, status)
    """)

    # ── governance.decision_run ──────────────────────────────────────
    # Sprint Q.13.D D.3 — improve_adoption_signal_job filters
    # tenant + status IN (...) + executed_at >= cutoff.
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_decision_run_tenant_status_executed_at
        ON governance.decision_run (tenant_id, status, executed_at)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS plan.ix_prod_sched_tenant_start_date")
    op.execute("DROP INDEX IF EXISTS plan.ix_prod_sched_tenant_machine_date")
    op.execute("DROP INDEX IF EXISTS plan.ix_prod_sched_tenant_employee_date")
    op.execute("DROP INDEX IF EXISTS plan.ix_prod_sched_tenant_status")
    op.execute(
        "DROP INDEX IF EXISTS governance.ix_decision_run_tenant_status_executed_at"
    )
