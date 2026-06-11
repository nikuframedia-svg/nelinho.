"""
F4.E — ``_load_template_p50`` precisa de ORDER BY antes do ``.limit(1)``.

A mesma fase pode existir em vários ``RoutingTemplatePhase`` (61 padrões de
routing); sem ORDER BY o Postgres devolve uma linha arbitrária — o p50 da
margem variava entre execuções. Agora: mais recente primeiro
(``created_at DESC``), ``id DESC`` como tiebreak estável — o mesmo padrão
de ``_load_bonus``/``_compute_baseline`` no próprio ficheiro.
"""

from __future__ import annotations

from typing import Any, List

import pytest

from src.profit.services.margin_preview import _load_template_p50
from tests.conftest import TEST_TENANT_ID, FakeSession


class _RecordingResult:
    def __init__(self, scalar: Any) -> None:
        self._scalar = scalar

    def scalar_one_or_none(self) -> Any:
        return self._scalar


class _RecordingSession(FakeSession):
    def __init__(self) -> None:
        super().__init__()
        self.statements: List[Any] = []

    async def execute(self, stmt: Any, *args: Any, **kwargs: Any):
        self.statements.append(stmt)
        scalar = self._scalar_queue.pop(0) if self._scalar_queue else None
        return _RecordingResult(scalar)


@pytest.mark.asyncio
async def test_load_template_p50_orders_by_recency_with_stable_tiebreak():
    session = _RecordingSession()
    session.queue_scalar(None)

    await _load_template_p50(session, TEST_TENANT_ID, "40")

    sql = str(session.statements[0]).lower()
    assert "order by" in sql, sql
    assert "created_at desc" in sql, sql
    assert "id desc" in sql, sql  # tiebreak estável quando created_at empata
    assert "limit" in sql, sql
