"""
ProdPlan ONE — CPO v4 Fitness
==============================

Multi-objective weighted-sum fitness. Lower is better.

Objectives (Sprint E initial weights):
- Makespan (hours)                 — weight 1.0
- Total tardiness (hours)          — weight 10.0
- Setup count                       — weight 0.5
- Safety-net penalty                — weight 1000 (applied when candidate
                                      violates baseline)

Sprint I will add a `quality_risk` term using the XGBoost model from
Sprint H; keep the hook here so the signature is stable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class FitnessConfig:
    w_makespan: float = 1.0
    w_tardiness: float = 10.0
    w_setups: float = 0.5
    w_quality_risk: float = 0.0  # enabled in Sprint I
    safety_penalty: float = 1e6


def compute_fitness(schedule: Dict[str, Any], config: Optional[FitnessConfig] = None) -> float:
    """
    Compute a single scalar from a schedule result dict.

    Expected keys (all optional — missing → 0):
      makespan_hours, total_tardiness_hours, setups, quality_risk,
      safety_violated (bool)
    """
    cfg = config or FitnessConfig()

    fitness = 0.0
    fitness += cfg.w_makespan * float(schedule.get("makespan_hours", 0))
    fitness += cfg.w_tardiness * float(schedule.get("total_tardiness_hours", 0))
    fitness += cfg.w_setups * float(schedule.get("setups", 0))
    fitness += cfg.w_quality_risk * float(schedule.get("quality_risk", 0))

    if schedule.get("safety_violated"):
        fitness += cfg.safety_penalty

    return fitness
