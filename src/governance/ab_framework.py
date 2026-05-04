"""
ProdPlan ONE — A/B Framework for rule firings (Sprint Q.14.C)
==============================================================

Builds on the rule-firing log (Q.14.A) + push channel (Q.14.B) to
answer the *"is this rule actually helping?"* question.

A *variant* is one concrete behaviour for a rule. The
``transport.complete_truck`` rule has hidden variants today: before
Sprint Q.13.E it targeted truck capacity (50); now it targets the
modal load (26). Without a framework, we can't tell whether the moda
change improved adoption — we just changed it. With this framework:

  * **Variant resolver** (`resolve_variant`) — deterministic per
    (rule_id, tenant_id, candidates). Same tenant always sees the
    same variant week after week, so the operator's experience is
    consistent. Hash-bucketing the *tenant_id* (not the firing) so
    a single tenant's history forms a coherent sample, not a
    randomised mix.

  * **Decorator extension** — `@record_rule_firing(variants=[...])`
    resolves the variant before the wrapped function runs and injects
    it as a `variant` kwarg. The producer function reads `variant` to
    pick its behaviour, and the audit row's `variant_id` column gets
    populated automatically.

  * **Adoption stats** (`compute_adoption_stats`) — Bayesian
    Beta-Bernoulli per variant. α=accepted+1, β=rejected+1, mean +
    95% credible interval via `scipy.stats.beta.ppf`. "Winner"
    declared only when CIs don't overlap AND each variant has ≥50
    completed firings (proposed → terminal).

Reuses the math semantics from `improve.record_adoption_signal`
(prior pseudo-counts, accepted vs rejected) but doesn't write back
to the suggestion table — adoption stats here are read-only over
existing `rule_firing` rows.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple
from uuid import UUID

logger = logging.getLogger(__name__)


# Minimum firings per variant before "winner" can be declared. Below
# this, any CI overlap is largely sampling noise. Matches the
# `improve.record_adoption_signal` cap (N=50) for shape symmetry.
_MIN_SAMPLE_FOR_WINNER = 50

# Default credible interval width. 95% is the convention; operators
# willing to act on weaker signal can override at the endpoint.
_DEFAULT_CREDIBLE_INTERVAL = 0.95


# ───────────────────────────────────────────────────────────────────────────
# Variant resolution
# ───────────────────────────────────────────────────────────────────────────


def resolve_variant(
    rule_id: str,
    tenant_id: UUID,
    candidates: Sequence[str],
) -> Optional[str]:
    """Pick a variant for ``(rule_id, tenant_id)`` deterministically.

    Same input → same output, **always**. The hash is computed once
    over ``(rule_id, tenant_id)`` so a tenant's history forms a coherent
    sample (no per-firing randomisation that would smear the signal).

    Returns ``None`` when ``candidates`` is empty — caller treats this
    as "no A/B configured, run the default branch".

    Args:
        rule_id: stable rule identifier, e.g. ``"transport.complete_truck"``.
        tenant_id: tenant UUID to bucket.
        candidates: ordered sequence of variant ids. Order matters for
            reproducibility (the hash maps to an index into this list);
            adding a variant in the middle re-buckets every tenant.
            Append-only is the safe contract.

    Example::

        variant = resolve_variant(
            rule_id="transport.complete_truck",
            tenant_id=my_tenant,
            candidates=["moda26", "ceiling50"],
        )
        # variant is one of the two strings, picked from a hash so the
        # same tenant_id always lands in the same bucket.
    """
    if not candidates:
        return None
    digest = hashlib.sha256(
        f"{rule_id}|{tenant_id}".encode("utf-8")
    ).digest()
    # First 4 bytes give us 32 bits of bucketing entropy — plenty for
    # any realistic candidate count.
    bucket = int.from_bytes(digest[:4], "big") % len(candidates)
    return candidates[bucket]


# ───────────────────────────────────────────────────────────────────────────
# Adoption stats
# ───────────────────────────────────────────────────────────────────────────


@dataclass
class VariantStats:
    """One row of the adoption breakdown."""

    variant_id: str
    total_fired: int
    accepted: int
    rejected: int
    expired: int
    superseded: int
    proposed_pending: int  # outcome still 'proposed', not yet decided
    acceptance_rate_mean: float  # Bayesian posterior mean
    acceptance_rate_low: float   # CI lower bound
    acceptance_rate_high: float  # CI upper bound
    sample_complete: bool        # True iff total_decided >= _MIN_SAMPLE_FOR_WINNER

    @property
    def total_decided(self) -> int:
        """Firings that reached a terminal outcome — denominator for
        the acceptance rate. ``proposed_pending`` rows aren't counted."""
        return self.accepted + self.rejected + self.expired + self.superseded

    def to_dict(self) -> Dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "total_fired": self.total_fired,
            "total_decided": self.total_decided,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "expired": self.expired,
            "superseded": self.superseded,
            "proposed_pending": self.proposed_pending,
            "acceptance_rate": {
                "mean": round(self.acceptance_rate_mean, 4),
                "ci_low": round(self.acceptance_rate_low, 4),
                "ci_high": round(self.acceptance_rate_high, 4),
            },
            "sample_complete": self.sample_complete,
        }


