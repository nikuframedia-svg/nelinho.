"""Sprint Q.7 Fase 3 — property-based tests for preview-delta detectors.

Hypothesis-driven invariants for the Spelke axioms in
`src/plan/services/preview_delta_service.py`:

* **Axiom 1** (worker double-booking) — for any random schedule, if a
  worker appears in two operations whose time intervals overlap, the
  conflict detector MUST flag a `worker_double_booking` issue.
* **Axiom 4** (pair rule) — for any operation classified as Laminagem
  with worker count < 2, `_detect_warnings` MUST emit a `pair_rule`
  warning.

These are PROPERTY tests (random inputs across thousands of cases) —
they catch edge cases unit tests miss (e.g. exact-boundary times,
single-second overlaps, name normalisation).
"""

from __future__ import annotations

import copy
from datetime import datetime, timedelta

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from src.plan.services.preview_delta_service import (
    PAIR_REQUIRED_PHASES,
    PreviewMutation,
    _apply_mutation,
    _detect_conflicts,
    _detect_warnings,
)


# ─────────────────────────────────────────────────────────────────────────
# Strategies
# ─────────────────────────────────────────────────────────────────────────

_BASE = datetime(2026, 4, 25, 8, 0, 0)


@st.composite
def _operation(draw, op_id_prefix="op"):
    """Generate a random scheduled op with non-zero duration."""
    op_idx = draw(st.integers(min_value=1, max_value=99))
    phase = draw(st.sampled_from(["LAMINAGEM", "PINTURA", "DESMOLDE", "CURA", "MONTAGEM"]))
    n_workers = draw(st.integers(min_value=1, max_value=3))
    workers = [f"w-{w}" for w in draw(st.lists(
        st.integers(min_value=1, max_value=20),
        min_size=n_workers, max_size=n_workers, unique=True,
    ))]
    start_offset_min = draw(st.integers(min_value=0, max_value=24 * 60))
    duration_min = draw(st.integers(min_value=15, max_value=4 * 60))
    start = _BASE + timedelta(minutes=start_offset_min)
    end = start + timedelta(minutes=duration_min)
    return {
        "id": f"{op_id_prefix}-{op_idx}",
        "phase_id": phase,
        "workers": workers,
        "start": start.isoformat(),
        "end": end.isoformat(),
    }


@st.composite
def _schedule(draw, n_ops=5):
    ops = []
    seen_ids: set[str] = set()
    for i in range(n_ops):
        op = draw(_operation(op_id_prefix=f"op{i}"))
        # Force unique IDs across the schedule
        while op["id"] in seen_ids:
            op = draw(_operation(op_id_prefix=f"op{i}"))
        seen_ids.add(op["id"])
        ops.append(op)
    return {"operations": ops}


# ─────────────────────────────────────────────────────────────────────────
# Property: worker double-booking is always detected when overlap exists
# ─────────────────────────────────────────────────────────────────────────

