"""
Tests for src.plan.cpo.decoder.decode + CPOv4Engine + safety_net.

Strategy: synthetic operations + machines + in-memory FactoryState
(no DB, no real Excel data). Focus on the greedy-decoder invariants:
precedence, machine no-overlap, worker no-overlap, mold exclusivity,
team_size honoured, deterministic for same seed.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List
from uuid import UUID, uuid4

import pytest

from src.plan.cpo.chromosome import Chromosome
from src.plan.cpo.decoder import decode
from src.plan.cpo.engine import CPOConfig, CPOv4Engine
from src.plan.cpo.fitness import FitnessConfig, compute_fitness
from src.plan.cpo.safety_net import apply_safety_net, is_worse_than_baseline
from src.plan.cpo.state import FactoryState, MoldInfo
from src.plan.engines.scheduling_adapter import SchedulingMachine, SchedulingOperation


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

HORIZON_START = datetime(2026, 4, 20, 8, 0, 0)
HORIZON_END = HORIZON_START + timedelta(days=14)


def _state_with_workers(workers_per_phase) -> FactoryState:
    s = FactoryState(tenant_id=UUID("11111111-1111-1111-1111-111111111111"))
    s.skill_matrix = {phase: set(workers) for phase, workers in workers_per_phase.items()}
    return s


def _op(op_id, order_id, sequence, duration_min, machine=None, **kwargs):
    return SchedulingOperation(
        operation_id=op_id,
        order_id=order_id,
        product_id=kwargs.pop("product_id", "P1"),
        sequence=sequence,
        operation_code=kwargs.pop("operation_code", "OP"),
        duration_minutes=duration_min,
        machine_id=machine,
        **kwargs,
    )


def _machines(n=2) -> List[SchedulingMachine]:
    return [SchedulingMachine(machine_id=f"M{i+1}", name=f"Machine {i+1}") for i in range(n)]


# ---------------------------------------------------------------------------
# Decoder invariants
# ---------------------------------------------------------------------------

class TestDecoderInvariants:
    def test_empty_ops_returns_empty(self):
        state = _state_with_workers({})
        chromo = Chromosome.identity(0)
        result = decode(chromo, [], _machines(1), state, HORIZON_START, HORIZON_END)
        assert result["operations"] == []
        assert result["makespan_hours"] == 0.0

    def test_preserves_intra_order_precedence(self):
        state = _state_with_workers({})
        ops = [
            _op("o1-s2", "O1", sequence=2, duration_min=60, machine="M1"),
            _op("o1-s1", "O1", sequence=1, duration_min=60, machine="M1"),
        ]
        # Chromosome puts s2 BEFORE s1 — decoder must still honour seq order
        chromo = Chromosome(permutation=[0, 1])
        result = decode(chromo, ops, _machines(1), state, HORIZON_START, HORIZON_END)

        ordered = sorted(result["operations"], key=lambda o: o["start_time"])
        assert ordered[0]["operation_id"] == "o1-s1"
        assert ordered[1]["operation_id"] == "o1-s2"

    def test_no_machine_overlap_same_time(self):
        state = _state_with_workers({})
        # 2 ops on same machine must serialize
        ops = [
            _op("a", "O1", sequence=1, duration_min=60, machine="M1"),
            _op("b", "O2", sequence=1, duration_min=60, machine="M1"),
        ]
        chromo = Chromosome(permutation=[0, 1])
        result = decode(chromo, ops, _machines(1), state, HORIZON_START, HORIZON_END)

        ops_out = {o["operation_id"]: o for o in result["operations"]}
        # One must end before the other starts
        end_a = datetime.fromisoformat(ops_out["a"]["end_time"])
        start_b = datetime.fromisoformat(ops_out["b"]["start_time"])
        assert end_a <= start_b

    def test_no_worker_overlap_when_team_size_applies(self):
        # Single worker; two ops on different machines but both need that worker
        state = _state_with_workers({"PHASE1": ["W1"]})
        ops = [
            _op("a", "O1", sequence=1, duration_min=60, machine="M1",
                phase_id="PHASE1", team_size=1),
            _op("b", "O2", sequence=1, duration_min=60, machine="M2",
                phase_id="PHASE1", team_size=1),
        ]
        chromo = Chromosome(permutation=[0, 1])
        result = decode(chromo, ops, _machines(2), state, HORIZON_START, HORIZON_END)

        ops_out = {o["operation_id"]: o for o in result["operations"]}
        assert "W1" in ops_out["a"]["workers"]
        assert "W1" in ops_out["b"]["workers"]
        # The worker must not be double-booked
        end_a = datetime.fromisoformat(ops_out["a"]["end_time"])
        start_b = datetime.fromisoformat(ops_out["b"]["start_time"])
        assert end_a <= start_b

    def test_team_size_two_assigns_pair(self):
        state = _state_with_workers({"LAMINAGEM": ["W1", "W2", "W3"]})
        ops = [
            _op("a", "O1", sequence=1, duration_min=60, machine="M1",
                phase_id="LAMINAGEM", team_size=2),
        ]
        chromo = Chromosome(permutation=[0])
        result = decode(chromo, ops, _machines(1), state, HORIZON_START, HORIZON_END)
        assert len(result["operations"][0]["workers"]) == 2

    def test_team_size_two_infeasible_when_pool_too_small(self):
        state = _state_with_workers({"LAMINAGEM": ["W1"]})
        ops = [
            _op("a", "O1", sequence=1, duration_min=60, machine="M1",
                phase_id="LAMINAGEM", team_size=2),
        ]
        chromo = Chromosome(permutation=[0])
        result = decode(chromo, ops, _machines(1), state, HORIZON_START, HORIZON_END)
        assert "a" in result["infeasible_op_ids"]

    def test_mold_exclusivity(self):
        state = _state_with_workers({})
        state.molds = {"MLD1": MoldInfo("MLD1", "M1", pocket_count=1)}
        state.molds_by_model = {"M1": [state.molds["MLD1"]]}

        ops = [
            _op("a", "O1", sequence=1, duration_min=60, machine="M1",
                mold_required=True, model_id="M1", mold_id="MLD1"),
            _op("b", "O2", sequence=1, duration_min=60, machine="M2",
                mold_required=True, model_id="M1", mold_id="MLD1"),
        ]
        chromo = Chromosome(permutation=[0, 1])
        result = decode(chromo, ops, _machines(2), state, HORIZON_START, HORIZON_END)

        ops_out = {o["operation_id"]: o for o in result["operations"]}
        end_a = datetime.fromisoformat(ops_out["a"]["end_time"])
        start_b = datetime.fromisoformat(ops_out["b"]["start_time"])
        assert end_a <= start_b

    def test_is_deterministic(self):
        state = _state_with_workers({"P": ["W1", "W2"]})
        ops = [
            _op("a", "O1", sequence=1, duration_min=30, machine="M1", phase_id="P"),
            _op("b", "O1", sequence=2, duration_min=30, machine="M1", phase_id="P"),
            _op("c", "O2", sequence=1, duration_min=45, machine="M2", phase_id="P"),
        ]
        chromo = Chromosome(permutation=[0, 1, 2])

        result_a = decode(chromo, ops, _machines(2), state, HORIZON_START, HORIZON_END)
        result_b = decode(chromo, ops, _machines(2), state, HORIZON_START, HORIZON_END)

        assert result_a["makespan_hours"] == result_b["makespan_hours"]
        assert [o["operation_id"] for o in result_a["operations"]] == \
               [o["operation_id"] for o in result_b["operations"]]


# ---------------------------------------------------------------------------
# Safety net
# ---------------------------------------------------------------------------

class TestSafetyNet:
    def test_candidate_worse_tardy_count_is_rejected(self):
        baseline = {"num_late_orders": 1, "total_tardiness_hours": 5.0}
        candidate = {"num_late_orders": 3, "total_tardiness_hours": 2.0}
        assert is_worse_than_baseline(candidate, baseline) is True

        out = apply_safety_net(candidate, baseline)
        assert out["safety_net_triggered"] is True
        assert out["num_late_orders"] == 1

    def test_candidate_better_keeps_it(self):
        baseline = {"num_late_orders": 3, "total_tardiness_hours": 10.0}
        candidate = {"num_late_orders": 1, "total_tardiness_hours": 2.0}
        out = apply_safety_net(candidate, baseline)
        assert out["safety_net_triggered"] is False
        assert out["num_late_orders"] == 1

    def test_equal_keeps_candidate(self):
        baseline = {"num_late_orders": 2, "total_tardiness_hours": 4.0}
        candidate = {"num_late_orders": 2, "total_tardiness_hours": 4.0}
        out = apply_safety_net(candidate, baseline)
        assert out["safety_net_triggered"] is False


# ---------------------------------------------------------------------------
# Fitness
# ---------------------------------------------------------------------------

class TestFitness:
    def test_zero_schedule_is_zero_fitness(self):
        assert compute_fitness({}, FitnessConfig()) == 0.0

    def test_tardiness_dominates_makespan(self):
        a = {"makespan_hours": 100, "total_tardiness_hours": 0}
        b = {"makespan_hours": 50, "total_tardiness_hours": 10}
        # With w_tardiness=10, w_makespan=1 — b scores 150, a scores 100 ⇒ a wins
        assert compute_fitness(a) < compute_fitness(b)

    def test_safety_penalty_is_dominant(self):
        clean = {"makespan_hours": 1000}
        violated = {"makespan_hours": 1, "safety_violated": True}
        assert compute_fitness(clean) < compute_fitness(violated)


# ---------------------------------------------------------------------------
# CPOv4Engine end-to-end on tiny synthetic problem
# ---------------------------------------------------------------------------

class TestCPOEngineSmoke:
    def test_single_order_single_machine(self):
        state = _state_with_workers({"P": ["W1"]})
        ops = [
            _op(f"o1-s{i}", "O1", sequence=i, duration_min=30, machine="M1",
                phase_id="P", team_size=1)
            for i in range(1, 4)
        ]
        engine = CPOv4Engine(
            state=state,
            config=CPOConfig(population_size=10, generations=5, time_limit_sec=5, seed=1),
        )
        result = engine.schedule(ops, _machines(1), HORIZON_START, HORIZON_END)

        assert result["success"] is True
        assert len(result["operations"]) == 3
        assert result["engine_used"] == "cpo_v4"
        assert result["num_late_orders"] == 0
        assert "cpo_meta" in result

    def test_engine_respects_time_budget(self):
        import time
        state = _state_with_workers({"P": ["W1", "W2", "W3", "W4"]})
        ops = [
            _op(f"o{i}-s1", f"O{i}", sequence=1, duration_min=30,
                machine="M1", phase_id="P")
            for i in range(20)
        ]
        engine = CPOv4Engine(
            state=state,
            config=CPOConfig(
                population_size=20,
                generations=200,    # large, budget should cut it short
                time_limit_sec=2.0,
                seed=1,
            ),
        )
        t0 = time.time()
        engine.schedule(ops, _machines(2), HORIZON_START, HORIZON_END)
        elapsed = time.time() - t0
        # Allow 2x slack for slow CI; must not run for the full 200 generations
        assert elapsed < 6.0

    def test_baseline_is_seeded_into_population(self):
        """Baseline (identity chromosome) must always be evaluated; ensures
        safety-net comparison has a real baseline to fall back to."""
        state = _state_with_workers({})
        ops = [
            _op("a", "O1", sequence=1, duration_min=30, machine="M1"),
            _op("b", "O1", sequence=2, duration_min=30, machine="M1"),
        ]
        engine = CPOv4Engine(
            state=state,
            config=CPOConfig(population_size=5, generations=3, seed=7),
        )
        result = engine.schedule(ops, _machines(1), HORIZON_START, HORIZON_END)
        assert result["cpo_meta"]["baseline_fitness"] >= 0
