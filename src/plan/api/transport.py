"""
ProdPlan ONE - Transport / Despacho API (Sprint Q.2 / DE01-DE08)
================================================================

REST surface for `TransportBatch`. Powers the new DispatchPage in the
frontend and the CEO Dashboard's "expedições próximas 7 dias" tile.

Endpoints (all under `/v1/plan/transport`):

  GET    /batches                              — list with filters
  POST   /batches                              — create
  GET    /batches/{id}                         — single batch w/ counts
  POST   /batches/{id}/orders                  — assign order
  DELETE /batches/{id}/orders/{order_id}       — remove order
  POST   /batches/{id}/freeze                  — lock against changes
  POST   /batches/{id}/dispatch                — mark dispatched
  GET    /batches/{id}/suggestions             — 5 suggestion types

Capacity defaults pulled from
`tenant_configuration.planning.transport.default_batch_size` so admins can
tune via the Settings UI without redeploy.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import List, Optional
from uuid import UUID

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.copilot.readers.production_summary import _is_non_production
from src.core.services.tenant_config_service import TenantConfigService
from src.plan.models.order import ProductionOrder
from src.plan.services.transport_batch_service import (
    TransportBatchNotFoundError,
    TransportBatchService,
)
from src.plan.services.transport_suggestions import (
    DEFAULT_DELIVERY_BUFFER_DAYS,
    DEFAULT_TRUCK_CAPACITY,
    TransportSuggestionsService,
)
from src.shared.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transport", tags=["Transport"])


def get_tenant_id(x_tenant_id: UUID = Header(..., alias="X-Tenant-Id")) -> UUID:
    return x_tenant_id


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TransportBatchOut(BaseModel):
    id: UUID
    code: str
    transport_date: date
    truck_capacity_units: int
    priority: int
    destination: Optional[str] = None
    status: str
    assigned_orders_count: Optional[int] = None
    # Q.38.A — estado dos barcos da batch (None quando não calculado, p.ex.
    # no create/freeze/dispatch onde a contagem não é relevante).
    ready: Optional[int] = None
    in_prod: Optional[int] = None
    at_risk: Optional[int] = None


class TransportBatchCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    transport_date: date
    truck_capacity_units: Optional[int] = Field(
        default=None,
        ge=1,
        description="Falls back to TenantConfig.planning.transport.default_batch_size.",
    )
    priority: int = 100
    destination: Optional[str] = Field(default=None, max_length=255)


class AssignOrderIn(BaseModel):
    order_id: UUID


class TransportSuggestionOut(BaseModel):
    type: str
    what: str
    why: str
    if_accept: str
    if_reject: str
    alternative: Optional[str] = None
    affected_order_ids: List[str] = Field(default_factory=list)
    target_batch_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

async def _load_truck_capacity(session: AsyncSession, tenant_id: UUID) -> int:
    """Default truck capacity from TenantConfig, fallback to module constant."""
    try:
        cfg = TenantConfigService(session, tenant_id)
        values = await cfg.get_category("planning")
        raw = values.get("transport.default_batch_size", DEFAULT_TRUCK_CAPACITY)
        return int(raw)
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("transport: cap default lookup failed: %s", exc)
        return DEFAULT_TRUCK_CAPACITY


async def _load_buffer_days(session: AsyncSession, tenant_id: UUID) -> int:
    """Days-before-transport buffer from TenantConfig."""
    try:
        cfg = TenantConfigService(session, tenant_id)
        values = await cfg.get_category("planning")
        raw = values.get(
            "transport.delivery_buffer_h", DEFAULT_DELIVERY_BUFFER_DAYS * 24,
        )
        # Stored as hours by the seeder (transport.delivery_buffer_h=24.0).
        return max(1, int(float(raw) / 24))
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("transport: buffer lookup failed: %s", exc)
        return DEFAULT_DELIVERY_BUFFER_DAYS


def _to_out(
    row,
    assigned_count: Optional[int] = None,
    *,
    ready: Optional[int] = None,
    in_prod: Optional[int] = None,
    at_risk: Optional[int] = None,
) -> TransportBatchOut:
    return TransportBatchOut(
        id=row.id,
        code=row.code,
        transport_date=row.transport_date,
        truck_capacity_units=row.truck_capacity_units,
        priority=row.priority,
        destination=row.destination,
        status=row.status,
        assigned_orders_count=assigned_count,
        ready=ready,
        in_prod=in_prod,
        at_risk=at_risk,
    )


# Q.38.A/B — janela (dias) para considerar uma ordem não-pronta "em risco".
_AT_RISK_HORIZON_DAYS = 3


def _batch_state_counts(
    batch_transport_date: Optional[date],
    orders: List[ProductionOrder],
) -> tuple[int, int, int]:
    """Calcula (ready, in_prod, at_risk) para as ordens de uma batch.

    - ``ready``  — ordens em fase administrativa (Entregue/Armazem/Embalado/…),
      via `_is_non_production` (normalização sem-acentos partilhada).
    - ``in_prod`` — as restantes (ainda em produção).
    - ``at_risk`` — subconjunto de ``in_prod`` cujo ``transport_date`` da batch
      está a ≤ 3 dias (inclui datas já passadas). Sem data de transporte na
      batch não há risco calculável → 0.
    """
    ready = 0
    in_prod = 0
    at_risk = 0
    today = date.today()
    horizon = (
        batch_transport_date is not None
        and batch_transport_date <= today + timedelta(days=_AT_RISK_HORIZON_DAYS)
    )
    for order in orders:
        if _is_non_production(order.current_phase_name):
            ready += 1
        else:
            in_prod += 1
            if horizon:
                at_risk += 1
    return ready, in_prod, at_risk


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/batches", response_model=list[TransportBatchOut])
async def list_batches(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    status_filter: Optional[str] = None,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> list[TransportBatchOut]:
    """List transport batches with optional date and status filters.

    Includes `assigned_orders_count` per batch so the UI can render the
    truck-capacity meter without a second round-trip.

    Q.38.A — também devolve `ready`/`in_prod`/`at_risk` por batch. As
    ordens de cada batch vêm de `transport_batch_assignment`.
    """
    svc = TransportBatchService(session, tenant_id)
    rows = await svc.list_batches(
        since=from_date, until=to_date, status=status_filter,
    )
    counts = await svc.orders_by_batch()

    # Carrega todas as ordens do tenant uma vez — indexadas por id para
    # resolver os assignments explícitos.
    all_orders = list(
        (
            await session.execute(
                select(ProductionOrder).where(
                    ProductionOrder.tenant_id == tenant_id
                )
            )
        ).scalars().all()
    )
    orders_by_id = {o.id: o for o in all_orders}

    out: list[TransportBatchOut] = []
    for r in rows:
        explicit_ids = counts.get(r.id, [])
        batch_orders = [
            orders_by_id[oid] for oid in explicit_ids if oid in orders_by_id
        ]
        assigned_count = len(explicit_ids)
        ready, in_prod, at_risk = _batch_state_counts(
            r.transport_date, batch_orders
        )
        out.append(
            _to_out(
                r,
                assigned_count,
                ready=ready,
                in_prod=in_prod,
                at_risk=at_risk,
            )
        )
    return out


@router.post(
    "/batches",
    response_model=TransportBatchOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_batch(
    body: TransportBatchCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> TransportBatchOut:
    capacity = body.truck_capacity_units or await _load_truck_capacity(
        session, tenant_id,
    )
    svc = TransportBatchService(session, tenant_id)
    row = await svc.create_batch(
        code=body.code,
        transport_date=body.transport_date,
        truck_capacity_units=capacity,
        priority=body.priority,
        destination=body.destination,
    )
    await session.commit()
    return _to_out(row, assigned_count=0)


@router.get("/batches/{batch_id}", response_model=TransportBatchOut)
async def get_batch(
    batch_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> TransportBatchOut:
    svc = TransportBatchService(session, tenant_id)
    try:
        row = await svc.get_batch(batch_id)
    except TransportBatchNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="batch not found")
    count = await svc.assigned_count(batch_id)
    return _to_out(row, assigned_count=count)


@router.post(
    "/batches/{batch_id}/orders",
    response_model=TransportBatchOut,
)
async def assign_order(
    batch_id: UUID,
    body: AssignOrderIn,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> TransportBatchOut:
    svc = TransportBatchService(session, tenant_id)
    try:
        row = await svc.get_batch(batch_id)
    except TransportBatchNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="batch not found")
    if row.status == "DISPATCHED":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="cannot assign to a DISPATCHED batch",
        )
    await svc.assign_order(batch_id=batch_id, order_id=body.order_id)
    count = await svc.assigned_count(batch_id)
    await session.commit()
    return _to_out(row, assigned_count=count)


@router.get("/batches/{batch_id}/orders")
async def list_batch_orders(
    batch_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """List the orders currently assigned to a batch.

    Sprint Q.9 Onda 3.3 — backs the DispatchPage's draggable order
    list. Returns `{batch_id, orders: [order_id, ...]}`. 404 when
    the batch doesn't exist; an empty list is a valid response for
    a batch nobody has assigned orders to yet.
    """
    svc = TransportBatchService(session, tenant_id)
    try:
        await svc.get_batch(batch_id)
    except TransportBatchNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="batch not found")
    orders = await svc.list_orders(batch_id)
    return {
        "batch_id": str(batch_id),
        "orders": [str(o) for o in orders],
    }


@router.get("/batches/{batch_id}/manifest")
async def batch_manifest(
    batch_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Q.31.E — documento de expedição de uma batch.

    Junta os dados da batch (código, data, destino) com a lista de barcos
    atribuídos (casco, modelo, fase actual). O frontend imprime isto como
    manifesto/packing-list. 404 se a batch não existe.
    """
    svc = TransportBatchService(session, tenant_id)
    try:
        batch = await svc.get_batch(batch_id)
    except TransportBatchNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="batch not found")

    order_ids = await svc.list_orders(batch_id)
    boats: list[dict] = []
    if order_ids:
        rows = (
            await session.execute(
                select(ProductionOrder).where(
                    ProductionOrder.tenant_id == tenant_id,
                    ProductionOrder.id.in_(order_ids),
                )
            )
        ).scalars().all()
        boats = [
            {
                "order_id": str(o.id),
                "hull": o.legacy_id,
                "product_name": o.product_name,
                "product_type": o.product_type,
                "current_phase": o.current_phase_name,
                "status": o.status.value if hasattr(o.status, "value") else str(o.status),
            }
            for o in sorted(rows, key=lambda r: r.legacy_id)
        ]

    return {
        "batch": {
            "id": str(batch.id),
            "code": batch.code,
            "transport_date": (
                batch.transport_date.isoformat() if batch.transport_date else None
            ),
            "destination": batch.destination,
            "status": batch.status,
            "truck_capacity_units": batch.truck_capacity_units,
        },
        "boats": boats,
        "boat_count": len(boats),
        "generated_at": datetime.now().isoformat(),
    }


