"""Q.166.G — harness de validação (READ-ONLY) do solver CP-SAT global.

Prova, no WIP real, que o plano escoa em 2-5 meses ao ritmo da fábrica (~14.7
barcos/dia), SEM persistir nada (não cria commit). Corre:
  load FactoryState → resolve (touch-time/canoas/rota-comum) → excluir reparações →
  CP-SAT timing (24/7) → post-pass concreto+calendário → KPIs.

Uso:
  & .\.venv\Scripts\python.exe scripts/cpsat_wip_clearance_validation.py [budget_s]

Read-only: lê factory_raw/plan; NÃO escreve. Exit 0 se makespan ∈ [2,5] meses.
"""
import asyncio
import sys
from datetime import datetime
from uuid import UUID

from src.shared.database import get_session_context
from src.plan.cpo.state import FactoryState, REPAIR_PHASE_IDS
from src.plan.services.routing_resolver import RoutingResolver
from src.plan.engines.cpsat_scheduler import CPSATScheduler, CPSATConfig, HAS_ORTOOLS
from src.plan.engines.cpsat_postpass import assign_concrete
from src.plan.cpo.decoder_kpis import build_result_dict

TENANT = UUID("00000000-0000-0000-0000-000000000001")


async def main(budget_s: float) -> int:
    if not HAS_ORTOOLS:
        print("ortools não instalado — não é possível validar.")
        return 2
    h0 = datetime.utcnow()
    async with get_session_context() as session:
        state = await FactoryState.load(session, TENANT, plan_cap=0)
        machines = []  # timing usa state.num_stations_for; KPIs só contam len(machines)
        ops_all = RoutingResolver(state).resolve_many(state.open_orders, horizon_start=h0)

    ops = [o for o in ops_all if str(o.phase_id) not in REPAIR_PHASE_IDS]
    timing = CPSATScheduler(
        CPSATConfig(budget_s=budget_s, num_workers=8)
    ).solve_timing(ops, state, h0)
    if not timing.available:
        print("CP-SAT não devolveu solução:", timing.reason)
        return 2
    scheduled = assign_concrete(ops, state, h0, timing.starts_min)
    result = build_result_dict(scheduled, ops, machines, h0, h0, engine_used="cpsat_global")

    boats = len({s.order_id for s in scheduled})
    mk_h = float(result["makespan_hours"])
    months = mk_h / 24 / 30.4
    work_days = (mk_h / 24) * 6.0 / 7.0  # Seg-Sáb
    rate = boats / work_days if work_days > 0 else 0.0
    print("=== Q.166.G VALIDAÇÃO CP-SAT (read-only) ===")
    print(f"barcos no plano  : {boats}")
    print(f"ops              : {len(ops)} (reparações excluídas: {len(ops_all) - len(ops)})")
    print(f"makespan_24x7    : {round(timing.makespan_min / 60 / 24, 1)} dias")
    print(f"makespan calend. : {round(mk_h)} h = {round(months, 1)} meses")
    print(f"ritmo            : {round(rate, 1)} barcos/dia útil (alvo ~14.7)")
    print(f"cpsat            : {timing.status} em {round(timing.solve_time_s, 1)}s")
    ok = 2.0 <= months <= 5.0
    print("RESULTADO        :", "OK (2-5 meses)" if ok else "FORA do alvo 2-5 meses")
    return 0 if ok else 1


if __name__ == "__main__":
    b = float(sys.argv[1]) if len(sys.argv) > 1 else 180.0
    sys.exit(asyncio.run(main(b)))
