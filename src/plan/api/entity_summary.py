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
from datetime import datetime, timezone
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, distinct, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.client_priority import ClientPriority
from src.core.models.employee import Employee
from src.core.models.partner import Customer
from src.governance.models.boat_phase_score import BoatPhaseScore
from src.governance.models.phase_operator_affinity import PhaseOperatorAffinity
from src.plan.cpo.state import (
    NELO_CURING_GAPS_SEED,
    _load_phase_queue_medians_db,
    normalize_phase_code,
)
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


# ─── Schemas (DTOs) — extraidos para entity_summary_schemas.py (saneamento) ───
from src.plan.api.entity_summary_schemas import (
    PhaseInTemplate,
    RoutingTemplateOut,
    BoatInProduction,
    ModeloSummary,
    OperatorScore,
    PhaseDrilldown,
    BoatScore,
    CuringGap,
    FaseSummary,
    OrderInList,
    LeadTimeEntry,
    ClienteHistory,
    ClienteSummary,
    PhaseHistoryEntry,
    EncomendaSummary,
    TopPhaseForOperator,
    OperatorTask,
    OperatorPhaseHistory,
    OperadorSummary,
)



# ─── Router ──────────────────────────────────────────────────────────────────


router = APIRouter(prefix="/v1/entity", tags=["Q.116.A Entity Summary"])


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _status_value(order: ProductionOrder) -> str:
    s = order.status
    return s.value if hasattr(s, "value") else str(s)


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _hours_between(start: Any, end: Any) -> Optional[float]:
    """Horas entre dois timestamps ISO (texto). None se faltar ou for inválido."""
    if not start or not end:
        return None
    try:
        s = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        e = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
    except ValueError:
        return None
    delta = (e - s).total_seconds() / 3600.0
    return round(delta, 1) if delta >= 0 else None


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


async def _build_phase_drilldown(
    session: AsyncSession,
    tenant_id: UUID,
    routing: "RoutingTemplateOut | None",
) -> List["PhaseDrilldown"]:
    """Q.116.E — top operadores (afinidade) por fase da rota do modelo.

    Uma só query batch a `PhaseOperatorAffinity` para todas as fases da rota
    (evita N+1), agrupada em Python (top-3/fase, score DESC) + um batch
    `Employee` para nomes. Devolve só as fases COM sinal de afinidade, na
    ordem `seq` da rota. Lista vazia quando não há routing nem afinidades —
    honesto, sem mock.
    """
    if routing is None or not routing.phases:
        return []

    phase_ids = [p.phase_id for p in routing.phases]
    aff_stmt = (
        select(PhaseOperatorAffinity)
        .where(
            and_(
                PhaseOperatorAffinity.tenant_id == tenant_id,
                PhaseOperatorAffinity.phase_id.in_(phase_ids),
            )
        )
        .order_by(PhaseOperatorAffinity.score.desc())
    )
    affinities = list((await session.execute(aff_stmt)).scalars().all())
    if not affinities:
        return []

    # Agrupa por fase (input já ordenado score DESC) → top-3 por fase.
    by_phase: dict[str, List[PhaseOperatorAffinity]] = {}
    for a in affinities:
        bucket = by_phase.setdefault(a.phase_id, [])
        if len(bucket) < 3:
            bucket.append(a)

    operator_ids = list({a.operator_id for a in affinities})
    emp_map: dict = {}
    if operator_ids:
        emp_stmt = select(Employee).where(
            and_(
                Employee.tenant_id == tenant_id,
                Employee.id.in_(operator_ids),
            )
        )
        emp_map = {
            e.id: e.employee_name
            for e in (await session.execute(emp_stmt)).scalars().all()
        }

    out: List[PhaseDrilldown] = []
    for p in sorted(routing.phases, key=lambda ph: ph.seq):
        bucket = by_phase.get(p.phase_id, [])
        if not bucket:
            continue  # só fases com sinal de afinidade
        out.append(
            PhaseDrilldown(
                phase_id=p.phase_id,
                phase_name=p.phase_name,
                seq=p.seq,
                top_operators=[
                    OperatorScore(
                        operator_id=str(a.operator_id),
                        operator_name=emp_map.get(a.operator_id, str(a.operator_id)),
                        score=float(a.score),
                        sample_count=int(a.sample_count),
                    )
                    for a in bucket
                ],
            )
        )
    return out


