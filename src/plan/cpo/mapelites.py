"""
ProdPlan ONE — CPO v4 MAP-Elites 3D Archive (Sprint F.2)
=========================================================

Discrete behavioral-descriptor grid that keeps the best chromosome found
in each region of the behavior space. Used for:
- Diversity-preserving elitism (replaces fixed top-K)
- "Timeline de Aprovação" extraction in Sprint K (5-10 representative
  solutions with different trade-offs)

Spec bugs fixed from v3:
- Grid is **discrete** (10×10×5), not continuous → solutions actually
  spread across cells instead of collapsing to 2-3.
- 10% random injection every `injection_period` generations to keep
  diversity from dying when the GA converges.

Behavioral descriptors (from the decoded schedule):
- X: avg_utilization           (0-100%)         → 10 bins
- Y: total_tardiness_hours     (0-max_tardy)    → 10 bins
- Z: num_late_orders           (0-max_late)     → 5 bins

These are extracted from the schedule dict the decoder returns, so no
extra domain knowledge is needed. Sprint I can refine the dimensions
(e.g. Laminagem utilisation specifically) once the scheduler exposes
per-centro metrics.
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.plan.cpo.chromosome import Chromosome

logger = logging.getLogger(__name__)


# Grid resolution — plan target is 10×10×5 = 500 cells.
DEFAULT_BINS = (10, 10, 5)
DEFAULT_MAX_TARDY_HOURS = 168.0  # 1 week of tardiness → saturates high bin
DEFAULT_MAX_LATE_ORDERS = 20


@dataclass(frozen=True)
class CellCoord:
    x: int
    y: int
    z: int

    def as_tuple(self) -> Tuple[int, int, int]:
        return (self.x, self.y, self.z)


@dataclass
class Elite:
    """One cell of the archive — best chromosome in that behavior region."""

    chromosome: Chromosome
    fitness: float
    behavioral: Dict[str, float]
    generation: int


@dataclass
class MAPElites3D:
    """Discrete behavior archive for CPO v4.

    Thread-unsafe by design — the GA runs single-threaded.

    Sprint P.11 — the three descriptor axes can be swapped for the Blueprint
    v2.0 set via `use_v2_axes=True`:

      Legacy (Sprint F):    x=avg_utilization, y=total_tardiness_hours, z=num_late_orders
      v2.0 (Blueprint):     x=lam_utilization, y=tardiness_transport_d, z=idle_pct

    The schedule dict is expected to carry both sets of keys when
    `use_v2_axes=True`; missing v2.0 keys fall back to the legacy values
    so that a half-migrated decoder still populates the grid sensibly.
    """

    bins: Tuple[int, int, int] = DEFAULT_BINS
    max_tardy_hours: float = DEFAULT_MAX_TARDY_HOURS
    max_late_orders: int = DEFAULT_MAX_LATE_ORDERS
    injection_period_generations: int = 50
    injection_fraction: float = 0.10
    use_v2_axes: bool = False

    _archive: Dict[Tuple[int, int, int], Elite] = field(default_factory=dict)
    _insertions: int = 0
    _replacements: int = 0

    # -------------------- public API ---------------------------------- #

    def insert(
        self,
        chromosome: Chromosome,
        fitness: float,
        schedule: Dict[str, Any],
        generation: int,
    ) -> bool:
        """
        Returns True if the candidate was admitted (new cell or improved
        the incumbent), False otherwise. Lower `fitness` wins (CPO convention).
        """
        coord = self._cell_for(schedule)
        key = coord.as_tuple()

        behavioral = self._behavioral_from_schedule(schedule)

        existing = self._archive.get(key)
        if existing is None:
            self._archive[key] = Elite(
                chromosome=chromosome.clone(),
                fitness=fitness,
                behavioral=behavioral,
                generation=generation,
            )
            self._insertions += 1
            return True

        if fitness < existing.fitness - 1e-9:
            self._archive[key] = Elite(
                chromosome=chromosome.clone(),
                fitness=fitness,
                behavioral=behavioral,
                generation=generation,
            )
            self._replacements += 1
            return True

        return False

    def is_empty(self) -> bool:
        return not self._archive

    def coverage(self) -> float:
        """Fraction of the grid with at least one elite."""
        total = max(1, self.bins[0] * self.bins[1] * self.bins[2])
        return round(len(self._archive) / total, 4)

    def cells_occupied(self) -> int:
        return len(self._archive)

    def elites(self) -> List[Elite]:
        return list(self._archive.values())

    def best(self) -> Optional[Elite]:
        """Elite with the minimum fitness across the whole archive."""
        if not self._archive:
            return None
        return min(self._archive.values(), key=lambda e: e.fitness)

    def sample(self, n: int, rng: random.Random) -> List[Chromosome]:
        """Uniformly sample `n` distinct elites (or all if fewer exist)."""
        if not self._archive:
            return []
        all_elites = list(self._archive.values())
        k = min(n, len(all_elites))
        chosen = rng.sample(all_elites, k)
        return [e.chromosome.clone() for e in chosen]

    def representatives(self, n: int = 10) -> List[Elite]:
        """
        Pick up to `n` elites that best span the behavior space.
        Used by Sprint K Timeline de Aprovação.

        Selection: lowest-fitness elite from each occupied cell, then
        greedy farthest-point so the `n` chosen are behaviorally diverse.
        """
        if not self._archive:
            return []
        if len(self._archive) <= n:
            return sorted(self._archive.values(), key=lambda e: e.fitness)

        # Start with the best elite, then greedy farthest-point in BD space.
        all_elites = list(self._archive.values())
        picked: List[Elite] = [min(all_elites, key=lambda e: e.fitness)]
        remaining = [e for e in all_elites if e is not picked[0]]

        def _bd_dist(a: Elite, b: Elite) -> float:
            # Manhattan distance in (bin-space) — coords already quantised.
            ca = self._cell_for_behavioral(a.behavioral).as_tuple()
            cb = self._cell_for_behavioral(b.behavioral).as_tuple()
            return sum(abs(x - y) for x, y in zip(ca, cb))

        while len(picked) < n and remaining:
            farthest = max(
                remaining,
                key=lambda cand: min(_bd_dist(cand, p) for p in picked),
            )
            picked.append(farthest)
            remaining.remove(farthest)
        return picked

    def explain_representative(
        self,
        elite: "Elite",
        *,
        primary_kpis: Optional[Dict[str, float]] = None,
    ) -> str:
        """Sprint C 4.3 ME2 — render a one-line trade-off narrative for a
        MAP-Elites elite. Used by the WG10 Timeline UI so each of the
        5-10 alternatives shows a human-readable caption without a
        round-trip to the LLM.

        Format: "{cell coordinates} — {headline BD values} [vs primary]"
        """
        coord = self._cell_for_behavioral(elite.behavioral).as_tuple()
        parts: List[str] = [f"cell({coord[0]},{coord[1]},{coord[2]})"]

        # Pick the top-3 behavioural descriptors — the one-liner stays
        # readable even on the v2 axes (lam_util / tardiness_d / idle_pct).
        bd_bits: List[str] = []
        for key, value in list(elite.behavioral.items())[:3]:
            if isinstance(value, (int, float)):
                bd_bits.append(f"{key}={value:.1f}")
            else:
                bd_bits.append(f"{key}={value}")
        if bd_bits:
            parts.append(", ".join(bd_bits))

        if primary_kpis and elite.behavioral:
            deltas: List[str] = []
            for key, value in elite.behavioral.items():
                baseline = primary_kpis.get(key)
                if isinstance(baseline, (int, float)) and isinstance(value, (int, float)):
                    diff = round(value - baseline, 2)
                    sign = "+" if diff > 0 else ""
                    deltas.append(f"{key} {sign}{diff}")
            if deltas:
                parts.append("vs primary: " + "; ".join(deltas[:3]))

        parts.append(f"fitness={elite.fitness:.2f}")
        return " — ".join(parts)

    def inject_random_candidates(
        self,
        current_population_size: int,
        rng: random.Random,
    ) -> List[Chromosome]:
        """
        Sample `injection_fraction * current_population_size` random elites
        from the archive. Called by the GA every `injection_period_generations`
        to keep diversity from collapsing.
        """
        k = max(1, int(self.injection_fraction * current_population_size))
        return self.sample(k, rng)

    def snapshot(self) -> Dict[str, Any]:
        """Observability — for tests and Prometheus exports."""
        return {
            "cells_occupied": self.cells_occupied(),
            "coverage": self.coverage(),
            "insertions": self._insertions,
            "replacements": self._replacements,
            "bins": list(self.bins),
        }

    # -------------------- internals ---------------------------------- #

    def _behavioral_from_schedule(self, schedule: Dict[str, Any]) -> Dict[str, float]:
        """Extract the descriptor values used for both binning and Timeline
        display. When `use_v2_axes=True`, prefers the v2.0 keys (lam_utilization,
        tardiness_transport_d, idle_pct) but falls back to legacy keys so a
        partially-migrated decoder still populates the archive."""
        if self.use_v2_axes:
            return {
                "lam_utilization": float(
                    schedule.get("lam_utilization",
                                 schedule.get("avg_utilization", 0.0)) or 0.0
                ),
                "tardiness_transport_d": float(
                    schedule.get(
                        "tardiness_transport_d",
                        schedule.get("total_tardiness_hours", 0.0) / 24.0,
                    ) or 0.0
                ),
                "idle_pct": float(schedule.get("idle_pct", 0.0) or 0.0),
            }
        return {
            "avg_utilization": float(schedule.get("avg_utilization", 0.0)),
            "total_tardiness_hours": float(schedule.get("total_tardiness_hours", 0.0)),
            "num_late_orders": int(schedule.get("num_late_orders", 0)),
        }

    def _cell_for(self, schedule: Dict[str, Any]) -> CellCoord:
        if self.use_v2_axes:
            return self._cell_for_v2(schedule)
        util = float(schedule.get("avg_utilization", 0.0))
        tardy_h = float(schedule.get("total_tardiness_hours", 0.0))
        late = int(schedule.get("num_late_orders", 0))
        return CellCoord(
            x=self._bin(util, 0.0, 100.0, self.bins[0]),
            y=self._bin(tardy_h, 0.0, self.max_tardy_hours, self.bins[1]),
            z=self._bin(float(late), 0.0, float(self.max_late_orders), self.bins[2]),
        )

    def _cell_for_v2(self, schedule: Dict[str, Any]) -> CellCoord:
        # Blueprint v2.0 axes:
        # X: Laminagem utilisation (0..100%)
        # Y: max tardiness vs transport (0..14 days)
        # Z: operators idle (0..50%)
        lam_util = float(schedule.get("lam_utilization",
                                      schedule.get("avg_utilization", 0.0)) or 0.0)
        tardy_d = float(schedule.get(
            "tardiness_transport_d",
            (schedule.get("total_tardiness_hours", 0.0) or 0.0) / 24.0,
        ))
        idle_pct = float(schedule.get("idle_pct", 0.0) or 0.0)
        return CellCoord(
            x=self._bin(lam_util, 0.0, 100.0, self.bins[0]),
            y=self._bin(tardy_d, 0.0, 14.0, self.bins[1]),
            z=self._bin(idle_pct, 0.0, 50.0, self.bins[2]),
        )

    def _cell_for_behavioral(self, bd: Dict[str, float]) -> CellCoord:
        if self.use_v2_axes:
            return CellCoord(
                x=self._bin(bd.get("lam_utilization", 0.0), 0.0, 100.0, self.bins[0]),
                y=self._bin(bd.get("tardiness_transport_d", 0.0), 0.0, 14.0, self.bins[1]),
                z=self._bin(bd.get("idle_pct", 0.0), 0.0, 50.0, self.bins[2]),
            )
        return CellCoord(
            x=self._bin(bd.get("avg_utilization", 0.0), 0.0, 100.0, self.bins[0]),
            y=self._bin(bd.get("total_tardiness_hours", 0.0), 0.0, self.max_tardy_hours, self.bins[1]),
            z=self._bin(float(bd.get("num_late_orders", 0)), 0.0, float(self.max_late_orders), self.bins[2]),
        )

    @staticmethod
    def _bin(value: float, lo: float, hi: float, n_bins: int) -> int:
        if n_bins <= 1:
            return 0
        if value <= lo:
            return 0
        if value >= hi:
            return n_bins - 1
        span = hi - lo
        if span <= 0:
            return 0
        idx = int(math.floor(((value - lo) / span) * n_bins))
        return max(0, min(n_bins - 1, idx))
