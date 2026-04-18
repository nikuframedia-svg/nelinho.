"""
Seed default tenant configuration values (Sprint L.4).

Usage:
    python scripts/seed_default_configs.py --tenant-id <UUID>
    python scripts/seed_default_configs.py --all-active

Idempotent: existing keys are left untouched. Safe to run after every
migration or when the Blueprint ships a new default value.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from uuid import UUID

from sqlalchemy import select

from src.core.models.tenant import Tenant, TenantStatus
from src.core.services.default_configs import seed_tenant_defaults
from src.core.services.tenant_config_service import TenantConfigService
from src.shared.database import async_session_factory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("seed_default_configs")


async def seed_for_tenant(tenant_id: UUID) -> int:
    async with async_session_factory() as session:
        svc = TenantConfigService(session, tenant_id)
        written = await seed_tenant_defaults(svc)
        await session.commit()
        return written


async def list_active_tenants() -> list[UUID]:
    async with async_session_factory() as session:
        result = await session.execute(
            select(Tenant.id).where(Tenant.status == TenantStatus.ACTIVE)
        )
        return [row[0] for row in result.all()]


async def main(args: argparse.Namespace) -> None:
    if args.tenant_id:
        tenants = [UUID(args.tenant_id)]
    elif args.all_active:
        tenants = await list_active_tenants()
        logger.info("Seeding %d active tenants", len(tenants))
    else:
        raise SystemExit("pass --tenant-id <UUID> or --all-active")

    total = 0
    for tid in tenants:
        written = await seed_for_tenant(tid)
        total += written
        logger.info("tenant=%s wrote=%d", tid, written)
    logger.info("done. total rows written: %d", total)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed default tenant configuration.")
    parser.add_argument("--tenant-id", help="Single tenant UUID to seed")
    parser.add_argument(
        "--all-active",
        action="store_true",
        help="Seed every tenant with status=ACTIVE",
    )
    asyncio.run(main(parser.parse_args()))
