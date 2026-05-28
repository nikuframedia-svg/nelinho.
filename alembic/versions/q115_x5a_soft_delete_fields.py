"""Q.115.X5.A — Soft-delete fields: production_orders, core.products, core.employees.

Adiciona colunas de soft-delete para suportar cancel/retire/deactivate
sem DROP de rows (histórico preservado para ML).

Revision ID: q115_x5a_soft_delete_fields
Revises: q115_a10_ml_drift_event
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "q115_x5a_soft_delete_fields"
down_revision = "q115_a10_ml_drift_event"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── plan.production_orders ──────────────────────────────────────────────
    # A tabela já existe com coluna `status` (String(20)); acrescentamos
    # os campos de cancelamento. Não alteramos o enum existente — o status
    # 'CANCELLED' já está definido no model OrderStatus.
    op.add_column(
        "production_orders",
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        schema="plan",
    )
    op.add_column(
        "production_orders",
        sa.Column("cancelled_by", sa.String(255), nullable=True),
        schema="plan",
    )
    op.add_column(
        "production_orders",
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        schema="plan",
    )

    # ── core.products ──────────────────────────────────────────────────────
    op.add_column(
        "products",
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        schema="core",
    )
    op.add_column(
        "products",
        sa.Column("retired_by", sa.String(255), nullable=True),
        schema="core",
    )
    op.add_column(
        "products",
        sa.Column("retirement_reason", sa.Text(), nullable=True),
        schema="core",
    )

    # ── core.employees ─────────────────────────────────────────────────────
    op.add_column(
        "employees",
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        schema="core",
    )
    op.add_column(
        "employees",
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        schema="core",
    )
    op.add_column(
        "employees",
        sa.Column("deactivated_by", sa.String(255), nullable=True),
        schema="core",
    )
    op.add_column(
        "employees",
        sa.Column("deactivation_reason", sa.Text(), nullable=True),
        schema="core",
    )

    # ── Tabela encomendas_cancelled (nova) ─────────────────────────────────
    # Não escrevemos no ERP directamente — guardamos o cancelamento aqui.
    op.execute("CREATE SCHEMA IF NOT EXISTS core")
    op.create_table(
        "encomendas_cancelled",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("encomenda_id", sa.String(100), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("cancelled_by", sa.String(255), nullable=False),
        sa.Column(
            "cancelled_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("audit_trace_id", sa.String(64), nullable=True),
        schema="core",
    )
    op.create_index(
        "ix_core_encomendas_cancelled_tenant_id",
        "encomendas_cancelled",
        ["tenant_id"],
        schema="core",
    )
    op.create_index(
        "ix_core_encomendas_cancelled_encomenda_id",
        "encomendas_cancelled",
        ["encomenda_id"],
        schema="core",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_core_encomendas_cancelled_encomenda_id",
        table_name="encomendas_cancelled",
        schema="core",
    )
    op.drop_index(
        "ix_core_encomendas_cancelled_tenant_id",
        table_name="encomendas_cancelled",
        schema="core",
    )
    op.drop_table("encomendas_cancelled", schema="core")

    op.drop_column("employees", "deactivation_reason", schema="core")
    op.drop_column("employees", "deactivated_by", schema="core")
    op.drop_column("employees", "deactivated_at", schema="core")
    op.drop_column("employees", "active", schema="core")

    op.drop_column("products", "retirement_reason", schema="core")
    op.drop_column("products", "retired_by", schema="core")
    op.drop_column("products", "retired_at", schema="core")

    op.drop_column("production_orders", "cancellation_reason", schema="plan")
    op.drop_column("production_orders", "cancelled_by", schema="plan")
    op.drop_column("production_orders", "cancelled_at", schema="plan")