async def _build_operator_phase_history(
    session: AsyncSession,
    employee_code: Optional[str],
    limit: int = 30,
) -> List["OperatorPhaseHistory"]:
    """Q.116.F — histórico de fases trabalhadas pelo operador (factory_raw).

    Fonte: `factory_raw.offp_eq ⋈ of_fp` por `OFFPEQ_E_ID = employee_code`
    (mesma cadeia do job de afinidades Q.150 + nomes de fase via
    `fases_producao`). `text()` defensivo — em dev sem factory_raw devolve
    lista vazia (honesto, sem mock).
    """
    if not employee_code:
        return []
    from sqlalchemy import text

    stmt = text(
        """
        SELECT o."OFFP_OF_ID"::text          AS of_id,
               o."OFFP_FP_ID"::text          AS phase_id,
               fp."FP_NOME"                  AS phase_name,
               o."OFFP_DATAINICIO"           AS started,
               NULLIF(o."OFFP_DATAFIM", '')  AS finished
        FROM factory_raw.offp_eq eq
        JOIN factory_raw.of_fp o ON o."OFFP_ID" = eq."OFFPEQ_OFFP_ID"
        LEFT JOIN factory_raw.fases_producao fp ON fp."FP_ID" = o."OFFP_FP_ID"
        WHERE eq."OFFPEQ_E_ID" = :ecode
          AND o."OFFP_FP_ID" IS NOT NULL
          AND NULLIF(o."OFFP_DATAINICIO", '') IS NOT NULL
        ORDER BY o."OFFP_DATAINICIO" DESC
        LIMIT :lim
        """
    )
    try:
        rows = (
            await session.execute(stmt, {"ecode": str(employee_code), "lim": limit})
        ).mappings().all()
    except (SQLAlchemyError, AttributeError) as exc:  # factory_raw ausente em dev.
        logger.debug("operator phase_history skipped (%s)", exc)
        return []

    out: List[OperatorPhaseHistory] = []
    for r in rows:
        started = r["started"]
        finished = r["finished"]
        out.append(
            OperatorPhaseHistory(
                of_legacy_id=_safe_int(r["of_id"]),
                phase_id=str(r["phase_id"]),
                phase_name=r["phase_name"],
                started_at=str(started) if started is not None else None,
                finished_at=str(finished) if finished is not None else None,
                hours=_hours_between(started, finished),
            )
        )
    return out


