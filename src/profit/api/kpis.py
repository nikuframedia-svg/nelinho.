"""
ProdPlan ONE - KPIs API
========================

Endpoint para snapshot de KPIs (source-of-truth para COPILOT).
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from src.shared.database import get_session
from src.shared.auth.headers import require_tenant_header
from src.shared.time import local_today, utc_now

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kpis", tags=["KPIs"])


get_tenant_id = require_tenant_header


class Citation(BaseModel):
    """Citation para KPI."""
    source_type: str  # "db", "calculation", "event"
    ref: str
    label: str
    confidence: float = 1.0
    trust_index: float = 1.0


class KPIMetric(BaseModel):
    """Métrica KPI individual."""
    value: Optional[float] = None
    updated_at: Optional[datetime] = None
    citations: List[Citation] = []
    reason: Optional[str] = None  # Se value=null, explicar porquê


class KPISnapshotResponse(BaseModel):
    """Resposta do snapshot de KPIs."""
    oee: KPIMetric
    availability: KPIMetric
    performance: KPIMetric
    quality_fpy: KPIMetric
    rework_rate: KPIMetric
    orders_total: KPIMetric
    orders_in_progress: KPIMetric
    orders_completed: KPIMetric
    updated_at: datetime


async def calculate_kpis(
    session: AsyncSession,
    tenant_id: UUID,
) -> Dict[str, KPIMetric]:
    """
    Calcular KPIs reais da base de dados.
    
    Returns:
        Dict com métricas calculadas ou None se não houver dados.
    """
    from sqlalchemy import select, case
    from src.plan.models.schedule import ProductionSchedule, ScheduleStatus
    from src.copilot.utils.citations import create_db_citation, create_calculation_citation
    import hashlib
    
    kpis = {}
    
    try:
        # 1. Orders stats — Q.55.B.3: contar `plan.production_orders` (a
        # tabela real, 521 ordens) em vez de `plan.production_schedules`
        # (output do scheduler, 159 linhas esparsas → contagens a zero,
        # e era daí que vinha o "não tenho dados" do copiloto).
        from src.plan.models.order import ProductionOrder

        orders_total = (await session.execute(
            select(func.count()).where(ProductionOrder.tenant_id == tenant_id)
        )).scalar() or 0

        orders_in_progress = (await session.execute(
            select(func.count()).where(
                ProductionOrder.tenant_id == tenant_id,
                ProductionOrder.status == "IN_PROGRESS",
            )
        )).scalar() or 0

        orders_completed = (await session.execute(
            select(func.count()).where(
                ProductionOrder.tenant_id == tenant_id,
                ProductionOrder.status == "COMPLETED",
            )
        )).scalar() or 0

        # Query hash para citations
        query_hash = hashlib.sha256(f"orders_stats_{tenant_id}".encode()).hexdigest()[:16]
        
        kpis["orders_total"] = KPIMetric(
            value=float(orders_total) if orders_total > 0 else None,
            updated_at=utc_now(),
            citations=[create_db_citation("plan.production_orders", query_hash, f"Total de ordens: {orders_total}")] if orders_total > 0 else [],
            reason="NO_SOURCE_DATA" if orders_total == 0 else None,
        )
        
        kpis["orders_in_progress"] = KPIMetric(
            value=float(orders_in_progress) if orders_in_progress > 0 else None,
            updated_at=utc_now(),
            citations=[create_db_citation("plan.production_orders", query_hash, f"Ordens em progresso: {orders_in_progress}")] if orders_in_progress > 0 else [],
            reason="NO_SOURCE_DATA" if orders_in_progress == 0 else None,
        )
        
        kpis["orders_completed"] = KPIMetric(
            value=float(orders_completed) if orders_completed > 0 else None,
            updated_at=utc_now(),
            citations=[create_db_citation("plan.production_orders", query_hash, f"Ordens completadas: {orders_completed}")] if orders_completed > 0 else [],
            reason="NO_SOURCE_DATA" if orders_completed == 0 else None,
        )
        
        # 2. Availability: fases iniciadas / total de fases
        # Assumindo que status IN_PROGRESS ou COMPLETED = fase iniciada
        phases_started_query = select(func.count(ProductionSchedule.id)).where(
            and_(
                ProductionSchedule.tenant_id == tenant_id,
                or_(
                    ProductionSchedule.status == ScheduleStatus.IN_PROGRESS,
                    ProductionSchedule.status == ScheduleStatus.COMPLETED,
                ),
            )
        )
        phases_started_result = await session.execute(phases_started_query)
        phases_started = phases_started_result.scalar() or 0
        
        phases_total_query = select(func.count(ProductionSchedule.id)).where(
            ProductionSchedule.tenant_id == tenant_id
        )
        phases_total_result = await session.execute(phases_total_query)
        phases_total = phases_total_result.scalar() or 0
        
        # Q.55.B.3 — exigir `phases_started > 0`. Com `production_schedules`
        # esparso (159 linhas, nenhuma iniciada) isto dava 0/total = 0.0,
        # e o copiloto reportava "Disponibilidade: 0,00%" como se fosse uma
        # leitura real. Sem fases iniciadas não há dado — devolver None.
        availability = None
        if phases_total > 0 and phases_started > 0:
            availability = (phases_started / phases_total) * 100.0
        
        kpis["availability"] = KPIMetric(
            value=round(availability, 1) if availability is not None else None,
            updated_at=utc_now(),
            citations=[create_calculation_citation(
                "availability",
                {"phases_started": phases_started, "phases_total": phases_total},
                f"Disponibilidade: {phases_started}/{phases_total} fases iniciadas"
            )] if availability is not None else [],
            reason="NO_SOURCE_DATA" if availability is None else None,
        )
        
        # 3. Performance: tempo padrão / tempo real (média)
        # Assumindo que scheduled_duration_hours é o padrão e actual_end - actual_start é o real
        performance_query = select(
            func.avg(ProductionSchedule.scheduled_duration_hours).label("avg_standard"),
            func.avg(
                case(
                    (
                        and_(
                            ProductionSchedule.actual_start.isnot(None),
                            ProductionSchedule.actual_end.isnot(None),
                        ),
                        func.extract('epoch', ProductionSchedule.actual_end - ProductionSchedule.actual_start) / 3600.0
                    ),
                    else_=None
                )
            ).label("avg_actual"),
        ).where(
            and_(
                ProductionSchedule.tenant_id == tenant_id,
                ProductionSchedule.scheduled_duration_hours.isnot(None),
                ProductionSchedule.actual_start.isnot(None),
                ProductionSchedule.actual_end.isnot(None),
            )
        )
        performance_result = await session.execute(performance_query)
        perf_row = performance_result.first()
        
        performance = None
        # Sprint Q.12 — converter para float ANTES da comparação fecha a
        # janela de race onde `avg_actual` Decimal != 0 mas float == 0.0.
        if perf_row and perf_row.avg_standard and perf_row.avg_actual:
            avg_std = float(perf_row.avg_standard)
            avg_act = float(perf_row.avg_actual)
            if avg_act > 0 and avg_std > 0:
                performance = min(100.0, (avg_std / avg_act) * 100.0)
        
        kpis["performance"] = KPIMetric(
            value=round(performance, 1) if performance is not None else None,
            updated_at=utc_now(),
            citations=[create_calculation_citation(
                "performance",
                {"avg_standard": float(perf_row.avg_standard), "avg_actual": float(perf_row.avg_actual)},
                f"Performance: {perf_row.avg_standard:.2f}h padrão / {perf_row.avg_actual:.2f}h real"
            )] if performance is not None else [],
            reason="NO_SOURCE_DATA" if performance is None else None,
        )
        
        # 4. Quality (FPY): orders SEM defeitos / total orders.
        #
        # Sprint Q.12 — antes calculávamos `orders_completed / orders_total`,
        # mas isso não é FPY (uma ordem completada pode ter tido rework
        # ou scrap).
        # Q.62.E.4 — `KPIFactory.product_defect_rate` agora consolida a
        # fórmula honesta: "fracção de ordens com >=1 retrabalho nos N
        # dias". FPY = 1 - product_defect_rate. Quando o factory não tem
        # dados (zero ordens ou rework_entry vazio) o factory devolve
        # None — preservamos esse contrato com `reason="NO_SOURCE_DATA"`.
        quality_fpy = None
        product_dr_decimal = None
        try:
            from src.profit.kpi_factory import KPIFactory as _KPIFactory

            _kpi = _KPIFactory(session, tenant_id)
            product_dr_decimal = await _kpi.product_defect_rate(window_days=90)
            if product_dr_decimal is not None:
                # product_defect_rate é [0,1]; FPY é [0,100].
                quality_fpy = float((1 - product_dr_decimal) * 100)
        except Exception as exc:
            logger.warning("KPIFactory.product_defect_rate failed: %s", exc)

        kpis["quality_fpy"] = KPIMetric(
            value=round(quality_fpy, 1) if quality_fpy is not None else None,
            updated_at=utc_now(),
            citations=[create_calculation_citation(
                "quality_fpy",
                {"product_defect_rate": float(product_dr_decimal) if product_dr_decimal is not None else None, "window_days": 90},
                f"FPY: {quality_fpy:.1f}% (1 - product_defect_rate × 100)",
            )] if quality_fpy is not None else [],
            reason="NO_SOURCE_DATA" if quality_fpy is None else None,
        )

        # 5. Rework Rate: orders com erros / total orders. Q.62.E.4 — vem
        # directamente do product_defect_rate (já lá em cima).
        rework_rate = None
        if product_dr_decimal is not None:
            rework_rate = float(product_dr_decimal * 100)

        kpis["rework_rate"] = KPIMetric(
            value=round(rework_rate, 1) if rework_rate is not None else None,
            updated_at=utc_now(),
            citations=[create_calculation_citation(
                "rework_rate",
                {"product_defect_rate": float(product_dr_decimal) if product_dr_decimal is not None else None, "window_days": 90},
                f"Taxa de retrabalho: {rework_rate:.1f}%",
            )] if rework_rate is not None else [],
            reason="NO_SOURCE_DATA" if rework_rate is None else None,
        )
        
        # 6. OEE = Availability × Performance × Quality
        oee = None
        if availability is not None and performance is not None and quality_fpy is not None:
            oee = (availability / 100.0) * (performance / 100.0) * (quality_fpy / 100.0) * 100.0
        
        kpis["oee"] = KPIMetric(
            value=round(oee, 1) if oee is not None else None,
            updated_at=utc_now(),
            citations=[create_calculation_citation(
                "oee",
                {"availability": availability, "performance": performance, "quality": quality_fpy},
                f"OEE: {availability:.1f}% × {performance:.1f}% × {quality_fpy:.1f}%"
            )] if oee is not None else [],
            reason="NO_SOURCE_DATA" if oee is None else None,
        )
        
    except Exception as e:
        logger.error(f"Erro ao calcular KPIs: {e}", exc_info=True)
        # Retornar todos como NO_SOURCE_DATA em caso de erro
        for kpi_name in ["oee", "availability", "performance", "quality_fpy", "rework_rate", "orders_total", "orders_in_progress", "orders_completed"]:
            if kpi_name not in kpis:
                kpis[kpi_name] = KPIMetric(
                    value=None,
                    reason=f"ERROR: {str(e)[:50]}",
                    citations=[],
                )
    
    return kpis


@router.get("/snapshot", response_model=KPISnapshotResponse)
async def get_kpi_snapshot(
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Obter snapshot de KPIs (source-of-truth para COPILOT).
    
    Retorna valores reais calculados da base de dados ou null com reason
    se não houver dados disponíveis.
    """
    kpis = await calculate_kpis(session, tenant_id)
    
    return KPISnapshotResponse(
        oee=kpis.get("oee", KPIMetric(value=None, reason="NO_SOURCE_DATA")),
        availability=kpis.get("availability", KPIMetric(value=None, reason="NO_SOURCE_DATA")),
        performance=kpis.get("performance", KPIMetric(value=None, reason="NO_SOURCE_DATA")),
        quality_fpy=kpis.get("quality_fpy", KPIMetric(value=None, reason="NO_SOURCE_DATA")),
        rework_rate=kpis.get("rework_rate", KPIMetric(value=None, reason="NO_SOURCE_DATA")),
        orders_total=kpis.get("orders_total", KPIMetric(value=None, reason="NO_SOURCE_DATA")),
        orders_in_progress=kpis.get("orders_in_progress", KPIMetric(value=None, reason="NO_SOURCE_DATA")),
        orders_completed=kpis.get("orders_completed", KPIMetric(value=None, reason="NO_SOURCE_DATA")),
        updated_at=utc_now(),
    )


