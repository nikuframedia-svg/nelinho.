"""Sprint D.4 — AdaptiveFitnessWeights (Camada 2) retrain pipeline.

Covers:

* ``insufficient_pairs`` path — with fewer than `min_pairs` rejections
  the retainer reports ``skipped`` and the caller keeps defaults.
* Direction of learning — 10 commits where the operator always rejects
  alternatives that have *more* setups/tardiness shifts the respective
  weight **up** (operator prefers low K → weight rises).
* Multiplier clamp — a pathological coefficient cannot push a weight
  outside ``[0.5×default, 2.0×default]`` before blending.
* Blend ratio — the 70/30 mix is exactly applied on top of the
  clamped learned weights.
* ``load_adaptive_weights`` read-side fallback: missing row → defaults;
  persisted row → merged weights with partial-fallback for missing keys.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from uuid import UUID, uuid4

import pytest

from src.governance.preference_learning.adaptive_weights import (
    AdaptiveFitnessWeights,
    DEFAULT_WEIGHTS,
    MULTIPLIER_MAX,
    MULTIPLIER_MIN,
    TENANT_CONFIG_CATEGORY,
    TENANT_CONFIG_KEY,
    load_adaptive_weights,
)
from src.plan.cpo.commits import ScheduleCommit


TENANT = UUID("22222222-2222-2222-2222-222222222222")


# ─── Test doubles ──────────────────────────────────────────────────────────


class _FakeSession:
    """Lets the retainer iterate over hand-crafted ScheduleCommit rows.

    `execute(stmt)` ignores the statement and always returns the same
    `_FakeResult` — tests don't need the where clause to actually filter,
    they control the set they pass in.
    """

    def __init__(self, commits: List[ScheduleCommit]) -> None:
        self._commits = commits
        self.added: List[Any] = []
        self.flush_calls = 0

    async def execute(self, _stmt):  # noqa: ANN001 — test stub
        class _R:
            def __init__(self, rows: List[Any]) -> None:
                self._rows = rows

            def scalars(self):
                class _S:
                    def __init__(self, rows: List[Any]) -> None:
                        self._rows = rows

                    def all(self) -> List[Any]:
                        return list(self._rows)

                return _S(self._rows)

        return _R(self._commits)

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        self.flush_calls += 1


class _FakeTenantConfigService:
    """Replace the real service during retrain tests — we only care that
    ``set()`` was called with the right shape, not that Postgres stores it.
    The module-level hook patches this in via monkeypatch.
    """

    last_instance: "_FakeTenantConfigService | None" = None

    def __init__(self, session: Any, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.sets: List[Dict[str, Any]] = []
        _FakeTenantConfigService.last_instance = self

    async def set(
        self,
        *,
        category: str,
        key: str,
        value: Any,
        user_id: Any,
        data_type: str,
    ) -> None:
        self.sets.append({
            "category": category,
            "key": key,
            "value": value,
            "user_id": user_id,
            "data_type": data_type,
        })

    async def get(self, category: str, key: str, default: Any = None) -> Any:
        # Return the last stored payload if keys match; else default.
        for entry in reversed(self.sets):
            if entry["category"] == category and entry["key"] == key:
                return entry["value"]
        return default


def _make_commit(
    *,
    deltas: List[Dict[str, float]],
    sha_suffix: str = "a",
) -> ScheduleCommit:
    sha = (sha_suffix * 64)[:64]
    rejected = [
        {"alt_idx": i, "kpis": {}, "delta_vs_chosen": d}
        for i, d in enumerate(deltas)
    ]
    return ScheduleCommit(
        id=uuid4(),
        tenant_id=TENANT,
        parent_id=None,
        commit_sha256=sha,
        author="test",
        message="",
        kpis={},
        operations=[],
        delta={},
        alternatives=[],
        cpo_meta={},
        rejected_alternatives=rejected,
        user_preference_signal={},
        evidence_refs=[],
        scenarios_tested=0,
        trust_index=0.9,
        operations_count=0,
        created_at=datetime.now(timezone.utc) - timedelta(days=1),
    )


# ─── Insufficient-data path ────────────────────────────────────────────────


def test_retrain_with_insufficient_pairs_returns_defaults(monkeypatch):
    """Below the min-pairs threshold the retainer bails and the caller
    sees the hardcoded defaults — the persistence layer must not be
    touched so the previous snapshot (if any) stays in effect."""
    # Q.7 Fase 3 fix: reset class-level state from prior tests in random order.
    _FakeTenantConfigService.last_instance = None
    monkeypatch.setattr(
        "src.core.services.tenant_config_service.TenantConfigService",
        _FakeTenantConfigService,
        raising=True,
    )
    # Only 3 rejection pairs — well below the 50-pair floor.
    commits = [
        _make_commit(deltas=[{"setups": 2.0}], sha_suffix=chr(ord("a") + i))
        for i in range(3)
    ]
    retainer = AdaptiveFitnessWeights(_FakeSession(commits), TENANT)

    result = asyncio.run(retainer.retrain(window_days=30))

    assert result.status == "skipped"
    assert result.reason and "insufficient" in result.reason
    assert result.pairs_used == 3
    assert result.weights == DEFAULT_WEIGHTS
    # Nothing written through the TenantConfigService on the skip path.
    assert _FakeTenantConfigService.last_instance is None or \
        not _FakeTenantConfigService.last_instance.sets


# ─── Direction of learning ────────────────────────────────────────────────


def _preference_commits(
    kpi_key: str,
    n_commits: int = 60,
    delta_per_alt: float = 2.0,
) -> List[ScheduleCommit]:
    """Build commits whose rejected alternatives are *always* worse on
    ``kpi_key``. 60 commits × 1 alt each = 60 pairs > MIN_PAIRS.
    """
    return [
        _make_commit(
            deltas=[{kpi_key: delta_per_alt}],
            sha_suffix=chr(ord("a") + (i % 26)) + chr(ord("a") + (i // 26)),
        )
        for i in range(n_commits)
    ]


def test_retrain_prefers_low_setup_raises_setup_weight(monkeypatch):
    monkeypatch.setattr(
        "src.core.services.tenant_config_service.TenantConfigService",
        _FakeTenantConfigService,
        raising=True,
    )
    _FakeTenantConfigService.last_instance = None

    commits = _preference_commits("setups", n_commits=60, delta_per_alt=3.0)
    retainer = AdaptiveFitnessWeights(_FakeSession(commits), TENANT)

    result = asyncio.run(retainer.retrain(window_days=30))

    assert result.status == "trained"
    assert result.pairs_used == 60
    # The setups weight must have risen above the default (0.5).
    assert result.weights["w_setups"] > DEFAULT_WEIGHTS["w_setups"]
    # Other weights, having no signal in this dataset, stay at their
    # blended-with-defaults value — which is still the default because
    # the learned side for those KPIs also resolves to default.
    assert result.weights["w_tardiness"] == pytest.approx(
        DEFAULT_WEIGHTS["w_tardiness"], rel=0.05,
    )


def test_retrain_prefers_low_tardiness_raises_tardiness_weight(monkeypatch):
    monkeypatch.setattr(
        "src.core.services.tenant_config_service.TenantConfigService",
        _FakeTenantConfigService,
        raising=True,
    )
    _FakeTenantConfigService.last_instance = None

    commits = _preference_commits(
        "total_tardiness_hours", n_commits=60, delta_per_alt=5.0,
    )
    retainer = AdaptiveFitnessWeights(_FakeSession(commits), TENANT)

    result = asyncio.run(retainer.retrain(window_days=30))

    assert result.status == "trained"
    assert result.weights["w_tardiness"] > DEFAULT_WEIGHTS["w_tardiness"]


# ─── Clamp + blend invariants ──────────────────────────────────────────────


def test_multiplier_clamp_holds():
    """Any coefficient in [-1e9, +1e9] maps to a multiplier in
    [MULTIPLIER_MIN, MULTIPLIER_MAX] — the formula is ``exp(-coef)``
    clamped, so a huge negative coef shouldn't explode the weight."""
    retainer = AdaptiveFitnessWeights(_FakeSession([]), TENANT)
    extreme = retainer._coefs_to_weights({
        "w_makespan": -100.0,
        "w_tardiness": +100.0,
        "w_setups": 0.0,
        "w_quality_risk": -100.0,
    })
    assert extreme["w_makespan"] == pytest.approx(
        DEFAULT_WEIGHTS["w_makespan"] * MULTIPLIER_MAX,
    )
    assert extreme["w_tardiness"] == pytest.approx(
        DEFAULT_WEIGHTS["w_tardiness"] * MULTIPLIER_MIN,
    )
    assert extreme["w_setups"] == pytest.approx(DEFAULT_WEIGHTS["w_setups"])
    assert extreme["w_quality_risk"] == pytest.approx(
        DEFAULT_WEIGHTS["w_quality_risk"] * MULTIPLIER_MAX,
    )


