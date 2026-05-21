"""Sprint Q.14.C — A/B framework tests.

Three layers tested:

  1. **Variant resolver determinism** — same (rule_id, tenant_id,
     candidates) always returns the same variant. Different inputs
     spread across buckets uniformly.
  2. **Adoption stats math** — Beta-Bernoulli posterior + CI per
     variant, winner declared only when CIs disjoint AND sample full.
  3. **Decorator integration** — `variants=` injects the resolved
     variant as a kwarg AND the audit row carries `variant_id`.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import pytest

import src.shared.decorators as decorators
from src.governance.ab_framework import (
    AdoptionReport,
    VariantStats,
    _beta_credible_interval,
    _beta_ci_normal_approx,
    compute_adoption_stats,
    resolve_variant,
)
from src.governance.models import RuleFiring, RuleFiringOutcome
from src.shared.decorators import record_rule_firing
from tests.conftest import FakeSession


_T1 = UUID("11111111-1111-1111-1111-111111111111")
_T2 = UUID("22222222-2222-2222-2222-222222222222")
_T3 = UUID("33333333-3333-3333-3333-333333333333")


# ───────────────────────────────────────────────────────────────────────────
# Variant resolver
# ───────────────────────────────────────────────────────────────────────────


def test_resolve_variant_is_deterministic_for_same_inputs():
    candidates = ["alpha", "beta", "gamma"]
    a = resolve_variant("rule.x", _T1, candidates)
    b = resolve_variant("rule.x", _T1, candidates)
    c = resolve_variant("rule.x", _T1, candidates)
    assert a == b == c
    assert a in candidates


def test_resolve_variant_returns_none_for_empty_candidates():
    assert resolve_variant("rule.x", _T1, []) is None


def test_resolve_variant_returns_only_value_when_single_candidate():
    assert resolve_variant("rule.x", _T1, ["only"]) == "only"


def test_resolve_variant_different_tenants_can_get_different_buckets():
    """Not GUARANTEED to differ for any 2 tenants (3-way bucket means
    1/3 chance of collision), but ACROSS many tenants the distribution
    should hit all candidates."""
    candidates = ["a", "b", "c", "d"]
    seen = set()
    # 100 deterministic tenant UUIDs — sample large enough that all
    # 4 buckets get at least one hit.
    for i in range(100):
        tid = UUID(int=i)
        seen.add(resolve_variant("rule.x", tid, candidates))
    assert seen == set(candidates), (
        f"Hash bucketing didn't spread across all candidates; got {seen}"
    )


def test_resolve_variant_different_rule_id_can_change_bucket():
    """Same tenant, different rule_id → may bucket differently. Not
    required but nice to have so different rules behave independently."""
    seen_per_rule = []
    for rule_id in [f"rule.{i}" for i in range(50)]:
        seen_per_rule.append(resolve_variant(rule_id, _T1, ["a", "b"]))
    # At least both buckets seen across 50 rules.
    assert set(seen_per_rule) == {"a", "b"}


# ───────────────────────────────────────────────────────────────────────────
# Adoption stats
# ───────────────────────────────────────────────────────────────────────────


def test_compute_adoption_returns_one_stats_per_variant():
    report = compute_adoption_stats("rule.x", [
        ("a", "accepted", 10),
        ("a", "rejected", 5),
        ("b", "accepted", 20),
        ("b", "rejected", 5),
    ])
    assert isinstance(report, AdoptionReport)
    assert len(report.variants) == 2
    assert {v.variant_id for v in report.variants} == {"a", "b"}


def test_compute_adoption_orders_by_acceptance_mean_desc():
    report = compute_adoption_stats("rule.x", [
        ("low_perf", "accepted", 10), ("low_perf", "rejected", 90),
        ("high_perf", "accepted", 90), ("high_perf", "rejected", 10),
    ])
    assert report.variants[0].variant_id == "high_perf"
    assert report.variants[1].variant_id == "low_perf"


def test_compute_adoption_acceptance_rate_uses_alpha_plus_one_prior():
    """Beta(α=accepted+1, β=rejected+1) — uniform prior. With 0
    accepts, 0 rejects, posterior mean is 0.5 (uniform fallback)."""
    report = compute_adoption_stats("rule.x", [
        ("a", "proposed", 5),  # all pending — no decided rows
    ])
    v = report.variants[0]
    assert v.acceptance_rate_mean == pytest.approx(0.5)
    assert v.total_decided == 0
    assert v.proposed_pending == 5


def test_compute_adoption_expired_counts_as_non_accepted():
    """`expired` rolls into the rejected bucket for the Bayesian
    update — operator had time to act + chose not to."""
    a_only_accept = compute_adoption_stats("rule.x", [
        ("a", "accepted", 10),
    ])
    a_with_expired = compute_adoption_stats("rule.x", [
        ("a", "accepted", 10),
        ("a", "expired", 10),
    ])
    # Mean drops because expired counts as non-accept.
    assert (
        a_with_expired.variants[0].acceptance_rate_mean
        < a_only_accept.variants[0].acceptance_rate_mean
    )


def test_compute_adoption_superseded_excluded_from_math():
    """`superseded` (newer firing replaced this one) carries no
    acceptance signal. Should NOT shift the posterior."""
    only = compute_adoption_stats("rule.x", [
        ("a", "accepted", 10),
        ("a", "rejected", 10),
    ])
    with_superseded = compute_adoption_stats("rule.x", [
        ("a", "accepted", 10),
        ("a", "rejected", 10),
        ("a", "superseded", 50),
    ])
    assert (
        only.variants[0].acceptance_rate_mean
        == pytest.approx(with_superseded.variants[0].acceptance_rate_mean)
    )


def test_compute_adoption_winner_requires_both_variants_full_sample():
    """Even with disjoint CIs, no winner if either variant has < min_sample."""
    report = compute_adoption_stats("rule.x", [
        # variant a: 60 accepts + 5 rejects → high mean, sample=65 ok
        ("a", "accepted", 60),
        ("a", "rejected", 5),
        # variant b: tiny sample → winner blocked even though clearly worse
        ("b", "accepted", 2),
        ("b", "rejected", 8),
    ], min_sample_for_winner=50)
    assert report.winner is None
    assert report.winner_reason is not None
    assert "decided firings" in report.winner_reason


def test_compute_adoption_winner_requires_disjoint_cis():
    """Even with full sample, no winner when CIs overlap."""
    report = compute_adoption_stats("rule.x", [
        # both variants ~50% with similar sample — CIs heavily overlap
        ("a", "accepted", 50),
        ("a", "rejected", 50),
        ("b", "accepted", 49),
        ("b", "rejected", 51),
    ], min_sample_for_winner=50)
    assert report.winner is None
    assert report.winner_reason is not None
    assert "CIs overlap" in report.winner_reason


def test_compute_adoption_winner_declared_when_cis_disjoint_and_full():
    report = compute_adoption_stats("rule.x", [
        # variant a: 90% acceptance, n=100
        ("a", "accepted", 90),
        ("a", "rejected", 10),
        # variant b: 10% acceptance, n=100
        ("b", "accepted", 10),
        ("b", "rejected", 90),
    ], min_sample_for_winner=50)
    assert report.winner == "a"
    assert "CI low" in report.winner_reason


def test_compute_adoption_winner_none_when_only_one_variant():
    report = compute_adoption_stats("rule.x", [
        ("only", "accepted", 50),
        ("only", "rejected", 50),
    ])
    assert report.winner is None
    assert "Only one variant" in report.winner_reason


def test_compute_adoption_skips_null_variant_rows():
    """Audit-only firings (no A/B) are filtered out — defensive guard
    even though the SQL query already does `WHERE variant_id IS NOT NULL`."""
    report = compute_adoption_stats("rule.x", [
        (None, "accepted", 100),  # ignored
        ("a", "accepted", 10),
        ("a", "rejected", 5),
    ])
    assert len(report.variants) == 1
    assert report.variants[0].variant_id == "a"


def test_credible_interval_clamps_to_unit_interval():
    """Tiny samples can push the normal approximation slightly past 0
    or 1; the clamp keeps the output in [0, 1]."""
    low, high = _beta_credible_interval(alpha=2, beta=1, level=0.95)
    assert 0.0 <= low <= high <= 1.0


def test_credible_interval_normal_approx_close_to_scipy():
    """The fallback path matches scipy within ~5pp for moderately-
    sized samples — used only when scipy isn't installed."""
    alpha, beta = 30, 20
    scipy_low, scipy_high = _beta_credible_interval(alpha, beta, 0.95)
    approx_low, approx_high = _beta_ci_normal_approx(alpha, beta, 0.025)
    assert abs(scipy_low - approx_low) < 0.05
    assert abs(scipy_high - approx_high) < 0.05


