"""Q.66.A.4 — job de alerts scan (copilot).

Movido de `src.shared.scheduler` sem alterações de comportamento.
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID
from src.shared.time import utc_now_naive

logger = logging.getLogger(__name__)


async def _alerts_scan_job(tenant_id: UUID) -> None:
    """Run AlertsEngine.scan() for a single tenant, own session."""
    from src.copilot.alerts.engine import AlertsEngine
    from src.shared.database import get_session_context

    started = utc_now_naive()
    try:
        async with get_session_context() as session:
            engine = AlertsEngine(session=session, tenant_id=tenant_id)
            summary = await engine.scan()
            await session.commit()
        elapsed_ms = int((utc_now_naive() - started).total_seconds() * 1000)
        logger.info(
            f"alerts_scan tenant={tenant_id} created={summary.get('created')} "
            f"skipped={summary.get('skipped_duplicate')} elapsed_ms={elapsed_ms}"
        )
    except Exception as e:
        logger.error(f"alerts_scan failed for tenant={tenant_id}: {e}", exc_info=True)
