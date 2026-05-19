"""
ProdPlan ONE - Stockout Predictor (Sprint Q.53.D)
==================================================

Predicts the date a material runs out of stock from its *real consumption
history* — not a guessed coefficient.

The current "days to stockout" heuristic in `MaterialService.get_position`
is `on_hand / avg_daily_demand`, where `avg_daily_demand` is whatever was
typed into `ROPConfig`. That number is often stale or absent.

This predictor instead reads the inventory ledger (`InventoryLedgerEntry`,
`transaction_type="consume"`, the `qty_out` column) — the factory's actual
issue movements — over a trailing window. It returns:

* `predicted_stockout_date` — `today + on_hand / avg_daily_consumption`;
* `confidence` — `"high" | "medium" | "low" | "none"`.

Honesty rules (ZERO MOCKS):

* No consumption history at all  → date `null`, confidence `"none"`.
* On-hand at or below zero       → date is today, confidence reflects history.
* Average consumption is zero    → date `null` (no demand ⇒ never depletes).

Confidence is a function of (a) how many days of history we have and
(b) how steady the consumption is (coefficient of variation). It is *not*
a probability — it is a coarse trust label for the UI.
"""

from __future__ import annotations

import logging
import statistics
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import InventoryLedgerEntry

logger = logging.getLogger(__name__)


# Trailing window of consumption history used to estimate the daily rate.
DEFAULT_WINDOW_DAYS = 90

# Confidence gates.
_MIN_DAYS_FOR_PREDICTION = 7   # fewer distinct consuming days ⇒ confidence "low"
_HIGH_CONF_MIN_DAYS = 30       # at least a month of history for "high"
_MEDIUM_CONF_MIN_DAYS = 14
# Coefficient of variation: steady demand keeps confidence up; spiky demand
# drops it one notch.
_STEADY_CV = 0.5
_VOLATILE_CV = 1.2


