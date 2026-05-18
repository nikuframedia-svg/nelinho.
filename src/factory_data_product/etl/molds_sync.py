"""Q.38.B — Excel mold sync (`Folha_IA_extra.xlsx` → `plan.mold`).

The ERP mirror (`src/adapters/nelo/etl/molds.py`) brings only the ~91
molds the SQL Server `MOLDES` table knows. The full ~510 production
molds live in the `Moldes` sheet of `Folha_IA_extra.xlsx`. This module
completes the **Excel → curated → `plan.mold`** path:

* :func:`parse_excel_molds` — read the `Moldes` sheet via the shared
  :class:`ExcelParser`, returning RAW row dicts;
* the curated step reuses :meth:`RawToCuratedTransformer._transform_molds`
  — the same transform the in-memory ingest engine runs, so the curated
  representation is identical;
* :func:`curated_mold_to_plan_row` — pure mapper, curated dict →
  `plan.mold` column dict;
* :func:`sync_molds_from_excel` — orchestrates: parse → transform →
  idempotent upsert into `plan.mold` via :class:`EtlRunner`.

Idempotent: upsert by `mold_code` (the Excel `MoldeId`). The Excel
`MoldeId` space (~70000+) is disjoint from the ERP `MLD_ID` space
(1..91), so the Excel sync and the ERP `molds` mirror write distinct
rows and never collide.

`model_id` is passed insert-only — the Excel sheet *does* carry a
`MoldeModeloId`, but it must not overwrite a value the ERP mirror or a
later enrichment owns once the row exists. `pocket_count` keeps the DB
default (1): the Excel `MoldeNumeroPocosId` is a poço-type *id*, not a
confirmed count, so no count is invented (same conservative stance as
the ERP mirror).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from src.adapters.nelo.etl.runner import EtlRunner, EtlRunResult
from src.factory_data_product.ingest.parser import ExcelParser
from src.factory_data_product.ingest.transformer import RawToCuratedTransformer
from src.plan.models.mold import Mold

logger = logging.getLogger(__name__)

_MOLDS_SHEET = "Moldes"


def parse_excel_molds(file_path: Path) -> List[Dict[str, Any]]:
    """Read the `Moldes` sheet of an Excel workbook into RAW row dicts.

    Each dict has the ``{"sheet_name", "payload_json"}`` shape the
    transformer expects. Returns an empty list when the workbook has no
    `Moldes` sheet (so a caller can report the gap rather than crash).
    """
    parser = ExcelParser()
    parsed = parser.parse(Path(file_path))
    sheet = parsed.sheets.get(_MOLDS_SHEET)
    if sheet is None:
        logger.warning(
            "molds_sync — workbook %s has no '%s' sheet", file_path, _MOLDS_SHEET,
        )
        return []
    return [
        {"sheet_name": _MOLDS_SHEET, "payload_json": row}
        for row in sheet.rows
    ]


def curated_mold_to_plan_row(curated: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Curated mold dict (from ``_transform_molds``) → ``plan.mold`` columns.

    ``mold_code`` carries the Excel ``MoldeId`` — the stable business
    key. Rows without a ``molde_id`` are dropped (the column is NOT
    NULL). ``model_id`` is the curated ``modelo_id`` (or the empty-string
    sentinel) and is applied insert-only by the caller.
    """
    molde_id = curated.get("molde_id")
    if molde_id in (None, ""):
        return None
    return {
        "mold_code": str(molde_id),
        "name": curated.get("molde_nome") or str(molde_id),
        "mold_type": curated.get("tipo"),
        "active": not bool(curated.get("em_manutencao", False)),
        "model_id": str(curated.get("modelo_id") or ""),
    }


def excel_rows_to_plan_molds(
    raw_rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """RAW `Moldes` rows → ``plan.mold`` column dicts (pure).

    Runs the curated transform (``_transform_molds``) then maps each
    curated row to a ``plan.mold`` row, dropping rows with no business
    key.
    """
    transformer = RawToCuratedTransformer()
    # `_transform_molds` writes onto a TransformResult; the ingestion_id
    # is irrelevant for this path (curated rows are not persisted — they
    # are an intermediate representation), so a fresh UUID is fine.
    result = transformer.transform(raw_rows, uuid4())
    mapped = [
        m for m in (curated_mold_to_plan_row(c) for c in result.molds)
        if m is not None
    ]
    return mapped


async def sync_molds_from_excel(
    *,
    session,
    tenant_id: UUID,
    file_path: Path,
) -> EtlRunResult:
    """Sync the ~510 Excel molds into ``plan.mold``.

    Parses the `Moldes` sheet, runs the curated transform, and upserts
    by ``mold_code`` through :class:`EtlRunner` (idempotent + audit row
    in ``core.etl_run``). The caller commits the session.

    ``model_id`` is insert-only — never overwritten on a re-run, so an
    ERP-side enrichment of the same row survives. ``pocket_count`` is
    never touched (DB default 1).
    """
    raw_rows = parse_excel_molds(file_path)

    async with EtlRunner(session, tenant_id, source="molds_excel") as run:
        run.count_read(len(raw_rows))
        mapped = excel_rows_to_plan_molds(raw_rows)
        run.count_skipped(len(raw_rows) - len(mapped))
        await run.upsert(
            Mold, mapped,
            key_fields=["mold_code"],
            update_fields=["name", "mold_type", "active"],
            insert_only_fields=["model_id"],
        )
        logger.info(
            "molds_sync — %d Excel mold(s) processed from %s",
            len(mapped), file_path,
        )
    return run.result


__all__ = [
    "curated_mold_to_plan_row",
    "excel_rows_to_plan_molds",
    "parse_excel_molds",
    "sync_molds_from_excel",
]
