"""Sprint Q.13.D D.4 — Camada 1 rule-application property tests.

The Q.11 Onda 1.1 wire copies `state.preference_rules` into
`FitnessConfig.preference_rules` so `compute_fitness` applies them.
Q.13.D pins the contract: the wire EXISTS and the application IS
monotonic — a rule that fires increases fitness; a rule that doesn't
match is a no-op.

Without these tests, a future refactor could:
  * Drop the auto-copy in `CPOv4Engine.__init__`
  * Skip the `cfg.preference_rules` branch in `compute_fitness`
  * Subtle off-by-one in `_temporal_penalty` weekday matching

Any of those would silently turn the moat (12 months of accumulated
preference signal) into noise. These tests turn each into an instant
red bar.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from hypothesis import given, settings, strategies as st

from src.plan.cpo.engine import CPOConfig, CPOv4Engine
from src.plan.cpo.fitness import FitnessConfig, compute_fitness
from src.plan.cpo.preference_adapter import compute_preference_penalty
from src.plan.cpo.state import FactoryState


# ─── Helpers ────────────────────────────────────────────────────────


def _op_dict(weekday: int, phase_id: str = "LAMINAGEM") -> dict:
    """Build an op dict with a `start_time` whose ISO weekday matches.

    `weekday` is 1=Mon..7=Sun (the format the `_weekday_from_op`
    helper expects).
    """
    # Find a base date and walk forward until isoweekday matches.
    base = datetime(2026, 5, 4)  # Monday
    delta = (weekday - base.isoweekday()) % 7
    target = base + timedelta(days=delta)
    return {
        "operation_id": f"op-{uuid4().hex[:8]}",
        "phase_id": phase_id,
        "phase_name": phase_id,
        "workers": ["w1"],
        "start_time": target.isoformat(),
        "end_time": (target + timedelta(hours=4)).isoformat(),
    }


def _schedule_with_ops(ops: list) -> dict:
    """Wrap ops in the schedule shape `compute_fitness` consumes."""
    return {
        "operations": ops,
        "makespan_hours": 8.0,
        "total_tardiness_hours": 0.0,
        "num_late_orders": 0,
        "setups": 1,
        "avg_utilization": 75.0,
        "safety_net_triggered": False,
    }


# ─── Wire test: state.preference_rules → fitness ────────────────────


def test_engine_constructor_copies_state_rules_into_fitness_config():
    """The Q.11 Onda 1.1 wire must stay live: instantiating CPOv4Engine
    with state.preference_rules populated copies the list into the
    fitness_config the engine carries."""
    rules = [
        {"type": "temporal_block", "predicate": {"weekday": 5}},
        {"type": "phase_threshold", "predicate": {"phase_id": "LAMINAGEM", "max_count": 3}},
    ]
    state = FactoryState(tenant_id=uuid4())
    state.preference_rules = list(rules)
    engine = CPOv4Engine(state=state, config=CPOConfig())
    assert engine.fitness_config.preference_rules == rules


def test_engine_does_not_overwrite_explicit_fitness_rules():
    """When the caller passes a FitnessConfig with rules already set,
    the engine respects it (doesn't clobber)."""
    state = FactoryState(tenant_id=uuid4())
    state.preference_rules = [
        {"type": "temporal_block", "predicate": {"weekday": 5}},
    ]
    pre_loaded = [
        {"type": "operator_affinity", "predicate": {"phase_id": "PINTURA", "operator_id": "w1"}},
    ]
    fc = FitnessConfig()
    fc.preference_rules = list(pre_loaded)
    engine = CPOv4Engine(state=state, config=CPOConfig(), fitness_config=fc)
    assert engine.fitness_config.preference_rules == pre_loaded


# ─── compute_fitness path: rule applies → fitness rises ─────────────


def test_temporal_rule_violation_increases_fitness():
    """A schedule with N ops on the blocked weekday pays N × penalty."""
    ops = [_op_dict(weekday=5) for _ in range(3)]  # 3 Friday ops
    schedule = _schedule_with_ops(ops)

    cfg_no_rules = FitnessConfig()
    cfg_with_rule = FitnessConfig()
    cfg_with_rule.preference_rules = [
        {"type": "temporal_block", "predicate": {"weekday": 5}},
    ]

    fit_no = compute_fitness(schedule, cfg_no_rules)
    fit_with = compute_fitness(schedule, cfg_with_rule)
    assert fit_with > fit_no


def test_temporal_rule_no_match_does_not_change_fitness():
    """When the schedule has zero ops on the blocked weekday, the
    penalty is zero and fitness is identical."""
    ops = [_op_dict(weekday=2) for _ in range(3)]  # Tuesday ops
    schedule = _schedule_with_ops(ops)

    cfg_no_rules = FitnessConfig()
    cfg_with_rule = FitnessConfig()
    cfg_with_rule.preference_rules = [
        {"type": "temporal_block", "predicate": {"weekday": 5}},  # blocks Friday
    ]

    fit_no = compute_fitness(schedule, cfg_no_rules)
    fit_with = compute_fitness(schedule, cfg_with_rule)
    assert fit_with == fit_no


# ─── Hypothesis property: monotonicity ──────────────────────────────


@given(
    n_blocked=st.integers(min_value=0, max_value=10),
    n_ok=st.integers(min_value=0, max_value=10),
    blocked_weekday=st.integers(min_value=1, max_value=7),
)
@settings(max_examples=50, deadline=None)
def test_property_more_violations_means_higher_or_equal_penalty(
    n_blocked: int, n_ok: int, blocked_weekday: int,
):
    """Monotonicity: penalty(n+1 violations) >= penalty(n violations).

    A schedule that violates a rule MORE TIMES gets a penalty AT LEAST
    AS HIGH as one that violates it fewer times. This property is the
    semantic guarantee that the GA can chase: "fewer violations →
    lower fitness". If broken, the optimiser can't learn to avoid the
    violations because the gradient lies."""
    ok_weekday = ((blocked_weekday) % 7) + 1  # different from blocked
    ops = [_op_dict(weekday=blocked_weekday) for _ in range(n_blocked)]
    ops += [_op_dict(weekday=ok_weekday) for _ in range(n_ok)]

    rules = [{"type": "temporal_block", "predicate": {"weekday": blocked_weekday}}]
    penalty = compute_preference_penalty({"operations": ops}, rules)

    # Add one more blocked op; penalty must rise (or stay equal when
    # n_blocked was 0 and the new op doesn't violate — but we just
    # added one that DOES, so it strictly rises in that case).
    ops_with_more = ops + [_op_dict(weekday=blocked_weekday)]
    penalty_more = compute_preference_penalty(
        {"operations": ops_with_more}, rules,
    )
    assert penalty_more >= penalty


@given(
    n_ops=st.integers(min_value=0, max_value=10),
)
@settings(max_examples=20, deadline=None)
def test_property_empty_rule_list_means_zero_penalty(n_ops: int):
    """No rules → no penalty, regardless of schedule size."""
    ops = [_op_dict(weekday=5) for _ in range(n_ops)]
    penalty = compute_preference_penalty({"operations": ops}, [])
    assert penalty == 0.0


def test_unknown_rule_type_is_silently_skipped():
    """A rule with `type` we don't recognise must NOT raise — it
    might be a future rule type that this version of the code doesn't
    know yet. The fitness loop has to keep running."""
    ops = [_op_dict(weekday=5)]
    rules = [{"type": "future_rule_xyz", "predicate": {"k": "v"}}]
    penalty = compute_preference_penalty({"operations": ops}, rules)
    assert penalty == 0.0


def test_malformed_predicate_does_not_crash():
    """Defensive: a predicate that isn't a dict is silently ignored,
    not a runtime error in the fitness hot path."""
    ops = [_op_dict(weekday=5)]
    rules = [{"type": "temporal_block", "predicate": "not a dict"}]
    penalty = compute_preference_penalty({"operations": ops}, rules)
    assert penalty == 0.0
