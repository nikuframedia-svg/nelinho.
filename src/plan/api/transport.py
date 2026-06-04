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
from datetime import date
from typing import List, Optional
from uuid import UUID

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.partner import Customer
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
from src.shared.auth.headers import require_tenant_header

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transport", tags=["Transport"])

# Q.143.B — janela de derivação de camiões a partir das ordens reais.
_REFRESH_HORIZON_DEFAULT_DAYS = 45
_REFRESH_HORIZON_MAX_DAYS = 180


get_tenant_id = require_tenant_header


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
    # Q.116.C — `customer_ids` (UUIDs distintas em core.customers) das
    # encomendas atribuidas a esta batch. Lista vazia quando a batch
    # nao tem orders, ou quando nenhum dos clientes esta sincronizado.
    # Pode ter >1 quando a batch consolida varios clientes (multi-stop).
    customer_ids: List[str] = Field(default_factory=list)


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


class RefreshFromOrdersOut(BaseModel):
    """Q.143.B — sumário da derivação de camiões a partir das ordens reais."""
    batches_created: int
    batches_touched: int
    orders_assigned: int
    overflow: int


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
    customer_ids: Optional[List[str]] = None,
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
        customer_ids=customer_ids or [],
    )


async def _resolve_customer_ids_for_orders(
    session: AsyncSession,
    tenant_id: UUID,
    order_ids: List[UUID],
) -> List[str]:
    """Resolve UUIDs de clientes para um conjunto de order_ids.

    Q.116.C — pivot ProductionOrder.customer_name → core.customers.id.
    Devolve lista distinta (ordenada deterministicamente). Pode ter
    >1 elemento quando a batch consolida varios clientes. Best-effort:
    se a sondagem falhar (ERP desync, schema), devolve [].
    """
    if not order_ids:
        return []
    try:
        ord_stmt = select(ProductionOrder.customer_name).where(
            ProductionOrder.tenant_id == tenant_id,
            ProductionOrder.id.in_(order_ids),
        )
        ord_rows = (await session.execute(ord_stmt)).all()
        names = {
            row[0]
            for row in ord_rows
            if row and row[0]
        }
        if not names:
            return []
        cust_stmt = select(Customer.id).where(
            Customer.tenant_id == tenant_id,
            Customer.customer_name.in_(names),
        )
        cust_rows = (await session.execute(cust_stmt)).all()
        seen: list[str] = []
        for row in cust_rows:
            val = str(row[0])
            if val not in seen:
                seen.append(val)
        return sorted(seen)
    except Exception as exc:  # pragma: no cover — best-effort.
        logger.debug("customer_ids lookup falhou para batch: %s", exc)
        return []


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
    """
    svc = TransportBatchService(session, tenant_id)
    rows = await svc.list_batches(
        since=from_date, until=to_date, status=status_filter,
    )
    counts = await svc.orders_by_batch()
    # Q.116.C — expor customer_ids por batch para o frontend envolver
    # cliente em `<Clickable>`. Resolvido a partir das order_ids
    # atribuidas (1 lookup por batch — `/batches` raramente devolve >50
    # batches por janela tipica de 7d).
    out: list[TransportBatchOut] = []
    for r in rows:
        order_ids = counts.get(r.id, [])
        customer_ids = await _resolve_customer_ids_for_orders(
            session, tenant_id, order_ids
        )
        out.append(_to_out(r, len(order_ids), customer_ids=customer_ids))
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


@router.post(
    "/batches/refresh-from-orders",
    response_model=RefreshFromOrdersOut,
)
async def refresh_batches_from_orders(
    horizon_days: int = Query(
        default=_REFRESH_HORIZON_DEFAULT_DAYS, ge=1, le=_REFRESH_HORIZON_MAX_DAYS,
    ),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> RefreshFromOrdersOut:
    """Q.143.B — popula os camiões a partir das `production_orders` reais.

    Para cada data de transporte na janela [hoje, hoje+horizon], garante um
    camião OPEN `SHP-{date}` e atribui-lhe as ordens dessa data que ainda não
    têm camião — preservando o drag-drop manual. Idempotente. DRAFT-safe (só
    cria/preenche camiões OPEN; não despacha nada — Q.17).
    """
    capacity = await _load_truck_capacity(session, tenant_id)
    svc = TransportBatchService(session, tenant_id)
    summary = await svc.refresh_from_orders(
        horizon_days=horizon_days,
        default_capacity=capacity,
    )
    await session.commit()
    return RefreshFromOrdersOut(**summary)


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
    # Q.116.C — resolver customer_ids para o detalhe individual.
    order_ids = await svc.list_orders(batch_id)
    customer_ids = await _resolve_customer_ids_for_orders(
        session, tenant_id, list(order_ids)
    )
    return _to_out(row, assigned_count=count, customer_ids=customer_ids)


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


# ---------------------------------------------------------------------------
# Q.135.F2.1 — barcos previstos sair numa data + a fase de cada um
# ---------------------------------------------------------------------------


class BoatOnDate(BaseModel):
    order_id: str
    hull: Optional[int] = None
    product_name: Optional[str] = None
    current_phase_name: Optional[str] = None
    phase_sequence: Optional[int] = None
    bucket: str  # CONCLUIDO | A_DECORRER | POR_COMECAR
    ready: bool
    transport_date: Optional[str] = None


class ByDateResponse(BaseModel):
    date: str
    total: int
    ready: int
    at_risk: int  # marcados p/ sair mas ainda não prontos
    boats: List[BoatOnDate]


@router.get("/by-date", response_model=ByDateResponse)
async def boats_by_transport_date(
    date_str: str = Query(..., alias="date", description="Data de expedição (YYYY-MM-DD)"),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> ByDateResponse:
    """Q.135.F2.1 — barcos previstos sair numa data + a fase atual de cada um.

    Lê de `production_orders` (WIP) as ordens com `transport_date == date`.
    Classifica a fase (CONCLUIDO/A_DECORRER/POR_COMECAR) e marca `ready` (fase
    terminal). Um barco marcado para sair que ainda NÃO está pronto = risco.
    Ordena por sequência de fase. Zero mocks — só dados reais.
    """
    from datetime import date as _date

    from src.plan.models.order import OrderStatus
    from src.plan.services.phase_classification import (
        classify_phase,
        is_completed_phase,
        phase_sequence,
    )

    try:
        target = _date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="date deve ser YYYY-MM-DD"
        )

    rows = (
        (
            await session.execute(
                select(ProductionOrder).where(
                    (ProductionOrder.tenant_id == tenant_id)
                    & (ProductionOrder.transport_date == target)
                    & (ProductionOrder.status != OrderStatus.CANCELLED)
                )
            )
        )
        .scalars()
        .all()
    )

    boats: List[BoatOnDate] = []
    for o in rows:
        phase = o.current_phase_name
        ready = is_completed_phase(phase)
        boats.append(
            BoatOnDate(
                order_id=str(o.id),
                hull=o.legacy_id,
                product_name=o.product_name,
                current_phase_name=phase,
                phase_sequence=phase_sequence(phase),
                bucket=classify_phase(phase).value,
                ready=ready,
                transport_date=(
                    o.transport_date.isoformat() if o.transport_date else None
                ),
            )
        )
    boats.sort(
        key=lambda b: (b.phase_sequence is None, b.phase_sequence or 0, b.hull or 0)
    )
    ready_n = sum(1 for b in boats if b.ready)
    return ByDateResponse(
        date=date_str,
        total=len(boats),
        ready=ready_n,
        at_risk=len(boats) - ready_n,
        boats=boats,
    )


# ---------------------------------------------------------------------------
# Q.135.F2.2 — barcos PRONTOS a sair (Embalado) + backlog honesto + ritmo real
# ---------------------------------------------------------------------------


class ReadyBoat(BaseModel):
    of_id: int
    model: Optional[str] = None
    # Q.143.E — referência da OF (ex: "Encomenda Rent", "Box nº 1"). Muitos
    # itens "Embalado" são encomendas custom sem modelo de catálogo (P_NOME =
    # "Encomenda de Cliente"); a referência desambigua-os honestamente.
    reference: Optional[str] = None
    ready_since: Optional[str] = None  # data de entrada na fase Embalado (ISO)
    days_ready: Optional[int] = None


class ReadyResponse(BaseModel):
    boats: List[ReadyBoat]
    embalado_count: int
    armazem_count: int  # backlog acumulado (contexto honesto)
    avg_days_ready: Optional[float] = None


def _days_since(raw: Optional[str]) -> Optional[int]:
    """Dias desde uma data-texto do ERP (`OFFP_DATAINICIO`, 'YYYY-MM-DD…')."""
    if not raw or len(raw) < 10:
        return None
    from datetime import date as _date

    try:
        d = _date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None
    return max(0, (_date.today() - d).days)


@router.get("/ready", response_model=ReadyResponse)
async def ready_to_ship(
    limit: int = Query(default=200, ge=1, le=1000),
    tenant_id: UUID = Depends(get_tenant_id),  # mirror ERP partilhado (tenant-agnóstico)
    session: AsyncSession = Depends(get_session),
) -> ReadyResponse:
    """Q.135.F2.2 — barcos fisicamente PRONTOS a sair = fase 'Embalado' (ERP),
    ainda não embarcados (não em `transp_of`). Mostra também o backlog em
    'Armazem' como contexto honesto (acumulador, não fila). ZERO MOCKS — lê o
    espelho `factory_raw` (não tenant-scoped)."""
    rows = (
        await session.execute(
            text(
                """
                SELECT o."OF_ID" AS of_id, p."P_NOME" AS model,
                       NULLIF(o."OF_REFERENCIA", '') AS reference, ph.ds AS ready_since
                FROM factory_raw.ordemfabrico o
                JOIN factory_raw.fases_producao f ON f."FP_ID" = o."OF_FP_ID"
                LEFT JOIN factory_raw.produto p ON p."P_ID" = o."OF_P_ID"
                LEFT JOIN LATERAL (
                    SELECT x."OFFP_DATAINICIO" AS ds FROM factory_raw.of_fp x
                    WHERE x."OFFP_OF_ID" = o."OF_ID" AND x."OFFP_FP_ID" = o."OF_FP_ID"
                    ORDER BY x."OFFP_DATAINICIO" DESC LIMIT 1
                ) ph ON TRUE
                WHERE f."FP_NOME" = 'Embalado' AND o."OF_DATAFIM" IS NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM factory_raw.transp_of t WHERE t."TROF_OF_ID" = o."OF_ID"
                  )
                ORDER BY ph.ds ASC NULLS LAST
                LIMIT :lim
                """
            ),
            {"lim": limit},
        )
    ).mappings().all()

    boats: List[ReadyBoat] = []
    for r in rows:
        d = _days_since(r["ready_since"])
        boats.append(
            ReadyBoat(
                of_id=int(r["of_id"]),
                model=r["model"],
                reference=r["reference"],
                ready_since=(str(r["ready_since"])[:10] if r["ready_since"] else None),
                days_ready=d,
            )
        )

    counts = (
        await session.execute(
            text(
                """
                SELECT f."FP_NOME" AS fase, count(*) AS n
                FROM factory_raw.ordemfabrico o
                JOIN factory_raw.fases_producao f ON f."FP_ID" = o."OF_FP_ID"
                WHERE f."FP_NOME" IN ('Armazem', 'Embalado') AND o."OF_DATAFIM" IS NULL
                GROUP BY 1
                """
            )
        )
    ).mappings().all()
    by_phase = {c["fase"]: int(c["n"]) for c in counts}
    days_vals = [b.days_ready for b in boats if b.days_ready is not None]
    return ReadyResponse(
        boats=boats,
        embalado_count=by_phase.get("Embalado", 0),
        armazem_count=by_phase.get("Armazem", 0),
        avg_days_ready=(round(sum(days_vals) / len(days_vals), 1) if days_vals else None),
    )


class ThroughputRow(BaseModel):
    month: str
    destino: Optional[str] = None
    tipo_transporte: Optional[str] = None
    n_ofs: int


@router.get("/throughput", response_model=List[ThroughputRow])
async def expedition_throughput(
    months: int = Query(default=6, ge=1, le=36),
    tenant_id: UUID = Depends(get_tenant_id),  # mirror ERP partilhado (tenant-agnóstico)
    session: AsyncSession = Depends(get_session),
) -> List[ThroughputRow]:
    """Q.135.F2.2 — ritmo REAL de expedição por mês×destino×tipo, do mart
    `marts.v_ofs_expedidas_mes` (já alimentado pelo mirror de logística)."""
    rows = (
        await session.execute(
            text(
                """
                SELECT data, destino, tipo_transporte, n_ofs
                FROM marts.v_ofs_expedidas_mes
                ORDER BY data DESC
                LIMIT :lim
                """
            ),
            {"lim": months * 6},
        )
    ).mappings().all()
    return [
        ThroughputRow(
            month=str(r["data"])[:7],
            destino=r["destino"],
            tipo_transporte=r["tipo_transporte"],
            n_ofs=int(r["n_ofs"] or 0),
        )
        for r in rows
    ]
