"""
F4.E — FPY conta ordens na MESMA unidade nos dois lados da fracção.

Antes deste fix, ``first_pass_yield()`` comparava:

* total  = ``count(CuratedOrder.id)``           → nº de LINHAS (uma por
  (ingestion_id, of_id) — a mesma OF re-ingerida conta 2×);
* rework = ``count(distinct ReworkEntry.of_id)`` → nº de ORDENS.

Com re-ingestões o denominador inflava e o FPY saía artificialmente alto.
Agora ambos contam ``of_id`` distintos.
"""

from __future__ import annotations

from typing import Any, List

import pytest

from src.profit.services.dashboard_metrics_service import DashboardMetricsService
from tests.conftest import TEST_TENANT_ID, FakeSession


class _RecordingResult:
    def __init__(self, scalar: Any) -> None:
        self._scalar = scalar

    def scalar_one(self) -> Any:
        return self._scalar


class _RecordingSession(FakeSession):
    """FakeSession que grava os statements executados (para inspecionar o
    SQL gerado) e suporta `.scalar_one()` usado pelo serviço."""

    def __init__(self) -> None:
        super().__init__()
        self.statements: List[Any] = []

    async def execute(self, stmt: Any, *args: Any, **kwargs: Any):
        self.statements.append(stmt)
        scalar = self._scalar_queue.pop(0) if self._scalar_queue else None
        return _RecordingResult(scalar)


@pytest.mark.asyncio
async def test_fpy_total_counts_distinct_of_ids():
    session = _RecordingSession()
    session.queue_scalar(10)  # total (ordens distintas concluídas)
    session.queue_scalar(3)   # ordens distintas com rework

    svc = DashboardMetricsService(session, TEST_TENANT_ID)
    result = await svc.first_pass_yield(window_days=30)

    # O denominador tem de ser DISTINCT sobre o business key of_id —
    # count(id) contava linhas (re-ingestões da mesma OF inflavam o total).
    total_sql = str(session.statements[0]).lower()
    assert "distinct" in total_sql, total_sql
    assert "of_id" in total_sql, total_sql
    assert ".id" not in total_sql.replace("of_id", ""), (
        "denominador não pode contar a PK uuid"
    )

    # Aritmética inalterada: (10 - 3) / 10 = 70%.
    assert result.orders_total == 10
    assert result.orders_with_rework == 3
    assert result.first_pass_yield_pct == pytest.approx(70.0)


@pytest.mark.asyncio
async def test_fpy_zero_total_is_honest_zero():
    # Estado-vazio honesto (invariante #8): sem ordens → 0%, não NaN/inventado.
    session = _RecordingSession()
    session.queue_scalar(0)
    session.queue_scalar(0)

    svc = DashboardMetricsService(session, TEST_TENANT_ID)
    result = await svc.first_pass_yield(window_days=30)

    assert result.orders_total == 0
    assert result.first_pass_yield_pct == 0.0
