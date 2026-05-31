"""Q.133.B — verificação AO VIVO: N estações paralelas por fase.

Prova: (1) state.phase_stations vem da concorrência real; (2) com work-centers o
makespan CAI vs o pool MANUAL único (paralelismo); (3) o molde continua a
serializar (axioma 3 intacto). Read-only ao motor (não escreve commit).

    .venv\\Scripts\\python.exe _audit\\q133\\verify_workcenters.py
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.plan.cpo.engine import CPOConfig, CPOv4Engine
from src.plan.cpo.state import FactoryState
from src.plan.engines.scheduling_adapter import SchedulingMachine
from src.plan.services.phase_workcenters import station_ids_for
from src.plan.services.routing_resolver import RoutingResolver

DSN = "postgresql+asyncpg://prodplan:prodplan@localhost:5432/prodplan_one"
TENANT = UUID("00000000-0000-0000-0000-000000000001")
N_ORDERS = 30  # conjunto pequeno para o probe correr rápido


def _run(state, ops, machines):
    cfg = CPOConfig(generations=12, time_limit_sec=8.0, total_budget_s=12.0)
    eng = CPOv4Engine(state=state, config=cfg)
    h0 = datetime(2026, 6, 1, 7, 0, 0)
    return eng.schedule(ops, machines, h0, h0 + timedelta(days=120))


async def main() -> None:
    eng = create_async_engine(DSN)
    async with AsyncSession(eng) as s:
        state = await FactoryState.load(session=s, tenant_id=TENANT)
    await eng.dispose()

    print("== Q.133.B work-centers ==")
    print(f"phase_stations (fases): {len(state.phase_stations)}")
    for fid in ("1", "2", "18"):
        print(f"  fase {fid}: N={state.phase_stations.get(fid)}")

    orders = state.open_orders[:N_ORDERS]
    resolver = RoutingResolver(state)
    ops = resolver.resolve_many(orders)
    print(f"ordens={len(orders)} ops={len(ops)}")
    # amostra: as ops carregam machine_id de estação?
    sample = next((o for o in ops if o.machine_id and "::" in str(o.machine_id)), None)
    print(f"op exemplo machine_id={getattr(sample,'machine_id',None)} "
          f"alts={len(getattr(sample,'alternative_machines',[]) or [])}")

    # máquinas work-center (todas as estações de todas as fases usadas)
    fases = {o.phase_id for o in ops if o.phase_id}
    wc_machines = [
        SchedulingMachine(machine_id=sid, name=sid, capacity=1, speed_factor=1.0,
                          centro_custo=str(f))
        for f in sorted(fases) if state.phase_stations.get(f)
        for sid in station_ids_for(f, state.phase_stations[f])
    ]
    manual = [SchedulingMachine(machine_id="MANUAL", name="Manual pool")]

    r_wc = _run(state, ops, wc_machines)
    r_manual = _run(state, list(ops), manual)
    mk_wc = float(r_wc.get("makespan_hours", 0.0))
    mk_manual = float(r_manual.get("makespan_hours", 0.0))
    print(f"\nmakespan MANUAL (1 pool)      : {mk_manual:,.0f} h")
    print(f"makespan WORK-CENTERS (N est.) : {mk_wc:,.0f} h")
    if mk_manual > 0:
        print(f"reducao: {100*(1 - mk_wc/mk_manual):.0f}%")

    # molde: ops da mesma Laminagem (fase 1) com o mesmo mold_id NAO se sobrepoem
    lam = [o for o in r_wc.get("operations", []) if str(o.get("phase_id")) == "1" and o.get("mold_id")]
    overlaps = 0
    for i in range(len(lam)):
        for j in range(i + 1, len(lam)):
            a, b = lam[i], lam[j]
            if a.get("mold_id") != b.get("mold_id"):
                continue
            if a.get("start") and b.get("start") and a.get("end") and b.get("end"):
                if a["start"] < b["end"] and b["start"] < a["end"]:
                    overlaps += 1
    print(f"\nLaminagem ops c/ molde: {len(lam)}; sobreposicoes mesmo molde: {overlaps} "
          f"({'OK molde exclusivo' if overlaps == 0 else 'FALHA axioma 3'})")


if __name__ == "__main__":
    asyncio.run(main())
