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
from itertools import pairwise
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

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
    num_workers: int = 16           # threads de pesquisa (Q.174.F1: 8→16)
    random_seed: int = 42           # determinismo
    deterministic: bool = False     # True → max_deterministic_time (testes reproduzíveis)
    horizon_minutes: int = _DEFAULT_HORIZON_MINUTES
    # Q.174.F1 — parar a search com gap relativo aceitável (0.0 = provar
    # otimalidade, comportamento antigo). FEASIBLE já passa o gate axioma-7.
    relative_gap_limit: float = 0.02
    # Q.174.F1 — kill-switch do horizonte dinâmico (bench A/B + reversão).
    dynamic_horizon: bool = True


@dataclass
class CPSATTimingResult:
    """Output de `solve_timing`: start/end por op (minutos desde horizon_start)."""

    available: bool                              # ortools presente E resolveu
    status: str = "UNKNOWN"                      # OPTIMAL/FEASIBLE/INFEASIBLE/...
    starts_min: Dict[str, int] = field(default_factory=dict)  # op_id → start (min)
    ends_min: Dict[str, int] = field(default_factory=dict)    # op_id → end (min)
    makespan_min: int = 0
    objective_bound: float = 0.0                 # lower bound do solver (p/ gap)
    gap_pct: float = 0.0                         # Q.174.F1 — gap relativo (%)
    horizon_minutes_used: int = 0                # Q.174.F1 — domínio efetivo
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
        start_floors_min: Optional[Dict[str, int]] = None,
        relax_mold_cooldown: bool = False,
    ) -> CPSATTimingResult:
        """Devolve start/end (min desde horizon_start) por op, minimizando makespan.

        `hint_starts_min` (opcional) = warm-start de um schedule greedy (op_id→min).
        `relax_mold_cooldown=True` remove a EXTENSÃO de cooldown dos intervalos
        do cumulative de moldes (Q.174.F2) — usado como 1ª fase do two-stage
        (Q.174.S): no scope completo (~7.4k ops) o modelo com cooldown é
        demasiado duro para o solver encontrar a PRIMEIRA solução a frio
        (UNKNOWN no budget inteiro); a solução relaxada serve de warm-start
        à 2ª fase com o modelo completo. A exclusividade do molde (cap
        n_molds, dur-only) mantém-se mesmo relaxado.
        Sem ortools → available=False (o caller mantém o greedy).
        """
        t0 = time.time()
        if not HAS_ORTOOLS:
            return CPSATTimingResult(available=False, reason="ortools_unavailable")
        if not operations:
            return CPSATTimingResult(available=True, status="OPTIMAL")

        # Q.174.F1 — horizonte DINÂMICO: o domínio fixo de 150d (216.000 min)
        # mata a propagação quando o makespan real é semanas. Com warm-start
        # do greedy, o teto passa a max(hint)×margem (clamp ao fixo) — domínio
        # 3-10× mais apertado nos casos reais. Sem hint → teto fixo (como era).
        # A margem 1.5 evita infeasible artificial (o CP-SAT tem de poder
        # MELHORAR a ordem, não só comprimir o hint).
        H = int(self.config.horizon_minutes)
        if hint_starts_min and self.config.dynamic_horizon:
            try:
                hint_max = max(int(v) for v in hint_starts_min.values())
                if start_floors_min:
                    hint_max = max(
                        hint_max, *(int(v) for v in start_floors_min.values())
                    )
                dur_max = max(
                    1, *(round(float(o.duration_minutes)) for o in operations)
                )
                h_dyn = int((hint_max + dur_max) * 1.5)
                if 0 < h_dyn < H:
                    H = h_dyn
            except (ValueError, TypeError):  # pragma: no cover — hint sujo
                pass
        model = cp_model.CpModel()

        starts: Dict[str, Any] = {}
        ends: Dict[str, Any] = {}
        intervals: Dict[str, Any] = {}
        dur_min: Dict[str, int] = {}
        team: Dict[str, int] = {}
        op_by_id: Dict[str, Any] = {}

        # Q.174.F1 — fases SEM pool de operadores (cura/estado químico,
        # workers_for(fase) vazio) não disputam gente: demanda 0 nos
        # cumulative de operadores. Antes, cada op de Cura (380 no último
        # plano) levava team>=1 ao cumulative GLOBAL — procura FANTASMA de
        # operador que aperta o solver com gente que nunca é alocada
        # (o post-pass dá-lhes workers=[] por construção).
        # NOTA (refutação medida 2026-06-12): FP_PLANEAMENTO=0 NÃO serve para
        # isto — marca o âmbito do planeador de laminação do ERP e inclui
        # Montagem/Lixagem/Colagem (6.9k ops COM operadores reais). O critério
        # honesto é o pool vazio (mesmo do decoder/post-pass).
        _wf = getattr(state, "workers_for", None)

        def _has_pool(fase: str) -> bool:
            if _wf is None:
                return True
            try:
                return bool(_wf(fase))
            except Exception:  # pragma: no cover — defensivo
                return True

        pool_by_phase: Dict[str, bool] = {}

        for op in operations:
            oid = str(op.operation_id)
            op_by_id[oid] = op
            d = max(1, round(float(op.duration_minutes)))
            dur_min[oid] = d
            fase = str(op.phase_id)
            if fase not in pool_by_phase:
                pool_by_phase[fase] = _has_pool(fase)
            team[oid] = (
                max(1, int(getattr(op, "team_size", 1) or 1))
                if pool_by_phase[fase] else 0
            )
            s = model.NewIntVar(0, H, f"s_{oid}")
            e = model.NewIntVar(0, H, f"e_{oid}")
            iv = model.NewIntervalVar(s, d, e, f"i_{oid}")
            starts[oid], ends[oid], intervals[oid] = s, e, iv
            # Q.174.F6 — piso por op (ETA de material/componente). Clamp a H
            # (um piso além do domínio tornaria o modelo trivialmente
            # infeasible — o caso é declarado a montante via unplannable).
            if start_floors_min:
                fl = start_floors_min.get(oid)
                if fl is not None and fl > 0:
                    model.Add(s >= min(int(fl), H))

        # ── Precedência intra-OF (sequence) + gap de cura (wall-clock) ──────────
        by_order: Dict[str, List[Any]] = defaultdict(list)
        for op in operations:
            by_order[str(op.order_id)].append(op)
        for order_ops in by_order.values():
            # Q.169.G — tiebreak determinístico por operation_id: empates de
            # sequência (Laminagem/Infusão na mesma posição; reparações a 0)
            # ficam chainados numa ordem estável (o zip já os serializa).
            so = sorted(
                order_ops,
                key=lambda o: (
                    int(getattr(o, "sequence", 0) or 0),
                    str(o.operation_id),
                ),
            )
            for prev, cur in pairwise(so):
                gap_h = 0.0
                mg = getattr(state, "min_gap_hours", None)
                if mg is not None:
                    try:
                        gap_h = float(mg(prev.phase_id, cur.phase_id))
                    except Exception as _e:  # pragma: no cover — defensivo
                        logger.warning("state.min_gap_hours(%s→%s) failed: %s", prev.phase_id, cur.phase_id, _e)
                        gap_h = 0.0
                gap = max(0, round(gap_h * 60))
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
                except Exception as _e:  # pragma: no cover
                    logger.warning("state.num_stations_for(%s) failed: %s", fase, _e)
                    n_st = 1
            model.AddCumulative(ivs, [1] * len(ivs), n_st)
            # operadores da fase: demanda=team_size, cap=|pool apto|.
            pool = 0
            wf = getattr(state, "workers_for", None)
            if wf is not None:
                try:
                    pool = len(wf(fase))
                except Exception as _e:  # pragma: no cover
                    logger.warning("state.workers_for(%s) failed: %s", fase, _e)
                    pool = 0
            if pool > 0:
                demands = [team[str(o.operation_id)] for o in fase_ops]
                # cap >= maior demanda individual da fase (senão infeasible trivial:
                # fase pair-required team=2 com pool=1). Espelha o downgrade
                # pair→solo do decoder (Sprint Q.8) — nunca bloqueia a fase.
                cap_phase = max(pool, max(demands, default=1))
                model.AddCumulative(ivs, demands, cap_phase)

        # ── Cumulative GLOBAL de operadores (~106 ativos) ───────────────────────
        # Q.174.F1 — só ops com demanda real (team>0): fases sem pool (cura/
        # estado) ficam fora — interval com demanda 0 só pesava no modelo.
        n_active = _active_operator_count(state)
        all_ivs = [
            intervals[str(o.operation_id)] for o in operations
            if team[str(o.operation_id)] > 0
        ]
        all_dem = [
            team[str(o.operation_id)] for o in operations
            if team[str(o.operation_id)] > 0
        ]
        if all_ivs:
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
        # Q.174.F2 — cooldown canónico: o molde fica ocupado dur+cooldown
        # (cura no molde + preparação; Plano_Planeia bloqueia ≈24h, Ocean
        # ≈72h). Intervalos ESTENDIDOS só no cumulative dos moldes (a op em
        # si não muda). Relaxação anónima: usa o MENOR cooldown dos moldes do
        # modelo (o post-pass aplica o exato por molde escolhido).
        mch = getattr(state, "mold_cooldown_hours", None)

        def _cd_min_for(model_id: str) -> int:
            if mch is None or relax_mold_cooldown:
                return 0
            try:
                if mfm is not None and not model_id.startswith("order::"):
                    molds = mfm(model_id)
                    if molds:
                        return round(60 * min(
                            float(mch(m.molde_id)) for m in molds
                        ))
                return round(60 * float(mch(None)))
            except Exception:  # pragma: no cover — defensivo
                return 0

        for model_id, mops in by_model_mold.items():
            n_molds = 1
            if mfm is not None and not model_id.startswith("order::"):
                try:
                    n_molds = max(1, len(mfm(model_id)))
                except Exception as _e:  # pragma: no cover
                    logger.warning("state.molds_for_model(%s) failed: %s", model_id, _e)
                    n_molds = 1
            cd = _cd_min_for(model_id)
            if cd > 0:
                ivs = [
                    model.NewFixedSizeIntervalVar(
                        starts[str(o.operation_id)],
                        dur_min[str(o.operation_id)] + cd,
                        f"im_{o.operation_id}",
                    )
                    for o in mops
                ]
            else:
                ivs = [intervals[str(o.operation_id)] for o in mops]
            model.AddCumulative(ivs, [1] * len(ivs), n_molds)

        # ── Makespan + objetivo ─────────────────────────────────────────────────
        makespan = model.NewIntVar(0, H, "makespan")
        for oid in ends:
            model.Add(makespan >= ends[oid])

        # Q.169.D — tardiness EVITÁVEL no objetivo. O solve minimizava SÓ
        # makespan: as due dates (79% das ordens desde Q.168.A) não
        # constrangiam nada. effective_due = max(due, horizonte) — mesmo
        # racional do decoder_kpis (Q.153.A2): ordens já vencidas ganham o
        # gradiente "acabar quanto antes" SEM a dívida histórica dominar.
        # Pesos 1:1 em minutos: 1 min de atraso de uma ordem vale 1 min de
        # makespan — trade-off económico simples e auditável.
        tard_vars: List[Any] = []
        for order_id, order_ops in by_order.items():
            dues = [
                d for d in (getattr(o, "due_date", None) for o in order_ops)
                if d is not None
            ]
            if not dues:
                continue
            due_min = int(max(
                0.0, (min(dues) - horizon_start).total_seconds() / 60.0,
            ))
            due_min = min(due_min, H)
            o_end = model.NewIntVar(0, H, f"oend_{order_id}")
            model.AddMaxEquality(
                o_end, [ends[str(o.operation_id)] for o in order_ops],
            )
            t = model.NewIntVar(0, H, f"tard_{order_id}")
            model.Add(t >= o_end - due_min)
            tard_vars.append(t)

        if tard_vars:
            model.Minimize(makespan + sum(tard_vars))
        else:
            model.Minimize(makespan)

        # ── Warm-start (hint) do greedy ─────────────────────────────────────────
        if hint_starts_min:
            for oid, s in starts.items():
                hv = hint_starts_min.get(oid)
                if hv is not None and 0 <= int(hv) <= H:
                    model.AddHint(s, int(hv))
            # Hints para operações não presentes em main_ops (ex.: fases de
            # reparação 14/76/77 excluídas pelo cpsat_global) são ignoradas
            # silenciosamente acima. Logar em DEBUG para troubleshooting.
            ignored_hints = set(hint_starts_min.keys()) - set(starts.keys())
            if ignored_hints:
                logger.debug(
                    "CP-SAT: %d hints ignoradas para ops fora de main_ops "
                    "(fases reparação?): %s",
                    len(ignored_hints),
                    sorted(ignored_hints)[:20],
                )

        # Q.174.F1 — DecisionStrategy: fixar primeiro os starts das ordens com
        # due mais cedo, ao valor mínimo (EDD greedy como guia da pesquisa).
        # Só quando há due dates suficientes (>=20% das ordens) — sem elas a
        # heurística não tem sinal e pode atrasar a prova de otimalidade.
        if tard_vars and len(tard_vars) * 5 >= len(by_order):
            due_sorted_starts: List[Any] = []
            order_due: List[Tuple[int, str]] = []
            for order_id, order_ops in by_order.items():
                dues = [
                    d for d in (getattr(o, "due_date", None) for o in order_ops)
                    if d is not None
                ]
                if not dues:
                    continue
                dm = int(max(
                    0.0, (min(dues) - horizon_start).total_seconds() / 60.0,
                ))
                order_due.append((dm, str(order_id)))
            for _dm, order_id in sorted(order_due):
                for o in by_order[order_id]:
                    due_sorted_starts.append(starts[str(o.operation_id)])
            if due_sorted_starts:
                model.AddDecisionStrategy(
                    due_sorted_starts,
                    cp_model.CHOOSE_FIRST,
                    cp_model.SELECT_MIN_VALUE,
                )

        # ── Solve ───────────────────────────────────────────────────────────────
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = int(self.config.num_workers)
        solver.parameters.random_seed = int(self.config.random_seed)
        # Q.174.F1 — parar cedo com gap aceitável (FEASIBLE já passa o gate;
        # 300s a provar otimalidade de um plano 2% pior é budget desperdiçado)
        # + linearization_level=2 (relaxação LP mais forte p/ cumulative).
        solver.parameters.relative_gap_limit = float(self.config.relative_gap_limit)
        solver.parameters.linearization_level = 2
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
        # Q.174.F1 — gap relativo persistível (objetivo vs lower bound): diz
        # se vale investir em mais tempo de search ou em modelo melhor.
        obj = float(solver.ObjectiveValue())
        bound = float(solver.BestObjectiveBound())
        gap_pct = (
            round(100.0 * (obj - bound) / obj, 2) if obj > 0 else 0.0
        )
        return CPSATTimingResult(
            available=True,
            status=status_name,
            starts_min=starts_out,
            ends_min=ends_out,
            makespan_min=int(solver.Value(makespan)),
            objective_bound=bound,
            gap_pct=gap_pct,
            horizon_minutes_used=H,
            solve_time_s=time.time() - t0,
        )
