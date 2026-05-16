"""
ProdPlan ONE - Alembic Environment Configuration
=================================================

Async migration support for SQLAlchemy 2.0.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import all models to ensure they're registered with metadata
from src.shared.database import Base
from src.shared.config import settings

# Import all model modules
from src.core.models import tenant, tenant_configuration, product, machine, employee, operation, bom, rates
from src.copilot import models as copilot_models
from src.dqa import models as dqa_models
from src.supply import models as supply_models
from src.shared.models import governance  # Decision ledger models
from src.twin import models as twin_models  # Digital Twin scenario models
from src.copilot.alerts import models as copilot_alerts_models  # Proactive alerts
from src.ml.models import orm as ml_orm_models  # ML model artifacts (Sprint G)
from src.plan.cpo import commits as plan_commits_models  # Schedule-as-Code (Sprint K)
from src.plan.models import transport as plan_transport_models  # Sprint P.2
from src.plan.models import routing_template as plan_routing_template_models  # Sprint P.4
from src.profit.models import pricing as profit_pricing_models  # Sprint Q.0/Q.2
from src.quality.models import rework as quality_rework_models  # Sprint R.1
from src.plan.models import mold as plan_mold_models  # Sprint R.6
# FASE -1.3 — imports em falta detectados na auditoria (CRIT-20)
from src.plan.models import schedule as plan_schedule_models  # ProductionSchedule
from src.plan.models import order as plan_order_models
from src.plan.models import mrp as plan_mrp_models
from src.plan.models import phase_gap as plan_phase_gap_models  # migration 023
from src.factory_data_product.models import curated as factory_curated_models  # migrations 028, 029
from src.sandbox import models as sandbox_models  # migration 030
from src.improve import models as improve_models  # migration 031
from src.shared.models import user as shared_user_models  # migration 046 (Q.22.A)
from src.legacy import models as legacy_models  # migration 047 (Q.22.C)

# this is the Alembic Config object
config = context.config

# Override sqlalchemy.url with our settings
config.set_main_option("sqlalchemy.url", settings.database_url.replace("+asyncpg", ""))

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for 'autogenerate'
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with a connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations in 'online' mode with async engine.
    """
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = settings.database_url
    
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

