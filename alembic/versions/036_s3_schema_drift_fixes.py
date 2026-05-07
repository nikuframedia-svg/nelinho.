"""Sprint S3 — schema drift fixes

Closes the model↔migration gaps identified in the foundation audit:

* Tenant: Python defaults (status, subscription_level, timezone, currency_code,
  locale) had no `server_default`, so SQL inserts that bypass the ORM landed
  NULL where code expects 'UTC' / 'EUR' / 'STARTER'.
* TenantConfiguration.valid_from: NOT NULL with Python `default=utcnow` only;
  raw SQL inserts failed.
* Employee.burden_rate: NOT NULL with Python `default=Decimal("0.32")` only;
  raw SQL inserts produced wrong wage calculations.
* Operation.machine_id: indexed in queries (filter by machine) but no
  `op.create_index` ever existed; added now.

All operations are idempotent-friendly: ALTER ... SET DEFAULT and CREATE INDEX
IF NOT EXISTS so re-runs do not break.

Revision ID: 033_s3_schema_drift
Revises: 032_hr_profit_operacoes
Create Date: 2026-05-02
"""
from alembic import op
import sqlalchemy as sa


revision = "036_s3_schema_drift"
down_revision = "035_sandbox_scenario_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- core.tenants server defaults ---------------------------------------
    op.alter_column(
        "tenants", "status",
        server_default="ACTIVE",
        schema="core",
    )
    op.alter_column(
        "tenants", "subscription_level",
        server_default="STARTER",
        schema="core",
    )
    op.alter_column(
        "tenants", "timezone",
        server_default="UTC",
        schema="core",
    )
    op.alter_column(
        "tenants", "currency_code",
        server_default="EUR",
        schema="core",
    )
    op.alter_column(
        "tenants", "locale",
        server_default="pt-PT",
        schema="core",
    )

    # --- core.tenant_configurations.valid_from ------------------------------
    op.alter_column(
        "tenant_configurations", "valid_from",
        server_default=sa.func.now(),
        schema="core",
    )

    # --- core.employees.burden_rate ------------------------------------------
    op.alter_column(
        "employees", "burden_rate",
        server_default="0.32",
        schema="core",
    )

    # --- core.operations.machine_id index -----------------------------------
    # `IF NOT EXISTS` so the migration is safe to re-run if the index was
    # created out-of-band on a hot DB.
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_operations_machine_id "
        "ON core.operations (machine_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS core.idx_operations_machine_id")

    op.alter_column("employees", "burden_rate", server_default=None, schema="core")
    op.alter_column("tenant_configurations", "valid_from", server_default=None, schema="core")

    op.alter_column("tenants", "locale", server_default=None, schema="core")
    op.alter_column("tenants", "currency_code", server_default=None, schema="core")
    op.alter_column("tenants", "timezone", server_default=None, schema="core")
    op.alter_column("tenants", "subscription_level", server_default=None, schema="core")
    op.alter_column("tenants", "status", server_default=None, schema="core")
