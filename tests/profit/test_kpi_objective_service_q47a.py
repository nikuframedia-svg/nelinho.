"""Unit tests for KpiObjectiveService — Sprint Q.47.A (F9).

Synthetic ``KpiRow`` / ``KpiObjectiveRow`` fixtures, no live DB. The
service takes injectable fetchers so tests feed canned ERP rows and a
fetcher that raises ``RuntimeError`` simulates the ERP being offline.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.adapters.nelo.schemas import KpiObjectiveRow, KpiRow
from src.profit.services.kpi_objective_service import (
    ERP_OFFLINE_REASON,
    KpiObjectiveService,
)


def _kpi(
    *,
    kpi_id: int = 1,
    name: str = "OEE da fábrica",
    description: str | None = "Eficiência global do equipamento",
    display_order: int = 1,
) -> KpiRow:
    return KpiRow(
        kpi_id=kpi_id,
        kpi_date=date(2026, 1, 1),
        name=name,
        description=description,
        parent_kpi_id=None,
        display_order=display_order,
        is_automatic=True,
        role=None,
    )


def _objective(
    *,
    objective_id: int = 1,
    kpi_id: int = 1,
    value: float = 75.0,
    objective: float = 80.0,
    objective_date_logged: date = date(2026, 4, 1),
    objective_date: date | None = date(2026, 4, 1),
) -> KpiObjectiveRow:
    return KpiObjectiveRow(
        objective_id=objective_id,
        kpi_id=kpi_id,
        objective_date_logged=objective_date_logged,
        value=value,
        objective=objective,
        objective_date=objective_date,
    )


def _fetchers(kpis: list[KpiRow], objectives: list[KpiObjectiveRow]):
    async def _defs() -> list[KpiRow]:
        return kpis

    async def _objs() -> list[KpiObjectiveRow]:
        return objectives

    return _defs, _objs


# ─── happy path: objective vs realised ──────────────────────────────────


@pytest.mark.asyncio
async def test_kpi_with_objective_below_target():
    """Realised 75 against objective 80 → 93.75% → status 'near'."""
    defs, objs = _fetchers([_kpi()], [_objective(value=75.0, objective=80.0)])
    svc = KpiObjectiveService(definition_fetcher=defs, objective_fetcher=objs)
    result = await svc.objectives()

    assert result.erp_available is True
    assert result.kpi_count == 1
    assert result.with_objective_count == 1
    row = result.rows[0]
    assert row.has_objective is True
    assert row.value == 75.0
    assert row.objective == 80.0
    assert row.attainment_pct == 93.8
    assert row.status == "near"


@pytest.mark.asyncio
async def test_kpi_objective_hit_when_value_meets_target():
    """Realised 82 against objective 80 → >100% → status 'hit'."""
    defs, objs = _fetchers([_kpi()], [_objective(value=82.0, objective=80.0)])
    svc = KpiObjectiveService(definition_fetcher=defs, objective_fetcher=objs)
    result = await svc.objectives()

    row = result.rows[0]
    assert row.status == "hit"
    assert row.attainment_pct == 102.5
    assert result.hit_count == 1
    assert result.below_count == 0


@pytest.mark.asyncio
async def test_kpi_objective_below_when_far_from_target():
    """Realised 50 against objective 80 → 62.5% → status 'below'."""
    defs, objs = _fetchers([_kpi()], [_objective(value=50.0, objective=80.0)])
    svc = KpiObjectiveService(definition_fetcher=defs, objective_fetcher=objs)
    result = await svc.objectives()

    row = result.rows[0]
    assert row.status == "below"
    assert row.attainment_pct == 62.5
    assert result.below_count == 1
    assert result.hit_count == 0


# ─── KPI defined but no objective logged ────────────────────────────────


@pytest.mark.asyncio
async def test_kpi_without_objective_is_surfaced_honestly():
    """A KPI the ERP defined but never set an objective for shows
    has_objective=False with null numbers — no invented target."""
    defs, objs = _fetchers([_kpi(kpi_id=9, name="FPY")], [])
    svc = KpiObjectiveService(definition_fetcher=defs, objective_fetcher=objs)
    result = await svc.objectives()

    assert result.kpi_count == 1
    assert result.with_objective_count == 0
    row = result.rows[0]
    assert row.has_objective is False
    assert row.value is None
    assert row.objective is None
    assert row.attainment_pct is None
    assert row.status == "no_objective"


# ─── latest objective wins ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_latest_objective_record_per_kpi_wins():
    """Two objective records for the same KPI — the most recent
    objective_date is the one shown."""
    objectives = [
        _objective(
            objective_id=1, kpi_id=1, value=60.0, objective=80.0,
            objective_date=date(2026, 1, 1),
        ),
        _objective(
            objective_id=2, kpi_id=1, value=78.0, objective=80.0,
            objective_date=date(2026, 5, 1),
        ),
    ]
    defs, objs = _fetchers([_kpi()], objectives)
    svc = KpiObjectiveService(definition_fetcher=defs, objective_fetcher=objs)
    result = await svc.objectives()

    row = result.rows[0]
    assert row.value == 78.0
    assert row.objective_date == "2026-05-01"


# ─── ordering by display_order ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_rows_ordered_by_display_order():
    kpis = [
        _kpi(kpi_id=1, name="C", display_order=3),
        _kpi(kpi_id=2, name="A", display_order=1),
        _kpi(kpi_id=3, name="B", display_order=2),
    ]
    defs, objs = _fetchers(kpis, [])
    svc = KpiObjectiveService(definition_fetcher=defs, objective_fetcher=objs)
    result = await svc.objectives()

    assert [r.name for r in result.rows] == ["A", "B", "C"]


# ─── ERP offline degradation ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_erp_offline_yields_explicit_empty_result():
    """When the ERP adapter raises RuntimeError (sqlserver_enabled=False)
    the service returns erp_available=False with a reason — ZERO MOCKS."""

    async def _explode() -> list[KpiRow]:
        raise RuntimeError("sqlserver_enabled=False or sqlserver_url=None.")

    async def _explode_obj() -> list[KpiObjectiveRow]:  # pragma: no cover
        raise AssertionError("objective fetcher must not run after defs fail")

    svc = KpiObjectiveService(
        definition_fetcher=_explode, objective_fetcher=_explode_obj
    )
    result = await svc.objectives()

    assert result.erp_available is False
    assert result.reason == ERP_OFFLINE_REASON
    assert result.rows == []
    assert result.kpi_count == 0
    assert result.with_objective_count == 0


# ─── degenerate objective of zero ───────────────────────────────────────


@pytest.mark.asyncio
async def test_zero_objective_does_not_divide_by_zero():
    """An objective of 0 is degenerate — no ratio, but no crash."""
    defs, objs = _fetchers([_kpi()], [_objective(value=5.0, objective=0.0)])
    svc = KpiObjectiveService(definition_fetcher=defs, objective_fetcher=objs)
    result = await svc.objectives()

    row = result.rows[0]
    assert row.attainment_pct is None
    assert row.status == "hit"


# ─── to_dict shape ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_result_to_dict_shape():
    defs, objs = _fetchers([_kpi()], [_objective()])
    svc = KpiObjectiveService(definition_fetcher=defs, objective_fetcher=objs)
    result = await svc.objectives()
    payload = result.to_dict()

    assert payload["erp_available"] is True
    assert payload["kpi_count"] == 1
    assert isinstance(payload["items"], list)
    item = payload["items"][0]
    assert set(item.keys()) == {
        "kpi_id", "name", "description", "display_order", "has_objective",
        "value", "objective", "attainment_pct", "status", "objective_date",
    }
