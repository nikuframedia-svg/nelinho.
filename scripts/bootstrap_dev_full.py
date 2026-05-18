"""Q.18.BOOTSTRAP — full dev environment setup.

Creates all DB tables (via Base.metadata.create_all with ALL models imported,
mirroring alembic/env.py imports), inserts the NELO dev tenant, and seeds the
183 default configs.

Idempotent. Safe to re-run.

Usage:
    python scripts/bootstrap_dev_full.py
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bootstrap_dev_full")

DEV_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
DEV_TENANT_NAME = "NELO Dev"
DEV_TENANT_CODE = "nelo-dev"


# Mirror alembic/env.py imports so Base.metadata is fully populated.
def _import_all_models() -> None:
    # Core
    from src.core.models import (  # noqa: F401
        tenant, tenant_configuration, product, machine, employee, operation, bom, rates,
    )
    # Domain modules
    from src.copilot import models as copilot_models  # noqa: F401
    from src.dqa import models as dqa_models  # noqa: F401
    from src.supply import models as supply_models  # noqa: F401
    from src.shared.models import governance  # noqa: F401  (legacy decision_runs/approvals)
    # Active Q.13+ governance models (decision_run singular, preference_rule, rule_firing, etc.)
    from src.governance import models as governance_main_models  # noqa: F401
    from src.twin import models as twin_models  # noqa: F401
    from src.copilot.alerts import models as copilot_alerts_models  # noqa: F401
    from src.ml.models import orm as ml_orm_models  # noqa: F401
    from src.plan.cpo import commits as plan_commits_models  # noqa: F401
    from src.plan.models import transport as plan_transport_models  # noqa: F401
    from src.plan.models import routing_template as plan_routing_template_models  # noqa: F401
    from src.profit.models import pricing as profit_pricing_models  # noqa: F401
    from src.quality.models import rework as quality_rework_models  # noqa: F401
    from src.plan.models import mold as plan_mold_models  # noqa: F401
    from src.plan.models import schedule as plan_schedule_models  # noqa: F401
    from src.plan.models import order as plan_order_models  # noqa: F401
    from src.plan.models import mrp as plan_mrp_models  # noqa: F401
    from src.plan.models import phase_gap as plan_phase_gap_models  # noqa: F401
    from src.plan.models import factory_calendar as plan_factory_calendar_models  # noqa: F401
    from src.factory_data_product.models import curated as factory_curated_models  # noqa: F401
    from src.sandbox import models as sandbox_models  # noqa: F401
    from src.improve import models as improve_models  # noqa: F401

    # Q.18.BOOTSTRAP — modules that env.py forgets but the running backend needs:
    from src.workforce import models as workforce_models  # noqa: F401
    from src.profit.models import cost as profit_cost_models  # noqa: F401
    from src.profit.models import phase_bonus as profit_phase_bonus_models  # noqa: F401
    from src.hr.models import allocation as hr_allocation_models  # noqa: F401
    from src.hr.models import legacy_allocation as hr_legacy_allocation_models  # noqa: F401
    from src.hr.models import productivity as hr_productivity_models  # noqa: F401
    from src.explain.models import explained_value as explain_explained_value_models  # noqa: F401

    # Q.17.C — tenant_rule + revision tables (NL→YAML rule authoring)
    from src.governance.yaml_policy import models as yaml_policy_models  # noqa: F401

    # Q.20.A — core.etl_run audit table (ERP→Postgres sync trail)
    from src.core.models import etl_run as core_etl_run_models  # noqa: F401

    # Q.22.A — shared.users identity table (backs GET /v1/auth/me)
    from src.shared.models import user as shared_user_models  # noqa: F401
    # Q.22.C — plan.production_errors (backs /api/errors*)
    from src.legacy import models as legacy_models  # noqa: F401
    # Q.22.D — reports.report_schedule + report_run
    from src.reports import models as reports_models  # noqa: F401


_SCHEMAS = (
    "core", "plan", "profit", "hr", "dqa", "governance", "supply", "quality",
    "sandbox", "twin", "improve", "shared", "reports",
    "factory_curated", "factory_meta", "factory_raw",
)


async def ensure_schemas() -> None:
    """Create every schema declared in any model's __table_args__."""
    from sqlalchemy import text
    from src.shared.database import engine

    async with engine.begin() as conn:
        for schema in _SCHEMAS:
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS {schema}'))
    log.info("ensured %d schemas", len(_SCHEMAS))


