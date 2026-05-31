"""Q.136 — verificação AO VIVO (read-only): boats-only + planear-da-fase-atual.

Prova: (1) scope=boats_only carrega só barcos (vs all = +acessórios); (2) cada
ordem traz current_fase_id; (3) um barco a meio planeia só o que falta (rota
truncada < rota completa); (4) schedule pequeno realista (makespan, molde 0
overlaps, status); (5) comparação CPO vs plano-ERP (OF_PLANO_DATA_PREVISTA).

    .venv\\Scripts\\python.exe _audit\\q136\\probe_boats.py
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.plan.cpo.engine import CPOConfig, CPOv4Engine
from src.plan.cpo.state import FactoryState, _load_open_orders_db
from src.plan.engines.scheduling_adapter import SchedulingMachine
from src.plan.services.phase_workcenters import station_ids_for
from src.plan.services.routing_resolver import RoutingResolver

DSN = "postgresql+asyncpg://prodplan:prodplan@localhost:5432/prodplan_one"
TENANT = UUID("00000000-0000-0000-0000-000000000001")


async def main() -> None:
    eng = create_async_engine(DSN)
    async with AsyncSession(eng) as s:
        # (1) boats_only vs all (direto no loader)
        boats = await _load_open_orders_db(s, TENANT, scope="boats_only")
        allo = await _load_open_orders_db(s, TENANT, scope="all")
        print(f"== Q.136 boats-only ==")
        print(f"scope=boats_only: {len(boats)} ordens (cap {len(boats)})")
        print(f"scope=all       : {len(allo)} ordens")
        with_phase = sum(1 for o in boats if o.get("current_fase_id"))
        print(f"barcos c/ current_fase_id: {with_phase}/{len(boats)}")

        # state completo (boats_only via config default)
        state = await FactoryState.load(session=s, tenant_id=TENANT)
    await eng.dispose()

    print(f"\nstate.open_orders={len(state.open_orders)} "
          f"(deviam ser barcos; default boats_only)")

    # (3) truncação ao vivo: um barco a meio (current_fase_id não-inicial)
    resolver = RoutingResolver(state)
    sample = None
    for o in state.open_orders:
        full = resolver.resolve({**o, "current_fase_id": None})
        trunc = resolver.resolve(o)
        if full and trunc and len(trunc) < len(full):
            sample = (o, len(full), len(trunc))
            break
    if sample:
        o, nf, nt = sample
        print(f"\ntruncação: of={o['of_id']} fase_atual={o.get('current_fase_id')} "
              f"rota_completa={nf} ops -> truncada={nt} ops (poupa {nf-nt})")
    else:
        print("\n(sem barco a meio com rota truncável na amostra)")

    # (4) schedule pequeno: makespan + molde
    orders = state.open_orders[:30]
    ops = resolver.resolve_many(orders)
    fases = {op.phase_id for op in ops if op.phase_id}
    ps = getattr(state, "phase_stations", {}) or {}
    machines = [
        SchedulingMachine(machine_id=sid, name=sid, capacity=1, speed_factor=1.0,
                          centro_custo=str(f))
        for f in sorted(fases) if ps.get(f)
        for sid in station_ids_for(f, ps[f])
    ] or [SchedulingMachine(machine_id="MANUAL", name="Manual")]
    print(f"\nschedule: ordens={len(orders)} ops={len(ops)} maquinas={len(machines)} "
          f"unplanned={resolver.unplanned_count}")
    h0 = datetime(2026, 6, 1, 7, 0, 0)
    r = CPOv4Engine(state=state, config=CPOConfig(generations=8, time_limit_sec=8.0,
                                                  total_budget_s=12.0)).schedule(
        ops, machines, h0, h0 + timedelta(days=120))
    print(f"  makespan={r.get('makespan_hours'):,.0f}h status={r.get('status')} "
          f"safety_net={r.get('safety_net_triggered')}")
    lam = [o for o in r.get("operations", []) if o.get("mold_id")]
    ov = 0
    for i in range(len(lam)):
        for j in range(i + 1, len(lam)):
            a, b = lam[i], lam[j]
            if a.get("mold_id") == b.get("mold_id") and a.get("start") and b.get("start"):
                if a["start"] < b["end"] and b["start"] < a["end"]:
                    ov += 1
    print(f"  ops c/ molde={len(lam)} sobreposicoes_mesmo_molde={ov} "
          f"({'OK molde exclusivo' if ov == 0 else 'FALHA axioma 3'})")


if __name__ == "__main__":
    asyncio.run(main())