def test_credible_interval_rejects_invalid_levels():
    with pytest.raises(ValueError):
        _beta_credible_interval(alpha=10, beta=10, level=0.0)
    with pytest.raises(ValueError):
        _beta_credible_interval(alpha=10, beta=10, level=1.0)


# ───────────────────────────────────────────────────────────────────────────
# Decorator integration — variant injection + persistence
# ───────────────────────────────────────────────────────────────────────────


# Q.68.3.4 — _FakeSession era um stub de 12L com ``staged`` (list) e
# ``committed`` (bool) flags. Subclasse local mantém os aliases sobre o
# canónico.
class _FakeSession(FakeSession):
    """Q.68.3.4 — subclasse local: empty result + commit flag."""

    @property
    def staged(self) -> list:
        return self.added

    @property
    def committed(self) -> bool:
        return self.commit_calls > 0


def _patch_session(monkeypatch, session: _FakeSession):
    @asynccontextmanager
    async def _ctx():
        yield session

    monkeypatch.setattr(decorators, "get_session_context", _ctx, raising=False)
    import src.shared.database as db
    monkeypatch.setattr(db, "get_session_context", _ctx)


@pytest.mark.asyncio
async def test_decorator_injects_variant_as_kwarg(monkeypatch):
    seen_variants: list = []

    @record_rule_firing(
        rule_id="test.ab",
        variants=["alpha", "beta", "gamma"],
    )
    async def detect(self, *, variant=None):
        seen_variants.append(variant)
        return [{"x": 1}]

    class _Holder:
        tenant_id = _T1
    holder = _Holder()

    session = _FakeSession()
    _patch_session(monkeypatch, session)
    await detect(holder)

    # The injected variant is one of the candidates AND deterministic.
    assert seen_variants[0] in ("alpha", "beta", "gamma")
    # Persist also captured the same variant.
    assert session.staged[0].variant_id == seen_variants[0]


