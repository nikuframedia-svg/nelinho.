"""Q.99 Onda 1 / Agente A — view `marts.v_ofs_em_curso_snapshot`.

Medida registada: `producao_ofs_em_curso.total` (CONTAGEM adimensional).

Critério canónico Q.79: "OF em curso" = OF cujo `OF_FP_ID` aponta para uma
fase com `FP_SEQUENCIA < 30`. Fases com sequência ≥ 30 correspondem a
estados terminais ("Recolhido", "Cancelado", "Devolvido", "Histórico", …)
e ficam de fora.

Anchor factory_raw espelho (Q.79 / Q.99): **4 233 OFs activas**.
- `factory_raw.ordemfabrico` (101 738 rows) JOIN
  `factory_raw.fases_producao` (32 fases com seq < 30 efectivamente
  pobladas) por `OF_FP_ID = FP_ID`.
- `OF_FP_ID` 100% preenchido na fonte (sem nulos).

Granularidade: snapshot **(fase_id, fase) → n_ofs** — uma linha por fase
activa, com a contagem absoluta. `SUM(n_ofs)` na view bate o anchor.
Não há dim de tempo (snapshot do estado actual; sem histórico de
transições aqui — esse fica para o cubo `producao_ofs_por_fase` da Onda
B se vier).

CONTAGEM é adimensional e trivialmente aditiva: soma sempre OK. Não há
ratio measure, não há mistura de unidades.

Idempotente. Falha cedo se factory_raw.* não existir.

Uso:
    .\\.venv\\Scripts\\python.exe scripts/setup_marts_ofs_em_curso.py
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_ofs_em_curso_snapshot AS
-- Q.99 Onda 1 / Agente A — snapshot de OFs em curso por fase activa.
-- Critério canónico Q.79: FP_SEQUENCIA < 30 = "em curso" (estados não-terminais).
-- Anchor factory_raw espelho: 4 233 OFs activas (SUM dos n_ofs).
-- CONTAGEM — soma sempre OK (sem mistura de unidades).
SELECT
    fp."FP_ID"                              AS fase_id,
    fp."FP_NOME"                            AS fase,
    COUNT(*)                                AS n_ofs
FROM factory_raw.ordemfabrico o
JOIN factory_raw.fases_producao fp
  ON fp."FP_ID" = o."OF_FP_ID"
WHERE fp."FP_SEQUENCIA" < 30
GROUP BY fp."FP_ID", fp."FP_NOME"
"""


async def _ensure_prereqs(pg_conn: asyncpg.Connection) -> None:
    """Confirma que as tabelas factory_raw necessárias existem."""
    for table in ("ordemfabrico", "fases_producao"):
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
                f"factory_raw.{table} não existe — corre primeiro "
                "`python scripts/q75_setup_raw_mirror.py` para espelhar "
                "o ERP, depois volta a correr este script."
            )

    await pg_conn.execute("CREATE SCHEMA IF NOT EXISTS marts")


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await _ensure_prereqs(conn)
        await conn.execute("DROP VIEW IF EXISTS marts.v_ofs_em_curso_snapshot")
        await conn.execute(VIEW_SQL)

        # Sanity 1: linhas da view (uma por fase activa) + total agregado.
        n_rows = await conn.fetchval(
            "SELECT COUNT(*) FROM marts.v_ofs_em_curso_snapshot"
        )
        total_ofs = await conn.fetchval(
            "SELECT SUM(n_ofs)::int FROM marts.v_ofs_em_curso_snapshot"
        )
        print(
            f"  OK view criada — {n_rows} fases activas | "
            f"{total_ofs:,} OFs em curso (total)."
        )

        # Sanity 2: nenhum n_ofs negativo nem fraccionário (CONTAGEM).
        guard = await conn.fetchrow(
            """
            SELECT
                MIN(n_ofs)::int AS min_n,
                MAX(n_ofs)::int AS max_n,
                BOOL_AND(n_ofs >= 0) AS all_non_negative
            FROM marts.v_ofs_em_curso_snapshot
            """
        )
        print(
            f"  Range guard: min={guard['min_n']}  "
            f"max={guard['max_n']}  all_non_negative={guard['all_non_negative']}"
        )
        assert guard["all_non_negative"], "CONTAGEM violada: n_ofs negativo"
        assert guard["min_n"] >= 1, "Esperado n_ofs >= 1 por linha agrupada"

        # Anchor Q.79 / Q.99: 4 233 OFs em curso no espelho.
        EXPECTED_ANCHOR = 4233
        assert total_ofs == EXPECTED_ANCHOR, (
            f"Anchor falhou: total={total_ofs} != esperado={EXPECTED_ANCHOR}. "
            "Confirma se o espelho factory_raw está sincronizado."
        )
        print(f"  ANCHOR Q.79/Q.99 bate: {total_ofs} OFs em curso (esperado {EXPECTED_ANCHOR}).")

        # Top 5 fases para inspecção rápida.
        rows = await conn.fetch(
            """
            SELECT fase, n_ofs
            FROM marts.v_ofs_em_curso_snapshot
            ORDER BY n_ofs DESC
            LIMIT 5
            """
        )
        print("\n  Top 5 fases activas:")
        for r in rows:
            print(f"    {r['fase']:40s} {r['n_ofs']:>6}")

        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
