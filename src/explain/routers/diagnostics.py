"""Q.66.D.4c — Diagnostics sub-router (extracted from `src.explain.api`).

Hosts the operator-facing diagnostic endpoints:

* ``POST /v1/explain/diagnostics/investigate`` — ERRO-TREE cascade
* ``POST /v1/explain/diagnostics/common-cause`` — Reichenbach
* ``POST /v1/explain/diagnostics/what-changed`` — Mill's method

Detectors (ErroTreeDetector, ReichenbachDetector, MillDiffDetector)
are lazy-imported inside the handlers — same pattern the
characterization tests patch.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session

get_tenant_id = require_tenant_header

router = APIRouter(prefix="/v1/explain", tags=["Explainability"])


# ═══════════════════════════════════════════════════════════════════════════
# DIAGNOSTICS — ERRO-TREE (Sprint Q.15.D.1)
# ═══════════════════════════════════════════════════════════════════════════
#
# Operator-facing endpoint for the ERRO-TREE handler. The frontend or
# the LLM (via tool-calling, capability `diagnostics.erro_tree.enabled`)
# POSTs the trigger + period + optional phase_id; the handler runs the
# 3-detector cascade (mold → worker → overload) and returns either a
# root_cause hypothesis or a "no isolated cause" verdict.
#
# Audit + push: the @record_rule_firing decorator on `investigate()`
# persists every call to governance.rule_firing (Q.14.A) and triggers
# pg_notify push to the SSE channel (Q.14.B) when the allowlist matches.


class DiagnosticsInvestigateRequest(BaseModel):
    """Body for `POST /v1/explain/diagnostics/investigate`."""

    trigger: str = Field(
        ...,
        description=(
            "What symptom prompted the investigation. "
            "Allowed: quality_drop / throughput_drop / delay_spike."
        ),
    )
    period_days: int = Field(
        default=7, ge=1, le=90,
        description="Lookback window. Default 7 — captures weekly drift.",
    )
    phase_id: Optional[str] = Field(
        default=None,
        description="Optional — restrict to a single phase.",
    )
    conversation_id: Optional[UUID] = Field(
        default=None,
        description=(
            "Sprint Q.15.D.5 — when supplied AND a hypothesis trips, "
            "the handler emits a verified CausalChain into the "
            "Camada-4 ABL pipeline (CopilotMessage.content_structured. "
            "causal_audit). Frontend passes the active conversation; "
            "scheduler-driven calls leave this null and chain emission "
            "is skipped (rule_firing audit still happens via Q.14.A)."
        ),
    )


@router.post("/diagnostics/investigate")
async def investigate_diagnostics(
    payload: DiagnosticsInvestigateRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_session),
):
    """Run the ERRO-TREE diagnostic cascade.

    Sprint Q.15.D.1 — replaces LLM improvisation with a real handler
    that reads governance.rule_firing-audited evidence + emits a
    `Hypothesis` with Beta-Bernoulli confidence + 95% CI.
    """
    from src.explain.diagnostics.erro_tree import ErroTreeDetector
    from src.explain.diagnostics.types import TriggerType

    try:
        trigger = TriggerType(payload.trigger)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid trigger '{payload.trigger}'. "
                f"Allowed: {[t.value for t in TriggerType]}"
            ),
        )

    detector = ErroTreeDetector(session=db, tenant_id=tenant_id)
    result = await detector.investigate(
        trigger=trigger,
        period_days=payload.period_days,
        phase_id=payload.phase_id,
        conversation_id=payload.conversation_id,
    )

    body: Dict[str, Any] = {
        "root_cause": None,
        "chain": result.chain,
        "steps_checked": result.steps_checked,
        "recommendation": result.recommendation,
    }
    if result.root_cause is not None:
        h = result.root_cause
        ci_low, ci_high = h.credible_interval(level=0.95)
        body["root_cause"] = {
            "type": h.type,
            "entity": h.entity,
            "confidence": round(h.confidence, 4),
            "credible_interval_95": {
                "low": round(ci_low, 4),
                "high": round(ci_high, 4),
            },
            "evidence": list(h.evidence),
        }
    return body


# ═══════════════════════════════════════════════════════════════════════════
# DIAGNOSTICS — Reichenbach (Sprint Q.15.D.2)
# ═══════════════════════════════════════════════════════════════════════════
#
# When 2+ phases drift simultaneously, the LLM (or the
# MultivariatePhaseMonitor scheduler hook) calls this endpoint instead
# of asking ERRO-TREE per phase. Reichenbach finds the shared resource
# (mold / workers / cascade) and returns a list of common-cause
# Hypothesis objects. When no common cause is found, falls back to
# per-phase ERRO-TREE results (verdict = "independent").


class CommonCauseRequest(BaseModel):
    """Body for `POST /v1/explain/diagnostics/common-cause`."""

    deviating_phases: List[str] = Field(
        ..., min_length=2,
        description=(
            "Phase ids that show simultaneous drift in the same window. "
            "The MultivariatePhaseMonitor produces this list on its 30-min "
            "schedule; the LLM may also pass it directly via tool-call."
        ),
    )
    period_days: int = Field(
        default=7, ge=1, le=90,
        description="Lookback window for the common-cause search.",
    )
    conversation_id: Optional[UUID] = Field(
        default=None,
        description=(
            "Sprint Q.15.D.5 — when supplied AND a common cause trips, "
            "emit a verified CausalChain into the Camada-4 ABL pipeline."
        ),
    )


def _serialise_hypothesis(h) -> Dict[str, Any]:
    """Convert a Hypothesis into the JSON shape the frontend renders."""
    ci_low, ci_high = h.credible_interval(level=0.95)
    return {
        "type": h.type,
        "entity": h.entity,
        "confidence": round(h.confidence, 4),
        "credible_interval_95": {
            "low": round(ci_low, 4),
            "high": round(ci_high, 4),
        },
        "evidence": list(h.evidence),
    }


@router.post("/diagnostics/common-cause")
async def common_cause(
    payload: CommonCauseRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_session),
):
    """Reichenbach common-cause analysis.

    Returns:
        ``{"verdict": "common_cause"|"independent"|"inconclusive",
           "common_causes": [Hypothesis, ...],
           "independent_causes": [Hypothesis, ...],
           "checks_run": [...]}``

    - ``common_cause`` → at least one shared-resource hypothesis tripped.
    - ``independent`` → no shared cause found; per-phase ERRO-TREE
      hypotheses are in `independent_causes` instead.
    - ``inconclusive`` → input had < 2 phases or no detectors produced anything.
    """
    from src.explain.diagnostics.reichenbach import ReichenbachDetector

    detector = ReichenbachDetector(session=db, tenant_id=tenant_id)
    result = await detector.find_common_cause(
        deviating_phases=payload.deviating_phases,
        period_days=payload.period_days,
        conversation_id=payload.conversation_id,
    )
    return {
        "verdict": result.verdict,
        "common_causes": [_serialise_hypothesis(h) for h in result.common_causes],
        "independent_causes": [
            _serialise_hypothesis(h) for h in result.independent_causes
        ],
        "checks_run": result.checks_run,
    }


# ═══════════════════════════════════════════════════════════════════════════
# DIAGNOSTICS — Mill's method (Sprint Q.15.D.4)
# ═══════════════════════════════════════════════════════════════════════════
#
# *"O que mudou entre antes e agora?"* — compare a "good" period with
# a "bad" period, rank what's different by Cohen's d correlation, and
# return a list of candidate causes ordered by likelihood.


class WhatChangedRequest(BaseModel):
    """Body for `POST /v1/explain/diagnostics/what-changed`."""

    good_period_start: date = Field(..., description="ISO date — start of 'before' (inclusive)")
    good_period_end: date = Field(..., description="ISO date — end of 'before' (exclusive)")
    bad_period_start: date = Field(..., description="ISO date — start of 'after' (inclusive)")
    bad_period_end: date = Field(..., description="ISO date — end of 'after' (exclusive)")
    metric: str = Field(
        default="error_rate",
        description="Metric to compare. Today: 'error_rate' (only)."
    )
    phase_id: Optional[str] = Field(
        default=None,
        description="Optional — restrict the comparison to one phase.",
    )
    likely_threshold: float = Field(
        default=0.7, ge=0.5, le=0.95,
        description=(
            "Correlation cutoff for `likely_cause=True`. 0.7 ≈ Cohen's "
            "'large' effect; lower it to surface weaker signals."
        ),
    )
    conversation_id: Optional[UUID] = Field(
        default=None,
        description=(
            "Sprint Q.15.D.5 — when supplied AND a likely_cause Change "
            "is found, emit a verified CausalChain into the Camada-4 "
            "ABL pipeline."
        ),
    )


@router.post("/diagnostics/what-changed")
async def what_changed(
    payload: WhatChangedRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_session),
):
    """Mill's method of difference — what changed between 2 periods.

    Sprint Q.15.D.4 — closes §10.4 of the v2.2 prompt. Returns:
      ``metric_comparison``: actual delta + Cohen's d on daily samples.
      ``changes_found``: list of {category, change, correlation,
        likely_cause, evidence}, ranked by correlation desc.
      ``unchanged``: dimensions whose data isn't there or the shift is
        below the noise floor.
      ``verdict``: one-liner naming the strongest likely_cause.
    """
    from src.explain.diagnostics.mill_diff import MillDiffDetector

    if payload.bad_period_end <= payload.good_period_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="bad_period must come after good_period.",
        )

    detector = MillDiffDetector(session=db, tenant_id=tenant_id)
    report = await detector.what_changed(
        good_start=payload.good_period_start,
        good_end=payload.good_period_end,
        bad_start=payload.bad_period_start,
        bad_end=payload.bad_period_end,
        metric=payload.metric,
        phase_id=payload.phase_id,
        likely_threshold=payload.likely_threshold,
        conversation_id=payload.conversation_id,
    )
    return report.to_dict()
