"""Q.115.X5 — CancelService: cancel/retire/deactivate de obras, encomendas, barcos, pessoas.

Invariantes:
- Soft-delete sempre (sem DROP de rows — histórico preservado para ML).
- Audit obrigatório em cada mutação (Q.61.18).
- Kafka emit via outbox (aggregate_type diferente por entidade).
- PT-PT em mensagens de erro.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.employee import Employee, EmploymentStatus
from src.core.models.encomenda_cancelled import EncomendaCancelled
from src.core.models.product import Product, ProductStatus
from src.governance.audit_service import audit_change
from src.plan.models.order import ProductionOrder, OrderStatus
from src.shared.observability import get_trace_id
from src.shared.outbox_models import EventOutbox


# ─── Resultado estruturado ────────────────────────────────────────────────────


@dataclass
class CancelResult:
    success: bool
    entity_id: str
    action: str
    cancelled_at: datetime
    audit_trace_id: Optional[str] = None
    decision_id: Optional[UUID] = None  # preenchido se Q.17 human_approval activo
    warning: Optional[str] = None
    warnings: list[str] = field(default_factory=list)


# ─── Helpers internos ─────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _emit_outbox(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    aggregate_id: UUID,
    aggregate_type: str,
    event_type: str,
    payload: dict,
) -> None:
    """Escreve evento no outbox (mesma tx que a mutação)."""
    row = EventOutbox(
        id=uuid4(),
        tenant_id=tenant_id,
        aggregate_id=aggregate_id,
        aggregate_type=aggregate_type,
        event_type=event_type,
        payload=payload,
        status="pending",
    )
    session.add(row)


# ─── Service ─────────────────────────────────────────────────────────────────


async def cancel_work_order(
    session: AsyncSession,
    *,
    of_id: UUID,
    reason: str,
    tenant_id: UUID,
    user_id: str,
) -> CancelResult:
    """Cancela uma ordem de fabrico (soft-delete).

    Validações:
    - OF existe (404 semântico: levanta ValueError).
    - OF não está já cancelada (409 semântico: levanta ValueError).
    Acção:
    - status = 'CANCELLED', preenche cancelled_at/by/reason.
    - Audit + Kafka via outbox.
    """
    stmt = select(ProductionOrder).where(
        ProductionOrder.id == of_id,
        ProductionOrder.tenant_id == tenant_id,
    )
    result = await session.execute(stmt)
    order = result.scalar_one_or_none()

    if order is None:
        raise LookupError(f"Ordem de fabrico '{of_id}' não encontrada.")

    if order.status == OrderStatus.CANCELLED:
        raise ValueError(f"Ordem de fabrico '{of_id}' já está cancelada.")

    now = _now()
    old_status = order.status.value if hasattr(order.status, "value") else str(order.status)

    order.status = OrderStatus.CANCELLED
    order.cancelled_at = now
    order.cancelled_by = user_id
    order.cancellation_reason = reason

    await session.flush()

    audit_row = await audit_change(
        session,
        tenant_id=tenant_id,
        entity_type="production_order",
        entity_id=of_id,
        action="UPDATE",
        old_values={"status": old_status},
        new_values={
            "status": "CANCELLED",
            "cancellation_reason": reason[:200],
        },
        actor_id=None,
        reason="cancel_work_order",
    )

    await _emit_outbox(
        session,
        tenant_id=tenant_id,
        aggregate_id=of_id,
        aggregate_type="production_order",
        event_type="production_order.cancelled",
        payload={
            "of_id": str(of_id),
            "reason": reason,
            "cancelled_by": user_id,
            "cancelled_at": now.isoformat(),
        },
    )

    return CancelResult(
        success=True,
        entity_id=str(of_id),
        action="cancel_work_order",
        cancelled_at=now,
        audit_trace_id=audit_row.trace_id,
    )


async def cancel_encomenda(
    session: AsyncSession,
    *,
    encomenda_id: str,
    reason: str,
    tenant_id: UUID,
    user_id: str,
) -> CancelResult:
    """Regista cancelamento de encomenda de cliente.

    Não escreve no ERP (MAR-KAYAKS) — cria row em core.encomendas_cancelled.
    Emite Kafka para auto_propose recompute.
    """
    # Verifica duplicado (idempotência: encomenda já cancelada → 409 semântico)
    existing = await session.execute(
        select(EncomendaCancelled).where(
            EncomendaCancelled.tenant_id == tenant_id,
            EncomendaCancelled.encomenda_id == encomenda_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError(f"Encomenda '{encomenda_id}' já está registada como cancelada.")

    now = _now()
    trace_id = get_trace_id()

    row = EncomendaCancelled(
        id=uuid4(),
        tenant_id=tenant_id,
        encomenda_id=encomenda_id,
        reason=reason,
        cancelled_by=user_id,
        cancelled_at=now,
        audit_trace_id=trace_id,
    )
    session.add(row)
    await session.flush()

    await audit_change(
        session,
        tenant_id=tenant_id,
        entity_type="encomenda_cancelled",
        entity_id=row.id,
        action="INSERT",
        new_values={"encomenda_id": encomenda_id, "reason": reason[:200]},
        actor_id=None,
        reason="cancel_encomenda",
    )

    await _emit_outbox(
        session,
        tenant_id=tenant_id,
        aggregate_id=row.id,
        aggregate_type="encomenda",
        event_type="encomenda.cancelled",
        payload={
            "encomenda_id": encomenda_id,
            "reason": reason,
            "cancelled_by": user_id,
            "cancelled_at": now.isoformat(),
        },
    )

    return CancelResult(
        success=True,
        entity_id=encomenda_id,
        action="cancel_encomenda",
        cancelled_at=now,
        audit_trace_id=trace_id,
    )


async def retire_boat(
    session: AsyncSession,
    *,
    boat_id: UUID,
    reason: str,
    tenant_id: UUID,
    user_id: str,
) -> CancelResult:
    """Retira barco/modelo de produção (soft-flag).

    Não DROP — mantém histórico para ML.
    """
    stmt = select(Product).where(
        Product.id == boat_id,
        Product.tenant_id == tenant_id,
    )
    result = await session.execute(stmt)
    product = result.scalar_one_or_none()

    if product is None:
        raise LookupError(f"Barco/produto '{boat_id}' não encontrado.")

    now = _now()
    old_status = product.status.value if hasattr(product.status, "value") else str(product.status)

    product.status = ProductStatus.INACTIVE
    product.retired_at = now
    product.retired_by = user_id
    product.retirement_reason = reason

    await session.flush()

    audit_row = await audit_change(
        session,
        tenant_id=tenant_id,
        entity_type="product",
        entity_id=boat_id,
        action="UPDATE",
        old_values={"status": old_status, "retired_at": None},
        new_values={
            "status": "INACTIVE",
            "retired_at": now.isoformat(),
            "retirement_reason": reason[:200],
        },
        actor_id=None,
        reason="retire_boat",
    )

    await _emit_outbox(
        session,
        tenant_id=tenant_id,
        aggregate_id=boat_id,
        aggregate_type="product",
        event_type="product.retired",
        payload={
            "boat_id": str(boat_id),
            "reason": reason,
            "retired_by": user_id,
            "retired_at": now.isoformat(),
        },
    )

    return CancelResult(
        success=True,
        entity_id=str(boat_id),
        action="retire_boat",
        cancelled_at=now,
        audit_trace_id=audit_row.trace_id,
    )


async def deactivate_employee(
    session: AsyncSession,
    *,
    employee_id: UUID,
    reason: str,
    tenant_id: UUID,
    user_id: str,
) -> CancelResult:
    """Desactiva operador (soft-flag active=false).

    Se tiver operações futuras planeadas, inclui warning no resultado
    e emite Kafka para replan. Não bloqueia a desactivação.
    """
    stmt = select(Employee).where(
        Employee.id == employee_id,
        Employee.tenant_id == tenant_id,
    )
    result = await session.execute(stmt)
    employee = result.scalar_one_or_none()

    if employee is None:
        raise LookupError(f"Operador '{employee_id}' não encontrado.")

    if not employee.active:
        raise ValueError(f"Operador '{employee_id}' já está desactivado.")

    # Verifica ops futuras — consulta worker_phase_assignment
    from src.hr.models.worker_phase_assignment import WorkerPhaseAssignment

    future_ops_result = await session.execute(
        select(WorkerPhaseAssignment).where(
            WorkerPhaseAssignment.worker_id == employee_id,
            WorkerPhaseAssignment.tenant_id == tenant_id,
            WorkerPhaseAssignment.assigned_at >= _now(),
            WorkerPhaseAssignment.assignment_type == "planned",
        )
    )
    future_ops = future_ops_result.scalars().all()
    n_future = len(future_ops)

    now = _now()
    old_status = employee.status.value if hasattr(employee.status, "value") else str(employee.status)

    employee.active = False
    employee.status = EmploymentStatus.TERMINATED
    employee.deactivated_at = now
    employee.deactivated_by = user_id
    employee.deactivation_reason = reason

    await session.flush()

    audit_row = await audit_change(
        session,
        tenant_id=tenant_id,
        entity_type="employee",
        entity_id=employee_id,
        action="UPDATE",
        old_values={"active": True, "status": old_status},
        new_values={
            "active": False,
            "status": "TERMINATED",
            "deactivation_reason": reason[:200],
        },
        actor_id=None,
        reason="deactivate_employee",
    )

    event_type = "employee.deactivated"
    payload: dict = {
        "employee_id": str(employee_id),
        "reason": reason,
        "deactivated_by": user_id,
        "deactivated_at": now.isoformat(),
        "future_ops_count": n_future,
        "replan_needed": n_future > 0,
    }

    await _emit_outbox(
        session,
        tenant_id=tenant_id,
        aggregate_id=employee_id,
        aggregate_type="employee",
        event_type=event_type,
        payload=payload,
    )

    warning: Optional[str] = None
    if n_future > 0:
        warning = (
            f"Operador tem {n_future} operação(ões) planeada(s) a partir de agora. "
            "Replan automático foi solicitado via Kafka."
        )

    return CancelResult(
        success=True,
        entity_id=str(employee_id),
        action="deactivate_employee",
        cancelled_at=now,
        audit_trace_id=audit_row.trace_id,
        warning=warning,
    )
