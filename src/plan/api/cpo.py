"""
ProdPlan ONE — CPO v4 API (Sprint E)
=====================================

`POST /v1/plan/cpo/schedule` — run the DRCFFS-R scheduler.

Inputs (all optional):
- orders: list of order dicts; if omitted, we pull open orders from
  the FactoryState (curated layer).
- machines: list of machine dicts; if omitted, we fall back to a single
  manual machine pool so the scheduler can still produce a schedule.
- horizon_days: planning horizon, default 30.

Output: `SchedulingResult`-compatible dict plus `cpo_meta` with
baseline/best fitness and `safety_net_triggered`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.cpo.engine import CPOConfig, CPOv4Engine
from src.plan.cpo.state import FactoryState
from src.plan.engines.scheduling_adapter import SchedulingMachine
from src.plan.services.routing_resolver import RoutingResolver
from src.shared.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/plan/cpo", tags=["CPO v4 Scheduler"])


class MachineInput(BaseModel):
    machine_id: str
    name: str = ""
    capacity: int = 1
    speed_factor: float = 1.0
    centro_custo: str = ""


class CPOScheduleRequest(BaseModel):
    orders: Optional[List[Dict[str, Any]]] = None
    machines: Optional[List[MachineInput]] = None
    horizon_days: int = Field(default=30, ge=1, le=180)
    time_limit_sec: float = Field(default=30.0, ge=1.0, le=300.0)
    population_size: int = Field(default=100, ge=10, le=500)
    generations: int = Field(default=50, ge=1, le=500)


class CPOScheduleResponse(BaseModel):
    tenant_id: str
    engine_used: str
    status: str
    solve_time_sec: float
    makespan_hours: float
    total_tardiness_hours: float
    num_late_orders: int
    setups: int
    avg_utilization: float
    safety_net_triggered: bool = False
    cpo_meta: Dict[str, Any] = Field(default_factory=dict)
    operations: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    infeasible_op_ids: List[str] = Field(default_factory=list)


def _tenant_id(
    x_tenant_id: UUID = Header(default=UUID("00000000-0000-0000-0000-000000000000")),
) -> UUID:
    return x_tenant_id


@router.post("/schedule", response_model=CPOScheduleResponse)
async def schedule_cpo(
    request: CPOScheduleRequest,
    tenant_id: UUID = Depends(_tenant_id),
    db: AsyncSession = Depends(get_session),
):
    """Run the CPO v4 hyper-heuristic scheduler over the active ingestion."""
    horizon_start = datetime.utcnow()
    horizon_end = horizon_start + timedelta(days=request.horizon_days)

    # Load factory state from curated layer
    state = await FactoryState.load(db, tenant_id)

    # Orders: explicit override OR FactoryState.open_orders
    orders = request.orders or state.open_orders
    if not orders:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No orders available. Either provide `orders` in the request "
                "or ingest data via /v1/factory-data/ingest to populate the "
                "curated layer."
            ),
        )

    resolver = RoutingResolver(state)
    operations = resolver.resolve_many(orders, horizon_start=horizon_start)
    if not operations:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Routing resolver returned no operations. No history or "
                "standard template found for these orders."
            ),
        )

    # Machines: explicit override OR a single manual pool fallback
    if request.machines:
        machines = [
            SchedulingMachine(
                machine_id=m.machine_id,
                name=m.name or m.machine_id,
                capacity=m.capacity,
                speed_factor=m.speed_factor,
                centro_custo=m.centro_custo,
            )
            for m in request.machines
        ]
    else:
        machines = [SchedulingMachine(machine_id="MANUAL", name="Manual pool")]

    engine = CPOv4Engine(
        state=state,
        config=CPOConfig(
            population_size=request.population_size,
            generations=request.generations,
            time_limit_sec=request.time_limit_sec,
        ),
    )

    result = engine.schedule(operations, machines, horizon_start, horizon_end)

    return CPOScheduleResponse(
        tenant_id=str(tenant_id),
        engine_used=result.get("engine_used", "cpo_v4"),
        status=result.get("status", "unknown"),
        solve_time_sec=float(result.get("solve_time_sec", 0.0)),
        makespan_hours=float(result.get("makespan_hours", 0.0)),
        total_tardiness_hours=float(result.get("total_tardiness_hours", 0.0)),
        num_late_orders=int(result.get("num_late_orders", 0)),
        setups=int(result.get("setups", 0)),
        avg_utilization=float(result.get("avg_utilization", 0.0)),
        safety_net_triggered=bool(result.get("safety_net_triggered", False)),
        cpo_meta=result.get("cpo_meta", {}),
        operations=result.get("operations", []),
        warnings=list(result.get("warnings", [])),
        infeasible_op_ids=list(result.get("infeasible_op_ids", [])),
    )
