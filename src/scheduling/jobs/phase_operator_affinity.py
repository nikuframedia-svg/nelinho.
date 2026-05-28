"""Q.115.G — job diário: calcula afinidade operador/fase a partir do histórico real.

Fonte: plan.fases_of_history (FaseOf_Inicio→FaseOf_Fim, 90 dias).
Destino: governance.phase_operator_affinity (UPSERT idempotente).

Cap 10%: score não pode alterar mais de 0.1 face ao valor anterior
(ou face a 0.5 neutro se for primeira vez). Garante estabilidade
face a picos de amostras.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, select, text

from src.governance.models.phase_operator_affinity import PhaseOperatorAffinity
from src.plan.models.fases_of_history import FasesOfHistory
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
    cutoff = started - timedelta(days=90)

    try:
        async with get_session_context() as session:
            # ── 1. Agrega histórico dos últimos 90 dias ──────────────────
            # Uma linha é "concluída" quando fase_fim IS NOT NULL.
            # worker_id e phase_id não nulos são obrigatórios.
            stmt = (
                select(
                    FasesOfHistory.worker_id,
                    FasesOfHistory.phase_id,
                    func.count().label("total"),
                    func.count(FasesOfHistory.fase_fim).label("concluidas"),
                )
                .where(
                    FasesOfHistory.tenant_id == tenant_id,
                    FasesOfHistory.fase_inicio >= cutoff,
                    FasesOfHistory.worker_id.is_not(None),
                    FasesOfHistory.phase_id.is_not(None),
                )
                .group_by(FasesOfHistory.worker_id, FasesOfHistory.phase_id)
            )
            result = await session.execute(stmt)
            rows = result.all()

            if not rows:
                logger.info(
                    "phase_operator_affinity_job: sem dados (90d) tenant=%s", tenant_id
                )
                return

            # ── 2. Lê scores anteriores para aplicar o cap ───────────────
            stmt_prev = select(
                PhaseOperatorAffinity.operator_id,
                PhaseOperatorAffinity.phase_id,
                PhaseOperatorAffinity.score,
            ).where(PhaseOperatorAffinity.tenant_id == tenant_id)
            prev_result = await session.execute(stmt_prev)
            previous: Dict[Tuple[UUID, str], float] = {
                (r.operator_id, r.phase_id): r.score
                for r in prev_result.all()
            }

            # ── 3. Calcula scores e persiste via UPSERT ──────────────────
            now_ts = datetime.now(timezone.utc)
            upserted = 0
            for row in rows:
                worker_id: UUID = row.worker_id
                phase_id: str = row.phase_id
                total: int = row.total
                concluidas: int = row.concluidas

                if total == 0:
                    continue

                win_rate = concluidas / total
                # quality_factor: não temos quality_score em fases_of_history → 1.0
                quality_factor = 1.0
                raw_score = _clamp(win_rate * quality_factor)

                prev = previous.get((worker_id, phase_id))
                final_score = _apply_cap(raw_score, prev)

                # UPSERT via INSERT ... ON CONFLICT DO UPDATE
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
                        "oid": worker_id,
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
            "phase_operator_affinity_job: tenant=%s pares=%s elapsed_ms=%s",
            tenant_id, upserted, elapsed_ms,
        )

    except Exception as exc:
        logger.error(
            "phase_operator_affinity_job tenant=%s falhou: %s",
            tenant_id, exc, exc_info=True,
        )
