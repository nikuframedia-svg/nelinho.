"""Gera chunks PT-PT por tabela e indexa no RAG do copilot.

Q.67.4.E — RAG schema docs PT-PT.

Para cada tabela das 17 schemas do nelinho (plan, core, supply, hr,
quality, profit, governance, dqa, twin, factory_curated, factory_meta,
factory_raw, reports, shared, improve, sandbox), cria 1 chunk:

    <schema>.<table> — <COMMENT_TABELA>. Colunas: <col1: tipo (comment)>,
    <col2: tipo (comment)>, .... Termos: <termos do glossário aplicáveis>.

Indexa via `src/copilot/rag.py:ingest_schema_docs`. Idempotente
(delete + reindex por source='schema_docs').

Uso:
    python scripts/copilot_index_schema.py            # ingere para dev tenant
    python scripts/copilot_index_schema.py --force    # reindex (delete primeiro)
    python scripts/copilot_index_schema.py --tenant <uuid>

Notas operacionais:
  * Em dev sem pgvector, `copilot_rag_chunk` pode não existir (exclusão
    em `bootstrap_dev_full.py`). O script falha cedo com mensagem clara.
  * O `cron nightly_schema_reindex_job` (pendente) chamará este módulo
    com `force=True` uma vez por dia.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from uuid import UUID

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("copilot_index_schema")

DEV_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


async def run(tenant_id: UUID, force: bool) -> int:
    from src.copilot.rag import ingest_schema_docs
    from src.shared.database import async_session_factory

    async with async_session_factory() as session:
        try:
            n = await ingest_schema_docs(
                session=session,
                tenant_id=tenant_id,
                force=force,
            )
        except Exception as exc:
            await session.rollback()
            log.error(
                "Falha ao indexar schema docs: %s. "
                "Verifica que pgvector está instalado e que a tabela "
                "copilot_rag_chunk existe (bootstrap_dev_full.py exclui-a "
                "em dev sem pgvector).",
                exc,
            )
            raise
        await session.commit()
    log.info("OK: %d chunks de schema docs indexados (tenant=%s, force=%s)", n, tenant_id, force)
    return n


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tenant",
        type=UUID,
        default=DEV_TENANT_ID,
        help="Tenant UUID alvo (default: dev tenant).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Apaga chunks existentes (source='schema_docs') antes de reingerir.",
    )
    args = parser.parse_args()

    n = asyncio.run(run(args.tenant, args.force))
    sys.exit(0 if n > 0 else 1)


if __name__ == "__main__":
    main()
