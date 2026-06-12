"""ProdPlan ONE — CP-SAT Global orchestrator (Q.166.F).

Cola as 3 peças do otimizador global de makespan e devolve o result-dict CANÓNICO
(o mesmo contrato do decoder, via `build_result_dict`):

    1. excluir fases de reparação (fluxo separado — decisão do dono);
    2. `CPSATScheduler.solve_timing` — TIMING global 24/7 (cumulative + makespan);
    3. `assign_concrete` — recursos concretos + calendário (Seg-Sáb);
    4. `build_result_dict` — KPIs idênticos ao decoder.

Best-effort: sem ortools / sem solução / sem ops → devolve None (o caller mantém o
greedy — fallback). NUNCA crasha o scheduler.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Union

from src.plan.cpo.decoder_kpis import build_result_dict
from src.plan.cpo.state import REPAIR_PHASE_IDS
from src.plan.engines.cpsat_postpass import assign_concrete
from src.plan.engines.cpsat_scheduler import (
    HAS_ORTOOLS,
    CPSATConfig,
    CPSATScheduler,
)

logger = logging.getLogger(__name__)


def greedy_hint_minutes(
    baseline: Dict[str, Any],
    horizon_start: datetime,
) -> Dict[str, int]:
    """Converte os starts do schedule greedy (baseline) em minutos desde
    horizon_start, para warm-start (`AddHint`) do CP-SAT. Best-effort → {}."""
    out: Dict[str, int] = {}
    for op in baseline.get("operations", []) or []:
        oid = op.get("operation_id")
        st = op.get("start_time") or op.get("start")
        if not oid or not st:
            continue
        try:
            dt = datetime.fromisoformat(str(st).replace("Z", "+00:00"))
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            m = int((dt - horizon_start).total_seconds() / 60.0)
            if m >= 0:
                out[str(oid)] = m
        except (ValueError, TypeError):  # pragma: no cover — defensivo
            continue
    return out


def run_cpsat_global(
    state: Any,
    operations: List[Any],
    machines: List[Any],
    horizon_start: datetime,
    horizon_end: datetime,
    *,
    config: Optional[CPSATConfig] = None,
    greedy_hint: Optional[Dict[str, int]] = None,
    product_price_eur: Optional[Mapping[str, Union[float, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """Corre o pipeline CP-SAT global e devolve o result-dict, ou None (fallback)."""
    if not HAS_ORTOOLS:
        return None
    # 1) separar fases de reparação — Q.173.L: ids efetivos vêm do state
    # (config de tenant `planning`/`repair.phase_ids`; default {14,76,77}).
    repair_ids = (
        frozenset(getattr(state, "repair_phase_ids", None) or REPAIR_PHASE_IDS)
    )
    main_ops = [o for o in operations if str(o.phase_id) not in repair_ids]
    repair_ops = [o for o in operations if str(o.phase_id) in repair_ids]
    if not main_ops:
        return None

    # 2) TIMING global (24/7, cumulative, makespan) — só ops principais:
    # reparações são rotas truncadas de 1 op, sem ganho no solver.
    timing = CPSATScheduler(config or CPSATConfig()).solve_timing(
        main_ops, state, horizon_start, hint_starts_min=greedy_hint,
    )
    if not timing.available:
        logger.info("CP-SAT global indisponível (%s) — fallback ao greedy", timing.reason)
        return None

    # 3) recursos concretos + calendário — Q.173.Q (decisão Luis 2026-06-11):
    # as REPARAÇÕES entram no MESMO plano (merge-back). O assign_concrete usa
    # o start do CP-SAT como PISO e resolve conflitos de operador/molde/cura/
    # precedência por construção — as reparações (sem start no timing → piso
    # 0) são colocadas primeiro, consistente com a prioridade repair_rank do
    # loader (Q.161.A). Antes, quando o CP-SAT ganhava, as ~76 OFs de
    # reparação DESAPARECIAM do plano servido (auditoria 2026-06-11). Bónus:
    # o result fica comensurável com o baseline greedy no gate axioma-7
    # (ambos incluem reparações).
    # Q.173.Q.1 — ordens MISTAS (reparação + fases principais na mesma rota):
    # o piso 0 da reparação não pode atropelar irmãs de sequência INFERIOR já
    # temporizadas pelo CP-SAT — o assign_concrete só serializa contra irmãs
    # processadas antes, e o validador estrutural recusa o commit ("um barco
    # não está em 2 fases"; 13 violações na validação live de 2026-06-11).
    # Piso da reparação = fim (start+dur) da irmã anterior mais tardia.
    # Ordens SÓ-reparação (as ~76 OFs) mantêm piso 0 → prioridade.
    starts = dict(timing.starts_min)
    main_by_order: Dict[str, List[Any]] = {}
    for o in main_ops:
        main_by_order.setdefault(str(o.order_id), []).append(o)
    for r in repair_ops:
        sibs = main_by_order.get(str(r.order_id))
        if not sibs:
            continue
        r_seq = int(getattr(r, "sequence", 0) or 0)
        floor_min = 0
        for s in sibs:
            if int(getattr(s, "sequence", 0) or 0) < r_seq:
                s_start = int(starts.get(str(s.operation_id), 0))
                s_dur = int(float(getattr(s, "duration_minutes", 0) or 0))
                floor_min = max(floor_min, s_start + s_dur)
        if floor_min:
            starts[str(r.operation_id)] = floor_min

    all_ops = repair_ops + main_ops
    scheduled = assign_concrete(all_ops, state, horizon_start, starts)

    # 4) result-dict canónico (mesmo contrato do decoder).
    result = build_result_dict(
        scheduled, all_ops, machines, horizon_start, horizon_end,
        product_price_eur=product_price_eur,
        engine_used="cpsat_global",
    )
    n_boats = len({s.order_id for s in scheduled})
    result["cpo_meta"] = {
        "engine": "cpsat_global",
        "cpsat_status": timing.status,
        "cpsat_solve_time_s": round(timing.solve_time_s, 1),
        "makespan_hours_24x7": round(timing.makespan_min / 60.0, 2),
        "cpsat_objective_bound_min": round(timing.objective_bound, 1),
        # Q.174.F1 — gap relativo + domínio efetivo: dizem se o próximo
        # investimento é mais tempo de search ou modelo melhor (auditável
        # pela BD, sem logs).
        "cpsat_gap_pct": timing.gap_pct,
        "cpsat_horizon_minutes": timing.horizon_minutes_used,
        "repair_ops_merged": len(repair_ops),
        "boats_in_main_plan": n_boats,
    }
    return result
