"""Q.116.E — LIST endpoints master-data para a tab Configurações > Master Data.

Resolve regressão silenciosa do Q.115.X5: `MasterDataTab.tsx` consumia
4 endpoints LIST que NÃO existiam e caía sempre em EmptyState. Este
módulo entrega-os.

4 endpoints READ-ONLY:
  GET /v1/work-orders?status=active&limit=20
  GET /v1/encomendas?status=active&limit=20
  GET /v1/master-data/boats?show_retired=false&limit=20
  GET /v1/master-data/employees?show_inactive=false&limit=20

Shapes alinhados COM EXACTIDÃO com `frontend/src/lib/api/masterDataApi.ts`
(WorkOrderItem, EncomendasItem, BoatItem, EmployeeItem). Qualquer drift de
campo aqui = EmptyState no frontend.

RBAC: Permission.SCHEDULE_READ (segue padrão Q.115).

NOTA Q.115.X5: o nelinho não tem tabela `encomenda` separada de
ProductionOrder. Os endpoints /v1/encomendas e /v1/work-orders devolvem
a mesma fonte (`production_orders`) com shapes diferentes. Quando
Q.66.X separar Encomenda↔ProductionOrder, este endpoint passa a ler a
nova tabela — ver TODO inline.

NOTA Q.115.X5: o conceito "barco" no NELO é o produto entregue
(ProductionOrder.COMPLETED). Aqui devolvemos a partir da mesma
tabela com filtro `completed_date IS NOT NULL` (active) ou
`cancelled_at IS NOT NULL` (retired).
"""
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.employee import Employee, EmploymentStatus
from src.core.models.partner import Customer
from src.plan.models.order import OrderStatus, ProductionOrder
from src.plan.services.phase_classification import is_completed_phase
from src.shared.auth.headers import require_tenant_header
from src.shared.auth.rbac import Permission, PermissionDependency
from src.shared.database import get_session

router = APIRouter(tags=["Q.116.E Master Data Lists"])

_require_schedule_read = PermissionDependency([Permission.SCHEDULE_READ])


# ─── Schemas ─────────────────────────────────────────────────────────────────


class WorkOrderItem(BaseModel):
    """Ordem de fabrico em curso — alinhada com frontend WorkOrderItem.

    `of_id` é stringificada (frontend usa string em todo o lado para
    consistência com IDs externos do ERP).

    Q.116.E (fix pós-reviewer): `modelo_id` e `cliente_id` expostos para
    o sweep clickable. `modelo_id = product_name` (business key NELO);
    `cliente_id` via lookup customer_name → core.customers.id (None se
    sem match).
    """

    of_id: str
    modelo: str
    modelo_id: Optional[str]
    cliente: str
    cliente_id: Optional[str]
    fase_actual: str
    status: str


class EncomendasItem(BaseModel):
    """Encomenda comercial — alinhada com frontend EncomendasItem.

    Por agora deriva de ProductionOrder (não há tabela Encomenda
    separada). `total_eur` é None até Q.66.X separar — None honesto, nunca
    0,00 € fabricado no ecrã (invariante #8).

    Q.116.E (fix pós-reviewer): `cliente_id` exposto para Clickable.
    """

    encomenda_id: str
    cliente: str
    cliente_id: Optional[str]
    data: str
    total_eur: Optional[float]


class BoatItem(BaseModel):
    """Barco/modelo entregue — alinhada com frontend BoatItem.

    `retired_at` é ISO string ou None. Convencionado: barcos
    "activos" = COMPLETED não cancelled; "retirados" = cancelled_at != None.

    Q.116.E (fix pós-reviewer): `modelo_id` exposto para Clickable.
    """

    boat_id: str
    modelo_nome: str
    modelo_id: Optional[str]
    retired_at: Optional[str]


class EmployeeItem(BaseModel):
    """Operador — alinhada com frontend EmployeeItem."""

    employee_id: str
    nome: str
    role: str
    active: bool


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _status_value(order: ProductionOrder) -> str:
    s = order.status
    return s.value if hasattr(s, "value") else str(s)


