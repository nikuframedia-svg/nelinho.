"""FASE 1B.4 (CRIT-23) — persist mold_batch_id, infeasible_reason, rule_used on plan.production_schedules

Auditoria PLANO (Decide) found that the CPO v4 decoder produces several
fields per scheduled op that the service-layer code (`scheduling_service.
generate_schedule`) silently dropped on the way to ProductionSchedule:

* ``mold_batch_id`` — Sprint I.4 multi-pocket batching identifier; needed
  for laminagem (WF11) traceability.
* ``infeasible_reason`` — short tag explaining why the op landed in
  ``infeasible_op_ids`` instead of being scheduled.
* ``rule_used`` — dispatch rule (EDD / SPT / WSPT / FIFO) that produced
  the assignment. Useful for post-hoc analysis of heuristic schedules.

``quality_risk_score`` (Numeric(5,4)) and ``quality_risk_scored_at``
already exist in the table — they were added by migration 019. This
migration only fills in the gaps.

This is a multi-head merge of the two pending heads at 035 — keeps the
graph linear from 037 onwards.

Revision ID: 037_schedule_extra_fields_fase1b
Revises: 035_s3_schema_drift, 035_sandbox_scenario_version
Create Date: 2026-05-02
"""
from alembic import op
import sqlalchemy as sa


revision = '037_schedule_extra_fields_fase1b'
# Sprint S6: 035_s3_schema_drift was renumbered to 036_s3_schema_drift to
# avoid a head collision with 035_sandbox_scenario_version. 036 already has
# 035_sandbox_scenario_version as its parent, so this becomes a single-parent
# linear migration.
down_revision = '036_s3_schema_drift'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'production_schedules',
        sa.Column('mold_batch_id', sa.String(length=64), nullable=True),
        schema='plan',
    )
    op.add_column(
        'production_schedules',
        sa.Column('infeasible_reason', sa.String(length=255), nullable=True),
        schema='plan',
    )
    op.add_column(
        'production_schedules',
        sa.Column('rule_used', sa.String(length=32), nullable=True),
        schema='plan',
    )
    op.create_index(
        'ix_production_schedules_mold_batch',
        'production_schedules',
        ['mold_batch_id'],
        schema='plan',
    )


def downgrade() -> None:
    op.drop_index(
        'ix_production_schedules_mold_batch',
        table_name='production_schedules',
        schema='plan',
    )
    op.drop_column('production_schedules', 'rule_used', schema='plan')
    op.drop_column('production_schedules', 'infeasible_reason', schema='plan')
    op.drop_column('production_schedules', 'mold_batch_id', schema='plan')
