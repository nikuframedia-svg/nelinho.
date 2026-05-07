"""Sprint Q.12 Onda 3.1 — optimistic locking for sandbox scenarios.

``SandboxService.simulate`` writes the row twice (SIMULATING then
SIMULATED) without holding any row lock. Two concurrent ``simulate``
calls on the same scenario both passed the status check, both flipped
to SIMULATING, and both raced to compute / overwrite ``impact``. We
add a ``version`` column and the service uses it as a CAS guard so
the second writer fails fast instead of silently corrupting the
projection.

Revision ID: 035_sandbox_scenario_version
Revises: 034_kill_switch_active
Create Date: 2026-05-02
"""
from alembic import op
import sqlalchemy as sa


revision = '035_sandbox_scenario_version'
down_revision = '034_kill_switch_active'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'sandbox_scenarios',
        sa.Column(
            'version',
            sa.Integer(),
            nullable=False,
            server_default='0',
        ),
        schema='sandbox',
    )


def downgrade() -> None:
    op.drop_column('sandbox_scenarios', 'version', schema='sandbox')
