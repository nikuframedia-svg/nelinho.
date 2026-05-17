"""OEE (Overall Equipment Effectiveness) service.

Computes the three OEE components from NELO operations data:

    OEE = Availability × Performance × Quality

Source: `src.adapters.nelo.services.list_operations` returns one row per
executed phase (`OF_FP`). Each row has:
- start_at / end_at  → actual duration
- standard_time_hours → routing standard (PRODF_TEMPO with K1 fallback)
- temperature / humidity → cura/secagem environment
- problem_* / is_return / severe_return → quality flags

Component definitions
---------------------
- **Availability** = SUM(actual hours) / SUM(planned hours)
  Planned hours = `working_days_in_period × 8h × shift_factor`.
  We use a fixed 8h day Monday-Friday for the MVP — refine to read
  TURNO + DIAS_TRABALHO in a follow-up.
- **Performance** = SUM(standard_time) / SUM(actual_time), capped at 1.0.
  Operations with `standard_time = 0` (routing not declared) are excluded
  from the Performance calc but counted in Availability.
- **Quality** = COUNT(passes_first_time) / COUNT(total operations)
  passes_first_time iff `is_return=False AND severe_return=False
  AND problem_logged_at IS NULL`.

Outlier filter: operations where `actual_time > OUTLIER_MULTIPLIER ×
standard_time` are excluded from Performance (probable forgotten close).

Grouping: pass `group_by` to slice by phase / shift / product_type /
mold. Operator grouping requires joining OFFP_EQ — deferred to A.6.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Callable, Iterable, Literal

from src.adapters.nelo.schemas import OperationRow
from src.adapters.nelo.services import list_operations

log = logging.getLogger(__name__)

GroupBy = Literal["none", "phase", "shift", "product_type", "mold"]
OUTLIER_MULTIPLIER = 10.0
DEFAULT_SHIFT_HOURS = 8.0


# ─── Dataclasses (Pydantic-free for service layer) ──────────────────────


@dataclass(frozen=True)
class OEEBreakdownItem:
    group_value: str | None  # e.g. "Laminagem" when group_by=phase; None for overall
    availability: float  # 0-1
    performance: float  # 0-1
    quality: float  # 0-1
    oee: float  # 0-1
    sample_size: int  # ops counted in Quality / Availability
    sample_excluded: int  # ops dropped as outliers from Performance


@dataclass(frozen=True)
class OEEResult:
    date_from: date
    date_to: date
    group_by: str
    overall: OEEBreakdownItem
    breakdown: list[OEEBreakdownItem]


# ─── Helpers ─────────────────────────────────────────────────────────────


def _actual_hours(op: OperationRow) -> float | None:
    """Duration of an operation in hours, or None if missing endpoints."""
    if op.start_at is None or op.end_at is None:
        return None
    delta = op.end_at - op.start_at
    h = delta.total_seconds() / 3600.0
    return h if h > 0 else None


def _passes_first_time(op: OperationRow) -> bool:
    return (
        not op.is_return
        and not op.severe_return
        and op.problem_logged_at is None
        and op.problem_interior_id is None
        and op.problem_paint_id is None
        and op.problem_mold_id is None
        and op.problem_lamination_id is None
    )


def _working_hours_in_period(date_from: date, date_to: date) -> float:
    """Mon-Fri × 8h, inclusive of both endpoints. MVP heuristic."""
    days = 0
    d = date_from
    while d <= date_to:
        if d.weekday() < 5:  # 0-4 = Mon-Fri
            days += 1
        d += timedelta(days=1)
    return days * DEFAULT_SHIFT_HOURS


def _group_key(op: OperationRow, group_by: GroupBy) -> str | None:
    if group_by == "none":
        return None
    if group_by == "phase":
        return op.phase_name
    if group_by == "shift":
        return str(op.shift_id) if op.shift_id is not None else "—"
    if group_by == "product_type":
        return op.product_type_name or "Other"
    if group_by == "mold":
        return str(op.mold_work_order_id) if op.mold_work_order_id else "—"
    raise ValueError(f"Unknown group_by: {group_by}")


# ─── Core component calculators ─────────────────────────────────────────


def _compute_components(
    ops: Iterable[OperationRow],
    planned_hours: float,
) -> tuple[float, float, float, int, int]:
    """Return (availability, performance, quality, sample_size, excluded).

    Availability is capped at 1.0 because the planned-hours denominator
    assumes 1 worker × shift hours. NELO has ~100 operators working in
    parallel — a proper calculation would scale by headcount derived
    from `OFFP_EQ`. For MVP we cap and note in the docstring.

    Performance defaults to 1.0 when no operation has a declared
    standard time (PRODF_TEMPO = 0). This avoids the "OEE = 0" trap
    for phases whose routing is undeclared in MAR-KAYAKS.
    """
    total_actual = 0.0
    perf_actual = 0.0
    perf_standard = 0.0
    excluded = 0
    quality_total = 0
    quality_passes = 0

    for op in ops:
        actual = _actual_hours(op)
        if actual is None:
            continue
        total_actual += actual
        quality_total += 1
        if _passes_first_time(op):
            quality_passes += 1

        # Performance only counts operations with declared standard.
        # Automatic phases (cura/secagem) have no operator labour — skip.
        if op.phase_is_automatic:
            continue
        if op.standard_time_hours <= 0:
            continue
        # Outlier filter
        if actual > OUTLIER_MULTIPLIER * op.standard_time_hours:
            excluded += 1
            continue
        perf_actual += actual
        perf_standard += op.standard_time_hours

    # Availability: clamp to [0, 1]. The denominator assumes a single-
    # worker shift; real factory parallelism makes ratios > 1 common.
    availability_raw = (total_actual / planned_hours) if planned_hours > 0 else 0.0
    availability = min(availability_raw, 1.0)

    # Performance: undeclared routing (PRODF_TEMPO=0) means we have no
    # baseline — default to 1.0 so OEE doesn't collapse to 0 for
    # under-instrumented phases. Real factories must declare standards
    # to get a meaningful number here.
    performance = (perf_standard / perf_actual) if perf_actual > 0 else 1.0
    performance = min(performance, 1.0)  # cap

    quality = (quality_passes / quality_total) if quality_total > 0 else 0.0

    return availability, performance, quality, quality_total, excluded


# ─── Public service ─────────────────────────────────────────────────────


class OEEService:
    """Stateless service. Pass in a fetcher (defaults to NELO adapter)."""

    def __init__(
        self,
        fetcher: Callable[[date, date, int], Any] | None = None,
        max_operations: int = 100_000,
    ) -> None:
        self._fetcher = fetcher or list_operations
        self._max_operations = max_operations

    async def calculate(
        self,
        date_from: date,
        date_to: date,
        group_by: GroupBy = "none",
    ) -> OEEResult:
        if date_from > date_to:
            raise ValueError("date_from must be <= date_to")

        ops = await self._fetcher(date_from, date_to, self._max_operations)
        planned = _working_hours_in_period(date_from, date_to)

        # Overall
        av, pf, ql, n, exc = _compute_components(ops, planned)
        overall = OEEBreakdownItem(
            group_value=None,
            availability=av,
            performance=pf,
            quality=ql,
            oee=av * pf * ql,
            sample_size=n,
            sample_excluded=exc,
        )

        if group_by == "none":
            return OEEResult(date_from, date_to, group_by, overall, breakdown=[])

        # Grouped — each group gets a proportional slice of planned hours
        groups: dict[str, list[OperationRow]] = defaultdict(list)
        for op in ops:
            key = _group_key(op, group_by)
            if key is not None:
                groups[key].append(op)

        breakdown: list[OEEBreakdownItem] = []
        total_actual = sum(_actual_hours(op) or 0 for op in ops)
        for key, group_ops in groups.items():
            # Per-group planned hours proportional to group's share of total
            # actual hours vs the full sample's actual hours. Avoids assuming
            # every group has access to full shift.
            group_actual = sum(_actual_hours(op) or 0 for op in group_ops)
            group_planned = (
                planned * (group_actual / total_actual)
                if total_actual > 0
                else 0.0
            )
            av, pf, ql, n, exc = _compute_components(group_ops, group_planned)
            # Skip groups where no operation contributed (n=0) — these
            # come from ops with broken start/end timestamps.
            if n == 0:
                continue
            breakdown.append(
                OEEBreakdownItem(
                    group_value=key,
                    availability=av,
                    performance=pf,
                    quality=ql,
                    oee=av * pf * ql,
                    sample_size=n,
                    sample_excluded=exc,
                )
            )

        # Sort: smaller OEE first if grouping by phase/mold (focus on
        # problem areas); alphabetical for product_type/shift.
        if group_by in ("phase", "mold"):
            breakdown.sort(key=lambda b: b.oee)
        else:
            breakdown.sort(key=lambda b: b.group_value or "")

        return OEEResult(date_from, date_to, group_by, overall, breakdown)
