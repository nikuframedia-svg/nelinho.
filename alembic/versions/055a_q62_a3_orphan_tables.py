"""Q.62.A.3 — create the 13 remaining create_all-only tables.

Apos Q.62.A.2 fechar a chain ate 055, `alembic check` ainda revelou 13
tabelas que vivem em `Base.metadata` mas que nenhuma migration cria.
Sao historicamente tabelas criadas pelo `init_db.create_all()` ao
arranque da app.

Esta migration usa `Table.create(checkfirst=True)` em vez de
`op.create_table(...)` para que seja idempotente: em DBs onde
`create_all` ja criou as tabelas (dev + prod historicas), a migration
e no-op; em fresh installs (futuro Q.61.16 path) cria-as.

Tabelas alvo:
  * hr.legacy_allocations              (Q.18.A.4 + Q.61.30 historico)
  * plan.production_orders             (core business)
  * plan.material_requirements         (MRP)
  * plan.purchase_orders               (MRP target)
  * factory_curated.cost_reference     (ETL output)
  * factory_curated.mold               (ETL output)
  * factory_curated.mold_usage         (ETL output)
  * factory_curated.order              (ETL output)
  * factory_curated.order_phase        (ETL output)
  * factory_curated.phase_capacity     (ETL output)
  * factory_curated.quality_event      (ETL output)
  * factory_curated.skill_matrix       (ETL output)
  * factory_raw.excel_row              (ETL raw layer)

Note: alembic check tambem detecta drift "modify_default" / "modify_type"
em ~30 colunas existentes (server_default differences entre create_all e
o que estava nas migrations). Esses ficam para uma Q.62.A.4 ou Q.63 — sao
cosmeticos (mesmo data) e arriscados (alter_column em prod).

Revision ID: 055a_q62_a3_orphans
Revises: 055_rework_location_zone
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa


revision = "055a_q62_a3_orphans"
down_revision = "055_rework_location_zone"
branch_labels = None
depends_on = None


_TARGET_TABLES = [
    ("hr", "legacy_allocations"),
    ("plan", "production_orders"),
    ("plan", "material_requirements"),
    ("plan", "purchase_orders"),
    ("factory_curated", "cost_reference"),
    ("factory_curated", "mold"),
    ("factory_curated", "mold_usage"),
    ("factory_curated", "order"),
    ("factory_curated", "order_phase"),
    ("factory_curated", "phase_capacity"),
    ("factory_curated", "quality_event"),
    ("factory_curated", "skill_matrix"),
    ("factory_raw", "excel_row"),
]


def _ensure_schemas() -> None:
    """Schemas usados pelas tabelas — IF NOT EXISTS para idempotencia."""
    op.execute("CREATE SCHEMA IF NOT EXISTS hr")
    op.execute("CREATE SCHEMA IF NOT EXISTS plan")
    op.execute("CREATE SCHEMA IF NOT EXISTS factory_curated")
    op.execute("CREATE SCHEMA IF NOT EXISTS factory_raw")


def upgrade() -> None:
    _ensure_schemas()

    # Import o model_registry para garantir que todos os models estao
    # registados em Base.metadata antes de chamar Table.create.
    from src.shared import model_registry  # noqa: F401
    from src.shared.database import Base

    bind = op.get_bind()
    for schema, table_name in _TARGET_TABLES:
        key = f"{schema}.{table_name}"
        table = Base.metadata.tables.get(key)
        if table is None:
            # Tabela esperada nao existe em metadata — log mas nao falha
            # (defesa contra renames futuros).
            op.execute(
                f"SELECT 'WARNING: {key} ausente em Base.metadata' AS warn"
            )
            continue
        # checkfirst=True -> NOOP se a tabela ja existe (criada via
        # create_all em dev/prod historicos).
        table.create(bind, checkfirst=True)


def downgrade() -> None:
    # Dropping tables that production already has would lose data —
    # downgrade e DROP IF EXISTS apenas para fresh installs.
    for schema, table_name in reversed(_TARGET_TABLES):
        op.execute(f"DROP TABLE IF EXISTS {schema}.{table_name} CASCADE")
