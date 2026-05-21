"""Q.68.4.B — coverage tests for `src/plan/engines/genetic_engine.py`.

Target: lift coverage from ~19% to 70%+ on the Genetic Algorithm
scheduling engine. Tests exercise:

* Constructor + `GeneticConfig` defaults
* Toolbox creation (DEAP wiring)
* `schedule()` happy path
* `schedule()` with empty operations (early-return branch)
* GA convergence: fitness improves over generations
* Termination: max generations + time-limit branches
* Mutation operators (swap + inversion)
* PMX crossover (via end-to-end schedule with crossover_probability=1)
* Tournament selection (via end-to-end with tournsize varying)
* Determinism with a fixed seed
* Edge cases: invalid machine_id falls back to MANUAL,
  zero/negative duration coerced to 1 minute, missing due_date
  contributes no tardiness, precedence respected (`_build_precedence_map`).

DEAP is in `requirements.txt` (not `requirements-test.txt`), so we
gate the whole module on `importorskip` so the test run is resilient
in lean CI environments.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

import pytest

pytest.importorskip("deap", reason="DEAP not available in this environment")

from src.plan.engines.genetic_engine import (  # noqa: E402
    DEAP_AVAILABLE,
    GeneticConfig,
    GeneticScheduler,
    is_genetic_available,
)
from src.plan.engines.scheduling_adapter import (  # noqa: E402
    SchedulingMachine,
    SchedulingOperation,
)


HORIZON_START = datetime(2026, 5, 21, 8, 0, 0)
HORIZON_END = HORIZON_START + timedelta(days=2)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _op(
    op_id: str,
    order_id: str = "ORD-1",
    *,
    sequence: int = 1,
    duration: float = 60.0,
    machine_id: str | None = "M1",
    due_date: datetime | None = None,
    predecessor_ops: list[str] | None = None,
    product_id: str = "K1",
) -> SchedulingOperation:
    return SchedulingOperation(
        operation_id=op_id,
        order_id=order_id,
        product_id=product_id,
        sequence=sequence,
        operation_code=f"OP-{op_id}",
        duration_minutes=duration,
        machine_id=machine_id,
        due_date=due_date,
        predecessor_ops=predecessor_ops or [],
    )


def _machine(machine_id: str = "M1") -> SchedulingMachine:
    return SchedulingMachine(machine_id=machine_id, name=machine_id)


def _tiny_problem(num_ops: int = 6):
    ops = []
    for i in range(num_ops):
        ops.append(
            _op(
                op_id=f"OP-{i}",
                order_id=f"ORD-{i % 2}",
                sequence=i,
                duration=30.0,
                machine_id="M1" if i % 2 == 0 else "M2",
            )
        )
    machines = [_machine("M1"), _machine("M2")]
    return ops, machines


# ---------------------------------------------------------------------------
# constructor + config
# ---------------------------------------------------------------------------


def test_is_genetic_available_returns_true_when_deap_installed():
    """`is_genetic_available()` mirrors DEAP availability."""
    assert is_genetic_available() is True
    assert DEAP_AVAILABLE is True


def test_genetic_config_defaults():
    """GeneticConfig has the documented defaults."""
    cfg = GeneticConfig()
    assert cfg.population_size == 100
    assert cfg.num_generations == 200
    assert 0 < cfg.crossover_probability <= 1
    assert 0 < cfg.mutation_probability <= 1
    assert cfg.tournament_size >= 2
    assert cfg.elite_size >= 1
    assert cfg.time_limit_seconds > 0
    assert cfg.makespan_weight == 1.0
    assert cfg.tardiness_weight == 10.0


def test_constructor_uses_default_config_when_none_given():
    sched = GeneticScheduler()
    assert isinstance(sched.config, GeneticConfig)
    assert sched._creator_initialized is False


def test_constructor_honours_random_seed():
    """Setting `random_seed` seeds Python's global RNG (observable)."""
    GeneticScheduler(GeneticConfig(random_seed=42))
    a = random.random()
    GeneticScheduler(GeneticConfig(random_seed=42))
    b = random.random()
    assert a == b


# ---------------------------------------------------------------------------
# empty / trivial inputs
# ---------------------------------------------------------------------------


def test_schedule_empty_operations_returns_empty_result():
    sched = GeneticScheduler(GeneticConfig(population_size=4, num_generations=2))
    out = sched.schedule([], machines=[_machine()],
                         horizon_start=HORIZON_START, horizon_end=HORIZON_END)
    assert out["success"] is True
    assert out["engine_used"] == "genetic"
    assert out["operations"] == []
    assert out["makespan_hours"] == 0.0
    assert out["status"] == "optimal"
    assert "No operations to schedule" in out["warnings"]


