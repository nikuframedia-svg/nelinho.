"""
Tests for src.dqa.trust_gates (Sprint AA.2).

Covers: DEFAULT_THRESHOLDS match the blueprint, `gate_allows` strictness,
`effective_mode` returns all gates, per-caller helpers (solver/P90/commit)
and `load_gate_config` reading from TenantConfig + falling back to defaults.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest

from src.core.models.tenant_configuration import TenantConfiguration
from src.core.services.tenant_config_service import _reset_cache_for_tests
from src.dqa.trust_gates import (
    DEFAULT_THRESHOLDS,
    TrustGate,
    TrustGateConfig,
    auto_reorder_allowed,
    effective_mode,
    gate_allows,
    is_solver_suggestion_only,
    load_gate_config,
    quality_disposition_allowed,
    requires_human_approval,
    should_use_p90_durations,
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
# Blueprint invariants
# ---------------------------------------------------------------------------

def test_default_thresholds_are_monotonic_and_match_blueprint():
    # Blueprint v2.0 §4.5 prescribes exactly these five gates in order.
    expected = [
        (TrustGate.SOLVER_SUGGESTION_ONLY, 0.50),
        (TrustGate.USE_P90_DURATIONS, 0.60),
        (TrustGate.AUTO_REORDER, 0.70),
        (TrustGate.AUTO_COMMIT, 0.75),
        (TrustGate.QUALITY_DISPOSITION, 0.80),
    ]
    values = [DEFAULT_THRESHOLDS[g] for g, _ in expected]
    assert values == [t for _, t in expected]
    assert values == sorted(values)  # strictly ascending


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def test_gate_allows_semantics():
    # Below threshold blocks; at threshold permits (≥, not >).
    assert gate_allows(0.80, TrustGate.QUALITY_DISPOSITION) is True
    assert gate_allows(0.79, TrustGate.QUALITY_DISPOSITION) is False
    assert gate_allows(0.50, TrustGate.SOLVER_SUGGESTION_ONLY) is True
    assert gate_allows(0.49, TrustGate.SOLVER_SUGGESTION_ONLY) is False


def test_effective_mode_returns_all_gates():
    mode = effective_mode(0.72)
    assert set(mode.keys()) == {g.value for g in TrustGate}
    # With TI=0.72: solver_suggestion_only (≥0.50) ✓, use_p90 (≥0.60) ✓,
    # auto_reorder (≥0.70) ✓, auto_commit (≥0.75) ✗, quality_disposition (≥0.80) ✗
    assert mode["solver_suggestion_only"] is True
    assert mode["use_p90_durations"] is True
    assert mode["auto_reorder"] is True
    assert mode["auto_commit"] is False
    assert mode["quality_disposition"] is False


def test_is_solver_suggestion_only():
    assert is_solver_suggestion_only(0.49) is True
    assert is_solver_suggestion_only(0.50) is False
    assert is_solver_suggestion_only(0.95) is False


def test_should_use_p90_durations():
    assert should_use_p90_durations(0.59) is True
    assert should_use_p90_durations(0.60) is False
    assert should_use_p90_durations(0.95) is False


def test_auto_reorder_allowed():
    assert auto_reorder_allowed(0.69) is False
    assert auto_reorder_allowed(0.70) is True


def test_requires_human_approval():
    assert requires_human_approval(0.74) is True
    assert requires_human_approval(0.75) is False
    assert requires_human_approval(0.95) is False


def test_quality_disposition_allowed():
    assert quality_disposition_allowed(0.79) is False
    assert quality_disposition_allowed(0.80) is True


# ---------------------------------------------------------------------------
# Custom config
# ---------------------------------------------------------------------------

def test_custom_config_overrides_defaults():
    cfg = TrustGateConfig(thresholds={
        **DEFAULT_THRESHOLDS,
        TrustGate.AUTO_COMMIT: 0.90,
    })
    # Default would allow at 0.75, custom requires 0.90
    assert gate_allows(0.80, TrustGate.AUTO_COMMIT, cfg) is False
    assert gate_allows(0.91, TrustGate.AUTO_COMMIT, cfg) is True
    # Other gates unchanged
    assert gate_allows(0.70, TrustGate.AUTO_REORDER, cfg) is True


def test_trust_gate_config_default_factory():
    cfg = TrustGateConfig.default()
    for gate, threshold in DEFAULT_THRESHOLDS.items():
        assert cfg.get(gate) == threshold


# ---------------------------------------------------------------------------
# load_gate_config — reads from TenantConfig
# ---------------------------------------------------------------------------

def _gate_row(tenant_id, key, value):
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


@pytest.mark.asyncio
async def test_load_gate_config_reads_seeded_thresholds(fake_session, tenant_id):
    fake_session.queue_scalars([
        _gate_row(tenant_id, f"gates.{g.value}", DEFAULT_THRESHOLDS[g])
        for g in TrustGate
    ])
    cfg = await load_gate_config(fake_session, tenant_id)
    for gate, expected in DEFAULT_THRESHOLDS.items():
        assert cfg.get(gate) == expected


@pytest.mark.asyncio
async def test_load_gate_config_custom_thresholds(fake_session, tenant_id):
    fake_session.queue_scalars([
        _gate_row(tenant_id, "gates.solver_suggestion_only", 0.40),
        _gate_row(tenant_id, "gates.use_p90_durations", 0.55),
        _gate_row(tenant_id, "gates.auto_reorder", 0.65),
        _gate_row(tenant_id, "gates.auto_commit", 0.70),
        _gate_row(tenant_id, "gates.quality_disposition", 0.75),
    ])
    cfg = await load_gate_config(fake_session, tenant_id)
    assert cfg.get(TrustGate.SOLVER_SUGGESTION_ONLY) == 0.40
    assert cfg.get(TrustGate.AUTO_COMMIT) == 0.70


@pytest.mark.asyncio
async def test_load_gate_config_falls_back_when_keys_missing(fake_session, tenant_id):
    fake_session.queue_scalars([])  # empty trust category
    cfg = await load_gate_config(fake_session, tenant_id)
    # Must still return every gate at the default threshold.
    for gate, threshold in DEFAULT_THRESHOLDS.items():
        assert cfg.get(gate) == threshold
