"""Q.158.A — hr.employee_skills.is_chefe (espelha EFP_CHEFE).

A matriz de polivalência da NELO (``dbo.ENTIDADE_FASE``) define, por
operador×fase: ``EFP_QUALIFICADO`` (gate — pode fazer) e ``EFP_CHEFE`` (pode
LIDERAR a fase — o "Chefe" do barco×fase no software de produção). O mirror
Q.20.D já tinha ``is_certified`` (=QUALIFICADO) mas faltava o flag de Chefe.
Esta migração acrescenta-o; o ETL passa a preenchê-lo (Q.158.A).

Revision ID: q158a_employee_skill_chefe
Revises: q157e_operation_execution
Create Date: 2026-06-02
"""
from alembic import op
import sqlalchemy as sa

revision = "q158a_employee_skill_chefe"
down_revision = "q157e_operation_execution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "employee_skills",
        sa.Column(
            "is_chefe", sa.Boolean(), nullable=False,
            server_default=sa.text("false"),
        ),
        schema="hr",
    )


def downgrade() -> None:
    op.drop_column("employee_skills", "is_chefe", schema="hr")
