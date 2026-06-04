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

import asyncio
import logging
from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

from src.profit.models.pricing import ProductPricing
from src.profit.services.dashboard_metrics_service import DashboardMetricsService
from src.profit.services.margin_calculator import MarginCalculator
from src.profit.services.order_cost_service import OrderCostService
from src.profit.services.throughput_service import ThroughputService
from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session

router = APIRouter(tags=["Profit"])


get_tenant_id = require_tenant_header


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
from src.shared.config import settings


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

    def _erp_unavailable(reason: str) -> dict:
        """Resposta honesta de degradação (HTTP 200, empty-state). Mesma
        shape do caminho de sucesso mas com `erp_available=False`; o
        frontend `useHonestEmptyState` mostra o `unavailable_reason`."""
        return {
            "date_from": df.isoformat(),
            "date_to": dt.isoformat(),
            "group_by": gb,
            "overall": None,
            "breakdown": [],
            "erp_available": False,
            "unavailable_reason": reason,
        }

    svc = OEEService()
    try:
        # Q.130.W — o `svc.calculate` lê o ERP NELO (SQL Server / OF_FP) via
        # aioodbc. O `connect_args={"timeout": ...}` (Q.130.T) não cobre o
        # caso de a query pesada (OF_FP, 2.6M linhas) demorar muito: o pedido
        # pendurava >20s. Impomos um teto duro no ENDPOINT com `asyncio.wait_for`.
        #
        # CRÍTICO: a chamada vai dentro de `asyncio.shield`. Cancelar uma
        # coroutine aioodbc a meio de uma operação ODBC bloqueante (que corre
        # num thread do executor) corrompe o driver nativo e CRASHA o processo
        # — verificado ao vivo. Com `shield`, o `wait_for` devolve TimeoutError
        # ao caller SEM cancelar a task interna: a query continua em background
        # e liberta a ligação ao terminar (o query-timeout do adapter fecha-a),
        # enquanto o endpoint já degradou honestamente.
        inner = asyncio.ensure_future(
            svc.calculate(df, dt, group_by=gb)  # type: ignore[arg-type]
        )
        # Retira o resultado/excepção quando terminar (evita o warning
        # "Task exception was never retrieved" se a task sobreviver ao pedido).
        inner.add_done_callback(lambda t: t.cancelled() or t.exception())
        result = await asyncio.wait_for(
            asyncio.shield(inner),
            timeout=float(settings.sqlserver_connect_timeout_s),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except asyncio.TimeoutError:
        # ERP demasiado lento/inalcançável: a leitura não respondeu dentro do
        # teto. NUNCA pendurar nem inventar números — degradar com
        # erp_available:false. A task interna fica a correr (shielded) e
        # liberta-se sozinha; não a cancelamos para não crashar o driver.
        log.warning(
            "OEE timeout — ERP NELO não respondeu em %ss",
            settings.sqlserver_connect_timeout_s,
        )
        return _erp_unavailable(
            "O ERP NELO (SQL Server / OF_FP) não respondeu a tempo "
            f"({settings.sqlserver_connect_timeout_s}s) — dados de OEE "
            "indisponíveis neste momento."
        )
    except (RuntimeError, OSError, SQLAlchemyError) as exc:
        # OEE is computed from the live NELO ERP (SQL Server / OF_FP).
        # When that adapter is not configured or unreachable (e.g. dev
        # without SQL Server) the read raises — degrade honestly with a
        # 200 + erp_available:false instead of a 500. The frontend
        # `useHonestEmptyState` picks up the marker and shows the reason.
        log.warning("OEE indisponível — adaptador NELO offline: %s", exc)
        return _erp_unavailable(
            "Os dados de OEE vêm do ERP NELO (SQL Server / OF_FP), "
            "que não está ligado neste ambiente."
        )

    return {
        "date_from": result.date_from.isoformat(),
        "date_to": result.date_to.isoformat(),
        "group_by": result.group_by,
        "overall": _oee_item_to_dict(result.overall),
        "breakdown": [_oee_item_to_dict(b) for b in result.breakdown],
        "erp_available": True,
        "unavailable_reason": None,
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


# ─── /orders/margins + /margin-summary (Q.31.A — drill-down de lucro) ─────

from src.plan.models.order import ProductionOrder
from src.profit.models.cost import CostCalculation
from src.profit.models.pricing import OrderRevenue


def _margin_row(
    order: ProductionOrder,
    cost_by_order: dict,
    rev_by_order: dict,
) -> dict:
    """Linha de margem de uma ordem. Sem `CostCalculation` → `calculated`
    a False e margens `null` — honesto, não inventa números."""
    key = str(order.legacy_id)
    cc = cost_by_order.get(key)
    revenue = rev_by_order.get(key)
    status_val = getattr(order.status, "value", None) or str(order.status)
    row = {
        "order_id": key,
        "hull": key,
        "product_name": order.product_name,
        "product_type": order.product_type,
        "status": status_val,
        "calculated": cc is not None,
        "revenue_eur": float(revenue) if revenue is not None else None,
        "total_cogs": None,
        "margin_eur": None,
        "margin_pct": None,
    }
    if cc is None:
        return row
    cogs = Decimal(str(cc.total_cogs))
    row["total_cogs"] = float(cogs)
    if revenue is not None:
        margin = revenue - cogs
        row["margin_eur"] = float(margin)
        if revenue > 0:
            row["margin_pct"] = float(
                (margin / revenue).quantize(Decimal("0.0001"))
            )
    return row


async def _collect_margin_rows(
    session: AsyncSession,
    tenant_id: UUID,
    date_from: Optional[date],
    date_to: Optional[date],
    limit: int,
) -> list[dict]:
    """Junta `ProductionOrder` + `CostCalculation` (Q.26, quando existe)
    + `OrderRevenue` numa lista de linhas de margem. 3 queries, sem N+1."""
    ostmt = select(ProductionOrder).where(ProductionOrder.tenant_id == tenant_id)
    if date_from is not None:
        ostmt = ostmt.where(ProductionOrder.created_date >= date_from)
    if date_to is not None:
        ostmt = ostmt.where(ProductionOrder.created_date <= date_to)
    ostmt = ostmt.order_by(
        ProductionOrder.created_date.desc().nullslast()
    ).limit(limit)
    orders = list((await session.execute(ostmt)).scalars().all())
    if not orders:
        return []

    keys = [str(o.legacy_id) for o in orders]

    # CostCalculation: a versão mais alta ganha (iteramos por ordem
    # crescente de versão, a última sobrepõe-se).
    cost_by_order: dict = {}
    cstmt = (
        select(CostCalculation)
        .where(
            CostCalculation.tenant_id == tenant_id,
            CostCalculation.order_id.in_(keys),
        )
        .order_by(CostCalculation.calculation_version)
    )
    for cc in (await session.execute(cstmt)).scalars().all():
        cost_by_order[cc.order_id] = cc

    rev_by_order: dict = {}
    rstmt = select(OrderRevenue).where(
        OrderRevenue.tenant_id == tenant_id,
        OrderRevenue.order_id.in_(keys),
    )
    for rv in (await session.execute(rstmt)).scalars().all():
        rev_by_order[rv.order_id] = Decimal(str(rv.total_revenue_eur))

    return [_margin_row(o, cost_by_order, rev_by_order) for o in orders]


@router.get("/orders/margins")
async def list_order_margins(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Q.31.A — lista de ordens com receita, COGS e margem por barco.

    Drill-down do KPID "Margem por barco". Ordens sem `CostCalculation`
    aparecem com `calculated=false` e margens `null`.
    """
    rows = await _collect_margin_rows(
        session, tenant_id, date_from, date_to, limit
    )
    return {"count": len(rows), "items": rows}


@router.get("/orders/margin-summary")
async def order_margin_summary(
    days: int = Query(30, ge=1, le=365),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Q.31.A — agregado de margem para o KPI da DirecaoPage.

    Só conta ordens com margem calculável (têm `CostCalculation` e
    receita). `order_count` é esse universo, não o total de ordens.
    """
    date_from = date.today() - timedelta(days=days)
    rows = await _collect_margin_rows(session, tenant_id, date_from, None, 2000)
    margins = [
        r["margin_eur"] for r in rows
        if r["calculated"] and r["margin_eur"] is not None
    ]
    if not margins:
        return {
            "days": days,
            "order_count": 0,
            "avg_margin_eur": None,
            "median_margin_eur": None,
            "negative_count": 0,
        }
    ordered = sorted(margins)
    n = len(ordered)
    median = (
        ordered[n // 2]
        if n % 2 == 1
        else (ordered[n // 2 - 1] + ordered[n // 2]) / 2
    )
    return {
        "days": days,
        "order_count": n,
        "avg_margin_eur": round(sum(margins) / n, 2),
        "median_margin_eur": round(median, 2),
        "negative_count": sum(1 for m in margins if m < 0),
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


# ─── /margin-by-segment (Q.53.C — margem por país / agente) ──────────────

from src.profit.services.cost_ledger_service import CostLedgerService
from src.profit.services.objectives_service import ObjectivesService
from src.profit.services.segment_service import MarginSegmentService


@router.get("/margin-by-segment")
async def get_margin_by_segment(
    dimension: str = Query(
        "country",
        description="Dimensão de segmentação: country | agent",
    ),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Q.53.C — margem agregada por dimensão de negócio.

    `dimension=country` parte do país do cliente; `dimension=agent` usa a
    referência comercial. Os dados vêm do ERP NELO; quando o adaptador
    está offline degrada com `erp_available=false` (sem inventar números).

    `tenant_id` é exigido (header) por consistência com o resto da API,
    mas os dados NELO são tenant-agnósticos (DB único MAR-KAYAKS).
    """
    svc = MarginSegmentService()
    try:
        return await svc.margin_by_segment(dimension)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


# ─── /kpis/objectives (Q.53.C — bandas-alvo do CEO) ──────────────────────

@router.get("/kpis/objectives")
async def get_kpi_objectives(
    pp1_window_days: int = Query(90, ge=1, le=365),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Q.53.C — bandas-alvo do CEO + sinal de impacto-PP1.

    Devolve `low/target/high` por KPI (faturação/dia, OTD, FPY,
    retrabalho) com defaults semeados em código e override por
    `TenantConfiguration` da categoria `cost`. Inclui o `pp1_impact`: €
    poupado por sugestões aceites (decisões executadas) na janela.
    """
    svc = ObjectivesService(session, tenant_id)
    return await svc.objectives(pp1_window_days=pp1_window_days)


# ─── /cost-ledger (Q.53.C — ledger de custos consolidado) ────────────────

@router.get("/cost-ledger")
async def get_cost_ledger(
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    limit: int = Query(2000, ge=1, le=5000),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Q.53.C — ledger de custos consolidado para a futura página Custos.

    Consolida os `CostCalculation` persistidos num único ledger: custo
    por centro de custo, COGS detalhado por barco, margem por produto e
    ranking de drivers de custo. Ordens sem cálculo aparecem como
    `calculated=false` — nada é imputado.
    """
    svc = CostLedgerService(session, tenant_id)
    return await svc.ledger(date_from=date_from, date_to=date_to, limit=limit)


# ─── /cost-reduction-suggestions (Q.54.H — sugestões accionáveis) ────────

from src.profit.services.cost_reduction_service import CostReductionService
from src.shared.auth.headers import require_tenant_header


class CostReductionRequest(BaseModel):
    """Janela e limite da análise de sugestões de redução de custo."""

    date_from: Optional[date] = None
    date_to: Optional[date] = None
    limit: int = 20


class SuggestionToDecisionRequest(BaseModel):
    """Promove uma sugestão (o dict devolvido por /cost-reduction-suggestions)
    a `DecisionRun` no Inbox de governança."""

    suggestion: dict
    proposed_by: str = "custos-ui"


@router.post("/cost-reduction-suggestions")
async def post_cost_reduction_suggestions(
    req: CostReductionRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Q.54.H — sugestões accionáveis de redução de custo.

    Analisa os `CostCalculation` persistidos, deteta barcos/centros de
    custo acima da mediana do tipo de produto e devolve uma sugestão por
    desvio. O texto explicativo é redigido pelo LLM (Ollama); os números
    vêm todos da análise determinística. POST porque a análise corre
    sobre uma janela e invoca o LLM — não é uma leitura barata.
    """
    svc = CostReductionService(session, tenant_id)
    return await svc.suggestions(
        date_from=req.date_from,
        date_to=req.date_to,
        limit=max(1, min(req.limit, 100)),
    )


@router.post(
    "/cost-reduction-suggestions/decision",
    status_code=status.HTTP_201_CREATED,
)
async def post_suggestion_to_decision(
    req: SuggestionToDecisionRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Q.54.H — transforma uma sugestão aceite numa Decisão.

    Cria um `DecisionRun` do tipo `cost_reduction` no Inbox de
    governança — fica a aguardar aprovação humana. O `expected_impact`
    leva o `eur_saved` (o excesso determinístico), por isso quando a
    decisão for executada conta para o KPI "Poupado por sugestões".
    """
    svc = CostReductionService(session, tenant_id)
    try:
        return await svc.create_decision_from_suggestion(
            req.suggestion, proposed_by=req.proposed_by
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sugestão sem o campo obrigatório: {exc}",
        ) from exc
