"""
ProdPlan ONE - Profit Dashboard + Margin + SKU Profitability API (Sprint Q.3-Q.6)
==================================================================================

Complements `api/cogs.py`, `api/pricing.py`, `api/scenarios.py`, `api/kpis.py`
with the Sprint Q endpoints:

    GET /v1/profit/dashboard                 (Q.5 — throughput €/dia + targets)
    GET /v1/profit/orders/{order_id}/cost    (Q.2 — cost per order)
    GET /v1/profit/orders/{order_id}/margin  (Q.3 — margin per order)
    GET /v1/profit/sku-profitability         (Q.4 — top-N aggregated revenue)
    GET /v1/profit/pricing/products/{product_id}  (read current pricing)
    POST /v1/profit/pricing/products/{product_id} (write new ProductPricing row)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.profit.models.pricing import ProductPricing
from src.profit.services.margin_calculator import MarginCalculator
from src.profit.services.order_cost_service import OrderCostService
from src.profit.services.throughput_service import ThroughputService
from src.shared.database import get_session

router = APIRouter(tags=["Profit"])


def get_tenant_id(x_tenant_id: UUID = Header(..., alias="X-Tenant-Id")) -> UUID:
    return x_tenant_id


# ─── Pydantic schemas ─────────────────────────────────────────────────────

class OrderCostRequest(BaseModel):
    cogs_per_unit_eur: float
    quantity: Optional[float] = None
    destination: Optional[str] = None
    sku_category: Optional[str] = None


class OrderMarginRequest(BaseModel):
    cogs_eur: float
    shipping_eur: float = 0.0
    product_id: Optional[UUID] = None


class ProductPricingIn(BaseModel):
    sale_value_default_eur: float
    currency_code: str = "EUR"
    valid_from: Optional[date] = None
    notes: Optional[str] = None


# ─── /dashboard (Q.5) ────────────────────────────────────────────────────

@router.get("/dashboard")
async def get_dashboard(
    as_of: Optional[date] = Query(None),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    svc = ThroughputService(session, tenant_id)
    return await svc.dashboard(as_of=as_of)


# ─── /orders/{id}/cost + /margin (Q.2, Q.3) ──────────────────────────────

@router.post("/orders/{order_id}/cost")
async def compute_order_cost(
    order_id: str,
    req: OrderCostRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    svc = OrderCostService(session, tenant_id)
    cost = await svc.compute(
        order_id=order_id,
        cogs_per_unit_eur=Decimal(str(req.cogs_per_unit_eur)),
        quantity=Decimal(str(req.quantity)) if req.quantity is not None else None,
        destination=req.destination,
        sku_category=req.sku_category,
    )
    return cost.to_dict()


@router.post("/orders/{order_id}/margin")
async def compute_order_margin(
    order_id: str,
    req: OrderMarginRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    calc = MarginCalculator(session, tenant_id)
    margin = await calc.compute(
        order_id=order_id,
        cogs_eur=Decimal(str(req.cogs_eur)),
        shipping_eur=Decimal(str(req.shipping_eur)),
        product_id=req.product_id,
    )
    return margin.to_dict()


# ─── /sku-profitability (Q.4) ────────────────────────────────────────────

@router.get("/sku-profitability")
async def sku_profitability(
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    top_n: int = Query(50, ge=1, le=500),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    svc = ThroughputService(session, tenant_id)
    date_to = date_to or date.today()
    date_from = date_from or date_to.replace(day=1)
    items = await svc.top_skus(date_from=date_from, date_to=date_to, top_n=top_n)
    return {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "top_n": top_n,
        "items": items,
    }


# ─── /pricing/products/{id} (Q.0) ────────────────────────────────────────

@router.get("/pricing/products/{product_id}")
async def get_current_pricing(
    product_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(ProductPricing)
        .where(
            and_(
                ProductPricing.tenant_id == tenant_id,
                ProductPricing.product_id == product_id,
                ProductPricing.active.is_(True),
            )
        )
        .order_by(ProductPricing.valid_from.desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"No active ProductPricing for {product_id}",
        )
    return {
        "id": str(row.id),
        "product_id": str(row.product_id),
        "sale_value_default_eur": float(row.sale_value_default_eur),
        "currency_code": row.currency_code,
        "valid_from": row.valid_from.isoformat(),
        "valid_to": row.valid_to.isoformat() if row.valid_to else None,
        "notes": row.notes,
    }


@router.post(
    "/pricing/products/{product_id}",
    status_code=status.HTTP_201_CREATED,
)
async def set_product_pricing(
    product_id: UUID,
    req: ProductPricingIn,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    row = ProductPricing(
        id=uuid4(),
        tenant_id=tenant_id,
        product_id=product_id,
        sale_value_default_eur=Decimal(str(req.sale_value_default_eur)),
        currency_code=req.currency_code,
        valid_from=req.valid_from or date.today(),
        active=True,
        notes=req.notes,
    )
    session.add(row)
    await session.flush()
    return {
        "id": str(row.id),
        "product_id": str(row.product_id),
        "sale_value_default_eur": float(row.sale_value_default_eur),
        "valid_from": row.valid_from.isoformat(),
    }
