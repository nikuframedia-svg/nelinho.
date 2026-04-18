"""
ProdPlan ONE — CPO v4 FRRMAB (Sprint F.1)
==========================================

Fitness-Rate-Rank-based Multi-Armed Bandit for adaptive operator selection.

Replaces the uniform random pick in `CPOv4Engine._mutate` with a UCB1
policy that biases toward operators producing bigger fitness improvements,
while still exploring rarely-used ones.

Spec parameters (from plan, fix the v3 bugs):
- c = 0.2      (low exploration — was 0.5 which kept selection random)
- window = 200 (FIFO history length — was 50, too short with 6 ops)
- decay = 0.9  (exponential discount on older rewards)

Reward shape:
    r = max(0, (parent_fitness - child_fitness) / abs(parent_fitness + eps))

so that regressing candidates score 0, and improvement size is relative.
"""

from __future__ import annotations

import logging
import math
import random
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.plan.cpo.chromosome import Chromosome

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mutation operators (pure functions: chromosome → chromosome)
# ---------------------------------------------------------------------------

OperatorFn = Callable[[Chromosome, random.Random], Chromosome]


def op_swap_adjacent(chromo: Chromosome, rng: random.Random) -> Chromosome:
    """Swap two adjacent positions in the permutation."""
    child = chromo.clone()
    n = len(child.permutation)
    if n < 2:
        return child
    i = rng.randrange(n - 1)
    child.permutation[i], child.permutation[i + 1] = (
        child.permutation[i + 1],
        child.permutation[i],
    )
    return child


def op_swap_random(chromo: Chromosome, rng: random.Random) -> Chromosome:
    """Swap two random positions in the permutation."""
    child = chromo.clone()
    n = len(child.permutation)
    if n < 2:
        return child
    i, j = rng.sample(range(n), 2)
    child.permutation[i], child.permutation[j] = (
        child.permutation[j],
        child.permutation[i],
    )
    return child


def op_insert_move(chromo: Chromosome, rng: random.Random) -> Chromosome:
    """Remove an element and insert it at a different position."""
    child = chromo.clone()
    n = len(child.permutation)
    if n < 2:
        return child
    i = rng.randrange(n)
    j = rng.randrange(n)
    value = child.permutation.pop(i)
    child.permutation.insert(j, value)
    return child


def op_flip_routing(chromo: Chromosome, rng: random.Random) -> Chromosome:
    """
    Reverse a small sub-sequence in the permutation (2-opt-style).

    Conceptually equivalent to reshuffling the routing choice for a
    contiguous run of operations. Works well on hybrid flow shops where
    nearby ops often share a critical resource.
    """
    child = chromo.clone()
    n = len(child.permutation)
    if n < 3:
        return child
    i = rng.randrange(n - 1)
    j = rng.randint(i + 1, n - 1)
    child.permutation[i : j + 1] = reversed(child.permutation[i : j + 1])
    return child


def op_shift_group(chromo: Chromosome, rng: random.Random) -> Chromosome:
    """
    Pick a contiguous block (2-5 elements) and shift it to another position.
    Captures the "move same-order ops as a block" intent of the plan.
    """
    child = chromo.clone()
    n = len(child.permutation)
    if n < 4:
        return op_insert_move(child, rng)
    block_size = rng.randint(2, min(5, n // 2))
    src_start = rng.randrange(n - block_size + 1)
    block = child.permutation[src_start : src_start + block_size]
    del child.permutation[src_start : src_start + block_size]
    dst = rng.randrange(len(child.permutation) + 1)
    child.permutation[dst:dst] = block
    return child


def op_perturb_params(chromo: Chromosome, rng: random.Random) -> Chromosome:
    """Perturb the scalar genes (edd_gap, buffer_pct, quality_weight)."""
    child = chromo.clone()
    child.edd_gap = max(5, min(30, child.edd_gap + rng.randint(-3, 3)))
    child.buffer_pct = max(0.0, min(0.30, child.buffer_pct + rng.uniform(-0.05, 0.05)))
    child.quality_weight = max(0.0, min(1.0, child.quality_weight + rng.uniform(-0.1, 0.1)))
    return child


#: Canonical operator set — wired into FRRMAB by default.
DEFAULT_OPERATORS: Dict[str, OperatorFn] = {
    "swap_adjacent": op_swap_adjacent,
    "swap_random": op_swap_random,
    "insert_move": op_insert_move,
    "flip_routing": op_flip_routing,
    "shift_group": op_shift_group,
    "perturb_params": op_perturb_params,
}


# ---------------------------------------------------------------------------
# FRRMAB
# ---------------------------------------------------------------------------

@dataclass
class _OperatorStats:
    plays: int = 0
    history: deque = field(default_factory=lambda: deque(maxlen=200))

    @property
    def mean_reward(self) -> float:
        if not self.history:
            return 0.0
        return sum(self.history) / len(self.history)


@dataclass
class FRRMAB:
    """
    Adaptive operator selection with UCB1 + sliding-window decay.

    Usage:
        mab = FRRMAB(rng=random.Random(42))
        name, fn = mab.select()
        child = fn(parent, rng)
        reward = max(0, parent_fitness - child_fitness) / (parent_fitness + 1e-6)
        mab.record(name, reward)
    """

    rng: random.Random
    c: float = 0.2
    window: int = 200
    decay: float = 0.9
    operators: Dict[str, OperatorFn] = field(default_factory=lambda: dict(DEFAULT_OPERATORS))
    _stats: Dict[str, _OperatorStats] = field(init=False)
    _total_plays: int = 0

    def __post_init__(self) -> None:
        self._stats = {
            name: _OperatorStats(history=deque(maxlen=self.window))
            for name in self.operators
        }

    # -------------------- public API ---------------------------------- #

    def select(self) -> Tuple[str, OperatorFn]:
        """Pick an operator by UCB1 score. Ties broken by lowest plays."""
        # Initial exploration: each operator must be tried at least once.
        for name, stats in self._stats.items():
            if stats.plays == 0:
                return name, self.operators[name]

        best_name, best_score = None, -math.inf
        for name, stats in self._stats.items():
            mean = stats.mean_reward
            exploration = self.c * math.sqrt(
                math.log(max(self._total_plays, 1)) / max(stats.plays, 1)
            )
            score = mean + exploration
            if score > best_score:
                best_score = score
                best_name = name
        assert best_name is not None
        return best_name, self.operators[best_name]

    def record(self, operator_name: str, reward: float) -> None:
        """Register a reward for an operator invocation."""
        if operator_name not in self._stats:
            logger.warning(f"FRRMAB.record: unknown operator {operator_name!r}")
            return
        stats = self._stats[operator_name]
        # Decay existing history by multiplying each entry before appending.
        if self.decay != 1.0 and stats.history:
            stats.history = deque(
                (r * self.decay for r in stats.history),
                maxlen=self.window,
            )
        stats.history.append(float(reward))
        stats.plays += 1
        self._total_plays += 1

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        """Observability helper — used by tests and Prometheus exporters."""
        return {
            name: {
                "plays": stats.plays,
                "mean_reward": round(stats.mean_reward, 6),
                "history_len": len(stats.history),
            }
            for name, stats in self._stats.items()
        }
