"""Q.99 Onda 1 / Agente C — view `marts.v_ofs_por_fase_snapshot`.

Medida registada: `producao_ofs_por_fase.total` (CONTAGEM adimensional).

Drill-down da medida do Agente A. **Mesma fonte, mesmo critério Q.79**
(`FP_SEQUENCIA < 30`), mas a dim `fase` é OBRIGATÓRIA — o utilizador
pergunta sempre "por fase" / "em fase X" / "distribuição por fase".

Diferença vs `producao_ofs_em_curso.total` (Agente A):
- Agente A é um *counter* total: pergunta canónica "Quantas OFs em
  curso?" → 4 233 (com `fase` como dim opcional para drill-down).
- Agente C (esta medida) é um *snapshot por fase*: a dim canónica
  obrigatória é `fase`. Pergunta canónica "Quantas OFs em curso na
  Laminagem peças?" / "Distribuição de OFs por fase?".
- Ambas têm a MESMA SUM(n_ofs) = 4 233. São **compatíveis** (mesma fonte,
  mesmo critério, mesma contagem); diferem só na ergonomia da consulta
  (`fase` opt-in vs `fase` obrigatória).

A view inclui `fp_sequencia` adicionalmente vs Agente A — útil para
ordenar/filtrar por etapa do processo industrial (laminagem cedo, pintura
no meio, controlo de qualidade tarde).

Anchor factory_raw espelho (Fase 0 confirmado contra a BD):
- **Total: 4 233 OFs em curso** distribuídas por **32 fases activas**.
- Top 10 (validado live):
    Laminagem peças           seq=10  n=1 233
    Corte peças               seq=13  n=1 100
    Não Laminado              seq= 1  n=  392
    Corte                     seq=13  n=  294
    Laminagem Infusão         seq=10  n=  222
    Laminagem Double Dutch    seq=10  n=  151
    Colagem Peças             seq=14  n=  139
    Laminagem                 seq=10  n=  107
    Controlo de qualidade Final seq=29 n=  88
    Acabamento 2              seq=20  n=   75

Granularidade: snapshot **(fp_id, fp_nome, fp_sequencia) → n_ofs** —
uma linha por fase activa. `SUM(n_ofs) = 4 233` é o invariante.

CONTAGEM adimensional, trivialmente aditiva. Soma cross-row sempre OK.

Idempotente. Falha cedo se factory_raw.* não existir.

Uso:
    .\\.venv\\Scripts\\python.exe scripts/setup_marts_ofs_por_fase.py
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_ofs_por_fase_snapshot AS
-- Q.99 Onda 1 / Agente C — distribuição de OFs em curso por fase activa.
-- Critério canónico Q.79: FP_SEQUENCIA < 30 = "em curso" (estados não-terminais).
-- Drill-down de producao_ofs_em_curso.total — mesma fonte, dim 'fase'
-- como cidadã de primeira classe (obrigatória semanticamente).
-- Anchor factory_raw espelho: 4 233 OFs activas (SUM dos n_ofs).
-- CONTAGEM — soma sempre OK (sem mistura de unidades).
SELECT
    fp."FP_ID"                              AS fp_id,
    fp."FP_NOME"                            AS fp_nome,
    fp."FP_SEQUENCIA"::int                  AS fp_sequencia,
    COUNT(*)                                AS n_ofs
FROM factory_raw.ordemfabrico o
JOIN factory_raw.fases_producao fp
  ON fp."FP_ID" = o."OF_FP_ID"
WHERE fp."FP_SEQUENCIA" < 30
GROUP BY fp."FP_ID", fp."FP_NOME", fp."FP_SEQUENCIA"
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
        await conn.execute("DROP VIEW IF EXISTS marts.v_ofs_por_fase_snapshot")
        await conn.execute(VIEW_SQL)

        # Sanity 1: linhas da view (uma por fase activa) + total agregado.
        n_rows = await conn.fetchval(
            "SELECT COUNT(*) FROM marts.v_ofs_por_fase_snapshot"
        )
        total_ofs = await conn.fetchval(
            "SELECT SUM(n_ofs)::int FROM marts.v_ofs_por_fase_snapshot"
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
                BOOL_AND(n_ofs >= 1) AS all_positive,
                BOOL_AND(fp_sequencia < 30) AS all_in_curso
            FROM marts.v_ofs_por_fase_snapshot
            """
        )
        print(
            f"  Range guard: min={guard['min_n']}  "
            f"max={guard['max_n']}  all_positive={guard['all_positive']}  "
            f"all_in_curso(<30)={guard['all_in_curso']}"
        )
        assert guard["all_positive"], "CONTAGEM violada: n_ofs < 1"
        assert guard["all_in_curso"], "Q.79 violado: fp_sequencia >= 30 vazou"

        # Anchor Q.79 / Q.99: 4 233 OFs em curso no espelho.
        EXPECTED_ANCHOR = 4233
        assert total_ofs == EXPECTED_ANCHOR, (
            f"Anchor falhou: total={total_ofs} != esperado={EXPECTED_ANCHOR}. "
            "Confirma se o espelho factory_raw está sincronizado."
        )
        print(f"  ANCHOR Q.79/Q.99 bate: {total_ofs} OFs em curso (esperado {EXPECTED_ANCHOR}).")

        # Sanity 3: delta zero contra a fonte raw (anti soma-cega).
        raw_total = await conn.fetchval(
            """
            SELECT COUNT(*)::int
            FROM factory_raw.ordemfabrico o
            JOIN factory_raw.fases_producao fp ON fp."FP_ID" = o."OF_FP_ID"
            WHERE fp."FP_SEQUENCIA" < 30
            """
        )
        assert raw_total == total_ofs, (
            f"Delta NON-zero view vs raw: view={total_ofs} raw={raw_total}"
        )
        print(f"  Delta zero view vs raw: {raw_total} == {total_ofs} OK")

        # Top 10 fases para inspecção rápida (espelha a anchor do briefing).
        rows = await conn.fetch(
            """
            SELECT fp_nome, fp_sequencia, n_ofs
            FROM marts.v_ofs_por_fase_snapshot
            ORDER BY n_ofs DESC
            LIMIT 10
            """
        )
        print("\n  Top 10 fases activas:")
        for r in rows:
            print(
                f"    {r['fp_nome']:40s} seq={r['fp_sequencia']:>2}  "
                f"n={r['n_ofs']:>5}"
            )

        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