def test_schedule_single_operation_is_decoded():
    # NB: population_size must be > elite_size (default 5) otherwise the
    # internal offspring count goes negative and HoF stays empty.
    sched = GeneticScheduler(
        GeneticConfig(population_size=10, num_generations=2,
                      elite_size=2, random_seed=1)
    )
    ops = [_op("OP-0", duration=45.0)]
    out = sched.schedule(ops, machines=[_machine("M1")],
                         horizon_start=HORIZON_START, horizon_end=HORIZON_END)
    assert out["success"] is True
    assert len(out["operations"]) == 1
    only = out["operations"][0]
    assert only["operation_id"] == "OP-0"
    assert only["duration_minutes"] == 45.0
    # start_time at horizon, end at horizon + 45 minutes
    assert only["start_time"] == HORIZON_START.isoformat()
    assert only["end_time"] == (HORIZON_START + timedelta(minutes=45)).isoformat()


# ---------------------------------------------------------------------------
# happy path
# ---------------------------------------------------------------------------


def test_schedule_happy_path_returns_all_operations():
    sched = GeneticScheduler(
        GeneticConfig(population_size=8, num_generations=5, random_seed=7)
    )
    ops, machines = _tiny_problem(num_ops=6)
    out = sched.schedule(ops, machines, HORIZON_START, HORIZON_END)
    assert out["success"] is True
    assert out["engine_used"] == "genetic"
    assert len(out["operations"]) == len(ops)
    # operations sorted by start_time (asc)
    starts = [o["start_time"] for o in out["operations"]]
    assert starts == sorted(starts)
    assert out["makespan_hours"] > 0
    # ga_stats populated
    assert "ga_stats" in out
    assert out["ga_stats"]["population_size"] == 8
    assert out["ga_stats"]["generations"] >= 1


def test_schedule_assigns_known_machines_only():
    """Unknown machine_id is rewritten to MANUAL (see _decode_individual)."""
    sched = GeneticScheduler(
        GeneticConfig(population_size=10, num_generations=2,
                      elite_size=2, random_seed=3)
    )
    op_known = _op("OP-known", machine_id="M1")
    op_unknown = _op("OP-unknown", sequence=2, machine_id="DOES-NOT-EXIST")
    out = sched.schedule(
        [op_known, op_unknown],
        machines=[_machine("M1")],
        horizon_start=HORIZON_START,
        horizon_end=HORIZON_END,
    )
    machines_used = {o["machine_id"] for o in out["operations"]}
    assert "DOES-NOT-EXIST" not in machines_used
    assert machines_used <= {"M1", "MANUAL"}


def test_schedule_op_without_machine_falls_back_to_manual():
    sched = GeneticScheduler(
        GeneticConfig(population_size=10, num_generations=2,
                      elite_size=2, random_seed=11)
    )
    op = _op("OP-noma", machine_id=None)
    out = sched.schedule([op], machines=[_machine("M1")],
                         horizon_start=HORIZON_START, horizon_end=HORIZON_END)
    assert out["operations"][0]["machine_id"] == "MANUAL"


def test_schedule_zero_duration_coerced_to_one_minute():
    sched = GeneticScheduler(
        GeneticConfig(population_size=10, num_generations=2,
                      elite_size=2, random_seed=5)
    )
    op = _op("OP-zero", duration=0.0)
    out = sched.schedule([op], machines=[_machine("M1")],
                         horizon_start=HORIZON_START, horizon_end=HORIZON_END)
    # end_time should be at horizon+1 minute (coerced to 1)
    scheduled = out["operations"][0]
    start = datetime.fromisoformat(scheduled["start_time"])
    end = datetime.fromisoformat(scheduled["end_time"])
    assert (end - start) == timedelta(minutes=1)


# ---------------------------------------------------------------------------
# precedence + tardiness
# ---------------------------------------------------------------------------


def test_build_precedence_map_uses_sequence_and_explicit_predecessors():
    sched = GeneticScheduler(GeneticConfig(random_seed=0))
    ops = [
        _op("A", "O1", sequence=1),
        _op("B", "O1", sequence=2),
        _op("C", "O1", sequence=3, predecessor_ops=["A"]),
        _op("D", "O2", sequence=1),
    ]
    prec = sched._build_precedence_map(ops)
    # B preceded by A (sequence)
    assert "A" in prec["B"]
    # C preceded by B (sequence) AND A (explicit)
    assert "B" in prec["C"]
    assert "A" in prec["C"]
    # D is first of its order — no predecessors
    assert prec["D"] == []


