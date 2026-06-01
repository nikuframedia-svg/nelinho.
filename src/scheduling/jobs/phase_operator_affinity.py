"""Q.115.G / Q.150.A — job diário: afinidade operador/fase do histórico REAL.

Fonte: `factory_raw.offp_eq ⋈ factory_raw.of_fp` (Q.150). NÃO se usa
`plan.fases_of_history` porque o ETL grava `worker_id` SEMPRE NULL neste
deployment → 0 linhas. O operador é `OFFPEQ_E_ID` (= `employee_code`),
resolvido a `core.employees.id` — o id que `get_fase_summary` usa para
resolver o NOME (join `PhaseOperatorAffinity.operator_id == Employee.id`).
Destino: governance.phase_operator_affinity (UPSERT idempotente).

Score = taxa de conclusão (`OFFP_DATAFIM` não-vazio) × (1 − taxa de defeito
`OFFP_RETURN`). Cap 10%: score não muda mais de 0.1 face ao anterior (ou 0.5
neutro na 1ª vez) — estabilidade face a picos de amostras.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, text

from src.core.models.employee import Employee
from src.governance.models.phase_operator_affinity import PhaseOperatorAffinity
from src.shared.database import get_session_context

logger = logging.getLogger(__name__)

# Neutro de referência para primeira computação
_NEUTRAL_SCORE = 0.5
# Delta máximo por execução (cap 10% da especificação)
_MAX_DELTA = 0.1


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _apply_cap(new_score: float, previous_score: Optional[float]) -> float:
    """Limita delta a 0.1 face ao anterior (ou 0.5 se primeira vez)."""
    base = previous_score if previous_score is not None else _NEUTRAL_SCORE
    delta = new_score - base
    if delta > _MAX_DELTA:
        new_score = base + _MAX_DELTA
    elif delta < -_MAX_DELTA:
        new_score = base - _MAX_DELTA
    return _clamp(new_score)


async def _phase_operator_affinity_job(tenant_id: UUID) -> None:
    """Calcula e persiste scores de afinidade operador/fase.

    Idempotente: cada execução recomputa todos os pares a partir do
    histórico e faz UPSERT — correr 2x produz o mesmo resultado.
    """

    started = datetime.now(timezone.utc)
    cutoff_iso = (started - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%S")
    now_iso = started.strftime("%Y-%m-%dT%H:%M:%S")

    try:
        async with get_session_context() as session:
            # ── 1. Agrega o histórico REAL (offp_eq ⋈ of_fp) dos últimos 90d ──
            # Operador = OFFPEQ_E_ID (conta toda a equipa). Conclusão =
            # OFFP_DATAFIM não-vazio. Defeito = OFFP_RETURN. Janela [cutoff, now]
            # — of_fp tem linhas com data FUTURA (planeadas) que não são histórico.
            stmt = text(
                """
                SELECT eq."OFFPEQ_E_ID"::text AS e_id,
                       o."OFFP_FP_ID"::text   AS phase_id,
                       COUNT(*)               AS total,
                       COUNT(NULLIF(o."OFFP_DATAFIM", '')) AS completed,
                       COUNT(*) FILTER (WHERE o."OFFP_RETURN") AS defects
                FROM factory_raw.offp_eq eq
                JOIN factory_raw.of_fp o ON o."OFFP_ID" = eq."OFFPEQ_OFFP_ID"
                WHERE eq."OFFPEQ_E_ID" IS NOT NULL
                  AND o."OFFP_FP_ID" IS NOT NULL
                  AND NULLIF(o."OFFP_DATAINICIO", '') IS NOT NULL
                  AND o."OFFP_DATAINICIO" >= :cutoff
                  AND o."OFFP_DATAINICIO" <= :now
                GROUP BY eq."OFFPEQ_E_ID", o."OFFP_FP_ID"
                """
            )
            rows = (
                await session.execute(stmt, {"cutoff": cutoff_iso, "now": now_iso})
            ).mappings().all()

            if not rows:
                logger.info(
                    "phase_operator_affinity_job: sem dados (90d) tenant=%s", tenant_id
                )
                return

            # ── 2. Resolve E_ID → core.employees.id (o id que get_fase_summary
            #       usa p/ resolver o nome). E_ID sem Employee → ignorado (sem
            #       linha fantasma; só falamos de operadores conhecidos).
            emp_rows = (
                await session.execute(
                    select(Employee.employee_code, Employee.id).where(
                        Employee.tenant_id == tenant_id
                    )
                )
            ).all()
            emp_id_by_code: Dict[str, UUID] = {str(c): i for c, i in emp_rows if c}

            # ── 3. Lê scores anteriores para aplicar o cap ───────────────
            prev_result = await session.execute(
                select(
                    PhaseOperatorAffinity.operator_id,
                    PhaseOperatorAffinity.phase_id,
                    PhaseOperatorAffinity.score,
                ).where(PhaseOperatorAffinity.tenant_id == tenant_id)
            )
            previous: Dict[Tuple[UUID, str], float] = {
                (r.operator_id, r.phase_id): r.score for r in prev_result.all()
            }

            # ── 4. Calcula scores e persiste via UPSERT ──────────────────
            now_ts = datetime.now(timezone.utc)
            upserted = 0
            no_employee = 0
            for row in rows:
                total = int(row["total"] or 0)
                if total == 0:
                    continue
                emp_id = emp_id_by_code.get(str(row["e_id"]))
                if emp_id is None:
                    no_employee += 1
                    continue
                phase_id = str(row["phase_id"])
                completed = int(row["completed"] or 0)
                defects = int(row["defects"] or 0)

                # Q.150 — taxa de conclusão penalizada pela taxa de defeito.
                win_rate = completed / total
                defect_rate = defects / total
                raw_score = _clamp(win_rate * (1.0 - defect_rate))
                final_score = _apply_cap(raw_score, previous.get((emp_id, phase_id)))

                await session.execute(
                    text(
                        """
                        INSERT INTO governance.phase_operator_affinity
                            (tenant_id, operator_id, phase_id, score, sample_count, last_computed_at)
                        VALUES
                            (:tid, :oid, :pid, :score, :cnt, :ts)
                        ON CONFLICT (tenant_id, operator_id, phase_id)
                        DO UPDATE SET
                            score = EXCLUDED.score,
                            sample_count = EXCLUDED.sample_count,
                            last_computed_at = EXCLUDED.last_computed_at
                        """
                    ),
                    {
                        "tid": tenant_id,
                        "oid": emp_id,
                        "pid": phase_id,
                        "score": final_score,
                        "cnt": total,
                        "ts": now_ts,
                    },
                )
                upserted += 1

            await session.commit()

        elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        logger.info(
            "phase_operator_affinity_job: tenant=%s pares=%s sem_employee=%s elapsed_ms=%s",
            tenant_id, upserted, no_employee, elapsed_ms,
        )

    except Exception as exc:
        logger.error(
            "phase_operator_affinity_job tenant=%s falhou: %s",
            tenant_id, exc, exc_info=True,
        )
