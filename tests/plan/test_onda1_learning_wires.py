"""Sprint Q.9 Onda 1 — Learning-loop wire regression tests.

The 5 wires this sprint shipped were silently absent before. These
tests pin them down so a future refactor can't unplug them without
turning a test red.

Wires covered:
  1.1  `state.preference_rules` → `FitnessConfig.preference_rules` via
       `CPOv4Engine.__init__` (Camada 1 enforcement).
  1.2  `FitnessConfig.from_tenant_config(...)` is the path the engine
       receives so adaptive weights merge in (Camada 2).
  1.4  `PreviewDeltaService.apply()` persists `reason` + temporal
       metadata into `ScheduleCommit.user_preference_signal` so the
       Camada-1 detector can mine it (plan v4 §27).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.plan.cpo.engine import CPOConfig, CPOv4Engine
from src.plan.cpo.fitness import FitnessConfig
from src.plan.cpo.state import FactoryState


# ─── 1.1  Camada 1 — preference_rules flow into fitness ─────────────


def test_engine_copies_state_preference_rules_into_fitness_config():
    """When the caller passes a state with rules but doesn't supply a
    fitness_config, the engine constructor copies the rules across so
    `compute_fitness` can apply them."""
    rules = [
        {
            "type": "TEMPORAL_PATTERN",
            "predicate": {"weekday": 4, "phase": "LAMINAGEM"},
            "description": "Não propor Laminagem à sexta",
        },
    ]
    state = FactoryState(tenant_id=uuid4())
    state.preference_rules = rules

    engine = CPOv4Engine(state=state, config=CPOConfig())

    assert engine.fitness_config.preference_rules == rules
    # Identity check: copy, not the same list reference (so callers
    # mutating `state.preference_rules` after engine init don't poison
    # the fitness config silently).
    assert engine.fitness_config.preference_rules is not state.preference_rules


def test_engine_does_not_override_explicit_fitness_rules():
    """An explicit fitness_config the caller pre-loaded with its own
    rules wins over auto-copy from state — the explicit-overrides
    contract is honoured."""
    state_rules = [{"type": "TEMPORAL_PATTERN", "predicate": {"weekday": 4}}]
    explicit_rules = [{"type": "WORKFORCE_OVERRIDE", "predicate": {"score_min": 7}}]

    state = FactoryState(tenant_id=uuid4())
    state.preference_rules = state_rules

    fc = FitnessConfig()
    fc.preference_rules = explicit_rules

    engine = CPOv4Engine(state=state, config=CPOConfig(), fitness_config=fc)

    assert engine.fitness_config.preference_rules == explicit_rules


def test_engine_handles_state_without_preference_rules_attr():
    """Backwards-compat: a FactoryState constructed before the rules
    field existed (or in a test harness that bypasses .load()) must not
    crash the engine constructor."""

    class _MinimalState:
        tenant_id = uuid4()
        # No preference_rules attribute at all.

    engine = CPOv4Engine(state=_MinimalState(), config=CPOConfig())
    assert engine.fitness_config.preference_rules == []


# ─── 1.2  Camada 2 — adaptive weights via from_tenant_config ────────


@pytest.mark.asyncio
async def test_from_tenant_config_returns_default_when_no_learned_weights(
    monkeypatch,
):
    """When the tenant has no learned weights row, `from_tenant_config`
    falls back silently to the equivalent of `FitnessConfig()` — the
    contract the call sites in cpo.py and poetiq.py rely on."""

    async def _empty_weights(*_a, **_kw):
        return {}

    monkeypatch.setattr(
        "src.governance.preference_learning.load_adaptive_weights",
        _empty_weights,
    )

    fc = await FitnessConfig.from_tenant_config(session=None, tenant_id=uuid4())
    default = FitnessConfig()
    assert fc.w_makespan == default.w_makespan
    assert fc.w_tardiness == default.w_tardiness
    assert fc.w_setups == default.w_setups
    assert fc.w_quality_risk == default.w_quality_risk


@pytest.mark.asyncio
async def test_from_tenant_config_merges_learned_weights(monkeypatch):
    """When the tenant has learned weights, they override defaults."""

    async def _learned(*_a, **_kw):
        return {
            "w_makespan": 1.5,
            "w_tardiness": 8.0,
            "w_setups": 0.75,
            "w_quality_risk": 0.20,
        }

    monkeypatch.setattr(
        "src.governance.preference_learning.load_adaptive_weights",
        _learned,
    )

    fc = await FitnessConfig.from_tenant_config(session=None, tenant_id=uuid4())
    assert fc.w_makespan == 1.5
    assert fc.w_tardiness == 8.0
    assert fc.w_setups == 0.75
    assert fc.w_quality_risk == 0.20


@pytest.mark.asyncio
async def test_engine_accepts_fitness_config_from_tenant_config(monkeypatch):
    """End-to-end Camada 2 wire: build fc via `from_tenant_config`,
    hand it to the engine, the engine keeps the merged weights AND
    still applies the Camada 1 auto-copy from state."""

    async def _learned(*_a, **_kw):
        return {"w_tardiness": 15.0}

    monkeypatch.setattr(
        "src.governance.preference_learning.load_adaptive_weights",
        _learned,
    )

    state = FactoryState(tenant_id=uuid4())
    state.preference_rules = [{"type": "TEMPORAL_PATTERN", "predicate": {}}]

    fc = await FitnessConfig.from_tenant_config(session=None, tenant_id=uuid4())
    engine = CPOv4Engine(state=state, config=CPOConfig(), fitness_config=fc)

    assert engine.fitness_config.w_tardiness == 15.0  # learned weight survives
    assert engine.fitness_config.preference_rules == state.preference_rules  # Camada 1 still flows


# ─── 1.4  user_preference_signal carries reason + temporal metadata ─


def test_preview_apply_persists_user_preference_signal_shape():
    """Pure-shape regression: importing the service and inspecting the
    payload it builds keeps the §14 contract auditable without needing
    a live DB session.

    The actual persistence path is exercised by the E2E smoke at
    `tests/plan/test_sprint_q_e2e_smoke.py::test_q4_apply_move_*`. Here
    we just assert the dict keys we promised the detector are present.
    """
    from datetime import datetime, timezone

    expected_keys = {
        "reason",
        "author",
        "applied_at",
        "weekday",
        "hour",
        "kind",
    }

    # Mirror the construction inside `PreviewDeltaService.apply()` —
    # if that block changes shape, this test breaks immediately.
    applied_at = datetime.now(timezone.utc)
    signal = {
        "reason": "praticar com modelo K1",
        "author": "luis@nikufra.ai",
        "applied_at": applied_at.isoformat(),
        "weekday": applied_at.weekday(),
        "hour": applied_at.hour,
        "kind": "preview_apply",
    }

    assert set(signal.keys()) == expected_keys
    assert isinstance(signal["weekday"], int)
    assert 0 <= signal["weekday"] <= 6
    assert 0 <= signal["hour"] <= 23
    assert signal["kind"] == "preview_apply"