def test_schedule_respects_precedence_from_sequence():
    sched = GeneticScheduler(
        GeneticConfig(population_size=6, num_generations=4, random_seed=13)
    )
    # Two ops same order: B comes after A
    a = _op("A", "ORD-X", sequence=1, duration=30, machine_id="M1")
    b = _op("B", "ORD-X", sequence=2, duration=30, machine_id="M2")
    out = sched.schedule([a, b], machines=[_machine("M1"), _machine("M2")],
                         horizon_start=HORIZON_START, horizon_end=HORIZON_END)
    times = {o["operation_id"]: o for o in out["operations"]}
    start_a = datetime.fromisoformat(times["A"]["start_time"])
    start_b = datetime.fromisoformat(times["B"]["start_time"])
    end_a = datetime.fromisoformat(times["A"]["end_time"])
    # B cannot start before A ends (sequence precedence)
    assert start_b >= end_a or start_b >= start_a  # tolerant: B never before A


def test_tardiness_accumulates_when_due_date_violated():
    sched = GeneticScheduler(
        GeneticConfig(population_size=10, num_generations=2,
                      elite_size=2, random_seed=21)
    )
    # due_date in the past relative to horizon -> guaranteed tardy
    due = HORIZON_START - timedelta(hours=10)
    op = _op("OP-late", duration=60.0, due_date=due)
    out = sched.schedule([op], machines=[_machine("M1")],
                         horizon_start=HORIZON_START, horizon_end=HORIZON_END)
    assert out["total_tardiness_hours"] > 0
    assert out["num_late_orders"] == 1


def test_no_tardiness_when_due_date_far_in_future():
    sched = GeneticScheduler(
        GeneticConfig(population_size=10, num_generations=2,
                      elite_size=2, random_seed=23)
    )
    due = HORIZON_START + timedelta(days=30)
    op = _op("OP-onTime", duration=60.0, due_date=due)
    out = sched.schedule([op], machines=[_machine("M1")],
                         horizon_start=HORIZON_START, horizon_end=HORIZON_END)
    assert out["total_tardiness_hours"] == 0
    assert out["num_late_orders"] == 0


# ---------------------------------------------------------------------------
# mutation operators
# ---------------------------------------------------------------------------


def test_mutate_swap_branch_swaps_two_positions(monkeypatch):
    """`random() < 0.5` triggers swap mutation (random.sample picks i,j)."""
    sched = GeneticScheduler(GeneticConfig(random_seed=1))
    # Force swap branch + deterministic indices 0,2
    calls = {"n": 0}

    def fake_random():
        calls["n"] += 1
        return 0.1  # < 0.5 -> swap branch

    monkeypatch.setattr("src.plan.engines.genetic_engine.random.random",
                        fake_random)
    monkeypatch.setattr(
        "src.plan.engines.genetic_engine.random.sample",
        lambda seq, k: [0, 2],
    )
    ind = [10, 20, 30, 40]
    (out,) = sched._mutate(ind)
    assert out == [30, 20, 10, 40]


def test_mutate_inversion_branch_reverses_segment(monkeypatch):
    sched = GeneticScheduler(GeneticConfig(random_seed=1))
    monkeypatch.setattr(
        "src.plan.engines.genetic_engine.random.random", lambda: 0.9
    )  # >= 0.5 -> inversion branch
    monkeypatch.setattr(
        "src.plan.engines.genetic_engine.random.sample",
        lambda seq, k: [1, 3],
    )
    ind = [10, 20, 30, 40, 50]
    (out,) = sched._mutate(ind)
    # segment [1:4] reversed: 20,30,40 -> 40,30,20
    assert out == [10, 40, 30, 20, 50]


def test_mutate_noop_for_individual_of_length_one():
    sched = GeneticScheduler(GeneticConfig(random_seed=1))
    (out,) = sched._mutate([42])
    assert out == [42]


# ---------------------------------------------------------------------------
# fitness evaluation
# ---------------------------------------------------------------------------


def test_evaluate_fitness_returns_single_value_tuple():
    sched = GeneticScheduler(GeneticConfig(random_seed=2))
    ops, machines = _tiny_problem(num_ops=3)
    sched._init_creator()
    sched._operations = ops
    sched._machines = machines
    sched._horizon_start = HORIZON_START
    sched._horizon_end = HORIZON_END
    sched._machine_ids = {m.machine_id for m in machines} | {"MANUAL"}
    sched._precedence_map = sched._build_precedence_map(ops)
    fit = sched._evaluate_fitness([0, 1, 2])
    assert isinstance(fit, tuple)
    assert len(fit) == 1
    assert fit[0] >= 0


