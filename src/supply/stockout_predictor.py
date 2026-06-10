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

Sprint Q.54.F — why this stays a heuristic, not an ML model
-----------------------------------------------------------
The Q.54 brief asked: train an ML model on `InventoryLedgerEntry` if
viable, otherwise improve the heuristic and document why. We chose to
improve the heuristic, deliberately:

* The target (`days_to_stockout`) is *deterministic*, not learned —
  `on_hand / consumption_rate`. An ML model would only ever be
  predicting the consumption rate, and per-SKU consumption history is
  short and sparse (a single material's `consume` rows over 90 days),
  far below the ≥20-with-signal floor the GBM models in `src/ml/`
  need. Fitting one per SKU would overfit; one global model can't
  capture per-material seasonality.
* The honest gain over a flat trailing average is *recency weighting*:
  if a material's consumption is trending up, the last fortnight should
  count more than day 1. So `predict()` now estimates the daily rate
  with an exponentially-weighted moving average (EWMA) over the
  per-day consumption series — recent days weigh more, but every day
  still contributes. No data is invented; it is the same ledger rows,
  weighted by age. The flat mean is kept as `avg_daily_consumption_flat`
  for transparency, and a `trend` label ("rising"/"falling"/"steady")
  is surfaced so the UI can flag accelerating depletion.

If per-SKU history ever grows enough (multi-year, dense), a forecasting
model (`SupplyForecast` already has the table) becomes worthwhile — but
that is a separate, data-gated sprint, not this one.
"""

from __future__ import annotations

import logging
import statistics
from src.shared.time import local_today
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

# Sprint Q.54.F — EWMA half-life (days). The weight of a day's
# consumption halves every `_EWMA_HALFLIFE_DAYS` days into the past, so
# the trailing fortnight dominates a 90-day window without discarding
# the older rows entirely. 14 days ≈ NELO's material reorder rhythm.
_EWMA_HALFLIFE_DAYS = 14.0

# Relative gap between the recency-weighted rate and the flat mean
# before we label the consumption a trend rather than steady noise.
_TREND_THRESHOLD = 0.15  # 15%


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
        today = as_of or local_today()
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
        avg_daily_flat = total_consumed / span

        # Sprint Q.54.F — recency-weighted (EWMA) daily rate. We build a
        # dense per-calendar-day series across the observed span (idle
        # days contribute zero consumption) and weight each day by its
        # age: weight = 0.5 ** (age_days / half_life). The rate is the
        # weighted mean. A material whose consumption is accelerating
        # gets a higher rate (earlier stockout) than the flat mean would
        # give; a decelerating one gets a lower rate. No invented data —
        # same ledger rows, weighted by age.
        avg_daily = _ewma_daily_rate(
            per_day, span_end=max(per_day), span_days=span,
        )
        if avg_daily <= 0:
            avg_daily = avg_daily_flat  # degenerate guard — fall back to flat

        # Trend label — is the recency-weighted rate materially above or
        # below the flat mean? Surfaced so the UI can flag accelerating
        # depletion ("rising") vs a tapering material ("falling").
        trend = _classify_trend(avg_daily, avg_daily_flat)

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
            avg_daily_consumption_flat=round(avg_daily_flat, 4),
            trend=trend,
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


def _ewma_daily_rate(
    per_day: dict[date, Decimal],
    *,
    span_end: date,
    span_days: int,
) -> float:
    """Recency-weighted mean daily consumption (Sprint Q.54.F).

    `per_day` maps a calendar day to that day's consumed quantity. We
    build a dense series across the whole observed span — every day in
    `[span_end - span_days + 1, span_end]` — so idle days correctly
    contribute zero. Each day is weighted by `0.5 ** (age / half_life)`
    where `age` is days before `span_end`. The result is the
    weight-normalised mean: ``Σ(weight·qty) / Σ(weight)``.

    A flat series returns the same number as the plain mean; an
    accelerating series returns a higher rate (recent high days weigh
    more), a tapering one returns a lower rate.
    """
    if not per_day or span_days <= 0:
        return 0.0

    weighted_sum = 0.0
    weight_total = 0.0
    for age in range(span_days):
        day = span_end - timedelta(days=age)
        qty = float(per_day.get(day, Decimal("0")))
        weight = 0.5 ** (age / _EWMA_HALFLIFE_DAYS)
        weighted_sum += weight * qty
        weight_total += weight

    if weight_total <= 0:  # pragma: no cover — span_days>0 guarantees >0
        return 0.0
    return weighted_sum / weight_total


def _classify_trend(rate_weighted: float, rate_flat: float) -> str:
    """Label the consumption trend by comparing the recency-weighted
    rate against the flat mean. "rising" = depleting faster than the
    window average; "falling" = tapering off; "steady" otherwise.
    """
    if rate_flat <= 0:
        return "steady"
    delta = (rate_weighted - rate_flat) / rate_flat
    if delta > _TREND_THRESHOLD:
        return "rising"
    if delta < -_TREND_THRESHOLD:
        return "falling"
    return "steady"


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
    avg_daily_consumption_flat: Optional[float] = None,
    trend: str = "steady",
) -> dict[str, Any]:
    return {
        "sku_id": sku_id,
        "predicted_stockout_date": (
            predicted_stockout_date.isoformat() if predicted_stockout_date else None
        ),
        "confidence": confidence,
        # Sprint Q.54.F — `avg_daily_consumption` is now the recency-
        # weighted (EWMA) rate; `avg_daily_consumption_flat` keeps the
        # plain trailing mean for transparency, and `trend` flags
        # accelerating vs tapering depletion.
        "avg_daily_consumption": avg_daily_consumption,
        "avg_daily_consumption_flat": (
            avg_daily_consumption_flat
            if avg_daily_consumption_flat is not None
            else avg_daily_consumption
        ),
        "trend": trend,
        "history_days": history_days,
        "total_consumed": total_consumed,
        "window_days": window_days,
        "days_to_stockout": days_to_stockout,
        "reason": reason,
        "method": "consumption_ledger_ewma",
    }
