"""Q.66.A.4 — job de shortage scan (supply).

Movido de `src.shared.scheduler` sem alterações de comportamento.
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID
from src.shared.time import utc_now_naive

logger = logging.getLogger(__name__)


async def _shortage_scan_job(tenant_id: UUID) -> None:
    """Run ShortageDetector.scan() hourly for a single tenant (Sprint O.4)."""
    from src.shared.database import get_session_context
    from src.supply.shortage_detector import ShortageDetector

    started = utc_now_naive()
    try:
        async with get_session_context() as session:
            detector = ShortageDetector(session=session, tenant_id=tenant_id)
            summary = await detector.scan()
            await session.commit()
        elapsed_ms = int((utc_now_naive() - started).total_seconds() * 1000)
        logger.info(
            "shortage_scan tenant=%s warn=%s critical=%s skipped=%s elapsed_ms=%s",
            tenant_id, summary.get("warn_created"),
            summary.get("critical_created"), summary.get("skipped_duplicate"),
            elapsed_ms,
        )
    except Exception as exc:
        logger.error("shortage_scan tenant=%s failed: %s", tenant_id, exc, exc_info=True)


async def _rop_recompute_job(tenant_id: UUID) -> None:
    """Q.173.Y — recalcula os ROPs (reorder points) por tenant.

    O serviço existe desde Q.67 mas NUNCA correu nem estava agendado —
    `supply_rop_configs` ficou a 0 e o shortage-risks do /overall devolvia
    [] para sempre (auditoria 2026-06-11). Com os mínimos reais
    (P_STOCKMIN), lead times reais (E_PRAZOENTREGA) e o ledger de 24 meses
    (Q.173.D/F), o cálculo passou a ter matéria-prima. Corre de madrugada,
    depois do sync nocturno dos espelhos.
    """
    from src.shared.database import get_session_context
    from src.supply.services.rop_calculator import recompute_rop_configs

    started = utc_now_naive()
    try:
        async with get_session_context() as session:
            summary = await recompute_rop_configs(session, tenant_id)
            await session.commit()
        elapsed_ms = int((utc_now_naive() - started).total_seconds() * 1000)
        logger.info(
            "rop_recompute tenant=%s %s elapsed_ms=%s",
            tenant_id, summary, elapsed_ms,
        )
    except Exception as exc:
        logger.error(
            "rop_recompute tenant=%s failed: %s", tenant_id, exc, exc_info=True,
        )
