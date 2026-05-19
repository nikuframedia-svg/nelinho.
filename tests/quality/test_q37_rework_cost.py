"""
Sub-sprint Q.37.A — Rework cost summary (custo do retrabalho em €).

`ImpactService.cost_summary` is the factory-wide €-cost rollup that feeds
the CEO question "quanto custou o retrabalho". Each test reads as an
independent spec (DAMP) and runs against the FakeSession — no real DB.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.quality.services.impact_service import (
    VALID_COST_GROUP_BY,
    ImpactService,
)
from tests.conftest import TEST_TENANT_ID


def test_cost_summary_group_by_set_covers_dimensions():
    # The four dimensions a CEO drills into: which error, which phase,
    # which boat model, which order.
    assert VALID_COST_GROUP_BY == {"error_code", "phase", "model", "of_id"}


@pytest.mark.asyncio
async def test_cost_summary_rejects_unknown_group_by(fake_session):
    svc = ImpactService(fake_session, TEST_TENANT_ID)
    with pytest.raises(ValueError):
        await svc.cost_summary(group_by="continent")


@pytest.mark.asyncio
async def test_cost_summary_aggregates_totals(fake_session):
    # Aggregate row: (events, events_with_cost, sum_cost, sum_hours, distinct_of).
    fake_session.queue_scalars([
        (8, 8, Decimal("1240.50"), Decimal("36.0"), 5),
    ])
    svc = ImpactService(fake_session, TEST_TENANT_ID)
    out = await svc.cost_summary()

    assert out["events"] == 8
    assert out["cost_estimate_eur"] == 1240.5
    assert out["hours_lost"] == 36.0
    assert out["affected_orders"] == 5
    assert out["cost_coverage_pct"] == 100.0
    assert out["group_by"] is None
    assert out["breakdown"] == []


@pytest.mark.asyncio
async def test_cost_summary_coverage_reflects_missing_estimates(fake_session):
    # 10 rework events, only 4 carry a € estimate — coverage is 40%, so the
    # headline € is a known under-count, not a fact.
    fake_session.queue_scalars([
        (10, 4, Decimal("500"), Decimal("20"), 3),
    ])
    svc = ImpactService(fake_session, TEST_TENANT_ID)
    out = await svc.cost_summary()

    assert out["events"] == 10
    assert out["events_with_cost_estimate"] == 4
    assert out["cost_coverage_pct"] == 40.0


@pytest.mark.asyncio
async def test_cost_summary_empty_window_returns_zeros(fake_session):
    # Nothing queued → no aggregate row. Honest zeros, no division crash.
    svc = ImpactService(fake_session, TEST_TENANT_ID)
    out = await svc.cost_summary()

    assert out["events"] == 0
    assert out["cost_estimate_eur"] == 0.0
    assert out["cost_coverage_pct"] == 0.0
    assert out["affected_orders"] == 0


@pytest.mark.asyncio
async def test_cost_summary_breakdown_by_error_code_sorted_by_cost(fake_session):
    # First execute → aggregate row; second execute → grouped rows.
    fake_session.queue_scalars([
        (6, 6, Decimal("900"), Decimal("18"), 4),
    ])
    fake_session.queue_scalars([
        ("MOLDE_BACO", 2, Decimal("200"), Decimal("6")),
        ("PINTURA_CORRER", 4, Decimal("700"), Decimal("12")),
    ])
    svc = ImpactService(fake_session, TEST_TENANT_ID)
    out = await svc.cost_summary(group_by="error_code")

    assert out["group_by"] == "error_code"
    # Sorted by € descending — the costliest error first.
    assert [b["key"] for b in out["breakdown"]] == [
        "PINTURA_CORRER", "MOLDE_BACO",
    ]
    assert out["breakdown"][0]["cost_estimate_eur"] == 700.0
    assert out["breakdown"][0]["events"] == 4
