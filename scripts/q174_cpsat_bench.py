"""Q.174.F1 — benchmark A/B do CP-SAT global sobre os dados REAIS.

Mede o efeito das mudanças de desempenho (demanda-fantasma zerada, parâmetros
relative_gap_limit/linearization, 16 workers, DecisionStrategy por due,
horizonte dinâmico) no op-set real do tenant dev, SEM tocar na BD (read-only:
carrega FactoryState + resolve as rotas, corre `solve_timing` em memória).

Variantes:
  A. OLD-cold  — sem hint, H fixo 150d, 8 workers, gap 0 (provar otimalidade)
  B. NEW-cold  — sem hint, H fixo, 16 workers, gap 2%, strategy, demanda-0
  C. OLD-warm  — hint (solução de B), H FIXO, 8 workers, gap 0
  D. NEW-warm  — hint (solução de B), H DINÂMICO, 16 workers, gap 2%, strategy

Uso::

    $env:PYTHONPATH = "."
    .\\.venv\\Scripts\\python.exe scripts/q174_cpsat_bench.py --budget 60
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from uuid import UUID

DEV_TENANT = UUID("00000000-0000-0000-0000-000000000001")


async def _load_ops():
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    from src.plan.cpo.state import REPAIR_PHASE_IDS, FactoryState
    from src.plan.services.routing_resolver import RoutingResolver
    from src.shared.config import settings

    eng = create_async_engine(settings.database_url)
    # naive local (os tempos do CPO são naive — padrão do decoder)
    horizon_start = datetime.now().replace(microsecond=0)  # noqa: DTZ005
    async with AsyncSession(eng) as session:
        state = await FactoryState.load(session, DEV_TENANT, plan_cap=0)
        orders = state.open_orders
        resolver = RoutingResolver(state)
        operations = resolver.resolve_many(orders, horizon_start=horizon_start)
    await eng.dispose()

    repair_ids = frozenset(
        getattr(state, "repair_phase_ids", None) or REPAIR_PHASE_IDS
    )
    main_ops = [o for o in operations if str(o.phase_id) not in repair_ids]
    return state, main_ops, horizon_start


def _solve(state, ops, horizon_start, *, budget, old: bool, hint=None,
           dynamic: bool = True):
    from src.plan.engines.cpsat_scheduler import CPSATConfig, CPSATScheduler

    if old:
        cfg = CPSATConfig(
            budget_s=budget, num_workers=8, relative_gap_limit=0.0,
            dynamic_horizon=False,
        )
    else:
        cfg = CPSATConfig(budget_s=budget, dynamic_horizon=dynamic)
    return CPSATScheduler(cfg).solve_timing(
        ops, state, horizon_start, hint_starts_min=hint,
    )


def _row(label, t):
    print(f"{label:<10} status={t.status:<8} makespan={t.makespan_min/60.0:8.1f}h "
          f"gap={t.gap_pct:5.2f}% H={t.horizon_minutes_used or 0:>7}min "
          f"solve={t.solve_time_s:6.1f}s")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--budget", type=float, default=60.0)
    args = parser.parse_args()

    state, ops, horizon_start = asyncio.run(_load_ops())
    n_zero_pool = sum(
        1 for o in ops if not (state.workers_for(str(o.phase_id)) or set())
    )
    print(f"ops={len(ops)} (sem-pool={n_zero_pool}) | budget={args.budget}s")

    a = _solve(state, ops, horizon_start, budget=args.budget, old=True)
    _row("A old-cold", a)
    b = _solve(state, ops, horizon_start, budget=args.budget, old=False,
               dynamic=False)
    _row("B new-cold", b)
    hint = dict(b.starts_min) if b.available else None
    if hint:
        c = _solve(state, ops, horizon_start, budget=args.budget, old=True,
                   hint=hint)
        _row("C old-warm", c)
        d = _solve(state, ops, horizon_start, budget=args.budget, old=False,
                   hint=hint, dynamic=True)
        _row("D new-warm", d)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
