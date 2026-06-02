"""Q.67.4.E — jobs do copilot (RAG schema reindex).

Job nocturno que re-indexa os schema docs PT-PT no RAG do copilot.
Cron 04:00 (low traffic).

Q.157.C — usa `force=True` (refresh canónico: delete + reingest). O
`ingest_schema_docs` com `force=False` NÃO detecta "schema mudou" — apenas
ACUMULA um novo chunk por tabela a cada corrida, duplicando o índice todas
as noites. `force=True` apaga os chunks `schema_docs` do tenant e reingere,
deixando exactamente 1 chunk por tabela (idempotente).
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
                force=True,  # Q.157.C — refresh canónico, sem duplicar
            )
            await session.commit()
        logger.info(
            "copilot_schema_reindex ok chunks=%d tenant=%s",
            chunks, tenant_id,
        )
    except Exception as exc:
        logger.warning("copilot_schema_reindex failed: %s", exc)
