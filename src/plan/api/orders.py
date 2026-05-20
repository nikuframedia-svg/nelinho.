"""GET /v1/plan/orders/active — orders activos para PhaseColumnView.

Sprint Q.18.ZIP.BE.1 · Q.54.B.

Devolve lista flat de production orders ainda no chão de fábrica no
formato consumido pelo BoatCard / PhaseColumnView do frontend Producao.

Q.54.B — o filtro deixou de ser ``status == IN_PROGRESS`` (que estava
desincronizado: 521 ordens TODAS IN_PROGRESS quando 329 já estavam
"Entregue"). Passou a EXCLUIR as ordens cuja fase é terminal — "Entregue",
"Armazem", "Embalado" — via :func:`is_completed_phase`. A classificação de
fases vive num sítio único: ``src/plan/services/phase_classification.py``.

Resposta:
    [
      {
        "id": "<uuid>",
        "hull": "<legacy_id como string>",
        "product_name": "...",
        "product_type": "K1|K2|K4|C1|C2|C4|Other",
        "customer_name": "..." | null,
        "phase": "<current_phase_name>",
        "phase_sequence": <int> | null,
        "status": "IN_PROGRESS",
        "created_date": "YYYY-MM-DD" | null,
        "transport_date": "YYYY-MM-DD" | null
      },
      ...
    ]

``phase_sequence`` (Q.54.B) — posição da fase na sequência de routing NELO,
para o frontend ordenar as colunas sem reinventar a ordem das fases.

``customer_name`` (Q.53.I) — cliente derivado da encomenda ERP quando
disponível; ``null`` honesto enquanto a sincronização não landa.

Endpoint só lê — drag-drop entre fases continua a passar por
``schedulePreviewApi.previewDelta`` (Q.4) que gera o ConsequenceBlock.
"""

from __future__ import annotations

import logging
import math
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.models.order import OrderStatus, ProductionOrder
from src.plan.services.phase_classification import (
    is_completed_phase,
    phase_sequence,
)
from src.plan.services.phase_ordering import (
    PhaseOrderingService,
    resolve_phase_sequence,
)
from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["PLAN.Orders"])


def _order_to_card(
    o: ProductionOrder,
    order_map: dict[str, int],
) -> dict[str, Any]:
    # Q.53.I — cliente é exposto a partir do atributo `customer_name` se a
    # sincronização ERP já o tiver populado; caso contrário `null` honesto
    # (sem mock). O modelo legacy ainda não tem coluna dedicada.
    customer = getattr(o, "customer_name", None)
    # Q.54.O — `phase_sequence` vem da ordem real do routing
    # (`routing_template_phase`) quando o routing está semeado; só cai no
    # dicionário estático `NELO_PHASE_ORDER` se `order_map` vier vazio.
    # Misturar as duas escalas daria colunas mal ordenadas.
    if order_map:
        seq = resolve_phase_sequence(o.current_phase_name, order_map)
    else:
        seq = phase_sequence(o.current_phase_name)
    return {
        "id": str(o.id),
        "hull": str(o.legacy_id) if o.legacy_id is not None else None,
        "product_name": o.product_name,
        "product_type": o.product_type,
        "customer_name": customer,
        # Q.54.B — `phase` traz sempre o NOME da fase; `phase_sequence` dá
        # a posição canónica no routing NELO (None se a fase é desconhecida).
        "phase": o.current_phase_name,
        "phase_sequence": seq,
        "status": o.status.value if hasattr(o.status, "value") else str(o.status),
        "created_date": o.created_date.isoformat() if o.created_date else None,
        "transport_date": o.transport_date.isoformat() if o.transport_date else None,
    }


