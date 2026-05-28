"""Q.115.A.06 — tabela quality.error_type_runbook_link (ligacao erro→runbook).

Um erro pode ter multiplos runbooks (por prioridade). PK composta
(tenant_id, error_code, runbook_id). FK para quality.runbook(id).

Revision ID: q115_a06_error_type_runbook_link
Revises: q115_a05_runbook
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "q115_a06_error_type_runbook_link"
down_revision = "q115_a05_runbook"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "error_type_runbook_link",
        sa.Column("error_code", sa.String(64), nullable=False),
        sa.Column(
            "runbook_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("quality.runbook.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "priority",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint(
            "tenant_id", "error_code", "runbook_id",
            name="pk_error_type_runbook_link",
        ),
        schema="quality",
    )
    op.create_index(
        "ix_quality_error_type_runbook_link_tenant_id",
        "error_type_runbook_link",
        ["tenant_id"],
        schema="quality",
    )

    # RLS — padrao Q.62.B
    op.execute(
        "ALTER TABLE quality.error_type_runbook_link ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation ON quality.error_type_runbook_link"
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation ON quality.error_type_runbook_link
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation ON quality.error_type_runbook_link"
    )
    op.execute(
        "ALTER TABLE quality.error_type_runbook_link DISABLE ROW LEVEL SECURITY"
    )
    op.drop_index(
        "ix_quality_error_type_runbook_link_tenant_id",
        table_name="error_type_runbook_link",
        schema="quality",
    )
    op.drop_table("error_type_runbook_link", schema="quality")