def test_blend_ratio_70_30_on_top_of_defaults():
    """``w_new = 0.70 × learned + 0.30 × default``. Round trip through
    ``_blend`` with controlled inputs."""
    retainer = AdaptiveFitnessWeights(_FakeSession([]), TENANT)
    learned = {
        "w_makespan": 2.0,    # × default 1.0 → learned doubled
        "w_tardiness": 5.0,   # half of default 10.0 → learned halved
        "w_setups": 0.5,      # == default
        "w_quality_risk": 0.20,  # 2× default 0.10
    }
    blended = retainer._blend(learned)
    assert blended["w_makespan"] == pytest.approx(0.70 * 2.0 + 0.30 * 1.0)
    assert blended["w_tardiness"] == pytest.approx(0.70 * 5.0 + 0.30 * 10.0)
    assert blended["w_setups"] == pytest.approx(0.5)
    assert blended["w_quality_risk"] == pytest.approx(
        0.70 * 0.20 + 0.30 * 0.10,
    )


# ─── load_adaptive_weights read path ───────────────────────────────────────


def test_load_adaptive_weights_returns_defaults_when_missing(monkeypatch):
    """Fresh tenants with no row yet must get the hardcoded defaults so
    the GA keeps working on day one."""
    class _EmptyService:
        def __init__(self, session: Any, tenant_id: UUID) -> None:
            pass

        async def get(self, category: str, key: str, default: Any = None) -> Any:
            return default

    monkeypatch.setattr(
        "src.core.services.tenant_config_service.TenantConfigService",
        _EmptyService,
        raising=True,
    )
    weights = asyncio.run(load_adaptive_weights(_FakeSession([]), TENANT))
    assert weights == DEFAULT_WEIGHTS


