"""Q.117.D — profit.kpi_snapshot (série histórica de KPIs).

Guarda um ponto por (tenant, kpi_name, dia) para o gráfico de tendência
da página LLM › KPIs. Escrito uma vez por dia pelo job
``_kpi_snapshot_job``; lido por ``GET /v1/profit/kpis/{name}/history``.

``value`` é nullable — quando o KPI não tem dados nesse dia gravamos NULL
em vez de inventar um zero (ZERO MOCKS aplica-se também ao backend).

Revision ID: q117d_kpi_snapshot
Revises: q116d_boat_boost_and_snapshot
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "q117d_kpi_snapshot"
down_revision = "q116d_boat_boost_and_snapshot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS profit")
    op.create_table(
        "kpi_snapshot",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kpi_name", sa.String(40), nullable=False),
        sa.Column("captured_date", sa.Date(), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(8), nullable=False, server_default=""),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "kpi_name", "captured_date",
            name="uq_kpi_snapshot_tenant_kpi_date",
        ),
        schema="profit",
    )
    op.create_index(
        "ix_kpi_snapshot_tenant_kpi_date",
        "kpi_snapshot",
        ["tenant_id", "kpi_name", "captured_date"],
        schema="profit",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_kpi_snapshot_tenant_kpi_date",
        table_name="kpi_snapshot",
        schema="profit",
    )
    op.drop_table("kpi_snapshot", schema="profit")
