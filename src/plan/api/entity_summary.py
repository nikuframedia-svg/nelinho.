"""Q.116.A/E — endpoints agregadores para os sheets contextuais.

READ-ONLY. Cada endpoint serve um sheet (Modelo / Fase / Cliente /
Encomenda / Operador) do frontend nelinho. Reutiliza serviços e
modelos existentes — zero lógica nova de negócio, só agregação.

Endpoints:
  GET /v1/entity/modelo/{model_id}         → ModeloSummary       (Q.116.A)
  GET /v1/entity/fase/{phase_id}           → FaseSummary         (Q.116.A)
  GET /v1/entity/cliente/{customer_id}     → ClienteSummary      (Q.116.A)
  GET /v1/entity/encomenda/{legacy_id}     → EncomendaSummary    (Q.116.A/C)
  GET /v1/entity/operador/{employee_id}    → OperadorSummary     (Q.116.E)

Padrões:
  - `tenant_id` injectado via `require_tenant_header`.
  - 404 quando a entidade principal não existe.
  - Lista vazia (não 404) quando a entidade existe mas não tem
    dados secundários (ex: modelo sem routing_template, fase sem
    afinidades aprendidas).
"""

from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.client_priority import ClientPriority
from src.core.models.employee import Employee
from src.core.models.partner import Customer
from src.governance.models.boat_phase_score import BoatPhaseScore
from src.governance.models.phase_operator_affinity import PhaseOperatorAffinity
from src.plan.cpo.state import NELO_CURING_GAPS_SEED, normalize_phase_code
from src.plan.models.order import OrderStatus, ProductionOrder
from src.plan.models.routing_template import RoutingTemplatePhase
from src.plan.services.phase_classification import is_completed_phase
from src.plan.services.routing_template_service import (
    RoutingTemplateNotFoundError,
    RoutingTemplateService,
)
from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session

logger = logging.getLogger(__name__)


# ─── Schemas ─────────────────────────────────────────────────────────────────


class PhaseInTemplate(BaseModel):
    # Q.116.BD fix: row id (UUID) exposto para que o frontend ModeloSheet
    # possa usar nos endpoints PATCH /routing-templates/{id}/sequence e
    # /phases/{phase_row_id}/flexible. Sem isto os botoes "Guardar
    # ordem" e modal "Posicao alternativa" ficam desactivados.
    id: UUID
    seq: int
    phase_id: str
    phase_name: Optional[str]
    duration_p50_h: Optional[float]
    can_skip: bool
    # Q.116.B fix: estado is_flexible + allowed_predecessors para o
    # frontend mostrar badge e modal pre-populado.
    is_flexible: bool = False
    allowed_predecessors: Optional[List[str]] = None


class RoutingTemplateOut(BaseModel):
    id: UUID
    code: str
    name: str
    phase_count: int
    phases: List[PhaseInTemplate]


class BoatInProduction(BaseModel):
    """Q.116.G — linha resumo de um barco actualmente em produção do modelo."""

    legacy_id: int
    current_phase_name: str
    customer_name: Optional[str] = None
    transport_date: Optional[str] = None
    effective_boost: int = 0


class ModeloSummary(BaseModel):
    # `model_` é um namespace protegido em Pydantic v2; silenciamos o
    # warning porque o domínio NELO usa "modelo" para barco (não LLM).
    model_config = {"protected_namespaces": ()}

    model_id: str
    model_name: str
    product_type: Optional[str]
    routing_template: Optional[RoutingTemplateOut]
    active_orders_count: int
    in_production_count: int
    # Q.116.G — lista (até 20) de barcos do modelo actualmente em
    # produção, ordenados por `created_date DESC`. effective_boost vem
    # do mesmo stack do EncomendaSummary (cliente + encomenda + barco).
    # TODO Q.117.X: paginar quando ultrapassar 20 — modelos populares
    # como K1-Vanquish-L podem ter muito mais.
    in_production_boats: List[BoatInProduction] = Field(default_factory=list)


