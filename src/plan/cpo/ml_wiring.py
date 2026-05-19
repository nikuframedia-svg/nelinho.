"""
ProdPlan ONE — CPO ML Wiring (Sprint Q.54.F)
=============================================

Single chokepoint that loads the active ML models from the registry and
attaches them to the CPO inputs.

Before Q.54.F the wiring was duplicated and partial: `src/plan/api/cpo.py`
loaded the Duration + QualityRisk predictors inline, but `poetiq.py` (the
copilot's POETIQ scheduling path) loaded neither — so a schedule proposed
through the copilot used 2× buffer templates and a zero quality-risk
term, while the same schedule through `/v1/plan/cpo/schedule` used the
trained models. Same factory, two different planners.

`apply_ml_to_cpo()` fixes that: every CPO entry-point calls it, the
models are loaded once, and the wiring is identical everywhere. The ML
is no longer an *optional extra* a caller may forget — it's the default
path. The honest fallback is preserved: when no model is active in the
registry (fresh tenant, retrain never ran), the predictor is simply
`None` and the resolver/fitness behave exactly as before (history /
standard templates). Nothing crashes; the difference is observable via
the returned `MLWiringReport`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class MLWiringReport:
    """What actually got wired this run — surfaced on `cpo_meta` so the
    API caller / E2E tests can assert the predictors were live."""

    duration_model_used: bool = False
    quality_risk_predictor_used: bool = False

    def as_meta(self) -> dict[str, bool]:
        return {
            "duration_model_used": self.duration_model_used,
            "quality_risk_predictor_used": self.quality_risk_predictor_used,
        }


async def load_duration_predictor(
    session: AsyncSession, tenant_id: UUID,
) -> Optional[Any]:
    """Load the active DurationModel, or None. Thin re-export so callers
    only import from one place."""
    from src.ml.registry_loader import load_active_duration_predictor
    return await load_active_duration_predictor(session, tenant_id)


async def apply_ml_to_cpo(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    fitness_config: Any,
) -> tuple[Optional[Any], MLWiringReport]:
    """Load the active ML models and wire them into the CPO inputs.

    Returns ``(duration_predictor, report)``:

    * ``duration_predictor`` — pass straight to ``RoutingResolver(state,
      duration_predictor=...)`` so phase durations come from the trained
      DurationModel's p50 instead of the legacy ``horas_standard * 2.0``.
    * ``fitness_config`` is mutated in place: when an active
      QualityRiskModel exists, ``fitness_config.quality_risk_predictor``
      is set so the GA's 0.10-weighted quality-risk term goes live.

    Both loads are best-effort. A registry outage or a fresh tenant
    yields ``None`` and the report reflects it — never raises.
    """
    from src.ml.registry_loader import (
        load_active_quality_risk_predictor,
    )

    report = MLWiringReport()

    # ── Duration model → RoutingResolver ──────────────────────────────
    duration_predictor: Optional[Any] = None
    try:
        duration_predictor = await load_duration_predictor(session, tenant_id)
    except Exception as exc:  # pragma: no cover — registry_loader is defensive
        logger.warning("apply_ml_to_cpo: duration load failed (%s)", exc)
    if duration_predictor is not None:
        report.duration_model_used = True
        logger.info(
            "CPO ML wiring: DurationModel active — wired into RoutingResolver"
        )

    # ── QualityRisk model → fitness ───────────────────────────────────
    try:
        quality_risk_predictor = await load_active_quality_risk_predictor(
            session, tenant_id,
        )
    except Exception as exc:  # pragma: no cover — registry_loader is defensive
        logger.warning("apply_ml_to_cpo: quality_risk load failed (%s)", exc)
        quality_risk_predictor = None
    if quality_risk_predictor is not None and fitness_config is not None:
        fitness_config.quality_risk_predictor = quality_risk_predictor
        report.quality_risk_predictor_used = True
        logger.info(
            "CPO ML wiring: QualityRiskModel active — predictor wired into fitness"
        )

    return duration_predictor, report
