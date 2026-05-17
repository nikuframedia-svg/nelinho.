"""
ProdPlan ONE — World-model forecast (Sprint F+++)
====================================================

Monte Carlo rollout sobre o NELO_DAG ao longo de N "turnos" (8 h
cada). Pensado para questões com **horizonte temporal + incerteza**
que o ``causal_query`` (single-step, exacto) não cobre:

  * "Como vai evoluir o throughput nos próximos 7 turnos?"
  * "Qual o range esperado de makespan se a temperatura oscilar?"

Filosofia de ruído (importante)
-------------------------------
**Jitter aplicado APENAS aos inputs + confounders** (não às funções).
Este é o primeiro instinto que o Plan agent atacou: wrappar as
``_FUNCTIONS`` com ruído gaussiano composto por profundidade
topológica fabricava precisão (std terminal balooned by graph depth,
not reality).

A interpretação honesta deste módulo é:

* "Como vai correr este KPI **se a evidência estiver fuzzy** (jitter
  inputs) **e o mundo derivar com o tempo** (DRIFT_PROFILE)?"

Não é "a função em si é estocástica" (não é — é determinística e
auditável no DAG). É um cenário-stress, não uma predição física.
``status="degraded"`` no payload final torna isto explícito.

Autoria
-------
Reutiliza ``_propagate``, ``_FUNCTIONS`` e ``NODES_BY_ID`` do módulo
:mod:`src.copilot.causal.nelo_dag`. Zero novas deps; só ``numpy``.
"""

from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# DRIFT_PROFILE — auditable confounder evolution per step
# ═══════════════════════════════════════════════════════════════════════════
#
# Cada entrada é uma função `(step:int, baseline:float) -> float` que
# calcula o "drift" aditivo a aplicar ao confounder para o turno t.
# Valores deliberadamente conservadores; a interpretação é
# "scenario-style stress", não "physical prediction".
#
# `step_unit` = "shift" (8 h). 14 turnos ≈ 1 semana útil.

STEP_UNIT: str = "shift"


def _drift_mold_age(step: int, _baseline: float) -> float:
    """Moldes envelhecem ~1 % de ano por turno (≈ 1 mês por ano de
    operação contínua a 3 turnos/dia). Monotone."""
    return step * 0.01


def _drift_external_temperature(step: int, _baseline: float) -> float:
    """Oscilação ~ semanal (período = 14 turnos) com amplitude 1.5 °C.
    Captura o ciclo dia/noite + sazonalidade curta."""
    return math.sin(step * 2 * math.pi / 14.0) * 1.5


def _drift_material_availability_pct(step: int, baseline: float) -> float:
    """Stock cai 0.5 pp por turno até atingir o piso de 50 %. Modela a
    desgaste sem reposição activa — pessimista por design."""
    drift = -step * 0.005
    floor_drift = 0.50 - baseline
    return max(drift, floor_drift)


DRIFT_PROFILE: Dict[str, Callable[[int, float], float]] = {
    "mold_age": _drift_mold_age,
    "external_temperature": _drift_external_temperature,
    "material_availability_pct": _drift_material_availability_pct,
}


# Inputs/confounders que sofrem jitter Gaussiano por sample. Outros
# inputs ficam fixos no valor que o `do` pediu (ou no baseline).
_JITTERABLE_NODES = (
    "mold_age",
    "external_temperature",
    "material_availability_pct",
    "operator_experience",
    "mold_availability_pct",
)


# ═══════════════════════════════════════════════════════════════════════════
# ForecastReport
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class StepStats:
    """Quantis + momentos do target num timestep específico."""
    step: int
    mean: float
    std: float
    p05: float
    p25: float
    p50: float
    p75: float
    p95: float


@dataclass
class ForecastReport:
    """Resultado de :func:`forecast`. JSON-friendly via :meth:`to_json`.

    ``trajectory`` tem um item por step. ``summary`` resume os
    extremos para o caso do consumer querer só a "moldura" sem ter
    que iterar a trajectória.
    """
    target: str
    status: str                          # "ok" | "degraded" | "unavailable"
    reason: Optional[str]
    step_unit: str
    horizon_steps: int
    samples: int
    jitter: float
    trajectory: List[StepStats] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    intervention: Optional[Dict[str, float]] = None
    observation: Optional[Dict[str, float]] = None

    def to_json(self) -> Dict[str, Any]:
        return {
            "target": self.target,
            "status": self.status,
            "reason": self.reason,
            "step_unit": self.step_unit,
            "horizon_steps": self.horizon_steps,
            "samples": self.samples,
            "jitter": self.jitter,
            "trajectory": [asdict(s) for s in self.trajectory],
            "summary": self.summary,
            "intervention": self.intervention,
            "observation": self.observation,
        }


