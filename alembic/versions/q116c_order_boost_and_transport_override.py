"""Q.116.C — tabelas plan.order_boost + plan.work_order_override.

Duas tabelas escritas pelos endpoints PATCH novos:

  * plan.order_boost — boost manual (0-100) por encomenda. PK = work_order_id
    (INTEGER, legacy_id da ProductionOrder = ID ERP, NÃO a UUID interna).
  * plan.work_order_override — override manual da data de transporte por
    encomenda. PK = work_order_id (INTEGER).

FK soft em ambas: não declaramos ForeignKey para plan.production_order para não
bloquear gestão histórica e para mantermos paridade com o estilo das tabelas
de configuração Q.115.A.* (client_priority é o exemplar).

Sem RLS nesta sub-sprint — o tenant_id é indexado para query, mas o
endpoint filtra explicitamente por tenant via require_tenant_header.

Revision ID: q116c_order_boost_transport
Revises: q115_x6b_boat_potential
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "q116c_order_boost_transport"
down_revision = "q115_x6b_boat_potential"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ─── plan.order_boost ─────────────────────────────────────────────────
    op.create_table(
        "order_boost",
        sa.Column("work_order_id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("boost", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.String(80), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "boost BETWEEN 0 AND 100",
            name="ck_order_boost_range",
        ),
        schema="plan",
    )
    op.create_index(
        "ix_order_boost_tenant",
        "order_boost",
        ["tenant_id"],
        schema="plan",
    )

    # ─── plan.work_order_override ─────────────────────────────────────────
    op.create_table(
        "work_order_override",
        sa.Column("work_order_id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "transport_date_override",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.String(80), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="plan",
    )
    op.create_index(
        "ix_work_order_override_tenant",
        "work_order_override",
        ["tenant_id"],
        schema="plan",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_work_order_override_tenant",
        table_name="work_order_override",
        schema="plan",
    )
    op.drop_table("work_order_override", schema="plan")
    op.drop_index(
        "ix_order_boost_tenant",
        table_name="order_boost",
        schema="plan",
    )
    op.drop_table("order_boost", schema="plan")
