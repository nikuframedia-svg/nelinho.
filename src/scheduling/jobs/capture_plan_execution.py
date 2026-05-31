"""Q.134.A3a — writer do loop plan-vs-real VERDADEIRO (PLANEADO vs REALIZADO).

A calibração (Q.133.A1/A2) fecha a *estrutura* do loop: o CPO lê o p50 real do
histórico. Mas isso é só a mediana — não aprende com o **desvio sistemático**
entre o que o CPO PLANEOU e o que a fábrica REALIZOU. Este job escreve esse par.

Por cada `ScheduleCommit` LIVE recente, casa cada operação planeada
(`order_id`=`OF_ID`, `phase_id`) com o realizado em `plan.fases_of_history`
(mesma `(of_id, phase_id)`) → `deviation_pct = (observed-planned)/planned*100`
→ UPSERT `plan.plan_execution_observed` (idempotente, keyed por
`(tenant, schedule_commit_id, of_id, phase_id)`). Sem realizado → observed e
deviation ficam NULL (tracking honesto: regista que está planeado mas ainda não
executado, nunca inventa um valor).

A calibração (Q.134.A3b) lê o `AVG(deviation_pct)` desta tabela e ajusta o p50.

`modelo` (=`OF_P_ID`) é resolvido de `factory_raw.ordemfabrico` para a
calibração poder agrupar por (modelo, fase). Spelke: planeado vem do commit
real, realizado de `fase_inicio→fase_fim` reais — nunca de coeficientes.

Corre 06:35 UTC (entre o plan_vs_actual 06:30 e a calibração 06:40) — wired em
`src/scheduling/core.py`. **Não verificável ao vivo nesta máquina** enquanto não
houver commits LIVE + `fases_of_history` populado; buildable + unit-testável.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import desc, select, text
from sqlalchemy.exc import SQLAlchemyError

from src.plan.cpo.commits import ScheduleCommit
from src.shared.database import get_session_context

logger = logging.getLogger(__name__)

# Quantos commits LIVE recentes re-capturar por corrida (UPSERT idempotente).
_MAX_COMMITS = 100

_HISTORY_SQL = text(
    """
    SELECT of_id::text     AS of_id,
           phase_id::text  AS phase_id,
           duration_min,
           fase_inicio,
           fase_fim
    FROM plan.fases_of_history
    WHERE tenant_id = :tid
      AND of_id = ANY(:of_ids)
    """
)

# OF_ID → OF_P_ID (modelo) para a calibração agrupar por (modelo, fase).
_MODELO_SQL = text(
    """
    SELECT "OF_ID"::text   AS of_id,
           "OF_P_ID"::text AS modelo
    FROM factory_raw.ordemfabrico
    WHERE "OF_ID"::text = ANY(:of_ids)
      AND "OF_P_ID" IS NOT NULL
    """
)

# UPSERT contra o índice único parcial (schedule_commit_id NOT NULL) criado na
# migração 066. Mesmo padrão executemany do phase_calibration_job.
_UPSERT_SQL = text(
    """
    INSERT INTO plan.plan_execution_observed
        (id, tenant_id, schedule_commit_id, of_id, phase_id, modelo,
         planned_start_at, planned_end_at, planned_duration_min,
         observed_start_at, observed_end_at, observed_duration_min,
         deviation_pct, captured_at, created_at, updated_at)
    VALUES
        (:id, :tid, :commit_id, :of_id, :phase, :modelo,
         :p_start, :p_end, :p_dur,
         :o_start, :o_end, :o_dur,
         :dev, :ts, :ts, :ts)
    ON CONFLICT (tenant_id, schedule_commit_id, of_id, phase_id)
        WHERE schedule_commit_id IS NOT NULL
    DO UPDATE SET
        modelo               = EXCLUDED.modelo,
        planned_start_at     = EXCLUDED.planned_start_at,
        planned_end_at       = EXCLUDED.planned_end_at,
        planned_duration_min = EXCLUDED.planned_duration_min,
        observed_start_at    = EXCLUDED.observed_start_at,
        observed_end_at      = EXCLUDED.observed_end_at,
        observed_duration_min= EXCLUDED.observed_duration_min,
        deviation_pct        = EXCLUDED.deviation_pct,
        captured_at          = EXCLUDED.captured_at,
        updated_at           = EXCLUDED.updated_at
    """
)


def _parse_iso(value: Any) -> Optional[datetime]:
    """ISO string (do op do commit) ou datetime → datetime, ou None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _naive(dt: Optional[datetime]) -> Optional[datetime]:
    """Despoja tz — as colunas são `timestamp without time zone`."""
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt


def _min_dt(a: Optional[datetime], b: Optional[datetime]) -> Optional[datetime]:
    if a is None:
        return b
    if b is None:
        return a
    return min(a, b)


def _max_dt(a: Optional[datetime], b: Optional[datetime]) -> Optional[datetime]:
    if a is None:
        return b
    if b is None:
        return a
    return max(a, b)


