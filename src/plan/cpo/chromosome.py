"""
ProdPlan ONE — CPO v4 Chromosome
=================================

1D chromosome: a permutation of operation indices + a handful of scalar
parameters. The heuristic decoder turns this into a feasible schedule.

Why 1D instead of a 3-vector (OSC+MAC+WAC):
- 3-vector explodes the search space to 10^15+ → GA drowns.
- 1D permutation + heuristic decoder is ~(n!) for n≈50 active ops ≈ 10^6.
- Standard genetic operators (OX, swap, insert) work without adaptation.
- Validated by Lu et al. 2018 and Mlekusch & Hartl 2025.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, replace
from typing import List


@dataclass
class Chromosome:
    """
    permutation: operation-index order (controls scheduling priority)
    edd_gap: EDD-window split parameter in days (5-30 typical)
    buffer_pct: JIT buffer percentage (0.0-0.3)
    quality_weight: weight for quality-risk penalty in fitness (0.0-1.0)
    """

    permutation: List[int] = field(default_factory=list)
    edd_gap: int = 14
    buffer_pct: float = 0.10
    quality_weight: float = 0.3

    def clone(self) -> "Chromosome":
        return replace(self, permutation=list(self.permutation))

    @classmethod
    def random(cls, n_ops: int, rng: random.Random) -> "Chromosome":
        perm = list(range(n_ops))
        rng.shuffle(perm)
        return cls(
            permutation=perm,
            edd_gap=rng.randint(5, 30),
            buffer_pct=round(rng.uniform(0.0, 0.25), 3),
            quality_weight=round(rng.uniform(0.0, 0.8), 3),
        )

    @classmethod
    def identity(cls, n_ops: int) -> "Chromosome":
        """Baseline chromosome — ops in their natural order, neutral scalars."""
        return cls(
            permutation=list(range(n_ops)),
            edd_gap=14,
            buffer_pct=0.10,
            quality_weight=0.3,
        )