class StockoutPredictor:
    """Consumption-history-based stockout-date estimator."""

    def __init__(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        *,
        window_days: int = DEFAULT_WINDOW_DAYS,
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.window_days = max(7, window_days)

    async def predict(
        self,
        *,
        sku_id: str,
        on_hand: float,
        as_of: Optional[date] = None,
    ) -> dict[str, Any]:
        """Predict the stockout date for one SKU.

        `on_hand` is passed in (the caller already has it) so the predictor
        stays focused on the consumption side. `as_of` defaults to today.

        Returns a document — see module docstring for the honesty rules.
        """
        today = as_of or date.today()
        since = datetime.now(timezone.utc) - timedelta(days=self.window_days)

        stmt = (
            select(InventoryLedgerEntry)
            .where(
                and_(
                    InventoryLedgerEntry.tenant_id == self.tenant_id,
                    InventoryLedgerEntry.sku_id == sku_id,
                    InventoryLedgerEntry.transaction_type == "consume",
                    InventoryLedgerEntry.date >= since,
                )
            )
            .order_by(InventoryLedgerEntry.date.asc())
        )
        rows = list((await self.session.execute(stmt)).scalars().all())

        # Sum consumption (qty_out) per calendar day.
        per_day: dict[date, Decimal] = {}
        for r in rows:
            if r.date is None:
                continue
            day = r.date.date() if hasattr(r.date, "date") else r.date
            qty_out = Decimal(str(r.qty_out or 0))
            if qty_out <= 0:
                continue
            per_day[day] = per_day.get(day, Decimal("0")) + qty_out

        consuming_days = len(per_day)
        total_consumed = float(sum(per_day.values(), start=Decimal("0")))

        if consuming_days == 0 or total_consumed <= 0:
            return _result(
                sku_id=sku_id,
                predicted_stockout_date=None,
                confidence="none",
                avg_daily_consumption=0.0,
                history_days=consuming_days,
                total_consumed=total_consumed,
                window_days=self.window_days,
                reason=(
                    "Sem consumo registado no ledger nos últimos "
                    f"{self.window_days} dias — sem base para prever rutura."
                ),
            )

        # Average over the *observed span* of consumption, not the whole
        # window — a material first consumed 10 days ago should not be
        # diluted by 80 idle days. Span is bounded below by the number of
        # consuming days so a burst on a single day cannot inflate the rate.
        observed_span = (max(per_day) - min(per_day)).days + 1
        span = max(observed_span, consuming_days)
        avg_daily = total_consumed / span

        # Confidence: history depth × steadiness.
        confidence = _grade_confidence(
            history_days=consuming_days,
            daily_values=[float(v) for v in per_day.values()],
        )

        if avg_daily <= 0:  # pragma: no cover — defended by total_consumed check
            return _result(
                sku_id=sku_id,
                predicted_stockout_date=None,
                confidence="none",
                avg_daily_consumption=0.0,
                history_days=consuming_days,
                total_consumed=total_consumed,
                window_days=self.window_days,
                reason="Consumo médio nulo.",
            )

        days_left = max(0.0, on_hand) / avg_daily
        stockout_date = today + timedelta(days=int(days_left))

        return _result(
            sku_id=sku_id,
            predicted_stockout_date=stockout_date,
            confidence=confidence,
            avg_daily_consumption=round(avg_daily, 4),
            history_days=consuming_days,
            total_consumed=round(total_consumed, 4),
            window_days=self.window_days,
            reason=None,
            days_to_stockout=round(days_left, 2),
        )

    async def predict_many(
        self,
        *,
        on_hand_by_sku: dict[str, float],
        as_of: Optional[date] = None,
    ) -> dict[str, dict[str, Any]]:
        """Predict for a batch of SKUs. Keyed by sku_id.

        Used by `/materials/from-bom` so the catalogue can show a stockout
        date column without N round-trips from the caller.
        """
        out: dict[str, dict[str, Any]] = {}
        for sku_id, on_hand in on_hand_by_sku.items():
            out[sku_id] = await self.predict(
                sku_id=sku_id, on_hand=on_hand, as_of=as_of,
            )
        return out


def _grade_confidence(*, history_days: int, daily_values: list[float]) -> str:
    """Coarse trust label for the predicted date.

    `history_days` is the count of distinct days with consumption.
    `daily_values` is the per-day consumed quantity (used for variability).
    """
    if history_days < _MIN_DAYS_FOR_PREDICTION:
        return "low"

    # Coefficient of variation — std / mean. Spiky demand erodes trust.
    cv = 0.0
    if len(daily_values) >= 2:
        mean = statistics.fmean(daily_values)
        if mean > 0:
            cv = statistics.pstdev(daily_values) / mean

    if history_days >= _HIGH_CONF_MIN_DAYS:
        base = "high"
    elif history_days >= _MEDIUM_CONF_MIN_DAYS:
        base = "medium"
    else:
        base = "low"

    # Volatile demand drops one notch; very steady demand never upgrades
    # (history depth is the ceiling).
    if cv >= _VOLATILE_CV:
        return {"high": "medium", "medium": "low", "low": "low"}[base]
    if cv >= _STEADY_CV:
        return {"high": "medium", "medium": "medium", "low": "low"}[base]
    return base


def _result(
    *,
    sku_id: str,
    predicted_stockout_date: Optional[date],
    confidence: str,
    avg_daily_consumption: float,
    history_days: int,
    total_consumed: float,
    window_days: int,
    reason: Optional[str],
    days_to_stockout: Optional[float] = None,
) -> dict[str, Any]:
    return {
        "sku_id": sku_id,
        "predicted_stockout_date": (
            predicted_stockout_date.isoformat() if predicted_stockout_date else None
        ),
        "confidence": confidence,
        "avg_daily_consumption": avg_daily_consumption,
        "history_days": history_days,
        "total_consumed": total_consumed,
        "window_days": window_days,
        "days_to_stockout": days_to_stockout,
        "reason": reason,
        "method": "consumption_ledger_trailing_avg",
    }
