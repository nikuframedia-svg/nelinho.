"""
Sub-sprint Q.46.B — Defect-by-zone hull map (F11).

`DefectZoneService.zone_map` faz o rollup factory-wide de retrabalho por
zona do casco — o mapa de calor / Pareto que responde "onde no barco a
fábrica falha". Cada teste lê como spec independente (DAMP) e corre
contra a FakeSession — sem DB real.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.quality.models.rework import ReworkEntry
from src.quality.services.defect_zone_service import DefectZoneService
from tests.conftest import TEST_TENANT_ID


def _rework(*, zone, of_id="OF-1", cost=None, hours=None) -> ReworkEntry:
    """Uma linha de retrabalho mínima para o teste de zona."""
    return ReworkEntry(
        tenant_id=TEST_TENANT_ID,
        of_id=of_id,
        error_code="risco-na-pintura",
        detected_at=datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
        location_zone=zone,
        cost_estimate_eur=Decimal(str(cost)) if cost is not None else None,
        hours_lost=Decimal(str(hours)) if hours is not None else None,
    )


@pytest.mark.asyncio
async def test_zone_map_empty_window_returns_honest_zeros(fake_session):
    # Sem eventos → zeros honestos, sem crash de divisão.
    fake_session.queue_scalars([])
    svc = DefectZoneService(fake_session, TEST_TENANT_ID)
    out = await svc.zone_map()

    assert out["total_events"] == 0
    assert out["events_with_zone"] == 0
    assert out["events_without_zone"] == 0
    assert out["zone_coverage_pct"] == 0.0
    assert out["distinct_zones"] == 0
    assert out["zones"] == []


@pytest.mark.asyncio
async def test_zone_map_aggregates_events_per_zone(fake_session):
    fake_session.queue_scalars([
        _rework(zone="Proa"),
        _rework(zone="Proa"),
        _rework(zone="Casco"),
    ])
    svc = DefectZoneService(fake_session, TEST_TENANT_ID)
    out = await svc.zone_map()

    assert out["total_events"] == 3
    assert out["distinct_zones"] == 2
    # Ordenado por nº de eventos — a zona que mais falha primeiro.
    assert out["zones"][0]["zone"] == "Proa"
    assert out["zones"][0]["events"] == 2
    assert out["zones"][1]["zone"] == "Casco"


@pytest.mark.asyncio
async def test_zone_map_share_and_cumulative_pareto(fake_session):
    fake_session.queue_scalars([
        _rework(zone="Proa"),
        _rework(zone="Proa"),
        _rework(zone="Proa"),
        _rework(zone="Casco"),
    ])
    svc = DefectZoneService(fake_session, TEST_TENANT_ID)
    out = await svc.zone_map()

    proa, casco = out["zones"]
    assert proa["share_pct"] == 75.0
    assert proa["cumulative_pct"] == 75.0
    # Pareto cumulativo fecha a 100% na última zona.
    assert casco["cumulative_pct"] == 100.0


@pytest.mark.asyncio
async def test_zone_map_coverage_reflects_unzoned_events(fake_session):
    # 4 eventos, só 1 com zona marcada — cobertura é 25%, o Pareto é parcial.
    fake_session.queue_scalars([
        _rework(zone="Proa"),
        _rework(zone=None),
        _rework(zone=None),
        _rework(zone=""),
    ])
    svc = DefectZoneService(fake_session, TEST_TENANT_ID)
    out = await svc.zone_map()

    assert out["total_events"] == 4
    assert out["events_with_zone"] == 1
    assert out["events_without_zone"] == 3
    assert out["zone_coverage_pct"] == 25.0
    # share é sobre os eventos COM zona, não sobre o total.
    assert out["zones"][0]["share_pct"] == 100.0


@pytest.mark.asyncio
async def test_zone_map_sums_cost_and_hours_and_orders(fake_session):
    fake_session.queue_scalars([
        _rework(zone="Proa", of_id="OF-1", cost=120, hours=4),
        _rework(zone="Proa", of_id="OF-2", cost=80, hours=2),
        _rework(zone="Proa", of_id="OF-1", cost=None, hours=None),
    ])
    svc = DefectZoneService(fake_session, TEST_TENANT_ID)
    out = await svc.zone_map()

    proa = out["zones"][0]
    assert proa["cost_estimate_eur"] == 200.0
    assert proa["hours_lost"] == 6.0
    # Duas ordens distintas (OF-1, OF-2) apesar de três eventos.
    assert proa["affected_orders"] == 2


@pytest.mark.asyncio
async def test_zone_map_top_n_caps_breakdown(fake_session):
    fake_session.queue_scalars([
        _rework(zone="Proa"),
        _rework(zone="Casco"),
        _rework(zone="Convés"),
    ])
    svc = DefectZoneService(fake_session, TEST_TENANT_ID)
    out = await svc.zone_map(top_n=2)

    assert len(out["zones"]) == 2
    # distinct_zones conta todas, mesmo as cortadas pelo top_n.
    assert out["distinct_zones"] == 3
