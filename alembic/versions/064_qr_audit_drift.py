"""Q.R-audit — colunas de timestamp em falta (drift ORM↔BD).

Auditoria 2026-05-30 (§6): tabelas que herdam de `TenantBase` (mixin com
`created_at`/`updated_at`) mas cujas colunas nunca foram criadas na BD.
Alinha o schema com o ORM:

  * governance.rule_firing               → created_at + updated_at  (faltavam ambas)
  * governance.causal_discovery_report   → created_at + updated_at  (faltavam ambas)
  * supply.inventory_ledger_entries      → updated_at               (created_at já existe)
  * supply.supply_forecasts              → updated_at               (created_at já existe)

`server_default=now()` faz o backfill das linhas existentes sem violar o
NOT NULL (mesmo padrão de 005_create_supply_tables.py). O drift de
`quality.rework_entry.boat_id` é resolvido do lado do ORM (modelo passa a
mapear a coluna que já existe na BD) — não precisa de DDL.

Revision ID: 064_qr_audit_drift
Revises: 063_q93_a_marts_schema
Create Date: 2026-05-30
"""
from alembic import op
import sqlalchemy as sa


revision = "064_qr_audit_drift"
down_revision = "063_q93_a_marts_schema"
branch_labels = None
depends_on = None


def _ts_column(name: str) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


def upgrade() -> None:
    # governance.rule_firing — faltam created_at + updated_at
    op.add_column("rule_firing", _ts_column("created_at"), schema="governance")
    op.add_column("rule_firing", _ts_column("updated_at"), schema="governance")

    # governance.causal_discovery_report — faltam created_at + updated_at
    op.add_column(
        "causal_discovery_report", _ts_column("created_at"), schema="governance"
    )
    op.add_column(
        "causal_discovery_report", _ts_column("updated_at"), schema="governance"
    )

    # supply.inventory_ledger_entries — falta updated_at
    op.add_column(
        "inventory_ledger_entries", _ts_column("updated_at"), schema="supply"
    )

    # supply.supply_forecasts — falta updated_at
    op.add_column("supply_forecasts", _ts_column("updated_at"), schema="supply")


def downgrade() -> None:
    op.drop_column("supply_forecasts", "updated_at", schema="supply")
    op.drop_column("inventory_ledger_entries", "updated_at", schema="supply")
    op.drop_column("causal_discovery_report", "updated_at", schema="governance")
    op.drop_column("causal_discovery_report", "created_at", schema="governance")
    op.drop_column("rule_firing", "updated_at", schema="governance")
    op.drop_column("rule_firing", "created_at", schema="governance")
