"""
Tests for src.dqa.trust_v2 (Sprint AA.1).

Unit-only: exercise component scorers, composite arithmetic, weight loading
(stubbed via TenantConfig seeder), and the calculator's resolution order
(components > signals > provider > optimistic default).
"""

from __future__ import annotations

import math
from datetime import datetime
from uuid import uuid4

import pytest

from src.core.models.tenant_configuration import TenantConfiguration
from src.core.services.tenant_config_service import _reset_cache_for_tests
from src.dqa.trust_v2 import (
    ALLOWED_SCOPES,
    PROVENANCE_TIER_SCORES,
    SCOPE_FACTORY,
    TrustComponents,
    TrustIndexV2Calculator,
    TrustSignals,
    TrustWeights,
    components_from_signals,
    score_anomaly,
    score_completeness,
    score_consistency,
    score_evidence,
    score_freshness,
    score_provenance,
    score_validity,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    _reset_cache_for_tests()


@pytest.fixture(autouse=True)
def _stub_publish(monkeypatch):
    async def fake(_t, _e):
        return True

    monkeypatch.setattr(
        "src.shared.kafka_client.publish_event", fake, raising=True,
    )


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------

def test_default_weights_sum_to_one():
    w = TrustWeights()
    assert math.isclose(w.total(), 1.0, abs_tol=1e-9)


def test_normalised_weights_rescale_to_one():
    w = TrustWeights(
        completeness=0.30, validity=0.40, freshness=0.30,
        consistency=0.40, provenance=0.30, anomaly=0.20, evidence=0.10,
    )
    assert w.total() > 1.0
    nw = w.normalised()
    assert math.isclose(nw.total(), 1.0, abs_tol=1e-9)


def test_normalised_rejects_all_zero():
    w = TrustWeights(0, 0, 0, 0, 0, 0, 0)
    with pytest.raises(ValueError):
        w.normalised()


def test_composite_respects_weights():
    components = TrustComponents(
        completeness=1.0, validity=0.0, freshness=1.0,
        consistency=0.0, provenance=1.0, anomaly=0.0, evidence=1.0,
    )
    w = TrustWeights()  # defaults sum to 1.0
    expected = (
        1.0 * 0.15 + 0.0 * 0.20 + 1.0 * 0.15 + 0.0 * 0.20
        + 1.0 * 0.15 + 0.0 * 0.10 + 1.0 * 0.05
    )
    assert math.isclose(components.composite(w), expected, abs_tol=1e-9)


def test_components_as_dict_includes_legacy_timeliness_alias():
    c = TrustComponents(freshness=0.42)
    assert c.as_dict(include_legacy_keys=True)["timeliness"] == 0.42
    assert "timeliness" not in c.as_dict(include_legacy_keys=False)


def test_causal_coherence_is_optional_and_not_weighted():
    """Onda 4.1 — verify CC really is excluded by comparing the SAME
    components with vs without causal_coherence set. The previous version
    of this test compared `c.composite(w) == c.composite(w)` which is a
    tautology (any composite equals itself). This rewrite reads the
    composite from a CC-bearing instance against a plain instance with
    identical other components and asserts they match.
    """
    weights = TrustWeights()
    plain = TrustComponents(
        completeness=0.8, validity=0.7, freshness=0.9,
        consistency=0.85, provenance=0.7, anomaly=0.95, evidence=1.0,
    )
    with_cc = TrustComponents(
        completeness=0.8, validity=0.7, freshness=0.9,
        consistency=0.85, provenance=0.7, anomaly=0.95, evidence=1.0,
        causal_coherence=0.5,  # set, but must not change the composite
    )
    assert plain.composite(weights) == with_cc.composite(weights)
    # And as a sanity check, swapping a weighted component DOES change it.
    different = TrustComponents(
        completeness=0.5, validity=0.7, freshness=0.9,
        consistency=0.85, provenance=0.7, anomaly=0.95, evidence=1.0,
    )
    assert different.composite(weights) != plain.composite(weights)


# ---------------------------------------------------------------------------
# Per-component scorers
# ---------------------------------------------------------------------------

def test_score_completeness_edge_cases():
    assert score_completeness(0, 0) == 1.0
    assert score_completeness(10, 0) == 1.0
    assert score_completeness(10, 10) == 0.0
    assert score_completeness(10, 5) == 0.5
    # missing can't exceed required, but we still clamp
    assert score_completeness(10, 100) == 0.0


def test_score_validity_edge_cases():
    assert score_validity(0, 0) == 1.0
    assert score_validity(10, 0) == 1.0
    assert score_validity(10, 10) == 0.0
    assert score_validity(10, 3) == 0.7


def test_score_freshness_exp_decay():
    # tau = 1 hour; age = 1 hour → exp(-1) ≈ 0.368
    f = score_freshness(age_seconds=3600, tau_seconds=3600)
    assert math.isclose(f, math.exp(-1), abs_tol=1e-9)

    # age 0 → 1.0
    assert score_freshness(0, 3600) == 1.0

    # missing info → optimistic 1.0 (we don't punish unknown)
    assert score_freshness(None, 3600) == 1.0
    assert score_freshness(3600, None) == 1.0


def test_score_consistency_averages_z_scores():
    # |z|=0 everywhere → 1.0
    assert score_consistency([0.0, 0.0], kappa=2.0) == 1.0
    # single z=2, kappa=2 → exp(-1) ≈ 0.368
    assert math.isclose(score_consistency([2.0], 2.0), math.exp(-1), abs_tol=1e-9)
    # empty list → optimistic 1.0
    assert score_consistency([], 2.0) == 1.0


def test_score_provenance_tiers():
    assert score_provenance("sensor") == 1.0
    assert score_provenance("SENSOR") == 1.0  # case-insensitive
    assert score_provenance("historian") == 0.85
    assert score_provenance("erp") == 0.70
    assert score_provenance("manual") == 0.50
    assert score_provenance("unknown-tier") == 0.50  # conservative default
    assert score_provenance("") == 0.50


def test_score_anomaly():
    assert score_anomaly(0.0) == 1.0
    assert score_anomaly(1.0) == 0.0
    assert score_anomaly(0.3) == 0.7


def test_score_evidence_tri_state():
    assert score_evidence(True) == 1.0
    assert score_evidence(False) == 0.0
    assert score_evidence(None) == 1.0  # optimistic when not checked


def test_components_from_signals_full_path():
    sig = TrustSignals(
        total_required=10, missing=2,
        total_validated=10, invalid=1,
        age_seconds=0, tau_seconds=3600,
        z_scores=[0.0], kappa=2.0,
        provenance_tier="historian",
        anomaly_probability=0.1,
        verifiable=True,
    )
    c = components_from_signals(sig)
    assert c.completeness == 0.8
    assert c.validity == 0.9
    assert c.freshness == 1.0
    assert c.consistency == 1.0
    assert c.provenance == 0.85
    assert math.isclose(c.anomaly, 0.9, abs_tol=1e-9)
    assert c.evidence == 1.0


def test_allowed_scopes_vocabulary():
    # Blueprint v2.0 §4.5 calls out factory / order / phase.
    assert {"factory", "order", "phase"} == ALLOWED_SCOPES


def test_provenance_tiers_match_blueprint():
    # Blueprint v2.0 §4.5: sensor > historian > ERP > manual
    assert PROVENANCE_TIER_SCORES["sensor"] > PROVENANCE_TIER_SCORES["historian"]
    assert PROVENANCE_TIER_SCORES["historian"] > PROVENANCE_TIER_SCORES["erp"]
    assert PROVENANCE_TIER_SCORES["erp"] > PROVENANCE_TIER_SCORES["manual"]


# ---------------------------------------------------------------------------
# Calculator — scope resolution + weight loading
# ---------------------------------------------------------------------------

def _weight_row(tenant_id, key, value):
    return TenantConfiguration(
        id=uuid4(),
        tenant_id=tenant_id,
        category="trust",
        key=key,
        value=TenantConfiguration.wrap(value),
        data_type="float",
        valid_from=datetime.utcnow(),
        created_at=datetime.utcnow(),
        last_modified_at=datetime.utcnow(),
    )


@pytest.fixture
def seeded_weights(fake_session, tenant_id):
    """Queue a full set of Blueprint v2.0 default weights as the next
    `get_category('trust')` result."""
    fake_session.queue_scalars([
        _weight_row(tenant_id, "weights.completeness", 0.15),
        _weight_row(tenant_id, "weights.validity", 0.20),
        _weight_row(tenant_id, "weights.freshness", 0.15),
        _weight_row(tenant_id, "weights.consistency", 0.20),
        _weight_row(tenant_id, "weights.provenance", 0.15),
        _weight_row(tenant_id, "weights.anomaly", 0.10),
        _weight_row(tenant_id, "weights.evidence", 0.05),
    ])


@pytest.mark.asyncio
async def test_load_weights_reads_from_tenant_config(fake_session, tenant_id, seeded_weights):
    calc = TrustIndexV2Calculator(fake_session, tenant_id)
    w = await calc.load_weights()
    assert math.isclose(w.total(), 1.0, abs_tol=1e-9)
    assert w.validity == 0.20


@pytest.mark.asyncio
async def test_load_weights_normalises_drifted_config(fake_session, tenant_id):
    fake_session.queue_scalars([
        _weight_row(tenant_id, "weights.completeness", 0.30),
        _weight_row(tenant_id, "weights.validity", 0.40),
        _weight_row(tenant_id, "weights.freshness", 0.30),
        _weight_row(tenant_id, "weights.consistency", 0.40),
        _weight_row(tenant_id, "weights.provenance", 0.30),
        _weight_row(tenant_id, "weights.anomaly", 0.20),
        _weight_row(tenant_id, "weights.evidence", 0.10),
    ])
    calc = TrustIndexV2Calculator(fake_session, tenant_id)
    w = await calc.load_weights()
    assert math.isclose(w.total(), 1.0, abs_tol=1e-6)


@pytest.mark.asyncio
async def test_compute_rejects_unknown_scope(fake_session, tenant_id, seeded_weights):
    calc = TrustIndexV2Calculator(fake_session, tenant_id)
    with pytest.raises(ValueError):
        await calc.compute_for_scope("nonsense")


@pytest.mark.asyncio
async def test_compute_explicit_components_takes_priority(fake_session, tenant_id, seeded_weights):
    async def should_not_be_called(*_a, **_kw):
        raise AssertionError("signals_provider must not be consulted when components given")

    calc = TrustIndexV2Calculator(fake_session, tenant_id, signals_provider=should_not_be_called)
    result = await calc.compute_for_scope(
        SCOPE_FACTORY,
        components=TrustComponents(completeness=0.5, validity=0.5, freshness=0.5,
                                   consistency=0.5, provenance=0.5, anomaly=0.5, evidence=0.5),
    )
    assert math.isclose(result.composite, 0.5, abs_tol=1e-6)


@pytest.mark.asyncio
async def test_compute_uses_signals_when_components_absent(fake_session, tenant_id, seeded_weights):
    calc = TrustIndexV2Calculator(fake_session, tenant_id)
    result = await calc.compute_for_scope(
        SCOPE_FACTORY,
        signals=TrustSignals(
            total_required=10, missing=0,
            total_validated=10, invalid=0,
            age_seconds=0, tau_seconds=3600,
            provenance_tier="sensor",
        ),
    )
    # Everything at the optimistic end + sensor provenance = 1.0
    assert math.isclose(result.composite, 1.0, abs_tol=1e-9)


@pytest.mark.asyncio
async def test_compute_uses_provider_as_fallback(fake_session, tenant_id, seeded_weights):
    seen = {}

    async def provider(session, tid, scope, scope_id):
        seen["scope"] = scope
        seen["scope_id"] = scope_id
        return TrustComponents(completeness=0.4, validity=0.4, freshness=0.4,
                               consistency=0.4, provenance=0.4, anomaly=0.4, evidence=0.4)

    calc = TrustIndexV2Calculator(fake_session, tenant_id, signals_provider=provider)
    sid = uuid4()
    result = await calc.compute_for_scope(SCOPE_FACTORY, scope_id=sid)
    assert seen == {"scope": SCOPE_FACTORY, "scope_id": sid}
    assert math.isclose(result.composite, 0.4, abs_tol=1e-6)


@pytest.mark.asyncio
async def test_compute_provider_wrong_return_type_raises(fake_session, tenant_id, seeded_weights):
    async def bad_provider(*_a, **_kw):
        return {"not": "valid"}

    calc = TrustIndexV2Calculator(fake_session, tenant_id, signals_provider=bad_provider)
    with pytest.raises(TypeError):
        await calc.compute_for_scope(SCOPE_FACTORY)


@pytest.mark.asyncio
async def test_compute_defaults_to_conservative_baseline_when_no_source(fake_session, tenant_id, seeded_weights):
    calc = TrustIndexV2Calculator(fake_session, tenant_id)
    result = await calc.compute_for_scope(SCOPE_FACTORY)
    # No signals, no components, no provider → all components default to 1.0
    # EXCEPT provenance, which scores 0.70 for the default "erp" tier.
    # Composite = 0.85 + 0.15*0.70 = 0.955.
    assert math.isclose(result.composite, 0.955, abs_tol=1e-6)
    assert result.scope == SCOPE_FACTORY


@pytest.mark.asyncio
async def test_to_dict_serialisation(fake_session, tenant_id, seeded_weights):
    calc = TrustIndexV2Calculator(fake_session, tenant_id)
    result = await calc.compute_for_scope(SCOPE_FACTORY)
    out = result.to_dict()
    assert out["scope"] == SCOPE_FACTORY
    assert out["scope_id"] is None
    assert "causal_coherence" in out["components"]
    assert isinstance(out["weights"], dict)
    assert math.isclose(sum(out["weights"].values()), 1.0, abs_tol=1e-6)