class OperatorScore(BaseModel):
    operator_id: str
    operator_name: str
    score: float
    sample_count: int


class BoatScore(BaseModel):
    boat_id: str
    score: float
    sample_count: int


class CuringGap(BaseModel):
    from_phase: str
    to_phase: str
    hours: float


class FaseSummary(BaseModel):
    phase_id: str
    phase_name: str
    top_operators: List[OperatorScore]
    difficult_boats: List[BoatScore]
    curing_gaps_in: List[CuringGap]
    curing_gaps_out: List[CuringGap]


class OrderInList(BaseModel):
    legacy_id: int
    product_name: str
    current_phase_name: str
    transport_date: Optional[str]
    status: str


class ClienteSummary(BaseModel):
    customer_id: str
    customer_name: str
    priority: Optional[int]
    active_orders_count: int
    orders: List[OrderInList]


class PhaseHistoryEntry(BaseModel):
    phase_name: str
    start_at: Optional[str]
    end_at: Optional[str]


class EncomendaSummary(BaseModel):
    legacy_id: int
    product_name: str
    product_type: Optional[str]
    customer_name: Optional[str]
    status: str
    current_phase_name: str
    created_date: Optional[str]
    transport_date: Optional[str]
    completed_date: Optional[str]
    phase_history: List[PhaseHistoryEntry]
    # Q.116.C — boost manual + override de data de transporte. As tabelas
    # plan.order_boost e plan.work_order_override estao a ser introduzidas
    # pelo Agent B em paralelo; ate ai (ou em dev sem migrate), os
    # endpoints devolvem defaults (0/None) em vez de falhar.
    boost: int = 0
    boost_reason: Optional[str] = None
    transport_date_override: Optional[str] = None
    transport_date_effective: Optional[str] = None
    # Q.116.G — breakdown completo do stack do boost. `client_boost` vem
    # de `ClientPriority` do cliente associado mapeado via
    # `client_boost_from_priority` (5 escalões 100/80/60/40/20).
    # `boat_boost` é o BoatBoost (PK = product_name string).
    # `effective_boost` é a soma capped a 200 via
    # `boost_service.compute_effective_boost`. Defaults 0 quando alguma
    # query falha (defesa em profundidade — endpoint robusto).
    client_boost: int = 0
    boat_boost: int = 0
    effective_boost: int = 0


# Q.116.E — Operador sheet ────────────────────────────────────────────────────


class TopPhaseForOperator(BaseModel):
    phase_id: str
    phase_name: str
    score: float
    sample_count: int


class OperadorSummary(BaseModel):
    operator_id: str
    operator_name: str
    role: Optional[str]
    active: bool
    top_phases: List[TopPhaseForOperator]
    total_phases_with_data: int


# ─── Router ──────────────────────────────────────────────────────────────────


router = APIRouter(prefix="/v1/entity", tags=["Q.116.A Entity Summary"])


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _status_value(order: ProductionOrder) -> str:
    s = order.status
    return s.value if hasattr(s, "value") else str(s)