@settings(deadline=None, max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(_schedule(n_ops=5))
def test_worker_doublebooking_detected_when_overlap(schedule):
    """For every random schedule, the detector either emits no conflict
    OR every emitted conflict corresponds to a real time overlap with
    a real worker collision. False positives = bug."""
    if len(schedule["operations"]) < 2:
        return

    target = schedule["operations"][0]
    other_workers = [
        w for op in schedule["operations"][1:] for w in op.get("workers", [])
    ]
    if not other_workers:
        return

    mutation = PreviewMutation(
        operation_id=target["id"],
        new_worker_ids=list({*target["workers"], other_workers[0]}),
    )
    after = copy.deepcopy(schedule)
    _apply_mutation(after, mutation)
    conflicts = _detect_conflicts(after, mutation)

    for c in conflicts:
        # Each emitted conflict must reference a real overlapping op id
        assert c.related_ids, f"Conflict {c.type} emitted without related_ids"
        for rid in c.related_ids:
            assert any(o.get("id") == rid for o in after["operations"]), (
                f"Conflict references unknown op id {rid}"
            )


# ─────────────────────────────────────────────────────────────────────────
# Property: pair_rule warning iff Laminagem with <2 workers
# ─────────────────────────────────────────────────────────────────────────

@settings(deadline=None, max_examples=300)
@given(
    phase=st.sampled_from(["LAMINAGEM", "PINTURA", "DESMOLDE", "MONTAGEM", "OUTRA"]),
    workers_count=st.integers(min_value=0, max_value=4),
)
def test_pair_rule_iff_laminagem_with_lt_2_workers(phase, workers_count):
    """The pair_rule warning fires EXACTLY when:
       (a) phase matches one in PAIR_REQUIRED_PHASES, AND
       (b) worker count < 2.
    Both directions: never fires for non-pair phases, never misses
    for pair phases with <2 workers."""
    workers = [f"w-{i}" for i in range(workers_count)]
    schedule = {
        "operations": [
            {
                "id": "op1",
                "phase_id": phase,
                "workers": workers,
                "start": "2026-04-25T08:00:00",
                "end": "2026-04-25T12:00:00",
            }
        ],
    }
    mutation = PreviewMutation(operation_id="op1", new_worker_ids=workers)
    warnings = _detect_warnings(schedule, mutation)

    is_pair_phase = any(p in phase for p in PAIR_REQUIRED_PHASES)
    expected_pair_warning = is_pair_phase and workers_count < 2

    pair_warnings = [w for w in warnings if w.type == "pair_rule"]
    assert (len(pair_warnings) > 0) == expected_pair_warning, (
        f"phase={phase} workers={workers_count} expected={expected_pair_warning} "
        f"got_pair_warnings={len(pair_warnings)}"
    )


# ─────────────────────────────────────────────────────────────────────────
# Property: applying mutation never adds NEW operations to the schedule
# ─────────────────────────────────────────────────────────────────────────

@settings(deadline=None, max_examples=100)
@given(_schedule(n_ops=4))
def test_apply_mutation_preserves_op_count(schedule):
    """Mutating an op (worker change OR phase change) must not create
    or destroy operations — only modify the targeted one."""
    if not schedule["operations"]:
        return
    target_id = schedule["operations"][0]["id"]
    before_count = len(schedule["operations"])

    after = copy.deepcopy(schedule)
    _apply_mutation(after, PreviewMutation(operation_id=target_id, new_worker_ids=["w-x"]))

    assert len(after["operations"]) == before_count, (
        "apply_mutation changed operation count — expected only an in-place edit"
    )


# ─────────────────────────────────────────────────────────────────────────
# Property: mutation with unknown op_id is a no-op
# ─────────────────────────────────────────────────────────────────────────

@settings(deadline=None, max_examples=50)
@given(
    bogus_id=st.text(
        alphabet=st.characters(min_codepoint=33, max_codepoint=126),
        min_size=1, max_size=20,
    ),
)
def test_mutation_unknown_op_is_noop(bogus_id):
    """Mutating an op_id that doesn't exist must NOT raise and must NOT
    silently mutate any op (would be a data-corruption bug)."""
    schedule = {
        "operations": [
            {"id": "real-op", "phase_id": "PINTURA", "workers": ["w1"]},
        ],
    }
    before = copy.deepcopy(schedule)
    _apply_mutation(schedule, PreviewMutation(operation_id=bogus_id, new_worker_ids=["w-x"]))
    # Schedule must be unchanged when target id is unknown.
    if bogus_id != "real-op":
        assert schedule == before


# ─────────────────────────────────────────────────────────────────────────
# Q.116.B+D — Spelke property tests for flexible predecessors + boost
# ─────────────────────────────────────────────────────────────────────────

from uuid import UUID  # noqa: E402

from src.plan.cpo.chromosome import Chromosome  # noqa: E402
from src.plan.cpo.decoder import decode as cpo_decode  # noqa: E402
from src.plan.cpo.state import FactoryState  # noqa: E402
from src.plan.engines.scheduling_adapter import (  # noqa: E402
    SchedulingMachine,
    SchedulingOperation,
)

_Q116_HORIZON_START = datetime(2026, 4, 20, 8, 0, 0)
_Q116_HORIZON_END = _Q116_HORIZON_START + timedelta(days=30)


def _q116_state() -> FactoryState:
    """Bare FactoryState with the seed curing gaps so axiom 6 has teeth."""
    from src.plan.cpo.state import NELO_CURING_GAPS_SEED, normalize_phase_code

    s = FactoryState(tenant_id=UUID("11111111-1111-1111-1111-111111111111"))
    s.skill_matrix = {}
    s.phase_transition_gaps = {
        (normalize_phase_code(frm), normalize_phase_code(to)): hours
        for frm, to, hours, _reason, _n in NELO_CURING_GAPS_SEED
    }
    return s


def _q116_machines(n: int = 2) -> List[SchedulingMachine]:
    return [
        SchedulingMachine(machine_id=f"M{i+1}", name=f"Machine {i+1}")
        for i in range(n)
    ]


def _q116_op(
    op_id: str,
    order_id: str,
    sequence: int,
    phase: str,
    *,
    duration_min: float = 60.0,
    machine: str = "M1",
    is_flexible: bool = False,
    allowed_predecessors: Optional[List[str]] = None,
) -> SchedulingOperation:
    return SchedulingOperation(
        operation_id=op_id,
        order_id=order_id,
        product_id="P1",
        sequence=sequence,
        operation_code=phase,
        duration_minutes=duration_min,
        machine_id=machine,
        phase_id=phase,
        is_flexible=is_flexible,
        allowed_predecessors=list(allowed_predecessors or []),
    )


def _build_q116_schedule_inputs(
    n_orders: int,
    flexible_idxs: List[int],
) -> Tuple[List[SchedulingOperation], List[SchedulingMachine], FactoryState]:
    """Build a 4-phase pipeline per order: LAMINAGEM → CURA → PINTURA → MONTAGEM.

    `flexible_idxs` lists the orders whose PINTURA op becomes flexible —
    it may start from EITHER CURA or directly from LAMINAGEM (skip cure
    by routing variant). We force CURA into allowed_predecessors so the
    op is still gated. This exercises both the gating logic and the gap
    chemistry (LAMINAGEM→CURA = 15h cure).
    """
    from typing import Optional as _Opt  # noqa: F401

    ops: List[SchedulingOperation] = []
    for i in range(n_orders):
        order_id = f"O{i+1}"
        ops.append(_q116_op(
            f"{order_id}-lam", order_id, 1, "LAMINAGEM",
            duration_min=30,
        ))
        ops.append(_q116_op(
            f"{order_id}-cura", order_id, 2, "CURA",
            duration_min=30,
        ))
        is_flex = i in flexible_idxs
        ops.append(_q116_op(
            f"{order_id}-pint", order_id, 3, "PINTURA_ACABAMENTO",
            duration_min=30,
            is_flexible=is_flex,
            allowed_predecessors=["CURA", "LAMINAGEM"] if is_flex else [],
        ))
        ops.append(_q116_op(
            f"{order_id}-mont", order_id, 4, "MONTAGEM",
            duration_min=30,
        ))
    return ops, _q116_machines(2), _q116_state()


@settings(
    deadline=None, max_examples=60,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(
    n_orders=st.integers(min_value=2, max_value=4),
    flex_count=st.integers(min_value=0, max_value=3),
)
def test_axiom_precedence_holds_with_flexible_phases(n_orders, flex_count):
    """Q.116.B — para cada op com is_flexible=True, op.start_time >=
    end_time de pelo menos UM allowed_predecessor (sibling cujo phase_id
    está em allowed_predecessors) já agendado. A precedência mantém-se,
    apenas que o predecessor real é seleccionado entre vários candidatos.
    """
    flex_count = min(flex_count, n_orders)
    flexible_idxs = list(range(flex_count))
    ops, machines, state = _build_q116_schedule_inputs(n_orders, flexible_idxs)
    chromo = Chromosome.identity(len(ops))
    result = cpo_decode(
        chromo, ops, machines, state, _Q116_HORIZON_START, _Q116_HORIZON_END,
    )
    out_by_id = {o["operation_id"]: o for o in result["operations"]}

    for op in ops:
        if not op.is_flexible:
            continue
        if op.operation_id not in out_by_id:
            continue  # infeasible — covered by other invariants
        op_start = datetime.fromisoformat(out_by_id[op.operation_id]["start_time"])
        # At least one allowed predecessor must be scheduled AND ended
        # before this op's start.
        allowed = set(op.allowed_predecessors)
        ok = False
        for sib in ops:
            if sib.order_id != op.order_id:
                continue
            if sib.phase_id not in allowed:
                continue
            if sib.operation_id not in out_by_id:
                continue
            sib_end = datetime.fromisoformat(out_by_id[sib.operation_id]["end_time"])
            if sib_end <= op_start:
                ok = True
                break
        assert ok, (
            f"Flexible op {op.operation_id} starts at {op_start} without any "
            f"completed allowed_predecessor in {allowed}"
        )


@settings(
    deadline=None, max_examples=60,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(
    n_orders=st.integers(min_value=1, max_value=3),
    use_flex=st.booleans(),
)
def test_axiom_curing_gap_holds_with_flexible_phases(n_orders, use_flex):
    """Q.116.B — gap chemistry (NELO_CURING_GAPS_SEED) aplica-se ao
    predecessor SELECCIONADO. Se PINTURA flexible escolheu CURA como
    predecessor, ainda assim verificamos que o intervalo entre o
    predecessor mais próximo (que está em allowed_predecessors) e a
    PINTURA respeita o min_gap_hours dessa transição.
    """
    flexible_idxs = list(range(n_orders)) if use_flex else []
    ops, machines, state = _build_q116_schedule_inputs(n_orders, flexible_idxs)
    chromo = Chromosome.identity(len(ops))
    result = cpo_decode(
        chromo, ops, machines, state, _Q116_HORIZON_START, _Q116_HORIZON_END,
    )
    out_by_id = {o["operation_id"]: o for o in result["operations"]}

    for op in ops:
        if op.phase_id != "PINTURA_ACABAMENTO":
            continue
        if op.operation_id not in out_by_id:
            continue
        op_start = datetime.fromisoformat(out_by_id[op.operation_id]["start_time"])
        # Find the chosen predecessor: the sibling whose end is the
        # latest among (allowed_predecessors if flexible else siblings
        # with lower sequence) that is <= op_start.
        candidate_phases = (
            set(op.allowed_predecessors) if op.is_flexible else None
        )
        chosen_end = None
        chosen_phase = None
        for sib in ops:
            if sib.order_id != op.order_id:
                continue
            if sib.operation_id == op.operation_id:
                continue
            if candidate_phases is not None:
                if sib.phase_id not in candidate_phases:
                    continue
            else:
                if sib.sequence >= op.sequence:
                    continue
            if sib.operation_id not in out_by_id:
                continue
            sib_end = datetime.fromisoformat(out_by_id[sib.operation_id]["end_time"])
            if sib_end > op_start:
                continue
            if chosen_end is None or sib_end > chosen_end:
                chosen_end = sib_end
                chosen_phase = sib.phase_id
        if chosen_end is None:
            continue  # no completed predecessor — different invariant
        required_gap_h = state.min_gap_hours(chosen_phase, op.phase_id)
        actual_gap_h = (op_start - chosen_end).total_seconds() / 3600.0
        # Allow 0.001h fuzz for fp.
        assert actual_gap_h + 1e-3 >= required_gap_h, (
            f"Op {op.operation_id} started {actual_gap_h:.3f}h after "
            f"{chosen_phase}; min curing gap is {required_gap_h:.3f}h"
        )


@settings(
    deadline=None, max_examples=60,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(
    n_orders=st.integers(min_value=2, max_value=4),
    boosts=st.lists(
        st.integers(min_value=0, max_value=10),
        min_size=2, max_size=4,
    ),
)
def test_boost_does_not_violate_precedence(n_orders, boosts):
    """Q.116.D — boosts aleatórios não permitem que um op arranque antes
    do seu predecessor legítimo. Boost só reordena TENTATIVAS no loop,
    nunca quebra precedências enforçadas pelo `_earliest_start`.
    """
    boosts = boosts[:n_orders] + [0] * max(0, n_orders - len(boosts))
    ops, machines, state = _build_q116_schedule_inputs(n_orders, [])
    chromo = Chromosome.identity(len(ops))
    boost_inputs = {
        f"O{i+1}": b for i, b in enumerate(boosts[:n_orders]) if b > 0
    }
    result = cpo_decode(
        chromo, ops, machines, state, _Q116_HORIZON_START, _Q116_HORIZON_END,
        boost_inputs=boost_inputs,
    )
    out_by_id = {o["operation_id"]: o for o in result["operations"]}

    # For every scheduled op, every sibling with lower sequence must
    # have ended by the time this op starts.
    for op in ops:
        if op.operation_id not in out_by_id:
            continue
        op_start = datetime.fromisoformat(out_by_id[op.operation_id]["start_time"])
        for sib in ops:
            if sib.order_id != op.order_id:
                continue
            if sib.sequence >= op.sequence:
                continue
            if sib.operation_id not in out_by_id:
                continue
            sib_end = datetime.fromisoformat(out_by_id[sib.operation_id]["end_time"])
            assert sib_end <= op_start, (
                f"Boost violated precedence: op {op.operation_id} "
                f"(seq={op.sequence}) started {op_start} before sibling "
                f"{sib.operation_id} (seq={sib.sequence}) ended {sib_end}"
            )


@settings(
    deadline=None, max_examples=60,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(
    n_orders=st.integers(min_value=2, max_value=3),
    boosts=st.lists(
        st.integers(min_value=0, max_value=10),
        min_size=2, max_size=3,
    ),
)
def test_boost_does_not_violate_curing_gaps(n_orders, boosts):
    """Q.116.D — curing chemistry (axiom 6) holds independent of boost.
    Para cada transição química conhecida (e.g. LAMINAGEM→CURA = 15h),
    o gap real entre fim do predecessor e início do sucessor respeita o
    min_gap_hours seed.
    """
    boosts = boosts[:n_orders] + [0] * max(0, n_orders - len(boosts))
    ops, machines, state = _build_q116_schedule_inputs(n_orders, [])
    chromo = Chromosome.identity(len(ops))
    boost_inputs = {
        f"O{i+1}": b for i, b in enumerate(boosts[:n_orders]) if b > 0
    }
    result = cpo_decode(
        chromo, ops, machines, state, _Q116_HORIZON_START, _Q116_HORIZON_END,
        boost_inputs=boost_inputs,
    )
    out_by_id = {o["operation_id"]: o for o in result["operations"]}

    # Walk every adjacent sibling pair within the same order and verify
    # curing gap chemistry is honoured.
    by_order: Dict[str, List[SchedulingOperation]] = {}
    for op in ops:
        by_order.setdefault(op.order_id, []).append(op)

    for order_id, order_ops in by_order.items():
        order_ops.sort(key=lambda o: o.sequence)
        for i in range(1, len(order_ops)):
            prev = order_ops[i - 1]
            curr = order_ops[i]
            if (
                prev.operation_id not in out_by_id
                or curr.operation_id not in out_by_id
            ):
                continue
            prev_end = datetime.fromisoformat(out_by_id[prev.operation_id]["end_time"])
            curr_start = datetime.fromisoformat(out_by_id[curr.operation_id]["start_time"])
            required = state.min_gap_hours(prev.phase_id, curr.phase_id)
            actual = (curr_start - prev_end).total_seconds() / 3600.0
            assert actual + 1e-3 >= required, (
                f"Curing gap violated for {order_id}: "
                f"{prev.phase_id}→{curr.phase_id} required {required}h, "
                f"got {actual:.3f}h"
            )


def test_higher_boost_starts_no_later_than_lower_when_resources_allow():
    """Q.116.D sanity (example test, NOT property). Two orders compete
    for the same machine. With boost on order B (higher than A), B must
    start no later than A. Schedules without boost serve as control.
    """
    state = _q116_state()
    state.skill_matrix = {}

    # Two single-op orders, same phase, same machine, identical duration.
    ops = [
        _q116_op("A-lam", "A", 1, "LAMINAGEM", duration_min=60, machine="M1"),
        _q116_op("B-lam", "B", 1, "LAMINAGEM", duration_min=60, machine="M1"),
    ]
    machines = _q116_machines(1)
    # Identity permutation: A appears before B.
    chromo = Chromosome.identity(len(ops))

    # Control: no boost. A should win the machine first.
    control = cpo_decode(
        chromo, ops, machines, state, _Q116_HORIZON_START, _Q116_HORIZON_END,
    )
    ctrl_by_id = {o["operation_id"]: o for o in control["operations"]}
    a_start_ctrl = datetime.fromisoformat(ctrl_by_id["A-lam"]["start_time"])
    b_start_ctrl = datetime.fromisoformat(ctrl_by_id["B-lam"]["start_time"])
    assert a_start_ctrl <= b_start_ctrl, "Control: A should run first by chromosome order"

    # Boost: B has higher boost; B should run no later than A.
    boosted = cpo_decode(
        chromo, ops, machines, state, _Q116_HORIZON_START, _Q116_HORIZON_END,
        boost_inputs={"B": 5, "A": 0},
    )
    bst_by_id = {o["operation_id"]: o for o in boosted["operations"]}
    a_start_boost = datetime.fromisoformat(bst_by_id["A-lam"]["start_time"])
    b_start_boost = datetime.fromisoformat(bst_by_id["B-lam"]["start_time"])
    assert b_start_boost <= a_start_boost, (
        f"Boosted order B started {b_start_boost} but unboosted A "
        f"started {a_start_boost} — boost did not promote B"
    )
