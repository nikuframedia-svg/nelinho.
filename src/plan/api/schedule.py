"""
ProdPlan ONE - Schedule API
============================
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import get_session
from src.plan.services.scheduling_service import SchedulingService
from src.plan.engines.scheduling_adapter import SchedulerEngine, DispatchRule

router = APIRouter(prefix="/schedule", tags=["Scheduling"])


def get_tenant_id(x_tenant_id: UUID = Header(...)) -> UUID:
    return x_tenant_id


class ScheduleGenerateRequest(BaseModel):
    """Request to generate schedule."""
    orders: List[Dict[str, Any]]
    machines: List[Dict[str, Any]]
    operations: List[Dict[str, Any]]
    engine: str = "heuristic"
    rule: str = "edd"
    planning_weeks: int = 4


class ScheduleResponse(BaseModel):
    """Schedule generation response."""
    planning_run_id: str
    status: str
    operations_scheduled: int
    kpis: Dict[str, Any]


@router.get("/")
async def list_schedules(
    status: Optional[str] = None,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """List all schedules."""
    # Return empty list for now (placeholder for future implementation)
    return {"data": [], "total": 0}


@router.post("/generate", response_model=ScheduleResponse)
async def generate_schedule(
    request: ScheduleGenerateRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Generate production schedule."""
    service = SchedulingService(session, tenant_id)
    
    result = await service.generate_schedule(
        orders=request.orders,
        machines=request.machines,
        operations=request.operations,
        engine=SchedulerEngine(request.engine),
        rule=DispatchRule(request.rule),
        planning_weeks=request.planning_weeks,
    )
    
    return ScheduleResponse(
        planning_run_id=result["planning_run_id"],
        status=result["status"],
        operations_scheduled=result["operations_scheduled"],
        kpis=result["kpis"],
    )


@router.get("/{planning_run_id}")
async def get_schedule(
    planning_run_id: str,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Get schedule by planning run ID."""
    service = SchedulingService(session, tenant_id)
    schedules = await service.get_schedule(planning_run_id=planning_run_id)
    
    return {
        "planning_run_id": planning_run_id,
        "operations": [
            {
                "id": str(s.id),
                "order_id": s.order_id,
                "operation_id": str(s.operation_id),
                "scheduled_start": s.scheduled_start_date.isoformat(),
                "scheduled_end": s.scheduled_end_date.isoformat(),
                "status": s.status.value,
            }
            for s in schedules
        ],
    }


@router.get("/order/{order_id}")
async def get_order_schedule(
    order_id: str,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Get schedule for an order."""
    service = SchedulingService(session, tenant_id)
    schedules = await service.get_schedule(order_id=order_id)
    
    return {
        "order_id": order_id,
        "operations": [
            {
                "id": str(s.id),
                "operation_sequence": s.operation_sequence,
                "scheduled_start": s.scheduled_start_date.isoformat(),
                "scheduled_end": s.scheduled_end_date.isoformat(),
                "status": s.status.value,
            }
            for s in schedules
        ],
    }



