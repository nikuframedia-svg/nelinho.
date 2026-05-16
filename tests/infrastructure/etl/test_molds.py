"""Q.20.C — molds mirror tests.

`_is_active` is pure. The end-to-end bridge runs against a live Postgres
(marked ``integration``): it seeds a curated ingestion + CuratedMold rows,
runs the mirror, asserts ``plan.mold``, then rolls back.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.infrastructure.erp.etl.molds import _is_active, mirror_molds


# ── pure ──────────────────────────────────────────────────────────────────


def test_is_active_false_when_in_maintenance():
    assert _is_active("Em Producao", True) is False


def test_is_active_false_when_retired_estado():
    assert _is_active("Retirado", False) is False
    assert _is_active("inativo", False) is False


def test_is_active_true_for_production_mold():
    assert _is_active("Em Producao", False) is True
    assert _is_active(None, False) is True


# ── integration: curated → plan.mold bridge ───────────────────────────────


class _FakeAdapter:
    """ERP knows only mold M-001 (2 pockets); M-002 / M-003 are Excel-only."""

    async def fetch_molds(self, **_kw):
        return [
            {"molde_id": "M-001", "molde_nome": "Molde 1", "estado": "Em Producao",
             "modelo_id": "K1", "numero_pocos": 2, "tamanho_id": "L"},
        ]


@pytest.mark.integration
async def test_mirror_molds_bridges_curated_to_plan_mold():
    from datetime import datetime, timezone

    from sqlalchemy import delete, func, select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from src.factory_data_product.models.curated import CuratedMold
    from src.factory_data_product.models.meta import (
        ActiveRun,
        IngestionRun,
        IngestionStatus,
        SourceType,
    )
    from src.plan.models.mold import Mold
    from src.shared.config import settings

    tenant = __import__("uuid").UUID("00000000-0000-0000-0000-000000000001")
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            ingestion_id = uuid4()
            session.add(IngestionRun(
                id=ingestion_id,
                created_by="test",
                source_type=SourceType.UPLOAD,
                file_name="test.xlsx",
                file_size_bytes=1,
                file_sha256="0" * 64,
                status=IngestionStatus.SUCCEEDED,
            ))
            await session.flush()  # ingestion_run must exist before its FKs
            session.add_all([
                CuratedMold(
                    id=uuid4(), ingestion_id=ingestion_id, molde_id="M-001",
                    molde_nome="Molde 1", modelo_id="K1", estado="Em Producao",
                    em_manutencao=False, is_quarantined=False,
                ),
                CuratedMold(
                    id=uuid4(), ingestion_id=ingestion_id, molde_id="M-002",
                    molde_nome="Molde 2", modelo_id="K2", estado="Em Producao",
                    em_manutencao=True, is_quarantined=False,
                ),
                # quarantined → must be excluded from the bridge
                CuratedMold(
                    id=uuid4(), ingestion_id=ingestion_id, molde_id="M-BAD",
                    molde_nome="Bad", modelo_id="K1", estado="Em Producao",
                    em_manutencao=False, is_quarantined=True,
                ),
            ])
            # ActiveRun is a singleton (id=1) — replace within the rolled-back tx.
            await session.execute(delete(ActiveRun))
            session.add(ActiveRun(
                id=1, active_ingestion_id=ingestion_id,
                activated_at_utc=datetime.now(timezone.utc), activated_by="test",
            ))
            await session.flush()

            result = await mirror_molds(
                session=session, tenant_id=tenant, adapter=_FakeAdapter(), since=None,
            )
            assert result.status == "ok"
            assert result.rows_read == 2          # quarantined row excluded
            assert result.rows_inserted == 2

            molds = (await session.execute(
                select(Mold).where(
                    Mold.tenant_id == tenant,
                    Mold.mold_code.in_(["M-001", "M-002", "M-BAD"]),
                )
            )).scalars().all()
            by_code = {m.mold_code: m for m in molds}
            assert set(by_code) == {"M-001", "M-002"}
            # pocket_count for M-001 comes from the ERP view (2); M-002 → default 1.
            assert by_code["M-001"].pocket_count == 2
            assert by_code["M-002"].pocket_count == 1
            # M-002 is em_manutencao → active False.
            assert by_code["M-001"].active is True
            assert by_code["M-002"].active is False

            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.integration
async def test_mirror_molds_noop_without_active_ingestion():
    from sqlalchemy import delete
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from src.factory_data_product.models.meta import ActiveRun
    from src.shared.config import settings

    tenant = __import__("uuid").UUID("00000000-0000-0000-0000-000000000001")
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            await session.execute(delete(ActiveRun))
            await session.flush()
            result = await mirror_molds(
                session=session, tenant_id=tenant, adapter=_FakeAdapter(), since=None,
            )
            assert result.status == "ok"
            assert result.rows_read == 0
            await session.rollback()
    finally:
        await engine.dispose()
