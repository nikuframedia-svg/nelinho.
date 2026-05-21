"""Sprint Q.9 (2.6) — ExplanationEngine.explain_margin /
explain_inventory_turnover / explain_machine_breakdown.

Replace 3 placeholder branches in `explain_kpi`. The first two are
structural explanations (no DB needed) so they're covered with simple
assertions on shape; the breakdown method runs the SQL path with a
mocked AsyncSession.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from src.profit.explanation_engine import ExplanationEngine


TENANT = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@pytest.fixture
def engine():
    return ExplanationEngine(session=AsyncMock(), tenant_id=TENANT)


@pytest.mark.asyncio
async def test_explain_margin_returns_structural_factors(engine):
    out = await engine.explain_margin()
    assert out["kpi"] == "margin"
    assert out["advisory_mode"] is True
    assert any(f["name"] == "Direct labour" for f in out["topFactors"])
    assert any(f["name"] == "Rework" for f in out["topFactors"])
    assert "suggestion" in out


@pytest.mark.asyncio
async def test_explain_inventory_turnover_includes_wip_buffer(engine):
    out = await engine.explain_inventory_turnover()
    assert out["kpi"] == "inventory_turnover"
    assert out["advisory_mode"] is True
    names = [f["name"] for f in out["topFactors"]]
    assert "WIP buffer (Laminagem→Pintura)" in names


@pytest.mark.asyncio
async def test_explain_kpi_dispatches_to_margin(engine):
    out = await engine.explain_kpi("margin")
    assert out["kpi"] == "margin"


@pytest.mark.asyncio
async def test_explain_kpi_dispatches_to_inventory_turnover(engine):
    out = await engine.explain_kpi("inventory_turnover")
    assert out["kpi"] == "inventory_turnover"


@pytest.mark.asyncio
async def test_explain_kpi_unknown_falls_back():
    engine = ExplanationEngine(session=AsyncMock(), tenant_id=TENANT)
    out = await engine.explain_kpi("not_a_real_kpi")
    assert out["topFactors"] == []
    assert "not yet available" in out["reason"]


@pytest.mark.asyncio
async def test_explain_machine_breakdown_returns_unassigned_vs_assigned():
    """Mock the DB to return 7 unassigned + 13 assigned; expect a
    35% / 65% split in the topFactors."""
    session = AsyncMock()

    async def _execute(_stmt):
        class _Result:
            def all(self_):
                # (machine_id, count) tuples
                return [(None, 7), (UUID("11111111-1111-1111-1111-111111111111"), 8),
                        (UUID("22222222-2222-2222-2222-222222222222"), 5)]

        return _Result()

    session.execute = _execute

    engine = ExplanationEngine(session=session, tenant_id=TENANT)
    out = await engine.explain_machine_breakdown(
        start_date=date(2026, 4, 1),
        end_date=date(2026, 4, 30),
    )
    assert out["kpi"] == "machine_breakdown"
    assert any(
        f["name"] == "Unassigned (setup/maintenance)" and f["count"] == 7
        for f in out["topFactors"]
    )
    assert any(
        f["name"] == "Capacity-contended" and f["count"] == 13
        for f in out["topFactors"]
    )
