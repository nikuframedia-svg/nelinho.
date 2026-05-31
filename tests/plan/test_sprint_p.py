"""
Sprint P — focused tests for the new pieces.

Covers: CPOConfig budgets, fitness v2.0 weights + truck_consolidation,
MAP-Elites v2.0 axes, chromosome routing_choices, greedy pipeline,
pair assignment, replan hook, routing mining, transport service,
POETIQ expanded loop, CP-SAT L-RHO stub.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from src.plan.cpo.chromosome import Chromosome
from src.plan.cpo.engine import CPOConfig
from src.plan.cpo.fitness import FitnessConfig, compute_fitness
from src.plan.cpo.greedy_pipeline import GreedyPipeline, PHASE_BUDGETS_S
from src.plan.cpo.mapelites import MAPElites3D
from src.plan.cpo.pair_assignment import (
    assign_pairs_for_ops,
    requires_pair,
)
from src.copilot.poetiq_expanded import (
    CritiqueReport,
    POETIQLoop,
    default_perturbation_tester,
)
from src.plan.engines.cpsat_lrho import CPSATLRHO, LRHOConfig
from src.plan.services.replan_hook import (
    handle_config_updated,
    should_trigger_replan,
)
from src.plan.services.routing_template_service import mine_routing_patterns
from src.plan.services.transport_batch_service import (
    compute_truck_consolidation_penalty_h,
)


# ---------------------------------------------------------------------------
# P.12 — CPOConfig budgets
# ---------------------------------------------------------------------------

def test_cpo_config_default_budgets_sum_to_total():
    cfg = CPOConfig()
    assert cfg.phase_budget_total() <= cfg.total_budget_s + 1e-6


def test_cpo_config_clips_ga_budget_above_total():
    cfg = CPOConfig(ga_budget_s=90.0, total_budget_s=60.0)
    assert cfg.ga_budget_s == 60.0
    assert cfg.time_limit_sec <= cfg.ga_budget_s


# ---------------------------------------------------------------------------
# P.6 — Fitness v2.0 weights
# ---------------------------------------------------------------------------

def test_fitness_legacy_default_unchanged():
    fit = compute_fitness(
        {"makespan_hours": 10, "total_tardiness_hours": 1, "setups": 2},
    )
    assert fit == 10 + 10 * 1 + 0.5 * 2


def test_fitness_v2_normalises_and_uses_throughput():
    cfg = FitnessConfig(use_v2_weights=True)
    cheap = compute_fitness(
        {"makespan_hours": 100, "total_tardiness_hours": 10,
         "total_idle_hours": 40, "setups": 5,
         "throughput_eur_day": 0},
        cfg,
    )
    rich = compute_fitness(
        {"makespan_hours": 100, "total_tardiness_hours": 10,
         "total_idle_hours": 40, "setups": 5,
         "throughput_eur_day": 35000},
        cfg,
    )
    # Higher throughput → lower fitness (minimised objective).
    assert rich < cheap


def test_truck_consolidation_weight_adds_penalty():
    cfg = FitnessConfig(truck_consolidation_weight=2.0)
    without = compute_fitness({"makespan_hours": 10}, cfg)
    with_penalty = compute_fitness(
        {"makespan_hours": 10, "truck_consolidation_penalty_h": 5.0},
        cfg,
    )
    assert with_penalty > without


# ---------------------------------------------------------------------------
# P.11 — MAP-Elites v2.0 axes
# ---------------------------------------------------------------------------

def test_mapelites_v2_axes_uses_lam_utilization():
    archive = MAPElites3D(use_v2_axes=True)
    c = Chromosome.identity(3)
    schedule = {
        "lam_utilization": 80.0,
        "tardiness_transport_d": 2.0,
        "idle_pct": 10.0,
    }
    admitted = archive.insert(c, 5.0, schedule, generation=1)
    assert admitted is True
    elite = archive.best()
    assert elite is not None
    assert elite.behavioral["lam_utilization"] == 80.0


def test_mapelites_v2_fallbacks_to_legacy_keys():
    archive = MAPElites3D(use_v2_axes=True)
    c = Chromosome.identity(3)
    # No v2.0 keys — falls back to avg_utilization + /24 on tardiness.
    schedule = {"avg_utilization": 75.0, "total_tardiness_hours": 48.0}
    assert archive.insert(c, 3.0, schedule, generation=1) is True
    elite = archive.best()
    assert elite is not None
    assert elite.behavioral["lam_utilization"] == 75.0
    # 48h / 24 = 2 days
    assert abs(elite.behavioral["tardiness_transport_d"] - 2.0) < 1e-6


# ---------------------------------------------------------------------------
# P.5 — Chromosome routing
# ---------------------------------------------------------------------------

def test_chromosome_routing_default_is_A():
    c = Chromosome.identity(5)
    assert c.routing_variant("op-1") == "A"


def test_chromosome_flip_variant_roundtrip():
    c = Chromosome.identity(5)
    c.flip_variant("op-1")
    assert c.routing_variant("op-1") == "B"
    c.flip_variant("op-1")
    assert c.routing_variant("op-1") == "A"


def test_chromosome_clone_copies_routing_choices():
    c = Chromosome.identity(3)
    c.flip_variant("op-Z")
    clone = c.clone()
    clone.routing_choices["op-Z"] = "A"
    # Original untouched.
    assert c.routing_choices["op-Z"] == "B"


# ---------------------------------------------------------------------------
# P.1 — Greedy pipeline (with a stubbed FactoryState)
# ---------------------------------------------------------------------------

class _StubState:
    molds: dict = {}
    PAIR_REQUIRED_PHASES: set = set()

    def mold_for(self, model_id):  # pragma: no cover — decoder path
        return None

    def workers_for(self, phase_id):
        return set()


@dataclass
class _StubOp:
    operation_id: str
    order_id: str
    sequence: int = 1
    phase_id: str = "P1"
    phase_name: str = "Phase 1"
    duration_minutes: int = 60
    machine_id: str = "M1"
    alternative_machines: tuple = ()
    predecessor_ops: tuple = ()
    mold_required: bool = False
    model_id: str = "MODEL-A"
    team_size: int = 1
    mold_id: str = None
    due_date: Any = None
    # Q.116.BD — protocolo SchedulingOperation ganhou posição alternativa.
    # Defaults inertes (False/vazio) curto-circuitam o branch is_flexible em
    # decoder_resources.py:61 → preserva o caminho legacy deste stub.
    is_flexible: bool = False
    allowed_predecessors: tuple = ()


@dataclass
class _StubMachine:
    machine_id: str = "M1"


def test_greedy_pipeline_produces_phase_timings():
    state = _StubState()
    ops = [_StubOp(operation_id=f"op-{i}", order_id=f"of-{i}") for i in range(3)]
    machines = [_StubMachine()]
    pipe = GreedyPipeline(state)
    result = pipe.run(
        Chromosome.identity(len(ops)),
        ops,
        machines,
        datetime.utcnow(),
        datetime.utcnow() + timedelta(days=7),
    )
    assert result.schedule["operations"]
    phases = [t.phase for t in result.phase_timings]
    assert phases == [1, 2, 3, 4, 5, 6, 7, 8]


def test_greedy_pipeline_demand_aggregation_drops_zero_duration():
    state = _StubState()
    ops = [
        _StubOp(operation_id="alive", order_id="of-1", duration_minutes=60),
        _StubOp(operation_id="zero", order_id="of-2", duration_minutes=0),
    ]
    pipe = GreedyPipeline(state)
    result = pipe.run(
        Chromosome.identity(len(ops)),
        ops,
        [_StubMachine()],
        datetime.utcnow(),
        datetime.utcnow() + timedelta(days=1),
    )
    assert result.demand_net_ops == 1


def test_greedy_phase_budgets_registered():
    assert sum(PHASE_BUDGETS_S.values()) <= 2.0 + 1e-6


def test_greedy_pipeline_keeps_decoder_worker_based_idle():
    """Q.134.I — the greedy BASELINE must report the SAME worker-based idle
    as a direct decode (which is what every GA candidate uses). Phase 8 used
    to overwrite total_idle_hours with an avg_utilization approximation,
    making baseline and candidates incomparable → the safety net reverted
    every work-center plan on a phantom idle regression."""
    from src.plan.cpo.decoder import decode

    state = _StubState()
    ops = [_StubOp(operation_id=f"op-{i}", order_id=f"of-{i}") for i in range(3)]
    machines = [_StubMachine(), _StubMachine(machine_id="M2")]
    h0 = datetime(2026, 6, 1, 7, 0, 0)
    h1 = h0 + timedelta(days=2)
    chromo = Chromosome.identity(len(ops))

    pipe_sched = GreedyPipeline(state).run(chromo, ops, machines, h0, h1).schedule
    direct = decode(chromo, ops, machines, state, h0, h1)

    # Same formula on both sides → identical idle (not the avg_util proxy).
    assert pipe_sched["total_idle_hours"] == direct["total_idle_hours"]
    assert pipe_sched["idle_ratio"] == direct["idle_ratio"]
    # Capacity exposed (Q.134.I observability).
    assert pipe_sched["num_machines"] == 2


# ---------------------------------------------------------------------------
# P.7 — Pair assignment
# ---------------------------------------------------------------------------

class _LaminagemState:
    PAIR_REQUIRED_PHASES = {"laminagem"}

    def workers_for(self, phase_id):
        if str(phase_id).lower() == "laminagem":
            return {"w1", "w2", "w3"}
        return set()


def test_requires_pair_only_for_listed_phases():
    state = _LaminagemState()
    lam = _StubOp(operation_id="op-1", order_id="of-1", phase_id="Laminagem")
    other = _StubOp(operation_id="op-2", order_id="of-2", phase_id="Pintura")
    assert requires_pair(lam, state) is True
    assert requires_pair(other, state) is False


def test_assign_pairs_returns_tuple_for_each_pair_op():
    state = _LaminagemState()
    ops = [
        _StubOp(operation_id="lam-a", order_id="of-1", phase_id="Laminagem"),
        _StubOp(operation_id="lam-b", order_id="of-2", phase_id="Laminagem"),
        _StubOp(operation_id="paint", order_id="of-3", phase_id="Pintura"),
    ]
    out = assign_pairs_for_ops(ops, state)
    assert "paint" not in out  # non-pair ops excluded
    assert set(out.keys()) == {"lam-a", "lam-b"}
    for chefe, partner in out.values():
        assert chefe is not None
        assert partner is not None
        assert chefe != partner


def test_assign_pairs_returns_none_when_pool_too_small():
    class _SingleWorker:
        PAIR_REQUIRED_PHASES = {"laminagem"}
        def workers_for(self, _):
            return {"only-one"}

    out = assign_pairs_for_ops(
        [_StubOp(operation_id="lam", order_id="of", phase_id="Laminagem")],
        _SingleWorker(),
    )
    assert out == {"lam": (None, None)}


# ---------------------------------------------------------------------------
# P.10 — CP-SAT L-RHO stub (no ortools in CI)
# ---------------------------------------------------------------------------

def test_cpsat_lrho_returns_unavailable_without_ortools(monkeypatch):
    from src.plan.engines import cpsat_lrho as mod

    monkeypatch.setattr(mod, "HAS_ORTOOLS", False)
    lrho = CPSATLRHO(LRHOConfig())
    result = lrho.refine(
        {"operations": [{"operation_id": "x", "start": datetime.utcnow(),
                         "end": datetime.utcnow() + timedelta(hours=1)}]},
        horizon_start=datetime.utcnow(),
        horizon_end=datetime.utcnow() + timedelta(days=1),
    )
    assert result.used is False
    assert "ortools_unavailable" in result.warnings


# ---------------------------------------------------------------------------
# P.13 — POETIQ expanded loop
# ---------------------------------------------------------------------------

def test_poetiq_stops_when_score_threshold_reached():
    calls = {"optimize": 0, "evaluate": 0}

    def optimizer(delta):
        calls["optimize"] += 1
        return {"score_proxy": 0.9}

    def evaluator(schedule):
        calls["evaluate"] += 1
        # First iteration already exceeds threshold.
        return CritiqueReport(kernel_score=0.9, llm_qual=1.0)

    loop = POETIQLoop(optimizer=optimizer, evaluator=evaluator,
                     good_enough_score=0.85, max_iterations=5)
    result = loop.run_expanded({"foo": 1})
    assert result.iterations == 1
    assert calls["optimize"] == 1


def test_poetiq_iterates_until_qualifier_decides():
    class _Iter:
        def __init__(self):
            self.count = 0
        def __call__(self, delta, critique):
            self.count += 1
            return {"refined": self.count}

    def optimizer(_d):
        return {"schedule": True}

    def evaluator(_s):
        return CritiqueReport(kernel_score=0.5, llm_qual=0.5)

    def tester(_s):
        return [
            default_perturbation_tester({
                "operations": [], "makespan_hours": 0,
            })[0],
        ]

    def qualifier(_s, c):
        return c.score > 2.0  # deliberately unreachable

    loop = POETIQLoop(
        optimizer=optimizer, evaluator=evaluator,
        tester=tester, iterator=_Iter(), qualifier=qualifier,
        max_iterations=3, good_enough_score=0.9,
    )
    result = loop.run_expanded({})
    assert result.iterations == 3
    assert result.qualified is False


def test_default_perturbation_tester_counts_affected_workers():
    schedule = {
        "operations": [
            {"workers": ["w1", "w2"], "machine_id": "M1"},
            {"workers": ["w1"], "machine_id": "M2"},
            {"workers": ["w3"], "machine_id": "M1"},
        ],
        "makespan_hours": 100.0,
    }
    reports = default_perturbation_tester(schedule, perturbations=["drop_worker"])
    assert reports[0].scenario == "drop_worker"
    # busiest worker = w1 (2 ops)
    assert reports[0].ops_affected == 2


# ---------------------------------------------------------------------------
# P.14 — Replan hook
# ---------------------------------------------------------------------------

def test_replan_triggers_on_planning_routing_update():
    assert should_trigger_replan({
        "config_type": "tenant_configuration.planning",
        "affected_entities": ["routing.templates.default_id"],
    })


def test_replan_ignores_unrelated_category():
    assert not should_trigger_replan({
        "config_type": "tenant_configuration.copilot",
        "affected_entities": ["rate_limit.per_hour"],
    })


def test_replan_triggers_on_legacy_machine_rates():
    assert should_trigger_replan({"config_type": "machine_rates"})


@pytest.mark.asyncio
async def test_handle_config_updated_calls_hook():
    seen = {}

    async def fake_trigger(*, tenant_id, reason, payload):
        seen["tenant_id"] = tenant_id
        seen["reason"] = reason
        seen["payload"] = payload

    tenant = uuid4()
    triggered = await handle_config_updated(
        {
            "config_type": "tenant_configuration.planning",
            "affected_entities": ["cpo.gen_count"],
        },
        tenant_id=tenant,
        scheduler_hook=fake_trigger,
    )
    assert triggered is True
    assert seen["tenant_id"] == tenant
    assert seen["reason"] == "CAPACITY_CHANGE"


@pytest.mark.asyncio
async def test_handle_config_updated_noop_when_not_triggering():
    called = {"n": 0}

    async def fake_trigger(**_kw):
        called["n"] += 1

    triggered = await handle_config_updated(
        {"config_type": "tenant_configuration.copilot",
         "affected_entities": ["rate_limit.per_hour"]},
        tenant_id=uuid4(),
        scheduler_hook=fake_trigger,
    )
    assert triggered is False
    assert called["n"] == 0


# ---------------------------------------------------------------------------
# P.4 — Routing mining
# ---------------------------------------------------------------------------

def test_routing_mining_ranks_by_coverage():
    data = {
        # pattern-1 covers 3 models, 6 occurrences
        "model-A": [["p1", "p2", "p3"], ["p1", "p2", "p3"]],
        "model-B": [["p1", "p2", "p3"], ["p1", "p2", "p3"]],
        "model-C": [["p1", "p2", "p3"], ["p1", "p2", "p3"]],
        # pattern-2 covers 1 model with 4 occurrences
        "model-D": [["alt", "x"]] * 4,
    }
    patterns = mine_routing_patterns(data, top_n=5, min_frequency=2)
    assert len(patterns) == 2
    assert patterns[0]["model_coverage"] == 3
    assert patterns[0]["phase_sequence"] == ["p1", "p2", "p3"]
    assert patterns[1]["phase_sequence"] == ["alt", "x"]


def test_routing_mining_respects_min_frequency():
    data = {"model-A": [["p1"]]}  # only 1 occurrence
    patterns = mine_routing_patterns(data, min_frequency=3)
    assert patterns == []


# ---------------------------------------------------------------------------
# P.2/P.3 — Truck consolidation arithmetic
# ---------------------------------------------------------------------------

def test_truck_consolidation_penalty_zero_when_within_tolerance():
    now = datetime.utcnow()
    ops_by_order = {
        "o1": [{"end": now}],
        "o2": [{"end": now + timedelta(hours=6)}],
    }
    batches = {"batch-1": ["o1", "o2"]}
    penalty = compute_truck_consolidation_penalty_h(
        ops_by_order, batches, tolerance_h=12.0,
    )
    assert penalty == 0.0


def test_truck_consolidation_penalty_counts_excess_span():
    now = datetime.utcnow()
    ops_by_order = {
        "o1": [{"end": now}],
        "o2": [{"end": now + timedelta(hours=30)}],
    }
    batches = {"batch-1": ["o1", "o2"]}
    penalty = compute_truck_consolidation_penalty_h(
        ops_by_order, batches, tolerance_h=12.0,
    )
    # span = 30h, tolerance = 12h → penalty 18h
    assert abs(penalty - 18.0) < 1e-6


def test_truck_consolidation_penalty_skips_single_order_batches():
    now = datetime.utcnow()
    penalty = compute_truck_consolidation_penalty_h(
        {"o1": [{"end": now}]},
        {"batch": ["o1"]},
    )
    assert penalty == 0.0
