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
from src.profit.services.dashboard_metrics_service import DashboardMetricsService
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


# ─── /oee (Q.19.A) — OEE from live NELO operations ───────────────────────

from datetime import timedelta

from src.profit.services.oee_service import OEEService


def _oee_item_to_dict(item) -> dict:
    return {
        "group_value": item.group_value,
        "availability": round(item.availability, 4),
        "performance": round(item.performance, 4),
        "quality": round(item.quality, 4),
        "oee": round(item.oee, 4),
        "sample_size": item.sample_size,
        "sample_excluded": item.sample_excluded,
    }


@router.get("/oee")
async def get_oee(
    date_from: Optional[date] = Query(None, description="Default: 30 days ago"),
    date_to: Optional[date] = Query(None, description="Default: today"),
    group_by: Optional[str] = Query(
        None,
        description="One of: phase, shift, product_type, mold",
    ),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """OEE from live NELO operations.

    Reads `OF_FP` via the read-only adapter (`src.adapters.nelo.services
    .list_operations`) and computes Availability × Performance × Quality
    over the window. See `src/profit/services/oee_service.py` for the
    component definitions and caveats.

    `tenant_id` is required (header) but NELO data is tenant-agnostic —
    the adapter reads the single MAR-KAYAKS DB. The header presence is
    enforced for consistency with the rest of the API.
    """
    today = date.today()
    df = date_from or (today - timedelta(days=30))
    dt = date_to or today
    gb = (group_by or "none").lower()
    if gb not in {"none", "phase", "shift", "product_type", "mold"}:
        raise HTTPException(status_code=400, detail=f"Invalid group_by: {gb}")

    svc = OEEService()
    try:
        result = await svc.calculate(df, dt, group_by=gb)  # type: ignore[arg-type]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "date_from": result.date_from.isoformat(),
        "date_to": result.date_to.isoformat(),
        "group_by": result.group_by,
        "overall": _oee_item_to_dict(result.overall),
        "breakdown": [_oee_item_to_dict(b) for b in result.breakdown],
    }


# ─── Sprint Q.5 — CEO Dashboard tiles (§9) ────────────────────────────────

@router.get("/otd")
async def get_otd(
    window_days: int = Query(30, ge=1, le=365),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """On-Time Delivery % over a rolling window. Plan v4 §9."""
    svc = DashboardMetricsService(session, tenant_id)
    result = await svc.otd(window_days=window_days)
    return result.to_dict()


@router.get("/backlog-by-client")
async def get_backlog_by_client(
    limit: int = Query(20, ge=1, le=100),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Pending orders × value × earliest deadline grouped by client.

    Client is currently proxied by `produto_nome` until proper customer
    wiring lands; the response key is `client_name` so the UI is
    forward-compatible.
    """
    svc = DashboardMetricsService(session, tenant_id)
    rows = await svc.backlog_by_client(limit=limit)
    return {"items": [r.to_dict() for r in rows], "count": len(rows)}


@router.get("/dashboard/active-alerts")
async def get_active_alerts(
    severity: Optional[str] = Query(None, description="INFO | WARN | CRITICAL"),
    limit: int = Query(20, ge=1, le=200),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Pass-through to `src.copilot.alerts.api` so the CEO dashboard can
    embed the alert feed without a second backend hop. Returns the same
    shape as `GET /v1/copilot/alerts`."""
    from sqlalchemy import desc as _desc
    from src.copilot.alerts.models import CopilotAlert

    stmt = (
        select(CopilotAlert)
        .where(CopilotAlert.tenant_id == tenant_id)
        .order_by(_desc(CopilotAlert.created_at))
        .limit(limit)
    )
    if severity:
        stmt = stmt.where(CopilotAlert.severity == severity.upper())
    rows = list((await session.execute(stmt)).scalars().all())

    by_severity = {"INFO": 0, "WARN": 0, "CRITICAL": 0}
    for a in rows:
        if a.severity in by_severity:
            by_severity[a.severity] += 1

    return {
        "items": [
            {
                "id": str(a.id),
                "code": a.code,
                "severity": a.severity,
                "title": a.title,
                "message_pt": a.message_pt,
                "status": a.status,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "context": a.context or {},
            }
            for a in rows
        ],
        "count": len(rows),
        "by_severity": by_severity,
    }


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