# ═══════════════════════════════════════════════════════════════════════════
# Public entry
# ═══════════════════════════════════════════════════════════════════════════


HORIZON_MIN, HORIZON_MAX = 1, 30
SAMPLES_MIN, SAMPLES_MAX = 50, 500
JITTER_MIN, JITTER_MAX = 0.0, 0.20


def forecast(
    target: str,
    *,
    do: Optional[Mapping[str, Any]] = None,
    observe: Optional[Mapping[str, Any]] = None,
    horizon_steps: int = 7,
    samples: int = 200,
    jitter: float = 0.05,
    seed: int = 42,
) -> ForecastReport:
    """Run a Monte Carlo rollout of ``target`` over ``horizon_steps``
    shifts. Returns a :class:`ForecastReport` with per-step quantiles.

    Parameters
    ----------
    target:
        DAG node id whose trajectory we want.
    do:
        Hard interventions (Pearl ``do``). These override the
        baseline AND skip the per-sample jitter for that node.
    observe:
        Soft observations. Overlay the baseline like ``do`` but the
        propagation continues to recompute downstream nodes from
        them (``_propagate`` semantics).
    horizon_steps:
        Number of shifts (1 shift = 8 h). Clamped to ``[1, 30]``.
    samples:
        Monte Carlo samples per step. Clamped to ``[50, 500]``.
    jitter:
        Std of the Gaussian noise added to inputs+confounders, as a
        fraction of each node's baseline. Clamped to ``[0.0, 0.20]``.
    seed:
        RNG seed for reproducibility.

    Returns
    -------
    ForecastReport
        ``status="degraded"`` because the trajectory is a synthetic
        scenario (not real telemetry); upgrades to ``"ok"`` once
        Sprint G feeds real series.
    """
    # Lazy import — keep the rest of the causal package importable
    # even when numpy is somehow absent (defensive; numpy IS a hard
    # dep but we never want this hot path to take the agent down).
    try:
        import numpy as np

        from src.copilot.causal.nelo_dag import (
            ALL_NODES,
            NODES_BY_ID,
            NodeCategory,
            _propagate,
        )
    except Exception as exc:  # pragma: no cover — defensive
        return ForecastReport(
            target=target, status="unavailable",
            reason=f"world_model unavailable: {exc}",
            step_unit=STEP_UNIT, horizon_steps=0, samples=0, jitter=0.0,
        )

    horizon_steps = max(HORIZON_MIN, min(HORIZON_MAX, int(horizon_steps)))
    samples = max(SAMPLES_MIN, min(SAMPLES_MAX, int(samples)))
    jitter = max(JITTER_MIN, min(JITTER_MAX, float(jitter)))

    if target not in NODES_BY_ID:
        return ForecastReport(
            target=target, status="unavailable",
            reason=f"unknown DAG node: {target!r}",
            step_unit=STEP_UNIT, horizon_steps=horizon_steps,
            samples=samples, jitter=jitter,
        )

    do_dict, err = _coerce_evidence(do, NODES_BY_ID, label="do")
    if err is not None:
        return ForecastReport(
            target=target, status="unavailable", reason=err,
            step_unit=STEP_UNIT, horizon_steps=horizon_steps,
            samples=samples, jitter=jitter,
        )
    observe_dict, err = _coerce_evidence(observe, NODES_BY_ID, label="observe")
    if err is not None:
        return ForecastReport(
            target=target, status="unavailable", reason=err,
            step_unit=STEP_UNIT, horizon_steps=horizon_steps,
            samples=samples, jitter=jitter,
        )

    # Pre-compute baselines for every node (single source of truth).
    baselines: Dict[str, float] = {n.id: float(n.baseline) for n in ALL_NODES}

    rng = np.random.default_rng(seed)
    trajectory: List[StepStats] = []

    for step in range(horizon_steps):
        # Per-step "ambient" overrides — drift on confounders only.
        ambient: Dict[str, float] = dict(observe_dict)
        for node_id, drift_fn in DRIFT_PROFILE.items():
            base = baselines[node_id]
            ambient[node_id] = base + drift_fn(step, base)
        # Honour explicit `observe` overrides ahead of drift.
        for k, v in observe_dict.items():
            ambient[k] = v

        target_values = np.empty(samples, dtype=float)
        for s in range(samples):
            # Build the per-sample do-overlay: caller's `do` wins,
            # then jitter on inputs/confounders that the caller did
            # NOT pin.
            sample_do: Dict[str, float] = dict(do_dict)
            for node_id in _JITTERABLE_NODES:
                if node_id in sample_do:
                    continue  # caller pinned it — no noise
                base = ambient.get(node_id, baselines[node_id])
                noise = rng.normal(0.0, jitter * max(abs(base), 1e-3))
                sample_do[node_id] = base + noise

            try:
                values = _propagate(do=sample_do, observe={})
            except Exception:  # pragma: no cover — defensive
                # One bad sample shouldn't kill the entire forecast.
                target_values[s] = baselines[target]
                continue
            target_values[s] = float(values[target])

        trajectory.append(StepStats(
            step=step,
            mean=float(np.mean(target_values)),
            std=float(np.std(target_values, ddof=1) if samples > 1 else 0.0),
            p05=float(np.quantile(target_values, 0.05)),
            p25=float(np.quantile(target_values, 0.25)),
            p50=float(np.quantile(target_values, 0.50)),
            p75=float(np.quantile(target_values, 0.75)),
            p95=float(np.quantile(target_values, 0.95)),
        ))

    p05_min = min(s.p05 for s in trajectory)
    p95_max = max(s.p95 for s in trajectory)
    summary = {
        "step_at_horizon": trajectory[-1].step,
        "mean_at_horizon": round(trajectory[-1].mean, 4),
        "p50_at_horizon": round(trajectory[-1].p50, 4),
        "p05_min_over_horizon": round(p05_min, 4),
        "p95_max_over_horizon": round(p95_max, 4),
        "ci90_at_horizon": [
            round(trajectory[-1].p05, 4), round(trajectory[-1].p95, 4),
        ],
        "trend": _classify_trend(trajectory),
    }

    return ForecastReport(
        target=target,
        status="degraded",
        reason=(
            "Monte Carlo sobre o NELO_DAG simbólico — útil para "
            "exploração de cenários. Sprint G + telemetria real "
            "elevará para status=ok."
        ),
        step_unit=STEP_UNIT,
        horizon_steps=horizon_steps,
        samples=samples,
        jitter=jitter,
        trajectory=trajectory,
        summary=summary,
        intervention=do_dict or None,
        observation=observe_dict or None,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _coerce_evidence(
    evidence: Optional[Mapping[str, Any]],
    nodes: Mapping[str, Any],
    *,
    label: str,
) -> tuple[Dict[str, float], Optional[str]]:
    """Validate + numerify a do/observe dict the same way
    ``causal_query`` does. Returns ``(coerced, error_or_None)``."""
    out: Dict[str, float] = {}
    if not evidence:
        return out, None
    for k, v in evidence.items():
        key = str(k)
        if key not in nodes:
            return out, f"unknown DAG node in {label}: {key!r}"
        try:
            out[key] = float(v)
        except (TypeError, ValueError):
            return out, (
                f"{label}[{key!r}] must be numeric, got "
                f"{type(v).__name__} ({v!r})"
            )
    return out, None


def _classify_trend(trajectory: List[StepStats]) -> str:
    """Coarse three-bucket trend label, useful for the LLM to verbalise.

    Compares mean at the horizon vs mean at step 0 with a 5 %
    relative tolerance (avoids labelling Gaussian wobble as "rising").
    """
    if len(trajectory) < 2:
        return "flat"
    first, last = trajectory[0].mean, trajectory[-1].mean
    base = max(abs(first), 1e-9)
    delta_pct = (last - first) / base
    if delta_pct > 0.05:
        return "rising"
    if delta_pct < -0.05:
        return "falling"
    return "flat"


__all__ = [
    "DRIFT_PROFILE",
    "ForecastReport",
    "STEP_UNIT",
    "StepStats",
    "forecast",
]