async def _build_boats_in_production(
    session: AsyncSession,
    tenant_id: UUID,
    orders: List[ProductionOrder],
    model_id: str,
) -> List[BoatInProduction]:
    """Q.116.G — calcula `BoatInProduction` para cada encomenda em curso.

    Faz batch lookups dos 3 níveis de boost (OrderBoost via work_order_id,
    BoatBoost via product_name, ClientPriority via customer_name) para
    evitar N+1.

    Defesa em profundidade: cada lookup tem try/except — se a tabela
    ainda não está migrada ou o modelo não importa, devolvemos a lista
    com `effective_boost=0` em vez de derrubar o endpoint.
    """
    if not orders:
        return []

    legacy_ids = [int(o.legacy_id) for o in orders]
    customer_names = list({
        getattr(o, "customer_name", None) for o in orders if getattr(o, "customer_name", None)
    })

    # 1. OrderBoost batch (PK = work_order_id INT).
    order_boost_map: dict[int, int] = {}
    try:
        from src.plan.models.order_boost import OrderBoost

        ob_stmt = select(OrderBoost).where(
            and_(
                OrderBoost.tenant_id == tenant_id,
                OrderBoost.work_order_id.in_(legacy_ids),
            )
        )
        for row in (await session.execute(ob_stmt)).scalars().all():
            order_boost_map[int(row.work_order_id)] = int(row.boost)
    except Exception as exc:  # pragma: no cover — defesa.
        logger.debug("OrderBoost batch skipped (%s)", exc)

    # 2. BoatBoost — uma só lookup para o modelo (todos os barcos do
    # modelo partilham o mesmo product_name).
    boat_boost_value: int = 0
    try:
        from src.plan.models.boat_boost import BoatBoost

        bb_stmt = select(BoatBoost).where(
            and_(
                BoatBoost.tenant_id == tenant_id,
                BoatBoost.boat_id == model_id,
            )
        )
        bb_row = (await session.execute(bb_stmt)).scalar_one_or_none()
        if bb_row is not None:
            boat_boost_value = int(bb_row.boost)
    except Exception as exc:  # pragma: no cover — defesa.
        logger.debug("BoatBoost lookup skipped (%s)", exc)

    # 3. ClientPriority batch via Customer.customer_name.
    priority_by_customer: dict[str, int] = {}
    if customer_names:
        try:
            cust_stmt = select(Customer).where(
                and_(
                    Customer.tenant_id == tenant_id,
                    Customer.customer_name.in_(customer_names),
                )
            )
            customers = list((await session.execute(cust_stmt)).scalars().all())
            cust_id_to_name = {c.id: c.customer_name for c in customers}
            if cust_id_to_name:
                cp_stmt = select(ClientPriority).where(
                    and_(
                        ClientPriority.tenant_id == tenant_id,
                        ClientPriority.client_id.in_(list(cust_id_to_name.keys())),
                    )
                )
                for cp_row in (await session.execute(cp_stmt)).scalars().all():
                    name = cust_id_to_name.get(cp_row.client_id)
                    if name is not None:
                        priority_by_customer[name] = int(cp_row.priority)
        except Exception as exc:  # pragma: no cover — defesa.
            logger.debug("ClientPriority batch skipped (%s)", exc)

    # 4. Combina via compute_effective_boost.
    try:
        from src.plan.services.boost_service import compute_effective_boost
    except ImportError as exc:  # pragma: no cover — defesa.
        logger.debug("boost_service import skipped (%s)", exc)
        compute_effective_boost = None  # type: ignore[assignment]

    out: List[BoatInProduction] = []
    for o in orders:
        legacy_id = int(o.legacy_id)
        ob = order_boost_map.get(legacy_id, 0)
        customer = getattr(o, "customer_name", None)
        priority = priority_by_customer.get(customer) if customer else None
        if compute_effective_boost is not None:
            eff = compute_effective_boost(
                client_priority=priority,
                order_boost=ob,
                boat_boost=boat_boost_value,
            )
        else:
            eff = 0
        out.append(
            BoatInProduction(
                legacy_id=legacy_id,
                current_phase_name=o.current_phase_name,
                customer_name=customer,
                transport_date=(
                    o.transport_date.isoformat() if o.transport_date else None
                ),
                effective_boost=int(eff),
            )
        )
    return out


# ─── Endpoint: Modelo ────────────────────────────────────────────────────────