async def _customer_id_lookup(
    session: AsyncSession, tenant_id: UUID, customer_names: List[str]
) -> dict:
    """Q.116.E — batch lookup customer_name → customer.id (UUID stringificada).

    Evita N+1: 1 SELECT por chamada do endpoint. Retorna dict; clientes
    sem match não aparecem (caller usa .get() com default None).
    """
    unique = {n for n in customer_names if n}
    if not unique:
        return {}
    stmt = select(Customer.id, Customer.customer_name).where(
        and_(
            Customer.tenant_id == tenant_id,
            Customer.customer_name.in_(unique),
        )
    )
    rows = (await session.execute(stmt)).all()
    return {name: str(cid) for cid, name in rows}


# ─── GET /v1/work-orders ─────────────────────────────────────────────────────


@router.get(
    "/v1/work-orders",
    response_model=List[WorkOrderItem],
    dependencies=[Depends(_require_schedule_read)],
    summary="Lista ordens de fabrico (work-orders) activas",
)
async def list_work_orders(
    status: str = Query("active", description="Filtro de estado: active|all|completed|cancelled"),
    limit: int = Query(20, ge=1, le=200),
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> List[WorkOrderItem]:
    """Lista ordens de fabrico do tenant.

    `status=active` (default) → exclui CANCELLED e fases terminais
    (`is_completed_phase`). Mantém a UI focada em trabalho em curso.

    `status=all` → não filtra. Útil para auditoria.

    Ordenação: created_date DESC (fallback para legacy_id DESC).
    """
    stmt = (
        select(ProductionOrder)
        .where(ProductionOrder.tenant_id == tenant_id)
        .order_by(ProductionOrder.created_date.desc().nullslast())
        .limit(limit * 2 if status == "active" else limit)
    )
    result = await session.execute(stmt)
    rows = list(result.scalars().all())

    if status == "active":
        rows = [
            r
            for r in rows
            if r.status != OrderStatus.CANCELLED
            and not is_completed_phase(r.current_phase_name)
        ]
    elif status == "cancelled":
        rows = [r for r in rows if r.status == OrderStatus.CANCELLED]
    elif status == "completed":
        rows = [r for r in rows if r.status == OrderStatus.COMPLETED]
    # status == "all" → sem filtro

    rows = rows[:limit]

    cust_map = await _customer_id_lookup(
        session, tenant_id, [getattr(r, "customer_name", None) or "" for r in rows]
    )

    return [
        WorkOrderItem(
            of_id=str(r.legacy_id),
            modelo=r.product_name,
            modelo_id=r.product_name,
            cliente=getattr(r, "customer_name", None) or "",
            cliente_id=cust_map.get(getattr(r, "customer_name", None) or ""),
            fase_actual=r.current_phase_name,
            status=_status_value(r),
        )
        for r in rows
    ]


# ─── GET /v1/encomendas ──────────────────────────────────────────────────────


@router.get(
    "/v1/encomendas",
    response_model=List[EncomendasItem],
    dependencies=[Depends(_require_schedule_read)],
    summary="Lista encomendas comerciais activas",
)
async def list_encomendas(
    status: str = Query("active", description="Filtro de estado: active|all|cancelled"),
    limit: int = Query(20, ge=1, le=200),
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> List[EncomendasItem]:
    """Lista encomendas comerciais.

    TODO Q.66.X: consolidar quando tabela Encomenda separada existir. Por
    agora deriva de ProductionOrder — cada OF representa uma encomenda
    1:1. `total_eur` fica 0.0 até a tabela separada chegar com price
    populada.
    """
    stmt = (
        select(ProductionOrder)
        .where(ProductionOrder.tenant_id == tenant_id)
        .order_by(ProductionOrder.created_date.desc().nullslast())
        .limit(limit * 2 if status == "active" else limit)
    )
    result = await session.execute(stmt)
    rows = list(result.scalars().all())

    if status == "active":
        rows = [r for r in rows if r.status != OrderStatus.CANCELLED]
    elif status == "cancelled":
        rows = [r for r in rows if r.status == OrderStatus.CANCELLED]

    rows = rows[:limit]

    cust_map = await _customer_id_lookup(
        session, tenant_id, [getattr(r, "customer_name", None) or "" for r in rows]
    )

    return [
        EncomendasItem(
            encomenda_id=str(r.legacy_id),
            cliente=getattr(r, "customer_name", None) or "",
            cliente_id=cust_map.get(getattr(r, "customer_name", None) or ""),
            data=(
                r.created_date.isoformat()
                if r.created_date is not None
                else ""
            ),
            # Q.168.C — None honesto (era 0.0 fabricado a pintar '0,00 €'
            # no MasterDataTab). Q.66.X liga o valor real quando a tabela
            # Encomenda separada existir.
            total_eur=None,
        )
        for r in rows
    ]


# ─── GET /v1/master-data/boats ───────────────────────────────────────────────


@router.get(
    "/v1/master-data/boats",
    response_model=List[BoatItem],
    dependencies=[Depends(_require_schedule_read)],
    summary="Lista barcos (modelos entregues)",
)
async def list_boats(
    show_retired: bool = Query(False, description="Incluir barcos cancelled/retired"),
    limit: int = Query(20, ge=1, le=200),
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> List[BoatItem]:
    """Lista barcos do tenant.

    Convenção Q.115.X5: "barco" = ProductionOrder com `completed_date`
    populada. "Retirado" = `cancelled_at IS NOT NULL` (soft-cancel via
    Q.115.X5 retire_boat).

    `show_retired=false` (default) → só barcos activos (não cancelled).
    `show_retired=true` → inclui também cancelled.
    """
    stmt = (
        select(ProductionOrder)
        .where(
            and_(
                ProductionOrder.tenant_id == tenant_id,
                ProductionOrder.completed_date.is_not(None),
            )
        )
        .order_by(ProductionOrder.completed_date.desc().nullslast())
        .limit(limit * 2 if not show_retired else limit)
    )
    result = await session.execute(stmt)
    rows = list(result.scalars().all())

    if not show_retired:
        rows = [r for r in rows if r.cancelled_at is None]

    rows = rows[:limit]

    return [
        BoatItem(
            boat_id=str(r.legacy_id),
            modelo_nome=r.product_name,
            modelo_id=r.product_name,
            retired_at=(
                r.cancelled_at.isoformat() if r.cancelled_at is not None else None
            ),
        )
        for r in rows
    ]


# ─── GET /v1/master-data/employees ───────────────────────────────────────────


@router.get(
    "/v1/master-data/employees",
    response_model=List[EmployeeItem],
    dependencies=[Depends(_require_schedule_read)],
    summary="Lista operadores",
)
async def list_employees(
    show_inactive: bool = Query(False, description="Incluir operadores inactivos"),
    limit: int = Query(20, ge=1, le=200),
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> List[EmployeeItem]:
    """Lista operadores do tenant.

    Convenção: `active` é o flag soft-deactivate do Q.115.X5. O campo
    `status` (EmploymentStatus) continua a existir como histórico HR mas
    para o painel master-data o que importa é o flag binário.

    `show_inactive=false` (default) → só operadores com `active=True`.
    `show_inactive=true` → inclui inactivos (active=False).

    `role` mapeia para `job_title` (string livre no ERP) — fallback para
    `department` se vazio, ou string vazia.
    """
    stmt = (
        select(Employee)
        .where(Employee.tenant_id == tenant_id)
        .order_by(Employee.employee_name.asc())
        .limit(limit * 2 if not show_inactive else limit)
    )
    result = await session.execute(stmt)
    rows = list(result.scalars().all())

    if not show_inactive:
        rows = [r for r in rows if getattr(r, "active", True)]

    rows = rows[:limit]

    return [
        EmployeeItem(
            employee_id=str(r.id),
            nome=r.employee_name,
            role=(r.job_title or r.department or ""),
            active=bool(getattr(r, "active", True)),
        )
        for r in rows
    ]
