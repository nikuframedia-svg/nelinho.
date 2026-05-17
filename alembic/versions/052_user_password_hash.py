"""Q.31.G — shared.users.password_hash.

Login real por password (decisão D3 do Luis: operadores autenticam por
password, não RFID). Adiciona a coluna `password_hash` à `shared.users`.

Nullable: a migração é segura sobre linhas existentes e um utilizador sem
password simplesmente não pode autenticar por `/v1/auth/login`. O hash é
bcrypt (passlib) — ver `src/shared/auth/passwords.py`.

Revision ID: 052_user_password_hash
Revises: 051_copilot_user_feedback
Create Date: 2026-05-17
"""

import sqlalchemy as sa
from alembic import op


revision = "052_user_password_hash"
down_revision = "051_copilot_user_feedback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        schema="shared",
    )


def downgrade() -> None:
    op.drop_column("users", "password_hash", schema="shared")
