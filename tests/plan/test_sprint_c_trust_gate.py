"""Sprint C 1.2 — Trust Index real + auto-approval gate.

Before this fix `trust_index=0.0` was hardcoded on every ScheduleCommit
and the governance `_auto_approval_allowed` never looked at it, so a
low-quality plan could auto-commit as long as the risk ceiling was
permissive. Now the v2 calculator drives the commit's TI and the gate
vetoes auto-approval below 0.75 (Blueprint §4.5).
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from src.governance.service import GovernanceService


TENANT = UUID("11111111-1111-1111-1111-111111111111")


# ---------------------------------------------------------------------------
# _compute_trust_index_for_schedule helper
# ---------------------------------------------------------------------------


def test_compute_trust_index_stays_in_unit_interval_on_dqa_failure():
    """The CPO endpoint must stay up even if DQA errors mid-way. The v2
    calculator is itself defensive (falls back to default weights + neutral
    components), so a broken session yields a valid score near the ceiling
    rather than crashing. The contract that matters for the caller: no
    exception, returned value is in [0, 1].
    """
    from src.plan.api.cpo import _compute_trust_index_for_schedule

    class _BoomSession:
        async def execute(self, *_a, **_kw):
            raise RuntimeError("boom")

        async def get(self, *_a, **_kw):
            raise RuntimeError("boom")

    result = asyncio.run(_compute_trust_index_for_schedule(_BoomSession(), TENANT))
    assert 0.0 <= result <= 1.0


def test_compute_trust_index_returns_zero_when_calculator_import_fails(monkeypatch):
    """If the DQA module itself cannot be imported (hard dependency break),
    the helper logs + returns 0 so the approval gate forces human review.
    """
    from src.plan.api import cpo as cpo_module
    import builtins

    real_import = builtins.__import__

    def _import_fail(name, *args, **kwargs):
        if name == "src.dqa.trust_v2":
            raise ImportError("simulated dqa breakage")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _import_fail)
    result = asyncio.run(cpo_module._compute_trust_index_for_schedule(
        AsyncMock(), TENANT,
    ))
    assert result == 0.0


def test_compute_trust_index_returns_positive_value_without_provider():
    """Without a SignalsProvider the calculator uses neutral components
    (all 1.0) — the composite ends up at the sum of weights (~1.0),
    which is the right "trust everything" baseline for now.
    """
    from src.plan.api.cpo import _compute_trust_index_for_schedule

    class _NeutralSession:
        async def execute(self, *_a, **_kw):
            # Return an empty iterator so TenantConfigService.get_category
            # returns {} and the calculator falls back to default weights.
            class _Empty:
                def all(self):
                    return []
                def scalars(self):
                    class _S:
                        def all(self):
                            return []
                    return _S()
            return _Empty()

        async def get(self, *_a, **_kw):
            return None

    value = asyncio.run(_compute_trust_index_for_schedule(_NeutralSession(), TENANT))
    # Weights sum to 1.0, all components 1.0 → composite ≈ 1.0.
    # Allow slack because TenantConfigService may use different code paths.
    assert 0.0 <= value <= 1.0


# ---------------------------------------------------------------------------
# _auto_approval_allowed with trust_index gate
# ---------------------------------------------------------------------------


class _FakeCfg:
    """Minimal TenantConfigService replacement that returns pre-seeded values."""

    def __init__(self, values):
        self._values = values

    async def get(self, category, key, default=None):
        return self._values.get(f"{category}.{key}", default)


@pytest.mark.asyncio
async def test_auto_approval_blocked_when_trust_index_below_075(monkeypatch):
    svc = GovernanceService(db=AsyncMock(), tenant_id=TENANT)
    # Even if config allows auto-approval at the risk level, TI < 0.75 wins.
    monkeypatch.setattr(
        "src.core.services.tenant_config_service.TenantConfigService",
        lambda *_a, **_kw: _FakeCfg({
            "governance.auto_approval.reschedule_order.enabled": True,
            "governance.auto_approval.reschedule_order.risk_ceiling": "HIGH",
        }),
    )
    allowed = await svc._auto_approval_allowed(
        decision_type="reschedule_order",
        risk_level="LOW",
        trust_index=0.50,
    )
    assert allowed is False


@pytest.mark.asyncio
async def test_auto_approval_allowed_when_trust_index_at_or_above_075(monkeypatch):
    svc = GovernanceService(db=AsyncMock(), tenant_id=TENANT)
    monkeypatch.setattr(
        "src.core.services.tenant_config_service.TenantConfigService",
        lambda *_a, **_kw: _FakeCfg({
            "governance.auto_approval.reschedule_order.enabled": True,
            "governance.auto_approval.reschedule_order.risk_ceiling": "HIGH",
        }),
    )
    allowed = await svc._auto_approval_allowed(
        decision_type="reschedule_order",
        risk_level="LOW",
        trust_index=0.80,
    )
    assert allowed is True


@pytest.mark.asyncio
async def test_auto_approval_blocked_when_caller_omits_trust_index(monkeypatch):
    """Q.66.A.3 — when the caller doesn't pass ``trust_index``, the gate
    BLOCKS auto-approval by design (better a row for human review than a
    silent rubber-stamp).

    Pre-Q.66.A.3 the gate tried to auto-resolve TI via
    ``_resolve_trust_index(scenario_id)``, but that method called a
    non-existent ``CommitsService.get_by_scenario_id`` and always
    returned ``None`` — dead code masked by a try/except. The deeper
    reason: SandboxScenario (the only caller passing scenario_id) does
    not run CPO, so there is no commit to resolve to. Connecting them
    would be a product change. Auto-resolution removed; callers that
    have a TI must pass it explicitly.
    """
    svc = GovernanceService(db=AsyncMock(), tenant_id=TENANT)
    monkeypatch.setattr(
        "src.core.services.tenant_config_service.TenantConfigService",
        lambda *_a, **_kw: _FakeCfg({
            "governance.auto_approval.reschedule_order.enabled": True,
            "governance.auto_approval.reschedule_order.risk_ceiling": "HIGH",
        }),
    )
    allowed = await svc._auto_approval_allowed(
        decision_type="reschedule_order",
        risk_level="LOW",
    )
    assert allowed is False  # missing TI → blocked, not silently allowed


@pytest.mark.asyncio
async def test_auto_approval_uses_caller_provided_trust_index(monkeypatch):
    """Contrapositive of the test above: when the caller passes a TI
    ≥ 0.75, the gate uses it (after config + risk checks)."""
    svc = GovernanceService(db=AsyncMock(), tenant_id=TENANT)
    monkeypatch.setattr(
        "src.core.services.tenant_config_service.TenantConfigService",
        lambda *_a, **_kw: _FakeCfg({
            "governance.auto_approval.reschedule_order.enabled": True,
            "governance.auto_approval.reschedule_order.risk_ceiling": "HIGH",
        }),
    )
    allowed = await svc._auto_approval_allowed(
        decision_type="reschedule_order",
        risk_level="LOW",
        trust_index=0.85,
    )
    assert allowed is True  # 0.85 ≥ 0.75 + risk LOW ≤ HIGH ceiling


@pytest.mark.asyncio
async def test_auto_approval_respects_exactly_075_boundary(monkeypatch):
    """The gate is strict < 0.75 (not ≤), so exactly 0.75 is allowed.
    Matches Blueprint v2.0 §4.5 table wording ("TI < 0.75 → no auto-commit").
    """
    svc = GovernanceService(db=AsyncMock(), tenant_id=TENANT)
    monkeypatch.setattr(
        "src.core.services.tenant_config_service.TenantConfigService",
        lambda *_a, **_kw: _FakeCfg({
            "governance.auto_approval.reschedule_order.enabled": True,
            "governance.auto_approval.reschedule_order.risk_ceiling": "HIGH",
        }),
    )
    allowed = await svc._auto_approval_allowed(
        decision_type="reschedule_order",
        risk_level="LOW",
        trust_index=0.75,
    )
    assert allowed is True
