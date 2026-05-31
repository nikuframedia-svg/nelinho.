"""Q.104.C Medida 2 — view `marts.v_atrasos_culpa_mes`.

Medida registada: `logistica_atrasos_culpa.total` (CONTAGEM adimensional).

**Fonte**: factory_raw.transp_datas (3 030 rows) JOIN
factory_raw.transp_datas_classificacao (3 valores: Culpa Nelo /
Transportador / Cliente). Q.104.A espelhamento.

**SEMÂNTICA CRÍTICA — culpa é CLASSIFICAÇÃO NELO REPORTADA, NÃO veredito**:
  - `TRDT_TRDTCL_ID` é o ID da classificação humana NELO atribuída ao
    atraso no momento da alteração de data.
  - O sistema **REPORTA** a repartição registada, **NÃO ATRIBUI**
    responsabilidade.
  - Atraso = alteração de data registada em TRANSP_DATAS. Atrasos NÃO
    registados aqui não estão visíveis.

**Granularidade view**: 1 row por (mês × culpa). Período por
`TRDT_DATA_CRIACAO` (quando a alteração foi registada).

**Anchor Q.104.A** (real pós-espelhamento):
  - Total = 3 030 atrasos (Q.82 dizia 3 027; +3 rows recentes).
  - Cliente 2 114 (~70 %); Nelo 790 (~26 %); Transportador 126 (~4 %).
  - **100 % têm classificação** — sem categoria NULL.

CONTAGEM adimensional — soma sempre OK.

Idempotente.

Uso::

    PYTHONPATH=. .venv/Scripts/python.exe scripts/setup_marts_atrasos_culpa_mes.py
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_atrasos_culpa_mes AS
-- Q.104.C Medida 2 — atrasos por (mês, classificação NELO).
-- Culpa é CLASSIFICAÇÃO humana NELO registada, não veredito do sistema.
SELECT
    DATE_TRUNC('month', CAST(NULLIF(td."TRDT_DATA_CRIACAO", '') AS date))::date AS data,
    COALESCE(cl."TRDTCL_NOME", 'Sem classificação')                AS culpa,
    td."TRDT_TRDTCL_ID"                                            AS culpa_id,
    COUNT(*)                                                       AS n_atrasos
FROM factory_raw.transp_datas td
LEFT JOIN factory_raw.transp_datas_classificacao cl
       ON cl."TRDTCL_ID" = td."TRDT_TRDTCL_ID"
WHERE td."TRDT_DATA_CRIACAO" IS NOT NULL
  AND NULLIF(td."TRDT_DATA_CRIACAO", '') IS NOT NULL
GROUP BY 1, 2, 3
"""


async def _ensure_prereqs(pg_conn: asyncpg.Connection) -> None:
    for table in ("transp_datas", "transp_datas_classificacao"):
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
        await conn.execute("DROP VIEW IF EXISTS marts.v_atrasos_culpa_mes")
        await conn.execute(VIEW_SQL)

        n = await conn.fetchval("SELECT COUNT(*) FROM marts.v_atrasos_culpa_mes")
        rng = await conn.fetchrow(
            "SELECT MIN(data) AS min_d, MAX(data) AS max_d FROM marts.v_atrasos_culpa_mes"
        )
        print(f"  OK view -- {n:,} rows. Range {rng['min_d']} -> {rng['max_d']}.")

        # Anchor total = 3030
        EXPECTED_TOTAL = 3030
        total = await conn.fetchval(
            "SELECT SUM(n_atrasos)::int FROM marts.v_atrasos_culpa_mes"
        )
        diff_pct = 100.0 * abs(total - EXPECTED_TOTAL) / EXPECTED_TOTAL
        print(
            f"  ANCHOR total atrasos: {total:,} "
            f"(esperado {EXPECTED_TOTAL:,}, delta {diff_pct:.2f} %)"
        )
        assert diff_pct < 1.0, f"Anchor falhou: delta {diff_pct} %"

        # Distribuição por culpa
        print("\n  Distribuição por culpa (anchor Q.82 70/26/4):")
        rows = await conn.fetch(
            """
            SELECT culpa, SUM(n_atrasos)::int AS n,
                   ROUND(100.0*SUM(n_atrasos)/3030, 1) AS pct
            FROM marts.v_atrasos_culpa_mes
            GROUP BY 1 ORDER BY 2 DESC
            """
        )
        for r in rows:
            c = (r['culpa'] or '?')[:30]
            print(f"    {c:<30} n={r['n']:>5,}  ({r['pct']} %)")

        # Anchor Cliente = 2114
        n_cliente = await conn.fetchval(
            "SELECT SUM(n_atrasos)::int FROM marts.v_atrasos_culpa_mes "
            "WHERE culpa='Culpa Cliente'"
        )
        print(f"\n  ANCHOR Culpa Cliente: {n_cliente:,} (esperado ~2 114)")
        assert 2100 <= n_cliente <= 2130, f"Cliente fora: {n_cliente}"

        # Range temporal
        rows = await conn.fetch(
            """
            SELECT EXTRACT(YEAR FROM data)::int AS ano, SUM(n_atrasos)::int AS n
            FROM marts.v_atrasos_culpa_mes
            GROUP BY 1 ORDER BY 1 DESC LIMIT 8
            """
        )
        print("\n  Histórico anual atrasos:")
        for r in rows:
            print(f"    {r['ano']}: {r['n']:,}")

        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
