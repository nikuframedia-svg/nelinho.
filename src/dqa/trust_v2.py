"""
ProdPlan ONE - Trust Index v2.0 (Sprint AA.1)
==============================================

Blueprint v2.0 §4.5 Trust Index — 7+1 components, scope-based. Coexists with
the legacy shape-based `TrustIndexCalculator` in `trust_index.py` (which
evaluates incoming request payloads, not production data).

Difference vs legacy:

| Aspect             | legacy `trust_index.py`        | this module (`trust_v2.py`)        |
|--------------------|--------------------------------|------------------------------------|
| Inputs             | a request dict + declared spec | factory/order/phase DB state       |
| Components         | 4 (C, V, Consistency, Timeliness) | 7+1 (C, V, F, K, P, A, E, CC)   |
| Weight source      | hardcoded (0.30/0.30/0.20/0.20) | TenantConfig (cat="trust")        |
| Caller             | QualityGateMiddleware          | CPO engine, decoder, ScheduleCommit |

The 8th component (CC — Causal Coherence) is reserved (`causal_coherence: Optional`)
and excluded from the composite until Sprint future. Weights always sum to 1.0;
if the admin edits a single weight into an unnormalised state, the calculator
normalises defensively (with a warning log) rather than returning a biased score.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# Scope names (Blueprint v2.0 §4.5 — factory/order/phase)
SCOPE_FACTORY = "factory"
SCOPE_ORDER = "order"
SCOPE_PHASE = "phase"
ALLOWED_SCOPES = frozenset({SCOPE_FACTORY, SCOPE_ORDER, SCOPE_PHASE})


# Provenance tiers (Blueprint v2.0 §4.5: sensor > historian > ERP > manual)
PROVENANCE_TIER_SCORES: dict[str, float] = {
    "sensor": 1.00,
    "historian": 0.85,
    "erp": 0.70,
    "manual": 0.50,
}


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TrustWeights:
    """Blueprint v2.0 §4.5 default weights. Sum must equal 1.0."""

    completeness: float = 0.15
    validity: float = 0.20
    freshness: float = 0.15
    consistency: float = 0.20
    provenance: float = 0.15
    anomaly: float = 0.10
    evidence: float = 0.05

    def as_dict(self) -> dict[str, float]:
        return {
            "completeness": self.completeness,
            "validity": self.validity,
            "freshness": self.freshness,
            "consistency": self.consistency,
            "provenance": self.provenance,
            "anomaly": self.anomaly,
            "evidence": self.evidence,
        }

    def total(self) -> float:
        return sum(self.as_dict().values())

    def normalised(self) -> "TrustWeights":
        """Return a rescaled copy whose weights sum to 1.0."""
        s = self.total()
        if s <= 0:
            raise ValueError("TrustWeights total must be > 0")
        return TrustWeights(**{k: v / s for k, v in self.as_dict().items()})


@dataclass
class TrustComponents:
    """Per-component scores in [0, 1]. `causal_coherence` is the 8th component,
    optional; it is NOT weighted in the composite until the blueprint assigns a
    weight to it."""

    completeness: float = 1.0
    validity: float = 1.0
    freshness: float = 1.0
    consistency: float = 1.0
    provenance: float = 1.0
    anomaly: float = 1.0
    evidence: float = 1.0
    causal_coherence: Optional[float] = None  # 8th — future

    def as_dict(self, include_legacy_keys: bool = False) -> dict[str, Optional[float]]:
        base: dict[str, Optional[float]] = {
            "completeness": self.completeness,
            "validity": self.validity,
            "freshness": self.freshness,
            "consistency": self.consistency,
            "provenance": self.provenance,
            "anomaly": self.anomaly,
            "evidence": self.evidence,
            "causal_coherence": self.causal_coherence,
        }
        if include_legacy_keys:
            # The old 4-component API emitted {completeness, validity, consistency, timeliness}.
            # We keep `completeness`/`validity`/`consistency` as-is and map
            # `timeliness <- freshness` so old dashboards still read something
            # sensible.
            base["timeliness"] = self.freshness
        return base

    def composite(self, weights: TrustWeights) -> float:
        """Weighted sum over the 7 weighted components. CC is excluded."""
        w = weights.as_dict()
        return sum(w[k] * getattr(self, k) for k in w)


@dataclass
class TrustSignals:
    """Raw inputs that the individual component scorers consume."""

    # completeness
    total_required: int = 0
    missing: int = 0
    # validity
    total_validated: int = 0
    invalid: int = 0
    # freshness
    age_seconds: Optional[float] = None
    tau_seconds: Optional[float] = None
    # consistency
    z_scores: list[float] = field(default_factory=list)
    kappa: float = 2.0
    # provenance
    provenance_tier: str = "erp"
    # anomaly
    anomaly_probability: float = 0.0
    # evidence
    verifiable: Optional[bool] = None


@dataclass
class TrustIndexResult:
    scope: str
    scope_id: Optional[UUID]
    components: TrustComponents
    weights: TrustWeights
    composite: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "scope_id": str(self.scope_id) if self.scope_id else None,
            "composite": round(self.composite, 4),
            "components": {
                k: (round(v, 4) if isinstance(v, float) else v)
                for k, v in self.components.as_dict().items()
            },
            "weights": self.weights.as_dict(),
        }


# ---------------------------------------------------------------------------
# Per-component scorers — pure functions, unit-testable
# ---------------------------------------------------------------------------

def score_completeness(total_required: int, missing: int) -> float:
    if total_required <= 0:
        return 1.0
    filled = max(0, total_required - missing)
    return _clamp(filled / total_required)


def score_validity(total_validated: int, invalid: int) -> float:
    if total_validated <= 0:
        return 1.0
    return _clamp(1.0 - invalid / total_validated)


def score_freshness(age_seconds: Optional[float], tau_seconds: Optional[float]) -> float:
    """Blueprint v2.0 §4.5: F = exp(-age / tau)."""
    if age_seconds is None or tau_seconds is None:
        return 1.0
    if age_seconds < 0:
        return 1.0
    if tau_seconds <= 0:
        return 1.0
    return _clamp(math.exp(-age_seconds / tau_seconds))


def score_consistency(z_scores: list[float], kappa: float = 2.0) -> float:
    """Blueprint v2.0 §4.5: K = exp(-|z| / kappa), averaged when multiple z-scores."""
    if not z_scores:
        return 1.0
    if kappa <= 0:
        return 1.0
    per = [math.exp(-abs(z) / kappa) for z in z_scores]
    return _clamp(sum(per) / len(per))


def score_provenance(tier: str) -> float:
    return PROVENANCE_TIER_SCORES.get((tier or "").lower(), 0.50)


def score_anomaly(prob: float) -> float:
    return _clamp(1.0 - prob)


def score_evidence(verifiable: Optional[bool]) -> float:
    if verifiable is None:
        return 1.0
    return 1.0 if verifiable else 0.0


def components_from_signals(signals: TrustSignals) -> TrustComponents:
    return TrustComponents(
        completeness=score_completeness(signals.total_required, signals.missing),
        validity=score_validity(signals.total_validated, signals.invalid),
        freshness=score_freshness(signals.age_seconds, signals.tau_seconds),
        consistency=score_consistency(signals.z_scores, signals.kappa),
        provenance=score_provenance(signals.provenance_tier),
        anomaly=score_anomaly(signals.anomaly_probability),
        evidence=score_evidence(signals.verifiable),
    )


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


# ---------------------------------------------------------------------------
# Calculator (v2.0, scope-based)
# ---------------------------------------------------------------------------

SignalsProviderResult = Union[TrustSignals, TrustComponents]
SignalsProvider = Callable[
    [AsyncSession, UUID, str, Optional[UUID]],
    Awaitable[SignalsProviderResult],
]


class TrustIndexV2Calculator:
    """Blueprint v2.0 §4.5 — scope-based Trust Index computer.

    Two ways to drive it:
    1. Pass a `signals`/`components` kwarg to `compute_for_scope()` — simplest,
       used by tests and by caller-side code that already has DQ summaries.
    2. Inject a `signals_provider` at construction — the provider is invoked
       lazily with `(session, tenant_id, scope, scope_id)` and returns either
       `TrustSignals` or `TrustComponents`. The concrete provider for
       factory/order/phase lives in Sprint AA.3.
    """

    def __init__(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        signals_provider: Optional[SignalsProvider] = None,
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self._signals_provider = signals_provider

    async def load_weights(self) -> TrustWeights:
        """Read weights from TenantConfigService. Falls back to defaults on any
        error (missing seeder, DB down, etc.) — we never fail a computation
        because config is slow/unavailable."""
        try:
            # Lazy import avoids a circular dependency during module import;
            # `src.core.services.tenant_config_service` imports from shared infra
            # that in turn may want dqa helpers.
            from src.core.services.tenant_config_service import TenantConfigService

            cfg = TenantConfigService(self.session, self.tenant_id)
            values = await cfg.get_category("trust")
            weights = TrustWeights(
                completeness=float(values.get("weights.completeness", 0.15)),
                validity=float(values.get("weights.validity", 0.20)),
                freshness=float(values.get("weights.freshness", 0.15)),
                consistency=float(values.get("weights.consistency", 0.20)),
                provenance=float(values.get("weights.provenance", 0.15)),
                anomaly=float(values.get("weights.anomaly", 0.10)),
                evidence=float(values.get("weights.evidence", 0.05)),
            )
        except Exception as exc:  # pragma: no cover — defensive
            # Onda 2.1 — keep this loud. Defaults silently being used means
            # the tenant's customised weights aren't applied; ops needs to
            # know via logs even when the calculation itself succeeds.
            logger.error(
                "TrustWeights load failed for tenant=%s, using defaults: %s",
                self.tenant_id, exc, exc_info=True,
            )
            return TrustWeights()

        if abs(weights.total() - 1.0) > 1e-6:
            logger.warning(
                "TrustWeights total=%.4f != 1.0; normalising",
                weights.total(),
            )
            weights = weights.normalised()
        return weights

    async def compute_for_scope(
        self,
        scope: str,
        scope_id: Optional[UUID] = None,
        *,
        signals: Optional[TrustSignals] = None,
        components: Optional[TrustComponents] = None,
    ) -> TrustIndexResult:
        """Produce a `TrustIndexResult` for (scope, scope_id).

        Resolution order for components:
        1. explicit `components` kwarg
        2. explicit `signals` kwarg → `components_from_signals()`
        3. `self._signals_provider(...)` — may return signals or components
        4. optimistic default (`TrustComponents()` — all 1.0) — used mostly in
           tests that only want to validate the composite arithmetic
        """
        if scope not in ALLOWED_SCOPES:
            raise ValueError(
                f"Unknown scope '{scope}'; allowed: {sorted(ALLOWED_SCOPES)}"
            )

        weights = await self.load_weights()

        if components is None:
            if signals is None and self._signals_provider is not None:
                raw = await self._signals_provider(
                    self.session, self.tenant_id, scope, scope_id
                )
                if isinstance(raw, TrustComponents):
                    components = raw
                elif isinstance(raw, TrustSignals):
                    signals = raw
                else:
                    raise TypeError(
                        "signals_provider must return TrustSignals or TrustComponents; "
                        f"got {type(raw).__name__}"
                    )
            if components is None:
                # Onda 1.3 — surface the silent "no inputs" case. Without
                # signals, signals_provider, or explicit components the
                # composite collapses to 1.0 (TrustSignals defaults), which
                # masks empty/broken data. Callers that legitimately want
                # the optimistic default should pass `signals=TrustSignals()`
                # explicitly so this warning doesn't fire.
                if signals is None and self._signals_provider is None:
                    logger.warning(
                        "TrustIndexV2: scope=%s scope_id=%s computed without "
                        "signals/provider — composite will be 1.0 (default)",
                        scope, scope_id,
                    )
                components = components_from_signals(signals or TrustSignals())

        composite = components.composite(weights)
        return TrustIndexResult(
            scope=scope,
            scope_id=scope_id,
            components=components,
            weights=weights,
            composite=composite,
        )