def build_observed_records(
    *,
    commit_id: Optional[UUID],
    tenant_id: UUID,
    operations: List[Dict[str, Any]],
    history_rows: List[Dict[str, Any]],
    modelo_by_of: Dict[str, str],
    ts: datetime,
) -> List[Dict[str, Any]]:
    """Lógica PURA: casa planeado (operations) vs realizado (history_rows) por
    `(of_id, phase_id)` e devolve os param-dicts do UPSERT. Sem I/O — unit-test.

    `deviation_pct = (observed-planned)/planned*100` só quando ambos existem e
    `planned > 0`; caso contrário NULL (honesto, nunca inventado). Agrega por
    `(of_id, phase_id)`: planeado soma durações (min start / max end), realizado
    idem do histórico.
    """
    planned: Dict[tuple[str, str], Dict[str, Any]] = {}
    for op in operations:
        of_id = str(op.get("order_id") or "")
        phase_id = str(op.get("phase_id") or "")
        if not of_id or not phase_id:
            continue
        agg = planned.setdefault(
            (of_id, phase_id), {"dur": 0.0, "start": None, "end": None}
        )
        agg["dur"] += float(op.get("duration_minutes") or 0.0)
        agg["start"] = _min_dt(agg["start"], _parse_iso(op.get("start_time")))
        agg["end"] = _max_dt(agg["end"], _parse_iso(op.get("end_time")))

    observed: Dict[tuple[str, str], Dict[str, Any]] = {}
    for r in history_rows:
        of_id = str(r.get("of_id") or "")
        phase_id = str(r.get("phase_id") or "")
        if not of_id or not phase_id:
            continue
        agg = observed.setdefault(
            (of_id, phase_id), {"dur": None, "start": None, "end": None}
        )
        dur = r.get("duration_min")
        if dur is not None:
            agg["dur"] = (agg["dur"] or 0.0) + float(dur)
        agg["start"] = _min_dt(agg["start"], _parse_iso(r.get("fase_inicio")))
        agg["end"] = _max_dt(agg["end"], _parse_iso(r.get("fase_fim")))

    records: List[Dict[str, Any]] = []
    for (of_id, phase_id), p in planned.items():
        o = observed.get((of_id, phase_id))
        obs_dur = o["dur"] if o else None
        planned_dur = float(p["dur"])
        deviation = None
        if obs_dur is not None and planned_dur > 0:
            deviation = (obs_dur - planned_dur) / planned_dur * 100.0
        records.append(
            {
                "id": uuid4(),
                "tid": tenant_id,
                "commit_id": commit_id,
                "of_id": of_id,
                "phase": phase_id,
                "modelo": modelo_by_of.get(of_id),
                "p_start": _naive(p["start"]),
                "p_end": _naive(p["end"]),
                "p_dur": planned_dur,
                "o_start": _naive(o["start"]) if o else None,
                "o_end": _naive(o["end"]) if o else None,
                "o_dur": obs_dur,
                "dev": deviation,
                "ts": ts,
            }
        )
    return records


async def _fetch_live_commits(session: Any, tenant_id: UUID) -> List[ScheduleCommit]:
    stmt = (
        select(ScheduleCommit)
        .where(
            (ScheduleCommit.tenant_id == tenant_id)
            & (ScheduleCommit.status == "LIVE")
        )
        .order_by(desc(ScheduleCommit.created_at))
        .limit(_MAX_COMMITS)
    )
    return list((await session.execute(stmt)).scalars().all())


async def _capture_plan_execution_job(tenant_id: UUID) -> int:
    """Captura PLANEADO vs REALIZADO dos commits LIVE recentes. Idempotente.

    Devolve o nº de pares (of, fase) escritos (0 quando não há commits LIVE).
    """
    started = datetime.now(timezone.utc)
    ts = started.replace(tzinfo=None)
    try:
        async with get_session_context() as session:
            commits = await _fetch_live_commits(session, tenant_id)
            if not commits:
                logger.info(
                    "capture_plan_execution: 0 commits LIVE tenant=%s", tenant_id
                )
                return 0
            total = 0
            for commit in commits:
                ops = list(commit.operations or [])
                of_ids = sorted(
                    {str(op.get("order_id")) for op in ops if op.get("order_id")}
                )
                if not of_ids:
                    continue
                history = [
                    dict(r)
                    for r in (
                        await session.execute(
                            _HISTORY_SQL, {"tid": tenant_id, "of_ids": of_ids}
                        )
                    ).mappings()
                ]
                modelo_by_of = {
                    str(r["of_id"]): str(r["modelo"])
                    for r in (
                        await session.execute(_MODELO_SQL, {"of_ids": of_ids})
                    ).mappings()
                }
                records = build_observed_records(
                    commit_id=commit.id,
                    tenant_id=tenant_id,
                    operations=ops,
                    history_rows=history,
                    modelo_by_of=modelo_by_of,
                    ts=ts,
                )
                if records:
                    await session.execute(_UPSERT_SQL, records)
                    total += len(records)
            await session.commit()
        elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        logger.info(
            "capture_plan_execution: tenant=%s commits=%s pares=%s elapsed_ms=%s",
            tenant_id, len(commits), total, elapsed_ms,
        )
        return total
    except SQLAlchemyError as exc:
        logger.error(
            "capture_plan_execution tenant=%s falhou: %s",
            tenant_id, exc, exc_info=True,
        )
        return 0


async def _capture_plan_execution_global_job(tenants: List[UUID]) -> None:
    """Wrapper global: itera os tenants registados. Best-effort por tenant.
    Registado no scheduler core a 06:35 UTC (entre plan_vs_actual e calibração)."""
    for tid in tenants:
        try:
            await _capture_plan_execution_job(tid)
        except Exception as exc:  # pragma: no cover — coberto pelo inner try
            logger.error(
                "capture_plan_execution_global_job tenant=%s falhou: %s",
                tid, exc, exc_info=True,
            )