@router.delete(
    "/batches/{batch_id}/orders/{order_id}",
    response_model=TransportBatchOut,
)
async def remove_order(
    batch_id: UUID,
    order_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> TransportBatchOut:
    svc = TransportBatchService(session, tenant_id)
    try:
        row = await svc.get_batch(batch_id)
    except TransportBatchNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="batch not found")
    if row.status == "DISPATCHED":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="cannot modify a DISPATCHED batch",
        )
    removed = await svc.remove_order(batch_id=batch_id, order_id=order_id)
    if not removed:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="order not assigned to this batch",
        )
    count = await svc.assigned_count(batch_id)
    await session.commit()
    return _to_out(row, assigned_count=count)


@router.post("/batches/{batch_id}/freeze", response_model=TransportBatchOut)
async def freeze_batch(
    batch_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> TransportBatchOut:
    svc = TransportBatchService(session, tenant_id)
    try:
        row = await svc.freeze(batch_id)
    except TransportBatchNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="batch not found")
    count = await svc.assigned_count(batch_id)
    await session.commit()
    return _to_out(row, assigned_count=count)


@router.post("/batches/{batch_id}/dispatch", response_model=TransportBatchOut)
async def dispatch_batch(
    batch_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> TransportBatchOut:
    svc = TransportBatchService(session, tenant_id)
    try:
        row = await svc.dispatch(batch_id)
    except TransportBatchNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="batch not found")
    count = await svc.assigned_count(batch_id)
    await session.commit()
    return _to_out(row, assigned_count=count)


