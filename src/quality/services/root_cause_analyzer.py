"""
ProdPlan ONE - Root-Cause Statistical Analyser (Sprint R.5 / QA09)
====================================================================

Instead of training an ML model (deferred), we compute simple statistical
correlations between `ReworkEntry` occurrences and candidate dimensions
(worker, model, mold, supplier, day-of-week). The method:

1. Fetch rework rows for a given error_code + window.
2. For each candidate dimension, compute the frequency distribution.
3. Compare it against the expected uniform distribution to flag outliers
   via chi-squared-like z-score.

Returns a ranked list — callers use it to seed a runbook or to decide
where to invest a preventive intervention. The analyser never crashes
when a dimension has zero samples.
"""

from __future__ import annotations

import math
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.quality.models.rework import ReworkEntry


CANDIDATE_DIMENSIONS = (
    "causer_employee_id",
    "model_id",
    "mold_id",
    "supplier_id",
    "phase_id_causer",
    "material_lot_id",
)


class RootCauseAnalyzer:
    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def analyse(
        self,
        *,
        error_code: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        top_n_per_dimension: int = 5,
    ) -> dict[str, Any]:
        since = since or datetime.now(timezone.utc) - timedelta(days=90)
        until = until or datetime.now(timezone.utc)

        stmt = select(ReworkEntry).where(
            and_(
                ReworkEntry.tenant_id == self.tenant_id,
                ReworkEntry.error_code == error_code,
                ReworkEntry.detected_at >= since,
                ReworkEntry.detected_at <= until,
            )
        )
        rows = list((await self.session.execute(stmt)).scalars().all())
        n = len(rows)
        if n == 0:
            return {
                "error_code": error_code,
                "total_events": 0,
                "dimensions": {},
                "summary": "No rework events in window",
            }

        dimensions: dict[str, list[dict[str, Any]]] = {}
        for dim in CANDIDATE_DIMENSIONS:
            counts = Counter(
                _dim_value(row, dim) for row in rows
                if _dim_value(row, dim) is not None
            )
            if not counts:
                continue
            ranked = _rank_counts(counts, total=n, top_n=top_n_per_dimension)
            if ranked:
                dimensions[dim] = ranked

        return {
            "error_code": error_code,
            "total_events": n,
            "window": {
                "from": since.isoformat(),
                "to": until.isoformat(),
            },
            "dimensions": dimensions,
            "summary": _summarise(dimensions, n),
        }


def _dim_value(row: ReworkEntry, dim: str) -> Optional[Any]:
    value = getattr(row, dim, None)
    if value is None:
        return None
    return str(value)


def _rank_counts(
    counter: Counter, *, total: int, top_n: int,
) -> list[dict[str, Any]]:
    unique = max(1, len(counter))
    expected = total / unique
    # Bail-out: if all values are identical to expectation, no signal.
    if expected <= 0:
        return []
    ranked = []
    for value, count in counter.most_common(top_n):
        # Pearson-style z-score for a binomial-ish count.
        stddev = math.sqrt(max(expected * (1 - 1 / unique), 1e-6))
        z = (count - expected) / stddev
        ranked.append({
            "value": value,
            "count": int(count),
            "share_pct": round(100.0 * count / total, 2),
            "expected": round(expected, 2),
            "z_score": round(z, 2),
            "signal": _signal(z),
        })
    return ranked


def _signal(z: float) -> str:
    if z >= 2.5:
        return "strong_positive"
    if z >= 1.5:
        return "positive"
    if z <= -2.5:
        return "strong_negative"
    return "neutral"


def _summarise(dimensions: dict[str, list[dict[str, Any]]], n: int) -> str:
    highlights = []
    for dim, ranked in dimensions.items():
        top = ranked[0] if ranked else None
        if top and top["signal"].startswith("strong"):
            highlights.append(f"{dim}={top['value']} ({top['share_pct']}% of {n})")
    if highlights:
        return "Dominant contributors: " + "; ".join(highlights)
    return f"No single dimension dominates (n={n})"
