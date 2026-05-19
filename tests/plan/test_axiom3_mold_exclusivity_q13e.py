"""Sprint Q.13.E E.3 — Spelke axiom 3 (mold exclusivity) property tests.

Plan v4 §51 — "1 poço ≠ 2 barcos": at any moment in time, a single
mold pocket can host at most ONE boat (or one batch of co-cycled
boats sharing the slot, by design).

This invariant has TWO enforcement layers:

  1. **CP-SAT layer** (`src.plan.engines.cpsat_lrho`) — already calls
     `model.AddNoOverlap` per mold_id at line 267-269. The solver
     CAN'T produce a schedule that violates the invariant.
  2. **Preview layer** (`src.plan.services.preview_delta_service`) —
     before Q.13.E this only flagged worker double-booking (axiom 1).
     The mold check now runs in `_detect_conflicts` so an operator
     who drag-drops a boat onto an in-use mold sees the conflict
     immediately, not after the next CPO solve.

These property tests exercise the preview layer (which is the
unguarded surface — CP-SAT's SAT-style proof is its own guarantee).

Test catalogue:
  * Real overlap on the same mold → MUST emit `mold_double_booking`.
  * No overlap on the same mold → MUST NOT emit.
  * Different molds → MUST NOT emit (even with overlap).
  * Same `mold_batch_id` → MUST NOT emit (multi-pocket sharing OK).
  * Random schedules: every emitted conflict points to a real
    overlap on the same mold (no false positives).
"""

from __future__ import annotations

import copy
from datetime import datetime, timedelta

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from src.plan.services.preview_delta_service import (
    PreviewMutation,
    _detect_conflicts,
)


_BASE = datetime(2026, 5, 3, 8, 0, 0)


def _op(
    op_id: str,
    *,
    mold_id: str,
    start_offset_min: int = 0,
    duration_min: int = 60,
    mold_batch_id: str | None = None,
):
    start = _BASE + timedelta(minutes=start_offset_min)
    end = start + timedelta(minutes=duration_min)
    return {
        "id": op_id,
        "phase_id": "LAMINAGEM",
        "workers": ["w-1"],
        "mold_id": mold_id,
        "mold_batch_id": mold_batch_id,
        "start": start.isoformat(),
        "end": end.isoformat(),
    }


# ───────────────────────────────────────────────────────────────────────────
# Unit-style axiom 3 tests (deterministic)
# ───────────────────────────────────────────────────────────────────────────


def test_mold_double_booking_detected_when_overlap_same_mold():
    schedule = {
        "operations": [
            _op("op1", mold_id="M-7", start_offset_min=0, duration_min=120),
            _op("op2", mold_id="M-7", start_offset_min=60, duration_min=60),
        ]
    }
    mutation = PreviewMutation(operation_id="op1")
    conflicts = _detect_conflicts(schedule, mutation)

    mold_conflicts = [c for c in conflicts if c.type == "mold_double_booking"]
    assert len(mold_conflicts) == 1
    assert mold_conflicts[0].severity == "conflict"
    assert "op2" in mold_conflicts[0].related_ids


def test_mold_double_booking_skipped_when_no_overlap():
    schedule = {
        "operations": [
            _op("op1", mold_id="M-7", start_offset_min=0, duration_min=60),
            _op("op2", mold_id="M-7", start_offset_min=120, duration_min=60),
        ]
    }
    mutation = PreviewMutation(operation_id="op1")
    conflicts = _detect_conflicts(schedule, mutation)

    assert not any(c.type == "mold_double_booking" for c in conflicts)


def test_mold_double_booking_skipped_when_different_molds():
    schedule = {
        "operations": [
            _op("op1", mold_id="M-7", start_offset_min=0, duration_min=120),
            _op("op2", mold_id="M-9", start_offset_min=60, duration_min=60),
        ]
    }
    mutation = PreviewMutation(operation_id="op1")
    conflicts = _detect_conflicts(schedule, mutation)

    assert not any(c.type == "mold_double_booking" for c in conflicts)