@dataclass
class AdoptionReport:
    """Full adoption summary for one rule_id."""

    rule_id: str
    variants: List[VariantStats]
    winner: Optional[str]            # variant_id when a winner exists
    winner_reason: Optional[str]     # human-readable rationale or None
    credible_interval: float         # the level used (e.g. 0.95)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "credible_interval": self.credible_interval,
            "variants": [v.to_dict() for v in self.variants],
            "winner": self.winner,
            "winner_reason": self.winner_reason,
        }


def compute_adoption_stats(
    rule_id: str,
    rows: List[Tuple[Optional[str], str, int]],
    *,
    credible_interval: float = _DEFAULT_CREDIBLE_INTERVAL,
    min_sample_for_winner: int = _MIN_SAMPLE_FOR_WINNER,
) -> AdoptionReport:
    """Compute per-variant Bayesian adoption stats.

    Args:
        rule_id: which rule to report on (used for the AdoptionReport
            label only — the rows are pre-filtered by the caller).
        rows: list of ``(variant_id, outcome, count)`` tuples. The
            caller emits this from a SQL ``GROUP BY variant_id, outcome``
            against ``governance.rule_firing``.
        credible_interval: posterior CI level (default 0.95).
        min_sample_for_winner: minimum decided firings per variant
            before a winner can be declared (default 50).

    Returns:
        :class:`AdoptionReport` with one :class:`VariantStats` per
        distinct variant_id, sorted by acceptance_rate_mean descending.
        ``winner`` is set only when one variant's CI sits strictly above
        another's CI AND both have ``sample_complete=True``.

    Notes:
        Beta(α=accepted+1, β=rejected+1) is the standard uniform prior
        choice for binary outcomes. ``rejected`` includes ``expired``
        for the math (operator didn't accept = same signal); ``superseded``
        is excluded entirely (a newer firing replaced this one — no
        acceptance signal either way).
    """
    # Aggregate the rows into per-variant counters.
    per_variant: Dict[str, Dict[str, int]] = {}
    for variant_id, outcome, count in rows:
        if variant_id is None:
            # Audit-only firings (no A/B); drop here, the caller queries
            # WHERE variant_id IS NOT NULL anyway, but defensive.
            continue
        slot = per_variant.setdefault(variant_id, {
            "proposed": 0, "accepted": 0, "rejected": 0,
            "expired": 0, "superseded": 0,
        })
        if outcome in slot:
            slot[outcome] += count

    variants: List[VariantStats] = []
    for variant_id, c in per_variant.items():
        accepted = c["accepted"]
        rejected = c["rejected"]
        expired = c["expired"]
        superseded = c["superseded"]
        proposed_pending = c["proposed"]
        # `expired` rolls into the "didn't accept" signal for the
        # Bayesian update (operator had time + chose not to act).
        non_accepted = rejected + expired
        decided = accepted + non_accepted + superseded
        # `superseded` doesn't carry an acceptance signal — it's
        # neutral. Exclude from the Beta math but keep in `total_decided`
        # so operators see the column.
        alpha = accepted + 1.0
        beta = non_accepted + 1.0
        mean = alpha / (alpha + beta)
        low, high = _beta_credible_interval(alpha, beta, credible_interval)
        sample_complete = decided >= min_sample_for_winner
        variants.append(VariantStats(
            variant_id=variant_id,
            total_fired=accepted + non_accepted + superseded + proposed_pending,
            accepted=accepted,
            rejected=rejected,
            expired=expired,
            superseded=superseded,
            proposed_pending=proposed_pending,
            acceptance_rate_mean=mean,
            acceptance_rate_low=low,
            acceptance_rate_high=high,
            sample_complete=sample_complete,
        ))

    variants.sort(key=lambda v: v.acceptance_rate_mean, reverse=True)
    winner, reason = _pick_winner(variants)
    return AdoptionReport(
        rule_id=rule_id,
        variants=variants,
        winner=winner,
        winner_reason=reason,
        credible_interval=credible_interval,
    )


