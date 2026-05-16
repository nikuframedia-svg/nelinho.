"""Q.20.C — molds mirror (ERP MOLDES → plan.mold).

The ERP knows only ~91 molds; the full ~510 production molds live in an
Excel workbook (``Folha_IA_extra.xlsx``) and reach ``plan.mold`` through
the ``factory_data_product`` curated ingest — a separate path. This
mirror covers the **ERP-side** catalogue (``MOLDES``):

* ``list_molds()`` → ``plan.mold``

``MOLDES`` carries no maintenance columns and no product linkage, so:

* ``model_id`` is left empty (``""``) — the ERP mold record does not say
  which model it produces; the curated/Excel side fills that.
* ``pocket_count`` defaults to 1 — ``MOLDES`` has no pocket column.
* ``mold_type`` is derived from ``MLD_MLDTP_ID`` as ``tipo-<id>``.
* ``acquired_date`` comes from ``MLD_DATA``.

Idempotent: upsert by ``mold_code`` (the ERP ``MLD_ID``). Re-running
never duplicates and never resets pocket/model data that a later curated
sync may have enriched (those columns are excluded from ``update_fields``).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, Optional
from uuid import UUID

from src.adapters.nelo import services
from src.adapters.nelo.schemas import MoldRow
from src.plan.models.mold import Mold

from .runner import EtlRunner, EtlRunResult
from .sync import register_mirror

logger = logging.getLogger(__name__)


def _map_mold(row: MoldRow) -> Optional[Dict[str, Any]]:
    """ERP ``MOLDES`` row → ``plan.mold`` column dict.

    ``mold_code`` carries the ERP ``MLD_ID`` (stable business key).
    ``model_id`` is the empty-string sentinel — the ERP record has no
    product linkage; the curated/Excel mold sync fills it. It is passed
    as an *insert-only* field so a re-run never reverts a model_id the
    curated sync may have set on the existing row.
    """
    if row.mold_id in (None, ""):
        return None
    acquired: Optional[date] = (
        row.acquired_at.date() if row.acquired_at is not None else None
    )
    return {
        "mold_code": str(row.mold_id),
        "name": str(row.mold_name or row.mold_id),
        "mold_type": f"tipo-{row.mold_type_id}" if row.mold_type_id is not None else None,
        "acquired_date": acquired,
        "active": True,
        "model_id": "",  # insert-only sentinel — NOT NULL column
    }


async def mirror_molds(
    *,
    session,
    tenant_id: UUID,
    since: Optional[date] = None,
) -> EtlRunResult:
    """Mirror the ERP-side mold catalogue into ``plan.mold``."""
    async with EtlRunner(session, tenant_id, source="molds") as run:
        rows = await services.list_molds()
        run.count_read(len(rows))
        mapped = [m for m in (_map_mold(r) for r in rows) if m is not None]
        run.count_skipped(len(rows) - len(mapped))
        # `model_id` is insert-only — owned by the curated/Excel mold sync
        # once the row exists; `pocket_count` keeps its DB default (1) and
        # is likewise never touched here.
        await run.upsert(
            Mold, mapped,
            key_fields=["mold_code"],
            update_fields=["name", "mold_type", "acquired_date", "active"],
            insert_only_fields=["model_id"],
        )
        logger.info("molds mirror — %d ERP mold(s) processed", len(mapped))
    return run.result


register_mirror("molds", mirror_molds)
