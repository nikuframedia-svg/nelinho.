"""Q.108.B2 — view `marts.v_transp_docs_mes`.

Documentação de transportes (TRANSP_DOCS espelhada Q.108-A). Agrega por
mês. Tem flag TRDOC_TRATADO (boolean) → docs_pendentes vs docs_emitidos.

Anchors honestos:
- Total docs: **46 917** rows
- Tratados: **37 254** (79.4%)
- Pendentes: **9 663** (20.6%)
- 2024 docs emitidos: **1 397** (tratados 1 394, pendentes 3)
- 2025 docs emitidos: 1 142
- Transportes com pelo menos 1 doc: 9 218 / 11 382 (81%)

Granularidade: 1 row por mês × tipo_estado (tratado / pendente).
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_transp_docs_mes AS
SELECT
    DATE_TRUNC('month', CAST(NULLIF(td."TRDOC_DATA", '') AS date))::date  AS data,
    COUNT(*)                                                              AS n_docs,
    SUM(CASE WHEN td."TRDOC_TRATADO" = TRUE THEN 1 ELSE 0 END)             AS n_tratados,
    SUM(CASE WHEN td."TRDOC_TRATADO" IS NULL OR td."TRDOC_TRATADO" = FALSE
             THEN 1 ELSE 0 END)                                            AS n_pendentes
FROM factory_raw.transp_docs td
WHERE td."TRDOC_DATA" IS NOT NULL
  AND NULLIF(td."TRDOC_DATA", '') IS NOT NULL
GROUP BY 1
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        # Pre-req: TRANSP_DOCS espelhada (Q.108-A).
        exists = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='factory_raw' AND table_name='transp_docs')"
        )
        if not exists:
            raise SystemExit(
                "factory_raw.transp_docs nao existe — corre primeiro "
                "`python scripts/q108_a_setup_extra_mirror.py`."
            )

        await conn.execute("DROP VIEW IF EXISTS marts.v_transp_docs_mes")
        await conn.execute(VIEW_SQL)

        n = await conn.fetchval("SELECT COUNT(*) FROM marts.v_transp_docs_mes")
        sums = await conn.fetchrow(
            "SELECT SUM(n_docs)::bigint AS total, "
            "SUM(n_tratados)::bigint AS tratados, "
            "SUM(n_pendentes)::bigint AS pendentes "
            "FROM marts.v_transp_docs_mes"
        )
        a2024 = await conn.fetchrow(
            "SELECT SUM(n_docs)::bigint AS d, SUM(n_tratados)::bigint AS t, "
            "SUM(n_pendentes)::bigint AS p "
            "FROM marts.v_transp_docs_mes "
            "WHERE EXTRACT(YEAR FROM data)=2024"
        )
        print(f"  OK -- {n:,} rows.")
        print(f"  Total: docs={sums['total']:,}  tratados={sums['tratados']:,}  "
              f"pendentes={sums['pendentes']:,}")
        print(f"  2024: docs={a2024['d']:,}  tratados={a2024['t']:,}  "
              f"pendentes={a2024['p']}")
        # Anchor: 2024 docs >= 1 390 (cobre 1 397 menos rows com TRDOC_DATA NULL).
        assert a2024['d'] >= 1_390, f"2024 docs anchor falhou: {a2024['d']}"
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
