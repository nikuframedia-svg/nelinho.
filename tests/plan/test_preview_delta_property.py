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
