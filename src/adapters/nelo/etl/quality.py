"""Q.20.E — quality mirror (ERP OF_FP → quality.error_catalog + rework_entry).

NELO records quality **inline** on the operation row: ``OF_FP`` carries
``OFFP_RETURN`` (the rework bit), ``OFFP_RETORNO_GRAVE`` (severe rework)
and a set of ``OFFP_PROBS_*`` problem-category columns. The child
``OFFP_PROBLEMA`` table is empty in MAR-KAYAKS — these columns are the
live data. The adapter surfaces all of them on :class:`OperationRow`.

This mirror imports, over a bounded ``[since, today]`` window:

* distinct problem categories → ``quality.error_catalog`` (the vocabulary)
* every operation flagged as rework / carrying a problem
  → ``quality.rework_entry`` (one row per incident)

Each rework row's ``id`` is a deterministic ``uuid5`` of the ERP
operation id, so re-importing an overlapping window upserts instead of
duplicating. ``severity_hint`` is ``high`` for a severe return
(``OFFP_RETORNO_GRAVE``), else ``medium``.

Heavy table — ``OF_FP`` has 2.6 M rows; always pass ``since`` to bound
the window. The mirror runs incrementally.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timezone, timedelta
from typing import Any, Dict, List, Optional
from uuid import NAMESPACE_DNS, UUID, uuid5

from src.adapters.nelo import services
from src.adapters.nelo.schemas import OperationRow
from src.quality.models.rework import ErrorCatalog, ReworkEntry

from .runner import EtlRunner, EtlRunResult
from .sync import register_mirror

logger = logging.getLogger(__name__)

# Default look-back when the caller passes no ``since`` — one year of
# operations, enough for the quality dashboards without scanning 18 years.
_DEFAULT_LOOKBACK_DAYS = 365


def _as_utc(value: Any) -> Optional[datetime]:
    """Coerce an ERP timestamp to a tz-aware (UTC) datetime —
    ``rework_entry.detected_at`` is ``timestamptz``."""
    dt: Optional[datetime] = None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime.combine(value, time.min)
    if dt is not None and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _problem_codes(op: OperationRow) -> List[tuple[str, str]]:
    """The (error_code, name) pairs an operation contributes.

    The ``OFFP_PROBS_*`` columns are numeric category ids (interior /
    paint / mold / lamination) plus a free-text neck field. Each present
    value becomes one catalogue code with a stable prefix.
    """
    pairs: List[tuple[str, str]] = []
    if op.problem_interior_id:
        pairs.append((f"INT-{op.problem_interior_id}", f"Problema interior {op.problem_interior_id}"))
    if op.problem_paint_id:
        pairs.append((f"PAINT-{op.problem_paint_id}", f"Problema pintura {op.problem_paint_id}"))
    if op.problem_mold_id:
        pairs.append((f"MOLD-{op.problem_mold_id}", f"Problema molde {op.problem_mold_id}"))
    if op.problem_lamination_id:
        pairs.append((f"LAM-{op.problem_lamination_id}", f"Problema laminagem {op.problem_lamination_id}"))
    if op.problem_neck and str(op.problem_neck).strip():
        pairs.append(("NECK", "Problema de gola"))
    return pairs


def _is_incident(op: OperationRow) -> bool:
    """An operation is a quality incident if it was a rework
    (``OFFP_RETURN``) or carries any problem-category value."""
    return bool(op.is_return) or bool(_problem_codes(op))


def build_catalog(ops: List[OperationRow]) -> List[Dict[str, Any]]:
    """Distinct error vocabulary across the operations window.

    A severe return anywhere lifts a code's ``severity_hint`` to ``high``.
    A mold-category code is flagged ``mold_related``.
    """
    seen: Dict[str, Dict[str, Any]] = {}
    for op in ops:
        for code, name in _problem_codes(op):
            entry = seen.get(code)
            severe = bool(op.severe_return)
            if entry is None:
                seen[code] = {
                    "error_code": code,
                    "name": name[:255],
                    "severity_hint": "high" if severe else "medium",
                    "typical_phase": str(op.phase_id),
                    "mold_related": code.startswith("MOLD-"),
                }
            elif severe:
                entry["severity_hint"] = "high"
    return list(seen.values())


def build_rework(ops: List[OperationRow]) -> List[Dict[str, Any]]:
    """One ``rework_entry`` row per quality incident.

    ``id`` is ``uuid5`` of the ERP operation id so a re-imported window
    upserts rather than duplicates. ``error_code`` is the first problem
    category; a plain rework with no categorised problem uses ``RETURN``.
    """
    rows: List[Dict[str, Any]] = []
    for op in ops:
        if not _is_incident(op):
            continue
        detected = _as_utc(op.problem_logged_at) or _as_utc(op.end_at) or _as_utc(op.start_at)
        if detected is None:
            continue
        codes = _problem_codes(op)
        error_code = codes[0][0] if codes else "RETURN"
        error_desc = codes[0][1] if codes else "Retrabalho sem problema categorizado"
        rows.append({
            "id": uuid5(NAMESPACE_DNS, f"nelo-erp-offp-{op.operation_id}"),
            "of_id": str(op.work_order_id),
            "model_id": str(op.product_id) if op.product_id else None,
            "phase_id_causer": str(op.phase_id),
            "phase_id_rework": str(op.phase_id),
            "error_code": error_code,
            "error_description": error_desc,
            "detected_at": detected,
            "context": {
                "erp_offp_id": str(op.operation_id),
                "is_return": bool(op.is_return),
                "severe_return": bool(op.severe_return),
                "phase_name": op.phase_name,
                "source": "erp_of_fp",
            },
        })
    return rows


async def mirror_quality(
    *,
    session,
    tenant_id: UUID,
    since: Optional[date] = None,
    source=services,
) -> EtlRunResult:
    """Mirror quality incidents into the error catalogue + rework log."""
    async with EtlRunner(session, tenant_id, source="quality") as run:
        date_from = since or (date.today() - timedelta(days=_DEFAULT_LOOKBACK_DAYS))
        date_to = date.today()
        ops = await source.list_operations(date_from=date_from, date_to=date_to)
        run.count_read(len(ops))

        incidents = [op for op in ops if _is_incident(op)]
        run.count_skipped(len(ops) - len(incidents))

        # 1. Error catalogue — distinct problem vocabulary.
        catalog = build_catalog(incidents)
        await run.upsert(
            ErrorCatalog, catalog,
            key_fields=["error_code"],
            update_fields=["name", "severity_hint", "typical_phase", "mold_related"],
        )

        # 2. Rework entries — one deterministically-keyed row per incident.
        rework = build_rework(incidents)
        await run.upsert(
            ReworkEntry, rework,
            key_fields=["id"],
            update_fields=[
                "of_id", "model_id", "phase_id_causer", "phase_id_rework",
                "error_code", "error_description", "detected_at", "context",
            ],
        )
        logger.info(
            "quality mirror — window=%s..%s incidents=%d catalogue=%d",
            date_from, date_to, len(incidents), len(catalog),
        )
    return run.result


register_mirror("quality", mirror_quality)
