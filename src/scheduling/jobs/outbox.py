"""Q.68.1.B — outbox dispatcher periodic drain job.

Drena `event_outbox` para Kafka a cada 5s. Antes deste job o dispatcher
só corria no shutdown (`src/app/startup.py`), por isso eventos pendentes
ficavam orphaned após crash do processo. APScheduler `coalesce=True +
max_instances=1` previne corridas paralelas; `FOR UPDATE SKIP LOCKED`
no SQL do dispatcher já garante idempotência se houver múltiplos workers.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def _outbox_drain_job() -> None:
    """Cada 5s drena event_outbox para Kafka. No-op se Kafka indisponível.

    Backoff exponencial (Q.66.E.1): retries com `next_retry_at` filter já
    estão no `OutboxDispatcher`; aqui só invocamos `run()`.
    """
    from src.shared.database import async_session_factory
    from src.shared.kafka_client import get_producer
    from src.shared.outbox_dispatcher import OutboxDispatcher

    producer = await get_producer()
    if producer is None:
        logger.debug("outbox_drain skipped — kafka unavailable")
        return

    dispatcher = OutboxDispatcher(
        db_session_factory=async_session_factory,
        kafka_producer=producer,
    )
    try:
        await dispatcher.run()
    except Exception as exc:  # job nunca rebenta scheduler
        logger.warning("outbox_drain error: %s", exc)
