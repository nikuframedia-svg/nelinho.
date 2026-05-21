"""Q.68.1.D — Seed RAG schema docs em dev (idempotente).

Chama ingest_schema_docs(force=True/False) sob tenant dev. Útil para:
- Bootstrap de ambiente dev fresco (após drop+recreate DB)
- Re-seed após mudanças de schema
- Verificação manual ad-hoc (o cron nightly Q.67.4.E só corre 04:00 UTC,
  por isso em dev a tabela copilot_rag_chunk começa vazia)

Uso:
    python scripts/seed_copilot_rag_dev.py
    python scripts/seed_copilot_rag_dev.py --tenant <uuid> --force

Notas:
- Em dev sem pgvector instalado a tabela `copilot_rag_chunk` não é
  criada por `bootstrap_dev_full.py` (skip explícito). O script
  apanha esse caso e imprime mensagem clara em vez de stack trace.
- `--force` apaga chunks `source_type='schema_docs'` antes de
  reingerir (refresh canónico). Sem `--force` acumula chunks novos.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DEV_TENANT = UUID("00000000-0000-0000-0000-000000000001")


async def main(tenant_id: UUID, force: bool) -> int:
    from src.copilot.rag import ingest_schema_docs
    from src.shared.database import async_session_factory

    async with async_session_factory() as session:
        chunks = await ingest_schema_docs(
            session=session,
            tenant_id=tenant_id,
            force=force,
        )
        await session.commit()
    print(f"Seeded {chunks} schema chunks for tenant {tenant_id} (force={force})")
    return chunks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Seed copilot RAG schema docs em dev (Q.68.1.D)",
    )
    parser.add_argument(
        "--tenant",
        default=str(DEV_TENANT),
        help="Tenant UUID (default: NELO dev tenant)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Apaga chunks existentes (source_type='schema_docs') antes de re-indexar",
    )
    args = parser.parse_args()

    try:
        chunks = asyncio.run(main(UUID(args.tenant), args.force))
    except Exception as exc:
        # Pgvector ausente em dev (tabela skip em bootstrap_dev_full) ou
        # Postgres offline são casos esperados — mensagem clara, exit 2.
        msg = str(exc).lower()
        if "copilot_rag_chunk" in msg or "pgvector" in msg or "vector" in msg:
            print(f"RAG seed skipped (pgvector indisponível em dev): {exc}")
            raise SystemExit(2) from exc
        print(f"RAG seed failed: {exc}")
        raise SystemExit(3) from exc

    raise SystemExit(0 if chunks > 0 else 1)
