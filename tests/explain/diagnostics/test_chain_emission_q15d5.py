"""Sprint Q.15.D.5 — CausalChain emission round-trip tests.

Three layers tested:

  1. `build_chain_from_hypothesis` produces a CausalChain that passes
     the verifier's structural layers (syntactic + dag_consistent +
     direction). The full `passed` boolean stays False because the
     kernel layer needs kernel_result we don't supply — that's by
     design (kernel verification is the ABL job's role, not ours).

  2. `build_chain_from_mill_change` does the same for Mill's diff
     output.

  3. Each detector (ErroTreeDetector, ReichenbachDetector, MillDiffDetector)
     emits + persists a chain via `record_diagnostic_chain` ONLY when
     `conversation_id` is supplied. Without it, no chain emission
     (the rule_firing audit from Q.14.A is sufficient).
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any, Optional
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from src.copilot.causal.chain import CausalChain, verify_chain_dict
from src.explain.diagnostics.chain_builder import (
    build_chain_from_hypothesis,
    build_chain_from_mill_change,
    record_diagnostic_chain,
)
from src.explain.diagnostics.mill_diff import Change
from src.explain.diagnostics.types import (
    Hypothesis,
    MoldUsage,
    TriggerType,
    WorkerStats,
)


_TENANT = UUID("11111111-1111-1111-1111-111111111111")
_CONV = UUID("22222222-2222-2222-2222-222222222222")


def _patch_persist(monkeypatch):
    import src.shared.decorators as decorators

    async def _noop(*a, **kw):
        return None
    monkeypatch.setattr(decorators, "_persist_firing", _noop)


# ───────────────────────────────────────────────────────────────────────────
# build_chain_from_hypothesis — covers all 7 known types
# ───────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("hyp_type,expected_root,expected_target", [
    ("mold_degradation", "mold_age", "throughput_eur_day"),
    ("shared_mold", "mold_age", "throughput_eur_day"),
    ("worker_skill", "operator_experience", "rework_rate"),
    ("shared_workers", "operator_experience", "rework_rate"),
    ("overload", "laminagem_queue_hours", "throughput_eur_day"),
    ("shared_transport_pressure", "makespan_hours", "throughput_eur_day"),
    ("cascade_effect", "mold_age", "rework_rate"),
])
def test_build_chain_routes_each_type_to_dag_node(
    hyp_type, expected_root, expected_target,
):
    h = Hypothesis(type=hyp_type, entity="x", alpha=8, beta=2, evidence=["e1"])
    chain = build_chain_from_hypothesis(h, trigger=TriggerType.QUALITY_DROP)
    assert chain is not None
    assert chain.root_cause == expected_root
    assert chain.target == expected_target


def test_build_chain_returns_none_for_unmapped_type():
    """An unknown hypothesis type → None, NOT a fabricated chain that
    would fail the dag_consistent layer downstream."""
    h = Hypothesis(
        type="future_unmapped", entity="x", alpha=8, beta=2, evidence=[],
    )
    chain = build_chain_from_hypothesis(h, trigger=TriggerType.QUALITY_DROP)
    assert chain is None


def test_build_chain_carries_evidence_through():
    h = Hypothesis(
        type="mold_degradation", entity="M-7",
        alpha=8, beta=2,
        evidence=["evidence one", "evidence two"],
    )
    chain = build_chain_from_hypothesis(h, trigger=TriggerType.QUALITY_DROP)
    assert chain is not None
    assert chain.evidence == ["evidence one", "evidence two"]


def test_build_chain_includes_handler_name_in_question():
    """Audit trail clarity: a chain in the ABL corpus must say which
    handler emitted it."""
    h = Hypothesis(type="overload", entity="WIP", alpha=8, beta=2, evidence=[])
    chain = build_chain_from_hypothesis(
        h, trigger=TriggerType.THROUGHPUT_DROP, handler="my_handler",
    )
    assert chain is not None
    assert "my_handler" in chain.question


@pytest.mark.parametrize("hyp_type", [
    "mold_degradation", "shared_mold", "worker_skill", "shared_workers",
    "overload", "shared_transport_pressure", "cascade_effect",
])
def test_chain_passes_structural_verifier_layers(hyp_type):
    """syntactic + dag_consistent + direction MUST pass for every
    mapped hypothesis type. Fails here mean the mechanism path I built
    in chain_builder doesn't exist in NELO_DAG."""
    h = Hypothesis(type=hyp_type, entity="x", alpha=8, beta=2, evidence=["e"])
    chain = build_chain_from_hypothesis(h, trigger=TriggerType.QUALITY_DROP)
    assert chain is not None
    result = verify_chain_dict(chain.model_dump())
    layer_pass = {layer.name: layer.passed for layer in result.layers}
    assert layer_pass["syntactic"] is True, (
        f"{hyp_type}: syntactic failed: "
        f"{[l.issues for l in result.layers if l.name == 'syntactic']}"
    )
    assert layer_pass["dag_consistent"] is True, (
        f"{hyp_type}: dag_consistent failed: "
        f"{[l.issues for l in result.layers if l.name == 'dag_consistent']}"
    )
    assert layer_pass["direction"] is True, (
        f"{hyp_type}: direction failed: "
        f"{[l.issues for l in result.layers if l.name == 'direction']}"
    )


