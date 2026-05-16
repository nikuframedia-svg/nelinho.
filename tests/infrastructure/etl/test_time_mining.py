"""Q.20.F — historical time-mining tests.

The cleaning maths (`mine_durations`, `_percentile`, `_mode_or_median`,
`_duration_hours`) is pure. The end-to-end mirror runs against a live
Postgres (marked ``integration``) and asserts that p50/p90 land on
``routing_template_phase``.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.infrastructure.erp.etl.time_mining import (
    _duration_hours,
    _mode_or_median,
    _percentile,
    mine_durations,
    mirror_time_mining,
)


# ── pure: cleaning maths ──────────────────────────────────────────────────


def test_percentile_basic():
    assert _percentile([1, 2, 3, 4, 5], 50) == 3
    assert _percentile([], 50) == 0.0
    assert _percentile([7], 90) == 7


def test_mode_or_median_prefers_mode():
    assert _mode_or_median([2.0, 2.0, 2.0, 3.0, 9.0]) == 2.0


def test_mode_or_median_falls_back_to_median_when_mode_zero():
    # mode is 0 → fall back to median of the non-zero values.
    assert _mode_or_median([0.0, 0.0, 4.0, 6.0]) == 5.0


def test_mine_durations_removes_zeros_and_outliers():
    # zeros dropped; 100 is above P95 and dropped; mode of {2,2,2,3} = 2.
    result = mine_durations([0, 2, 2, 2, 3, 100])
    assert result is not None
    p50, p90 = result
    assert p50 == 2.0
    assert p90 >= p50            # invariant: p90 never below p50


def test_mine_durations_none_when_no_usable_data():
    assert mine_durations([]) is None
    assert mine_durations([0, 0, 0]) is None


def test_mine_durations_p90_ge_p50_property():
    import random

    rng = random.Random(42)
    for _ in range(50):
        sample = [rng.random() * 20 for _ in range(rng.randint(1, 40))]
        result = mine_durations(sample)
        if result is not None:
            p50, p90 = result
            assert p90 >= p50 >= 0


def test_duration_hours_from_timestamps():
    op = {
        "fase_of_inicio": datetime(2025, 1, 1, 8, 0),
        "fase_of_fim": datetime(2025, 1, 1, 11, 30),
    }
    assert _duration_hours(op) == 3.5


def test_duration_hours_none_when_incomplete_or_negative():
    assert _duration_hours({"fase_of_inicio": datetime(2025, 1, 1)}) is None
    assert _duration_hours({
        "fase_of_inicio": datetime(2025, 1, 1, 12, 0),
        "fase_of_fim": datetime(2025, 1, 1, 11, 0),
    }) is None


# ── integration ───────────────────────────────────────────────────────────


def _op(produto_id, fase_id, start_h, end_h):
    return {
        "produto_id": produto_id, "fase_id": fase_id,
        "fase_of_inicio": datetime(2025, 3, 1, start_h, 0, tzinfo=timezone.utc),
        "fase_of_fim": datetime(2025, 3, 1, end_h, 0, tzinfo=timezone.utc),
    }


class _FakeAdapter:
    async def fetch_operations(self, *, since=None, limit=None):
        # All 4h on phase LAM for product TM-P1 → p50 should be 4.
        return [
            _op("TM-P1", "LAM", 8, 12),
            _op("TM-P1", "LAM", 8, 12),
            _op("TM-P1", "LAM", 8, 12),
            _op("TM-P1", "LAM", 9, 14),       # 5h
            _op("GHOST", "LAM", 8, 12),       # unknown product → skipped
        ]


@pytest.mark.integration
async def test_mirror_time_mining_fills_durations():
    from uuid import UUID, uuid4

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from src.plan.models.routing_template import (
        ModelRoutingAssignment,
        RoutingTemplate,
        RoutingTemplatePhase,
    )
    from src.shared.config import settings

    tenant = UUID("00000000-0000-0000-0000-000000000001")
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            template = RoutingTemplate(
                tenant_id=tenant, code="ERP-tmtest01", name="TM test",
                phase_count=1, active=True, model_coverage=1,
            )
            session.add(template)
            await session.flush()
            session.add(RoutingTemplatePhase(
                tenant_id=tenant, template_id=template.id, seq=1,
                phase_id="LAM", phase_name="Laminagem", requires_mold=True,
            ))
            session.add(ModelRoutingAssignment(
                tenant_id=tenant, model_id="TM-P1",
                primary_template_id=template.id,
            ))
            await session.flush()

            result = await mirror_time_mining(
                session=session, tenant_id=tenant, adapter=_FakeAdapter(), since=None,
            )
            assert result.status == "ok"
            assert result.rows_read == 5
            assert result.rows_skipped == 1     # the GHOST product
            assert result.rows_updated == 1

            phase = (await session.execute(
                select(RoutingTemplatePhase).where(
                    RoutingTemplatePhase.template_id == template.id
                )
            )).scalar_one()
            assert phase.duration_p50_h is not None
            assert float(phase.duration_p50_h) == 4.0       # mode of the sample
            assert float(phase.duration_p90_h) >= 4.0

            await session.rollback()
    finally:
        await engine.dispose()
