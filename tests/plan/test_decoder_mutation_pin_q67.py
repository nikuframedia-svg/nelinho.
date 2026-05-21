"""
Q.67.3.B — Mutation-pin tests for src.plan.cpo.decoder helpers.

Strategy
========
Instead of running ``mutmut --paths-to-mutate src/plan/cpo/decoder.py``
(10-30min on Luis' laptop), we *anticipate* the mutant classes that
mutmut typically generates and pin the boundary behaviour explicitly:

* arithmetic   : ``x + 1`` ↔ ``x - 1``, ``a / b`` ↔ ``a * b``
* comparisons  : ``>`` ↔ ``>=``, ``==`` ↔ ``!=``, ``<`` ↔ ``<=``
* constants    : magic numbers replaced by ``0`` / ``1`` / +1 / -1
* defaults     : ``or 1`` removed, ``or default`` removed
* control flow : ``True`` ↔ ``False`` in early-return branches

Focus is the 5 smallest pure helpers in ``decoder.py`` whose lines
mutmut hammers hardest:

* ``_pocket_count``                       — ``max(1, ...)`` guard +
                                            ``or 1`` default
* ``classify_rework_phase``               — substring vs equality
* ``_is_desmolde``                        — startswith vs endswith vs ``==``
* ``_last_on_machine_has_different_family`` — ``batch_size`` tail-skip +
                                            empty-family early return
* ``_estimate_utilization``               — ``min(100.0, ...)`` clamp +
                                            ``max(1.0, ...)`` divider

Each helper gets 4-6 pin-tests. If mutmut later flips a single
operator inside any of these functions, *at least one* of these tests
must fail.

Mutation-aware test design — see ``agent_docs/q67_3b_mutation_pin_strategy.md``.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List
from uuid import UUID

import pytest

from src.plan.cpo.decoder import (
    DEFAULT_REWORK_BUFFER_PCT,
    POST_DESMOLDE_PHASE_NAMES,
    REWORK_BUFFER_PHASE_KEYWORDS,
    ScheduledOp,
    _empty_result,
    _estimate_utilization,
    _is_desmolde,
    _last_on_machine_has_different_family,
    _pocket_count,
    classify_rework_phase,
    compute_mold_batches,
)
from src.plan.cpo.state import FactoryState, MoldInfo
from src.plan.engines.scheduling_adapter import (
    SchedulingMachine,
    SchedulingOperation,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

T0 = datetime(2026, 5, 1, 8, 0, 0)


def _state(molds: dict[str, MoldInfo] | None = None) -> FactoryState:
    s = FactoryState(tenant_id=UUID("11111111-1111-1111-1111-111111111111"))
    if molds:
        s.molds.update(molds)
    return s


def _scheduled(
    op_id: str,
    machine_id: str,
    setup_family: str,
    end_offset_min: int = 60,
) -> ScheduledOp:
    return ScheduledOp(
        operation_id=op_id,
        order_id="O1",
        phase_id="PH",
        machine_id=machine_id,
        workers=[],
        mold_id=None,
        start=T0,
        end=T0 + timedelta(minutes=end_offset_min),
        duration_minutes=float(end_offset_min),
        setup_family=setup_family,
    )


def _machine(mid: str = "M1") -> SchedulingMachine:
    return SchedulingMachine(machine_id=mid, name=mid)


def _op(
    op_id: str,
    *,
    setup_family: str = "",
    phase_id: str = "PH",
    mold_required: bool = False,
    model_id: str = "",
    mold_id: str | None = None,
) -> SchedulingOperation:
    return SchedulingOperation(
        operation_id=op_id,
        order_id="O1",
        product_id="P1",
        sequence=1,
        operation_code=op_id,
        duration_minutes=60.0,
        machine_id="M1",
        phase_id=phase_id,
        setup_family=setup_family,
        mold_required=mold_required,
        model_id=model_id,
        mold_id=mold_id,
    )


# ---------------------------------------------------------------------------
# 1) _pocket_count — ``max(1, int(getattr(..., "pocket_count", 1) or 1))``
# ---------------------------------------------------------------------------

class TestPocketCount:
    """Pin ``max(1, ...)`` guard and ``or 1`` fallback.

    Mutmut typically flips ``max(1, x)`` to ``max(0, x)`` or ``min(1, x)``,
    and removes the ``or 1`` defaulter. Each test below dies under one of
    those mutations.
    """

    def test_missing_mold_returns_one(self):
        # If ``state.molds`` has no entry, default is 1 — NOT 0.
        s = _state()
        assert _pocket_count(s, "missing-id") == 1

    def test_pocket_count_one_returns_one(self):
        # Pin the equality boundary: a recorded pocket_count of 1 must
        # stay 1 (mutmut may change ``max(1, x)`` to ``max(2, x)``).
        s = _state({"m1": MoldInfo(molde_id="m1", modelo_id="X", pocket_count=1)})
        assert _pocket_count(s, "m1") == 1

    def test_pocket_count_two_returns_two(self):
        # The smallest "real" batching value — mutmut flipping the
        # ``max(1, x)`` constant must surface here.
        s = _state({"m1": MoldInfo(molde_id="m1", modelo_id="X", pocket_count=2)})
        assert _pocket_count(s, "m1") == 2

    def test_pocket_count_six_passes_through(self):
        # Large value — pins that ``max`` doesn't clip from above.
        s = _state({"m1": MoldInfo(molde_id="m1", modelo_id="X", pocket_count=6)})
        assert _pocket_count(s, "m1") == 6

    def test_pocket_count_zero_floored_to_one(self):
        # ``or 1`` falls back when ``pocket_count`` is 0 / falsy; ``max(1, _)``
        # still floors. Both guards must be alive.
        s = _state({"m1": MoldInfo(molde_id="m1", modelo_id="X", pocket_count=0)})
        assert _pocket_count(s, "m1") == 1

    def test_pocket_count_negative_floored_to_one(self):
        # ``or 1`` keeps the truthy ``-3`` so the floor comes from ``max(1, x)``;
        # if that ``1`` is mutated to ``0`` (the most common mutmut survivor)
        # this returns ``-3`` and the test catches it.
        s = _state({"m1": MoldInfo(molde_id="m1", modelo_id="X", pocket_count=-3)})
        assert _pocket_count(s, "m1") == 1


# ---------------------------------------------------------------------------
# 2) classify_rework_phase — substring containment, None safety
# ---------------------------------------------------------------------------

class TestClassifyReworkPhase:
    """Pin keyword containment + None handling.

    Mutations that swap ``in`` for ``==``, remove the ``.lower()``,
    or change the keyword list constants all die in these tests.
    """

    def test_none_both_returns_none(self):
        # Both inputs ``None`` → falsy haystack ``" "`` → no bucket.
        assert classify_rework_phase(None, None) is None

    def test_lixagem_agua_classified(self):
        # Exact PT keyword from the seeded dict.
        assert classify_rework_phase("Lixagem Água", None) == "sanding_water"

    def test_lixagem_polimento_classified(self):
        assert classify_rework_phase("Lixagem polimento", None) == "sanding_polish"

    def test_pintura_acabamento_classified(self):
        assert classify_rework_phase("Pintura Acabamento", None) == "painting_finishing"

    def test_unrelated_phase_returns_none(self):
        assert classify_rework_phase("Cura", "cura_ambiente") is None

    def test_case_insensitive_matching(self):
        # ``.lower()`` mutation would break this branch.
        assert classify_rework_phase(None, "LIXAGEM POLISH") == "sanding_polish"

    def test_phase_id_path_independent_of_name(self):
        # When only ``phase_id`` carries the signature, classification
        # still succeeds — pins the ``haystack`` concat path.
        assert classify_rework_phase(None, "painting finishing v2") == "painting_finishing"

    def test_seed_constants_pinned(self):
        # Defensive: the keyword dict must keep 3 buckets. A mutmut run
        # that empties one of the tuples would still pass the per-keyword
        # tests above (because at least one keyword survives), but this
        # catches "all keywords removed for bucket X" mutations.
        assert set(REWORK_BUFFER_PHASE_KEYWORDS.keys()) == {
            "sanding_water", "sanding_polish", "painting_finishing",
        }
        for bucket, tup in REWORK_BUFFER_PHASE_KEYWORDS.items():
            assert len(tup) >= 1, f"bucket {bucket} lost all keywords"
        # And the buffer percentages reference the same three buckets.
        assert set(DEFAULT_REWORK_BUFFER_PCT.keys()) == set(
            REWORK_BUFFER_PHASE_KEYWORDS.keys()
        )


# ---------------------------------------------------------------------------
# 3) _is_desmolde — startswith vs equality vs endswith
# ---------------------------------------------------------------------------

class TestIsDesmolde:
    """Pin the three independent match clauses:

    * ``phase_name.startswith("desmolde")``
    * ``phase_id == "desmolde"``
    * ``phase_id.endswith(".desmolde")``
    """

    def test_phase_name_exact_lowercase(self):
        op = _op("o", phase_id="PH")
        # Assign phase_name directly — SchedulingOperation doesn't have one
        # by default; the helper reads via ``getattr`` so monkey-attr is fine.
        op.phase_name = "desmolde"
        assert _is_desmolde(op) is True

    def test_phase_name_prefix_only(self):
        op = _op("o", phase_id="OTHER")
        op.phase_name = "Desmolde Final"
        assert _is_desmolde(op) is True

    def test_phase_name_uppercase_normalised(self):
        op = _op("o", phase_id="OTHER")
        op.phase_name = "DESMOLDE"
        assert _is_desmolde(op) is True

    def test_phase_id_equality(self):
        # No phase_name at all — fall to phase_id branch.
        op = _op("o", phase_id="desmolde")
        assert _is_desmolde(op) is True

    def test_phase_id_endswith_dot_desmolde(self):
        # The dotted-namespace variant — ``.endswith(".desmolde")``.
        op = _op("o", phase_id="nelo.fase.desmolde")
        assert _is_desmolde(op) is True

    def test_phase_id_contains_but_not_endswith(self):
        # ``contains`` would be a mutation survivor — we need ``endswith``
        # specifically. ``desmolde_v2`` doesn't end with ``.desmolde``.
        op = _op("o", phase_id="desmolde_v2")
        # Neither equality nor endswith match — must be False.
        assert _is_desmolde(op) is False

    def test_completely_unrelated_returns_false(self):
        op = _op("o", phase_id="laminagem")
        assert _is_desmolde(op) is False

    def test_post_desmolde_phase_names_constant_kept_in_sync(self):
        # Pin the seed set — mutmut emptying this dict would let "desmolde"
        # ops escape the QC buffer.
        assert "desmolde" in {x.lower() for x in POST_DESMOLDE_PHASE_NAMES}


# ---------------------------------------------------------------------------
# 4) _last_on_machine_has_different_family — batch_size tail-skip
# ---------------------------------------------------------------------------

class TestLastOnMachineSetupBoundary:
    """Pin the setup detector's boundary cases:

    * empty ``setup_family`` on the *current* op → never a setup
    * empty ``setup_family`` on the *previous* op → never a setup
    * ``batch_size`` controls how many ScheduledOps from the tail get
      skipped (mutmut may flip ``-tail_skip`` to ``+tail_skip`` or change
      ``max(0, batch_size)`` to ``max(1, batch_size)``)
    * a same-machine prior with a *different* non-empty family → setup
    """

    def test_empty_current_family_returns_false(self):
        op = _op("X", setup_family="")
        prior = _scheduled("A", "M1", "famA")
        assert _last_on_machine_has_different_family(
            "M1", op, [prior], batch_size=0,
        ) is False

    def test_empty_prior_family_returns_false(self):
        op = _op("X", setup_family="famB")
        prior = _scheduled("A", "M1", "")
        assert _last_on_machine_has_different_family(
            "M1", op, [prior], batch_size=0,
        ) is False

    def test_same_family_returns_false(self):
        op = _op("X", setup_family="famA")
        prior = _scheduled("A", "M1", "famA")
        assert _last_on_machine_has_different_family(
            "M1", op, [prior], batch_size=0,
        ) is False

    def test_different_family_returns_true(self):
        op = _op("X", setup_family="famB")
        prior = _scheduled("A", "M1", "famA")
        # batch_size=0 because the prior is NOT part of the current batch —
        # default batch_size=1 would skip it via the tail-skip.
        assert _last_on_machine_has_different_family(
            "M1", op, [prior], batch_size=0,
        ) is True

    def test_different_machine_ignored(self):
        # ``M2`` prior must not influence ``M1`` decision.
        op = _op("X", setup_family="famB")
        prior = _scheduled("A", "M2", "famA")
        assert _last_on_machine_has_different_family(
            "M1", op, [prior], batch_size=0,
        ) is False

    def test_batch_size_skips_recent_tail(self):
        # The 2 tail entries are the *current* batch (just appended).
        # The pre-batch ``famA`` on M1 has a different family → setup=True.
        op = _op("X", setup_family="famB")
        scheduled = [
            _scheduled("A0", "M1", "famA"),      # 2 back — real prior
            _scheduled("CUR1", "M1", "famB"),    # current batch
            _scheduled("CUR2", "M1", "famB"),    # current batch
        ]
        assert _last_on_machine_has_different_family(
            "M1", op, scheduled, batch_size=2,
        ) is True

    def test_batch_size_skips_all_scheduled_when_too_large(self):
        # No prior left after tail-skip → False (no comparator).
        op = _op("X", setup_family="famB")
        scheduled = [
            _scheduled("CUR1", "M1", "famB"),
            _scheduled("CUR2", "M1", "famB"),
        ]
        assert _last_on_machine_has_different_family(
            "M1", op, scheduled, batch_size=2,
        ) is False

    def test_default_batch_size_is_one(self):
        # Default batch_size=1 means we skip the very last entry.
        # So the only thing in ``scheduled`` is the "current batch" tail —
        # there is no prior, so no setup is charged.
        op = _op("X", setup_family="famB")
        scheduled = [_scheduled("CUR", "M1", "famB")]
        assert _last_on_machine_has_different_family("M1", op, scheduled) is False


# ---------------------------------------------------------------------------
# 5) _estimate_utilization — clamp + divisor floor
# ---------------------------------------------------------------------------

class TestEstimateUtilization:
    """Pin ``min(100.0, ...)`` clamp + ``max(1.0, span_min)`` divisor floor.

    Mutmut flipping ``min`` for ``max`` (or removing the ``* 100``) would
    inflate utilisation past sane limits — every test here either pins
    the cap or a known mid-range value.
    """

    def test_no_machines_returns_zero(self):
        # Pin the early return: no division attempted.
        assert _estimate_utilization([], [], T0, T0 + timedelta(hours=1)) == 0.0

    def test_no_scheduled_ops_returns_zero(self):
        ms = [_machine("M1")]
        assert _estimate_utilization(
            [], ms, T0, T0 + timedelta(hours=1),
        ) == 0.0

    def test_half_capacity_returns_fifty(self):
        # 1 machine, horizon=60 min, busy=30 min → 50%.
        ms = [_machine("M1")]
        scheduled = [_scheduled("a", "M1", "f", end_offset_min=30)]
        result = _estimate_utilization(scheduled, ms, T0, T0 + timedelta(minutes=60))
        assert result == 50.0

    def test_full_capacity_returns_hundred(self):
        # 1 machine, 60min horizon, 60min busy → 100% exactly (boundary).
        ms = [_machine("M1")]
        scheduled = [_scheduled("a", "M1", "f", end_offset_min=60)]
        result = _estimate_utilization(scheduled, ms, T0, T0 + timedelta(minutes=60))
        assert result == 100.0

    def test_over_capacity_capped_at_hundred(self):
        # Two ops totalling 120 min on a 60-min horizon — clamp at 100.0.
        # If ``min(100.0, x)`` becomes ``max`` or is removed, this returns 200.0.
        ms = [_machine("M1")]
        scheduled = [
            _scheduled("a", "M1", "f", end_offset_min=60),
            _scheduled("b", "M1", "f", end_offset_min=60),
        ]
        result = _estimate_utilization(scheduled, ms, T0, T0 + timedelta(minutes=60))
        assert result == 100.0

    def test_zero_horizon_doesnt_divide_by_zero(self):
        # ``span_min = max(1.0, ...)`` floor protects against /0.
        ms = [_machine("M1")]
        scheduled = [_scheduled("a", "M1", "f", end_offset_min=0)]
        # horizon_start == horizon_end → span = max(1.0, 0) = 1.0
        result = _estimate_utilization(scheduled, ms, T0, T0)
        # 0 minutes busy, 1 machine, 1 min span → 0%
        assert result == 0.0

    def test_two_machines_halves_utilisation(self):
        # 2 machines, 60min horizon, 60min busy on M1 → 50% (averaged across the fleet).
        ms = [_machine("M1"), _machine("M2")]
        scheduled = [_scheduled("a", "M1", "f", end_offset_min=60)]
        result = _estimate_utilization(scheduled, ms, T0, T0 + timedelta(minutes=60))
        assert result == 50.0


# ---------------------------------------------------------------------------
# 6) _empty_result — every zero/empty field pinned
# ---------------------------------------------------------------------------

class TestEmptyResult:
    """Pin the empty-schedule shape.

    Mutmut may flip ``0.0`` to ``1.0``, drop fields, or change
    ``success: True`` to ``False``. The CPO engine and safety_net rely
    on this exact shape for the "nothing to schedule" branch.
    """

    def test_success_is_true_for_empty(self):
        # Empty input is not a *failure* — it's a vacuously successful schedule.
        r = _empty_result(T0)
        assert r["success"] is True

    def test_engine_used_pinned(self):
        r = _empty_result(T0)
        assert r["engine_used"] == "cpo_v4"

    def test_numeric_kpis_are_zero(self):
        r = _empty_result(T0)
        # Each of these has been a mutmut target in adjacent code paths.
        for key in (
            "makespan_hours",
            "total_tardiness_hours",
            "num_late_orders",
            "setups",
            "routing_variants_applied",
            "backwards_shifts",
            "total_idle_hours",
            "idle_ratio",
            "lam_utilization",
            "idle_pct",
            "tardiness_transport_d",
            "throughput_eur_total",
            "throughput_eur_day",
            "avg_utilization",
        ):
            assert r[key] == 0 or r[key] == 0.0, f"{key} should be zero, got {r[key]!r}"

    def test_warnings_default_empty(self):
        assert _empty_result(T0)["warnings"] == []

    def test_warnings_passthrough(self):
        # The optional argument must actually land on the output —
        # mutmut removing the assignment would surface here.
        r = _empty_result(T0, warnings=["no machines"])
        assert r["warnings"] == ["no machines"]

    def test_warnings_is_independent_copy(self):
        # Pin that ``list(warnings or [])`` defensively copies.
        original = ["x"]
        r = _empty_result(T0, warnings=original)
        original.append("y")
        assert r["warnings"] == ["x"]


# ---------------------------------------------------------------------------
# 7) compute_mold_batches — singleton vs urgency window
# ---------------------------------------------------------------------------

class TestComputeMoldBatches:
    """Pin the boundary between "no batch" and "urgent singleton batch":

    * empty ops → ``{}``
    * single op without due_date → no batch
    * single op due 4 days out → no batch (URGENCY_DAYS=3)
    * single op due 2 days out → urgent batch emitted
    * pocket_count <= 1 → never batched
    """

    def test_empty_returns_empty(self):
        assert compute_mold_batches([], _state()) == {}

    def test_pocket_count_one_skipped(self):
        # ``if pocket_count <= 1: continue`` — pin the boundary at 1.
        state = _state({"mA": MoldInfo(molde_id="mA", modelo_id="MOD", pocket_count=1)})
        ops = [
            _op("op1", mold_required=True, model_id="MOD", mold_id="mA"),
            _op("op2", mold_required=True, model_id="MOD", mold_id="mA"),
        ]
        # pocket_count==1 means single-slot — never batched.
        assert compute_mold_batches(ops, state) == {}

    def test_pocket_count_two_batches_two_ops(self):
        # Smallest viable pocket_count (2) groups two non-conflicting peers.
        state = _state({"mA": MoldInfo(molde_id="mA", modelo_id="MOD", pocket_count=2)})
        ops = [
            SchedulingOperation(
                operation_id="op1", order_id="O1", product_id="P", sequence=1,
                operation_code="op1", duration_minutes=60.0, machine_id="M1",
                phase_id="PH", mold_required=True, model_id="MOD", mold_id="mA",
            ),
            SchedulingOperation(
                operation_id="op2", order_id="O2", product_id="P", sequence=1,
                operation_code="op2", duration_minutes=60.0, machine_id="M1",
                phase_id="PH", mold_required=True, model_id="MOD", mold_id="mA",
            ),
        ]
        result = compute_mold_batches(ops, state)
        assert len(result) == 2
        # Both ops share the same batch_id.
        assert result["op1"] == result["op2"]

    def test_singleton_without_due_date_not_batched(self):
        state = _state({"mA": MoldInfo(molde_id="mA", modelo_id="MOD", pocket_count=4)})
        op = SchedulingOperation(
            operation_id="lonely", order_id="O1", product_id="P", sequence=1,
            operation_code="lonely", duration_minutes=60.0, machine_id="M1",
            phase_id="PH", mold_required=True, model_id="MOD", mold_id="mA",
            # due_date stays None — no urgency anchor.
        )
        # No due_date → no batch (the urgency branch is skipped).
        assert compute_mold_batches([op], state) == {}

    def test_singleton_due_far_future_not_batched(self):
        # Due 10 days out — outside URGENCY_DAYS=3 window.
        state = _state({"mA": MoldInfo(molde_id="mA", modelo_id="MOD", pocket_count=4)})
        op = SchedulingOperation(
            operation_id="lonely", order_id="O1", product_id="P", sequence=1,
            operation_code="lonely", duration_minutes=60.0, machine_id="M1",
            phase_id="PH", mold_required=True, model_id="MOD", mold_id="mA",
            due_date=datetime.utcnow() + timedelta(days=10),
        )
        assert compute_mold_batches([op], state) == {}

    def test_singleton_due_within_urgency_window_batched(self):
        # Due 1 day out — inside URGENCY_DAYS=3 → urgent singleton batch.
        state = _state({"mA": MoldInfo(molde_id="mA", modelo_id="MOD", pocket_count=4)})
        op = SchedulingOperation(
            operation_id="urgent", order_id="O1", product_id="P", sequence=1,
            operation_code="urgent", duration_minutes=60.0, machine_id="M1",
            phase_id="PH", mold_required=True, model_id="MOD", mold_id="mA",
            due_date=datetime.utcnow() + timedelta(days=1),
        )
        result = compute_mold_batches([op], state)
        assert "urgent" in result
        # The urgent flag is baked into the batch_id.
        assert "urgent" in result["urgent"]
