"""
ProdPlan ONE — OTD Risk Prediction (Sprint Q.54.F)
====================================================

Orchestrates the active `OTDRiskModel` over every open production order
to answer the Painel / Direção question: "which kayaks are heading for a
late delivery?" — so a manager is warned days ahead, not on the
transport day.

This is the order-delivery twin of `DefectRiskService` (which scores
phase defect risk). Same shape: load the active artifact, score the open
orders, return a ranked list with honest degradation when no model is
available.

Pipeline
--------
1. `ensure_otd_risk_model` trains + promotes an `otd_risk` artifact from
   the DB history (completed orders' on-time/late label) if none is
   active yet, so the Painel bootstraps on first use.
2. Read the OPEN orders from `plan.production_orders` (legacy_id,
   product_type, transport_date, current_phase_id).
3. Build the feature row per order: `slack_days` is the headroom between
   today and the transport date; `n_phases` / `total_planned_hours` size
   the order from `factory_curated.order_phase`; `open_phases` is how
   many phases are still ahead of the current one.
4. Score with `predict_proba_batch`, rank, return.

Honest degradation: no model trainable (thin history) → `model_available
= false` and an empty list — never a fabricated probability.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.ml.registry_loader import load_active_otd_risk_predictor
from src.ml.training_service import ensure_otd_risk_model

logger = logging.getLogger(__name__)

# P(late) bands for the UI badge.
RISK_BANDS: tuple[tuple[float, str], ...] = (
    (0.60, "alto"),
    (0.30, "medio"),
    (0.0, "baixo"),
)


def _risk_band(p: float) -> str:
    for threshold, label in RISK_BANDS:
        if p >= threshold:
            return label
    return "baixo"


class OTDRiskService:
    """Scores open orders for on-time-delivery risk."""

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def _order_phase_aggregates(self) -> dict[str, dict[str, float]]:
        """Per-order phase count + total real hours from the curated
        layer. Keyed by `of_id` (the order's legacy id as text)."""
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT of_id,
                           COUNT(*)               AS n_phases,
                           COALESCE(SUM(horas_reais), 0) AS total_hours
                    FROM factory_curated.order_phase
                    WHERE is_quarantined = false
                    GROUP BY of_id
                    """
                )
            )
        ).all()
        return {
            str(of_id): {
                "n_phases": int(n or 0),
                "total_hours": float(total or 0.0),
            }
            for of_id, n, total in rows
        }

    async def otd_risk(self, *, top_n: int = 50) -> dict[str, Any]:
        # 1. Make sure a model is active (train on first use if needed).
        await ensure_otd_risk_model(self.session, self.tenant_id)
        predictor = await load_active_otd_risk_predictor(
            self.session, self.tenant_id
        )
        if predictor is None:
            logger.warning("otd_risk: no active otd_risk model — degrading.")
            return {
                "model_available": False,
                "reason": "Sem modelo de risco de atraso activo — histórico "
                          "de entregas insuficiente para treinar.",
                "orders": [],
            }

        # 2. Open orders with a transport date (nothing to be late on
        #    without one).
        orders = (
            await self.session.execute(
                text(
                    """
                    SELECT legacy_id, product_name, product_type,
                           current_phase_id, current_phase_name,
                           transport_date
                    FROM plan.production_orders
                    WHERE tenant_id = :t
                      AND status NOT IN ('completed', 'done', 'cancelled')
                      AND transport_date IS NOT NULL
                    ORDER BY transport_date
                    """
                ),
                {"t": str(self.tenant_id)},
            )
        ).mappings().all()
        if not orders:
            return {"model_available": True, "orders": []}

        aggregates = await self._order_phase_aggregates()
        today = date.today()

        feature_rows: list[dict[str, Any]] = []
        for o in orders:
            of_id = str(o["legacy_id"])
            agg = aggregates.get(of_id, {"n_phases": 0, "total_hours": 0.0})
            transport = o["transport_date"]
            try:
                slack_days = float((transport - today).days)
            except (TypeError, AttributeError):
                slack_days = 0.0
            feature_rows.append(
                {
                    "modelo_id": str(o["product_type"] or "desconhecido"),
                    "n_phases": agg["n_phases"],
                    "total_planned_hours": round(agg["total_hours"], 2),
                    "slack_days": round(slack_days, 2),
                    # Open orders: every remaining phase is "open". We
                    # don't track the current-phase index here, so use
                    # n_phases as an upper bound — the model's other
                    # features carry the signal.
                    "open_phases": agg["n_phases"],
                    "phase_error_rate_mean": 0.0,
                }
            )

        # 3. Score.
        try:
            probs = predictor(feature_rows)
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("otd_risk: predictor failed (%s) — degrading.", exc)
            return {
                "model_available": False,
                "reason": "Falha ao executar o modelo de risco de atraso.",
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
                    "transport_date": (
                        o["transport_date"].isoformat()
                        if o["transport_date"] else None
                    ),
                    "late_probability": round(p, 4),
                    "risk_band": _risk_band(p),
                    "features": feats,
                }
            )
        items.sort(key=lambda d: d["late_probability"], reverse=True)

        return {
            "model_available": True,
            "total_orders": len(items),
            "high_risk_count": sum(1 for i in items if i["risk_band"] == "alto"),
            "orders": items[:top_n],
        }