async def _build_encomenda_phase_history(
    session: AsyncSession,
    legacy_id: int,
    limit: int = 100,
) -> List["PhaseHistoryEntry"]:
    """Q.172.F4E (era TODO Q.116.A) — histórico REAL de fases da encomenda.

    Fonte: `factory_raw.of_fp` (a mesma cadeia do histórico do operador
    Q.116.F e dos jobs de afinidade Q.150 — `plan.fases_of_history` está
    vazia em produção, não é fonte). Ordenado cronologicamente, com
    tiebreak `OFFP_ID` (re-trabalhos repetem a fase, datas podem empatar).
    Sentinela SQL-Server `1900-01-01` (= sem data) excluída — mostrar uma
    data falsa seria mock. `text()` defensivo — em dev sem `factory_raw`
    devolve lista vazia (honesto, sem mock).
    """
    from sqlalchemy import text

    stmt = text(
        """
        SELECT fp."FP_NOME"                  AS phase_name,
               o."OFFP_FP_ID"::text          AS phase_id,
               o."OFFP_DATAINICIO"           AS started,
               NULLIF(o."OFFP_DATAFIM", '')  AS finished
        FROM factory_raw.of_fp o
        LEFT JOIN factory_raw.fases_producao fp ON fp."FP_ID" = o."OFFP_FP_ID"
        WHERE o."OFFP_OF_ID" = :of_id
          AND NULLIF(o."OFFP_DATAINICIO", '') IS NOT NULL
          AND o."OFFP_DATAINICIO"::text NOT LIKE '1900-01-01%'
        ORDER BY o."OFFP_DATAINICIO" ASC, o."OFFP_ID" ASC
        LIMIT :lim
        """
    )
    try:
        rows = (
            await session.execute(stmt, {"of_id": int(legacy_id), "lim": limit})
        ).mappings().all()
    except (SQLAlchemyError, AttributeError) as exc:  # factory_raw ausente em dev.
        logger.debug("encomenda phase_history skipped (%s)", exc)
        return []

    out: List[PhaseHistoryEntry] = []
    for r in rows:
        started = r["started"]
        finished = r["finished"]
        out.append(
            PhaseHistoryEntry(
                phase_name=str(r["phase_name"] or r["phase_id"]),
                start_at=str(started) if started is not None else None,
                end_at=str(finished) if finished is not None else None,
            )
        )
    return out


async def _build_operator_today_tasks(
    session: AsyncSession,
    tenant_id: UUID,
    employee_code: Optional[str],
) -> List["OperatorTask"]:
    """Q.116.F — tarefas de HOJE do operador no último ScheduleCommit.

    O operador vive em `op["workers"]` como `employee_code` (Q.140.F/Q.148),
    não em `operator_id`. Filtramos as operações cujo `start_time` começa
    hoje (UTC). Import/lookup defensivos — sem plano devolve lista vazia
    (honesto, sem mock).
    """
    if not employee_code:
        return []
    try:
        from src.plan.cpo.commits import ScheduleCommit

        stmt = (
            select(ScheduleCommit)
            .where(ScheduleCommit.tenant_id == tenant_id)
            .order_by(ScheduleCommit.created_at.desc())
            .limit(1)
        )
        commit = (await session.execute(stmt)).scalar_one_or_none()
    except (ImportError, SQLAlchemyError) as exc:  # modelo/tabela ausente.
        logger.debug("operator today_tasks commit lookup skipped (%s)", exc)
        return []
    if commit is None:
        return []

    today_iso = datetime.now(timezone.utc).date().isoformat()
    ecode = str(employee_code)
    raw_tasks: List[dict] = []
    for op in (getattr(commit, "operations", None) or []):
        workers = op.get("workers") or []
        if ecode not in [str(w) for w in workers]:
            continue
        start = op.get("start_time")
        if not start or str(start)[:10] != today_iso:
            continue
        raw_tasks.append(op)

    if not raw_tasks:
        return []

    # Nomes de fase via RoutingTemplatePhase (mesmo namespace do decoder).
    phase_ids = list({op.get("phase_id") for op in raw_tasks if op.get("phase_id")})
    name_map: dict = {}
    if phase_ids:
        names_stmt = select(
            RoutingTemplatePhase.phase_id, RoutingTemplatePhase.phase_name
        ).where(
            and_(
                RoutingTemplatePhase.tenant_id == tenant_id,
                RoutingTemplatePhase.phase_id.in_(phase_ids),
            )
        )
        for pid, pname in (await session.execute(names_stmt)).all():
            if pid not in name_map and pname:
                name_map[pid] = pname

    out: List[OperatorTask] = [
        OperatorTask(
            operation_id=str(op.get("operation_id") or ""),
            order_legacy_id=_safe_int(op.get("order_id")),
            phase_name=name_map.get(op.get("phase_id"))
            or (str(op.get("phase_id")) if op.get("phase_id") else "—"),
            start_time=op.get("start_time"),
            end_time=op.get("end_time"),
        )
        for op in raw_tasks
    ]
    out.sort(key=lambda t: t.start_time or "")
    return out


