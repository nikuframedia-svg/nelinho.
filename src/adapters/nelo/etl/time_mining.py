"""Q.20.F — historical time mining (OF_FP → routing_template_phase).

The routing templates built by Q.20.B carry NULL durations. This mirror
fills ``duration_p50_h`` / ``duration_p90_h`` from the **real** operation
history — never from standard coefficients (CLAUDE.md §1.7: NELO
standards diverge from reality by up to 25×).

Cleaning recipe (project invariant — CLAUDE.md):

    duration = OFFP_DATAFIM − OFFP_DATAINICIO
    → remove zeros
    → remove values above P95
    → p50 = mode of the cleaned sample (fallback: median of non-zero)
    → p90 = 90th percentile of the cleaned sample

Operations are bucketed by (routing template, phase): a product's
``ModelRoutingAssignment`` maps it to its template, so every product
sharing a pattern pools its history into the same estimate.

Heavy table — ``OF_FP`` has 2.6 M rows. The window is paged month by
month so each adapter call stays well under the row cap. This mirror is
excluded from the nightly ``nelo_erp_sync`` and run on its own cadence.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from statistics import median, multimode
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, update

from src.adapters.nelo import services
from src.adapters.nelo.schemas import OperationRow
from src.plan.models.routing_template import ModelRoutingAssignment, RoutingTemplatePhase

from .runner import EtlRunner, EtlRunResult
from .sync import register_mirror

logger = logging.getLogger(__name__)

# Default look-back when no ``since`` is given — 3 years of history is a
# large, statistically solid sample without scanning all 18 years.
_DEFAULT_LOOKBACK_DAYS = 365 * 3


# ─── pure mining ────────────────────────────────────────────────────


def _percentile(sorted_vals: List[float], pct: float) -> float:
    """Linear-interpolation percentile of an already-sorted list."""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * (pct / 100.0)
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return sorted_vals[int(k)]
    return sorted_vals[lo] * (hi - k) + sorted_vals[hi] * (k - lo)


def _mode_or_median(values: List[float]) -> float:
    """Canonical duration: mode of the (rounded) sample, falling back to
    the median of the non-zero values when the mode is 0 or undefined.
    """
    if not values:
        return 0.0
    rounded = [round(v, 2) for v in values]
    modes = multimode(rounded)
    candidate = modes[0] if modes else 0.0
    if candidate and candidate > 0:
        return float(candidate)
    nonzero = [v for v in values if v > 0]
    return float(median(nonzero)) if nonzero else 0.0


def mine_durations(raw: List[float]) -> Optional[Tuple[float, float]]:
    """Return ``(p50_hours, p90_hours)`` from a raw duration sample.

    Returns ``None`` when there is no usable (non-zero) data — the caller
    then leaves the phase's durations untouched rather than writing junk.
    """
    nonzero = sorted(d for d in raw if d and d > 0)
    if not nonzero:
        return None
    p95 = _percentile(nonzero, 95)
    cleaned = sorted(d for d in nonzero if d <= p95) or nonzero
    p50 = _mode_or_median(cleaned)
    p90 = _percentile(cleaned, 90)
    if p50 <= 0:
        return None
    return (p50, max(p90, p50))


def operation_duration_h(op: OperationRow) -> Optional[float]:
    """Real span of one operation, in hours, from the ERP timestamps.

    Standard coefficients are deliberately NOT consulted — only
    ``OFFP_DATAINICIO`` / ``OFFP_DATAFIM`` (``start_at`` / ``end_at``).
    Returns ``None`` for a missing or non-positive span.
    """
    if op.start_at is None or op.end_at is None:
        return None
    span_h = (op.end_at - op.start_at).total_seconds() / 3600.0
    return span_h if span_h > 0 else None


# ─── date-window paging ─────────────────────────────────────────────


def _month_windows(date_from: date, date_to: date) -> List[Tuple[date, date]]:
    """Split ``[date_from, date_to]`` into month-ish windows so each
    adapter call stays well under the OF_FP row cap."""
    windows: List[Tuple[date, date]] = []
    cursor = date_from
    while cursor <= date_to:
        nxt = cursor + timedelta(days=30)
        windows.append((cursor, min(nxt - timedelta(days=1), date_to)))
        cursor = nxt
    return windows


# ─── mirror entry point ─────────────────────────────────────────────


async def mirror_time_mining(
    *,
    session,
    tenant_id: UUID,
    since: Optional[date] = None,
) -> EtlRunResult:
    """Mine real durations and write p50/p90 into routing_template_phase."""
    async with EtlRunner(session, tenant_id, source="time_mining") as run:
        tpl_by_product = await _template_by_product(session, tenant_id)
        if not tpl_by_product:
            logger.warning(
                "time_mining — no routing templates; run the master mirror "
                "(Q.20.B) first. Nothing to mine into."
            )
            return run.result

        date_from = since or (date.today() - timedelta(days=_DEFAULT_LOOKBACK_DAYS))
        date_to = date.today()

        samples: Dict[Tuple[UUID, str], List[float]] = defaultdict(list)
        skipped = 0
        for win_from, win_to in _month_windows(date_from, date_to):
            ops = await services.list_operations(date_from=win_from, date_to=win_to)
            run.count_read(len(ops))
            for op in ops:
                dur = operation_duration_h(op)
                template_id = tpl_by_product.get(str(op.product_id))
                phase_key = str(op.phase_id)
                if dur is None or template_id is None:
                    skipped += 1
                    continue
                samples[(template_id, phase_key)].append(dur)
        run.count_skipped(skipped)

        updated = await _write_durations(session, samples)
        run.result.rows_updated += updated
        logger.info(
            "time_mining — window=%s..%s buckets=%d phases_updated=%d",
            date_from, date_to, len(samples), updated,
        )
    return run.result


async def _template_by_product(session, tenant_id: UUID) -> Dict[str, UUID]:
    """Map ERP product id → its primary routing template UUID."""
    rows = await session.execute(
        select(
            ModelRoutingAssignment.model_id,
            ModelRoutingAssignment.primary_template_id,
        ).where(ModelRoutingAssignment.tenant_id == tenant_id)
    )
    return {str(model_id): tpl for model_id, tpl in rows}


async def _write_durations(
    session, samples: Dict[Tuple[UUID, str], List[float]],
) -> int:
    """Write mined p50/p90 onto matching ``routing_template_phase`` rows.

    A bucket with no usable data is skipped (durations stay NULL — junk
    is worse than a missing estimate). Returns the rows updated.
    """
    updated = 0
    for (template_id, phase_key), durations in samples.items():
        mined = mine_durations(durations)
        if mined is None:
            continue
        p50, p90 = mined
        result = await session.execute(
            update(RoutingTemplatePhase)
            .where(
                RoutingTemplatePhase.template_id == template_id,
                RoutingTemplatePhase.phase_id == phase_key,
            )
            .values(
                duration_p50_h=Decimal(str(round(p50, 4))),
                duration_p90_h=Decimal(str(round(p90, 4))),
            )
        )
        updated += result.rowcount or 0
    return updated


register_mirror("time_mining", mirror_time_mining)