@pytest.mark.asyncio
async def test_decorator_caller_can_override_variant(monkeypatch):
    """If the caller passes `variant=` explicitly, the decorator
    must NOT override — the operator-supplied value wins. Useful
    for force-running a specific variant in tests / debugging."""
    seen: list = []

    @record_rule_firing(
        rule_id="test.ab.override",
        variants=["alpha", "beta"],
    )
    async def detect(self, *, variant=None):
        seen.append(variant)
        return []

    class _Holder:
        tenant_id = _T1
    holder = _Holder()

    session = _FakeSession()
    _patch_session(monkeypatch, session)
    await detect(holder, variant="forced")

    assert seen == ["forced"]
    # The audit row must reflect what actually ran (decorator-resolved
    # variant — even though the producer ran with "forced", the audit
    # captures the assigned bucket so the A/B math stays correct).
    assert session.staged[0].variant_id in ("alpha", "beta")


@pytest.mark.asyncio
async def test_decorator_no_variants_means_audit_only(monkeypatch):
    """Backward compat: a decorator without `variants=` doesn't inject
    anything and the row's variant_id stays NULL."""

    @record_rule_firing(rule_id="test.no_ab")
    async def detect(self):
        return []

    class _Holder:
        tenant_id = _T1
    holder = _Holder()

    session = _FakeSession()
    _patch_session(monkeypatch, session)
    await detect(holder)

    assert session.staged[0].variant_id is None


@pytest.mark.asyncio
async def test_decorator_sets_variants_marker():
    """Introspection tools list rules + their variants by walking
    decorated functions. Pin that the marker survives functools.wraps."""

    @record_rule_firing(rule_id="test.markers", variants=["x", "y"])
    async def detect(self, *, variant=None):
        return []

    assert getattr(detect, "__rule_firing_id__", None) == "test.markers"
    assert getattr(detect, "__rule_firing_variants__", None) == ("x", "y")
