"""
Q.55.B.1 — `_build_operational_snapshot` tem de ir mesmo à base de dados.

Antes deste sub-sprint, a função devolvia uma estrutura de zeros sempre que
não lhe passassem um `kpi_snapshot` — ou seja, em quase todas as perguntas.
O copiloto via `has_data: false` e respondia "não tenho dados" mesmo com
164 ordens em curso e 100 mil eventos de retrabalho na BD.

Estes testes fixam o contrato novo: a função consulta `production_orders`
e `rework_entry` e devolve números reais.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from src.copilot.context_builder import _build_operational_snapshot
from tests.conftest import FakeSession

TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _window_start() -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=6)


@pytest.mark.asyncio
async def test_snapshot_le_ordens_e_retrabalho_da_bd():
    """Com dados na BD, o snapshot traz contagens reais e `has_data=True`."""
    session = FakeSession()
    last_detected = datetime.now(timezone.utc) - timedelta(days=1)
    # Ordem dos execute(): ordens-por-estado, top-fases, retrabalho-total, retrabalho-7d.
    session.queue_scalars([("IN_PROGRESS", 164), ("COMPLETED", 357)])
    session.queue_scalars([("Laminagem peças", 64), ("Corte peças", 55)])
    session.queue_scalars([(100688, last_detected)])
    session.queue_scalars([(1240,)])

    snap = await _build_operational_snapshot(
        session, TENANT, _window_start(), has_hr_role=False, kpi_snapshot=None,
    )

    assert snap["orders_in_progress"] == 164
    assert snap["orders_completed"] == 357
    assert snap["orders_total"] == 521
    assert snap["rework_events_total"] == 100688
    assert snap["rework_events_7d"] == 1240
    assert snap["rework_last_detected"] == last_detected.date().isoformat()
    assert snap["top_phases_by_wip"][0] == {"phase": "Laminagem peças", "wip": 64}
    assert snap["has_data"] is True
    assert snap["data_status"] == "DATA_AVAILABLE"


@pytest.mark.asyncio
async def test_snapshot_sobrepoe_kpis_quando_existem():
    """Quando há `kpi_snapshot`, OEE/disponibilidade vêm de lá; as contagens
    de ordens/retrabalho continuam a vir da BD."""
    session = FakeSession()
    session.queue_scalars([("IN_PROGRESS", 10)])
    session.queue_scalars([("Pintura", 10)])
    session.queue_scalars([(50, datetime.now(timezone.utc))])
    session.queue_scalars([(5,)])

    kpi = {
        "oee": {"value": 72.5},
        "availability": {"value": 88.0},
        "quality_fpy": {"value": 94.0},
    }
    snap = await _build_operational_snapshot(
        session, TENANT, _window_start(), has_hr_role=False, kpi_snapshot=kpi,
    )

    assert snap["oee"] == 72.5
    assert snap["availability"] == 88.0
    assert snap["quality"] == 94.0
    assert snap["orders_in_progress"] == 10  # da BD, não do kpi_snapshot
    assert snap["has_data"] is True


@pytest.mark.asyncio
async def test_snapshot_bd_vazia_degrada_sem_rebentar():
    """BD sem linhas → estrutura coerente, `has_data=False`, sem excepção."""
    session = FakeSession()
    session.queue_scalars([])  # ordens
    session.queue_scalars([])  # fases
    session.queue_scalars([(0, None)])  # retrabalho total
    session.queue_scalars([(0,)])  # retrabalho 7d

    snap = await _build_operational_snapshot(
        session, TENANT, _window_start(), has_hr_role=False, kpi_snapshot=None,
    )

    assert snap["orders_total"] == 0
    assert snap["rework_events_total"] == 0
    assert snap["rework_last_detected"] is None
    assert snap["top_phases_by_wip"] == []
    assert snap["has_data"] is False
    assert snap["data_status"] == "NO_DATA_AVAILABLE"
