"""
Supply ROP / ABC endpoints — `/v1/supply/rop/*` + `/abc` + `/rop-configs/recompute`.

Q.67.6.B4 — extracted from ``src/supply/api.py``. ``ROPCalculator``,
``ABCAnalysis`` and ``recompute_rop_configs`` are resolved through
``src.supply.api`` to preserve test patches.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session

from ._common import (
    ABCAnalysisRequest,
    ABCBucket,
    ABCDistributionResponse,
    ROPSkuResponse,
)


router = APIRouter(tags=["Supply Chain"])


@router.get("/rop/{sku_id}", response_model=ROPSkuResponse)
async def calculate_rop(
    sku_id: str,
    avg_daily_demand: float,
    lead_time_days: int,
    lead_time_std_dev: float,
    service_level: float = 0.95,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
):
    """Calculate Reorder Point (ROP) for a SKU."""
    if avg_daily_demand < 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="avg_daily_demand must be >= 0")
    if lead_time_days < 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="lead_time_days must be >= 0")
    if lead_time_std_dev < 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="lead_time_std_dev must be >= 0")
    if service_level not in (0.90, 0.95, 0.99):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="service_level must be one of 0.90, 0.95, 0.99",
        )

    from src.supply import api as supply_api

    calculator = supply_api.ROPCalculator()
    result = calculator.calculate_rop(
        avg_daily_demand=avg_daily_demand,
        lead_time_days=lead_time_days,
        lead_time_std_dev=lead_time_std_dev,
        service_level=service_level,
    )

    return ROPSkuResponse(sku_id=sku_id, **result)


@router.post("/abc", response_model=ABCDistributionResponse)
async def calculate_abc_analysis(
    request: ABCAnalysisRequest,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
):
    """Calculate ABC classification for inventory SKUs."""
    from src.supply import api as supply_api

    analyzer = supply_api.ABCAnalysis()
    result = analyzer.calculate_abc_distribution(
        skus_list=[s.model_dump() for s in request.skus_list],
    )
    return ABCDistributionResponse(
        distribution={
            "A": ABCBucket(count=len(result["A"]), skus=result["A"]),
            "B": ABCBucket(count=len(result["B"]), skus=result["B"]),
            "C": ABCBucket(count=len(result["C"]), skus=result["C"]),
        }
    )


@router.post("/rop-configs/recompute")
async def trigger_rop_recompute(
    lookback_days: int = Query(90, ge=7, le=365),
    service_level: float = Query(0.95, ge=0.8, le=0.999),
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Q.64.C — recompute ROP configs from inventory_ledger history.

    Le `supply.inventory_ledger_entries` (qty_out, ultimos `lookback_days`)
    + `supply.supply_material_master` (active SKUs), e faz upsert em
    `supply.supply_rop_configs` aplicando a formula classica de inventory
    management. Idempotente: segunda chamada substitui, nao duplica.
    Devolve `{rows_processed, rows_upserted, rows_skipped}`.
    """
    from src.supply import api as supply_api

    result = await supply_api.recompute_rop_configs(
        session,
        tenant_id,
        lookback_days=lookback_days,
        service_level=service_level,
    )
    await session.commit()
    return result
