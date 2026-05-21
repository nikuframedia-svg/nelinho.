"""Q.66.A.4 — job de daily feedback (copilot).

Movido de `src.shared.scheduler` sem alterações de comportamento.
"""

from __future__ import annotations

import logging
from typing import List
from uuid import UUID

logger = logging.getLogger(__name__)


async def _daily_feedback_job(tenant_ids: List[UUID]) -> None:
    """Regenerate daily feedback for each tenant. No-op if job module missing."""
    try:
        from src.copilot.jobs.daily_feedback import generate_daily_feedback
    except ImportError:
        logger.debug("daily_feedback job module not available — skipping")
        return

    from src.shared.database import get_session_context

    for tid in tenant_ids:
        try:
            async with get_session_context() as session:
                await generate_daily_feedback(session, tid)
                await session.commit()
            logger.info(f"daily_feedback generated for tenant={tid}")
        except Exception as e:
            logger.error(f"daily_feedback failed for tenant={tid}: {e}", exc_info=True)
