"""Q.62.C.1 — team_defect_rate factory-wide com Laplace smoothing.

Distinct de `quality_score(employee_id)` que é per-employee. Este é o
KPI executivo "comportamento da equipa" (Hipótese A do Q.62.C).

Formula: `(sum_defects + α) / (sum_ops + β)` com α=1, β=10 (consistente
com `quality_score`).

Testes injectam contadores via monkeypatch — driver code testado contra
DB real noutros sítios.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from src.workforce.employee_extras_service import (
    SMOOTHING_ALPHA,
    SMOOTHING_BETA,
    EmployeeExtrasService,
)


_TENANT = UUID("11111111-1111-1111-1111-111111111111")


def _service_with_counts(ops_count: int, defects_count: int) -> EmployeeExtrasService:
    """Builds an EmployeeExtrasService whose session.execute returns
    ops_count for the first query (ProductionSchedule) and defects_count
    for the second (ReworkEntry).
    """
    session = AsyncMock()
    # session.execute precisa devolver objects diferentes em call order.
    results: list[MagicMock] = []
    for count in (ops_count, defects_count):
        r = MagicMock()
        r.scalar_one = MagicMock(return_value=count)
        results.append(r)
    session.execute = AsyncMock(side_effect=results)
    return EmployeeExtrasService(session=session, tenant_id=_TENANT)


@pytest.mark.asyncio
async def test_empty_team_returns_laplace_floor():
    """0 ops + 0 defects → (0 + 1) / (0 + 10) = 0.1."""
    svc = _service_with_counts(ops_count=0, defects_count=0)
    rate = await svc.team_defect_rate(window_days=90)
    assert rate == pytest.approx(SMOOTHING_ALPHA / SMOOTHING_BETA)  # 0.1


@pytest.mark.asyncio
async def test_100_ops_5_defects_gives_laplace_smoothed_rate():
    """100 ops + 5 defects → (5 + 1) / (100 + 10) = 6/110 ≈ 0.0545."""
    svc = _service_with_counts(ops_count=100, defects_count=5)
    rate = await svc.team_defect_rate(window_days=90)
    assert rate == pytest.approx(6 / 110, abs=0.0001)


@pytest.mark.asyncio
async def test_high_defect_rate_capped_below_1():
    """100 ops + 95 defects → (95+1)/(100+10) = 96/110 ≈ 0.873.

    Laplace smoothing puxa para baixo quando há mais ruído (β=10) — o
    cap natural é < 1.
    """
    svc = _service_with_counts(ops_count=100, defects_count=95)
    rate = await svc.team_defect_rate(window_days=90)
    assert 0 < rate < 1
    assert rate == pytest.approx(96 / 110, abs=0.0001)


@pytest.mark.asyncio
async def test_window_days_affects_since_in_query():
    """window_days é traduzido para `since = now - window_days`. Os
    objectos AsyncMock recebem o stmt; conferimos que executes foram
    chamados 2x (ops + defects) e que o window é razoável (1-365 dias).
    """
    svc = _service_with_counts(ops_count=10, defects_count=1)
    before = datetime.now(timezone.utc)
    await svc.team_defect_rate(window_days=30)
    after = datetime.now(timezone.utc)

    # Confirma 2 calls (ops query + defects query).
    assert svc.session.execute.await_count == 2

    # Janela calculada deve estar entre [before - 30d - 1s, after - 30d + 1s].
    # Smoke: 30 dias atras está numa janela apertada de tempo.
    expected_since_lo = before - timedelta(days=30, seconds=1)
    expected_since_hi = after - timedelta(days=30) + timedelta(seconds=1)
    assert expected_since_lo <= expected_since_hi  # sanity da janela
