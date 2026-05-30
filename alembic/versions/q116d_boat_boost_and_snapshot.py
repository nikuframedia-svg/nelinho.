"""Q.116.D — plan.boat_boost + plan.plan_schedule_commits.boost_inputs_snapshot.

Duas mudancas escritas pelo endpoint PATCH novo + decoder CPO unificado:

  * plan.boat_boost — boost manual (0-100) por BARCO. PK composta
    (tenant_id, boat_id). Boat_id e a string usada no MOVIMENTO/OF_FP da
    NELO ERP — varchar(80) e suficiente.
  * plan.plan_schedule_commits.boost_inputs_snapshot — JSONB com o
    snapshot dos inputs de boost (client/order/boat/effective) que
    entraram no commit, para reprodutibilidade do replay.

Forma do snapshot:
    {"<work_order_id>": {"client": int, "order": int,
                         "boat": int, "effective": int}}

Sem RLS nesta sub-sprint — o tenant_id e indexado para query e o endpoint
filtra explicitamente por tenant via require_tenant_header.

Revision ID: q116d_boat_boost_and_snapshot
Revises: q116b_routing_alt_predecessors
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "q116d_boat_boost_and_snapshot"
down_revision = "q116b_routing_alt_predecessors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ─── plan.boat_boost ──────────────────────────────────────────────────
    op.create_table(
        "boat_boost",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("boat_id", sa.String(80), nullable=False),
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
            name="ck_boat_boost_range",
        ),
        sa.PrimaryKeyConstraint("tenant_id", "boat_id"),
        schema="plan",
    )
    op.create_index(
        "ix_boat_boost_tenant",
        "boat_boost",
        ["tenant_id"],
        schema="plan",
    )

    # ─── plan.plan_schedule_commits.boost_inputs_snapshot ────────────────
    op.add_column(
        "plan_schedule_commits",
        sa.Column(
            "boost_inputs_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        # plan_schedule_commits vive no schema default (public) — sem schema= (fix Q.124)
    )


def downgrade() -> None:
    op.drop_column(
        "plan_schedule_commits",
        "boost_inputs_snapshot",
    )
    op.drop_index(
        "ix_boat_boost_tenant",
        table_name="boat_boost",
        schema="plan",
    )
    op.drop_table("boat_boost", schema="plan")
