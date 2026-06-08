"""Q.20.E — quality mirror (ERP OF_FP → quality.error_catalog).

NELO records quality **inline** on the operation row: ``OF_FP`` carries
``OFFP_RETURN`` (the rework bit), ``OFFP_RETORNO_GRAVE`` (severe rework)
and a set of ``OFFP_PROBS_*`` problem-category columns. The child
``OFFP_PROBLEMA`` table is empty in MAR-KAYAKS — these columns are the
live data. The adapter surfaces all of them on :class:`OperationRow`.

This mirror imports, over a bounded ``[since, today]`` window, the
**distinct problem categories → ``quality.error_catalog``** (the error
vocabulary consumed by the copilot ontology, rework/roi services, search).

**Q.167.E — já NÃO escreve ``quality.rework_entry``.** A fonte canónica de
defeitos passou a ser ``OF_CHECKLIST`` (mirror :mod:`.checklist`), que separa
quem **causou** de quem **detectou** (RCA real, 78,5 % das linhas divergem).
Os dois escreviam ``rework_entry`` com namespaces ``uuid5`` distintos → cada
defeito contava 2×. Só o checklist escreve agora; o catálogo (vocabulário,
não-rework) continua aqui.

Heavy table — ``OF_FP`` has 2.6 M rows; always pass ``since`` to bound
the window. The mirror runs incrementally.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from src.adapters.nelo import services
from src.adapters.nelo.schemas import OperationRow
from src.quality.models.rework import ErrorCatalog

from .runner import EtlRunner, EtlRunResult
from .sync import register_mirror

logger = logging.getLogger(__name__)

# Default look-back when the caller passes no ``since`` — one year of
# operations, enough for the quality dashboards without scanning 18 years.
_DEFAULT_LOOKBACK_DAYS = 365


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


async def mirror_quality(
    *,
    session,
    tenant_id: UUID,
    since: Optional[date] = None,
) -> EtlRunResult:
    """Mirror quality incidents into the error catalogue + rework log."""
    async with EtlRunner(session, tenant_id, source="quality") as run:
        date_from = since or (date.today() - timedelta(days=_DEFAULT_LOOKBACK_DAYS))
        date_to = date.today()
        ops = await services.list_operations(date_from=date_from, date_to=date_to)
        run.count_read(len(ops))

        incidents = [op for op in ops if _is_incident(op)]
        run.count_skipped(len(ops) - len(incidents))

        # Error catalogue — distinct problem vocabulary. Q.167.E: o rework_entry
        # foi removido (o checklist é a fonte única); só o catálogo fica.
        catalog = build_catalog(incidents)
        await run.upsert(
            ErrorCatalog, catalog,
            key_fields=["error_code"],
            update_fields=["name", "severity_hint", "typical_phase", "mold_related"],
        )
        logger.info(
            "quality mirror — window=%s..%s incidents=%d catalogue=%d",
            date_from, date_to, len(incidents), len(catalog),
        )
    return run.result


register_mirror("quality", mirror_quality)
