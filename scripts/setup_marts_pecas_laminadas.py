"""Q.99 Onda 1 / Agente B — view `marts.v_pecas_laminadas_mes`.

Medida registada: `producao_pecas_laminadas.total` (CONTAGEM adimensional).

**Plano B descoberto na Fase 0**: a view ERP `vPecasLaminadas` NÃO está
espelhada em `factory_raw`. A alternativa contar fases de laminagem
terminadas por mês via `factory_raw.of_fp` + `factory_raw.fases_producao`,
filtrando `FP_NOME ILIKE '%lamin%'`.

Critério de "peça laminada":
  - Uma row em `of_fp` cuja fase é de laminagem (FP_NOME ILIKE '%lamin%')
  - E que tem `OFFP_DATAFIM` preenchido (fase terminada — não em curso).
  - Período = mês do `OFFP_DATAFIM` (texto ISO `YYYY-MM-DDTHH:MM:SS` → CAST).

Anchor Q.99 / Agente B: **2 393 fases de laminagem terminadas em Abril 2026**.
Breakdown (todas as 5 fases que batem o ILIKE):
  Laminagem peças           1 122
  Laminagem (genérica)        611
  Laminagem Infusão           383
  Não Laminado                191   ← incluído pelo ILIKE (decisão pendente)
  Laminagem Double Dutch       86
  TOTAL                     2 393

**Nota de fidelidade**: "Não Laminado" (FP_ID=11, seq=1) é apanhado pelo
ILIKE `%lamin%` mas semanticamente é o OPOSTO de laminagem — significa
"ainda não foi laminado". O anchor 2 393 do briefing inclui-o; mantive
o filtro literal do briefing por princípio "não inventar decisões de
negócio sozinho". Para refinar mais tarde, basta acrescentar
`AND fp."FP_ID" <> 11` no WHERE da view (passaria a 2 202 em Abril).

Cobertura `OFFP_DATAFIM`: 57 029 / 57 185 rows de laminagem (99,73%) — só
0,27% das fases de laminagem ficam sem data fim no espelho. Aceitável.

Granularidade da view: `(data, fp_nome, fase_id) → n`. Uma linha por
(mês × fase). `SUM(n) WHERE data='2026-04'` = anchor 2 393.

CONTAGEM é adimensional — soma sempre OK.

Idempotente. Falha cedo se factory_raw.* não existir.

Uso:
    .\\.venv\\Scripts\\python.exe scripts/setup_marts_pecas_laminadas.py
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_pecas_laminadas_mes AS
-- Q.99 Onda 1 / Agente B — fases de laminagem TERMINADAS, agregadas por
-- (data, fase). Filtro literal `FP_NOME ILIKE '%lamin%'` conforme
-- briefing (Plano B porque vPecasLaminadas não foi espelhada).
-- Q.99 ajuste pós-smoke: coluna `data` (DATE primeiro do mês) substitui
-- `data` string para a dim Cube poder ser `type: time` — assim o LLM
-- usa `timeDimensions/dateRange` correctamente.
-- Anchor: SUM(n) WHERE data='2026-04-01' = 2 393.
-- CONTAGEM — soma sempre OK (sem mistura de unidades).
SELECT
    DATE_TRUNC('month',
        CAST(NULLIF(ofp."OFFP_DATAFIM", '') AS date)
    )::date                                                          AS data,
    fp."FP_ID"                                                       AS fase_id,
    fp."FP_NOME"                                                     AS fase,
    COUNT(*)                                                         AS n
FROM factory_raw.of_fp ofp
JOIN factory_raw.fases_producao fp
  ON fp."FP_ID" = ofp."OFFP_FP_ID"
WHERE fp."FP_NOME" ILIKE '%lamin%'
  AND NULLIF(ofp."OFFP_DATAFIM", '') IS NOT NULL
GROUP BY 1, 2, 3
"""


async def _ensure_prereqs(pg_conn: asyncpg.Connection) -> None:
    """Confirma que as tabelas factory_raw necessárias existem."""
    for table in ("of_fp", "fases_producao"):
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
                "`python scripts/q75_setup_raw_mirror.py` para espelhar "
                "o ERP, depois volta a correr este script."
            )

    await pg_conn.execute("CREATE SCHEMA IF NOT EXISTS marts")


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await _ensure_prereqs(conn)
        await conn.execute("DROP VIEW IF EXISTS marts.v_pecas_laminadas_mes")
        await conn.execute(VIEW_SQL)

        # Sanity 1: linhas da view + range temporal coberto.
        n_rows = await conn.fetchval(
            "SELECT COUNT(*) FROM marts.v_pecas_laminadas_mes"
        )
        rng = await conn.fetchrow(
            """
            SELECT MIN(data) AS min_m, MAX(data) AS max_m
            FROM marts.v_pecas_laminadas_mes
            """
        )
        print(
            f"  OK view criada -- {n_rows:,} linhas (data, fase). "
            f"Range: {rng['min_m']} a {rng['max_m']}."
        )

        # Validar coluna `data` é date
        col_type = await conn.fetchval(
            """
            SELECT data_type FROM information_schema.columns
            WHERE table_schema='marts' AND table_name='v_pecas_laminadas_mes'
              AND column_name='data'
            """
        )
        print(f"  Coluna 'data' tipo: {col_type}")

        # Sanity 2: nenhum n negativo (CONTAGEM trivial).
        guard = await conn.fetchrow(
            """
            SELECT
                MIN(n)::int AS min_n,
                MAX(n)::int AS max_n,
                BOOL_AND(n >= 1) AS all_positive
            FROM marts.v_pecas_laminadas_mes
            """
        )
        print(
            f"  Range guard: min={guard['min_n']}  "
            f"max={guard['max_n']}  all_positive={guard['all_positive']}"
        )
        assert guard["all_positive"], "CONTAGEM violada: n nao positivo"

        # Anchor Q.99 / Agente B: 2 393 em Abril 2026.
        EXPECTED_ANCHOR = 2393
        total_abril = await conn.fetchval(
            """
            SELECT SUM(n)::int FROM marts.v_pecas_laminadas_mes
            WHERE data = '2026-04-01'
            """
        )
        assert total_abril == EXPECTED_ANCHOR, (
            f"Anchor falhou: total={total_abril} != esperado={EXPECTED_ANCHOR}. "
            "Confirma se o espelho factory_raw esta sincronizado."
        )
        print(
            f"  ANCHOR Q.99 Onda 1 / Agente B bate: "
            f"{total_abril} pecas laminadas em Abril 2026."
        )

        # Subset Laminagem pecas (top-1) em Abril 2026.
        lp_abril = await conn.fetchval(
            """
            SELECT n FROM marts.v_pecas_laminadas_mes
            WHERE data = '2026-04-01' AND fase = 'Laminagem peças'
            """
        )
        print(f"  Subset Laminagem pecas em Abril 2026: {lp_abril}")

        # Breakdown Abril 2026.
        rows = await conn.fetch(
            """
            SELECT fase, n
            FROM marts.v_pecas_laminadas_mes
            WHERE data = '2026-04-01'
            ORDER BY n DESC
            """
        )
        print("\n  Breakdown Abril 2026:")
        for r in rows:
            print(f"    {r['fase']:30s} {r['n']:>6,}")

        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
