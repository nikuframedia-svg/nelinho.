"""
ProdPlan ONE — Adaptive Fitness Weights (Sprint D.4, Camada 2)
===============================================================

**Layer 2 of the learning stack**: the GA's cost weights adjust themselves
to the operator's observed preferences.

Camada 1 (PreferenceRuleDetector) surfaces explicit rules ("never Laminagem
on Fridays"). This layer is different — it learns *relative importances*
from the stream of rejected alternatives that pile up inside each
`ScheduleCommit.rejected_alternatives`.

How it works
------------
Every commit holds the chosen plan plus a list of near-miss alternatives,
each carrying ``delta_vs_chosen = {kpi: rejected_kpi - chosen_kpi, ...}``.
Across a rolling window we have hundreds of such pairs. For every pair
we know *which side the operator picked*, so we can fit a pairwise
logistic regression:

* **Feature** — ``chosen_kpi - rejected_kpi`` (= ``-delta_vs_chosen``).
* **Label** — 1 when this direction is the chosen one, 0 when flipped.
  Flipping the sign of every pair gives a perfectly balanced dataset.
* **Standardisation** — each KPI lives on a different scale (tardiness
  in hours, setups in counts). We z-score before LR so the coefficient
  magnitudes are comparable.
* **Coefficient → weight multiplier** — ``m = exp(-coef)`` clamped to
  ``[0.5, 2.0]``. A negative coefficient (operator prefers *lower* K)
  pushes the weight up; a positive one pushes it down.
* **Blend** — the learned multiplier is applied to the domain default
  with ``w_new = 0.70 × w_learned + 0.30 × w_default``. Even with a
  strong learned signal the default keeps a 30 % anchor so we don't
  drift to an absurd regime on a lucky streak.

Why pairwise and not per-pair ranking
-------------------------------------
The raw data only has "rejected was worse" events — no chosen-vs-chosen
comparisons. Duplicating every pair with a flipped sign encodes the
preference symmetrically and turns it into a standard binary
classification that sklearn can fit. The coefficients interpret exactly
as "how strongly does the operator care about this KPI's direction".

Guardrails
----------
* < ``MIN_PAIRS`` pairs → bail early, keep defaults. Noise is worse
  than no adaptation.
* Weights are persisted via ``TenantConfigService`` so every retrain
  is history-preserving and auditable (Sprint C audit trail).
* ``CPOConfig`` / ``FitnessConfig`` read through a factory that falls
  back to hardcoded defaults if the tenant never trained.

Designed to run weekly (Sundays 02:00 UTC) — see
``_preference_weights_retrain_job`` in ``src/shared/scheduler.py``.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

import numpy as np
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.cpo.commits import ScheduleCommit

logger = logging.getLogger(__name__)


# ─── Public config ──────────────────────────────────────────────────────

# Map FitnessConfig legacy scalar weights → the key we expect in
# `delta_vs_chosen`. Only these four participate in adaptation; v2.0
# normalised weights and penalties stay fixed.
ADAPTIVE_KPI_KEYS: Dict[str, str] = {
    "w_makespan": "makespan_hours",
    "w_tardiness": "total_tardiness_hours",
    "w_setups": "setups",
    "w_quality_risk": "quality_risk_score",
}

# Domain defaults — MUST match `FitnessConfig` so a tenant that never
# trained gets identical behaviour to one that hasn't opted in.
DEFAULT_WEIGHTS: Dict[str, float] = {
    "w_makespan": 1.0,
    "w_tardiness": 10.0,
    "w_setups": 0.5,
    "w_quality_risk": 0.10,
}

DEFAULT_MIN_PAIRS = 50
DEFAULT_WINDOW_DAYS = 30
BLEND_LEARNED_PCT = 0.70
MULTIPLIER_MIN = 0.5
MULTIPLIER_MAX = 2.0

TENANT_CONFIG_CATEGORY = "governance"
TENANT_CONFIG_KEY = "adaptive_fitness_weights"


@dataclass
class RetrainResult:
    """Outcome of a single retrain pass — persisted alongside the weights."""

    status: str                  # "trained", "skipped", "error"
    reason: Optional[str]        # human-readable skip/error explanation
    commits_scanned: int
    pairs_used: int
    weights: Dict[str, float]    # the blended weights actually in effect
    raw_learned: Dict[str, float]  # pre-blend, for audit
    coefficients: Dict[str, float]  # z-scored LR coefs per KPI
    # Sprint R.2 — Camada 1↔2 cross-check. Each entry describes a
    # contradiction between a confirmed PreferenceRule (Camada 1) and
    # the freshly-trained weights (Camada 2). Doesn't block retrain;
    # surfaces in the R.1 dashboard so a human can decide which side
    # is right.
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    # Sprint R.4 — one-line PT explanation per KPI ("Peso de Tardiness
    # subiu 12% — categoria dominante: CUSTOMER (84 pares)"). Rendered
    # by templates so the audit trail is reproducible. Empty when the
    # retrain was skipped.
    explanations: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "commits_scanned": self.commits_scanned,
            "pairs_used": self.pairs_used,
            "weights": self.weights,
            "raw_learned": self.raw_learned,
            "coefficients": self.coefficients,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "min_pairs": DEFAULT_MIN_PAIRS,
            "blend_learned_pct": BLEND_LEARNED_PCT,
            "warnings": list(self.warnings),
            "explanations": list(self.explanations),
        }


# ─── Retainer ────────────────────────────────────────────────────────────


class AdaptiveFitnessWeights:
    """Fit + persist adaptive weights for a tenant.

    Usage::

        retainer = AdaptiveFitnessWeights(session, tenant_id)
        result = await retainer.retrain(window_days=30)
        # result.weights is already persisted via TenantConfigService;
        # also returned so the cron job can log the summary.
    """

    def __init__(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        *,
        min_pairs: int = DEFAULT_MIN_PAIRS,
        blend_learned_pct: float = BLEND_LEARNED_PCT,
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.min_pairs = min_pairs
        self.blend_learned_pct = blend_learned_pct

    # ─── Public entry ──────────────────────────────────────────────────

    async def retrain(
        self,
        window_days: int = DEFAULT_WINDOW_DAYS,
    ) -> RetrainResult:
        commits = await self._fetch_commits_with_rejections(window_days)
        pairs = self._collect_delta_pairs(commits)

        if len(pairs) < self.min_pairs:
            logger.info(
                "adaptive_fitness_weights: insufficient data for tenant %s "
                "(%d pairs < %d) — keeping defaults",
                self.tenant_id, len(pairs), self.min_pairs,
            )
            return RetrainResult(
                status="skipped",
                reason=f"insufficient_data ({len(pairs)} pairs < {self.min_pairs})",
                commits_scanned=len(commits),
                pairs_used=len(pairs),
                weights=dict(DEFAULT_WEIGHTS),
                raw_learned={},
                coefficients={},
            )

        coefs = self._fit_logistic(pairs)
        raw_learned = self._coefs_to_weights(coefs)
        blended = self._blend(raw_learned)

        # Sprint R.2 — Camada 1↔2 contradiction check. Best effort: a
        # failure to load rules must NOT break the retrain (the weights
        # are already valid). Warnings are advisory.
        warnings: List[Dict[str, Any]] = []
        try:
            confirmed_rules = await self._fetch_confirmed_tradeoff_rules()
            warnings = detect_weight_rule_contradictions(
                blended_weights=blended, confirmed_rules=confirmed_rules,
            )
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning(
                "adaptive_fitness_weights: contradiction check failed for "
                "tenant %s (%s) — proceeding without warnings",
                self.tenant_id, exc,
            )

        # Sprint R.4 — Camada 2 explainability. Renders one PT-text
        # explanation per KPI from previous-vs-current weight + which
        # rejection category dominated this window. Best effort.
        explanations: List[Dict[str, Any]] = []
        try:
            from src.governance.preference_learning.retrain_explanation import (
                build_retrain_explanations,
            )

            previous_weights = await self._load_previous_weights()
            by_category = self._collect_rejection_categories(commits)
            built = build_retrain_explanations(
                current_weights=blended,
                previous_weights=previous_weights,
                pairs_used=len(pairs),
                by_category=by_category,
            )
            explanations = [e.to_dict() for e in built]
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning(
                "adaptive_fitness_weights: explanation build failed for "
                "tenant %s (%s) — proceeding without explanations",
                self.tenant_id, exc,
            )

        result = RetrainResult(
            status="trained",
            reason=None,
            commits_scanned=len(commits),
            pairs_used=len(pairs),
            weights=blended,
            raw_learned=raw_learned,
            coefficients=coefs,
            warnings=warnings,
            explanations=explanations,
        )

        await self._persist(result)
        logger.info(
            "adaptive_fitness_weights: tenant=%s commits=%d pairs=%d "
            "weights=%s warnings=%d",
            self.tenant_id, len(commits), len(pairs), blended, len(warnings),
        )
        return result

    async def _load_previous_weights(self) -> Optional[Dict[str, float]]:
        """Read the prior persisted weights (if any) for delta calculation.

        Returns ``None`` on the very first retrain — the caller treats
        that as "no prior signal" and reports zero delta against
        defaults. Any read failure is swallowed (retrain must not break
        because the explanation read got noisy).
        """
        from src.core.services.tenant_config_service import TenantConfigService

        try:
            svc = TenantConfigService(self.session, self.tenant_id)
            payload = await svc.get(
                TENANT_CONFIG_CATEGORY,
                TENANT_CONFIG_KEY,
                default=None,
            )
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug(
                "adaptive_fitness_weights: previous weights read failed (%s)", exc,
            )
            return None
        if not isinstance(payload, dict):
            return None
        weights = payload.get("weights")
        if not isinstance(weights, dict):
            return None
        return {k: float(v) for k, v in weights.items() if isinstance(v, (int, float))}

    @staticmethod
    def _collect_rejection_categories(
        commits: List[ScheduleCommit],
    ) -> Dict[str, int]:
        """Count rejection categories across the window.

        Walks ``user_preference_signal.rejection_category`` first
        (set by the cpo decide endpoint when a category was provided)
        and then per-alternative categories where the commit didn't
        carry one at the top level.
        """
        from collections import Counter

        counts: Counter = Counter()
        for commit in commits:
            rejected = commit.rejected_alternatives or []
            if not rejected:
                continue
            signal = commit.user_preference_signal or {}
            top_category = (
                signal.get("rejection_category")
                if isinstance(signal, dict) else None
            )
            if isinstance(top_category, str) and top_category:
                counts[top_category] += len(rejected)
                continue
            for alt in rejected:
                if isinstance(alt, dict):
                    cat = alt.get("rejection_category")
                    if isinstance(cat, str) and cat:
                        counts[cat] += 1
        return dict(counts)

    async def _fetch_confirmed_tradeoff_rules(self) -> List[Any]:
        """Return CONFIRMED PreferenceRule rows of TRADEOFF type for this tenant.

        Imported lazily so the read side (`load_adaptive_weights`) keeps
        a small module surface and so unit tests can monkey-patch the
        models module without dragging the rule layer in.
        """
        from src.governance.models import (
            PreferenceRule,
            PreferenceRuleStatus,
            PreferenceRuleType,
        )

        stmt = select(PreferenceRule).where(
            and_(
                PreferenceRule.tenant_id == self.tenant_id,
                PreferenceRule.status == PreferenceRuleStatus.CONFIRMED.value,
                PreferenceRule.type == PreferenceRuleType.TRADEOFF_PREFERENCE.value,
            )
        )
        return list((await self.session.execute(stmt)).scalars().all())

    # ─── Data access ───────────────────────────────────────────────────

    async def _fetch_commits_with_rejections(
        self, window_days: int,
    ) -> List[ScheduleCommit]:
        since = datetime.now(timezone.utc) - timedelta(days=window_days)
        stmt = (
            select(ScheduleCommit)
            .where(
                and_(
                    ScheduleCommit.tenant_id == self.tenant_id,
                    ScheduleCommit.created_at >= since,
                )
            )
            .order_by(ScheduleCommit.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return [
            c for c in result.scalars().all()
            if (c.rejected_alternatives or [])
        ]

    # ─── Feature extraction ────────────────────────────────────────────

    def _collect_delta_pairs(
        self, commits: List[ScheduleCommit],
    ) -> List[Dict[str, float]]:
        """Flatten every rejected alternative's `delta_vs_chosen` into a
        list of feature dicts keyed by our ADAPTIVE_KPI_KEYS mapping.

        Missing KPIs default to 0.0 (indifferent). Non-numeric entries
        are dropped so one malformed commit doesn't poison the fit.
        """
        pairs: List[Dict[str, float]] = []
        for commit in commits:
            for alt in commit.rejected_alternatives or []:
                delta = alt.get("delta_vs_chosen") if isinstance(alt, dict) else None
                if not isinstance(delta, dict):
                    continue
                row: Dict[str, float] = {}
                for weight_key, kpi_key in ADAPTIVE_KPI_KEYS.items():
                    value = delta.get(kpi_key, 0.0)
                    if isinstance(value, (int, float)) and not math.isnan(float(value)):
                        row[weight_key] = float(value)
                    else:
                        row[weight_key] = 0.0
                pairs.append(row)
        return pairs

    # ─── Model fit ─────────────────────────────────────────────────────

    def _fit_logistic(
        self, pairs: List[Dict[str, float]],
    ) -> Dict[str, float]:
        """Build the balanced pairwise dataset and fit a LogisticRegression.

        Returns ``{weight_key: standardised_coefficient}``. A negative
        coefficient means "operator prefers lower values of this KPI" —
        which for cost-style KPIs (tardiness, setups) is the expected
        direction.
        """
        # sklearn is a hard dep declared in requirements.txt; import here
        # keeps the module import cost of `preference_learning` cheap for
        # callers that never retrain (most request paths).
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler

        keys = list(ADAPTIVE_KPI_KEYS.keys())
        deltas = np.array(
            [[p.get(k, 0.0) for k in keys] for p in pairs],
            dtype=float,
        )

        # Pairwise: for every rejected alternative we know which side
        # won. `chosen - rejected = -delta` is the "winning" direction
        # (label 1); the flipped sign is the losing direction (label 0).
        chosen_minus_rejected = -deltas
        rejected_minus_chosen = +deltas
        x_raw = np.concatenate([chosen_minus_rejected, rejected_minus_chosen], axis=0)
        y = np.concatenate([np.ones(len(deltas)), np.zeros(len(deltas))])

        # Standardise so weights trained on tardiness-hours don't drown
        # out weights on setups-count.
        scaler = StandardScaler()
        x_scaled = scaler.fit_transform(x_raw)
        # Guard against a constant column (operator never saw variation
        # on that KPI in this window): StandardScaler leaves it as 0s,
        # which LR tolerates — coefficient will simply come out as 0.

        model = LogisticRegression(
            fit_intercept=False,
            max_iter=500,
            solver="lbfgs",
        )
        model.fit(x_scaled, y)
        coefs = model.coef_[0]
        return {k: float(c) for k, c in zip(keys, coefs)}

    # ─── Coef → weight → blend ─────────────────────────────────────────

    def _coefs_to_weights(self, coefs: Dict[str, float]) -> Dict[str, float]:
        """Turn each coefficient into a pre-blend weight.

        `coef < 0` → operator prefers lower K → raise weight
        `coef > 0` → operator tolerates higher K → lower weight
        Clamp the multiplier to `[MULTIPLIER_MIN, MULTIPLIER_MAX]` so
        a single noisy window can't flip the GA upside-down.
        """
        weights: Dict[str, float] = {}
        for key, coef in coefs.items():
            default = DEFAULT_WEIGHTS[key]
            multiplier = math.exp(-coef)
            multiplier = max(MULTIPLIER_MIN, min(MULTIPLIER_MAX, multiplier))
            weights[key] = default * multiplier
        return weights

    def _blend(self, learned: Dict[str, float]) -> Dict[str, float]:
        """`w_new = blend * w_learned + (1 - blend) * w_default` per key."""
        blend = self.blend_learned_pct
        return {
            key: blend * learned.get(key, DEFAULT_WEIGHTS[key])
            + (1.0 - blend) * DEFAULT_WEIGHTS[key]
            for key in DEFAULT_WEIGHTS
        }

    # ─── Persistence ───────────────────────────────────────────────────

    async def _persist(self, result: RetrainResult) -> None:
        """Store under ``governance.adaptive_fitness_weights``. The Tenant
        Config service records history so we can diff weights across
        training runs.
        """
        from src.core.services.tenant_config_service import TenantConfigService

        svc = TenantConfigService(self.session, self.tenant_id)
        await svc.set(
            category=TENANT_CONFIG_CATEGORY,
            key=TENANT_CONFIG_KEY,
            value=result.to_dict(),
            user_id=None,
            data_type="json",
        )


# ─── Sprint R.2 — Camada 1↔2 contradiction detector ─────────────────────


# Maps a confirmed-rule "prefer/sacrifice" KPI to the adaptive weight
# the GA uses for that KPI. If a rule says "prefer low setups" and the
# learned multiplier on `w_setups` came out below 1.0, we flag it.
_PREFER_KPI_TO_WEIGHT_KEY: Dict[str, str] = {
    "makespan_hours": "w_makespan",
    "total_tardiness_hours": "w_tardiness",
    "setups": "w_setups",
    "quality_risk_score": "w_quality_risk",
}


def detect_weight_rule_contradictions(
    *,
    blended_weights: Dict[str, float],
    confirmed_rules: List[Any],
) -> List[Dict[str, Any]]:
    """Return advisory warnings where blended weights contradict
    CONFIRMED ``TRADEOFF_PREFERENCE`` rules.

    A confirmed rule of the form ``{prefer: setups, sacrifice: ...}``
    encodes "operator wants low setups". The corresponding fitness
    weight ``w_setups`` should therefore be at-or-above its default.
    If the freshly-blended weight is below default, the two layers
    disagree — surface a warning so the human can pick a winner.
    """
    warnings: List[Dict[str, Any]] = []
    for rule in confirmed_rules:
        predicate = getattr(rule, "predicate", None) or {}
        prefer = predicate.get("prefer")
        if not isinstance(prefer, str):
            continue
        weight_key = _PREFER_KPI_TO_WEIGHT_KEY.get(prefer)
        if not weight_key or weight_key not in DEFAULT_WEIGHTS:
            continue
        default = DEFAULT_WEIGHTS[weight_key]
        actual = blended_weights.get(weight_key)
        if not isinstance(actual, (int, float)) or default == 0:
            continue
        ratio = actual / default
        # Slight noise tolerance — anything down to 0.95× default is
        # within the blend's natural drift. Below that the pairwise
        # data and the explicit rule are saying different things.
        if ratio < 0.95:
            warnings.append({
                "kpi": prefer,
                "weight_key": weight_key,
                "rule_id": str(getattr(rule, "id", "")),
                "rule_description": getattr(rule, "description", ""),
                "expected_direction": "up",
                "observed_multiplier": round(ratio, 3),
                "message": (
                    f"Regra confirmada manda preferir {prefer} baixo, mas o "
                    f"peso {weight_key} caiu para {ratio:.2f}× do default. "
                    "Reveja a regra ou os dados de rejeição recentes."
                ),
            })
    return warnings


# ─── Read helper — used by FitnessConfig.from_tenant_config ──────────────


async def load_adaptive_weights(
    session: AsyncSession,
    tenant_id: UUID,
) -> Dict[str, float]:
    """Return the four adaptive weights for a tenant, or the defaults.

    Consumers (e.g. ``FitnessConfig.from_tenant_config``) call this to
    merge adaptive weights into the dataclass without caring whether the
    retrain job has ever run. The defaults are used when:

    * The tenant has no adaptive weights row yet (fresh tenant).
    * The most recent retrain produced ``status="skipped"`` (below
      the sample threshold) — in which case ``weights`` inside the
      payload is already a copy of the defaults.
    * The TenantConfigService is unreachable (defensive, logged).
    """
    from src.core.services.tenant_config_service import TenantConfigService

    try:
        svc = TenantConfigService(session, tenant_id)
        payload = await svc.get(
            TENANT_CONFIG_CATEGORY,
            TENANT_CONFIG_KEY,
            default=None,
        )
    except Exception as exc:  # pragma: no cover — read failures must not crash fitness
        logger.warning(
            "load_adaptive_weights: fell back to defaults for tenant %s (%s)",
            tenant_id, exc,
        )
        return dict(DEFAULT_WEIGHTS)

    if not isinstance(payload, dict):
        return dict(DEFAULT_WEIGHTS)
    weights = payload.get("weights")
    if not isinstance(weights, dict):
        return dict(DEFAULT_WEIGHTS)

    # Be tolerant of partial persistence — any missing key falls back
    # to its default so the fitness function always has every weight.
    merged = dict(DEFAULT_WEIGHTS)
    for key, value in weights.items():
        if key in merged and isinstance(value, (int, float)):
            merged[key] = float(value)
    return merged
