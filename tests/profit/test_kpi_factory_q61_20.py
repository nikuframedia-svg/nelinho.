"""Q.61.20 — KPI factory (consolidacao incremental).

Pina:
  * `throughput_*` delegam para `ThroughputService` (mesmo valor).
  * `defect_rate`/`oee`/`otd` lancam NotImplementedError com mensagem
    explicita — forca decisao Q.62 em vez de theater.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Optional
from unittest.mock import AsyncMock
from uuid import UUID

import pytest


TENANT = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@pytest.mark.asyncio
async def test_throughput_today_delegates_to_throughput_service(monkeypatch):
    """KPIFactory.throughput_today devolve o que ThroughputService devolve."""
    expected = Decimal("32500.00")

    async def _stub_throughput_today(self, *, as_of=None):
        return expected

    monkeypatch.setattr(
        "src.profit.services.throughput_service.ThroughputService.throughput_today",
        _stub_throughput_today,
    )

    from src.profit.kpi_factory import KPIFactory

    session = AsyncMock()
    factory = KPIFactory(session, TENANT)
    assert await factory.throughput_today() == expected


@pytest.mark.asyncio
async def test_throughput_mtd_ytd_trend_all_delegate(monkeypatch):
    """As 4 variantes de throughput delegam todas."""
    calls: dict[str, int] = {"today": 0, "mtd": 0, "ytd": 0, "trend": 0}

    async def _today(self, *, as_of=None):
        calls["today"] += 1
        return Decimal("1")

    async def _mtd(self, *, as_of=None):
        calls["mtd"] += 1
        return Decimal("2")

    async def _ytd(self, *, as_of=None):
        calls["ytd"] += 1
        return Decimal("3")

    async def _trend(self, *, days_back=14, until=None):
        calls["trend"] += 1
        return [{"day": str(date.today()), "eur": "1"}]

    monkeypatch.setattr(
        "src.profit.services.throughput_service.ThroughputService.throughput_today", _today,
    )
    monkeypatch.setattr(
        "src.profit.services.throughput_service.ThroughputService.throughput_mtd", _mtd,
    )
    monkeypatch.setattr(
        "src.profit.services.throughput_service.ThroughputService.throughput_ytd", _ytd,
    )
    monkeypatch.setattr(
        "src.profit.services.throughput_service.ThroughputService.throughput_trend", _trend,
    )

    from src.profit.kpi_factory import KPIFactory

    factory = KPIFactory(AsyncMock(), TENANT)
    assert await factory.throughput_today() == Decimal("1")
    assert await factory.throughput_mtd() == Decimal("2")
    assert await factory.throughput_ytd() == Decimal("3")
    assert isinstance(await factory.throughput_trend(), list)

    assert calls == {"today": 1, "mtd": 1, "ytd": 1, "trend": 1}


@pytest.mark.asyncio
async def test_defect_rate_raises_not_implemented_until_q62():
    """KPI ainda nao consolidado — falha alto em vez de mascarar."""
    from src.profit.kpi_factory import KPIFactory

    factory = KPIFactory(AsyncMock(), TENANT)
    with pytest.raises(NotImplementedError, match="Q.62"):
        await factory.defect_rate()


@pytest.mark.asyncio
async def test_oee_raises_not_implemented_until_q62():
    from src.profit.kpi_factory import KPIFactory

    factory = KPIFactory(AsyncMock(), TENANT)
    with pytest.raises(NotImplementedError, match="Q.62"):
        await factory.oee()


@pytest.mark.asyncio
async def test_otd_raises_not_implemented_until_q62():
    from src.profit.kpi_factory import KPIFactory

    factory = KPIFactory(AsyncMock(), TENANT)
    with pytest.raises(NotImplementedError, match="Q.62"):
        await factory.otd()
