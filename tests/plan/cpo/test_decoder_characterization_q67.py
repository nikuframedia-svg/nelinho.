"""
Q.67.6.A3 — Characterization tests for src.plan.cpo.decoder.decode.

Purpose
=======
Pin the ACTUAL end-to-end behaviour of the heuristic decoder *before*
Q.67.6.B3 carves it into sub-modules. Where Q.67.3.B (mutation-pin)
hammers atomic helpers (_pocket_count, _is_desmolde, ...), this file
sits one layer above and locks the contract of ``decode(...)``:

* return dict schema (keys + types + rounding)
* end-to-end pipeline sub-phases identified from decoder.py L235-731:
    1. _empty_result short-circuit (no ops / no machines)
    2. chromosome permutation sanitisation (out-of-range / duplicates / missing)
    3. precedence resolution (intra-order sequence + predecessor_ops)
    4. mould-batch pre-computation (compute_mold_batches integration)
    5. resource selection (machine, workers, mould) per peer
    6. backward target_start application
    7. calendar snapping (FactoryState.calendar=None → 24/7 legacy path)
    8. timeline aggregation (machine_free_at / worker_free_at / mold_free_at)
    9. KPI accumulation (makespan, tardiness, idle, MAP-Elites axes, throughput)
   10. soft-horizon success flag + infeasible bookkeeping

If a sub-module rewrite shifts any of these contracts, at least one
test here MUST fail — that's the characterization point.

ZERO MOCKS: synthetic SchedulingOperation/SchedulingMachine + bare
FactoryState. No DB, no fixtures of legacy data.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

import pytest

from src.plan.cpo.chromosome import Chromosome
from src.plan.cpo.decoder import (
    _empty_result,
    decode,
)
from src.plan.cpo.state import FactoryState, MoldInfo
from src.plan.engines.scheduling_adapter import (
    SchedulingMachine,
    SchedulingOperation,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

HORIZON_START = datetime(2026, 5, 1, 8, 0, 0)
HORIZON_END = HORIZON_START + timedelta(days=7)
TENANT = UUID("11111111-1111-1111-1111-111111111111")


def _state(
    *,
    skills: Optional[Dict[str, List[str]]] = None,
    molds: Optional[Dict[str, MoldInfo]] = None,
    molds_by_model: Optional[Dict[str, List[MoldInfo]]] = None,
) -> FactoryState:
    s = FactoryState(tenant_id=TENANT)
    if skills:
        s.skill_matrix = {phase: set(workers) for phase, workers in skills.items()}
    if molds:
        s.molds = dict(molds)
    if molds_by_model:
        s.molds_by_model = molds_by_model
    return s


def _op(
    op_id: str,
    order_id: str,
    sequence: int,
    duration_min: float,
    *,
    machine: Optional[str] = "M1",
    phase_id: Optional[str] = None,
    team_size: int = 1,
    mold_required: bool = False,
    model_id: str = "",
    mold_id: Optional[str] = None,
    predecessor_ops: Optional[List[str]] = None,
    due_date: Optional[datetime] = None,
    product_id: str = "P1",
    setup_family: str = "",
) -> SchedulingOperation:
    return SchedulingOperation(
        operation_id=op_id,
        order_id=order_id,
        product_id=product_id,
        sequence=sequence,
        operation_code="OP",
        duration_minutes=duration_min,
        machine_id=machine,
        phase_id=phase_id,
        team_size=team_size,
        mold_required=mold_required,
        model_id=model_id,
        mold_id=mold_id,
        predecessor_ops=list(predecessor_ops or []),
        due_date=due_date,
        setup_family=setup_family,
    )


def _machines(n: int = 1) -> List[SchedulingMachine]:
    return [
        SchedulingMachine(machine_id=f"M{i + 1}", name=f"Machine {i + 1}")
        for i in range(n)
    ]


# Canonical result-schema keys, pinned so a refactor can't silently drop one.
RESULT_KEYS = {
    "success",
    "engine_used",
    "operations",
    "makespan_hours",
    "total_tardiness_hours",
    "num_late_orders",
    "otd_delivery",
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
    "warnings",
    "infeasible_op_ids",
}

# Canonical per-operation dict schema.
OP_KEYS = {
    "operation_id",
    "order_id",
    "phase_id",
    "machine_id",
    "workers",
    "mold_id",
    "mold_batch_id",
    "start_time",
    "end_time",
    "duration_minutes",
    "setup_family",
}


# ---------------------------------------------------------------------------
# Sub-phase 1 — _empty_result short-circuit
# ---------------------------------------------------------------------------


class TestEmptyShortCircuit:
    def test_no_ops_returns_empty_result_with_full_schema(self):
        # _empty_result lacks otd_delivery → schema is a superset minus that key.
        result = decode(
            Chromosome.identity(0), [], _machines(1), _state(),
            HORIZON_START, HORIZON_END,
        )
        # Pin the exact keys produced by _empty_result.
        empty = _empty_result(HORIZON_START)
        assert set(result.keys()) == set(empty.keys())
        assert result["operations"] == []
        assert result["makespan_hours"] == 0.0
        assert result["engine_used"] == "cpo_v4"
        assert result["success"] is True
        assert result["warnings"] == []
        assert result["infeasible_op_ids"] == []

    def test_no_machines_emits_warning_and_short_circuits(self):
        ops = [_op("a", "O1", 1, 60)]
        result = decode(
            Chromosome.identity(1), ops, [], _state(),
            HORIZON_START, HORIZON_END,
        )
        assert result["operations"] == []
        assert "No machines available" in result["warnings"]


# ---------------------------------------------------------------------------
# Sub-phase 2 — chromosome permutation sanitisation
# ---------------------------------------------------------------------------


class TestPermutationSanitisation:
    def test_out_of_range_indices_are_dropped_and_missing_appended(self):
        # 2 ops; permutation references index 99 (oob) + 0, missing 1.
        ops = [
            _op("a", "O1", 1, 30, machine="M1"),
            _op("b", "O2", 1, 30, machine="M1"),
        ]
        chromo = Chromosome(permutation=[99, 0])
        result = decode(
            chromo, ops, _machines(1), _state(),
            HORIZON_START, HORIZON_END,
        )
        # Both ops still scheduled despite malformed perm.
        ids = {o["operation_id"] for o in result["operations"]}
        assert ids == {"a", "b"}

    def test_duplicate_indices_are_deduped_each_op_runs_once(self):
        ops = [
            _op("a", "O1", 1, 30, machine="M1"),
            _op("b", "O2", 1, 30, machine="M1"),
        ]
        chromo = Chromosome(permutation=[0, 0, 1, 1])
        result = decode(
            chromo, ops, _machines(1), _state(),
            HORIZON_START, HORIZON_END,
        )
        ids = [o["operation_id"] for o in result["operations"]]
        # Each op appears exactly once (no double-schedule).
        assert sorted(ids) == ["a", "b"]


# ---------------------------------------------------------------------------
# Sub-phase 3 — precedence resolution
# ---------------------------------------------------------------------------


class TestPrecedence:
    def test_intra_order_sequence_enforced_even_when_reordered_by_chromo(self):
        ops = [
            _op("o1-s2", "O1", 2, 30, machine="M1"),
            _op("o1-s1", "O1", 1, 30, machine="M1"),
        ]
        # Chromo: s2 first
        chromo = Chromosome(permutation=[0, 1])
        result = decode(
            chromo, ops, _machines(1), _state(),
            HORIZON_START, HORIZON_END,
        )
        ordered = sorted(result["operations"], key=lambda o: o["start_time"])
        assert ordered[0]["operation_id"] == "o1-s1"
        assert ordered[1]["operation_id"] == "o1-s2"

    def test_explicit_predecessor_ops_block_until_pred_scheduled(self):
        ops = [
            _op("downstream", "O1", 1, 30, machine="M1",
                predecessor_ops=["upstream"]),
            _op("upstream", "O2", 1, 30, machine="M2"),
        ]
        chromo = Chromosome(permutation=[0, 1])
        result = decode(
            chromo, ops, _machines(2), _state(),
            HORIZON_START, HORIZON_END,
        )
        ops_out = {o["operation_id"]: o for o in result["operations"]}
        end_up = datetime.fromisoformat(ops_out["upstream"]["end_time"])
        start_down = datetime.fromisoformat(ops_out["downstream"]["start_time"])
        assert start_down >= end_up

    def test_unsatisfiable_predecessor_triggers_deadlock_warning(self):
        # Predecessor "ghost" never exists; deadlock fallback marks op infeasible.
        ops = [
            _op("orphan", "O1", 1, 30, machine="M1",
                predecessor_ops=["ghost"]),
        ]
        chromo = Chromosome(permutation=[0])
        result = decode(
            chromo, ops, _machines(1), _state(),
            HORIZON_START, HORIZON_END,
        )
        assert "orphan" in result["infeasible_op_ids"]
        assert any("deadlock" in w.lower() for w in result["warnings"])


# ---------------------------------------------------------------------------
# Sub-phase 5 — resource selection (machine / workers / mould)
# ---------------------------------------------------------------------------


class TestResourceSelection:
    def test_machine_no_overlap_on_same_machine(self):
        ops = [
            _op("a", "O1", 1, 60, machine="M1"),
            _op("b", "O2", 1, 60, machine="M1"),
        ]
        chromo = Chromosome(permutation=[0, 1])
        result = decode(
            chromo, ops, _machines(1), _state(),
            HORIZON_START, HORIZON_END,
        )
        ops_out = {o["operation_id"]: o for o in result["operations"]}
        end_a = datetime.fromisoformat(ops_out["a"]["end_time"])
        start_b = datetime.fromisoformat(ops_out["b"]["start_time"])
        assert end_a <= start_b

    def test_worker_no_overlap_across_machines(self):
        # Shared single worker forces serialisation despite separate machines.
        ops = [
            _op("a", "O1", 1, 60, machine="M1", phase_id="P", team_size=1),
            _op("b", "O2", 1, 60, machine="M2", phase_id="P", team_size=1),
        ]
        chromo = Chromosome(permutation=[0, 1])
        result = decode(
            chromo, ops, _machines(2), _state(skills={"P": ["W1"]}),
            HORIZON_START, HORIZON_END,
        )
        ops_out = {o["operation_id"]: o for o in result["operations"]}
        end_a = datetime.fromisoformat(ops_out["a"]["end_time"])
        start_b = datetime.fromisoformat(ops_out["b"]["start_time"])
        assert end_a <= start_b

    def test_no_skill_pool_logs_manual_warning_when_skill_matrix_set(self):
        # phase_id with no matching skill → warning + scheduled as manual.
        state = _state(skills={"OTHER_PHASE": ["W1"]})
        ops = [_op("a", "O1", 1, 30, machine="M1", phase_id="UNSEEN_PHASE")]
        chromo = Chromosome(permutation=[0])
        result = decode(
            chromo, ops, _machines(1), state,
            HORIZON_START, HORIZON_END,
        )
        assert any("skill_matrix" in w for w in result["warnings"])
        # Scheduled with no workers but not infeasible.
        assert result["operations"][0]["workers"] == []
        assert "a" not in result["infeasible_op_ids"]

    def test_mold_required_without_resolution_marks_infeasible(self):
        # mold_required=True, mold_id unset, no molds_by_model → infeasible.
        ops = [_op(
            "a", "O1", 1, 30, machine="M1",
            mold_required=True, model_id="UNKNOWN",
        )]
        chromo = Chromosome(permutation=[0])
        result = decode(
            chromo, ops, _machines(1), _state(),
            HORIZON_START, HORIZON_END,
        )
        assert "a" in result["infeasible_op_ids"]

    def test_mold_exclusivity_serialises_same_mould(self):
        # Two ops competing for the same single-pocket mould.
        mold = MoldInfo("MLD1", "MOD1", pocket_count=1)
        state = _state(
            molds={"MLD1": mold},
            molds_by_model={"MOD1": [mold]},
        )
        ops = [
            _op("a", "O1", 1, 60, machine="M1",
                mold_required=True, model_id="MOD1", mold_id="MLD1"),
            _op("b", "O2", 1, 60, machine="M2",
                mold_required=True, model_id="MOD1", mold_id="MLD1"),
        ]
        chromo = Chromosome(permutation=[0, 1])
        result = decode(
            chromo, ops, _machines(2), state,
            HORIZON_START, HORIZON_END,
        )
        ops_out = {o["operation_id"]: o for o in result["operations"]}
        end_a = datetime.fromisoformat(ops_out["a"]["end_time"])
        start_b = datetime.fromisoformat(ops_out["b"]["start_time"])
        assert end_a <= start_b


# ---------------------------------------------------------------------------
# Sub-phase 6 — backward target_start application
# ---------------------------------------------------------------------------


class TestBackwardScheduling:
    def test_forward_chromosome_starts_at_horizon(self):
        ops = [_op("a", "O1", 1, 60, machine="M1")]
        chromo = Chromosome(permutation=[0], schedule_direction="forward")
        result = decode(
            chromo, ops, _machines(1), _state(),
            HORIZON_START, HORIZON_END,
        )
        start = datetime.fromisoformat(result["operations"][0]["start_time"])
        assert start == HORIZON_START
        assert result["backwards_shifts"] == 0

    def test_backward_chromosome_shifts_op_toward_due_date(self):
        due = HORIZON_START + timedelta(days=3)
        ops = [_op("a", "O1", 1, 60, machine="M1", due_date=due)]
        chromo = Chromosome(permutation=[0], schedule_direction="backward")
        result = decode(
            chromo, ops, _machines(1), _state(),
            HORIZON_START, HORIZON_END,
        )
        start = datetime.fromisoformat(result["operations"][0]["start_time"])
        # The op should be pushed near `due - duration` instead of at horizon.
        assert start > HORIZON_START
        assert result["backwards_shifts"] >= 1


# ---------------------------------------------------------------------------
# Sub-phase 9 — KPI accumulation
# ---------------------------------------------------------------------------


class TestKPIAccumulation:
    def test_result_dict_has_full_schema(self):
        ops = [_op("a", "O1", 1, 60, machine="M1")]
        result = decode(
            Chromosome.identity(1), ops, _machines(1), _state(),
            HORIZON_START, HORIZON_END,
        )
        assert set(result.keys()) == RESULT_KEYS
        # Numeric rounding contract: 2 decimals for hours/percentages, 4 for ratios.
        assert isinstance(result["makespan_hours"], float)
        assert isinstance(result["otd_delivery"], float)
        assert isinstance(result["idle_ratio"], float)

    def test_operation_dict_has_full_schema(self):
        ops = [_op("a", "O1", 1, 60, machine="M1")]
        result = decode(
            Chromosome.identity(1), ops, _machines(1), _state(),
            HORIZON_START, HORIZON_END,
        )
        assert set(result["operations"][0].keys()) == OP_KEYS

    def test_otd_vacuous_one_when_no_due_dates(self):
        # No due_date set on any op → otd_delivery is vacuously 1.0.
        ops = [_op("a", "O1", 1, 30, machine="M1")]
        result = decode(
            Chromosome.identity(1), ops, _machines(1), _state(),
            HORIZON_START, HORIZON_END,
        )
        assert result["otd_delivery"] == 1.0
        assert result["num_late_orders"] == 0

    def test_late_order_increments_tardiness_and_drops_otd(self):
        # 1-hour op, but due_date is BEFORE the horizon start → tardy.
        due = HORIZON_START - timedelta(hours=1)
        ops = [_op("a", "O1", 1, 60, machine="M1", due_date=due)]
        result = decode(
            Chromosome.identity(1), ops, _machines(1), _state(),
            HORIZON_START, HORIZON_END,
        )
        assert result["num_late_orders"] == 1
        assert result["total_tardiness_hours"] > 0
        # otd_delivery = 1 - 1/1 = 0
        assert result["otd_delivery"] == 0.0

    def test_throughput_eur_day_zero_without_price_mapping(self):
        ops = [_op("a", "O1", 1, 60, machine="M1", product_id="P1")]
        result = decode(
            Chromosome.identity(1), ops, _machines(1), _state(),
            HORIZON_START, HORIZON_END,
        )
        # Legacy callers don't pass product_price_eur — must default to 0.
        assert result["throughput_eur_day"] == 0.0
        assert result["throughput_eur_total"] == 0.0

    def test_throughput_eur_day_uses_last_op_per_order(self):
        # Two-phase order; price tied to product_id; only final op contributes.
        ops = [
            _op("a", "O1", 1, 30, machine="M1", product_id="P1"),
            _op("b", "O1", 2, 30, machine="M1", product_id="P1"),
        ]
        result = decode(
            Chromosome.identity(2), ops, _machines(1), _state(),
            HORIZON_START, HORIZON_END,
            product_price_eur={"P1": 1000.0},
        )
        assert result["throughput_eur_total"] == 1000.0
        assert result["throughput_eur_day"] > 0.0

    def test_setups_counted_on_machine_when_setup_family_changes(self):
        # Two ops same machine, different setup_family → one setup counted.
        ops = [
            _op("a", "O1", 1, 30, machine="M1", setup_family="GREEN"),
            _op("b", "O2", 1, 30, machine="M1", setup_family="BLUE"),
        ]
        chromo = Chromosome(permutation=[0, 1])
        result = decode(
            chromo, ops, _machines(1), _state(),
            HORIZON_START, HORIZON_END,
        )
        assert result["setups"] >= 1

    def test_setups_zero_when_setup_family_unset(self):
        # Empty setup_family is conservative → no setups inflated.
        ops = [
            _op("a", "O1", 1, 30, machine="M1", setup_family=""),
            _op("b", "O2", 1, 30, machine="M1", setup_family=""),
        ]
        chromo = Chromosome(permutation=[0, 1])
        result = decode(
            chromo, ops, _machines(1), _state(),
            HORIZON_START, HORIZON_END,
        )
        assert result["setups"] == 0

    def test_idle_ratio_in_zero_one_range_and_idle_pct_is_percentage(self):
        ops = [
            _op("a", "O1", 1, 60, machine="M1", phase_id="P", team_size=1),
        ]
        result = decode(
            Chromosome.identity(1), ops, _machines(1),
            _state(skills={"P": ["W1", "W2"]}),
            HORIZON_START, HORIZON_END,
        )
        assert 0.0 <= result["idle_ratio"] <= 1.0
        # idle_pct = idle_ratio * 100 (within 0.5 due to rounding)
        assert abs(result["idle_pct"] - result["idle_ratio"] * 100.0) < 0.5

    def test_lam_utilization_high_when_only_laminagem_phase(self):
        ops = [_op("a", "O1", 1, 60, machine="M1", phase_id="LAMINAGEM")]
        result = decode(
            Chromosome.identity(1), ops, _machines(1), _state(),
            HORIZON_START, HORIZON_END,
        )
        # All scheduled minutes are laminagem → ~100%.
        assert result["lam_utilization"] == 100.0


# ---------------------------------------------------------------------------
# Sub-phase 10 — soft-horizon success + infeasible bookkeeping
# ---------------------------------------------------------------------------


class TestSoftHorizonAndSuccessFlag:
    def test_success_true_when_all_ops_fit(self):
        ops = [_op("a", "O1", 1, 30, machine="M1")]
        result = decode(
            Chromosome.identity(1), ops, _machines(1), _state(),
            HORIZON_START, HORIZON_END,
        )
        assert result["success"] is True
        assert result["infeasible_op_ids"] == []

    def test_success_false_when_op_exceeds_horizon(self):
        # Op longer than the entire horizon → soft-horizon flag.
        short_end = HORIZON_START + timedelta(minutes=10)
        ops = [_op("a", "O1", 1, 60, machine="M1")]
        result = decode(
            Chromosome.identity(1), ops, _machines(1), _state(),
            HORIZON_START, short_end,
        )
        assert result["success"] is False
        assert "a" in result["infeasible_op_ids"]
        assert any("exceeds horizon" in w for w in result["warnings"])


# ---------------------------------------------------------------------------
# Sub-phase 9b — determinism (cross-call reproducibility)
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_two_calls_with_same_inputs_produce_identical_output(self):
        state = _state(skills={"P": ["W1", "W2", "W3"]})
        ops = [
            _op("a", "O1", 1, 30, machine="M1", phase_id="P", team_size=1),
            _op("b", "O1", 2, 45, machine="M1", phase_id="P", team_size=1),
            _op("c", "O2", 1, 60, machine="M2", phase_id="P", team_size=1),
        ]
        chromo = Chromosome(permutation=[2, 0, 1])
        result_a = decode(
            chromo, ops, _machines(2), state, HORIZON_START, HORIZON_END,
        )
        result_b = decode(
            chromo, ops, _machines(2), state, HORIZON_START, HORIZON_END,
        )
        assert result_a["makespan_hours"] == result_b["makespan_hours"]
        assert result_a["setups"] == result_b["setups"]
        assert [o["operation_id"] for o in result_a["operations"]] == \
               [o["operation_id"] for o in result_b["operations"]]
        assert [o["start_time"] for o in result_a["operations"]] == \
               [o["start_time"] for o in result_b["operations"]]