def test_load_adaptive_weights_returns_persisted_weights_with_partial_fallback(
    monkeypatch,
):
    """A partial payload (only 2 of 4 keys) must still resolve to a full
    weight dict — the missing keys take their defaults."""
    stored_payload = {
        "weights": {
            "w_setups": 0.9,
            "w_tardiness": 12.0,
            # w_makespan + w_quality_risk deliberately missing
        },
        "trained_at": "2026-04-20T02:00:00+00:00",
    }

    class _FilledService:
        def __init__(self, session: Any, tenant_id: UUID) -> None:
            pass

        async def get(self, category: str, key: str, default: Any = None) -> Any:
            if (
                category == TENANT_CONFIG_CATEGORY
                and key == TENANT_CONFIG_KEY
            ):
                return stored_payload
            return default

    monkeypatch.setattr(
        "src.core.services.tenant_config_service.TenantConfigService",
        _FilledService,
        raising=True,
    )
    weights = asyncio.run(load_adaptive_weights(_FakeSession([]), TENANT))
    assert weights["w_setups"] == 0.9
    assert weights["w_tardiness"] == 12.0
    assert weights["w_makespan"] == DEFAULT_WEIGHTS["w_makespan"]
    assert weights["w_quality_risk"] == DEFAULT_WEIGHTS["w_quality_risk"]


# ─── Sprint R.2 — Camada 1↔2 cross-check ──────────────────────────────────


class _RuleStub:
    """Minimal stand-in for PreferenceRule used by the cross-check."""

    def __init__(
        self,
        *,
        predicate: Dict[str, Any],
        rule_id: str = "test-rule",
        description: str = "test rule",
    ) -> None:
        self.id = rule_id
        self.predicate = predicate
        self.description = description


def test_cross_check_no_warnings_when_weights_align_with_rule():
    from src.governance.preference_learning import detect_weight_rule_contradictions

    rule = _RuleStub(predicate={"prefer": "setups", "sacrifice": "throughput_eur_day"})
    blended = {
        "w_makespan": 1.0,
        "w_tardiness": 10.0,
        "w_setups": 0.7,  # default 0.5 → 1.4× → aligns with "prefer setups low"
        "w_quality_risk": 0.10,
    }
    warnings = detect_weight_rule_contradictions(
        blended_weights=blended, confirmed_rules=[rule],
    )
    assert warnings == []


def test_cross_check_emits_warning_when_weight_contradicts_confirmed_rule():
    from src.governance.preference_learning import detect_weight_rule_contradictions

    # Operator confirmed "prefer low tardiness" but the freshly trained
    # weight came out at 0.5× the default. Camadas disagree → warning.
    rule = _RuleStub(predicate={"prefer": "total_tardiness_hours"})
    blended = {
        "w_makespan": 1.0,
        "w_tardiness": 5.0,  # default 10.0 → 0.5× → contradicts the rule
        "w_setups": 0.5,
        "w_quality_risk": 0.10,
    }
    warnings = detect_weight_rule_contradictions(
        blended_weights=blended, confirmed_rules=[rule],
    )
    assert len(warnings) == 1
    w = warnings[0]
    assert w["weight_key"] == "w_tardiness"
    assert w["kpi"] == "total_tardiness_hours"
    assert w["observed_multiplier"] == 0.5
    assert "tardiness" in w["message"].lower()


def test_cross_check_ignores_rules_with_unknown_kpis():
    """A rule that prefers a KPI we don't adapt must be silently skipped."""
    from src.governance.preference_learning import detect_weight_rule_contradictions

    rule = _RuleStub(predicate={"prefer": "avg_utilization"})  # not in the 4
    blended = dict(DEFAULT_WEIGHTS)
    warnings = detect_weight_rule_contradictions(
        blended_weights=blended, confirmed_rules=[rule],
    )
    assert warnings == []
