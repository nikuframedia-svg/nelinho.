"""
ProdPlan ONE — Defect Risk Prediction (Q.53.A)
================================================

Orchestrates the active `QualityRiskModel` over every in-progress
production order to answer the "Predições" tab on the Qualidade page:
"which kayaks are most likely to pick up a defect at their current phase?".

Pipeline
--------
1. Load the active `quality_risk` artifact via `registry_loader`. If none is
   active yet, `ensure_quality_risk_model` trains+promotes one from the DB
   history so the page bootstraps on first use.
2. Read the in-progress orders from `plan.production_orders` (legacy_id,
   product_type, current_phase_id/name).
3. Join the empirical per-fase rework rate from `quality.rework_entry` so
   the `phase_error_rate` feature is real, not a guess.
4. Score each order with `predict_proba_batch` and return a ranked list.

Honest degradation: when no model can be trained (empty history) the
endpoint returns ``model_available=false`` and an empty list — never a
fabricated probability.
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.ml.registry_loader import load_active_quality_risk_predictor
from src.ml.training_service import ensure_quality_risk_model

logger = logging.getLogger(__name__)

# P(defeito) bands for the UI badge.
RISK_BANDS: tuple[tuple[float, str], ...] = (
    (0.40, "alto"),
    (0.20, "medio"),
    (0.0, "baixo"),
)


def _risk_band(p: float) -> str:
    for threshold, label in RISK_BANDS:
        if p >= threshold:
            return label
    return "baixo"


class DefectRiskService:
    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def _phase_error_rates(self) -> dict[str, float]:
        """Empirical rework rate per fase id, used as the `phase_error_rate`
        feature. Rework events of a fase / phase executions of that fase.
        """
        rework = (
            await self.session.execute(
                text(
                    """
                    SELECT phase_id_causer AS phase, COUNT(*) AS n
                    FROM quality.rework_entry
                    WHERE tenant_id = :t AND phase_id_causer IS NOT NULL
                    GROUP BY phase_id_causer
                    """
                ),
                {"t": str(self.tenant_id)},
            )
        ).all()
        phases = (
            await self.session.execute(
                text(
                    """
                    SELECT fase_id, COUNT(*) AS n
                    FROM factory_curated.order_phase
                    WHERE is_quarantined = false
                    GROUP BY fase_id
                    """
                )
            )
        ).all()
        phase_counts = {str(fid): int(n or 0) for fid, n in phases}
        rates: dict[str, float] = {}
        for phase, n in rework:
            key = str(phase or "").strip()
            total = phase_counts.get(key, 0)
            if total:
                rates[key] = min(0.95, int(n or 0) / total)
        return rates

    async def defect_risk(self, *, top_n: int = 50) -> dict[str, Any]:
        # 1. Make sure a model is active (train on first use if needed).
        await ensure_quality_risk_model(self.session, self.tenant_id)
        predictor = await load_active_quality_risk_predictor(
            self.session, self.tenant_id
        )
        if predictor is None:
            logger.warning(
                "defect_risk: no active quality_risk model — degrading."
            )
            return {
                "model_available": False,
                "reason": "Sem modelo de risco activo — histórico de "
                          "qualidade insuficiente para treinar.",
                "orders": [],
            }

        # 2. In-progress orders.
        orders = (
            await self.session.execute(
                text(
                    """
                    SELECT legacy_id, product_name, product_type,
                           current_phase_id, current_phase_name
                    FROM plan.production_orders
                    WHERE tenant_id = :t
                      AND status NOT IN ('completed', 'done', 'cancelled')
                    ORDER BY legacy_id
                    """
                ),
                {"t": str(self.tenant_id)},
            )
        ).mappings().all()
        if not orders:
            return {"model_available": True, "orders": []}

        # 3. Real per-fase error rate + per-fase queue depth.
        error_rates = await self._phase_error_rates()
        queue = {
            str(fid): int(n or 0)
            for fid, n in (
                await self.session.execute(
                    text(
                        "SELECT current_phase_id, COUNT(*) "
                        "FROM plan.production_orders "
                        "WHERE tenant_id = :t AND current_phase_id IS NOT NULL "
                        "GROUP BY current_phase_id"
                    ),
                    {"t": str(self.tenant_id)},
                )
            ).all()
        }

        feature_rows: list[dict[str, Any]] = []
        for o in orders:
            fase = str(o["current_phase_id"] or "")
            feature_rows.append(
                {
                    "modelo_id": str(o["product_type"] or "desconhecido"),
                    "fase_id": fase,
                    "team_size": 1,
                    "mold_pocket_count": 1,
                    "phase_error_rate": round(error_rates.get(fase, 0.0), 4),
                    "queue_depth": queue.get(fase, 0),
                }
            )

        # 4. Score.
        try:
            probs = predictor(feature_rows)
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("defect_risk: predictor failed (%s) — degrading.", exc)
            return {
                "model_available": False,
                "reason": "Falha ao executar o modelo de risco.",
                "orders": [],
            }

        items: list[dict[str, Any]] = []
        for o, feats, p in zip(orders, feature_rows, probs):
            p = float(p)
            items.append(
                {
                    "of_id": str(o["legacy_id"]),
                    "product_name": o["product_name"],
                    "product_type": o["product_type"],
                    "current_phase_id": o["current_phase_id"],
                    "current_phase_name": o["current_phase_name"],
                    "defect_probability": round(p, 4),
                    "risk_band": _risk_band(p),
                    "features": feats,
                }
            )
        items.sort(key=lambda d: d["defect_probability"], reverse=True)

        return {
            "model_available": True,
            "total_orders": len(items),
            "high_risk_count": sum(1 for i in items if i["risk_band"] == "alto"),
            "orders": items[:top_n],
        }