@router.get("/snapshot-dev", response_model=KPISnapshotResponse)
async def get_kpi_snapshot_dev(
    session: AsyncSession = Depends(get_session),
):
    """
    Endpoint de desenvolvimento - SEM autenticação.

    Sprint Q.12 — só responde quando ``settings.debug`` estiver ligado.
    Antes vazava KPIs do tenant ``00000000-...0001`` para qualquer
    cliente na internet.
    """
    from uuid import UUID
    from src.shared.config import settings

    if not getattr(settings, "debug", False):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="dev endpoint disabled in production",
        )

    dev_tenant_id = UUID("00000000-0000-0000-0000-000000000001")
    kpis = await calculate_kpis(session, dev_tenant_id)
    
    return KPISnapshotResponse(
        oee=kpis.get("oee", KPIMetric(value=None, reason="NO_SOURCE_DATA")),
        availability=kpis.get("availability", KPIMetric(value=None, reason="NO_SOURCE_DATA")),
        performance=kpis.get("performance", KPIMetric(value=None, reason="NO_SOURCE_DATA")),
        quality_fpy=kpis.get("quality_fpy", KPIMetric(value=None, reason="NO_SOURCE_DATA")),
        rework_rate=kpis.get("rework_rate", KPIMetric(value=None, reason="NO_SOURCE_DATA")),
        orders_total=kpis.get("orders_total", KPIMetric(value=None, reason="NO_SOURCE_DATA")),
        orders_in_progress=kpis.get("orders_in_progress", KPIMetric(value=None, reason="NO_SOURCE_DATA")),
        orders_completed=kpis.get("orders_completed", KPIMetric(value=None, reason="NO_SOURCE_DATA")),
        updated_at=utc_now(),
    )


