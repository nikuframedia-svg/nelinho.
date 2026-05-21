"""Q.67.4.E — jobs do copilot (RAG schema reindex).

Job nocturno que re-indexa os schema docs PT-PT no RAG do copilot.
Cron 04:00 (low traffic). Idempotente — usa `force=False` por default
(só re-indexa se schema mudou). Em prod, mudanças de schema vêm de
deploy (Alembic), 1 reindex/dia é suficiente.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def _copilot_schema_reindex_job() -> None:
    """Q.67.4.E — re-indexa schema docs no RAG do copilot.

    No-op se `copilot_enabled=False` ou pgvector/RAG indisponível.
    Logs sucesso/falha sem rebentar o scheduler.
    """
    from src.shared.config import get_settings

    settings = get_settings()
    if not settings.copilot_enabled:
        logger.debug("copilot_schema_reindex skipped — copilot_enabled=False")
        return

    try:
        from src.shared.database import async_session_factory
        from src.copilot.rag import ingest_schema_docs

        # Tenant id default — multi-tenant reindex pode iterar tenants
        # via core.tenants table num follow-up. Por agora reindex sob o
        # tenant dev (00000000-...-001) que é o que existe em dev.
        from uuid import UUID
        tenant_id = UUID("00000000-0000-0000-0000-000000000001")

        async with async_session_factory() as session:
            chunks = await ingest_schema_docs(
                session=session,
                tenant_id=tenant_id,
                force=False,
            )
        logger.info(
            "copilot_schema_reindex ok chunks=%d tenant=%s",
            chunks, tenant_id,
        )
    except Exception as exc:  # noqa: BLE001  Q.67.4.E: best-effort nightly job
        logger.warning("copilot_schema_reindex failed: %s", exc)
