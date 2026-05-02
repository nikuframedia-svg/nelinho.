"""Tests for SemanticQueries.lead_time() (Sprint Q.9 1.1 fix).

The query previously referenced `CuratedOrder.lead_time_days` which does
not exist on the model — every call would raise AttributeError. Now
the lead time is computed inline as `data_conclusao - data_entrada`.
"""

from __future__ import annotations

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
async def test_lead_time_returns_avg_min_max_for_completed_orders():
    """Aggregates avg/min/max of (data_conclusao - data_entrada) over
    orders completed in the window."""
    from src.factory_data_product.semantic.queries import SemanticQueries

    fake_db = AsyncMock()
    # SQLAlchemy returns the row tuple via .one(); the agg result has
    # named attributes (total_orders / avg_lead_time / ...).
    fake_db.execute = AsyncMock(return_value=_StubResult(
        SimpleNamespace(
            total_orders=3,
            avg_lead_time=21.0,
            min_lead_time=10.0,
            max_lead_time=42.0,
        )
    ))

    sq = SemanticQueries(db=fake_db, ingestion_id=uuid4())

    result = await sq.lead_time_analysis(days_back=90)

    assert result["data"]["total_completed_orders"] == 3
    assert result["data"]["avg_lead_time_days"] == 21.0
    assert result["data"]["min_lead_time_days"] == 10.0
    assert result["data"]["max_lead_time_days"] == 42.0
    assert result["metadata"]["days_back"] == 90


@pytest.mark.asyncio
async def test_lead_time_handles_no_completed_orders():
    """Empty window → zero/None across the board, no division errors."""
    from src.factory_data_product.semantic.queries import SemanticQueries

    fake_db = AsyncMock()
    fake_db.execute = AsyncMock(return_value=_StubResult(
        SimpleNamespace(
            total_orders=0,
            avg_lead_time=None,
            min_lead_time=None,
            max_lead_time=None,
        )
    ))

    sq = SemanticQueries(db=fake_db, ingestion_id=uuid4())
    result = await sq.lead_time_analysis()

    assert result["data"]["total_completed_orders"] == 0
    assert result["data"]["avg_lead_time_days"] is None
    assert result["data"]["min_lead_time_days"] is None
    assert result["data"]["max_lead_time_days"] is None
