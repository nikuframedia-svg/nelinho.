"""Q.115.H — job diário de aprendizagem de runbooks (04:00 UTC).

Corre `learn_runbook_from_history` para os top-20 error_codes mais
frequentes nos últimos 30 dias. Best-effort: falhas por error_code são
logadas e o job continua para os restantes.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

logger = logging.getLogger(__name__)

_TOP_N = 20
_LOOKBACK_DAYS = 30


async def _runbook_learning_job(tenant_id: UUID) -> None:
    """Aprende runbooks para os top-{_TOP_N} error_codes do tenant."""
    from sqlalchemy import func, select

    from src.quality.models.rework import ReworkEntry
    from src.quality.services.runbook_service import learn_runbook_from_history
    from src.shared.database import get_session_context

    started = datetime.now(timezone.utc)
    since = started - timedelta(days=_LOOKBACK_DAYS)

    try:
        async with get_session_context() as session:
            # Top-N error_codes por frequência na janela
            top_codes_result = await session.execute(
                select(ReworkEntry.error_code, func.count().label("cnt"))
                .where(
                    ReworkEntry.tenant_id == tenant_id,
                    ReworkEntry.detected_at >= since,
                )
                .group_by(ReworkEntry.error_code)
                .order_by(func.count().desc())
                .limit(_TOP_N)
            )
            top_codes = [row.error_code for row in top_codes_result.all()]

            learned = 0
            skipped = 0
            for error_code in top_codes:
                try:
                    runbook = await learn_runbook_from_history(
                        session=session,
                        tenant_id=tenant_id,
                        error_code=error_code,
                    )
                    if runbook is not None:
                        learned += 1
                    else:
                        skipped += 1
                except Exception as exc:  # pragma: no cover
                    logger.warning(
                        "runbook_learning: erro para error_code=%s tenant=%s: %s",
                        error_code, tenant_id, exc, exc_info=True,
                    )
                    skipped += 1

            await session.commit()

        elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        logger.info(
            "runbook_learning tenant=%s top_codes=%d learned=%d skipped=%d elapsed_ms=%d",
            tenant_id, len(top_codes), learned, skipped, elapsed_ms,
        )
    except Exception as exc:
        logger.error(
            "runbook_learning tenant=%s failed: %s", tenant_id, exc, exc_info=True
        )