@router.get(
    "/batches/{batch_id}/suggestions",
    response_model=list[TransportSuggestionOut],
)
async def batch_suggestions(
    batch_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> list[TransportSuggestionOut]:
    """Return DE03-DE08 suggestions for a single batch."""
    capacity = await _load_truck_capacity(session, tenant_id)
    buffer_days = await _load_buffer_days(session, tenant_id)

    svc = TransportSuggestionsService(
        session, tenant_id,
        truck_capacity=capacity,
        buffer_days=buffer_days,
    )
    suggestions = await svc.for_batch(batch_id)
    return [TransportSuggestionOut(**s.to_dict()) for s in suggestions]


# ─── Sprint Q.5 — Expeditions horizon (CEO dashboard tile) ─────────────────

@router.get("/expeditions/next-n-days")
async def expeditions_next_n_days(
    horizon_days: int = 7,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """List transport batches scheduled within the next N days.

    Used by the CEO dashboard tile "Expedições próximos 7 dias" (Plan
    v4 §9). Each batch carries a `risk` band (`ok | near_capacity |
    over_capacity`) so the UI can colour the row without doing the
    arithmetic itself.
    """
    if horizon_days < 1 or horizon_days > 60:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="horizon_days must be in [1, 60]",
        )
    from src.profit.services.dashboard_metrics_service import (
        DashboardMetricsService,
    )

    svc = DashboardMetricsService(session, tenant_id)
    rows = await svc.expeditions_next_n_days(horizon_days=horizon_days)
    return {
        "horizon_days": horizon_days,
        "items": [r.to_dict() for r in rows],
        "count": len(rows),
    }