def _pick_winner(
    variants: List[VariantStats],
) -> Tuple[Optional[str], Optional[str]]:
    """Strict CI-disjoint test: top variant's CI low must exceed the
    next variant's CI high, AND both variants must have enough sample.

    Returns ``(winner_id, reason)`` when a winner is found, ``(None,
    explanation)`` when not — the explanation tells operators why a
    winner couldn't be declared (CI overlap, insufficient sample, etc.)
    so the dashboard can render it.
    """
    if len(variants) < 2:
        return None, "Only one variant — no comparison possible"
    top, second = variants[0], variants[1]
    if not top.sample_complete:
        return None, (
            f"Top variant '{top.variant_id}' has only "
            f"{top.total_decided} decided firings (need ≥ "
            f"{_MIN_SAMPLE_FOR_WINNER})"
        )
    if not second.sample_complete:
        return None, (
            f"Runner-up '{second.variant_id}' has only "
            f"{second.total_decided} decided firings (need ≥ "
            f"{_MIN_SAMPLE_FOR_WINNER})"
        )
    if top.acceptance_rate_low <= second.acceptance_rate_high:
        return None, (
            f"CIs overlap — '{top.variant_id}' "
            f"[{top.acceptance_rate_low:.2f}-{top.acceptance_rate_high:.2f}] "
            f"vs '{second.variant_id}' "
            f"[{second.acceptance_rate_low:.2f}-{second.acceptance_rate_high:.2f}]"
        )
    return top.variant_id, (
        f"CI low {top.acceptance_rate_low:.3f} > "
        f"runner-up CI high {second.acceptance_rate_high:.3f}"
    )


def _beta_credible_interval(
    alpha: float, beta: float, level: float,
) -> Tuple[float, float]:
    """Return ``(low, high)`` of the Beta(α, β) CI at the given level.

    Uses scipy when available (preferred — exact percentiles); falls
    back to a normal approximation when scipy isn't importable. The
    fallback is fine for α + β > 30 but loose for tiny samples.
    """
    if level <= 0.0 or level >= 1.0:
        raise ValueError(f"level must be in (0,1); got {level}")
    tail = (1.0 - level) / 2.0
    try:
        from scipy.stats import beta as _beta_dist
        low = float(_beta_dist.ppf(tail, alpha, beta))
        high = float(_beta_dist.ppf(1.0 - tail, alpha, beta))
        return low, high
    except Exception as exc:
        logger.debug(
            "scipy unavailable (%s) — using normal approximation for CI",
            exc,
        )
        return _beta_ci_normal_approx(alpha, beta, tail)


def _beta_ci_normal_approx(
    alpha: float, beta: float, tail: float,
) -> Tuple[float, float]:
    """Wilson-style normal approximation. Loose for α+β < 30; close
    enough above. Used only when scipy isn't installed."""
    import math
    n = alpha + beta
    p = alpha / n
    var = (alpha * beta) / ((n ** 2) * (n + 1))
    sigma = math.sqrt(var)
    # z for two-sided level: invert the normal CDF analytically via
    # an Abramowitz approximation. For 95% (tail=0.025), z≈1.96.
    z = _normal_inverse_cdf(1.0 - tail)
    low = max(0.0, p - z * sigma)
    high = min(1.0, p + z * sigma)
    return low, high


def _normal_inverse_cdf(p: float) -> float:
    """Beasley-Springer-Moro approximation of Φ⁻¹(p). Accurate to ~1e-7
    on [0.025, 0.975] which is all we need for credible intervals."""
    import math
    a = [-3.969683028665376e+01, 2.209460984245205e+02,
         -2.759285104469687e+02, 1.383577518672690e+02,
         -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02,
         -1.556989798598866e+02, 6.680131188771972e+01,
         -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01,
         -2.400758277161838e+00, -2.549732539343734e+00,
          4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01,
         2.445134137142996e+00, 3.754408661907416e+00]
    plow = 0.02425
    phigh = 1.0 - plow
    if p < plow:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
    if p <= phigh:
        q = p - 0.5
        r = q * q
        return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
               (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
    q = math.sqrt(-2.0 * math.log(1.0 - p))
    return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
           ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)


__all__ = [
    "AdoptionReport",
    "VariantStats",
    "compute_adoption_stats",
    "resolve_variant",
]
