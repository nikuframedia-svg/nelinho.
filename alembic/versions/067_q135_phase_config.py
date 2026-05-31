"""Q.135.F3.1 — cria plan.phase_config (overrides de fase para o CPO).

Revision ID: 067_q135_phase_config
Revises: 066_q134_create_all_only
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "067_q135_phase_config"
down_revision = "066_q134_create_all_only"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "phase_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phase_id", sa.String(64), nullable=False),
        sa.Column("team_size_override", sa.Integer(), nullable=True),
        sa.Column("num_stations_override", sa.Integer(), nullable=True),
        sa.Column(
            "allowed_worker_ids",
            postgresql.ARRAY(sa.String()),
            nullable=True,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        # TenantBase fornece created_at + updated_at — ambos têm de existir.
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "tenant_id", "phase_id", name="uq_phase_config_tenant_phase"
        ),
        sa.Index("ix_phase_config_tenant", "tenant_id"),
        schema="plan",
    )

    # RLS tenant_isolation
    op.execute("ALTER TABLE plan.phase_config ENABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON plan.phase_config")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON plan.phase_config
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON plan.phase_config")
    op.drop_table("phase_config", schema="plan")
