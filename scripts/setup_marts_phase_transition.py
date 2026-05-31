"""Q.108.W2 — view `marts.v_phase_transition_time_mes`.

Tempo de transição entre fases consecutivas no fluxo da mesma OF. Identifica
queues (idle time) entre estações.

Definição:
  Para cada OF, ordenar fases por FP_SEQUENCIA e calcular:
    transition_h = MIN(OFFP_DATAINICIO_seguinte) - MAX(OFFP_DATAFIM_actual)

Source: factory_raw.of_fp + factory_raw.fases_producao (FP_SEQUENCIA ordering).

Granularidade: mês de fechamento da fase actual × fase_origem × fase_destino.
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_phase_transition_time_mes AS
WITH phase_envelope AS (
    SELECT
        ofp."OFFP_OF_ID"                                            AS of_id,
        fp."FP_ID"                                                  AS fase_id,
        fp."FP_NOME"                                                AS fase,
        fp."FP_SEQUENCIA"                                           AS seq,
        MIN(CAST(NULLIF(ofp."OFFP_DATAINICIO", '') AS timestamp))   AS phase_start,
        MAX(CAST(NULLIF(ofp."OFFP_DATAFIM", '') AS timestamp))      AS phase_end
    FROM factory_raw.of_fp ofp
    JOIN factory_raw.fases_producao fp
      ON fp."FP_ID" = ofp."OFFP_FP_ID"
    WHERE NULLIF(ofp."OFFP_DATAINICIO", '') IS NOT NULL
      AND NULLIF(ofp."OFFP_DATAFIM", '')    IS NOT NULL
      AND fp."FP_SEQUENCIA" < 30
    GROUP BY 1, 2, 3, 4
),
with_next AS (
    SELECT
        of_id,
        fase_id, fase, seq, phase_end,
        LEAD(fase)        OVER (PARTITION BY of_id ORDER BY seq) AS next_fase,
        LEAD(phase_start) OVER (PARTITION BY of_id ORDER BY seq) AS next_phase_start
    FROM phase_envelope
),
transitions AS (
    SELECT
        DATE_TRUNC('month', phase_end)::date                              AS data,
        fase                                                              AS fase_origem,
        next_fase                                                         AS fase_destino,
        EXTRACT(EPOCH FROM (next_phase_start - phase_end)) / 3600.0       AS transition_h
    FROM with_next
    WHERE next_phase_start IS NOT NULL
      AND next_phase_start > phase_end       -- transição limpa (sem overlap)
)
SELECT
    data,
    fase_origem,
    fase_destino,
    COUNT(*)                                                    AS n_transitions,
    AVG(transition_h)                                           AS transition_h_avg,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY transition_h)   AS transition_h_p50,
    PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY transition_h)   AS transition_h_p90
FROM transitions
GROUP BY 1, 2, 3
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("DROP VIEW IF EXISTS marts.v_phase_transition_time_mes")
        await conn.execute(VIEW_SQL)

        n_rows = await conn.fetchval(
            "SELECT COUNT(*) FROM marts.v_phase_transition_time_mes"
        )
        print(f"  OK view criada — {n_rows:,} linhas (mês × transição).")

        if n_rows == 0:
            print("  AVISO: 0 linhas.")
            return 0

        edge = await conn.fetchrow(
            """
            SELECT
                SUM(n_transitions)            AS total,
                AVG(transition_h_avg)         AS overall_avg,
                COUNT(DISTINCT (fase_origem, fase_destino)) AS n_pares,
                MIN(data) AS min_mes,
                MAX(data) AS max_mes
            FROM marts.v_phase_transition_time_mes
            """
        )
        print(
            f"  Total transitions = {edge['total']:,}  "
            f"AVG transition = {edge['overall_avg']:.2f}h  "
            f"({edge['n_pares']} pares fase→fase, "
            f"{edge['min_mes']} → {edge['max_mes']})"
        )
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
