"""Q.53.B — factory calendar (plan.factory_calendar_day)

The CPO decoder used to schedule 24/7 — no weekends, no holidays. This
table is the working-time master: one row per (tenant, day) with a
working flag, the shift capacity in hours and a human label. Seeded by
`src/adapters/nelo/etl/calendar.py` (PT national holidays + weekends).

Revision ID: 054_factory_calendar
Revises: 053_warehouse_stock
Create Date: 2026-05-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "054_factory_calendar"
down_revision = "053_warehouse_stock"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "factory_calendar_day",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("is_working_day", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("shift_hours", sa.Numeric(5, 2), nullable=False, server_default="8.00"),
        sa.Column("label", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Index("ix_factory_calendar_day_day", "day"),
        sa.UniqueConstraint(
            "tenant_id", "day",
            name="uq_factory_calendar_day_tenant_day",
        ),
        schema="plan",
    )


def downgrade() -> None:
    op.drop_table("factory_calendar_day", schema="plan")
