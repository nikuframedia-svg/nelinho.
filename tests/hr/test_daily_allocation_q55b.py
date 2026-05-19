"""Q.55.B — atribuição diária deixa de exigir um ProductionSchedule.

Antes: `create_single_allocation` levantava `ValueError` quando não havia
uma `ProductionSchedule` a cobrir o dia — e 0 das 164 ordens IN_PROGRESS
tinham uma. Resultado: clicar "Atribuir" em qualquer barco → 409 sempre.

Agora a operação resolve-se a partir da FASE ACTUAL da ordem, via
`OperationResolver` (get-or-create de `core.operations`). O schedule,
quando existe, continua a dar a operação mais precisa.

Mudança de contrato (intencional): "sem schedule" já NÃO é 409. As
recusas de negócio passam a ser: ordem inexistente / fase terminal → 409;
ordem ainda não arrancada (fase "Pendente") → 422.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from src.core.models.audit import AuditLog
from src.core.models.operation import Operation
from src.hr.api.allocations import DailyAllocationRequest, create_daily_allocation
from src.hr.services.allocation_service import (
    AllocationService,
    OrderNotAllocatableError,
    PhaseNotStartedError,
)
from src.plan.models.order import OrderStatus, ProductionOrder
from src.plan.services.operation_resolver import (
    OperationResolver,
    operation_code_for_phase,
)
from src.plan.services.phase_classification import is_workable_phase

TENANT = UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture(autouse=True)
def _no_kafka(monkeypatch):
    async def _noop(*_a, **_k):
        return True

    monkeypatch.setattr(
        "src.hr.services.allocation_service.publish_event", _noop
    )


def _order(phase: str) -> ProductionOrder:
    return ProductionOrder(
        id=uuid4(),
        tenant_id=TENANT,
        legacy_id=4272,
        product_name="K1 Vanquish",
        product_type="K1",
        current_phase_name=phase,
        status=OrderStatus.IN_PROGRESS,
    )


def _operation(code: str) -> Operation:
    return Operation(
        id=uuid4(),
        tenant_id=TENANT,
        operation_code=code,
        operation_name="Laminagem",
    )


def _feed(session, *rows) -> None:
    """Alinha a FakeSession — um `(scalar, scalars)` por `execute()`.

    Ordem das queries do serviço: load-order → resolve-schedule →
    [lookup de operação] → employee-rate.
    """
    for scalar, scalars in rows:
        session.queue_scalar(scalar)
        session.queue_scalars(scalars)


# ── Atribuição sem schedule ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_allocation_without_schedule_resolves_operation_from_phase(
    fake_session,
):
    """Ordem activa sem ProductionSchedule → atribui na mesma (já não 409)."""
    emp = uuid4()
    _feed(
        fake_session,
        (_order("Laminagem"), []),  # load-order
        (None, []),                 # resolve-schedule → nenhuma
        (None, []),                 # operation lookup → não existe
        (None, [Decimal("10")]),    # employee-rate
    )

    service = AllocationService(fake_session, TENANT)
    allocation = await service.create_single_allocation(
        employee_id=emp,
        order_id="4272",
        allocation_date=date(2026, 5, 19),
    )

    assert allocation.operation_id is not None
    assert allocation.employee_id == emp
    # A operação de routing foi criada lazy, com auditoria na mesma sessão.
    created_ops = [o for o in fake_session.added if isinstance(o, Operation)]
    audits = [a for a in fake_session.added if isinstance(a, AuditLog)]
    assert len(created_ops) == 1
    assert allocation.operation_id == created_ops[0].id
    assert any(a.entity_type == "operation" for a in audits)


@pytest.mark.asyncio
async def test_allocation_reuses_existing_phase_operation(fake_session):
    """Operação de routing já existe → reutiliza-a, não duplica."""
    existing = _operation(operation_code_for_phase("Laminagem"))
    _feed(
        fake_session,
        (_order("Laminagem"), []),  # load-order
        (None, []),                 # resolve-schedule → nenhuma
        (existing, []),             # operation lookup → existe
        (None, [Decimal("10")]),    # employee-rate
    )

    service = AllocationService(fake_session, TENANT)
    allocation = await service.create_single_allocation(
        employee_id=uuid4(),
        order_id="4272",
        allocation_date=date(2026, 5, 19),
    )

    assert allocation.operation_id == existing.id
    assert not [o for o in fake_session.added if isinstance(o, Operation)]


# ── OperationResolver ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_resolve_phase_operation_creates_operation_and_audit(fake_session):
    fake_session.queue_scalar(None)  # lookup → não existe

    resolver = OperationResolver(fake_session, TENANT)
    op = await resolver.resolve_phase_operation("Pintura Acabamento")

    assert isinstance(op, Operation)
    assert op.operation_code == operation_code_for_phase("Pintura Acabamento")
    assert op.operation_name == "Pintura Acabamento"
    assert op in fake_session.added
    audit = next(a for a in fake_session.added if isinstance(a, AuditLog))
    assert audit.entity_type == "operation"
    assert audit.action == "INSERT"
    assert audit.entity_id == op.id


@pytest.mark.asyncio
async def test_resolve_phase_operation_returns_existing_without_duplicate(
    fake_session,
):
    existing = _operation(operation_code_for_phase("Cura"))
    fake_session.queue_scalar(existing)  # lookup → encontra

    resolver = OperationResolver(fake_session, TENANT)
    op = await resolver.resolve_phase_operation("Cura")

    assert op is existing
    assert fake_session.added == []  # nada criado


def test_operation_code_for_phase_is_deterministic_and_bounded():
    code = operation_code_for_phase("Laminagem peças")

    assert code == operation_code_for_phase("Laminagem peças")  # determinístico
    assert code.startswith("PHASE_")
    assert len(code) <= 50
    # Sem acentos — "peças" e "pecas" dão o mesmo código.
    assert operation_code_for_phase("Laminagem peças") == operation_code_for_phase(
        "Laminagem pecas"
    )


# ── Recusas de negócio ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_allocation_terminal_phase_is_rejected(fake_session):
    """Barco já entregue → OrderNotAllocatableError (a API → 409)."""
    _feed(fake_session, (_order("Entregue"), []))

    service = AllocationService(fake_session, TENANT)
    with pytest.raises(OrderNotAllocatableError):
        await service.create_single_allocation(
            employee_id=uuid4(),
            order_id="4272",
            allocation_date=date(2026, 5, 19),
        )


@pytest.mark.asyncio
async def test_allocation_pending_phase_is_rejected(fake_session):
    """Ordem ainda não arrancou → PhaseNotStartedError (a API → 422)."""
    _feed(fake_session, (_order("Pendente"), []))

    service = AllocationService(fake_session, TENANT)
    with pytest.raises(PhaseNotStartedError):
        await service.create_single_allocation(
            employee_id=uuid4(),
            order_id="4272",
            allocation_date=date(2026, 5, 19),
        )


@pytest.mark.asyncio
async def test_daily_endpoint_pending_phase_is_422(fake_session):
    _feed(fake_session, (_order("Pendente"), []))

    with pytest.raises(HTTPException) as exc:
        await create_daily_allocation(
            request=DailyAllocationRequest(
                employee_id=uuid4(),
                order_id="4272",
                allocation_date=date(2026, 5, 19),
            ),
            tenant_id=TENANT,
            session=fake_session,
        )
    assert exc.value.status_code == 422
    assert fake_session.commit_calls == 0


@pytest.mark.asyncio
async def test_daily_endpoint_terminal_phase_is_409(fake_session):
    _feed(fake_session, (_order("Armazem"), []))

    with pytest.raises(HTTPException) as exc:
        await create_daily_allocation(
            request=DailyAllocationRequest(
                employee_id=uuid4(),
                order_id="4272",
                allocation_date=date(2026, 5, 19),
            ),
            tenant_id=TENANT,
            session=fake_session,
        )
    assert exc.value.status_code == 409
    assert fake_session.commit_calls == 0


# ── is_workable_phase ────────────────────────────────────────────────────


def test_is_workable_phase_true_for_shop_floor_phases():
    assert is_workable_phase("Laminagem")
    assert is_workable_phase("Pintura Acabamento")
    assert is_workable_phase("Cura")


def test_is_workable_phase_false_for_pending_terminal_and_empty():
    assert not is_workable_phase("Pendente")
    assert not is_workable_phase("Não Laminado")
    assert not is_workable_phase("Entregue")
    assert not is_workable_phase("")
    assert not is_workable_phase(None)
