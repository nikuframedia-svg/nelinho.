"""
ProdPlan ONE - Capacity API
============================
"""

from datetime import date
from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import get_session
from src.plan.services.capacity_service import CapacityService

router = APIRouter(prefix="/capacity", tags=["Capacity"])


def get_tenant_id(x_tenant_id: UUID = Header(...)) -> UUID:
    return x_tenant_id


class CapacityAnalysisRequest(BaseModel):
    """Capacity analysis request."""
    machines: List[Dict[str, Any]]
    from_date: date = None
    to_date: date = None
    period_days: int = 7


@router.post("/analysis")
async def analyze_capacity(
    request: CapacityAnalysisRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Analyze capacity utilization."""
    service = CapacityService(session, tenant_id)
    
    result = await service.analyze_capacity(
        machines=request.machines,
        from_date=request.from_date,
        to_date=request.to_date,
        period_days=request.period_days,
    )
    
    return result


@router.get("/machines/{machine_id}/availability")
async def get_machine_availability(
    machine_id: UUID,
    from_date: date = None,
    to_date: date = None,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Get availability for a machine."""
    service = CapacityService(session, tenant_id)
    
    result = await service.get_machine_availability(
        machine_id=machine_id,
        from_date=from_date,
        to_date=to_date,
    )
    
    return result










