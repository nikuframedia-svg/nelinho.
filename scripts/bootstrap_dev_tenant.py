"""Q.18.AUTH bootstrap — insert NELO dev tenant + seed 183 configs.

Idempotent. Safe to run repeatedly.

Usage:
    python scripts/bootstrap_dev_tenant.py
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bootstrap_dev_tenant")

DEV_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
DEV_TENANT_NAME = "NELO Dev"
DEV_TENANT_SLUG = "nelo-dev"


async def ensure_tenant() -> UUID:
    from src.shared.database import async_session_factory, init_db
    from src.core.models.tenant import Tenant, TenantStatus

    await init_db()  # idempotent — Base.metadata.create_all
    async with async_session_factory() as session:
        existing = await session.get(Tenant, DEV_TENANT_ID)
        if existing:
            log.info("tenant exists: %s status=%s", existing.id, existing.status)
            return DEV_TENANT_ID
        tenant = Tenant(
            id=DEV_TENANT_ID,
            tenant_name=DEV_TENANT_NAME,
            tenant_code=DEV_TENANT_SLUG,
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


async def main() -> None:
    tid = await ensure_tenant()
    written = await seed_configs(tid)
    print(f"OK — tenant {tid} ready, {written} configs seeded")


if __name__ == "__main__":
    asyncio.run(main())
