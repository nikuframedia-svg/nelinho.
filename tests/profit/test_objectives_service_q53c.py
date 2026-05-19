"""Q.53.C — GET /v1/profit/kpis/objectives.

CEO target bands (low/target/high) per KPI, seeded with defaults and
overridable by TenantConfiguration, plus the PP1-impact signal (€ saved
by accepted = executed decisions).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from src.profit.services.objectives_service import ObjectivesService

TENANT = UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture(autouse=True)
def _clear_config_cache():
    """TenantConfigService keeps a module-level category cache; clear it
    so one test's `cost` override does not leak into the next."""
    from src.core.services.tenant_config_service import _CACHE

    _CACHE.clear()
    yield
    _CACHE.clear()


def _decision(*, status: str, expected=None, actual=None, days_ago: int = 1):
    from src.governance.models import DecisionRun

    return DecisionRun(
        id=uuid4(),
        tenant_id=TENANT,
        decision_type="scheduling_adjustment",
        title="t",
        status=status,
        action_data={},
        expected_impact=expected,
        actual_impact=actual,
        proposed_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
        audit_hash="x" * 64,
    )


@pytest.mark.asyncio
async def test_objectives_seeds_four_ceo_kpis(fake_session):
    fake_session.queue_scalars([])  # cost config — empty
    fake_session.queue_scalars([])  # decisions — none

    out = await ObjectivesService(fake_session, TENANT).objectives()

    kpis = {k["kpi"]: k for k in out["kpis"]}
    assert set(kpis) == {
        "throughput_eur_day", "otd_pct", "fpy_pct", "rework_pct",
    }
    # Seeded defaults from the deliverable.
    assert kpis["throughput_eur_day"]["low"] == 30000.0
    assert kpis["throughput_eur_day"]["high"] == 35000.0
    assert kpis["otd_pct"]["target"] == 95.0
    assert kpis["fpy_pct"]["target"] == 95.0
    assert kpis["rework_pct"]["target"] == 8.0
    # Rework is a lower-is-better KPI.
    assert kpis["rework_pct"]["direction"] == "lower"
    assert kpis["otd_pct"]["direction"] == "higher"
    assert all(k["source"] == "seed_default" for k in out["kpis"])


@pytest.mark.asyncio
async def test_tenant_config_overrides_seed(fake_session):
    # `cost` category returns a custom throughput band.
    fake_session.queue_scalars([
        SimpleConfig("target.throughput_eur_day_min", 40000),
        SimpleConfig("target.throughput_eur_day_max", 48000),
    ])
    fake_session.queue_scalars([])  # decisions

    out = await ObjectivesService(fake_session, TENANT).objectives()
    tp = next(k for k in out["kpis"] if k["kpi"] == "throughput_eur_day")
    assert tp["low"] == 40000.0
    assert tp["high"] == 48000.0
    assert tp["source"] == "tenant_config"


@pytest.mark.asyncio
async def test_pp1_impact_sums_executed_decisions(fake_session):
    fake_session.queue_scalars([])  # cost config
    fake_session.queue_scalars([
        _decision(status="executed", actual={"eur_saved": 2400}),
        _decision(status="executed_partial", actual={"eur_saved": 600}),
        # expected_impact fallback when actual is missing.
        _decision(status="executed", expected={"eur_saved": 1000}),
    ])

    out = await ObjectivesService(fake_session, TENANT).objectives()
    pp1 = out["pp1_impact"]
    assert pp1["accepted_decisions"] == 3
    assert pp1["decisions_with_eur"] == 3
    assert pp1["eur_saved"] == 4000.0
    assert pp1["reason"] is None


@pytest.mark.asyncio
async def test_pp1_impact_zero_when_no_executed_decisions(fake_session):
    fake_session.queue_scalars([])  # cost config
    fake_session.queue_scalars([])  # decisions — none

    out = await ObjectivesService(fake_session, TENANT).objectives()
    pp1 = out["pp1_impact"]
    assert pp1["accepted_decisions"] == 0
    assert pp1["eur_saved"] == 0.0
    assert "Ainda não há decisões executadas" in pp1["reason"]


@pytest.mark.asyncio
async def test_pp1_impact_counts_decision_without_eur_signal(fake_session):
    """An executed decision with no eur figure counts as accepted but
    contributes 0 — it is NOT imputed a savings number."""
    fake_session.queue_scalars([])  # cost config
    fake_session.queue_scalars([
        _decision(status="executed", actual={"note": "no euros here"}),
    ])

    out = await ObjectivesService(fake_session, TENANT).objectives()
    pp1 = out["pp1_impact"]
    assert pp1["accepted_decisions"] == 1
    assert pp1["decisions_with_eur"] == 0
    assert pp1["eur_saved"] == 0.0


class SimpleConfig:
    """Stand-in for a TenantConfiguration row — only `key`/`raw_value`."""

    def __init__(self, key, raw_value):
        self.key = key
        self.raw_value = raw_value
