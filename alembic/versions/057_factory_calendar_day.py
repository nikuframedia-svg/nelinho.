"""Q.51 — plan.factory_calendar_day (F10 — calendário de capacidade real).

O scheduler CPO assumia que todos os dias do calendário são dias úteis com
8h fixas. Um plano que ignora fins-de-semana, feriados e o encerramento de
Agosto falha no contacto com a realidade. Esta tabela é o calendário de
capacidade da fábrica — uma linha por data, a dizer se a fábrica trabalha
nesse dia. Populada pelo mirror ETL ``calendar`` a partir de
``DIAS_TRABALHO`` + ``FERIAS`` do ERP.

Em dev a tabela é criada por ``Base.metadata.create_all``
(``scripts/bootstrap_dev_full.py``); esta migração cobre produção.

Revision ID: 057_factory_calendar_day
Revises: 053_copilot_feedback_audit_link
Create Date: 2026-05-19
"""

import sqlalchemy as sa
from alembic import op


revision = "057_factory_calendar_day"
down_revision = "053_copilot_feedback_audit_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "factory_calendar_day",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("calendar_date", sa.Date(), nullable=False),
        sa.Column(
            "is_working_day",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "is_holiday",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("holiday_kind", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "calendar_date", name="uq_factory_calendar_day_date",
        ),
        schema="plan",
    )
    op.create_index(
        "ix_factory_calendar_day_tenant_date",
        "factory_calendar_day",
        ["tenant_id", "calendar_date"],
        schema="plan",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_factory_calendar_day_tenant_date",
        table_name="factory_calendar_day",
        schema="plan",
    )
    op.drop_table("factory_calendar_day", schema="plan")
