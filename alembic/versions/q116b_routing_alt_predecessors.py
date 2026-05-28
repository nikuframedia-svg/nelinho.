"""Q.116.B — editor de fases com posicao alternativa.

Adiciona duas colunas a `plan.routing_template_phase`:

  * `allowed_predecessors` — ARRAY de phase_id strings que podem
    legitimamente preceder esta fase. NULL quando a fase nao e flexivel.
  * `is_flexible` — flag boolean. True = a fase pode aparecer em mais
    do que uma posicao no routing; False = posicao fixa (default).

Usado pelo editor de fases (Q.116.B/D/F) para definir fases com
posicao alternativa. O decoder unificado (Agent CPO) le estas colunas
para validar permutacoes geradas pelo GA; o verify_invariants.py
garante que cada par (predecessor_alternativo, fase_flexivel) tem
gap de cura declarado em `NELO_CURING_GAPS_SEED`.

Q.116.B e so infra — nenhuma fase nasce `is_flexible` apos esta
migration; sao os endpoints PATCH novos que mudam o estado quando o
admin reordena ou marca uma fase como alternativa.

Revision ID: q116b_routing_alt_predecessors
Revises: q116c_order_boost_transport_override
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa

revision = "q116b_routing_alt_predecessors"
down_revision = "q116c_order_boost_transport_override"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "routing_template_phase",
        sa.Column("allowed_predecessors", sa.ARRAY(sa.String(100)), nullable=True),
        schema="plan",
    )
    op.add_column(
        "routing_template_phase",
        sa.Column(
            "is_flexible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        schema="plan",
    )


def downgrade() -> None:
    op.drop_column("routing_template_phase", "is_flexible", schema="plan")
    op.drop_column("routing_template_phase", "allowed_predecessors", schema="plan")