async def create_all_tables() -> None:
    _import_all_models()
    from src.shared.database import Base, engine

    # Q.18.BOOTSTRAP — pgvector é optional em dev. Exclude tabelas com columns
    # VECTOR(...) do create_all em dev. Em produção pgvector está instalado e
    # estas tabelas criam normalmente. RAG search degrada para text-only em dev.
    pgvector_dependent = {"copilot_rag_chunk"}
    tables_to_create = [
        t for name, t in Base.metadata.tables.items()
        if name.split(".")[-1] not in pgvector_dependent
    ]
    skipped = len(Base.metadata.tables) - len(tables_to_create)
    if skipped:
        log.warning(
            "skipping %d pgvector-dependent table(s) in dev: %s",
            skipped, sorted(pgvector_dependent),
        )

    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(sync_conn, tables=tables_to_create)
        )
    log.info(
        "create_all done — %d tables created (out of %d in metadata)",
        len(tables_to_create), len(Base.metadata.tables),
    )


async def ensure_tenant() -> UUID:
    from src.shared.database import async_session_factory
    from src.core.models.tenant import Tenant, TenantStatus

    async with async_session_factory() as session:
        existing = await session.get(Tenant, DEV_TENANT_ID)
        if existing:
            log.info("tenant exists: %s status=%s", existing.id, existing.status)
            return DEV_TENANT_ID
        tenant = Tenant(
            id=DEV_TENANT_ID,
            tenant_name=DEV_TENANT_NAME,
            tenant_code=DEV_TENANT_CODE,
            status=TenantStatus.ACTIVE,
        )
        session.add(tenant)
        await session.commit()
        log.info("inserted tenant %s (%s)", DEV_TENANT_ID, DEV_TENANT_NAME)
        return DEV_TENANT_ID


async def seed_configs(tenant_id: UUID) -> int:
    from src.shared.database import async_session_factory
    from src.core.services.tenant_config_service import TenantConfigService
    from src.core.services.default_configs import seed_tenant_defaults

    async with async_session_factory() as session:
        svc = TenantConfigService(session, tenant_id)
        written = await seed_tenant_defaults(svc)
        await session.commit()
        log.info("seeded %d config rows for tenant %s", written, tenant_id)
        return written


async def populate_curated_if_erp_available(tenant_id: UUID) -> None:
    """Q.36.D — passo condicional: quando o ERP MAR-KAYAKS está acessível
    (``SQLSERVER_ENABLED=true``), corre o mirror de qualidade + o
    ``curated_loader`` para que ``factory_curated.*`` não arranque vazio.

    Sem ERP em dev, é um no-op: o bootstrap continua a ser corrível numa
    máquina sem ligação ao SQL Server. Os detectores causais devolvem
    "sem causa" honesto até o ``populate_curated.py`` correr.
    """
    from src.shared.config import settings

    if not getattr(settings, "sqlserver_enabled", False):
        log.info(
            "curated populate SKIPPED — SQLSERVER_ENABLED=False. "
            "Corre scripts/populate_curated.py quando o ERP estiver acessível."
        )
        return

    from src.adapters.nelo.etl.quality import mirror_quality
    from src.adapters.nelo.services import close_engine
    from src.factory_data_product.etl.curated_loader import load_curated
    from src.shared.database import async_session_factory

    try:
        async with async_session_factory() as session:
            await mirror_quality(session=session, tenant_id=tenant_id)
            await session.commit()
        async with async_session_factory() as session:
            counts = await load_curated(session, tenant_id)
            await session.commit()
        log.info(
            "curated populated — order_phase=%d allocation=%d quality_event=%d",
            counts["order_phase"], counts["allocation"], counts["quality_event"],
        )
    except Exception as exc:  # noqa: BLE001 — bootstrap não morre por isto
        log.warning(
            "curated populate falhou (%s) — DB continua utilizável; "
            "corre scripts/populate_curated.py manualmente.", exc,
        )
    finally:
        await close_engine()


async def main() -> None:
    await ensure_schemas()
    await create_all_tables()
    tid = await ensure_tenant()
    written = await seed_configs(tid)
    await populate_curated_if_erp_available(tid)
    print(f"OK — DB ready, tenant {tid}, {written} configs seeded")


if __name__ == "__main__":
    asyncio.run(main())