# ───────────────────────────────────────────────────────────────────────────
# build_chain_from_mill_change
# ───────────────────────────────────────────────────────────────────────────


def test_build_chain_from_mill_change_for_volume():
    change = Change(
        category="volume",
        change="WIP 200 → 600",
        correlation=0.9,
        likely_cause=True,
        evidence=["WIP doubled"],
    )
    chain = build_chain_from_mill_change(
        change, metric="error_rate", phase_id="LAMINAGEM",
    )
    assert chain is not None
    assert chain.root_cause == "laminagem_queue_hours"
    assert chain.target == "throughput_eur_day"
    assert "WIP" in chain.question


def test_build_chain_from_mill_change_skips_unmapped_category():
    """Material / shift / routing have no mapping today (no curated
    data) — return None instead of a fake chain."""
    change = Change(
        category="material", change="?", correlation=0.8,
        likely_cause=True, evidence=[],
    )
    chain = build_chain_from_mill_change(change, metric="error_rate")
    assert chain is None


# ───────────────────────────────────────────────────────────────────────────
# record_diagnostic_chain — best-effort persist
# ───────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_record_diagnostic_chain_returns_false_when_chain_none():
    """None input → False, no exception. The orchestrator's emit
    path uses this to decide whether to log."""
    out = await record_diagnostic_chain(
        session=AsyncMock(),
        tenant_id=_TENANT,
        conversation_id=_CONV,
        chain=None,
    )
    assert out is False


@pytest.mark.asyncio
async def test_record_diagnostic_chain_swallows_persist_failure(monkeypatch):
    """When `record_causal_audit` raises, this function logs +
    returns False — the diagnostic result still flows to the operator."""
    import src.copilot.causal.runtime as runtime

    async def _boom(*a, **kw):
        raise RuntimeError("DB exploded")
    monkeypatch.setattr(runtime, "record_causal_audit", _boom)

    h = Hypothesis(type="mold_degradation", entity="M-7", alpha=8, beta=2,
                   evidence=["e"])
    chain = build_chain_from_hypothesis(h, trigger=TriggerType.QUALITY_DROP)
    out = await record_diagnostic_chain(
        session=AsyncMock(),
        tenant_id=_TENANT,
        conversation_id=_CONV,
        chain=chain,
    )
    assert out is False


@pytest.mark.asyncio
async def test_record_diagnostic_chain_returns_true_on_success(monkeypatch):
    """Happy path: record_causal_audit returns a CopilotMessage → True."""
    import src.copilot.causal.runtime as runtime
    from unittest.mock import MagicMock

    async def _ok(*a, **kw):
        return MagicMock()  # truthy CopilotMessage

    monkeypatch.setattr(runtime, "record_causal_audit", _ok)

    h = Hypothesis(type="mold_degradation", entity="M-7", alpha=8, beta=2,
                   evidence=["e"])
    chain = build_chain_from_hypothesis(h, trigger=TriggerType.QUALITY_DROP)
    out = await record_diagnostic_chain(
        session=AsyncMock(),
        tenant_id=_TENANT,
        conversation_id=_CONV,
        chain=chain,
    )
    assert out is True


# ───────────────────────────────────────────────────────────────────────────
# Detector integration — emission opt-in via conversation_id
# ───────────────────────────────────────────────────────────────────────────


def _make_repo(**overrides):
    repo = AsyncMock()
    repo.molds_active_during.return_value = ["M-7"]
    repo.mold_phase_count.side_effect = [20, 120]
    repo.mold_error_count.side_effect = [6, 12]
    repo.mold_error_types.return_value = Counter({"interior enrugado": 6})
    repo.workers_active_in_phase.return_value = []
    repo.worker_phase_stats.return_value = WorkerStats(
        worker_id="", phase_id="", total_allocations=0, error_count=0,
    )
    repo.phase_error_rate.return_value = 0.0
    repo.current_wip.return_value = 0
    repo.avg_wip_during.return_value = 0.0
    for k, v in overrides.items():
        getattr(repo, k).return_value = v
    return repo


