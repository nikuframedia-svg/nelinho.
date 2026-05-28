"""
ProdPlan ONE — Defect Risk Prediction (Q.53.A / Q.115.E)
=========================================================

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

Q.115.E — preview_for_combination: P(defeito) para uma combinação
(operator_id, phase_id, boat_id) com similar_pairs e risk_factors.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.ml.registry_loader import load_active_quality_risk_predictor
from src.ml.training_service import ensure_quality_risk_model

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Q.115.E — Response models
# ---------------------------------------------------------------------------

class SimilarPair(BaseModel):
    operator_id: str
    operator_name: str
    phase_id: str
    phase_name: str
    historical_defect_rate: float
    sample_n: int


class RiskFactor(BaseModel):
    feature: str
    contribution: float  # signed; positive = aumenta risco
    description_pt: str


class QualityRiskPreview(BaseModel):
    operator_id: str | None
    phase_id: str | None
    boat_id: str | None  # NULL — Q.115.A.07 deferred (migration 018 não em main)
    p_defect: float
    historical_count: int
    similar_pairs: list[SimilarPair]
    top_risk_factors: list[RiskFactor]
    confidence: Literal["high", "medium", "low"]
    computed_at: datetime


# Mapeamento PT-PT para features do modelo
_FEATURE_DESCRIPTIONS_PT: dict[str, str] = {
    "modelo_id": "Tipo de barco (modelo)",
    "fase_id": "Fase de produção",
    "team_size": "Tamanho da equipa na fase",
    "mold_pocket_count": "Número de cavidades do molde",
    "phase_error_rate": "Taxa histórica de erro nesta fase",
    "queue_depth": "Volume de trabalho na fila desta fase",
}


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

    # ------------------------------------------------------------------
    # Q.115.E — preview_for_combination
    # ------------------------------------------------------------------

    async def preview_for_combination(
        self,
        operator_id: str | None = None,
        phase_id: str | None = None,
        boat_id: str | None = None,
        # TODO(Q.115.A.07): boat_id ignorado até migration 018 chegar a main
        # (quality.rework_entry.boat_id deferred). Quando migration 018 for
        # mergeada, activar filtragem por boat_id na query historical_count.
    ) -> QualityRiskPreview:
        """P(defeito) para uma combinação (operator, phase, boat).

        1. Carrega QualityRiskModel activo. Se não existe, usa taxa empírica.
        2. Constrói feature vector com valores médios/defaults razoáveis.
        3. Conta historical_count em quality.rework_entry para operator+phase.
        4. Top-3 similar_pairs por (operator_id, phase_id) com mais amostras.
        5. top_risk_factors via feature_importances_ × feature_value (SHAP-lite).
        6. Confidence: low se <20, medium se 20-100, high se >100.
        """
        # 1 — historical count + similar pairs via rework_entry
        # boat_id deferred (Q.115.A.07) — agrega só por operator+phase
        historical_count, similar_pairs = await self._historical_stats(
            operator_id=operator_id,
            phase_id=phase_id,
        )

        # 2 — decide confidence
        if historical_count < 20:
            confidence: Literal["high", "medium", "low"] = "low"
        elif historical_count <= 100:
            confidence = "medium"
        else:
            confidence = "high"

        # 3 — error rates para feature
        error_rates = await self._phase_error_rates()
        fase_key = str(phase_id or "")
        phase_error_rate = round(error_rates.get(fase_key, 0.0), 4)

        # 4 — feature vector
        feature_row = {
            "modelo_id": str(boat_id or "desconhecido"),
            "fase_id": fase_key,
            "team_size": 1,
            "mold_pocket_count": 1,
            "phase_error_rate": phase_error_rate,
            "queue_depth": historical_count,
        }

        # 5 — predict
        p_defect, risk_factors = await self._predict_with_factors(
            feature_row=feature_row,
            confidence=confidence,
        )

        return QualityRiskPreview(
            operator_id=operator_id,
            phase_id=phase_id,
            boat_id=None,  # Q.115.A.07 deferred — migration 018 não em main
            p_defect=round(p_defect, 4),
            historical_count=historical_count,
            similar_pairs=similar_pairs,
            top_risk_factors=risk_factors,
            confidence=confidence,
            computed_at=datetime.now(timezone.utc),
        )

    async def _historical_stats(
        self,
        operator_id: str | None,
        phase_id: str | None,
    ) -> tuple[int, list[SimilarPair]]:
        """Conta rework_entry para (operator, phase) e devolve top-3 pairs."""
        # Tenta contar na tabela quality.rework_entry.
        # Se a tabela não existir (migration 018 deferred), devolve zeros.
        try:
            filters: list[str] = ["tenant_id = :t"]
            params: dict[str, Any] = {"t": str(self.tenant_id)}
            if operator_id:
                filters.append("causer_employee_id::text = :op")
                params["op"] = operator_id
            if phase_id:
                filters.append("phase_id_causer = :ph")
                params["ph"] = phase_id

            where = " AND ".join(filters)
            count_row = (
                await self.session.execute(
                    text(f"SELECT COUNT(*) FROM quality.rework_entry WHERE {where}"),
                    params,
                )
            ).scalar()
            historical_count = int(count_row or 0)

            # Top-3 similar pairs: operadores × fases com mais amostras
            pair_rows = (
                await self.session.execute(
                    text(
                        """
                        SELECT
                            COALESCE(causer_employee_id::text, 'desconhecido') AS op_id,
                            COALESCE(phase_id_causer, 'desconhecida') AS ph_id,
                            COUNT(*) AS total,
                            COALESCE(
                                SUM(CASE WHEN resolved_at IS NULL THEN 1 ELSE 0 END),
                                0
                            ) AS unresolved
                        FROM quality.rework_entry
                        WHERE tenant_id = :t
                        GROUP BY causer_employee_id, phase_id_causer
                        ORDER BY total DESC
                        LIMIT 3
                        """
                    ),
                    {"t": str(self.tenant_id)},
                )
            ).all()

            similar_pairs = [
                SimilarPair(
                    operator_id=str(row[0]),
                    operator_name=str(row[0]),  # sem join HR — usa ID como nome
                    phase_id=str(row[1]),
                    phase_name=str(row[1]),
                    historical_defect_rate=round(
                        float(row[3]) / max(float(row[2]), 1), 4
                    ),
                    sample_n=int(row[2]),
                )
                for row in pair_rows
            ]
        except Exception as exc:
            err_str = str(exc).lower()
            if any(
                m in err_str
                for m in ("does not exist", "undefinedtable", "no such table", "relation")
            ):
                logger.warning(
                    "quality.rework_entry indisponível (migration 018 deferred): %s", exc
                )
                return 0, []
            raise

        return historical_count, similar_pairs

    async def _predict_with_factors(
        self,
        feature_row: dict[str, Any],
        confidence: Literal["high", "medium", "low"],
    ) -> tuple[float, list[RiskFactor]]:
        """Tenta predict_proba via modelo activo; fallback por phase_error_rate."""
        from src.ml.models_domain.quality_risk import NUMERIC_COLS

        try:
            await ensure_quality_risk_model(self.session, self.tenant_id)
            predictor = await load_active_quality_risk_predictor(
                self.session, self.tenant_id
            )
        except Exception as exc:
            logger.warning("preview_for_combination: falha ao carregar modelo: %s", exc)
            predictor = None

        if predictor is None:
            # Fallback: usa phase_error_rate como proxy
            p_defect = float(feature_row.get("phase_error_rate", 0.0))
            risk_factors = [
                RiskFactor(
                    feature="phase_error_rate",
                    contribution=p_defect,
                    description_pt=_FEATURE_DESCRIPTIONS_PT["phase_error_rate"],
                )
            ]
            return p_defect, risk_factors

        try:
            p_defect = float(predictor([feature_row])[0])
        except Exception as exc:
            logger.warning("preview_for_combination: predictor falhou: %s", exc)
            p_defect = float(feature_row.get("phase_error_rate", 0.0))

        # SHAP-lite: feature_importances_ × feature_value (sinalizado)
        risk_factors = _compute_risk_factors(predictor, feature_row)
        return p_defect, risk_factors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compute_risk_factors(
    predictor: Any,
    feature_row: dict[str, Any],
) -> list[RiskFactor]:
    """SHAP-lite: top-3 features com maior contribuição local.

    Contribuição = feature_importances_[i] × feature_value (sinalizado).
    O predictor expõe o classificador via atributo `_model` ou directamente.
    Se feature_importances_ não estiver acessível, devolve lista vazia.
    """
    from src.ml.models_domain.quality_risk import CATEGORICAL_COLS, NUMERIC_COLS

    clf = getattr(predictor, "_model", None) or getattr(predictor, "classifier", None)
    # predictor é um callable wrapping QualityRiskModel — tenta navegar
    if clf is None:
        inner = getattr(predictor, "__self__", None)
        if inner is not None:
            clf = getattr(inner, "classifier", None)

    if clf is None or not hasattr(clf, "feature_importances_"):
        return []

    importances = clf.feature_importances_
    # feature order: categoricals (one-hot) + numerics
    # Usa NUMERIC_COLS para contribuições numéricas (mais interpretável)
    numeric_contribs: list[tuple[str, float]] = []
    n_features = len(importances)
    # As últimas len(NUMERIC_COLS) posições correspondem às features numéricas
    n_num = len(NUMERIC_COLS)
    if n_features >= n_num:
        for i, col in enumerate(NUMERIC_COLS):
            feat_val = float(feature_row.get(col, 0.0))
            imp = float(importances[n_features - n_num + i])
            contribution = imp * feat_val
            numeric_contribs.append((col, contribution))

    # Ordena por abs(contribution) DESC, top-3
    numeric_contribs.sort(key=lambda x: abs(x[1]), reverse=True)
    return [
        RiskFactor(
            feature=col,
            contribution=round(contrib, 4),
            description_pt=_FEATURE_DESCRIPTIONS_PT.get(col, col),
        )
        for col, contrib in numeric_contribs[:3]
    ]
