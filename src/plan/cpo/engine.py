"""
ProdPlan ONE — CPO v4 Engine
=============================

Orchestrates: baseline greedy → GA exploration → safety net → result.

Implements `SchedulingAdapter`-compatible output (`SchedulingResult` dict)
so callers can swap it in via `adapter.configure(engine=SchedulerEngine.CPO_V4)`.

Sprint E scope: permutation GA with 3 mutation operators, OX crossover,
population 100, generations 50. No adaptive ops yet (that's Sprint F).
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from src.plan.cpo.chromosome import Chromosome
from src.plan.cpo.decoder import decode
from src.plan.cpo.fitness import FitnessConfig, compute_fitness
from src.plan.cpo.safety_net import apply_safety_net
from src.plan.cpo.state import FactoryState
from src.plan.engines.scheduling_adapter import SchedulingMachine, SchedulingOperation

logger = logging.getLogger(__name__)


@dataclass
class CPOConfig:
    population_size: int = 100
    generations: int = 50
    tournament_size: int = 5
    crossover_rate: float = 0.60
    mutation_rate: float = 0.30
    elitism_size: int = 5
    seed: Optional[int] = 42
    time_limit_sec: float = 30.0


class CPOv4Engine:
    """Hyper-heuristic scheduler for DRCFFS-R (NELO production)."""

    def __init__(
        self,
        state: FactoryState,
        config: Optional[CPOConfig] = None,
        fitness_config: Optional[FitnessConfig] = None,
    ) -> None:
        self.state = state
        self.config = config or CPOConfig()
        self.fitness_config = fitness_config or FitnessConfig()
        self._rng = random.Random(self.config.seed)

    def schedule(
        self,
        operations: List[SchedulingOperation],
        machines: List[SchedulingMachine],
        horizon_start: Optional[datetime] = None,
        horizon_end: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        started = time.time()
        horizon_start = horizon_start or datetime.utcnow()
        horizon_end = horizon_end or (horizon_start + timedelta(weeks=4))

        if not operations:
            return _empty_result(horizon_start)

        n = len(operations)

        # 1. Baseline greedy (chromosome = identity permutation)
        baseline_chromo = Chromosome.identity(n)
        baseline = decode(baseline_chromo, operations, machines, self.state, horizon_start, horizon_end)
        baseline_fit = compute_fitness(baseline, self.fitness_config)
        logger.info(
            f"CPO baseline: makespan={baseline['makespan_hours']:.1f}h, "
            f"tardy={baseline['num_late_orders']}, fitness={baseline_fit:.2f}"
        )

        # 2. GA exploration
        best = baseline
        best_fit = baseline_fit
        best_chromo = baseline_chromo

        population = [Chromosome.random(n, self._rng) for _ in range(self.config.population_size - 1)]
        population.append(baseline_chromo.clone())  # seed baseline into pop

        for gen in range(self.config.generations):
            if time.time() - started > self.config.time_limit_sec:
                logger.info(f"CPO budget exhausted at generation {gen}")
                break

            # Evaluate
            scored: List[Tuple[float, Chromosome, Dict[str, Any]]] = []
            for chromo in population:
                result = decode(chromo, operations, machines, self.state, horizon_start, horizon_end)
                fit = compute_fitness(result, self.fitness_config)
                scored.append((fit, chromo, result))

                if fit < best_fit:
                    best_fit = fit
                    best_chromo = chromo
                    best = result

            # Selection + reproduction
            scored.sort(key=lambda t: t[0])
            elite = [c for (_, c, _) in scored[: self.config.elitism_size]]
            next_pop: List[Chromosome] = [c.clone() for c in elite]

            while len(next_pop) < self.config.population_size:
                p1 = self._tournament(scored)
                p2 = self._tournament(scored)
                if self._rng.random() < self.config.crossover_rate:
                    child = self._crossover_ox(p1, p2)
                else:
                    child = p1.clone()
                if self._rng.random() < self.config.mutation_rate:
                    child = self._mutate(child)
                next_pop.append(child)

            population = next_pop

        # 3. Safety net — best candidate vs. baseline
        best["engine_used"] = "cpo_v4"
        best_final = apply_safety_net(best, baseline)

        elapsed = time.time() - started
        best_final["solve_time_sec"] = round(elapsed, 3)
        best_final["status"] = "optimal" if not best_final.get("safety_net_triggered") else "safety_net"
        best_final["cpo_meta"] = {
            "baseline_fitness": round(baseline_fit, 2),
            "best_fitness": round(best_fit, 2),
            "improvement_pct": round(
                100.0 * (baseline_fit - best_fit) / max(baseline_fit, 1e-6), 2
            ),
            "generations_run": gen + 1 if operations else 0,
        }
        return best_final

    # ------------------------------------------------------------------ #
    # GA operators                                                       #
    # ------------------------------------------------------------------ #

    def _tournament(
        self,
        scored: List[Tuple[float, Chromosome, Dict[str, Any]]],
    ) -> Chromosome:
        competitors = self._rng.sample(scored, min(self.config.tournament_size, len(scored)))
        competitors.sort(key=lambda t: t[0])
        return competitors[0][1]

    def _crossover_ox(self, p1: Chromosome, p2: Chromosome) -> Chromosome:
        """Order Crossover (OX) — preserves relative order of ops from each parent."""
        n = len(p1.permutation)
        if n < 2:
            return p1.clone()
        a, b = sorted(self._rng.sample(range(n), 2))
        child_perm = [-1] * n
        child_perm[a:b + 1] = p1.permutation[a:b + 1]
        fill = [x for x in p2.permutation if x not in child_perm[a:b + 1]]
        j = 0
        for i in range(n):
            if child_perm[i] == -1:
                child_perm[i] = fill[j]
                j += 1
        child = Chromosome(
            permutation=child_perm,
            edd_gap=(p1.edd_gap + p2.edd_gap) // 2,
            buffer_pct=(p1.buffer_pct + p2.buffer_pct) / 2,
            quality_weight=(p1.quality_weight + p2.quality_weight) / 2,
        )
        return child

    def _mutate(self, chromo: Chromosome) -> Chromosome:
        """Pick one of 3 operators at random: swap, insert, perturb_scalars."""
        op = self._rng.choice(("swap", "insert", "scalars"))
        child = chromo.clone()
        if op == "swap" and len(child.permutation) >= 2:
            i, j = self._rng.sample(range(len(child.permutation)), 2)
            child.permutation[i], child.permutation[j] = child.permutation[j], child.permutation[i]
        elif op == "insert" and len(child.permutation) >= 2:
            i = self._rng.randrange(len(child.permutation))
            j = self._rng.randrange(len(child.permutation))
            v = child.permutation.pop(i)
            child.permutation.insert(j, v)
        else:  # scalars
            child.edd_gap = max(5, min(30, child.edd_gap + self._rng.randint(-3, 3)))
            child.buffer_pct = max(0.0, min(0.3, child.buffer_pct + self._rng.uniform(-0.05, 0.05)))
            child.quality_weight = max(0.0, min(1.0, child.quality_weight + self._rng.uniform(-0.1, 0.1)))
        return child


def _empty_result(horizon_start: datetime) -> Dict[str, Any]:
    return {
        "success": True,
        "engine_used": "cpo_v4",
        "operations": [],
        "makespan_hours": 0.0,
        "total_tardiness_hours": 0.0,
        "num_late_orders": 0,
        "setups": 0,
        "avg_utilization": 0.0,
        "warnings": ["No operations provided"],
        "infeasible_op_ids": [],
        "status": "empty",
        "solve_time_sec": 0.0,
    }
