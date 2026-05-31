"""Q.134.I — probe: de onde vem a violação de idle no safety_net com work-centers.

Decoda baseline (identity) vs uma mutação e mede total_idle_hours / idle_ratio /
n_active_workers / num_machines, e corre apply_safety_net p/ ver o que dispara.
Read-only.
    .venv\\Scripts\\python.exe _audit\\q134\\probe_idle.py
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.plan.cpo.engine import CPOConfig, CPOv4Engine
from src.plan.cpo.safety_net import apply_safety_net
from src.plan.cpo.state import FactoryState
from src.plan.engines.scheduling_adapter import SchedulingMachine
from src.plan.services.phase_workcenters import station_ids_for
from src.plan.services.routing_resolver import RoutingResolver

DSN = "postgresql+asyncpg://prodplan:prodplan@localhost:5432/prodplan_one"
TENANT = UUID("00000000-0000-0000-0000-000000000001")
N_ORDERS = 30


def _summ(tag, r):
    print(f"  [{tag}] makespan={r.get('makespan_hours'):,.0f}h "
          f"idle_h={r.get('total_idle_hours'):,.1f} "
          f"idle_ratio={r.get('idle_ratio')} "
          f"num_machines={r.get('num_machines')} "
          f"ops={len(r.get('operations') or [])}")


async def main() -> None:
    eng = create_async_engine(DSN)
    async with AsyncSession(eng) as s:
        state = await FactoryState.load(session=s, tenant_id=TENANT)
    await eng.dispose()

    orders = state.open_orders[:N_ORDERS]
    resolver = RoutingResolver(state)
    ops = resolver.resolve_many(orders)
    fases = {o.phase_id for o in ops if o.phase_id}
    wc = [SchedulingMachine(machine_id=sid, name=sid, capacity=1, speed_factor=1.0,
                            centro_custo=str(f))
          for f in sorted(fases) if state.phase_stations.get(f)
          for sid in station_ids_for(f, state.phase_stations[f])]
    print(f"ordens={len(orders)} ops={len(ops)} wc_machines={len(wc)}")

    cfg = CPOConfig(generations=12, time_limit_sec=8.0, total_budget_s=12.0)
    e = CPOv4Engine(state=state, config=cfg)
    h0 = datetime(2026, 6, 1, 7, 0, 0)
    r = e.schedule(ops, wc, h0, h0 + timedelta(days=120))
    print("\nresultado final do engine:")
    _summ("final", r)
    print(f"  safety_net_triggered={r.get('safety_net_triggered')} "
          f"status={r.get('status')}")


if __name__ == "__main__":
    asyncio.run(main())
