"""Q.134.I — probe 2: baseline (identity) vs mutações; idle/idle_ratio/n_workers."""
from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.plan.cpo.chromosome import Chromosome
from src.plan.cpo.decoder import decode
from src.plan.cpo.state import FactoryState
from src.plan.engines.scheduling_adapter import SchedulingMachine
from src.plan.services.phase_workcenters import station_ids_for
from src.plan.services.routing_resolver import RoutingResolver

DSN = "postgresql+asyncpg://prodplan:prodplan@localhost:5432/prodplan_one"
TENANT = UUID("00000000-0000-0000-0000-000000000001")
N_ORDERS = 30


def _nworkers(r):
    ws = set()
    for op in r.get("operations") or []:
        for w in (op.get("workers") or []):
            ws.add(w)
    return len(ws)


def _line(tag, r):
    print(f"  [{tag:9}] idle_h={r.get('total_idle_hours'):>12,.1f} "
          f"idle_ratio={r.get('idle_ratio'):.4f} "
          f"n_workers={_nworkers(r):>3} "
          f"makespan={r.get('makespan_hours'):>8,.0f}h")


async def main() -> None:
    eng = create_async_engine(DSN)
    async with AsyncSession(eng) as s:
        state = await FactoryState.load(session=s, tenant_id=TENANT)
    await eng.dispose()

    orders = state.open_orders[:N_ORDERS]
    ops = RoutingResolver(state).resolve_many(orders)
    fases = {o.phase_id for o in ops if o.phase_id}
    wc = [SchedulingMachine(machine_id=sid, name=sid, capacity=1, speed_factor=1.0,
                            centro_custo=str(f))
          for f in sorted(fases) if state.phase_stations.get(f)
          for sid in station_ids_for(f, state.phase_stations[f])]
    print(f"ops={len(ops)} wc_machines={len(wc)}")

    h0 = datetime(2026, 6, 1, 7, 0, 0)
    h1 = h0 + timedelta(days=120)
    n = len(ops)
    base = decode(Chromosome.identity(n), ops, wc, state, h0, h1)
    _line("baseline", base)
    for seed in (1, 2, 3):
        c = Chromosome.random(n, random.Random(seed))
        r = decode(c, ops, wc, state, h0, h1)
        _line(f"mut s={seed}", r)


if __name__ == "__main__":
    asyncio.run(main())
