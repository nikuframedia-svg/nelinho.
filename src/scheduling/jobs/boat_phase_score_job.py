"""Q.115.X6.A — job diário: calcula score de afinidade barco/fase.

Fonte: plan.fases_of_history (90 dias) + quality.rework_entry (90 dias).
Destino: governance.boat_phase_score (UPSERT idempotente).

Lógica:
    score = (concluidas - peso_defeito * defect_count) / sample_count
    normalizado [0,1] e com cap 10% face ao valor anterior.

Corre às 03:45 UTC, depois do phase_operator_affinity (03:30).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, select, text

from src.governance.models.boat_phase_score import BoatPhaseScore
from src.plan.models.fases_of_history import FasesOfHistory
from src.quality.models.rework import ReworkEntry
from src.shared.database import get_session_context

logger = logging.getLogger(__name__)

# Neutro de referência para primeira computação
_NEUTRAL_SCORE = 0.5
# Delta máximo por execução (cap 10% — padrão Q.93.1.G)
_MAX_DELTA = 0.1
# Peso do defeito na fórmula de score
_DEFECT_WEIGHT = 0.3


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _apply_cap(new_score: float, previous_score: Optional[float]) -> float:
    """Limita delta a 0.1 face ao anterior (ou 0.5 neutro se primeira vez)."""
    base = previous_score if previous_score is not None else _NEUTRAL_SCORE
    delta = new_score - base
    if delta > _MAX_DELTA:
        new_score = base + _MAX_DELTA
    elif delta < -_MAX_DELTA:
        new_score = base - _MAX_DELTA
    return _clamp(new_score)


async def _boat_phase_score_job(tenant_id: UUID) -> None:
    """Calcula e persiste scores de afinidade barco/fase.

    Idempotente: cada execução recomputa todos os pares a partir do
    histórico e faz UPSERT — correr 2x produz o mesmo resultado.

    boat_id é derivado de FasesOfHistory via join com plan.production_orders
    (product_name como identificador do barco). Quando product_name não existe
    para um of_id, o par é ignorado.
    """
    started = datetime.now(timezone.utc)
    cutoff = started - timedelta(days=90)

    try:
        async with get_session_context() as session:
            # ── 1. Agrega throughput por (boat, phase) via join ──────────────
            # Join fases_of_history → production_orders para obter product_name
            # como boat_id. Uma linha conta quando fase_fim IS NOT NULL.
            stmt = text(
                """
                SELECT
                    COALESCE(po.product_name, foh.of_id) AS boat_id,
                    foh.phase_id,
                    COUNT(*) AS total,
                    COUNT(foh.fase_fim) AS concluidas
                FROM plan.fases_of_history foh
                LEFT JOIN plan.production_orders po
                    ON po.tenant_id = foh.tenant_id
                    AND CAST(po.legacy_id AS TEXT) = foh.of_id
                WHERE
                    foh.tenant_id = :tid
                    AND foh.fase_inicio >= :cutoff
                    AND foh.phase_id IS NOT NULL
                GROUP BY
                    COALESCE(po.product_name, foh.of_id),
                    foh.phase_id
                """
            )
            result = await session.execute(stmt, {"tid": tenant_id, "cutoff": cutoff})
            phase_rows = result.all()

            if not phase_rows:
                logger.info(
                    "boat_phase_score_job: sem dados (90d) tenant=%s", tenant_id
                )
                return

            # ── 2. Agrega defeitos por (boat, phase) ────────────────────────
            stmt_defects = text(
                """
                SELECT
                    COALESCE(re.model_id, re.of_id) AS boat_id,
                    re.phase_id_causer AS phase_id,
                    COUNT(*) AS defect_count
                FROM quality.rework_entry re
                WHERE
                    re.tenant_id = :tid
                    AND re.detected_at >= :cutoff
                    AND re.phase_id_causer IS NOT NULL
                GROUP BY
                    COALESCE(re.model_id, re.of_id),
                    re.phase_id_causer
                """
            )
            def_result = await session.execute(
                stmt_defects, {"tid": tenant_id, "cutoff": cutoff}
            )
            defect_map: Dict[Tuple[str, str], int] = {
                (r.boat_id, r.phase_id): r.defect_count
                for r in def_result.all()
                if r.boat_id and r.phase_id
            }

            # ── 3. Lê scores anteriores para aplicar o cap ──────────────────
            prev_stmt = select(
                BoatPhaseScore.boat_id,
                BoatPhaseScore.phase_id,
                BoatPhaseScore.score,
            ).where(BoatPhaseScore.tenant_id == tenant_id)
            prev_result = await session.execute(prev_stmt)
            previous: Dict[Tuple[str, str], float] = {
                (r.boat_id, r.phase_id): r.score
                for r in prev_result.all()
            }

            # ── 4. Calcula scores e persiste via UPSERT ──────────────────────
            now_ts = datetime.now(timezone.utc)
            upserted = 0
            for row in phase_rows:
                boat_id: str = row.boat_id
                phase_id: str = row.phase_id
                total: int = row.total
                concluidas: int = row.concluidas

                if total == 0 or not boat_id or not phase_id:
                    continue

                defect_count = defect_map.get((boat_id, phase_id), 0)
                # score bruto: taxa de conclusão penalizada por defeitos
                win_rate = concluidas / total
                penalty = _DEFECT_WEIGHT * (defect_count / total)
                raw_score = _clamp(win_rate - penalty)

                prev = previous.get((boat_id, phase_id))
                final_score = _apply_cap(raw_score, prev)

                await session.execute(
                    text(
                        """
                        INSERT INTO governance.boat_phase_score
                            (tenant_id, boat_id, phase_id, score, sample_count, last_computed_at)
                        VALUES
                            (:tid, :bid, :pid, :score, :cnt, :ts)
                        ON CONFLICT (tenant_id, boat_id, phase_id)
                        DO UPDATE SET
                            score = EXCLUDED.score,
                            sample_count = EXCLUDED.sample_count,
                            last_computed_at = EXCLUDED.last_computed_at
                        """
                    ),
                    {
                        "tid": tenant_id,
                        "bid": boat_id,
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
            "boat_phase_score_job: tenant=%s pares=%s elapsed_ms=%s",
            tenant_id, upserted, elapsed_ms,
        )

    except Exception as exc:
        logger.error(
            "boat_phase_score_job tenant=%s falhou: %s",
            tenant_id, exc, exc_info=True,
        )
