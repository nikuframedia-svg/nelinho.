"""Q.115.X6.A / Q.150.B — job diário: score de afinidade barco/fase (REAL).

Fonte: factory_raw.of_fp (Q.150). NÃO se usa plan.fases_of_history (vazio
neste deployment) nem quality.rework_entry. barco = product_name (via
plan.production_orders por OFFP_OF_ID); conclusão = OFFP_DATAFIM não-vazio;
defeito = OFFP_RETURN. Destino: governance.boat_phase_score (UPSERT idempotente).

Lógica: score = clamp(win_rate − peso_defeito × taxa_defeito), cap 10% face
ao anterior. Corre às 03:45 UTC, depois do phase_operator_affinity (03:30).
"""
from __future__ import annotations

import logging

from src.shared.coerce import clamp as _clamp
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, text

from src.governance.models.boat_phase_score import BoatPhaseScore
from src.shared.database import get_session_context

logger = logging.getLogger(__name__)

# Neutro de referência para primeira computação
_NEUTRAL_SCORE = 0.5
# Delta máximo por execução (cap 10% — padrão Q.93.1.G)
_MAX_DELTA = 0.1
# Peso do defeito na fórmula de score
_DEFECT_WEIGHT = 0.3


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
    cutoff_iso = (started - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%S")
    now_iso = started.strftime("%Y-%m-%dT%H:%M:%S")

    try:
        async with get_session_context() as session:
            # ── 1. Agrega (barco, fase) do histórico REAL (of_fp), 90d ───────
            # barco = product_name (via production_orders por OFFP_OF_ID).
            # conclusão = OFFP_DATAFIM não-vazio; defeito = OFFP_RETURN.
            # Janela [cutoff, now] — of_fp tem linhas planeadas (futuras).
            stmt = text(
                """
                SELECT COALESCE(po.product_name, o."OFFP_OF_ID"::text) AS boat_id,
                       o."OFFP_FP_ID"::text AS phase_id,
                       COUNT(*) AS total,
                       COUNT(NULLIF(o."OFFP_DATAFIM", '')) AS concluidas,
                       COUNT(*) FILTER (WHERE o."OFFP_RETURN") AS defects
                FROM factory_raw.of_fp o
                LEFT JOIN plan.production_orders po
                  ON po.tenant_id = :tid
                  AND CAST(po.legacy_id AS TEXT) = o."OFFP_OF_ID"::text
                WHERE NULLIF(o."OFFP_DATAINICIO", '') IS NOT NULL
                  AND o."OFFP_DATAINICIO" >= :cutoff
                  AND o."OFFP_DATAINICIO" <= :now
                  AND o."OFFP_FP_ID" IS NOT NULL
                GROUP BY COALESCE(po.product_name, o."OFFP_OF_ID"::text), o."OFFP_FP_ID"
                """
            )
            phase_rows = (
                await session.execute(
                    stmt, {"tid": tenant_id, "cutoff": cutoff_iso, "now": now_iso}
                )
            ).all()

            if not phase_rows:
                logger.info(
                    "boat_phase_score_job: sem dados (90d) tenant=%s", tenant_id
                )
                return

            # ── 2. Lê scores anteriores para aplicar o cap ──────────────────
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

            # ── 3. Calcula scores e persiste via UPSERT ──────────────────────
            now_ts = datetime.now(timezone.utc)
            upserted = 0
            for row in phase_rows:
                boat_id: str = row.boat_id
                phase_id: str = row.phase_id
                total: int = int(row.total or 0)
                concluidas: int = int(row.concluidas or 0)
                defect_count: int = int(row.defects or 0)

                if total == 0 or not boat_id or not phase_id:
                    continue

                # score bruto: taxa de conclusão penalizada por defeitos (OFFP_RETURN)
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