class KPISnapshotExplainedResponse(BaseModel):
    """Response with KPI snapshot and explanations."""
    snapshot: KPISnapshotResponse
    explanations: Dict[str, Any]  # KPI name -> explanation dict
    timestamp: datetime


@router.get("/snapshot-explained", response_model=KPISnapshotExplainedResponse)
async def get_kpi_snapshot_explained(
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Get KPI snapshot with explanations.
    
    Returns KPI values along with root cause analysis for each KPI.
    """
    from src.profit.explanation_engine import ExplanationEngine
    
    # Get snapshot
    kpis = await calculate_kpis(session, tenant_id)
    snapshot = KPISnapshotResponse(
        oee=kpis.get("oee", KPIMetric(value=None, reason="NO_SOURCE_DATA")),
        availability=kpis.get("availability", KPIMetric(value=None, reason="NO_SOURCE_DATA")),
        performance=kpis.get("performance", KPIMetric(value=None, reason="NO_SOURCE_DATA")),
        quality_fpy=kpis.get("quality_fpy", KPIMetric(value=None, reason="NO_SOURCE_DATA")),
        rework_rate=kpis.get("rework_rate", KPIMetric(value=None, reason="NO_SOURCE_DATA")),
        orders_total=kpis.get("orders_total", KPIMetric(value=None, reason="NO_SOURCE_DATA")),
        orders_in_progress=kpis.get("orders_in_progress", KPIMetric(value=None, reason="NO_SOURCE_DATA")),
        orders_completed=kpis.get("orders_completed", KPIMetric(value=None, reason="NO_SOURCE_DATA")),
        updated_at=utc_now(),
    )
    
    # Generate explanations for relevant KPIs
    explanation_engine = ExplanationEngine(session, tenant_id)
    explanations = {}

    # Explain OTD if orders data available
    if snapshot.orders_total.value is not None and snapshot.orders_total.value > 0:
        explanations["otd"] = await explanation_engine.explain_kpi("otd")

    # Sprint Q.22.B — explain the remaining KPIs the engine supports.
    # margin / inventory_turnover give a structural (advisory) explanation
    # with no data gate; machine_breakdown queries the schedule table
    # directly and degrades to an empty topFactors list when there is no
    # data. None of these 404 — the panel always has something to render.
    for kpi_name in ("margin", "inventory_turnover", "machine_breakdown"):
        explanations[kpi_name] = await explanation_engine.explain_kpi(kpi_name)

    return KPISnapshotExplainedResponse(
        snapshot=snapshot,
        explanations=explanations,
        timestamp=utc_now(),
    )


@router.get("/otd-heatmap")
async def get_otd_heatmap(
    weeks: int = 12,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Get OTD heatmap data by product and week.
    
    Returns a matrix of OTD percentages for each product type across weeks.
    Uses product_code prefix (e.g., "K1", "K2", "C1") to group products.
    """
    from datetime import date, timedelta
    from sqlalchemy import func as sql_func, case, cast, String
    from sqlalchemy.sql import func as sql_func_expr
    from src.plan.models.schedule import ProductionSchedule, ScheduleStatus
    from src.core.models.product import Product
    
    # Calculate date range
    end_date = local_today()
    start_date = end_date - timedelta(weeks=weeks)
    
    # Extract product type from product_code (first 2 chars, e.g., "K1", "C2")
    product_type_expr = sql_func.substr(Product.product_code, 1, 2).label('product_type')
    week_start = sql_func.date_trunc('week', ProductionSchedule.scheduled_end_date)
    
    # Calculate OTD per product type per week
    query = select(
        product_type_expr,
        week_start.label('week'),
        sql_func.count(ProductionSchedule.order_id.distinct()).label('total_orders'),
        sql_func.sum(
            case(
                (
                    and_(
                        ProductionSchedule.status == ScheduleStatus.COMPLETED,
                        ProductionSchedule.actual_end.isnot(None),
                        ProductionSchedule.scheduled_end_date.isnot(None),
                        sql_func.date(ProductionSchedule.actual_end) <= ProductionSchedule.scheduled_end_date
                    ),
                    1
                ),
                else_=0
            )
        ).label('on_time_orders'),
    ).select_from(
        ProductionSchedule
    ).join(
        Product, ProductionSchedule.product_id == Product.id
    ).where(
        and_(
            ProductionSchedule.tenant_id == tenant_id,
            ProductionSchedule.scheduled_end_date >= start_date,
            ProductionSchedule.scheduled_end_date <= end_date,
        )
    ).group_by(
        product_type_expr,
        week_start
    )
    
    result = await session.execute(query)
    rows = result.all()
    
    # Build heatmap data structure
    product_types = sorted(set(row.product_type for row in rows if row.product_type))
    weeks_list = sorted(set(row.week for row in rows))
    
    # Initialize heatmap matrix
    heatmap = {}
    for product_type in product_types:
        heatmap[product_type] = {}
        for week in weeks_list:
            heatmap[product_type][week.isoformat()] = None  # None means no data
    
    # Fill in OTD values
    for row in rows:
        product_type = str(row.product_type) if row.product_type else None
        if not product_type:
            continue
        week_str = row.week.isoformat()
        total = float(row.total_orders) if row.total_orders else 0
        on_time = float(row.on_time_orders) if row.on_time_orders else 0
        otd = (on_time / total * 100) if total > 0 else None
        if product_type not in heatmap:
            heatmap[product_type] = {}
        heatmap[product_type][week_str] = otd
    
    return {
        "product_types": product_types,
        "weeks": [w.isoformat() for w in weeks_list],
        "heatmap": heatmap,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }


class KPIHistoryPoint(BaseModel):
    """Um ponto da série histórica de um KPI."""
    date: str
    value: Optional[float] = None


class KPIHistoryResponse(BaseModel):
    """Série histórica de um KPI (Q.117.D)."""
    name: str
    unit: str
    days: int
    points: List[KPIHistoryPoint]


@router.get("/{name}/history", response_model=KPIHistoryResponse)
async def get_kpi_history_endpoint(
    name: str,
    days: int = 30,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Série histórica de um KPI para o gráfico de tendência (Q.117.D).

    Lê de ``profit.kpi_snapshot`` (escrito 1×/dia por ``_kpi_snapshot_job``).
    404 quando ``name`` não está na whitelist de KPIs com histórico.
    Pontos com ``value=null`` representam dias sem dados — nunca inventados.
    """
    from src.profit.services.kpi_history import get_kpi_history

    result = await get_kpi_history(session, tenant_id, name, days=days)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"KPI '{name}' não suporta histórico.",
        )
    return KPIHistoryResponse(**result)

