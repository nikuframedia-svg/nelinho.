"""Q.133.B — N estações paralelas por fase, derivado da concorrência REAL.

O ERP não tem master de máquinas/centros (`OFFP_ARM_ID` constante, `core.machines`
vazio). MAS a concorrência histórica em `factory_raw.of_fp` prova que cada fase
corre N barcos em paralelo (ex.: Laminagem ~11, Cura ~13). O CPO serializava tudo
num pool "MANUAL" único → makespan irrealista.

`derive_phase_stations` mede o **p95 da concorrência** (sweep-line sobre os
timestamps reais; p95 e não o pico, para ser robusto a dias anómalos) e devolve
`{fase_id: N}` (N estações por fase). O `scheduler_run` constrói N máquinas por
fase e o `routing_resolver` atribui cada op ao work-center da sua fase — dando
paralelismo real SEM tocar o decoder (cada estação continua capacity-1, o molde
continua a serializar via `mold_free_at`).

Spelke: N vem de `OFFP_DATAINICIO→OFFP_DATAFIM` reais (limpos, teto 168h), nunca
inventado; `N>=1` sempre (axioma capacity≥0).
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

_LOOKBACK_DAYS = 365
_N_MAX = 40          # teto (ex.: "Corte peças" tem p95~191 — componentes)
_N_DEFAULT = 4       # fases de produção sem amostra suficiente

_SQL = text(
    """
    WITH base AS (
        SELECT op."OFFP_FP_ID"::text AS fase_id,
               CAST(NULLIF(op."OFFP_DATAINICIO", '') AS timestamp) AS t0,
               CAST(NULLIF(op."OFFP_DATAFIM", '')    AS timestamp) AS t1
        FROM factory_raw.of_fp op
        JOIN factory_raw.fases_producao f
          ON f."FP_ID" = op."OFFP_FP_ID" AND f."FP_PRODUCAO" = true
        WHERE NULLIF(op."OFFP_DATAINICIO", '') IS NOT NULL
          AND NULLIF(op."OFFP_DATAFIM", '')    IS NOT NULL
          AND CAST(NULLIF(op."OFFP_DATAFIM", '') AS timestamp)
            > CAST(NULLIF(op."OFFP_DATAINICIO", '') AS timestamp)
          AND CAST(NULLIF(op."OFFP_DATAFIM", '') AS timestamp)
            - CAST(NULLIF(op."OFFP_DATAINICIO", '') AS timestamp) <= interval '168 hours'
          AND CAST(NULLIF(op."OFFP_DATAINICIO", '') AS timestamp) >= :cutoff
    ),
    ev AS (
        SELECT fase_id, t0 AS t, 1 AS d FROM base
        UNION ALL SELECT fase_id, t1 AS t, -1 AS d FROM base
    ),
    run AS (
        SELECT fase_id,
               SUM(d) OVER (
                   PARTITION BY fase_id ORDER BY t, d DESC
                   ROWS UNBOUNDED PRECEDING
               ) AS running
        FROM ev
    )
    SELECT fase_id,
           percentile_cont(0.95) WITHIN GROUP (ORDER BY running) AS p95
    FROM run
    GROUP BY fase_id
    """
)

# Todas as fases de produção — para garantir que CADA fase tem o seu próprio
# work-center (uma op sem estação cairia na estação de outra fase no decoder).
_ALL_PROD_PHASES_SQL = text(
    'SELECT "FP_ID"::text AS fase_id FROM factory_raw.fases_producao '
    'WHERE "FP_PRODUCAO" = true'
)


async def derive_phase_stations(session: Any, tenant_id: UUID) -> Dict[str, int]:
    """`{fase_id: N}` — N estações paralelas por fase do p95 da concorrência real.

    Best-effort: session None / tabela ausente → `{}` (o caller cai no pool
    "MANUAL" — back-compat). `factory_raw` é tenant-agnóstico (tenant_id só p/
    assinatura coerente)."""
    if session is None:
        return {}
    cutoff = datetime.now(timezone.utc) - timedelta(days=_LOOKBACK_DAYS)
    try:
        rows = (await session.execute(
            _SQL, {"cutoff": cutoff.replace(tzinfo=None)}
        )).mappings().all()
        all_phases = (await session.execute(_ALL_PROD_PHASES_SQL)).mappings().all()
    except SQLAlchemyError as exc:  # pragma: no cover — DB outage / missing table
        logger.debug("Q.133.B phase_stations load skipped: %s", exc)
        return {}
    out: Dict[str, int] = {}
    for r in rows:
        p95 = r["p95"]
        if p95 is None:
            continue
        out[str(r["fase_id"])] = max(1, min(_N_MAX, math.ceil(float(p95))))
    # Fases de produção sem amostra de concorrência → N_DEFAULT estações, para
    # toda a op ter o SEU work-center (nunca ser agendada na estação de outra
    # fase). Sem este passo, ops dessas fases ficavam com machine_id=None.
    for r in all_phases:
        out.setdefault(str(r["fase_id"]), _N_DEFAULT)
    return out


def station_ids_for(fase_id: str, n_stations: int) -> list[str]:
    """IDs determinísticos das estações de uma fase: ``{fase}::01..::0N``.
    Ordenados/zero-padded para o tie-break do decoder ser estável."""
    n = max(1, int(n_stations or 1))
    width = max(2, len(str(n)))
    return [f"{fase_id}::{i:0{width}d}" for i in range(1, n + 1)]
