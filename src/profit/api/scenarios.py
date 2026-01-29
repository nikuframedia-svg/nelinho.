"""
ProdPlan ONE - Scenarios API
=============================
"""

from decimal import Decimal
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import get_session
from src.profit.services.cost_service import CostService
from src.profit.calculators.scenario_simulator import CostMultipliers

router = APIRouter(prefix="/scenarios", tags=["Scenarios"])


def get_tenant_id(x_tenant_id: UUID = Header(...)) -> UUID:
    return x_tenant_id


class ScenarioRequest(BaseModel):
    """Scenario simulation request."""
    base_order_id: str
    scenario_name: str = "Custom Scenario"
    material_multiplier: Decimal = Decimal("1.0")
    labor_multiplier: Decimal = Decimal("1.0")
    machine_multiplier: Decimal = Decimal("1.0")
    overhead_multiplier: Decimal = Decimal("1.0")
    scrap_multiplier: Decimal = Decimal("1.0")
    volume_multiplier: Decimal = Decimal("1.0")


@router.post("/simulate")
async def simulate_scenario(
    request: ScenarioRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Simulate a what-if scenario."""
    service = CostService(session, tenant_id)
    
    multipliers = CostMultipliers(
        material=request.material_multiplier,
        labor=request.labor_multiplier,
        machine=request.machine_multiplier,
        overhead=request.overhead_multiplier,
        scrap=request.scrap_multiplier,
    )
    
    result = await service.simulate_scenario(
        base_order_id=request.base_order_id,
        multipliers=multipliers,
        volume_multiplier=request.volume_multiplier,
        scenario_name=request.scenario_name,
    )
    
    return result.to_dict()


class SensitivityRequest(BaseModel):
    """Sensitivity analysis request."""
    base_order_id: str
    component: str  # material, labor, machine, etc.
    range_percent: List[int] = [-20, -10, 0, 10, 20, 30]


@router.post("/sensitivity")
async def sensitivity_analysis(
    request: SensitivityRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Run sensitivity analysis for a component."""
    service = CostService(session, tenant_id)
    
    result = await service.run_sensitivity_analysis(
        base_order_id=request.base_order_id,
        component=request.component,
        range_percent=request.range_percent,
    )
    
    return {
        "base_order_id": request.base_order_id,
        "component": request.component,
        "sensitivity": result,
    }










