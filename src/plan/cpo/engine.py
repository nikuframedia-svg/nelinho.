"""
ProdPlan ONE — CPO v4 Engine
=============================

Orchestrates: baseline greedy → GA exploration → safety net → result.

Implements `SchedulingAdapter`-compatible output (`SchedulingResult` dict)
so callers can swap it in via `adapter.configure(engine=SchedulerEngine.CPO_V4)`.

Sprint E scope: permutation GA with 3 mutation operators, OX crossover,
population 100, generations 50.
Sprint F scope: FRRMAB-driven operator selection (6 ops), MAP-Elites 3D
archive for diversity-preserving elitism, surrogate-model skip filter,
and stagnation restart. All four features are gated by `CPOConfig` flags
so Sprint E tests keep their exact behaviour when flags are left off.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from src.plan.cpo.chromosome import Chromosome
from src.plan.cpo.decoder import decode
from src.plan.cpo.fitness import FitnessConfig, compute_fitness
from src.plan.cpo.frrmab import FRRMAB
from src.plan.cpo.mapelites import MAPElites3D
from src.plan.cpo.safety_net import apply_safety_net
from src.plan.cpo.state import FactoryState
from src.plan.cpo.surrogate import CPOSurrogateLayer
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

    # -------------------- Sprint F adaptive flags -------------------- #
    #: Use FRRMAB for mutation operator selection (6 ops).
    use_frrmab: bool = True
    #: Track elite candidates in a MAP-Elites 3D archive.
    use_mapelites: bool = True
    #: Let the surrogate skip clearly worse candidates before decode.
    #: Off by default — requires >=20 real evals before useful.
    use_surrogate: bool = False
    #: Restart fraction of the population when stagnant for N generations.
    use_restart: bool = True
    stagnation_limit_generations: int = 20
    restart_random_fraction: float = 0.50  # rest comes from elite+MAP-Elites


class CPOv4Engine:
    """Hyper-heuristic scheduler for DRCFFS-R (NELO production)."""

    def __init__(
        self,
        state: FactoryState,
        config: Optional[CPOConfig] = None,
        fitness_config: Optional[FitnessConfig] = None,
        surrogate: Optional[CPOSurrogateLayer] = None,
        mapelites: Optional[MAPElites3D] = None,
    ) -> None:
        self.state = state
        self.config = config or CPOConfig()
        self.fitness_config = fitness_config or FitnessConfig()
        self._rng = random.Random(self.config.seed)

        # Adaptive layers — created lazily so Sprint E tests that don't
        # construct these directly still get defaults driven by config.
        self._frrmab = FRRMAB(rng=self._rng) if self.config.use_frrmab else None
        self._mapelites = (
            mapelites if mapelites is not None
            else (MAPElites3D() if self.config.use_mapelites else None)
        )
        self._surrogate = (
            surrogate if surrogate is not None
            else CPOSurrogateLayer(enabled=self.config.use_surrogate)
        )

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

        # Surrogate context (static across the run, cheap to precompute).
        total_duration = sum(float(op.duration_minutes) for op in operations)
        surrogate_ctx = {
            "n_ops": n,
            "n_orders": len({op.order_id for op in operations}),
            "avg_duration_min": (total_duration / n) if n else 0.0,
        }

        # 2. GA exploration
        best = baseline
        best_fit = baseline_fit
        best_chromo = baseline_chromo

        # Seed MAP-Elites with the baseline so restart/injection always
        # has at least one viable elite to draw from.
        if self._mapelites is not None:
            self._mapelites.insert(baseline_chromo, baseline_fit, baseline, generation=0)

        population = [Chromosome.random(n, self._rng) for _ in range(self.config.population_size - 1)]
        population.append(baseline_chromo.clone())

        # Stagnation tracking for restart logic.
        last_best_fit = baseline_fit
        stagnation_count = 0
        total_skips = 0
        total_real_evals = 0
        gen = 0

        for gen in range(self.config.generations):
            if time.time() - started > self.config.time_limit_sec:
                logger.info(f"CPO budget exhausted at generation {gen}")
                break

            # ----- Evaluate --------------------------------------------
            scored: List[Tuple[float, Chromosome, Optional[Dict[str, Any]]]] = []
            for chromo in population:
                if self._surrogate.should_skip_candidate(chromo, surrogate_ctx):
                    # Use the baseline fitness as a pessimistic placeholder —
                    # the tournament will deprioritize this candidate, but it
                    # stays in the pool so its genes can still recombine.
                    scored.append((baseline_fit * 2, chromo, None))
                    total_skips += 1
                    continue

                result = decode(chromo, operations, machines, self.state, horizon_start, horizon_end)
                fit = compute_fitness(result, self.fitness_config)
                scored.append((fit, chromo, result))
                total_real_evals += 1

                # Track best + MAP-Elites + surrogate sample
                if fit < best_fit:
                    best_fit = fit
                    best_chromo = chromo
                    best = result
                if self._mapelites is not None:
                    self._mapelites.insert(chromo, fit, result, generation=gen)
                self._surrogate.record(chromo, surrogate_ctx, fit)

            # ----- Stagnation detection --------------------------------
            if best_fit < last_best_fit - 1e-9:
                last_best_fit = best_fit
                stagnation_count = 0
            else:
                stagnation_count += 1

            # ----- Selection + reproduction ----------------------------
            scored.sort(key=lambda t: t[0])

            elite_count = max(
                self.config.elitism_size,
                int(0.05 * self.config.population_size),  # explicit top-5%
            )
            elite_scored = scored[:elite_count]
            next_pop: List[Chromosome] = [c.clone() for (_, c, _) in elite_scored]

            # Periodic diversity injection from MAP-Elites.
            if (
                self._mapelites is not None
                and (gen + 1) % self._mapelites.injection_period_generations == 0
                and not self._mapelites.is_empty()
            ):
                for elite in self._mapelites.inject_random_candidates(
                    self.config.population_size, self._rng
                ):
                    if len(next_pop) >= self.config.population_size:
                        break
                    next_pop.append(elite)

            # Restart after prolonged stagnation — 50% random, 50% mixed
            # between existing elite and MAP-Elites samples.
            if (
                self.config.use_restart
                and stagnation_count >= self.config.stagnation_limit_generations
            ):
                next_pop = self._restart_population(
                    n=n,
                    current_elite=elite_scored,
                )
                stagnation_count = 0
                logger.info(f"CPO restart at generation {gen} (stagnation reached)")

            while len(next_pop) < self.config.population_size:
                p1 = self._tournament(scored)
                p2 = self._tournament(scored)
                if self._rng.random() < self.config.crossover_rate:
                    child = self._crossover_ox(p1, p2)
                else:
                    child = p1.clone()
                if self._rng.random() < self.config.mutation_rate:
                    child, op_name, parent_fit = self._mutate_with_frrmab(child, scored)
                    # FRRMAB reward comes from the NEXT generation's
                    # evaluation — store the parent fitness so we can
                    # compute the reward after decode.
                    child._frrmab_op = op_name  # type: ignore[attr-defined]
                    child._frrmab_parent_fit = parent_fit  # type: ignore[attr-defined]
                next_pop.append(child)

            # Update FRRMAB rewards from the previous generation's children.
            self._update_frrmab_rewards(scored)

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
            "real_evaluations": total_real_evals,
            "surrogate_skips": total_skips,
            "frrmab": self._frrmab.snapshot() if self._frrmab is not None else None,
            "mapelites": self._mapelites.snapshot() if self._mapelites is not None else None,
            "surrogate": self._surrogate.snapshot() if self._surrogate is not None else None,
        }
        return best_final

    # ------------------------------------------------------------------ #
    # FRRMAB integration                                                 #
    # ------------------------------------------------------------------ #

    def _mutate_with_frrmab(
        self,
        chromo: Chromosome,
        scored: List[Tuple[float, Chromosome, Optional[Dict[str, Any]]]],
    ) -> Tuple[Chromosome, Optional[str], float]:
        """Apply mutation via FRRMAB (or the legacy random picker)."""
        # Parent fitness is this chromosome's fitness in `scored` if present.
        parent_fit = self._lookup_fitness(chromo, scored)
        if self._frrmab is None:
            return self._mutate(chromo), None, parent_fit
        op_name, op_fn = self._frrmab.select()
        return op_fn(chromo, self._rng), op_name, parent_fit

    def _update_frrmab_rewards(
        self,
        scored: List[Tuple[float, Chromosome, Optional[Dict[str, Any]]]],
    ) -> None:
        """After each generation, turn parent→child fitness deltas into
        FRRMAB rewards. The reward is zero when no improvement."""
        if self._frrmab is None:
            return
        for fit, chromo, _ in scored:
            op_name = getattr(chromo, "_frrmab_op", None)
            parent_fit = getattr(chromo, "_frrmab_parent_fit", None)
            if op_name is None or parent_fit is None:
                continue
            denom = abs(parent_fit) + 1e-6
            reward = max(0.0, (parent_fit - fit) / denom)
            self._frrmab.record(op_name, reward)
            # Clear so we don't double-count next generation.
            chromo._frrmab_op = None  # type: ignore[attr-defined]
            chromo._frrmab_parent_fit = None  # type: ignore[attr-defined]

    @staticmethod
    def _lookup_fitness(
        chromo: Chromosome,
        scored: List[Tuple[float, Chromosome, Optional[Dict[str, Any]]]],
    ) -> float:
        for fit, c, _ in scored:
            if c is chromo:
                return fit
        return 0.0

    # ------------------------------------------------------------------ #
    # Restart                                                            #
    # ------------------------------------------------------------------ #

    def _restart_population(
        self,
        n: int,
        current_elite: List[Tuple[float, Chromosome, Optional[Dict[str, Any]]]],
    ) -> List[Chromosome]:
        pop_size = self.config.population_size
        rand_count = max(1, int(self.config.restart_random_fraction * pop_size))
        elite_count = pop_size - rand_count

        mixed: List[Chromosome] = []

        # Take from MAP-Elites if available (most diverse elite source).
        if self._mapelites is not None and not self._mapelites.is_empty():
            mixed.extend(self._mapelites.sample(elite_count, self._rng))

        # Fill remaining from current generation's elite list.
        for _, c, _ in current_elite:
            if len(mixed) >= elite_count:
                break
            mixed.append(c.clone())

        # Random genomes to seed exploration.
        while len(mixed) < pop_size:
            mixed.append(Chromosome.random(n, self._rng))

        return mixed[:pop_size]

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
