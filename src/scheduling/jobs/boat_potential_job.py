"""Q.115.X6.B — job diário: calcula score de potencialidade por barco.

Fonte: plan.fases_of_history + quality.rework_entry + profit.order_revenue (365 dias).
Destino: governance.boat_potential (UPSERT idempotente).

4 componentes normalizadas:
  1. margin_norm     — receita média por OF / p90 receita (precisa de profit.order_revenue)
  2. throughput_norm — ops concluídas / p90 concluídas
  3. low_defect_norm — 1 - (taxa de defeitos)
  4. lead_time_norm  — 1 - (duration_media_normalizada)

potential_score = mean(componentes) clamp [0,1]

Corre às 04:15 UTC, entre improve_adoption_signal (04:00) e audit_retention_purge (04:30).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Tuple
from uuid import UUID

from sqlalchemy import text

from src.governance.models.boat_potential import BoatPotential
from src.shared.database import get_session_context

logger = logging.getLogger(__name__)

_HISTORY_DAYS = 365


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _percentile_90(values: List[float]) -> float:
    """Percentil 90 simples sem dependências externas."""
    if not values:
        return 1.0
    sorted_vals = sorted(values)
    idx = int(len(sorted_vals) * 0.9)
    return sorted_vals[min(idx, len(sorted_vals) - 1)] or 1.0


async def _boat_potential_job(tenant_id: UUID) -> None:
    """Calcula e persiste scores de potencialidade por barco.

    Idempotente: cada execução recomputa todos os barcos a partir do
    histórico e faz UPSERT — correr 2x produz o mesmo resultado.
    """
    started = datetime.now(timezone.utc)
    cutoff = started - timedelta(days=_HISTORY_DAYS)

    try:
        async with get_session_context() as session:
            # ── 1. Throughput + lead_time por barco ──────────────────────────
            stmt_throughput = text(
                """
                SELECT
                    COALESCE(po.product_name, foh.of_id) AS boat_id,
                    COUNT(foh.fase_fim) AS concluidas,
                    AVG(EXTRACT(EPOCH FROM (foh.fase_fim - foh.fase_inicio))/60) AS avg_duration_min
                FROM plan.fases_of_history foh
                LEFT JOIN plan.production_orders po
                    ON po.tenant_id = foh.tenant_id
                    AND CAST(po.legacy_id AS TEXT) = foh.of_id
                WHERE
                    foh.tenant_id = :tid
                    AND foh.fase_inicio >= :cutoff
                    AND foh.fase_fim IS NOT NULL
                GROUP BY
                    COALESCE(po.product_name, foh.of_id)
                """
            )
            tp_result = await session.execute(
                stmt_throughput, {"tid": tenant_id, "cutoff": cutoff}
            )
            tp_rows = tp_result.all()

            if not tp_rows:
                logger.info(
                    "boat_potential_job: sem dados (365d) tenant=%s", tenant_id
                )
                return

            boat_throughput: Dict[str, int] = {}
            boat_avg_duration: Dict[str, float] = {}
            for r in tp_rows:
                if r.boat_id:
                    boat_throughput[r.boat_id] = int(r.concluidas or 0)
                    boat_avg_duration[r.boat_id] = float(r.avg_duration_min or 0)

            # ── 2. Defeitos por barco ────────────────────────────────────────
            stmt_defects = text(
                """
                SELECT
                    COALESCE(re.model_id, re.of_id) AS boat_id,
                    COUNT(*) AS defect_count
                FROM quality.rework_entry re
                WHERE
                    re.tenant_id = :tid
                    AND re.detected_at >= :cutoff
                GROUP BY
                    COALESCE(re.model_id, re.of_id)
                """
            )
            def_result = await session.execute(
                stmt_defects, {"tid": tenant_id, "cutoff": cutoff}
            )
            boat_defects: Dict[str, int] = {
                r.boat_id: int(r.defect_count)
                for r in def_result.all()
                if r.boat_id
            }

            # ── 3. Receita por barco (profit.order_revenue via of_id) ────────
            stmt_revenue = text(
                """
                SELECT
                    COALESCE(po.product_name, orv.order_id) AS boat_id,
                    SUM(orv.total_revenue_eur) AS total_eur,
                    COUNT(DISTINCT orv.order_id) AS num_orders
                FROM profit.order_revenue orv
                LEFT JOIN plan.production_orders po
                    ON po.tenant_id = :tid
                    AND CAST(po.legacy_id AS TEXT) = orv.order_id
                WHERE
                    orv.tenant_id = :tid
                GROUP BY
                    COALESCE(po.product_name, orv.order_id)
                """
            )
            rev_result = await session.execute(stmt_revenue, {"tid": tenant_id})
            boat_revenue_total: Dict[str, Decimal] = {}
            boat_revenue_per_order: Dict[str, float] = {}
            for r in rev_result.all():
                if r.boat_id:
                    boat_revenue_total[r.boat_id] = Decimal(str(r.total_eur or 0))
                    num_orders = int(r.num_orders or 1)
                    boat_revenue_per_order[r.boat_id] = float(r.total_eur or 0) / num_orders

            # ── 4. Normalização: percentil 90 como referência ────────────────
            all_tp = [float(v) for v in boat_throughput.values() if v > 0]
            all_dur = [float(v) for v in boat_avg_duration.values() if v > 0]
            all_rev = [float(v) for v in boat_revenue_per_order.values() if v > 0]

            p90_tp = _percentile_90(all_tp)
            p90_dur = _percentile_90(all_dur)
            p90_rev = _percentile_90(all_rev)

            # ── 5. Computa potential_score e persiste UPSERT ─────────────────
            now_ts = datetime.now(timezone.utc)
            all_boats = set(boat_throughput.keys())
            upserted = 0

            for boat_id in all_boats:
                tp_val = float(boat_throughput.get(boat_id, 0))
                dur_val = float(boat_avg_duration.get(boat_id, 0))
                defect_count = float(boat_defects.get(boat_id, 0))
                rev_val = float(boat_revenue_per_order.get(boat_id, 0))

                # Componente 1: margem normalizada
                margin_norm = _clamp(rev_val / p90_rev) if p90_rev > 0 else 0.5

                # Componente 2: throughput normalizado
                throughput_norm = _clamp(tp_val / p90_tp) if p90_tp > 0 else 0.5

                # Componente 3: low defect (quanto menos defeitos melhor)
                defect_rate = defect_count / max(tp_val, 1)
                low_defect_norm = _clamp(1.0 - defect_rate)

                # Componente 4: lead time curto (quanto menor a duração média melhor)
                lead_time_norm = _clamp(1.0 - (dur_val / p90_dur)) if p90_dur > 0 else 0.5

                potential_score = _clamp(
                    (margin_norm + throughput_norm + low_defect_norm + lead_time_norm) / 4.0
                )

                revenue_lifetime = boat_revenue_total.get(boat_id, Decimal("0"))

                await session.execute(
                    text(
                        """
                        INSERT INTO governance.boat_potential
                            (tenant_id, boat_id, potential_score, revenue_eur_lifetime, last_computed_at)
                        VALUES
                            (:tid, :bid, :score, :rev, :ts)
                        ON CONFLICT (tenant_id, boat_id)
                        DO UPDATE SET
                            potential_score = EXCLUDED.potential_score,
                            revenue_eur_lifetime = EXCLUDED.revenue_eur_lifetime,
                            last_computed_at = EXCLUDED.last_computed_at
                        """
                    ),
                    {
                        "tid": tenant_id,
                        "bid": boat_id,
                        "score": potential_score,
                        "rev": float(revenue_lifetime),
                        "ts": now_ts,
                    },
                )
                upserted += 1

            await session.commit()

        elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        logger.info(
            "boat_potential_job: tenant=%s barcos=%s elapsed_ms=%s",
            tenant_id, upserted, elapsed_ms,
        )

    except Exception as exc:
        logger.error(
            "boat_potential_job tenant=%s falhou: %s",
            tenant_id, exc, exc_info=True,
        )
