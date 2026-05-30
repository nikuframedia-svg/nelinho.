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

from datetime import date

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


def _make_boat_order(
    *,
    tenant_id: UUID = TENANT_ID,
    legacy_id: int = 101,
) -> ProductionOrder:
    """ProductionOrder com completed_date — convenção Q.115.X5 para 'barco'."""
    o = ProductionOrder()
    o.id = uuid4()
    o.tenant_id = tenant_id
    o.legacy_id = legacy_id
    o.product_name = "K1 Vanquish"
    o.product_type = "K1"
    o.current_phase_name = "ENTREGUE"
    o.status = OrderStatus.COMPLETED
    o.completed_date = date(2026, 5, 1)
    o.cancelled_at = None
    o.cancelled_by = None
    o.cancellation_reason = None
    return o


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
    of_id = str(order.legacy_id)  # legacy_id como a lista devolve

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
    assert result.entity_id == of_id
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
            of_id="9999",
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
            of_id=str(order.legacy_id),
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
    """(T5) retire_boat happy path → cancelled_at populado em ProductionOrder + audit + outbox emit."""
    session = _FakeSession()
    boat = _make_boat_order(legacy_id=101)
    session.push_result(boat)

    result = await retire_boat(
        session,
        boat_id="101",
        reason="Modelo descontinuado por decisão de produto",
        tenant_id=TENANT_ID,
        user_id="user-test",
    )

    assert result.success is True
    assert result.entity_id == "101"
    assert boat.status == OrderStatus.CANCELLED
    assert boat.cancelled_at is not None
    assert boat.cancelled_by == "user-test"
    assert boat.cancellation_reason == "Modelo descontinuado por decisão de produto"

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
            boat_id="9999",
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
        of_id=str(order.legacy_id),
        reason="Audit log test — cancelamento confirmado",
        tenant_id=TENANT_ID,
        user_id="audit-tester",
    )
    audit_rows = session.get_added_type(AuditLog)
    assert any(r.reason == "cancel_work_order" for r in audit_rows)

    # retire_boat
    session2 = _FakeSession()
    boat = _make_boat_order(legacy_id=202)
    session2.push_result(boat)
    await retire_boat(
        session2,
        boat_id="202",
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


# ─── Regressão Q.130.F — cancel OF por legacy_id ─────────────────────────────


@pytest.mark.asyncio
async def test_q130_f_cancel_work_order_by_legacy_id():
    """Q.130.F: cancel_work_order aceita legacy_id (string inteiro) como a lista devolve.

    Antes do fix a rota declarava UUID → FastAPI rejeitava com 422 porque a UI
    envia o legacy_id (ex: "42") que não é UUID válido.
    """
    session = _FakeSession()
    order = _make_order()
    assert order.legacy_id == 42  # confirmamos que é inteiro

    session.push_result(order)

    result = await cancel_work_order(
        session,
        of_id="42",  # legacy_id como a lista devolve — string inteiro
        reason="Q.130.F regressão — legacy_id aceite pelo serviço",
        tenant_id=TENANT_ID,
        user_id="user-q130f",
    )

    assert result.success is True
    assert result.entity_id == "42"
    assert order.status == OrderStatus.CANCELLED
    assert order.cancelled_by == "user-q130f"

    from src.core.models.audit import AuditLog
    from src.shared.outbox_models import EventOutbox

    assert len(session.get_added_type(AuditLog)) == 1
    outbox = session.get_added_type(EventOutbox)
    assert len(outbox) == 1
    assert outbox[0].payload["of_id"] == "42"


@pytest.mark.asyncio
async def test_q130_f_cancel_work_order_invalid_id_returns_lookup_error():
    """Q.130.F: of_id não inteiro → LookupError (mapeado para 404 no endpoint)."""
    session = _FakeSession()

    with pytest.raises(LookupError, match="não encontrada"):
        await cancel_work_order(
            session,
            of_id="nao-e-um-numero",
            reason="Q.130.F regressão — id inválido tratado",
            tenant_id=TENANT_ID,
            user_id="user-q130f",
        )


# ─── Regressão Q.130.G — retire boat por legacy_id de ProductionOrder ────────


@pytest.mark.asyncio
async def test_q130_g_retire_boat_by_legacy_id():
    """Q.130.G: retire_boat aceita legacy_id de ProductionOrder como a lista devolve.

    Antes do fix: rota declarava UUID + serviço consultava Product.id → duplo erro
    (422 da rota + 404 da entidade errada).
    """
    session = _FakeSession()
    boat = _make_boat_order(legacy_id=77)

    session.push_result(boat)

    result = await retire_boat(
        session,
        boat_id="77",  # legacy_id como a lista devolve
        reason="Q.130.G regressão — legacy_id e entidade correctos",
        tenant_id=TENANT_ID,
        user_id="user-q130g",
    )

    assert result.success is True
    assert result.entity_id == "77"
    assert boat.status == OrderStatus.CANCELLED
    assert boat.cancelled_at is not None
    assert boat.cancelled_by == "user-q130g"
    assert boat.cancellation_reason == "Q.130.G regressão — legacy_id e entidade correctos"

    from src.core.models.audit import AuditLog
    from src.shared.outbox_models import EventOutbox

    audit = session.get_added_type(AuditLog)
    assert len(audit) == 1
    assert audit[0].reason == "retire_boat"
    outbox = session.get_added_type(EventOutbox)
    assert len(outbox) == 1
    assert outbox[0].payload["boat_id"] == "77"


@pytest.mark.asyncio
async def test_q130_g_retire_boat_already_retired():
    """Q.130.G: barco já retirado (cancelled_at != None) → ValueError (409)."""
    session = _FakeSession()
    boat = _make_boat_order(legacy_id=88)
    boat.cancelled_at = _NOW  # já retirado

    session.push_result(boat)

    with pytest.raises(ValueError, match="já está retirado"):
        await retire_boat(
            session,
            boat_id="88",
            reason="Q.130.G regressão — dupla retirada bloqueada",
            tenant_id=TENANT_ID,
            user_id="user-q130g",
        )


@pytest.mark.asyncio
async def test_q130_g_retire_boat_invalid_id_returns_lookup_error():
    """Q.130.G: boat_id não inteiro → LookupError (mapeado para 404 no endpoint)."""
    session = _FakeSession()

    with pytest.raises(LookupError, match="não encontrado"):
        await retire_boat(
            session,
            boat_id="nao-e-um-numero",
            reason="Q.130.G regressão — id inválido tratado",
            tenant_id=TENANT_ID,
            user_id="user-q130g",
        )


# ─── Regressão FE-10/BE-6 — banner de replan ao desactivar operador ──────────


@pytest.mark.asyncio
async def test_fe10_be6_warning_ops_planeadas_com_ops():
    """FE-10/BE-6: deactivate_employee com 2 ops futuras → warning_ops_planeadas=2.

    Antes do fix: CancelResult/CancelOut não tinham o campo numérico →
    FE lia data.warning_ops_planeadas=undefined → banner nunca disparava.
    """
    from src.hr.models.worker_phase_assignment import WorkerPhaseAssignment

    session = _FakeSession()
    emp = _make_employee()
    session.push_result(emp)

    wpa1 = WorkerPhaseAssignment()
    wpa1.worker_id = emp.id
    wpa2 = WorkerPhaseAssignment()
    wpa2.worker_id = emp.id
    session.push_result([wpa1, wpa2])

    result = await deactivate_employee(
        session,
        employee_id=emp.id,
        reason="FE-10/BE-6 regressão — banner de replan",
        tenant_id=TENANT_ID,
        user_id="user-fe10",
    )

    assert result.warning_ops_planeadas == 2

    # Confirma que CancelOut propaga o campo
    from src.master_data.api.cancel import CancelOut
    out = CancelOut(
        entity_id=result.entity_id,
        action=result.action,
        cancelled_at=result.cancelled_at,
        audit_trace_id=result.audit_trace_id,
        warning=result.warning,
        warning_ops_planeadas=result.warning_ops_planeadas,
    )
    assert out.warning_ops_planeadas == 2


@pytest.mark.asyncio
async def test_fe10_be6_warning_ops_planeadas_sem_ops():
    """FE-10/BE-6: deactivate_employee sem ops futuras → warning_ops_planeadas=0."""
    session = _FakeSession()
    emp = _make_employee()
    session.push_result(emp)
    session.push_result([])  # sem ops futuras

    result = await deactivate_employee(
        session,
        employee_id=emp.id,
        reason="FE-10/BE-6 regressão — sem replan necessário",
        tenant_id=TENANT_ID,
        user_id="user-fe10",
    )

    assert result.warning_ops_planeadas == 0
    assert result.warning is None
