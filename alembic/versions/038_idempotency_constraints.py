"""FASE 3.1 — schedule idempotency constraint (HIGH-42)

Adds the missing UNIQUE on
``plan.production_schedules(tenant_id, order_id, operation_id, planning_run_id)``
so a second call to ``SchedulingService.generate_schedule`` with the
same input no longer silently produces a parallel duplicate plan, and
downstream consumers (copilot, alerts, twin) have a deterministic
"current plan" to query.

HIGH-39 (legacy_id global unique → composite tenant + legacy_id on
``plan.production_orders``) is **deferred**: that table is currently
created by ``Base.metadata.create_all`` at startup, not by Alembic
(see project memory ``project_alembic_create_all_legacy.md``). Adding
an ``ALTER TABLE`` here would crash on a fresh DB before the app
starts. The fix becomes safe once ``create_all`` is removed and the
table moves into a regular migration.

Revision ID: 038_idempotency_constraints
Revises: 037_schedule_extra_fields_fase1b
Create Date: 2026-05-02
"""
from alembic import op


revision = '038_idempotency_constraints'
down_revision = '037_schedule_extra_fields_fase1b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_production_schedules_planning",
        "production_schedules",
        ["tenant_id", "order_id", "operation_id", "planning_run_id"],
        schema="plan",
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_production_schedules_planning",
        "production_schedules",
        schema="plan",
        type_="unique",
    )
