"""Create twin schema and scenario tables

Revision ID: 009_twin_scenarios
Revises: 008_pgvector
Create Date: 2026-04-16

Creates the Digital Twin persistence layer:
- Schema `twin`
- twin.twin_scenarios — scenario root (baseline, status, hash)
- twin.twin_scenario_deltas — ordered deltas applied to baseline
- twin.twin_scenario_comparisons — persisted KPI comparison results

Replaces the in-memory scenarios_store dict in src/twin/api.py.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '009_twin_scenarios'
down_revision = '008_pgvector'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS twin")

    op.create_table(
        'twin_scenarios',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('base_scenario_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('baseline_state', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('baseline_ingestion_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('simulation_result', postgresql.JSONB(), nullable=True),
        sa.Column('simulated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scenario_hash', sa.String(64), nullable=True),
        sa.Column('created_by', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ['base_scenario_id'],
            ['twin.twin_scenarios.id'],
            ondelete='SET NULL',
        ),
        sa.Index('ix_twin_scenarios_tenant_status', 'tenant_id', 'status'),
        sa.Index('ix_twin_scenarios_created_at', 'created_at'),
        schema='twin',
    )

    op.create_table(
        'twin_scenario_deltas',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('scenario_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_key', sa.String(255), nullable=False),
        sa.Column('patch', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('applied_by', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ['scenario_id'],
            ['twin.twin_scenarios.id'],
            ondelete='CASCADE',
        ),
        sa.Index('ix_twin_deltas_scenario', 'scenario_id'),
        schema='twin',
    )

    op.create_table(
        'twin_scenario_comparisons',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('scenario_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('baseline_scenario_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('comparison_result', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('kpi_deltas', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('compared_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('compared_by', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ['scenario_id'],
            ['twin.twin_scenarios.id'],
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['baseline_scenario_id'],
            ['twin.twin_scenarios.id'],
            ondelete='SET NULL',
        ),
        sa.Index('ix_twin_comparisons_scenarios', 'scenario_id', 'baseline_scenario_id'),
        schema='twin',
    )


def downgrade() -> None:
    op.drop_table('twin_scenario_comparisons', schema='twin')
    op.drop_table('twin_scenario_deltas', schema='twin')
    op.drop_table('twin_scenarios', schema='twin')
    op.execute("DROP SCHEMA IF EXISTS twin CASCADE")
