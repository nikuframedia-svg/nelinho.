"""Tests for SemanticQueries.wip() active vs zombie split (Sprint Q.8).

Excel snapshot showed 41% of "open" orders are zombies (created >6
months ago, never closed). The wip() query buckets them so the
Dashboard stops over-reporting WIP.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest


class _StubResult:
    def __init__(self, row):
        self._row = row

    def one(self):
        return self._row

    def scalar(self):
        return self._row


@pytest.mark.asyncio
async def test_wip_splits_active_and_zombie_buckets(monkeypatch):
    """Open orders within 180d window count as ACTIVE; older count as ZOMBIE.
    Total exposed for backwards compatibility."""
    from src.factory_data_product.semantic.queries import SemanticQueries

    fake_db = AsyncMock()
    # Two execute() calls: first the open_query (total/active/zombie),
    # then the open_phases_query.
    fake_db.execute = AsyncMock(side_effect=[
        _StubResult(SimpleNamespace(total=1387, active=822, zombie=565)),
        _StubResult((10, 1500.0, 8)),
    ])

    sq = SemanticQueries(db=fake_db, ingestion_id=uuid4())

    result = await sq.wip()

    assert result["data"]["open_orders"] == 1387
    assert result["data"]["wip_active"] == 822
    assert result["data"]["wip_zombie"] == 565
    assert result["data"]["zombie_pct"] == 40.7
    assert result["metadata"]["zombie_cutoff_days"] == 180


@pytest.mark.asyncio
async def test_wip_zero_zombies_when_all_recent(monkeypatch):
    from src.factory_data_product.semantic.queries import SemanticQueries

    fake_db = AsyncMock()
    fake_db.execute = AsyncMock(side_effect=[
        _StubResult(SimpleNamespace(total=50, active=50, zombie=0)),
        _StubResult((100, 800.0, 100)),
    ])

    sq = SemanticQueries(db=fake_db, ingestion_id=uuid4())
    result = await sq.wip()

    assert result["data"]["wip_active"] == 50
    assert result["data"]["wip_zombie"] == 0
    assert result["data"]["zombie_pct"] == 0.0


@pytest.mark.asyncio
async def test_wip_handles_zero_open_orders_without_division_error(monkeypatch):
    from src.factory_data_product.semantic.queries import SemanticQueries

    fake_db = AsyncMock()
    fake_db.execute = AsyncMock(side_effect=[
        _StubResult(SimpleNamespace(total=0, active=0, zombie=0)),
        _StubResult((0, None, 0)),
    ])

    sq = SemanticQueries(db=fake_db, ingestion_id=uuid4())
    result = await sq.wip()

    assert result["data"]["open_orders"] == 0
    assert result["data"]["zombie_pct"] == 0.0
