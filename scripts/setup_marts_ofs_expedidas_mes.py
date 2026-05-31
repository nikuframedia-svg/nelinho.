"""Q.104.B Medida 1 — view `marts.v_ofs_expedidas_mes`.

Medida registada: `logistica_ofs_expedidas.total` (CONTAGEM adimensional).

**Fonte**: factory_raw.transp_of (junção N:M) + factory_raw.transporte +
lookups TRANSP_DESTINO + TRANSP_TIPO. Q.104.A espelhamento.

**Critério "OF expedida"** (Q.82 §4 canónico, validado Q.104.A):
  - `TROF_ENVIADO = TRUE` (96 % das rows em TRANSP_OF)
  - `TRANSPORTE.TR_DATA NOT NULL` (data canónica do transporte)
  - **NÃO** usar `OF_DATATRANSPORTE` (morto desde 2009).
  - **NÃO** usar `TR_DATA_ENTREGA` (só 15 % cobertura).

**Granularidade view**: 1 row por (mês × destino × tipo_transporte).
`COUNT(DISTINCT TROF_OF_ID)` evita dupla contagem da junção N:M (média
8.6 OFs por transporte).

**Anchor Q.104.A** (real pós-espelhamento, refinado vs Q.82):
  - 2024: 5 573 OFs expedidas (Q.82 dizia 5 874; delta ~5 % aceitável,
    espelho mais recente / refinamento de critério).
  - Top destinos 2024: UE 3 904, Outros 1 529, Nacional 228.
  - **88 OFs sem destino** identificável (TR_DEST_ID NULL ou fora do
    lookup) — categoria "Desconhecido" emerge.

CONTAGEM adimensional — soma sempre OK.

Idempotente. Falha cedo se factory_raw.transp_* não existir.

Uso::

    PYTHONPATH=. .venv/Scripts/python.exe scripts/setup_marts_ofs_expedidas_mes.py
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_ofs_expedidas_mes AS
-- Q.104.B Medida 1 — OFs expedidas agregadas por (mês, destino, tipo_transporte).
-- COUNT(DISTINCT TROF_OF_ID) evita dupla contagem da junção N:M.
SELECT
    DATE_TRUNC('month', CAST(NULLIF(tr."TR_DATA", '') AS date))::date AS data,
    COALESCE(d."DEST_NOME", 'Desconhecido')                           AS destino,
    tr."TR_DEST_ID"                                                   AS destino_id,
    COALESCE(tt."TRTP_NOME", 'Desconhecido')                          AS tipo_transporte,
    tr."TR_TRTP_ID"                                                   AS tipo_transporte_id,
    COUNT(DISTINCT tof."TROF_OF_ID")                                  AS n_ofs,
    COUNT(*)                                                          AS n_rows_juncao
FROM factory_raw.transp_of tof
JOIN factory_raw.transporte tr ON tr."TR_ID" = tof."TROF_TR_ID"
LEFT JOIN factory_raw.transp_destino d ON d."DEST_ID" = tr."TR_DEST_ID"
LEFT JOIN factory_raw.transp_tipo tt   ON tt."TRTP_ID" = tr."TR_TRTP_ID"
WHERE tof."TROF_ENVIADO" = TRUE
  AND tr."TR_DATA" IS NOT NULL
  AND NULLIF(tr."TR_DATA", '') IS NOT NULL
GROUP BY 1, 2, 3, 4, 5
"""


async def _ensure_prereqs(pg_conn: asyncpg.Connection) -> None:
    for table in ("transp_of", "transporte", "transp_destino", "transp_tipo"):
        exists = await pg_conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'factory_raw' AND table_name = $1
            )
            """,
            table,
        )
        if not exists:
            raise SystemExit(
                f"factory_raw.{table} nao existe -- corre primeiro "
                "scripts/q104_setup_logistica_mirror.py"
            )
    await pg_conn.execute("CREATE SCHEMA IF NOT EXISTS marts")


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await _ensure_prereqs(conn)
        await conn.execute("DROP VIEW IF EXISTS marts.v_ofs_expedidas_mes")
        await conn.execute(VIEW_SQL)

        n = await conn.fetchval("SELECT COUNT(*) FROM marts.v_ofs_expedidas_mes")
        rng = await conn.fetchrow(
            "SELECT MIN(data) AS min_d, MAX(data) AS max_d FROM marts.v_ofs_expedidas_mes"
        )
        print(f"  OK view -- {n:,} rows. Range {rng['min_d']} -> {rng['max_d']}.")

        # Anchor 2024: 5 830 (SUM(n_ofs) por destino+tipo agregada via view).
        # NOTA: COUNT DISTINCT global = 5 573; a SUM da view supera em ~257
        # devido a OFs expedidas em destinos múltiplos no mesmo ano (cada
        # par (destino, tipo) conta separadamente, semanticamente correto
        # para perguntas "OFs para UE em 2024" vs "globais 2024").
        EXPECTED_2024 = 5830
        n_2024 = await conn.fetchval(
            "SELECT SUM(n_ofs)::int FROM marts.v_ofs_expedidas_mes "
            "WHERE EXTRACT(YEAR FROM data) = 2024"
        )
        diff_pct = 100.0 * abs(n_2024 - EXPECTED_2024) / EXPECTED_2024
        print(
            f"  ANCHOR OFs 2024 (SUM agregada): {n_2024:,}  "
            f"(esperado {EXPECTED_2024:,}, delta {diff_pct:.2f} %; "
            f"nota: COUNT DISTINCT global = 5 573, diff = OFs em destinos múltiplos)"
        )
        assert diff_pct < 0.5, f"Anchor falhou: delta {diff_pct} %"

        # Distribuição por destino 2024
        print("\n  Distribuição 2024 por destino:")
        rows = await conn.fetch(
            """
            SELECT destino, SUM(n_ofs)::int AS n
            FROM marts.v_ofs_expedidas_mes
            WHERE EXTRACT(YEAR FROM data) = 2024
            GROUP BY 1 ORDER BY 2 DESC
            """
        )
        for r in rows:
            print(f"    {(r['destino'] or '?'):<25} n={r['n']:,}")

        # Top tipos transporte 2024
        print("\n  Top tipos_transporte 2024:")
        rows = await conn.fetch(
            """
            SELECT tipo_transporte, SUM(n_ofs)::int AS n
            FROM marts.v_ofs_expedidas_mes
            WHERE EXTRACT(YEAR FROM data) = 2024
            GROUP BY 1 ORDER BY 2 DESC LIMIT 8
            """
        )
        for r in rows:
            print(f"    {(r['tipo_transporte'] or '?'):<30} n={r['n']:,}")

        # Anual histórico
        print("\n  Histórico anual:")
        rows = await conn.fetch(
            """
            SELECT EXTRACT(YEAR FROM data)::int AS ano, SUM(n_ofs)::int AS n
            FROM marts.v_ofs_expedidas_mes
            GROUP BY 1 ORDER BY 1 DESC LIMIT 8
            """
        )
        for r in rows:
            print(f"    {r['ano']}: {r['n']:,}")

        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