@router.get("/orders/active")
async def list_active_orders(
    phase: str | None = Query(None, description="Filtrar por current_phase_name."),
    limit: int = Query(200, ge=1, le=2000),
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """Ordens ainda no chão de fábrica.

    Q.54.B — exclui ordens em fase terminal ("Entregue"/"Armazem"/
    "Embalado") e ordens ``CANCELLED``. O filtro de fase é por NOME, feito
    em Python (o ERP não expõe um flag de fase terminal); o volume é baixo
    (~500 ordens) por isso carregar e filtrar é barato. O param ``phase``
    continua a permitir afunilar para uma fase concreta.
    """
    stmt = (
        select(ProductionOrder)
        .where(ProductionOrder.tenant_id == tenant_id)
        # CANCELLED nunca é chão de fábrica; COMPLETED filtra-se a seguir
        # pela fase (defesa em profundidade — mesmo que o status não tenha
        # transitado, a fase terminal exclui a ordem).
        .where(ProductionOrder.status != OrderStatus.CANCELLED)
    )
    if phase:
        stmt = stmt.where(ProductionOrder.current_phase_name == phase)
    stmt = stmt.order_by(ProductionOrder.created_date.desc().nullslast())
    result = await session.execute(stmt)
    rows = result.scalars().all()

    # Q.54.O — ordem canónica das fases derivada do routing real. Mapa
    # vazio (routing não-semeado) → `_order_to_card` cai no dicionário
    # estático. Uma só query agregada — `/orders/active` não é hot.
    order_map = await PhaseOrderingService(session, tenant_id).phase_order_map()

    active = [o for o in rows if not is_completed_phase(o.current_phase_name)]
    return [_order_to_card(o, order_map) for o in active[:limit]]


@router.get("/orders/otd-risk")
async def orders_otd_risk(
    top_n: int = Query(50, ge=1, le=200),
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Q.54.F — risco de atraso por encomenda (Painel / Direção).

    P(atraso) de cada ordem aberta segundo o `OTDRiskModel` activo.
    Treina+promove um modelo no primeiro acesso quando o registry está
    vazio; degrada com ``model_available=false`` quando o histórico de
    entregas é demasiado fino para treinar. Avisa que um barco vai
    falhar a data antes do dia do transporte.
    """
    from src.plan.services.otd_risk_service import OTDRiskService

    svc = OTDRiskService(session, tenant_id)
    return await svc.otd_risk(top_n=top_n)


# ─── Q.61.32a — Migrado de src/legacy/api.py ─────────────────────────
#
# Os 3 endpoints abaixo (`GET /orders`, `/orders/stats`, `/orders/{order_id}`)
# vinham de `src/legacy/api.py` sob prefixo `/api/*`. Q.61.32a moveu-os
# para `/v1/plan/orders/*` mantendo o comportamento 100% — incluindo o
# fallback fail-soft em DB outage. Limpeza desse padrão fica para Q.62
# (touched-file pays). Behavioural preservation é o invariante deste
# sub-sprint.


@router.get("/orders")
async def list_orders_paginated(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    pageSize: int = Query(20, ge=1, le=100, description="Items per page"),
    status: str | None = Query(None, description="ALL, IN_PROGRESS, COMPLETED"),
    search: str | None = Query(
        None, description="Pesquisa em product_name, legacy_id ou phase"
    ),
    productType: str | None = Query(None, description="K1/K2/K4/C1/C2/C4/Other"),
    sortBy: str = Query("createdDate", description="createdDate/productName/status/id"),
    sortOrder: str = Query("desc", description="asc/desc"),
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Lista paginada de production orders.

    Migrado em Q.61.32a de `/api/orders` (legacy router). Preserva o
    contrato 1-para-1: mesmos query params, mesma shape de resposta.
    """
    try:
        query = select(ProductionOrder).where(ProductionOrder.tenant_id == tenant_id)

        if status and status.upper() != "ALL":
            try:
                order_status = OrderStatus(status.upper())
                query = query.where(ProductionOrder.status == order_status.value)
            except ValueError:
                pass  # status inválido, ignora silenciosamente (comportamento legacy)

        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    ProductionOrder.product_name.ilike(search_pattern),
                    ProductionOrder.current_phase_name.ilike(search_pattern),
                    ProductionOrder.legacy_id.cast(str).ilike(search_pattern),
                )
            )

        if productType and productType.upper() != "ALL":
            query = query.where(ProductionOrder.product_type == productType.upper())

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await session.execute(count_query)
        total = total_result.scalar() or 0

        sort_field_map = {
            "createdDate": ProductionOrder.created_date,
            "productName": ProductionOrder.product_name,
            "status": ProductionOrder.status,
            "id": ProductionOrder.legacy_id,
        }
        sort_field = sort_field_map.get(sortBy, ProductionOrder.created_date)
        if sortOrder.lower() == "asc":
            query = query.order_by(sort_field.asc())
        else:
            query = query.order_by(sort_field.desc())

        offset = (page - 1) * pageSize
        query = query.limit(pageSize).offset(offset)

        result = await session.execute(query)
        orders = result.scalars().all()

        orders_data = [
            {
                "id": str(order.legacy_id),
                "productId": str(order.product_id) if order.product_id else None,
                "productName": order.product_name,
                "productType": order.product_type,
                "currentPhaseId": (
                    str(order.current_phase_id) if order.current_phase_id else None
                ),
                "currentPhaseName": order.current_phase_name,
                "createdDate": (
                    order.created_date.isoformat() if order.created_date else None
                ),
                "completedDate": (
                    order.completed_date.isoformat() if order.completed_date else None
                ),
                "transportDate": (
                    order.transport_date.isoformat() if order.transport_date else None
                ),
                "status": (
                    order.status.value
                    if hasattr(order.status, "value")
                    else str(order.status)
                ),
            }
            for order in orders
        ]

        total_pages = math.ceil(total / pageSize) if pageSize > 0 else 0
        return {
            "data": orders_data,
            "total": total,
            "page": page,
            "pageSize": pageSize,
            "totalPages": total_pages,
            "hasNextPage": page < total_pages,
            "hasPreviousPage": page > 1,
        }
    except Exception as e:  # noqa: BLE001  Q.62.E.1: comportamento copiado tal-qual em Q.61.32a (legacy fallback)
        error_str = str(e).lower()
        if (
            "connection refused" in error_str
            or "operationalerror" in error_str
            or "interfaceerror" in error_str
        ):
            logger.warning("DB unavailable in list_orders_paginated, returning fallback: %s", e)
            return {
                "data": [],
                "total": 0,
                "page": page,
                "pageSize": pageSize,
                "totalPages": 0,
                "hasNextPage": False,
                "hasPreviousPage": False,
            }
        raise


