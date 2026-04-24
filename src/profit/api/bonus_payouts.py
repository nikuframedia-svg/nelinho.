"""
ProdPlan ONE — Phase Bonus Payouts API (CX5)
==============================================

Exposes the per-(product × phase) monetary bonus table and aggregations
thereof. This is the canonical home for the ERP `CoeficienteX` value.
"""

from datetime import date
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.profit.services.bonus_payout_service import BonusPayoutService
from src.shared.database import get_session

router = APIRouter(prefix="/bonus-payouts", tags=["Phase Bonus Payouts"])


def get_tenant_id(x_tenant_id: UUID = Header(...)) -> UUID:
    return x_tenant_id


class BonusPayoutRow(BaseModel):
    product_id: UUID
    phase_id: UUID
    bonus_eur: Decimal = Field(..., ge=0)
    currency_code: str = "EUR"
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    source: str = "ERP_STANDARD"


class BulkUpsertRequest(BaseModel):
    rows: List[BonusPayoutRow]


class BulkUpsertResponse(BaseModel):
    upserted: int


class BonusLookupResponse(BaseModel):
    product_id: UUID
    phase_id: UUID
    bonus_eur: Decimal
    on_date: date


@router.post("", response_model=BulkUpsertResponse)
async def bulk_upsert(
    request: BulkUpsertRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Ingest (or replace) bonus payouts from the ERP standard sheet."""
    service = BonusPayoutService(session, tenant_id)
    payload = [r.model_dump() for r in request.rows]
    n = await service.bulk_upsert(payload)
    return BulkUpsertResponse(upserted=n)


@router.get("/lookup", response_model=BonusLookupResponse)
async def lookup_bonus(
    product_id: UUID = Query(...),
    phase_id: UUID = Query(...),
    on_date: Optional[date] = Query(None),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Bonus € paid for this (product, phase) effective on `on_date`."""
    service = BonusPayoutService(session, tenant_id)
    ref = on_date or date.today()
    bonus = await service.get_bonus(product_id, phase_id, ref)
    return BonusLookupResponse(
        product_id=product_id,
        phase_id=phase_id,
        bonus_eur=bonus,
        on_date=ref,
    )