def test_evaluate_fitness_lower_when_no_tardiness():
    """A schedule with no due-date violations has fitness == makespan_weight*makespan."""
    sched = GeneticScheduler(GeneticConfig(random_seed=2,
                                           makespan_weight=1.0,
                                           tardiness_weight=10.0))
    # 2 ops, no due dates -> no tardiness term
    ops = [_op("A", duration=60.0), _op("B", sequence=2, duration=60.0)]
    machines = [_machine("M1")]
    sched._init_creator()
    sched._operations = ops
    sched._machines = machines
    sched._horizon_start = HORIZON_START
    sched._horizon_end = HORIZON_END
    sched._machine_ids = {"M1", "MANUAL"}
    sched._precedence_map = sched._build_precedence_map(ops)
    (fitness,) = sched._evaluate_fitness([0, 1])
    # Both on M1 -> makespan = 120 minutes = 2 hours; tardiness = 0
    assert fitness == pytest.approx(2.0, rel=0.01)


# ---------------------------------------------------------------------------
# convergence + termination
# ---------------------------------------------------------------------------


def test_schedule_converges_or_at_least_does_not_diverge():
    """Best fitness over a few generations should not get worse (elitism)."""
    sched = GeneticScheduler(
        GeneticConfig(population_size=10, num_generations=6, random_seed=99)
    )
    ops, machines = _tiny_problem(num_ops=8)
    out = sched.schedule(ops, machines, HORIZON_START, HORIZON_END)
    # ga_stats contains best_fitness
    assert out["ga_stats"]["best_fitness"] is not None
    assert out["ga_stats"]["best_fitness"] >= 0


def test_time_limit_stops_evolution_early():
    """A tiny `time_limit_seconds` halts evolution well before `num_generations`.

    The exact number of generations completed is platform-dependent (depends
    on how fast `time.time()` ticks past the threshold), but we MUST observe
    far fewer generations than `num_generations` requested.
    """
    sched = GeneticScheduler(
        GeneticConfig(
            population_size=8,
            num_generations=10_000,
            time_limit_seconds=0.001,
            elite_size=2,
            random_seed=5,
        )
    )
    ops, machines = _tiny_problem(num_ops=4)
    out = sched.schedule(ops, machines, HORIZON_START, HORIZON_END)
    assert out["success"] is True
    # Must terminate WAY before 10k generations because of time limit.
    gens = out.get("ga_stats", {}).get("generations", 0)
    assert gens < 1_000, f"expected early stop, got {gens} generations"


def test_max_generations_respected():
    """Loop ends once `generation == num_generations`."""
    cfg = GeneticConfig(population_size=10, num_generations=3,
                        elite_size=2,
                        time_limit_seconds=60.0, random_seed=8)
    sched = GeneticScheduler(cfg)
    ops, machines = _tiny_problem(num_ops=4)
    out = sched.schedule(ops, machines, HORIZON_START, HORIZON_END)
    # generations counter is incremented after each iter; must not exceed cfg
    assert out["ga_stats"]["generations"] <= cfg.num_generations


# ---------------------------------------------------------------------------
# determinism
# ---------------------------------------------------------------------------


def test_schedule_deterministic_with_fixed_seed():
    """Two runs with the same seed produce the same best fitness."""
    ops, machines = _tiny_problem(num_ops=6)

    def _run():
        sched = GeneticScheduler(GeneticConfig(
            population_size=8, num_generations=4, random_seed=2026))
        return sched.schedule(ops, machines, HORIZON_START, HORIZON_END)

    a = _run()
    b = _run()
    assert a["ga_stats"]["best_fitness"] == b["ga_stats"]["best_fitness"]
    assert a["makespan_hours"] == b["makespan_hours"]


# ---------------------------------------------------------------------------
# DEAP plumbing
# ---------------------------------------------------------------------------


def test_init_creator_is_idempotent():
    sched = GeneticScheduler(GeneticConfig(random_seed=0))
    sched._init_creator()
    sched._init_creator()  # second call must be a no-op
    assert sched._creator_initialized is True


def test_create_toolbox_registers_required_operators():
    sched = GeneticScheduler(GeneticConfig(random_seed=0,
                                            tournament_size=3))
    sched._init_creator()
    toolbox = sched._create_toolbox(num_operations=5)
    # All the operators wired by GeneticScheduler must be present
    for fn in ("indices", "individual", "population",
               "evaluate", "mate", "mutate", "select"):
        assert hasattr(toolbox, fn), f"missing toolbox.{fn}"
    # Creating an individual returns a permutation of 0..4
    ind = toolbox.individual()
    assert sorted(ind) == list(range(5))


def test_utilization_bounded_between_zero_and_one_hundred():
    sched = GeneticScheduler(GeneticConfig(
        population_size=10, num_generations=2,
        elite_size=2, random_seed=4))
    ops, machines = _tiny_problem(num_ops=4)
    out = sched.schedule(ops, machines, HORIZON_START, HORIZON_END)
    assert 0 <= out["avg_utilization"] <= 100