@router.get("/orders/stats")
async def orders_stats(
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Estatísticas agregadas (total, in-progress, completed, transport, fases).

    Migrado em Q.61.32a de `/api/orders/stats`.
    """
    try:
        total_query = select(func.count(ProductionOrder.id)).where(
            ProductionOrder.tenant_id == tenant_id
        )
        total = (await session.execute(total_query)).scalar() or 0

        in_progress_query = select(func.count(ProductionOrder.id)).where(
            and_(
                ProductionOrder.tenant_id == tenant_id,
                ProductionOrder.status == OrderStatus.IN_PROGRESS.value,
            )
        )
        in_progress = (await session.execute(in_progress_query)).scalar() or 0

        completed_query = select(func.count(ProductionOrder.id)).where(
            and_(
                ProductionOrder.tenant_id == tenant_id,
                ProductionOrder.status == OrderStatus.COMPLETED.value,
            )
        )
        completed = (await session.execute(completed_query)).scalar() or 0

        with_transport_query = select(func.count(ProductionOrder.id)).where(
            and_(
                ProductionOrder.tenant_id == tenant_id,
                ProductionOrder.transport_date.isnot(None),
            )
        )
        with_transport = (await session.execute(with_transport_query)).scalar() or 0

        phase_query = (
            select(
                ProductionOrder.current_phase_name,
                func.count(ProductionOrder.id).label("count"),
            )
            .where(ProductionOrder.tenant_id == tenant_id)
            .group_by(ProductionOrder.current_phase_name)
            .order_by(func.count(ProductionOrder.id).desc())
            .limit(8)
        )
        phase_result = await session.execute(phase_query)
        phase_distribution = [
            {"phase": row[0], "count": row[1]} for row in phase_result.all()
        ]

        return {
            "total": total,
            "inProgress": in_progress,
            "completed": completed,
            "withTransport": with_transport,
            "phaseDistribution": phase_distribution,
        }
    except Exception as e:  # noqa: BLE001  Q.62.E.1: comportamento copiado tal-qual em Q.61.32a (legacy fallback)
        error_str = str(e).lower()
        if (
            "connection refused" in error_str
            or "operationalerror" in error_str
            or "interfaceerror" in error_str
        ):
            logger.warning("DB unavailable in orders_stats, returning fallback: %s", e)
            return {
                "total": 0,
                "inProgress": 0,
                "completed": 0,
                "withTransport": 0,
                "phaseDistribution": [],
            }
        raise


@router.get("/orders/{order_id}")
async def get_order_by_legacy_id(
    order_id: int,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Lookup individual de uma encomenda pelo `legacy_id` (inteiro do ERP).

    Migrado em Q.61.32a de `/api/orders/{order_id}`. `order_id` é o
    inteiro legacy do ERP (não a UUID `ProductionOrder.id`); FastAPI
    valida e devolve 422 para paths não-numéricos (logo `active`,
    `stats`, `otd-risk` continuam a ser routed para os handlers
    estáticos registados antes deste).
    """
    query = select(ProductionOrder).where(
        and_(
            ProductionOrder.tenant_id == tenant_id,
            ProductionOrder.legacy_id == order_id,
        )
    )
    result = await session.execute(query)
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    return {
        "id": str(order.legacy_id),
        "productId": str(order.product_id) if order.product_id else None,
        "productName": order.product_name,
        "productType": order.product_type,
        "currentPhaseId": (
            str(order.current_phase_id) if order.current_phase_id else None
        ),
        "currentPhaseName": order.current_phase_name,
        "createdDate": order.created_date.isoformat() if order.created_date else None,
        "completedDate": (
            order.completed_date.isoformat() if order.completed_date else None
        ),
        "transportDate": (
            order.transport_date.isoformat() if order.transport_date else None
        ),
        "status": (
            order.status.value if hasattr(order.status, "value") else str(order.status)
        ),
    }
