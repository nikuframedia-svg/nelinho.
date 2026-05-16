"""Q.20.C — molds mirror (factory_curated.mold → plan.mold).

The 510 production molds live in the ``Folha_IA_extra.xlsx`` workbook;
the ERP only knows ~91 of them. So the source of truth here is the
``factory_data_product`` curated layer (fed by the Excel ingest CLI),
not the ERP.

This mirror bridges the **active** curated ingestion's ``CuratedMold``
rows into ``plan.mold`` — the operational table the CPO scheduler and
the mold-health jobs read. It then reconciles the ERP-side catalogue
(``vw_pp1_moldes``) against ``plan.mold`` via ``compare_shadow`` and
logs the divergence (≈419 Excel-only molds is expected, not an error).

Prerequisite: run the Excel ingest first ::

    python -m src.factory_data_product.cli.commands ingest Folha_IA_extra.xlsx
    python -m src.factory_data_product.cli.commands activate <ingestion_id>
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select

from src.factory_data_product.models.curated import CuratedMold
from src.factory_data_product.models.meta import ActiveRun
from src.infrastructure.erp.sqlserver import compare_shadow
from src.plan.models.mold import Mold

from .runner import EtlRunner, EtlRunResult
from .sync import register_mirror

logger = logging.getLogger(__name__)

# Curated `estado` values that mean the mold is no longer in service.
_RETIRED_ESTADOS = {"inactivo", "inativo", "retirado", "abatido", "sucata"}


def _is_active(estado: Any, em_manutencao: Any) -> bool:
    if em_manutencao:
        return False
    return str(estado or "").strip().lower() not in _RETIRED_ESTADOS


async def mirror_molds(
    *,
    session,
    tenant_id: UUID,
    adapter,
    since: Optional[date] = None,
) -> EtlRunResult:
    """Bridge curated molds → ``plan.mold`` and reconcile against the ERP."""
    async with EtlRunner(session, tenant_id, source="molds") as run:
        active_id = await session.scalar(
            select(ActiveRun.active_ingestion_id).where(ActiveRun.id == 1)
        )
        if active_id is None:
            logger.warning(
                "molds mirror — no active curated ingestion. Run the Excel "
                "ingest (factory_data_product CLI) first; nothing to bridge."
            )
            return run.result

        # ERP pocket counts — vw_pp1_moldes carries `numero_pocos` for the
        # ~91 molds the ERP knows; default 1 for the Excel-only majority.
        erp_rows = await adapter.fetch_molds()
        erp_pockets: Dict[str, int] = {}
        for m in erp_rows:
            try:
                erp_pockets[str(m.get("molde_id"))] = int(m.get("numero_pocos") or 1)
            except (TypeError, ValueError):
                erp_pockets[str(m.get("molde_id"))] = 1

        curated = (await session.execute(
            select(CuratedMold).where(
                CuratedMold.ingestion_id == active_id,
                CuratedMold.is_quarantined.is_(False),
            )
        )).scalars().all()
        run.count_read(len(curated))

        mapped: List[Dict[str, Any]] = []
        for c in curated:
            mold_code = str(c.molde_id)
            mapped.append({
                "mold_code": mold_code,
                "model_id": str(c.modelo_id or ""),
                "name": c.molde_nome,
                "pocket_count": erp_pockets.get(mold_code, 1),
                "mold_type": c.tipo,
                "active": _is_active(c.estado, c.em_manutencao),
            })
        await run.upsert(
            Mold, mapped,
            key_fields=["mold_code"],
            update_fields=["model_id", "name", "pocket_count",
                           "mold_type", "active"],
        )

        await _reconcile(session, tenant_id, erp_rows)
    return run.result


async def _reconcile(session, tenant_id: UUID, erp_rows: List[Dict[str, Any]]) -> None:
    """Log how the ERP mold catalogue diverges from ``plan.mold``.

    Expected: ≈419 molds present only in the curated/Excel side (the ERP
    only tracks ~91). ``only_in_live`` (ERP molds missing from plan.mold)
    SHOULD be empty — a non-empty set means the Excel sheet is stale.
    """
    plan_codes = (await session.execute(
        select(Mold.mold_code).where(Mold.tenant_id == tenant_id)
    )).scalars().all()
    diff = await compare_shadow(
        [{"mold_code": str(m.get("molde_id"))} for m in erp_rows],
        [{"mold_code": c} for c in plan_codes],
        key="mold_code",
    )
    logger.info(
        "molds reconcile — erp=%d plan=%d match=%d only_in_erp=%d only_in_plan=%d",
        diff["live_count"], diff["curated_count"], diff["match_count"],
        len(diff["only_in_live"]), len(diff["only_in_curated"]),
    )
    if diff["only_in_live"]:
        logger.warning(
            "molds reconcile — %d ERP mold(s) missing from plan.mold "
            "(Excel sheet may be stale): %s",
            len(diff["only_in_live"]), diff["only_in_live"][:20],
        )


register_mirror("molds", mirror_molds)
