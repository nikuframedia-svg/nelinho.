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
from typing import Dict, List, Literal

ScheduleDirection = Literal["forward", "backward"]


@dataclass
class Chromosome:
    """1D chromosome — permutation + scalar parameters + Sprint P extensions.

    permutation: operation-index order (controls scheduling priority)
    edd_gap: EDD-window split parameter in days (5-30 typical)
    buffer_pct: JIT buffer percentage (0.0-0.3)
    quality_weight: weight for quality-risk penalty in fitness (0.0-1.0)

    Sprint P.5 — routing_choices: per-operation A/B variant selector.
      Key = operation_id (str). Missing keys fall back to "A" (standard routing).
      Decoded by the RoutingResolver → `SchedulingOperation.variant`.

    Sprint P.2 — schedule_direction: "forward" (default, Sprint E/F behaviour)
      or "backward" (backwards-from-transport PL14). The decoder treats this
      as a hint; the CPOConfig.use_backwards_scheduling flag is the master
      switch.
    """

    permutation: List[int] = field(default_factory=list)
    edd_gap: int = 14
    buffer_pct: float = 0.10
    quality_weight: float = 0.3
    # Sprint C 4.3 C3 — days-gap used by the greedy phase-4 (setup
    # grouping). Controls how aggressively batches of the same mould
    # are packed together: higher gap → looser groups (better
    # utilisation, later delivery), lower gap → tighter groups (more
    # setups, earlier delivery). Defaulted to 5 days matching the
    # NELO factory's typical mould-change cadence.
    setup_grouping_gap: int = 5
    routing_choices: Dict[str, str] = field(default_factory=dict)
    schedule_direction: ScheduleDirection = "forward"

    def clone(self) -> "Chromosome":
        return replace(
            self,
            permutation=list(self.permutation),
            routing_choices=dict(self.routing_choices),
        )

    def routing_variant(self, operation_id: str) -> str:
        return self.routing_choices.get(operation_id, "A")

    def flip_variant(self, operation_id: str) -> None:
        cur = self.routing_choices.get(operation_id, "A")
        self.routing_choices[operation_id] = "B" if cur == "A" else "A"

    @classmethod
    def random(cls, n_ops: int, rng: random.Random) -> "Chromosome":
        perm = list(range(n_ops))
        rng.shuffle(perm)
        return cls(
            permutation=perm,
            edd_gap=rng.randint(5, 30),
            buffer_pct=round(rng.uniform(0.0, 0.25), 3),
            # Sprint C 4.3 C2 — the docstring promised 0.0-1.0, the code
            # sampled 0.0-0.8. Align the random draw to the documented
            # range so the GA can actually explore the "maximum quality"
            # end of the spectrum.
            quality_weight=round(rng.uniform(0.0, 1.0), 3),
            # routing_choices + schedule_direction intentionally defaulted —
            # v2.0 features are opt-in via CPOConfig flags so random chromos
            # produced by Sprint E/F tests still decode identically.
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