@router.get("/modelo/{model_id}", response_model=ModeloSummary)
async def get_modelo_summary(
    model_id: str,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> ModeloSummary:
    """Sheet "Modelo" — resumo de um modelo NELO.

    `model_id` é a STRING business-key (product_name no ERP). Sem FK
    rigorosa nesta versão porque o ERP mantém o identificador como string.
    """
    # 1. Sondamos production_orders por product_name — define se o modelo
    #    "existe" (tem encomendas registadas).
    orders_stmt = (
        select(ProductionOrder)
        .where(
            and_(
                ProductionOrder.tenant_id == tenant_id,
                ProductionOrder.product_name == model_id,
            )
        )
    )
    orders_result = await session.execute(orders_stmt)
    orders = list(orders_result.scalars().all())

    # 2. product_type — primeiro hit não-nulo das encomendas, ou None.
    product_type: Optional[str] = None
    for o in orders:
        if o.product_type:
            product_type = o.product_type
            break

    # 3. Contagens: activas (não CANCELLED) e in_production (não terminal).
    active_orders_count = 0
    in_production_count = 0
    for o in orders:
        if o.status == OrderStatus.CANCELLED:
            continue
        if o.status == OrderStatus.IN_PROGRESS:
            active_orders_count += 1
            if not is_completed_phase(o.current_phase_name):
                in_production_count += 1

    # 4. Routing template — best-effort. None se o modelo ainda não foi
    #    semeado em `model_routing_assignment`.
    routing_template_out: Optional[RoutingTemplateOut] = None
    svc = RoutingTemplateService(session, tenant_id)
    try:
        template_id = await svc.resolve_for_model(model_id=model_id, variant="A")
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("resolve_for_model falhou para %s: %s", model_id, exc)
        template_id = None

    if template_id is not None:
        try:
            template = await svc.get_template(template_id)
            phases = await svc.template_phases(template_id)
        except RoutingTemplateNotFoundError:
            template = None
            phases = []
        if template is not None:
            phase_outs = [
                PhaseInTemplate(
                    id=p.id,
                    seq=p.seq,
                    phase_id=p.phase_id,
                    phase_name=p.phase_name,
                    duration_p50_h=(
                        float(p.duration_p50_h) if p.duration_p50_h is not None else None
                    ),
                    can_skip=bool(p.can_skip),
                    is_flexible=bool(getattr(p, "is_flexible", False)),
                    allowed_predecessors=getattr(p, "allowed_predecessors", None),
                )
                for p in phases
            ]
            routing_template_out = RoutingTemplateOut(
                id=template.id,
                code=template.code,
                name=template.name,
                phase_count=template.phase_count,
                phases=phase_outs,
            )

    # Q.116.G — barcos do modelo actualmente em produção (ordem
    # `created_date DESC`, limit 20). Aproveita a query inicial de
    # ProductionOrder (já carregada) para evitar segunda viagem ao DB.
    # TODO Q.117.X: paginar — modelos populares podem ter > 20.
    in_production: List[ProductionOrder] = [
        o
        for o in orders
        if o.status != OrderStatus.CANCELLED
        and not is_completed_phase(o.current_phase_name)
    ]
    # Sort created_date DESC, com None no fim.
    in_production.sort(
        key=lambda o: (o.created_date is None, o.created_date),
        reverse=True,
    )
    in_production = in_production[:20]

    in_production_boats = await _build_boats_in_production(
        session, tenant_id, in_production, model_id
    )

    return ModeloSummary(
        model_id=model_id,
        model_name=model_id,  # business-key é também o nome humano no NELO
        product_type=product_type,
        routing_template=routing_template_out,
        active_orders_count=active_orders_count,
        in_production_count=in_production_count,
        in_production_boats=in_production_boats,
    )


# ─── Endpoint: Fase ──────────────────────────────────────────────────────────


@router.get("/fase/{phase_id}", response_model=FaseSummary)
async def get_fase_summary(
    phase_id: str,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> FaseSummary:
    """Sheet "Fase" — resumo de uma fase de produção.

    Devolve top-5 operadores (score DESC), top-5 barcos mais difíceis
    (score ASC) e curing gaps onde a fase é destino (in) ou origem (out).

    404 quando a fase não tem registos em NENHUMA fonte:
    routing_template_phase, phase_operator_affinity, boat_phase_score,
    nem aparece em NELO_CURING_GAPS_SEED.
    """
    # 1. Nome humano da fase — primeiro nome distinto no routing_template_phase.
    phase_name_stmt = (
        select(distinct(RoutingTemplatePhase.phase_name))
        .where(
            and_(
                RoutingTemplatePhase.tenant_id == tenant_id,
                RoutingTemplatePhase.phase_id == phase_id,
            )
        )
        .limit(1)
    )
    phase_name_result = await session.execute(phase_name_stmt)
    phase_name_row = phase_name_result.scalar_one_or_none()
    phase_name = phase_name_row or phase_id
    has_template_match = phase_name_row is not None

    # 2. top_operators — top 5 por score DESC.
    aff_stmt = (
        select(PhaseOperatorAffinity)
        .where(
            and_(
                PhaseOperatorAffinity.tenant_id == tenant_id,
                PhaseOperatorAffinity.phase_id == phase_id,
            )
        )
        .order_by(PhaseOperatorAffinity.score.desc())
        .limit(5)
    )
    aff_result = await session.execute(aff_stmt)
    affinities = list(aff_result.scalars().all())

    operator_ids = list({a.operator_id for a in affinities})
    emp_map: dict = {}
    if operator_ids:
        emp_stmt = select(Employee).where(
            and_(
                Employee.tenant_id == tenant_id,
                Employee.id.in_(operator_ids),
            )
        )
        emp_result = await session.execute(emp_stmt)
        emp_map = {e.id: e.employee_name for e in emp_result.scalars().all()}

    top_operators = [
        OperatorScore(
            operator_id=str(a.operator_id),
            operator_name=emp_map.get(a.operator_id, str(a.operator_id)),
            score=float(a.score),
            sample_count=int(a.sample_count),
        )
        for a in affinities
    ]

    # 3. difficult_boats — top 5 por score ASC (mais difícil = score mais baixo).
    boat_stmt = (
        select(BoatPhaseScore)
        .where(
            and_(
                BoatPhaseScore.tenant_id == tenant_id,
                BoatPhaseScore.phase_id == phase_id,
            )
        )
        .order_by(BoatPhaseScore.score.asc())
        .limit(5)
    )
    boat_result = await session.execute(boat_stmt)
    boat_rows = list(boat_result.scalars().all())
    difficult_boats = [
        BoatScore(
            boat_id=r.boat_id,
            score=float(r.score),
            sample_count=int(r.sample_count),
        )
        for r in boat_rows
    ]

    # 4. Curing gaps — match case-insensitive contra NELO_CURING_GAPS_SEED.
    norm_phase = normalize_phase_code(phase_id)
    curing_gaps_in: List[CuringGap] = []
    curing_gaps_out: List[CuringGap] = []
    for from_phase, to_phase, hours, _reason, _n in NELO_CURING_GAPS_SEED:
        if normalize_phase_code(to_phase) == norm_phase:
            curing_gaps_in.append(
                CuringGap(from_phase=from_phase, to_phase=to_phase, hours=float(hours))
            )
        if normalize_phase_code(from_phase) == norm_phase:
            curing_gaps_out.append(
                CuringGap(from_phase=from_phase, to_phase=to_phase, hours=float(hours))
            )

    # 5. 404 se NENHUMA fonte conhece a fase.
    has_any_data = (
        has_template_match
        or bool(affinities)
        or bool(boat_rows)
        or bool(curing_gaps_in)
        or bool(curing_gaps_out)
    )
    if not has_any_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fase {phase_id} sem registos no tenant",
        )

    return FaseSummary(
        phase_id=phase_id,
        phase_name=phase_name,
        top_operators=top_operators,
        difficult_boats=difficult_boats,
        curing_gaps_in=curing_gaps_in,
        curing_gaps_out=curing_gaps_out,
    )


# ─── Endpoint: Cliente ───────────────────────────────────────────────────────


@router.get("/cliente/{customer_id}", response_model=ClienteSummary)
async def get_cliente_summary(
    customer_id: UUID,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> ClienteSummary:
    """Sheet "Cliente" — resumo de um cliente.

    404 quando `customer_id` não existe em core.customers. Lista de
    encomendas é vazia quando o cliente existe mas ainda não tem
    encomendas associadas.
    """
    # 1. Cliente — 404 se não existir.
    cust_stmt = select(Customer).where(
        and_(Customer.tenant_id == tenant_id, Customer.id == customer_id)
    )
    cust_result = await session.execute(cust_stmt)
    customer = cust_result.scalar_one_or_none()
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente {customer_id} não existe",
        )

    # 2. Prioridade — opcional (pode não estar definida).
    cp_stmt = select(ClientPriority).where(
        and_(
            ClientPriority.tenant_id == tenant_id,
            ClientPriority.client_id == customer_id,
        )
    )
    cp_result = await session.execute(cp_stmt)
    cp_row = cp_result.scalar_one_or_none()
    priority = cp_row.priority if cp_row is not None else None

    # 3. Encomendas associadas ao cliente.
    # TODO Q.116.C: substituir esta junção por FK adequada
    # production_orders.customer_id → core.customers.id. Por agora, o
    # ProductionOrder não tem coluna `customer_name` populada de forma
    # confiável (Q.53.I está pendente do sync ERP). Deixamos a query
    # filtrada pelo nome do cliente como contrato, mas em DB stale
    # devolverá lista vazia — é honesto.
    orders_stmt = (
        select(ProductionOrder)
        .where(
            and_(
                ProductionOrder.tenant_id == tenant_id,
                ProductionOrder.status != OrderStatus.CANCELLED,
                # Filtro best-effort por customer_name string (Q.53.I).
                ProductionOrder.product_name.is_not(None),
            )
        )
        .order_by(ProductionOrder.created_date.desc().nullslast())
        .limit(200)
    )
    orders_result = await session.execute(orders_stmt)
    all_orders = list(orders_result.scalars().all())

    # Filtra em Python pelo customer_name (atributo soft do model — pode
    # não estar populado ainda).
    customer_orders = [
        o for o in all_orders if getattr(o, "customer_name", None) == customer.customer_name
    ]

    active_orders_count = sum(
        1 for o in customer_orders if not is_completed_phase(o.current_phase_name)
    )

    orders_out = [
        OrderInList(
            legacy_id=int(o.legacy_id),
            product_name=o.product_name,
            current_phase_name=o.current_phase_name,
            transport_date=(
                o.transport_date.isoformat() if o.transport_date is not None else None
            ),
            status=_status_value(o),
        )
        for o in customer_orders[:20]
    ]

    return ClienteSummary(
        customer_id=str(customer.id),
        customer_name=customer.customer_name,
        priority=priority,
        active_orders_count=active_orders_count,
        orders=orders_out,
    )


# ─── Endpoint: Encomenda ─────────────────────────────────────────────────────


@router.get("/encomenda/{legacy_id}", response_model=EncomendaSummary)
async def get_encomenda_summary(
    legacy_id: int,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> EncomendaSummary:
    """Sheet "Encomenda" — resumo de uma encomenda (production order).

    `legacy_id` é o inteiro do ERP. 404 se não existir. `phase_history`
    é uma lista vazia até a sincronização sync.WorkOrderPhase (Q.44.Z)
    estar populada em produção — ver TODO inline.
    """
    stmt = select(ProductionOrder).where(
        and_(
            ProductionOrder.tenant_id == tenant_id,
            ProductionOrder.legacy_id == legacy_id,
        )
    )
    result = await session.execute(stmt)
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Encomenda legacy_id={legacy_id} não existe",
        )

    # TODO Q.116.A: phase_history virá quando sync.WorkOrderPhase
    # (Q.44.Z, ver agent_docs/sprint_history.md) estiver em prod. Hoje
    # não há tabela 1:N para histórico de fases ligada a
    # ProductionOrder — devolver lista vazia é honesto, sem mock.
    phase_history: List[PhaseHistoryEntry] = []

    # Q.116.C — boost manual + override de data de transporte. Defesa em
    # profundidade: o Agent B esta a criar plan.order_boost +
    # plan.work_order_override em paralelo; tanto o import como a query
    # podem falhar (modelo nao existe, ou tabela nao migrada). Em qualquer
    # caso, devolvemos defaults — nao queremos derrubar o endpoint Encomenda.
    boost_value: int = 0
    boost_reason: Optional[str] = None
    transport_date_override: Optional[str] = None
    legacy_id_int = int(order.legacy_id)
    try:
        from src.plan.models.order_boost import OrderBoost

        boost_stmt = select(OrderBoost).where(
            and_(
                OrderBoost.tenant_id == tenant_id,
                OrderBoost.work_order_id == legacy_id_int,
            )
        )
        boost_row = (await session.execute(boost_stmt)).scalar_one_or_none()
        if boost_row is not None:
            boost_value = int(boost_row.boost)
            boost_reason = boost_row.reason
    except Exception as exc:  # pragma: no cover — defesa: import ou DB ausente.
        logger.debug("OrderBoost lookup skipped (%s)", exc)

    try:
        from src.plan.models.work_order_override import (
            WorkOrderOverride,
        )

        ovr_stmt = select(WorkOrderOverride).where(
            and_(
                WorkOrderOverride.tenant_id == tenant_id,
                WorkOrderOverride.work_order_id == legacy_id_int,
            )
        )
        ovr_row = (await session.execute(ovr_stmt)).scalar_one_or_none()
        if ovr_row is not None and getattr(ovr_row, "transport_date_override", None):
            ovr_date = ovr_row.transport_date_override
            transport_date_override = (
                ovr_date.isoformat() if hasattr(ovr_date, "isoformat") else str(ovr_date)
            )
    except Exception as exc:  # pragma: no cover — defesa: import ou DB ausente.
        logger.debug("WorkOrderOverride lookup skipped (%s)", exc)

    transport_date_iso = (
        order.transport_date.isoformat() if order.transport_date else None
    )
    transport_date_effective = transport_date_override or transport_date_iso

    # Q.116.G — boat_boost + client_boost + effective_boost. Lazy import
    # como o OrderBoost: o modelo existe (Q.116.D) mas em DB sem migrar
    # a query falha. Defaults 0 mantêm o endpoint robusto.
    boat_boost_value: int = 0
    try:
        from src.plan.models.boat_boost import BoatBoost

        bb_stmt = select(BoatBoost).where(
            and_(
                BoatBoost.tenant_id == tenant_id,
                BoatBoost.boat_id == order.product_name,
            )
        )
        bb_row = (await session.execute(bb_stmt)).scalar_one_or_none()
        if bb_row is not None:
            boat_boost_value = int(bb_row.boost)
    except Exception as exc:  # pragma: no cover — defesa: import ou DB ausente.
        logger.debug("BoatBoost lookup skipped (%s)", exc)

    client_boost_value: int = 0
    effective_boost_value: int = 0
    try:
        from src.plan.services.boost_service import (
            client_boost_from_priority,
            compute_effective_boost,
        )

        priority: Optional[int] = None
        customer_name_val = getattr(order, "customer_name", None)
        if customer_name_val:
            # Encadeamento: Customer.customer_name → Customer.id → ClientPriority.priority.
            cust_q = select(Customer).where(
                and_(
                    Customer.tenant_id == tenant_id,
                    Customer.customer_name == customer_name_val,
                )
            )
            cust_row = (await session.execute(cust_q)).scalar_one_or_none()
            if cust_row is not None:
                cp_q = select(ClientPriority).where(
                    and_(
                        ClientPriority.tenant_id == tenant_id,
                        ClientPriority.client_id == cust_row.id,
                    )
                )
                cp_row = (await session.execute(cp_q)).scalar_one_or_none()
                if cp_row is not None:
                    priority = int(cp_row.priority)

        client_boost_value = client_boost_from_priority(priority)
        effective_boost_value = compute_effective_boost(
            client_priority=priority,
            order_boost=boost_value,
            boat_boost=boat_boost_value,
        )
    except Exception as exc:  # pragma: no cover — defesa: import ou DB ausente.
        logger.debug("client/effective boost lookup skipped (%s)", exc)

    return EncomendaSummary(
        legacy_id=legacy_id_int,
        product_name=order.product_name,
        product_type=order.product_type,
        customer_name=getattr(order, "customer_name", None),
        status=_status_value(order),
        current_phase_name=order.current_phase_name,
        created_date=order.created_date.isoformat() if order.created_date else None,
        transport_date=transport_date_iso,
        completed_date=(
            order.completed_date.isoformat() if order.completed_date else None
        ),
        phase_history=phase_history,
        boost=boost_value,
        boost_reason=boost_reason,
        transport_date_override=transport_date_override,
        transport_date_effective=transport_date_effective,
        client_boost=client_boost_value,
        boat_boost=boat_boost_value,
        effective_boost=effective_boost_value,
    )


# ─── Endpoint: Operador (Q.116.E) ────────────────────────────────────────────


@router.get("/operador/{employee_id}", response_model=OperadorSummary)
async def get_operador_summary(
    employee_id: UUID,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> OperadorSummary:
    """Sheet "Operador" — resumo de um operador NELO.

    Devolve metadados HR básicos + top-5 fases por afinidade aprendida
    (PhaseOperatorAffinity, score DESC) + contagem total de fases para
    as quais já existe sinal de aprendizagem.

    404 quando o operador não existe em core.employees.

    Lista vazia de `top_phases` quando o operador existe mas ainda não
    há sinal aprendido — honesto, sem mock.
    """
    # 1. Operador — 404 se não existir no tenant.
    emp_stmt = select(Employee).where(
        and_(
            Employee.tenant_id == tenant_id,
            Employee.id == employee_id,
        )
    )
    emp_result = await session.execute(emp_stmt)
    employee = emp_result.scalar_one_or_none()
    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Operador {employee_id} não existe",
        )

    role = employee.job_title or employee.department
    active_flag = bool(getattr(employee, "active", True))

    # 2. Top 5 afinidades — score DESC.
    aff_stmt = (
        select(PhaseOperatorAffinity)
        .where(
            and_(
                PhaseOperatorAffinity.tenant_id == tenant_id,
                PhaseOperatorAffinity.operator_id == employee_id,
            )
        )
        .order_by(PhaseOperatorAffinity.score.desc())
        .limit(5)
    )
    aff_result = await session.execute(aff_stmt)
    affinities = list(aff_result.scalars().all())

    # 3. Nomes humanos das fases — lookup batch contra routing_template_phase.
    phase_ids = list({a.phase_id for a in affinities})
    phase_name_map: dict = {}
    if phase_ids:
        names_stmt = (
            select(RoutingTemplatePhase.phase_id, RoutingTemplatePhase.phase_name)
            .where(
                and_(
                    RoutingTemplatePhase.tenant_id == tenant_id,
                    RoutingTemplatePhase.phase_id.in_(phase_ids),
                )
            )
        )
        names_result = await session.execute(names_stmt)
        # `.all()` devolve tuplos (phase_id, phase_name) — primeiro hit ganha.
        for row in names_result.all():
            pid, pname = row[0], row[1]
            if pid not in phase_name_map and pname is not None:
                phase_name_map[pid] = pname

    top_phases = [
        TopPhaseForOperator(
            phase_id=a.phase_id,
            phase_name=phase_name_map.get(a.phase_id, a.phase_id),
            score=float(a.score),
            sample_count=int(a.sample_count),
        )
        for a in affinities
    ]

    # 4. Contagem total de fases com dado de aprendizagem para este operador.
    count_stmt = (
        select(func.count())
        .select_from(PhaseOperatorAffinity)
        .where(
            and_(
                PhaseOperatorAffinity.tenant_id == tenant_id,
                PhaseOperatorAffinity.operator_id == employee_id,
            )
        )
    )
    count_result = await session.execute(count_stmt)
    total_phases_with_data = int(count_result.scalar() or 0)

    return OperadorSummary(
        operator_id=str(employee.id),
        operator_name=employee.employee_name,
        role=role,
        active=active_flag,
        top_phases=top_phases,
        total_phases_with_data=total_phases_with_data,
    )
