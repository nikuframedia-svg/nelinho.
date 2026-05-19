"""
Tests for StockoutPredictor (Sprint Q.53.D).

Predicts the stockout date from real consumption history in the inventory
ledger. DB reads mocked via `FakeSession`; each test is an independent
spec (DAMP).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from src.supply.models import InventoryLedgerEntry
from src.supply.stockout_predictor import StockoutPredictor
from tests.conftest import TEST_TENANT_ID


def _consume(*, sku_id: str = "MAT-001", qty_out: Decimal, days_ago: int) -> InventoryLedgerEntry:
    """A 'consume' ledger entry `days_ago` days in the past."""
    return InventoryLedgerEntry(
        id=uuid4(),
        tenant_id=TEST_TENANT_ID,
        sku_id=sku_id,
        date=datetime.now(timezone.utc) - timedelta(days=days_ago),
        qty_opening=Decimal("0"),
        qty_in=Decimal("0"),
        qty_out=qty_out,
        qty_closing=Decimal("0"),
        transaction_type="consume",
        reference_id=None,
    )


class TestNoHistory:
    @pytest.mark.asyncio
    async def test_no_consumption_returns_null_date_none_confidence(self, fake_session):
        fake_session.queue_scalars([])  # no consume entries
        predictor = StockoutPredictor(fake_session, TEST_TENANT_ID)
        result = await predictor.predict(sku_id="MAT-001", on_hand=500.0)

        assert result["predicted_stockout_date"] is None
        assert result["confidence"] == "none"
        assert result["avg_daily_consumption"] == 0.0
        assert result["history_days"] == 0
        assert result["reason"] is not None

    @pytest.mark.asyncio
    async def test_only_zero_qty_entries_treated_as_no_history(self, fake_session):
        # Entries exist but all qty_out == 0 ⇒ honestly no demand signal.
        fake_session.queue_scalars([
            _consume(qty_out=Decimal("0"), days_ago=5),
            _consume(qty_out=Decimal("0"), days_ago=10),
        ])
        predictor = StockoutPredictor(fake_session, TEST_TENANT_ID)
        result = await predictor.predict(sku_id="MAT-001", on_hand=100.0)
        assert result["predicted_stockout_date"] is None
        assert result["confidence"] == "none"


class TestPrediction:
    @pytest.mark.asyncio
    async def test_steady_consumption_predicts_future_date(self, fake_session):
        # 40 days of steady 10/day consumption ⇒ avg ~10/day.
        rows = [_consume(qty_out=Decimal("10"), days_ago=d) for d in range(1, 41)]
        fake_session.queue_scalars(rows)
        predictor = StockoutPredictor(fake_session, TEST_TENANT_ID)
        result = await predictor.predict(sku_id="MAT-001", on_hand=100.0)

        assert result["predicted_stockout_date"] is not None
        # 100 on-hand / 10 per day ≈ 10 days out.
        predicted = date.fromisoformat(result["predicted_stockout_date"])
        assert 8 <= (predicted - date.today()).days <= 12
        assert result["avg_daily_consumption"] == pytest.approx(10.0, abs=0.5)
        assert result["confidence"] == "high"  # 40 steady days

    @pytest.mark.asyncio
    async def test_short_history_yields_low_confidence(self, fake_session):
        # Only 3 distinct consuming days ⇒ below the prediction floor.
        rows = [_consume(qty_out=Decimal("5"), days_ago=d) for d in (1, 2, 3)]
        fake_session.queue_scalars(rows)
        predictor = StockoutPredictor(fake_session, TEST_TENANT_ID)
        result = await predictor.predict(sku_id="MAT-001", on_hand=50.0)
        assert result["predicted_stockout_date"] is not None
        assert result["confidence"] == "low"

    @pytest.mark.asyncio
    async def test_volatile_demand_drops_confidence(self, fake_session):
        # 35 consuming days but extremely spiky ⇒ not "high".
        rows = []
        for d in range(1, 36):
            qty = Decimal("100") if d % 7 == 0 else Decimal("1")
            rows.append(_consume(qty_out=qty, days_ago=d))
        fake_session.queue_scalars(rows)
        predictor = StockoutPredictor(fake_session, TEST_TENANT_ID)
        result = await predictor.predict(sku_id="MAT-001", on_hand=200.0)
        assert result["confidence"] in ("medium", "low")
        assert result["confidence"] != "high"

    @pytest.mark.asyncio
    async def test_zero_on_hand_predicts_today(self, fake_session):
        rows = [_consume(qty_out=Decimal("10"), days_ago=d) for d in range(1, 31)]
        fake_session.queue_scalars(rows)
        predictor = StockoutPredictor(fake_session, TEST_TENANT_ID)
        result = await predictor.predict(sku_id="MAT-001", on_hand=0.0)
        # Already empty — stockout date is today, but history still graded.
        assert result["predicted_stockout_date"] == date.today().isoformat()
        assert result["confidence"] == "high"

    @pytest.mark.asyncio
    async def test_days_to_stockout_reported(self, fake_session):
        rows = [_consume(qty_out=Decimal("20"), days_ago=d) for d in range(1, 31)]
        fake_session.queue_scalars(rows)
        predictor = StockoutPredictor(fake_session, TEST_TENANT_ID)
        result = await predictor.predict(sku_id="MAT-001", on_hand=200.0)
        # 200 / 20 per day = 10 days.
        assert result["days_to_stockout"] == pytest.approx(10.0, abs=1.0)
        assert result["method"] == "consumption_ledger_trailing_avg"


class TestPredictMany:
    @pytest.mark.asyncio
    async def test_batch_keyed_by_sku(self, fake_session):
        # Two SKUs: first has history, second has none.
        rows_a = [_consume(sku_id="A", qty_out=Decimal("5"), days_ago=d)
                  for d in range(1, 31)]
        fake_session.queue_scalars(rows_a)   # predict("A")
        fake_session.queue_scalars([])       # predict("B")
        predictor = StockoutPredictor(fake_session, TEST_TENANT_ID)
        out = await predictor.predict_many(
            on_hand_by_sku={"A": 100.0, "B": 50.0}
        )
        assert set(out) == {"A", "B"}
        assert out["A"]["predicted_stockout_date"] is not None
        assert out["B"]["predicted_stockout_date"] is None
        assert out["B"]["confidence"] == "none"
