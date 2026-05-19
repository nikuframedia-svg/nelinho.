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

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.models.order import OrderStatus, ProductionOrder
from src.plan.services.phase_classification import (
    is_completed_phase,
    phase_sequence,
)
from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session

router = APIRouter(tags=["PLAN.Orders"])


def _order_to_card(o: ProductionOrder) -> dict[str, Any]:
    # Q.53.I — cliente é exposto a partir do atributo `customer_name` se a
    # sincronização ERP já o tiver populado; caso contrário `null` honesto
    # (sem mock). O modelo legacy ainda não tem coluna dedicada.
    customer = getattr(o, "customer_name", None)
    return {
        "id": str(o.id),
        "hull": str(o.legacy_id) if o.legacy_id is not None else None,
        "product_name": o.product_name,
        "product_type": o.product_type,
        "customer_name": customer,
        # Q.54.B — `phase` traz sempre o NOME da fase; `phase_sequence` dá
        # a posição canónica no routing NELO (None se a fase é desconhecida).
        "phase": o.current_phase_name,
        "phase_sequence": phase_sequence(o.current_phase_name),
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

    active = [o for o in rows if not is_completed_phase(o.current_phase_name)]
    return [_order_to_card(o) for o in active[:limit]]


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
