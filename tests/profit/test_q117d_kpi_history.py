"""Q.117.D — testes do serviço de histórico de KPIs.

Padrão FakeSession (Q.61.02) — sem PostgreSQL, sem SQLite.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional
from uuid import UUID

import pytest

from src.profit.services.kpi_history import (
    SNAPSHOT_KPIS,
    capture_kpi_snapshot,
    get_kpi_history,
)
from tests.conftest import FakeSession

TENANT = UUID("00000000-0000-0000-0000-000000000001")


@dataclass
class _Metric:
    value: Optional[float]


def _kpis(**vals: Optional[float]) -> dict:
    return {name: _Metric(vals.get(name)) for name in SNAPSHOT_KPIS}


@pytest.mark.asyncio
async def test_capture_insere_um_ponto_por_kpi():
    session = FakeSession()
    # Cada KPI faz um existing-check → não existe ainda.
    for _ in SNAPSHOT_KPIS:
        session.queue_scalar(None)

    written = await capture_kpi_snapshot(
        session, TENANT, on_date=date(2026, 5, 29),
        kpis=_kpis(quality_fpy=96.5, rework_rate=3.1, orders_total=521),
    )

    assert written == len(SNAPSHOT_KPIS)
    assert len(session.added) == len(SNAPSHOT_KPIS)
    by_name = {s.kpi_name: s for s in session.added}
    assert by_name["quality_fpy"].value == 96.5
    assert by_name["quality_fpy"].unit == "%"
    assert by_name["orders_total"].value == 521.0
    assert session.commit_calls == 1


@pytest.mark.asyncio
async def test_capture_value_none_quando_sem_dados():
    session = FakeSession()
    for _ in SNAPSHOT_KPIS:
        session.queue_scalar(None)

    await capture_kpi_snapshot(
        session, TENANT, on_date=date(2026, 5, 29), kpis=_kpis(),
    )

    by_name = {s.kpi_name: s for s in session.added}
    # Sem dados → NULL, nunca 0 falso.
    assert by_name["quality_fpy"].value is None


@pytest.mark.asyncio
async def test_capture_idempotente_actualiza_existente():
    session = FakeSession()

    class _Existing:
        def __init__(self) -> None:
            self.value = 90.0
            self.unit = "%"

    existing = _Existing()
    # Primeiro KPI já existe; restantes não.
    session.queue_scalar(existing)
    for _ in range(len(SNAPSHOT_KPIS) - 1):
        session.queue_scalar(None)

    await capture_kpi_snapshot(
        session, TENANT, on_date=date(2026, 5, 29),
        kpis=_kpis(quality_fpy=97.0),
    )

    assert existing.value == 97.0
    # Só os restantes foram adicionados (o existente foi actualizado).
    assert len(session.added) == len(SNAPSHOT_KPIS) - 1


@pytest.mark.asyncio
async def test_history_kpi_invalido_devolve_none():
    session = FakeSession()
    result = await get_kpi_history(session, TENANT, "kpi_inexistente")
    assert result is None


@pytest.mark.asyncio
async def test_history_devolve_pontos_ordenados():
    session = FakeSession()

    @dataclass
    class _Row:
        captured_date: date
        value: Optional[float]

    session.queue_scalars([
        _Row(date(2026, 5, 27), 95.0),
        _Row(date(2026, 5, 28), None),
        _Row(date(2026, 5, 29), 96.2),
    ])

    result = await get_kpi_history(session, TENANT, "quality_fpy", days=30)

    assert result is not None
    assert result["name"] == "quality_fpy"
    assert result["unit"] == "%"
    assert result["points"][0] == {"date": "2026-05-27", "value": 95.0}
    # Dia sem dados preservado como None (gráfico salta o ponto).
    assert result["points"][1]["value"] is None