def test_mold_double_booking_skipped_when_same_batch_multi_pocket():
    """Multi-pocket moulds: ops sharing `mold_batch_id` co-cycle in the
    same slot by design — must NOT trigger a conflict."""
    schedule = {
        "operations": [
            _op("op1", mold_id="M-7", start_offset_min=0, duration_min=120,
                mold_batch_id="batch-1"),
            _op("op2", mold_id="M-7", start_offset_min=0, duration_min=120,
                mold_batch_id="batch-1"),
        ]
    }
    mutation = PreviewMutation(operation_id="op1")
    conflicts = _detect_conflicts(schedule, mutation)

    assert not any(c.type == "mold_double_booking" for c in conflicts)


def test_mold_double_booking_no_op_when_op_has_no_mold():
    """An op with `mold_id=None` cannot violate axiom 3."""
    schedule = {
        "operations": [
            _op("op1", mold_id=None),  # type: ignore[arg-type]
            _op("op2", mold_id="M-7"),
        ]
    }
    mutation = PreviewMutation(operation_id="op1")
    conflicts = _detect_conflicts(schedule, mutation)

    assert not any(c.type == "mold_double_booking" for c in conflicts)


# ───────────────────────────────────────────────────────────────────────────
# Property tests
# ───────────────────────────────────────────────────────────────────────────


@st.composite
def _mold_op(draw, op_id: str):
    mold_id = draw(st.sampled_from(["M-1", "M-2", "M-3", "M-4"]))
    start_off = draw(st.integers(min_value=0, max_value=12 * 60))
    duration = draw(st.integers(min_value=15, max_value=4 * 60))
    return _op(op_id, mold_id=mold_id, start_offset_min=start_off,
               duration_min=duration)


@settings(deadline=None, max_examples=300, suppress_health_check=[HealthCheck.too_slow])
@given(st.lists(st.integers(min_value=1, max_value=20), min_size=2, max_size=6, unique=True))
def test_property_emitted_conflicts_correspond_to_real_overlaps(op_indices):
    """For any random schedule, every emitted `mold_double_booking`
    must correspond to a real overlap on the same mold. False positives
    indicate a regression in the detector."""
    from hypothesis import strategies as st

    # Deterministically build a schedule from the indices so we can
    # cross-check overlap predicate manually.
    ops = []
    for i, idx in enumerate(op_indices):
        ops.append(_op(
            f"op{i}",
            mold_id=f"M-{idx % 3}",  # 3 molds → many collisions
            start_offset_min=(idx * 17) % (10 * 60),
            duration_min=30 + (idx * 13) % 90,
        ))
    schedule = {"operations": ops}

    target_id = ops[0]["id"]
    mutation = PreviewMutation(operation_id=target_id)
    conflicts = _detect_conflicts(schedule, mutation)
    target = ops[0]

    for c in [c for c in conflicts if c.type == "mold_double_booking"]:
        # Each emitted conflict references at least one real op_id...
        assert c.related_ids, (
            "mold_double_booking emitted without related_ids"
        )
        for rid in c.related_ids:
            other = next((o for o in ops if o["id"] == rid), None)
            assert other is not None, f"Conflict references unknown op id {rid}"
            # ...whose mold matches and whose time window overlaps.
            assert other["mold_id"] == target["mold_id"]
            t_start = datetime.fromisoformat(target["start"])
            t_end = datetime.fromisoformat(target["end"])
            o_start = datetime.fromisoformat(other["start"])
            o_end = datetime.fromisoformat(other["end"])
            assert t_start < o_end and t_end > o_start, (
                "Detector flagged a conflict on non-overlapping intervals"
            )


@settings(deadline=None, max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(
    duration_a=st.integers(min_value=15, max_value=240),
    duration_b=st.integers(min_value=15, max_value=240),
    gap_min=st.integers(min_value=1, max_value=480),
)
def test_property_no_overlap_no_conflict(duration_a, duration_b, gap_min):
    """Property: if two ops on the same mold are separated by ≥1 min,
    no conflict is emitted. This is the "completeness" direction."""
    schedule = {
        "operations": [
            _op("opA", mold_id="M-7", start_offset_min=0, duration_min=duration_a),
            _op(
                "opB", mold_id="M-7",
                start_offset_min=duration_a + gap_min,
                duration_min=duration_b,
            ),
        ]
    }
    mutation = PreviewMutation(operation_id="opA")
    conflicts = _detect_conflicts(schedule, mutation)
    assert not any(c.type == "mold_double_booking" for c in conflicts), (
        f"Spurious mold conflict for non-overlapping ops "
        f"(da={duration_a}, db={duration_b}, gap={gap_min})"
    )
