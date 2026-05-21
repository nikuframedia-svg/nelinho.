"""Q.25.C — verificar que o sync ERP->Postgres aterrou.

Conta as linhas das tabelas dos schemas que os 5 mirrors Q.20 escrevem
(`core`, `plan`, `hr`, `quality`) no Postgres do nelinho. Read-only.
Sem segredos: le `settings.database_url`.

Uso:
    $env:PYTHONPATH = "c:/Users/User/nelinho"
    .\.venv\Scripts\python.exe scripts/check_nelo_sync.py
"""

from __future__ import annotations

import asyncio

import asyncpg

from src.shared.config import settings

# schemas que os mirrors ETL Q.20 escrevem
_SCHEMAS = ("core", "plan", "hr", "quality")


async def main() -> None:
    # asyncpg quer postgresql:// puro (sem o +asyncpg do SQLAlchemy)
    dsn = settings.database_url.replace("+asyncpg", "")
    print("=== Q.25.C — verificacao do sync ERP->Postgres ===")
    print(f"db = ...@{dsn.split('@')[-1]}")
    print()

    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema = ANY($1::text[]) AND table_type = 'BASE TABLE'
            ORDER BY table_schema, table_name
            """,
            list(_SCHEMAS),
        )
        total = 0
        for r in rows:
            sch, tbl = r["table_schema"], r["table_name"]
            try:
                n = await conn.fetchval(f'SELECT count(*) FROM "{sch}"."{tbl}"')
            except Exception as e:
                print(f"  {sch}.{tbl:38s}  ERRO: {type(e).__name__}")
                continue
            total += n
            flag = "  <- vazia" if n == 0 else ""
            print(f"  {sch}.{tbl:38s} {n:>12,}{flag}")

        # foco: as duracoes reais mineradas pelo time_mining
        print()
        try:
            with_dur = await conn.fetchval(
                "SELECT count(*) FROM plan.routing_template_phase "
                "WHERE duration_p50_h IS NOT NULL"
            )
            print(f"  routing_template_phase com duration_p50_h: {with_dur:,}")
        except Exception as e:
            print(f"  (check de duracoes falhou: {type(e).__name__}: {e})")

        print()
        print(f"=== {len(rows)} tabelas, {total:,} linhas nos 4 schemas ===")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