def _as_date(value: Any) -> Any:
    """datetime → date; date passa tal e qual; None → None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value


async def _customer_of_ids_from_erp(
    session: AsyncSession,
    customer_code: Optional[str],
) -> List[int]:
    """Q.172.F4E (era TODO Q.116.C) — OF_IDs do cliente no espelho ERP.

    `core.customers.customer_code` é o `E_ID` da entidade NELO (seed
    Q.125 `setup_customers_from_entidade`); `factory_raw.ordemfabrico`
    liga cada OF ao cliente via `OF_E_ID`. Esta é a junção REAL que o
    filtro antigo por `customer_name` (atributo inexistente no modelo —
    lista sempre vazia) nunca conseguiu fazer.

    Devolve [] quando o código não é numérico (cliente criado à mão) ou
    quando o espelho `factory_raw` não está disponível (dev) — o caller
    devolve lista vazia honesta, sem mock.
    """
    try:
        entity_id = int(str(customer_code).strip())
    except (TypeError, ValueError):
        return []
    from sqlalchemy import text

    stmt = text(
        """
        SELECT o."OF_ID" AS of_id
        FROM factory_raw.ordemfabrico o
        WHERE o."OF_E_ID" = :eid
        -- mais recentes primeiro; cap defensivo p/ clientes com décadas
        -- de histórico (a lista alimenta um IN() em production_orders)
        ORDER BY o."OF_ID" DESC
        LIMIT 2000
        """
    )
    try:
        rows = (await session.execute(stmt, {"eid": entity_id})).mappings().all()
    except (SQLAlchemyError, AttributeError) as exc:  # factory_raw ausente em dev.
        logger.debug("cliente OF_IDs (ERP mirror) skipped (%s)", exc)
        return []
    out: List[int] = []
    for r in rows:
        v = _safe_int(r["of_id"])
        if v is not None:
            out.append(v)
    return out


async def _build_cliente_history(
    session: AsyncSession,
    customer_name: Optional[str],
    customer_orders: List[ProductionOrder],
) -> "ClienteHistory":
    """Q.116.D — lead-time (encomendas concluídas) + revenue (marts).

    Lead-time: `completed_date − created_date` das encomendas concluídas já
    casadas pelo nome (mesma base honesta do gap Q.53.I). Revenue:
    `SUM(facturado_eur)` em `marts.v_facturacao_mes` por nome de cliente —
    `text()` defensivo, None quando a view não existe (dev) ou não casa.
    """
    # ── Lead-time (em memória, sem query) ───────────────────────────────
    lead_times: List[LeadTimeEntry] = []
    for o in customer_orders:
        cd = _as_date(getattr(o, "created_date", None))
        fd = _as_date(getattr(o, "completed_date", None))
        if cd is None or fd is None:
            continue
        days = (fd - cd).days
        if days < 0:
            continue
        lead_times.append(LeadTimeEntry(legacy_id=int(o.legacy_id), days=float(days)))

    avg_lead = (
        round(sum(lt.days for lt in lead_times) / len(lead_times), 1)
        if lead_times
        else None
    )

    # ── Revenue (marts.v_facturacao_mes, por nome) ──────────────────────
    revenue_eur: Optional[float] = None
    revenue_note: Optional[str] = None
    if customer_name:
        try:
            from sqlalchemy import text

            rev = (
                await session.execute(
                    text(
                        "SELECT SUM(facturado_eur) AS total "
                        "FROM marts.v_facturacao_mes WHERE cliente = :name"
                    ),
                    {"name": customer_name},
                )
            ).scalar()
            if rev is not None:
                revenue_eur = float(rev)
                revenue_note = "Base sem IVA (PHC) · match por nome de cliente."
            else:
                revenue_note = (
                    "Sem facturação para este nome (ou mart por sincronizar)."
                )
        except SQLAlchemyError as exc:  # mart de facturação ausente em dev.
            logger.debug("cliente revenue skipped (%s)", exc)
            revenue_note = "Mart de facturação indisponível."

    return ClienteHistory(
        completed_orders_count=len(lead_times),
        avg_lead_time_days=avg_lead,
        lead_times=lead_times[:20],
        revenue_eur=revenue_eur,
        revenue_note=revenue_note,
    )


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
    # Q.172.F4E (fecha o TODO Q.117.X): o truncamento a 20 deixa de ser
    # silencioso — `in_production_truncated` + `in_production_count`
    # (total real) dizem ao frontend que a lista é parcial.
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
    in_production_truncated = len(in_production) > 20
    in_production = in_production[:20]

    in_production_boats = await _build_boats_in_production(
        session, tenant_id, in_production, model_id
    )

    # Q.116.C — encomendas activas (não-CANCELLED) do modelo para a tab
    # Encomendas. Mesmo shape/semântica que ClienteSummary.orders, ordenadas
    # created_date DESC (None no fim), limit 20.
    model_orders = [o for o in orders if o.status != OrderStatus.CANCELLED]
    model_orders.sort(
        key=lambda o: (o.created_date is None, o.created_date),
        reverse=True,
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
        for o in model_orders[:20]
    ]

    # Q.116.E — drill-down por fase: top operadores (afinidade) para cada
    # fase da rota resolvida. Vazio quando o modelo não tem routing.
    phase_drilldown_out = await _build_phase_drilldown(
        session, tenant_id, routing_template_out
    )

    return ModeloSummary(
        model_id=model_id,
        model_name=model_id,  # business-key é também o nome humano no NELO
        product_type=product_type,
        routing_template=routing_template_out,
        active_orders_count=active_orders_count,
        in_production_count=in_production_count,
        in_production_boats=in_production_boats,
        in_production_truncated=in_production_truncated,
        orders=orders_out,
        phase_drilldown=phase_drilldown_out,
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
    # Q.172.F4E — ORDER BY no DISTINCT antes do LIMIT 1: sem ele o nome
    # devolvido era não-determinístico quando a fase tem >1 nome nos templates.
    phase_name_stmt = (
        select(distinct(RoutingTemplatePhase.phase_name))
        .where(
            and_(
                RoutingTemplatePhase.tenant_id == tenant_id,
                RoutingTemplatePhase.phase_id == phase_id,
            )
        )
        .order_by(RoutingTemplatePhase.phase_name)
        .limit(1)
    )
    phase_name_result = await session.execute(phase_name_stmt)
    phase_name_row = phase_name_result.scalar_one_or_none()
    phase_name = phase_name_row or phase_id
    has_template_match = phase_name_row is not None

    # 2. top_operators — top 5 por score DESC (tiebreak operator_id p/ determinismo).
    aff_stmt = (
        select(PhaseOperatorAffinity)
        .where(
            and_(
                PhaseOperatorAffinity.tenant_id == tenant_id,
                PhaseOperatorAffinity.phase_id == phase_id,
            )
        )
        .order_by(
            PhaseOperatorAffinity.score.desc(), PhaseOperatorAffinity.operator_id
        )
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

    # 3. difficult_boats — top 5 por score ASC (mais difícil = score mais baixo;
    # tiebreak boat_id p/ determinismo entre execuções).
    boat_stmt = (
        select(BoatPhaseScore)
        .where(
            and_(
                BoatPhaseScore.tenant_id == tenant_id,
                BoatPhaseScore.phase_id == phase_id,
            )
        )
        .order_by(BoatPhaseScore.score.asc(), BoatPhaseScore.boat_id)
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

    # 6. Q.160 — fila inter-fase MEDIDA desta fase (mediana real de of_fp). É o
    # MESMO valor que o CPO usa no decoder (reusa o loader), por isso o número
    # do sheet bate com o do planeador. None se a fase não tem >=5 obs.
    q_by_phase, _q_global = await _load_phase_queue_medians_db(session, tenant_id)
    fila_mediana_h = (
        round(float(q_by_phase[str(phase_id)]), 2)
        if str(phase_id) in q_by_phase else None
    )

    return FaseSummary(
        phase_id=phase_id,
        phase_name=phase_name,
        top_operators=top_operators,
        difficult_boats=difficult_boats,
        curing_gaps_in=curing_gaps_in,
        curing_gaps_out=curing_gaps_out,
        fila_mediana_h=fila_mediana_h,
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

    # 3. Encomendas associadas ao cliente — junção REAL via espelho ERP
    # (Q.172.F4E, fecha o TODO Q.116.C): customer_code (=E_ID NELO) →
    # factory_raw.ordemfabrico.OF_E_ID → production_orders.legacy_id.
    # O filtro antigo comparava `getattr(o, "customer_name", None)` com o
    # nome do cliente, mas ProductionOrder nunca teve essa coluna — a
    # lista vinha SEMPRE vazia (filtro partido, não "sem encomendas").
    # Sem espelho (dev) ou sem OFs → lista vazia honesta.
    customer_orders: List[ProductionOrder] = []
    of_ids = await _customer_of_ids_from_erp(session, customer.customer_code)
    if of_ids:
        orders_stmt = (
            select(ProductionOrder)
            .where(
                and_(
                    ProductionOrder.tenant_id == tenant_id,
                    ProductionOrder.status != OrderStatus.CANCELLED,
                    ProductionOrder.legacy_id.in_(of_ids),
                )
            )
            # Tiebreak legacy_id: created_date é Date (sem hora) — sem o
            # desempate o LIMIT devolvia linhas diferentes entre execuções.
            .order_by(
                ProductionOrder.created_date.desc().nullslast(),
                ProductionOrder.legacy_id.desc(),
            )
            .limit(200)
        )
        orders_result = await session.execute(orders_stmt)
        customer_orders = list(orders_result.scalars().all())

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

    # Q.116.D — secção Histórico (lead-time das concluídas + revenue do mart).
    history = await _build_cliente_history(
        session, customer.customer_name, customer_orders
    )

    return ClienteSummary(
        customer_id=str(customer.id),
        customer_name=customer.customer_name,
        priority=priority,
        active_orders_count=active_orders_count,
        orders=orders_out,
        history=history,
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
    vem do espelho `factory_raw.of_fp` (Q.172.F4E) — lista vazia honesta
    quando o espelho não está disponível (dev) ou a OF não tem fases.
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

    # Q.172.F4E (fecha o TODO Q.116.A) — histórico real de fases via
    # factory_raw.of_fp (OFFP_OF_ID = legacy_id). Vazio honesto em dev
    # sem espelho ERP.
    phase_history: List[PhaseHistoryEntry] = await _build_encomenda_phase_history(
        session, int(legacy_id)
    )

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

    # 2. Top 5 afinidades — score DESC (tiebreak phase_id: o operador é fixo
    # nesta query, por isso o desempate determinístico é pela fase).
    aff_stmt = (
        select(PhaseOperatorAffinity)
        .where(
            and_(
                PhaseOperatorAffinity.tenant_id == tenant_id,
                PhaseOperatorAffinity.operator_id == employee_id,
            )
        )
        .order_by(PhaseOperatorAffinity.score.desc(), PhaseOperatorAffinity.phase_id)
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

    # Q.116.F — tarefas de hoje (último plano) + histórico de fases (ERP).
    today_tasks = await _build_operator_today_tasks(
        session, tenant_id, employee.employee_code
    )
    phase_history = await _build_operator_phase_history(
        session, employee.employee_code
    )

    return OperadorSummary(
        operator_id=str(employee.id),
        operator_name=employee.employee_name,
        role=role,
        active=active_flag,
        top_phases=top_phases,
        total_phases_with_data=total_phases_with_data,
        today_tasks=today_tasks,
        phase_history=phase_history,
    )
