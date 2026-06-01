"""Q.152 — view `marts.v_ofs_fechadas_dia`.

OFs produzidas/fechadas por DIA. Source: factory_raw.ordemfabrico, usando
`OF_DATAFIM` (data de fecho do header da OF) como data canónica de conclusão —
MESMA definição de `marts.v_throughput_modelo_sem` / measure
`producao_throughput_modelo.total`, mas granularidade DIÁRIA e sem
modelo/disciplina.

Existe porque o copiloto não conseguia responder "quantas ofs foram produzidas
hoje": a única measure de OFs fechadas (`producao_lead_time_of.ofs_fechadas`) é
MENSAL (envelope of_fp) — pedir "hoje" devolvia o bucket do mês inteiro. Esta
view dá a contagem diária honesta (hoje = COUNT de OFs com OF_DATAFIM = hoje).

Granularidade: (dia) → n_ofs_fechadas. CONTAGEM adimensional, trivialmente
aditiva. É VIEW (não materializada) → sempre live, "hoje" recomputa a cada
query; sem job de refresh (igual a v_backlog_dia).

Idempotente. Falha cedo se factory_raw.ordemfabrico não existir.

Uso:
    .\\.venv\\Scripts\\python.exe scripts/setup_marts_ofs_fechadas_dia.py
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_ofs_fechadas_dia AS
-- Q.152: OFs produzidas/fechadas por dia.
-- Critério: OF_DATAFIM (header) preenchida — mesma definição canónica de
-- fecho que producao_throughput_modelo (OF_DATAFIM), granularidade DIÁRIA.
-- CONTAGEM — soma sempre OK (sem mistura de unidades).
SELECT
    CAST(NULLIF(o."OF_DATAFIM", '') AS date)  AS data,
    COUNT(*)                                  AS n_ofs_fechadas
FROM factory_raw.ordemfabrico o
WHERE NULLIF(o."OF_DATAFIM", '') IS NOT NULL
GROUP BY 1
"""


async def _ensure_prereqs(pg_conn: asyncpg.Connection) -> None:
    """Confirma que factory_raw.ordemfabrico existe + cria schema marts."""
    exists = await pg_conn.fetchval(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'factory_raw' AND table_name = 'ordemfabrico'
        )
        """
    )
    if not exists:
        raise SystemExit(
            "factory_raw.ordemfabrico não existe — corre primeiro "
            "`python scripts/q75_setup_raw_mirror.py` para espelhar o ERP, "
            "depois volta a correr este script."
        )
    await pg_conn.execute("CREATE SCHEMA IF NOT EXISTS marts")


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await _ensure_prereqs(conn)
        await conn.execute("DROP VIEW IF EXISTS marts.v_ofs_fechadas_dia")
        await conn.execute(VIEW_SQL)

        # Sanity 1: linhas (uma por dia) + total agregado.
        n_rows = await conn.fetchval(
            "SELECT COUNT(*) FROM marts.v_ofs_fechadas_dia"
        )
        total = await conn.fetchval(
            "SELECT COALESCE(SUM(n_ofs_fechadas), 0)::int "
            "FROM marts.v_ofs_fechadas_dia"
        )
        print(
            f"  OK view criada — {n_rows:,} dias com OFs fechadas | "
            f"{total:,} OFs fechadas (total)."
        )

        if n_rows == 0:
            print("  AVISO: 0 linhas — verifica o espelho factory_raw.ordemfabrico.")
            return 0

        # Sanity 2: CONTAGEM — sem negativos.
        guard = await conn.fetchrow(
            """
            SELECT MIN(n_ofs_fechadas)::int AS min_n,
                   MAX(n_ofs_fechadas)::int AS max_n,
                   BOOL_AND(n_ofs_fechadas >= 0) AS all_non_negative
            FROM marts.v_ofs_fechadas_dia
            """
        )
        assert guard["all_non_negative"], "CONTAGEM violada: n_ofs_fechadas negativo"
        print(
            f"  Range guard: min={guard['min_n']}  max={guard['max_n']}  "
            f"all_non_negative={guard['all_non_negative']}"
        )

        # Sanity 3: o nº de HOJE — o que o copiloto deve responder. Relativo
        # ao dia (não hard-codar); imprime para verificação manual.
        hoje = await conn.fetchval(
            "SELECT COALESCE(n_ofs_fechadas, 0) FROM marts.v_ofs_fechadas_dia "
            "WHERE data = CURRENT_DATE"
        )
        print(f"  OFs fechadas HOJE (CURRENT_DATE) = {hoje or 0}")

        # Últimos 7 dias para inspecção rápida.
        rows = await conn.fetch(
            """
            SELECT data, n_ofs_fechadas
            FROM marts.v_ofs_fechadas_dia
            WHERE data >= CURRENT_DATE - 7
            ORDER BY data DESC
            """
        )
        print("\n  Últimos 7 dias:")
        for r in rows:
            print(f"    {r['data']}  {r['n_ofs_fechadas']:>5}")

        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
