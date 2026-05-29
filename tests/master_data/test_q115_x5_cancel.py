"""Q.115.X5 — Testes para cancel/retire/deactivate (obras/encomendas/barcos/pessoas).

11 testes:
1.  cancel_work_order happy path → status=CANCELLED + audit + outbox emit
2.  cancel_work_order OF inexistente → LookupError
3.  cancel_work_order já cancelada → ValueError (409)
4.  cancel_encomenda happy path → success=True + audit + outbox emit
5.  retire_boat happy path → retired_at populado + audit + outbox emit
6.  retire_boat inexistente → LookupError
7.  deactivate_employee com ops futuras → warning + replan_needed=True no payload
8.  deactivate_employee → active=False
9.  reason muito curta (<10c) → ValidationError (Pydantic min_length=10)
10. RBAC sem permission → 403
11. Audit log: cada acção escreve linha com reason correcto

Padrão: FakeSession in-memory. Async SQLAlchemy 2.0. DAMP.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

from pydantic import ValidationError

from src.core.models.employee import Employee, EmploymentStatus, EmploymentType
from src.core.models.encomenda_cancelled import EncomendaCancelled
from src.core.models.product import Product, ProductStatus, ProductType
from src.master_data.services.cancel_service import (
    cancel_encomenda,
    cancel_work_order,
    deactivate_employee,
    retire_boat,
)
from src.plan.models.order import OrderStatus, ProductionOrder

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
_NOW = datetime(2026, 5, 28, 10, 0, 0, tzinfo=timezone.utc)


# ─── Fake session ─────────────────────────────────────────────────────────────


class _Bag:
    """Store simples para objectos adicionados à session fake."""

    def __init__(self) -> None:
        self.added: List[Any] = []
        self._query_result: Any = None

    def set_query(self, obj: Any) -> None:
        self._query_result = obj


class _FakeResult:
    def __init__(self, obj: Any) -> None:
        self._obj = obj

    def scalar_one_or_none(self) -> Any:
        return self._obj

    def scalars(self) -> "_FakeResult":
        return self

    def all(self) -> List[Any]:
        if self._obj is None:
            return []
        if isinstance(self._obj, list):
            return self._obj
        return [self._obj]


class _FakeSession:
    """Session async mínima para testes unitários do CancelService."""

    def __init__(self) -> None:
        self.added: List[Any] = []
        self._execute_results: List[Any] = []  # stack FIFO
        self.rollback = AsyncMock()
        self.commit = AsyncMock()

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        pass

    def push_result(self, obj: Any) -> None:
        """Empurra resultado para a próxima chamada a execute()."""
        self._execute_results.append(obj)

    async def execute(self, _stmt: Any) -> _FakeResult:
        if self._execute_results:
            return _FakeResult(self._execute_results.pop(0))
        return _FakeResult(None)

    def get_added_type(self, cls: type) -> List[Any]:
        return [o for o in self.added if isinstance(o, cls)]


# ─── Fixtures ─────────────────────────────────────────────────────────────────


def _make_order(
    status: OrderStatus = OrderStatus.IN_PROGRESS,
    *,
    tenant_id: UUID = TENANT_ID,
) -> ProductionOrder:
    # Q.122.B — ProductionOrder() (não __new__): o construtor declarativo default
    # configura o _sa_instance_state, necessário para setar atributos mapeados.
    # __new__ bypassa-o → AttributeError em order.id = ... (SQLAlchemy 2.0).
    order = ProductionOrder()
    order.id = uuid4()
    order.tenant_id = tenant_id
    order.legacy_id = 42
    order.product_name = "K1 Vanquish"
    order.product_type = "K1"
    order.current_phase_name = "PINTURA"
    order.status = status
    order.cancelled_at = None
    order.cancelled_by = None
    order.cancellation_reason = None
    return order


def _make_product(
    *,
    tenant_id: UUID = TENANT_ID,
) -> Product:
    p = Product()
    p.id = uuid4()
    p.tenant_id = tenant_id
    p.product_code = "K1-VQ"
    p.product_name = "K1 Vanquish"
    p.product_type = ProductType.FINISHED_GOOD
    p.status = ProductStatus.ACTIVE
    p.retired_at = None
    p.retired_by = None
    p.retirement_reason = None
    return p


def _make_employee(
    *,
    active: bool = True,
    tenant_id: UUID = TENANT_ID,
) -> Employee:
    emp = Employee()
    emp.id = uuid4()
    emp.tenant_id = tenant_id
    emp.employee_code = "OP-001"
    emp.employee_name = "João Silva"
    emp.status = EmploymentStatus.ACTIVE
    emp.employment_type = EmploymentType.FULL_TIME
    emp.hire_date = _NOW.date()
    emp.active = active
    emp.deactivated_at = None
    emp.deactivated_by = None
    emp.deactivation_reason = None
    return emp


# ─── Testes ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cancel_work_order_happy_path():
    """(T1) cancel_work_order: happy path → status=CANCELLED + audit + outbox emit."""
    session = _FakeSession()
    order = _make_order()
    of_id = order.id

    session.push_result(order)

    with patch("src.master_data.services.cancel_service.get_trace_id", return_value="trace-001"):
        result = await cancel_work_order(
            session,
            of_id=of_id,
            reason="Cliente cancelou a encomenda de evento",
            tenant_id=TENANT_ID,
            user_id="user-test",
        )

    assert result.success is True
    assert result.entity_id == str(of_id)
    assert result.action == "cancel_work_order"
    assert order.status == OrderStatus.CANCELLED
    assert order.cancelled_by == "user-test"
    assert order.cancellation_reason == "Cliente cancelou a encomenda de evento"
    assert order.cancelled_at is not None

    # Audit + outbox foram adicionados à session
    from src.core.models.audit import AuditLog
    from src.shared.outbox_models import EventOutbox

    audit_rows = session.get_added_type(AuditLog)
    outbox_rows = session.get_added_type(EventOutbox)
    assert len(audit_rows) == 1
    assert audit_rows[0].reason == "cancel_work_order"
    assert len(outbox_rows) == 1
    assert outbox_rows[0].event_type == "production_order.cancelled"


@pytest.mark.asyncio
async def test_cancel_work_order_not_found():
    """(T2) cancel_work_order OF inexistente → LookupError."""
    session = _FakeSession()
    session.push_result(None)  # execute retorna None

    with pytest.raises(LookupError, match="não encontrada"):
        await cancel_work_order(
            session,
            of_id=uuid4(),
            reason="Razão de cancelamento longa o suficiente",
            tenant_id=TENANT_ID,
            user_id="user-test",
        )


@pytest.mark.asyncio
async def test_cancel_work_order_already_cancelled():
    """(T3) cancel_work_order já cancelada → ValueError (409 semântico)."""
    session = _FakeSession()
    order = _make_order(status=OrderStatus.CANCELLED)
    session.push_result(order)

    with pytest.raises(ValueError, match="já está cancelada"):
        await cancel_work_order(
            session,
            of_id=order.id,
            reason="Tentativa de cancelar novamente",
            tenant_id=TENANT_ID,
            user_id="user-test",
        )


@pytest.mark.asyncio
async def test_cancel_encomenda_happy_path():
    """(T4) cancel_encomenda happy path → success=True + audit + outbox emit."""
    session = _FakeSession()
    session.push_result(None)  # sem duplicado

    with patch("src.master_data.services.cancel_service.get_trace_id", return_value="trace-002"):
        result = await cancel_encomenda(
            session,
            encomenda_id="ENC-2026-001",
            reason="Cliente desistiu da encomenda por motivos financeiros",
            tenant_id=TENANT_ID,
            user_id="user-test",
        )

    assert result.success is True
    assert result.entity_id == "ENC-2026-001"
    assert result.action == "cancel_encomenda"

    from src.core.models.audit import AuditLog
    from src.shared.outbox_models import EventOutbox

    audit_rows = session.get_added_type(AuditLog)
    outbox_rows = session.get_added_type(EventOutbox)
    encomenda_rows = session.get_added_type(EncomendaCancelled)

    assert len(encomenda_rows) == 1
    assert encomenda_rows[0].encomenda_id == "ENC-2026-001"
    assert len(audit_rows) == 1
    assert audit_rows[0].reason == "cancel_encomenda"
    assert len(outbox_rows) == 1
    assert outbox_rows[0].event_type == "encomenda.cancelled"


@pytest.mark.asyncio
async def test_retire_boat_happy_path():
    """(T5) retire_boat happy path → retired_at populado + audit + outbox emit."""
    session = _FakeSession()
    product = _make_product()
    session.push_result(product)

    result = await retire_boat(
        session,
        boat_id=product.id,
        reason="Modelo descontinuado por decisão de produto",
        tenant_id=TENANT_ID,
        user_id="user-test",
    )

    assert result.success is True
    assert result.entity_id == str(product.id)
    assert product.status == ProductStatus.INACTIVE
    assert product.retired_at is not None
    assert product.retired_by == "user-test"

    from src.core.models.audit import AuditLog
    from src.shared.outbox_models import EventOutbox

    assert len(session.get_added_type(AuditLog)) == 1
    outbox = session.get_added_type(EventOutbox)
    assert len(outbox) == 1
    assert outbox[0].event_type == "product.retired"


@pytest.mark.asyncio
async def test_retire_boat_not_found():
    """(T6) retire_boat inexistente → LookupError."""
    session = _FakeSession()
    session.push_result(None)

    with pytest.raises(LookupError, match="não encontrado"):
        await retire_boat(
            session,
            boat_id=uuid4(),
            reason="Modelo que não existe no sistema de produção",
            tenant_id=TENANT_ID,
            user_id="user-test",
        )


@pytest.mark.asyncio
async def test_deactivate_employee_with_future_ops():
    """(T7) deactivate_employee com ops futuras → warning + replan_needed no payload."""
    from src.hr.models.worker_phase_assignment import WorkerPhaseAssignment

    session = _FakeSession()
    emp = _make_employee()

    # 1ª execute: busca employee; 2ª execute: lista de ops futuras (3 ops)
    session.push_result(emp)

    wpa1 = WorkerPhaseAssignment()
    wpa1.worker_id = emp.id
    wpa2 = WorkerPhaseAssignment()
    wpa2.worker_id = emp.id
    wpa3 = WorkerPhaseAssignment()
    wpa3.worker_id = emp.id

    session.push_result([wpa1, wpa2, wpa3])

    result = await deactivate_employee(
        session,
        employee_id=emp.id,
        reason="Operador rescindiu contrato por vontade própria",
        tenant_id=TENANT_ID,
        user_id="user-test",
    )

    assert result.success is True
    assert result.warning is not None
    assert "3" in result.warning
    assert "replan" in result.warning.lower()

    from src.shared.outbox_models import EventOutbox

    outbox = session.get_added_type(EventOutbox)
    assert len(outbox) == 1
    assert outbox[0].payload["replan_needed"] is True
    assert outbox[0].payload["future_ops_count"] == 3


@pytest.mark.asyncio
async def test_deactivate_employee_active_false():
    """(T8) deactivate_employee → employee.active=False + status=TERMINATED."""
    session = _FakeSession()
    emp = _make_employee()
    session.push_result(emp)
    session.push_result([])  # sem ops futuras

    await deactivate_employee(
        session,
        employee_id=emp.id,
        reason="Operador rescindiu contrato por vontade própria",
        tenant_id=TENANT_ID,
        user_id="user-test",
    )

    assert emp.active is False
    assert emp.status == EmploymentStatus.TERMINATED
    assert emp.deactivated_by == "user-test"
    assert emp.deactivated_at is not None


def test_cancel_body_reason_too_short():
    """(T9) reason muito curta (<10c) → ValidationError do Pydantic."""
    from src.master_data.api.cancel import CancelBody

    with pytest.raises(ValidationError):
        CancelBody(reason="curta")

    # Razão com exactamente 10 caracteres deve passar
    body = CancelBody(reason="1234567890")
    assert body.reason == "1234567890"


def test_rbac_dependency_declared_on_router():
    """(T10) Verifica que todos os 4 endpoints declaram _require_master_write.

    Confirma que a PermissionDependency(MASTER_DATA_WRITE) está wired
    nos routes — sem precisar de DB real.
    """
    from fastapi import Depends
    from src.master_data.api.cancel import router, _require_master_write

    # Recolhe todos os routes e verifica que têm a dependency injectada
    cancel_routes = [r for r in router.routes if hasattr(r, "dependencies")]
    assert len(cancel_routes) == 4, "Devem existir exactamente 4 endpoints de cancel"

    for route in cancel_routes:
        dep_calls = [d.dependency for d in route.dependencies]
        assert _require_master_write in dep_calls, (
            f"Endpoint {route.path} não tem _require_master_write declarado"
        )


@pytest.mark.asyncio
async def test_audit_log_written_per_action():
    """(T11) Cada acção escreve linha audit com reason correcto."""
    from src.core.models.audit import AuditLog

    # cancel_work_order
    session = _FakeSession()
    order = _make_order()
    session.push_result(order)
    await cancel_work_order(
        session,
        of_id=order.id,
        reason="Audit log test — cancelamento confirmado",
        tenant_id=TENANT_ID,
        user_id="audit-tester",
    )
    audit_rows = session.get_added_type(AuditLog)
    assert any(r.reason == "cancel_work_order" for r in audit_rows)

    # retire_boat
    session2 = _FakeSession()
    product = _make_product()
    session2.push_result(product)
    await retire_boat(
        session2,
        boat_id=product.id,
        reason="Audit log test — retirada confirmada",
        tenant_id=TENANT_ID,
        user_id="audit-tester",
    )
    audit_rows2 = session2.get_added_type(AuditLog)
    assert any(r.reason == "retire_boat" for r in audit_rows2)

    # cancel_encomenda
    session3 = _FakeSession()
    session3.push_result(None)  # sem duplicado
    await cancel_encomenda(
        session3,
        encomenda_id="ENC-AUDIT-001",
        reason="Audit log test — encomenda cancelada",
        tenant_id=TENANT_ID,
        user_id="audit-tester",
    )
    audit_rows3 = session3.get_added_type(AuditLog)
    assert any(r.reason == "cancel_encomenda" for r in audit_rows3)
