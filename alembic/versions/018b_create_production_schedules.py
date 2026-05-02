"""Create production_schedules table (FASE -1.2 — repair migration drift)

Revision ID: 018b_create_production_schedules
Revises: 018_quality_rework
Create Date: 2026-05-02

Background
----------
The ORM model `src.plan.models.schedule.ProductionSchedule` (table
``plan.production_schedules``) was never created by any Alembic migration.
In production it appeared because ``init_db()`` calls
``Base.metadata.create_all`` at startup. Migration 019 then adds columns
to a table that no migration creates, so ``alembic upgrade head`` on a
clean database fails at 019.

This migration creates the table to match the ORM exactly, restoring
Alembic as the single source of truth.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '018b_create_production_schedules'
down_revision = '018_quality_rework'
branch_labels = None
depends_on = None


SCHEDULE_STATUS_VALUES = (
    'DRAFT', 'SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED',
)


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS plan")

    schedule_status = postgresql.ENUM(
        *SCHEDULE_STATUS_VALUES,
        name='schedule_status',
        create_type=False,
    )
    schedule_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'production_schedules',
        # TenantBase columns
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),

        # Order reference
        sa.Column('order_id', sa.String(50), nullable=False),
        sa.Column('order_line', sa.Integer(), nullable=False, server_default='1'),

        # Product
        sa.Column(
            'product_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('core.products.id'),
            nullable=False,
        ),
        sa.Column('quantity', sa.Numeric(18, 6), nullable=False),

        # Operation
        sa.Column(
            'operation_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('core.operations.id'),
            nullable=False,
        ),
        sa.Column('operation_sequence', sa.Integer(), nullable=False, server_default='0'),

        # Machine
        sa.Column(
            'machine_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('core.machines.id'),
            nullable=True,
        ),

        # Scheduling
        sa.Column('scheduled_start_date', sa.Date(), nullable=False),
        sa.Column('scheduled_start_time', sa.Time(), nullable=True),
        sa.Column('scheduled_end_date', sa.Date(), nullable=False),
        sa.Column('scheduled_end_time', sa.Time(), nullable=True),

        # Duration
        sa.Column('scheduled_duration_hours', sa.Numeric(10, 2), nullable=True),
        sa.Column('setup_time_minutes', sa.Integer(), nullable=False, server_default='0'),

        # Assignment
        sa.Column('assigned_employee_id', postgresql.UUID(as_uuid=True), nullable=True),

        # Status
        sa.Column(
            'status',
            sa.Enum(
                *SCHEDULE_STATUS_VALUES,
                name='schedule_status',
                create_type=False,
            ),
            nullable=False,
            server_default='SCHEDULED',
        ),

        # Actuals
        sa.Column('actual_start', sa.DateTime(), nullable=True),
        sa.Column('actual_end', sa.DateTime(), nullable=True),
        sa.Column('actual_quantity', sa.Numeric(18, 6), nullable=True),

        # Batch
        sa.Column('batch_number', sa.String(50), nullable=True),
        sa.Column('sequence_in_machine', sa.Integer(), nullable=False, server_default='0'),

        # Planning metadata
        sa.Column('planning_run_id', sa.String(50), nullable=True),
        sa.Column('engine_used', sa.String(50), nullable=True),

        sa.Index('ix_production_schedules_tenant_id', 'tenant_id'),
        sa.Index('ix_production_schedules_order_id', 'order_id'),
        schema='plan',
    )


def downgrade() -> None:
    op.drop_table('production_schedules', schema='plan')
    schedule_status = postgresql.ENUM(
        *SCHEDULE_STATUS_VALUES,
        name='schedule_status',
        create_type=False,
    )
    schedule_status.drop(op.get_bind(), checkfirst=True)
