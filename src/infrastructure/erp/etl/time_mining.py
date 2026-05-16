"""Q.20.F — historical time mining (vw_pp1_of_fp → routing_template_phase).

The routing templates built by Q.20.B carry NULL durations. This mirror
fills ``duration_p50_h`` / ``duration_p90_h`` from the **real** operation
history — never from standard coefficients (NELO standards diverge from
reality by up to 25×).

Cleaning recipe (project invariant — ``CLAUDE.md``):

    duration = fase_of_fim − fase_of_inicio
    → remove zeros
    → remove values above P95
    → p50 = mode of the cleaned sample (fallback: median of non-zero)
    → p90 = 90th percentile of the cleaned sample

Operations are bucketed by (routing template, phase): a product's
``ModelRoutingAssignment`` maps it to its template, so every product
sharing a pattern pools its history into the same estimate.

This is the heavy mirror — it runs weekly (job ``nelo_time_mining``),
not in the nightly ``nelo_erp_sync``.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from statistics import median, multimode
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, update

from src.plan.models.routing_template import ModelRoutingAssignment, RoutingTemplatePhase

from .runner import EtlRunner, EtlRunResult
from .sync import register_mirror

logger = logging.getLogger(__name__)

# Cap the paging loop so a pathological ERP response can't spin forever.
_BATCH = 100_000
_MAX_BATCHES = 60


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


def _duration_hours(op: Dict[str, Any]) -> Optional[float]:
    """Real span of one operation, from the ERP start/end timestamps.

    Standard coefficients are deliberately NOT consulted — only
    ``fase_of_inicio``/``fase_of_fim``.
    """
    inicio = op.get("fase_of_inicio")
    fim = op.get("fase_of_fim")
    if not isinstance(inicio, datetime) or not isinstance(fim, datetime):
        return None
    span_h = (fim - inicio).total_seconds() / 3600.0
    return span_h if span_h > 0 else None


# ─── mirror entry point ─────────────────────────────────────────────


async def mirror_time_mining(
    *,
    session,
    tenant_id: UUID,
    adapter,
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

        samples: Dict[Tuple[UUID, str], List[float]] = defaultdict(list)
        skipped = await _collect_samples(
            adapter, since, tpl_by_product, samples, run,
        )
        run.count_skipped(skipped)

        updated = 0
        for (template_id, fase_id), durations in samples.items():
            mined = mine_durations(durations)
            if mined is None:
                continue
            p50, p90 = mined
            result = await session.execute(
                update(RoutingTemplatePhase)
                .where(
                    RoutingTemplatePhase.template_id == template_id,
                    RoutingTemplatePhase.phase_id == fase_id,
                )
                .values(
                    duration_p50_h=Decimal(str(round(p50, 4))),
                    duration_p90_h=Decimal(str(round(p90, 4))),
                )
            )
            updated += result.rowcount or 0
        run.result.rows_updated += updated
        logger.info(
            "time_mining — buckets=%d phases_updated=%d", len(samples), updated,
        )
    return run.result


async def _template_by_product(session, tenant_id: UUID) -> Dict[str, UUID]:
    rows = await session.execute(
        select(
            ModelRoutingAssignment.model_id,
            ModelRoutingAssignment.primary_template_id,
        ).where(ModelRoutingAssignment.tenant_id == tenant_id)
    )
    return {str(model_id): tpl for model_id, tpl in rows}


async def _collect_samples(
    adapter,
    since: Optional[date],
    tpl_by_product: Dict[str, UUID],
    samples: Dict[Tuple[UUID, str], List[float]],
    run: EtlRunner,
) -> int:
    """Page through ``vw_pp1_of_fp`` accumulating durations per
    (template, phase). Returns the count of skipped operations."""
    skipped = 0
    cursor = since
    for _ in range(_MAX_BATCHES):
        ops = await adapter.fetch_operations(since=cursor, limit=_BATCH)
        if not ops:
            break
        run.count_read(len(ops))
        max_inicio: Optional[datetime] = None
        for op in ops:
            inicio = op.get("fase_of_inicio")
            if isinstance(inicio, datetime) and (
                max_inicio is None or inicio > max_inicio
            ):
                max_inicio = inicio
            dur = _duration_hours(op)
            template_id = tpl_by_product.get(str(op.get("produto_id")))
            fase_id = str(op.get("fase_id") or "")
            if dur is None or template_id is None or not fase_id:
                skipped += 1
                continue
            samples[(template_id, fase_id)].append(dur)
        if len(ops) < _BATCH or max_inicio is None:
            break
        # Advance the cursor past this batch. Boundary rows sharing the
        # exact timestamp may re-appear — harmless for percentile stats.
        cursor = max_inicio.date()
    return skipped


register_mirror("time_mining", mirror_time_mining)
