"""Q.133.A1 — job de calibração de durações por (modelo, fase).

Materializa p50/p95 reais por (OF_P_ID, fase) de `factory_raw.of_fp` em
`plan.phase_duration_calibration` (UPSERT idempotente, com prior/delta vs a
corrida anterior). Fecha a estrutura do loop de aprendizagem: o
`FactoryState` (Q.133.A2) lê esta tabela e prefere o p50 calibrado quando há
amostra suficiente — em vez de re-agregar 537K linhas de of_fp por `load()`.

Fonte e limpeza idênticas a `state.py:_load_historical_durations_routes_db`
(mesmo JOIN of_fp↔ordemfabrico por OF_P_ID, mesmo piso/teto de duração) — por
isso o keyspace bate com `median_duration_h` (modelo = OF_P_ID). Spelke: só
`OFFP_DATAINICIO→OFFP_DATAFIM` reais, nunca CoeficienteX.

Corre ~06:40 UTC (depois do plan_vs_actual 06:30). `factory_raw` é
tenant-agnóstico → escreve sob o tenant dado. Corrida manual:
`scripts/q133_calibrate_durations.py`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.shared.database import get_session_context

logger = logging.getLogger(__name__)

# Limpeza igual a state.py (_DUR_FLOOR_H=0.05, _DUR_CEIL_H=24*7), em minutos.
_DUR_FLOOR_MIN = 0.05 * 60.0
_DUR_CEIL_MIN = 24.0 * 7 * 60.0
# Amostra mínima por (modelo, fase) para confiar no p50 calibrado (Q.133 D2).
_MIN_OBS = 5

_AGG_SQL = text(
    """
    WITH d AS (
        SELECT ofb."OF_P_ID"::text   AS modelo,
               op."OFFP_FP_ID"::text AS phase_id,
               EXTRACT(EPOCH FROM (
                   CAST(NULLIF(op."OFFP_DATAFIM", '')    AS timestamp)
                 - CAST(NULLIF(op."OFFP_DATAINICIO", '') AS timestamp)
               )) / 60.0 AS dur_min
        FROM factory_raw.of_fp op
        JOIN factory_raw.ordemfabrico ofb ON ofb."OF_ID" = op."OFFP_OF_ID"
        WHERE NULLIF(op."OFFP_DATAINICIO", '') IS NOT NULL
          AND NULLIF(op."OFFP_DATAFIM", '')    IS NOT NULL
          AND CAST(NULLIF(op."OFFP_DATAFIM", '') AS timestamp)
            > CAST(NULLIF(op."OFFP_DATAINICIO", '') AS timestamp)
          AND ofb."OF_P_ID" IS NOT NULL
    )
    SELECT modelo, phase_id,
           percentile_cont(0.5)  WITHIN GROUP (ORDER BY dur_min) AS p50,
           percentile_cont(0.95) WITHIN GROUP (ORDER BY dur_min) AS p95,
           count(*) AS n
    FROM d
    WHERE dur_min > :floor AND dur_min <= :ceil
    GROUP BY modelo, phase_id
    HAVING count(*) >= :min_n
    """
)

# prior_p50_min/delta_pct lêem o valor PRÉ-update (o DO UPDATE SET avalia o RHS
# contra a linha antiga). No 1º INSERT ficam NULL/0 — honesto (sem prior).
_UPSERT_SQL = text(
    """
    INSERT INTO plan.phase_duration_calibration
        (tenant_id, modelo, phase_id, p50_min, p95_min, n_obs, calibrated_at,
         prior_p50_min, delta_pct)
    VALUES (:tid, :modelo, :phase, :p50, :p95, :n, :ts, NULL, NULL)
    ON CONFLICT (tenant_id, modelo, phase_id) DO UPDATE SET
        prior_p50_min = plan.phase_duration_calibration.p50_min,
        p50_min       = EXCLUDED.p50_min,
        p95_min       = EXCLUDED.p95_min,
        n_obs         = EXCLUDED.n_obs,
        calibrated_at = EXCLUDED.calibrated_at,
        delta_pct     = CASE
            WHEN plan.phase_duration_calibration.p50_min > 0
            THEN (EXCLUDED.p50_min - plan.phase_duration_calibration.p50_min)
                 / plan.phase_duration_calibration.p50_min * 100.0
            ELSE NULL END
    """
)


async def _phase_calibration_job(tenant_id: UUID) -> int:
    """Recalcula e faz UPSERT da calibração de durações. Idempotente.

    Devolve o nº de pares (modelo, fase) escritos (0 quando sem dados).
    """
    started = datetime.now(timezone.utc)
    try:
        async with get_session_context() as session:
            rows = (
                await session.execute(
                    _AGG_SQL,
                    {"floor": _DUR_FLOOR_MIN, "ceil": _DUR_CEIL_MIN, "min_n": _MIN_OBS},
                )
            ).all()
            if not rows:
                logger.info("phase_calibration_job: sem dados tenant=%s", tenant_id)
                return 0
            # `calibrated_at` é `timestamp without time zone` → naive.
            cal_ts = started.replace(tzinfo=None)
            params = [
                {
                    "tid": tenant_id,
                    "modelo": str(r.modelo),
                    "phase": str(r.phase_id),
                    "p50": float(r.p50),
                    "p95": float(r.p95),
                    "n": int(r.n),
                    "ts": cal_ts,
                }
                for r in rows
            ]
            await session.execute(_UPSERT_SQL, params)  # executemany
            await session.commit()
        elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        logger.info(
            "phase_calibration_job: tenant=%s pares=%s elapsed_ms=%s",
            tenant_id, len(params), elapsed_ms,
        )
        return len(params)
    except SQLAlchemyError as exc:
        logger.error(
            "phase_calibration_job tenant=%s falhou: %s",
            tenant_id, exc, exc_info=True,
        )
        return 0


async def _phase_calibration_global_job(tenants: List[UUID]) -> None:
    """Wrapper global: itera os tenants registados. Best-effort por tenant.
    Registado no scheduler core a 06:40 UTC (depois do plan_vs_actual)."""
    for tid in tenants:
        try:
            await _phase_calibration_job(tid)
        except Exception as exc:  # pragma: no cover — coberto pelo inner try
            logger.error(
                "phase_calibration_global_job tenant=%s falhou: %s",
                tid, exc, exc_info=True,
            )
