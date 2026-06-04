"""
ProdPlan ONE - MRP API
=======================
"""

from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import get_session
from src.plan.services.mrp_service import MRPService
from src.shared.auth.headers import require_tenant_header

router = APIRouter(prefix="/mrp", tags=["MRP"])


get_tenant_id = require_tenant_header


class MRPCalculateRequest(BaseModel):
    """MRP calculation request."""
    orders: List[Dict[str, Any]]
    inventory: Dict[str, Dict[str, Any]] = {}
    bom_data: Dict[str, Any] = None
    planning_horizon_weeks: int = 12


class MRPResponse(BaseModel):
    """MRP calculation response."""
    mrp_run_id: str
    status: str
    items_analyzed: int
    purchase_orders: int
    total_po_value: float
    currency: str


@router.post("/calculate", response_model=MRPResponse)
async def calculate_mrp(
    request: MRPCalculateRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Run MRP calculation."""
    service = MRPService(session, tenant_id)
    
    result = await service.run_mrp(
        orders=request.orders,
        inventory=request.inventory,
        bom_data=request.bom_data,
        planning_horizon_weeks=request.planning_horizon_weeks,
    )
    
    return MRPResponse(
        mrp_run_id=result["mrp_run_id"],
        status=result["status"],
        items_analyzed=result["items_analyzed"],
        purchase_orders=result["purchase_orders"],
        total_po_value=result["total_po_value"],
        currency=result["currency"],
    )


@router.get("/{mrp_run_id}/requirements")
async def get_requirements(
    mrp_run_id: str,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Get material requirements for an MRP run."""
    service = MRPService(session, tenant_id)
    requirements = await service.get_requirements(mrp_run_id=mrp_run_id)
    
    return {
        "mrp_run_id": mrp_run_id,
        "requirements": [
            {
                "material_id": str(r.material_id),
                "gross_requirement": float(r.gross_requirement),
                "net_requirement": float(r.net_requirement),
                "order_quantity": float(r.order_quantity),
                "due_date": r.due_date.isoformat(),
            }
            for r in requirements
        ],
    }