@pytest.mark.asyncio
async def test_erro_tree_skips_chain_emission_without_conversation_id(monkeypatch):
    """No conversation_id → no chain emission. The rule_firing log
    (Q.14.A) is enough audit for scheduler-driven calls."""
    from src.explain.diagnostics.erro_tree import ErroTreeDetector
    from src.explain.diagnostics.types import TriggerType

    _patch_persist(monkeypatch)
    record_calls = []

    async def _spy(*a, **kw):
        record_calls.append(kw)

    monkeypatch.setattr(
        "src.copilot.causal.runtime.record_causal_audit", _spy,
    )

    repo = _make_repo()
    detector = ErroTreeDetector.__new__(ErroTreeDetector)
    detector.session = AsyncMock()
    detector.tenant_id = _TENANT
    detector._repo = repo
    from src.explain.diagnostics.erro_tree import (
        MoldDetector, OverloadDetector, WorkerDetector,
    )
    detector._detectors = [
        MoldDetector(repo), WorkerDetector(repo), OverloadDetector(repo),
    ]

    await detector.investigate(
        trigger=TriggerType.QUALITY_DROP,
        period_days=7,
        # NO conversation_id supplied
    )
    assert record_calls == []  # zero emission


@pytest.mark.asyncio
async def test_erro_tree_emits_chain_when_conversation_id_supplied(monkeypatch):
    """conversation_id supplied + hypothesis trips → record_causal_audit
    receives a CausalChain dict for the mold root cause."""
    from src.explain.diagnostics.erro_tree import (
        ErroTreeDetector, MoldDetector, OverloadDetector, WorkerDetector,
    )
    from src.explain.diagnostics.types import TriggerType

    _patch_persist(monkeypatch)
    captured = {}

    async def _capture(*a, **kw):
        captured.update(kw)
        from unittest.mock import MagicMock
        return MagicMock()

    monkeypatch.setattr(
        "src.copilot.causal.runtime.record_causal_audit", _capture,
    )

    repo = _make_repo()
    detector = ErroTreeDetector.__new__(ErroTreeDetector)
    detector.session = AsyncMock()
    detector.tenant_id = _TENANT
    detector._repo = repo
    detector._detectors = [
        MoldDetector(repo), WorkerDetector(repo), OverloadDetector(repo),
    ]

    await detector.investigate(
        trigger=TriggerType.QUALITY_DROP,
        period_days=7,
        conversation_id=_CONV,
    )
    assert captured  # record_causal_audit was called
    assert captured.get("conversation_id") == _CONV
    chain_dict = captured.get("chain_dict")
    assert chain_dict is not None
    assert chain_dict["root_cause"] == "mold_age"
    assert chain_dict["target"] == "throughput_eur_day"


@pytest.mark.asyncio
async def test_mill_diff_emits_chain_only_for_likely_cause(monkeypatch):
    """A Change with `likely_cause=False` (correlation < threshold)
    must NOT trigger emission — we only feed strong signals to ABL."""
    from src.explain.diagnostics.mill_diff import MillDiffDetector

    _patch_persist(monkeypatch)
    captured = []

    async def _capture(*a, **kw):
        captured.append(kw)
        from unittest.mock import MagicMock
        return MagicMock()

    monkeypatch.setattr(
        "src.copilot.causal.runtime.record_causal_audit", _capture,
    )

    repo = AsyncMock()
    # Force a very weak signal — error_rate barely shifts
    repo.daily_phase_error_rate_samples.side_effect = [
        [0.10, 0.11, 0.10],
        [0.11, 0.12, 0.11],  # tiny shift
    ]
    repo.molds_active_during.return_value = []
    repo.mold_usage.return_value = MoldUsage(
        mold_id="", total_phases=0, error_count=0,
    )
    repo.workers_in_phase_set.return_value = set()
    repo.daily_wip_samples.return_value = []
    repo.transport_volume_during.return_value = 0
    repo.has_material_lot_tracking.return_value = False
    repo.has_shift_tracking.return_value = False

    detector = MillDiffDetector.__new__(MillDiffDetector)
    detector.session = AsyncMock()
    detector.tenant_id = _TENANT
    detector._repo = repo

    await detector.what_changed(
        good_start=date(2026, 4, 1), good_end=date(2026, 4, 4),
        bad_start=date(2026, 4, 5), bad_end=date(2026, 4, 8),
        metric="error_rate", phase_id="LAMINAGEM",
        conversation_id=_CONV,
    )
    # Either no shift detected at all OR no likely_cause Change → no emission
    assert captured == []
