"""Q.66.A.4 — job de shortage scan (supply).

Movido de `src.shared.scheduler` sem alterações de comportamento.
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

logger = logging.getLogger(__name__)


async def _shortage_scan_job(tenant_id: UUID) -> None:
    """Run ShortageDetector.scan() hourly for a single tenant (Sprint O.4)."""
    from src.shared.database import get_session_context
    from src.supply.shortage_detector import ShortageDetector

    started = datetime.utcnow()
    try:
        async with get_session_context() as session:
            detector = ShortageDetector(session=session, tenant_id=tenant_id)
            summary = await detector.scan()
            await session.commit()
        elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
        logger.info(
            "shortage_scan tenant=%s warn=%s critical=%s skipped=%s elapsed_ms=%s",
            tenant_id, summary.get("warn_created"),
            summary.get("critical_created"), summary.get("skipped_duplicate"),
            elapsed_ms,
        )
    except Exception as exc:
        logger.error("shortage_scan tenant=%s failed: %s", tenant_id, exc, exc_info=True)
