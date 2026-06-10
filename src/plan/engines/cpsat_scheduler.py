"""ProdPlan ONE — CPO CP-SAT Global Scheduler (Q.166).

Otimizador GLOBAL de makespan (OR-Tools CP-SAT) que substitui o greedy/GA, que
estava estruturalmente 5-10× acima do teto de capacidade. Faz só o TIMING (start/
end por op respeitando capacidades CUMULATIVE + precedência + cura) minimizando o
makespan; a atribuição concreta de operador/molde/estação é um POST-PASS separado
(`cpsat_postpass.py`, reusa o load-balance Q.164.A + earliest-free molde Q.165.C).

Modelo (RCPSP cumulative — NÃO per-worker NoOverlap, o bug do `cpsat_lrho` morto):
  * 1 IntervalVar por op (duração = touch-time em minutos, inteiro).
  * Precedência intra-OF por `sequence` + gap de cura wall-clock (`min_gap_hours`).
  * Cumulative por fase: estações (cap=`num_stations_for`) e pool de operadores da
    fase (demanda=team_size, cap=|workers_for|).
  * Cumulative GLOBAL de operadores (demanda=team_size, cap=nº ativos dinâmico,
    união do skill_matrix) —
    resolve o duplo-conta do operador polivalente sem per-worker NoOverlap.
  * Cumulative de moldes por modelo (cap=|molds_for_model|; 1 molde → exclusivo).
  * Objetivo: minimizar makespan. 24/7 wall-clock (o calendário é um finalizador à parte).

OR-Tools é opcional: sem `ortools` → `solve_timing` devolve `available=False` e o
caller mantém o greedy (fallback). Determinístico (`random_seed`).
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:  # pragma: no cover — ortools é opcional em runtime
    from ortools.sat.python import cp_model  # type: ignore

    HAS_ORTOOLS = True
except Exception:  # pragma: no cover
    cp_model = None  # type: ignore
    HAS_ORTOOLS = False


# Domínio temporal por defeito (minutos): ~150 dias. Apertar o domínio é crítico
# para a propagação do CP-SAT (um domínio de 3.6 anos mata o solver). É um TETO de
# horizonte 24/7; o makespan real (calendário) é maior mas o finalizador trata disso.
_DEFAULT_HORIZON_MINUTES = 150 * 24 * 60


@dataclass
class CPSATConfig:
    """Parâmetros do solver CP-SAT global (Q.166)."""

    budget_s: float = 30.0          # orçamento de tempo (robô passa 300-1200s)
    num_workers: int = 8            # threads de pesquisa
    random_seed: int = 42           # determinismo
    deterministic: bool = False     # True → max_deterministic_time (testes reproduzíveis)
    horizon_minutes: int = _DEFAULT_HORIZON_MINUTES


@dataclass
class CPSATTimingResult:
    """Output de `solve_timing`: start/end por op (minutos desde horizon_start)."""

    available: bool                              # ortools presente E resolveu
    status: str = "UNKNOWN"                      # OPTIMAL/FEASIBLE/INFEASIBLE/...
    starts_min: Dict[str, int] = field(default_factory=dict)  # op_id → start (min)
    ends_min: Dict[str, int] = field(default_factory=dict)    # op_id → end (min)
    makespan_min: int = 0
    objective_bound: float = 0.0                 # lower bound do solver (p/ gap)
    solve_time_s: float = 0.0
    reason: str = ""                             # quando available=False


def _active_operator_count(state: Any) -> int:
    """Nº de operadores ATIVOS distintos (cap global). União dos pools por fase do
    skill_matrix (já filtrado a ativos, Q.160). Mínimo 1 para não bloquear."""
    matrix = getattr(state, "skill_matrix", {}) or {}
    distinct: set = set()
    for pool in matrix.values():
        distinct.update(pool)
    return max(1, len(distinct))


class CPSATScheduler:
    """Resolve o TIMING global (makespan) com CP-SAT cumulative. Stateless."""

    def __init__(self, config: Optional[CPSATConfig] = None) -> None:
        self.config = config or CPSATConfig()

    def solve_timing(
        self,
        operations: List[Any],          # List[SchedulingOperation]
        state: Any,                     # FactoryState
        horizon_start: datetime,
        *,
        hint_starts_min: Optional[Dict[str, int]] = None,
    ) -> CPSATTimingResult:
        """Devolve start/end (min desde horizon_start) por op, minimizando makespan.

        `hint_starts_min` (opcional) = warm-start de um schedule greedy (op_id→min).
        Sem ortools → available=False (o caller mantém o greedy).
        """
        t0 = time.time()
        if not HAS_ORTOOLS:
            return CPSATTimingResult(available=False, reason="ortools_unavailable")
        if not operations:
            return CPSATTimingResult(available=True, status="OPTIMAL")

        H = int(self.config.horizon_minutes)
        model = cp_model.CpModel()

        starts: Dict[str, Any] = {}
        ends: Dict[str, Any] = {}
        intervals: Dict[str, Any] = {}
        dur_min: Dict[str, int] = {}
        team: Dict[str, int] = {}
        op_by_id: Dict[str, Any] = {}

        for op in operations:
            oid = str(op.operation_id)
            op_by_id[oid] = op
            d = max(1, int(round(float(op.duration_minutes))))
            dur_min[oid] = d
            team[oid] = max(1, int(getattr(op, "team_size", 1) or 1))
            s = model.NewIntVar(0, H, f"s_{oid}")
            e = model.NewIntVar(0, H, f"e_{oid}")
            iv = model.NewIntervalVar(s, d, e, f"i_{oid}")
            starts[oid], ends[oid], intervals[oid] = s, e, iv

        # ── Precedência intra-OF (sequence) + gap de cura (wall-clock) ──────────
        by_order: Dict[str, List[Any]] = defaultdict(list)
        for op in operations:
            by_order[str(op.order_id)].append(op)
        for order_ops in by_order.values():
            so = sorted(order_ops, key=lambda o: int(getattr(o, "sequence", 0) or 0))
            for prev, cur in zip(so, so[1:]):
                gap_h = 0.0
                mg = getattr(state, "min_gap_hours", None)
                if mg is not None:
                    try:
                        gap_h = float(mg(prev.phase_id, cur.phase_id))
                    except Exception:  # pragma: no cover — defensivo
                        gap_h = 0.0
                gap = max(0, int(round(gap_h * 60)))
                model.Add(starts[str(cur.operation_id)]
                          >= ends[str(prev.operation_id)] + gap)

        # ── Cumulative por fase: estações + pool de operadores da fase ──────────
        by_phase: Dict[str, List[Any]] = defaultdict(list)
        for op in operations:
            by_phase[str(op.phase_id)].append(op)
        for fase, fase_ops in by_phase.items():
            ivs = [intervals[str(o.operation_id)] for o in fase_ops]
            # estações: cada op ocupa 1 estação; cap = nº estações paralelas reais.
            n_st = 1
            nsf = getattr(state, "num_stations_for", None)
            if nsf is not None:
                try:
                    n_st = max(1, int(nsf(fase)))
                except Exception:  # pragma: no cover
                    n_st = 1
            model.AddCumulative(ivs, [1] * len(ivs), n_st)
            # operadores da fase: demanda=team_size, cap=|pool apto|.
            pool = 0
            wf = getattr(state, "workers_for", None)
            if wf is not None:
                try:
                    pool = len(wf(fase))
                except Exception:  # pragma: no cover
                    pool = 0
            if pool > 0:
                demands = [team[str(o.operation_id)] for o in fase_ops]
                # cap >= maior demanda individual da fase (senão infeasible trivial:
                # fase pair-required team=2 com pool=1). Espelha o downgrade
                # pair→solo do decoder (Sprint Q.8) — nunca bloqueia a fase.
                cap_phase = max(pool, max(demands, default=1))
                model.AddCumulative(ivs, demands, cap_phase)

        # ── Cumulative GLOBAL de operadores (~106 ativos) ───────────────────────
        n_active = _active_operator_count(state)
        all_ivs = [intervals[str(o.operation_id)] for o in operations]
        all_dem = [team[str(o.operation_id)] for o in operations]
        # cap global >= max demanda individual (senão infeasible artificial).
        cap_global = max(n_active, max(all_dem, default=1))
        model.AddCumulative(all_ivs, all_dem, cap_global)

        # ── Cumulative de moldes por modelo ─────────────────────────────────────
        # Q.169.C — ops com mold_required mas SEM model_id iam TODAS para a
        # chave '' com capacidade 1: barcos não-relacionados ficavam
        # serializados num molde fantasma (sobre-restrição apanhada pela
        # matriz de paridade Q.169.A). Sem modelo não se conhece o molde —
        # agrupa-se por BARCO (a precedência intra-OF já serializa as fases
        # do próprio barco; barcos distintos não partilham molde conhecido).
        by_model_mold: Dict[str, List[Any]] = defaultdict(list)
        for op in operations:
            if bool(getattr(op, "mold_required", False)):
                mid = str(getattr(op, "model_id", "") or "")
                key = mid if mid else f"order::{op.order_id}"
                by_model_mold[key].append(op)
        mfm = getattr(state, "molds_for_model", None)
        for model_id, mops in by_model_mold.items():
            n_molds = 1
            if mfm is not None and not model_id.startswith("order::"):
                try:
                    n_molds = max(1, len(mfm(model_id)))
                except Exception:  # pragma: no cover
                    n_molds = 1
            ivs = [intervals[str(o.operation_id)] for o in mops]
            model.AddCumulative(ivs, [1] * len(ivs), n_molds)

        # ── Makespan + objetivo ─────────────────────────────────────────────────
        makespan = model.NewIntVar(0, H, "makespan")
        for oid in ends:
            model.Add(makespan >= ends[oid])
        model.Minimize(makespan)

        # ── Warm-start (hint) do greedy ─────────────────────────────────────────
        if hint_starts_min:
            for oid, s in starts.items():
                hv = hint_starts_min.get(oid)
                if hv is not None and 0 <= int(hv) <= H:
                    model.AddHint(s, int(hv))

        # ── Solve ───────────────────────────────────────────────────────────────
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = int(self.config.num_workers)
        solver.parameters.random_seed = int(self.config.random_seed)
        if self.config.deterministic:
            solver.parameters.max_deterministic_time = float(self.config.budget_s)
        else:
            solver.parameters.max_time_in_seconds = float(self.config.budget_s)

        status = solver.Solve(model)
        status_name = solver.StatusName(status)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return CPSATTimingResult(
                available=False, status=status_name,
                reason=f"no_solution:{status_name}",
                solve_time_s=time.time() - t0,
            )

        starts_out = {oid: int(solver.Value(s)) for oid, s in starts.items()}
        ends_out = {oid: int(solver.Value(e)) for oid, e in ends.items()}
        return CPSATTimingResult(
            available=True,
            status=status_name,
            starts_min=starts_out,
            ends_min=ends_out,
            makespan_min=int(solver.Value(makespan)),
            objective_bound=float(solver.BestObjectiveBound()),
            solve_time_s=time.time() - t0,
        )
