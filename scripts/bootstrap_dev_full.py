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


# Q.61.14 — single import (model_registry e a fonte unica de modelos).
# Antes deste sub-sprint, este ficheiro tinha 28 imports manuais que
# divergiam do alembic/env.py em ~12 modulos — bootstrap criava tabelas
# que producao via `alembic upgrade head` deixava por criar.
def _import_all_models() -> None:
    from src.shared import model_registry


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


async def seed_rag_schema_docs(tenant_id: UUID) -> int:
    """Q.68.1.D — Seed RAG schema docs em dev (idempotente).

    O cron nightly `_copilot_schema_reindex_job` (Q.67.4.E) só corre
    04:00 UTC, por isso em dev a tabela `copilot_rag_chunk` ficaria
    vazia até next morning ou run manual. Este passo garante que um
    bootstrap fresco já tem os chunks indexados.

    Skip silencioso (com warning) quando `copilot_rag_chunk` não foi
    criada — caso comum em dev sem pgvector (create_all faz skip
    explícito ao topo deste ficheiro).
    """
    from src.copilot.rag import ingest_schema_docs
    from src.shared.database import async_session_factory

    async with async_session_factory() as session:
        chunks = await ingest_schema_docs(
            session=session,
            tenant_id=tenant_id,
            force=False,  # safe: incremental, não apaga
        )
        await session.commit()
    log.info("seeded %d RAG schema chunks for tenant %s", chunks, tenant_id)
    return chunks


async def main() -> None:
    await ensure_schemas()
    await create_all_tables()
    tid = await ensure_tenant()
    written = await seed_configs(tid)

    # Q.68.1.D — Seed RAG schema docs (best-effort, pgvector-dependent).
    rag_chunks = 0
    try:
        rag_chunks = await seed_rag_schema_docs(tid)
    except Exception as exc:
        log.warning(
            "RAG seed skipped (pgvector ausente em dev?): %s",
            exc,
        )

    print(
        f"OK — DB ready, tenant {tid}, {written} configs seeded, "
        f"{rag_chunks} RAG chunks"
    )


if __name__ == "__main__":
    asyncio.run(main())
