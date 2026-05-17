"""Q.31.D.2 — atribuição diária de operadores por drag-drop.

O frontend arrasta operador → barco; o backend resolve a operação
concreta a partir da `ProductionSchedule` (a fase agendada que cobre o
dia, menor `operation_sequence`) e cria a `HRAllocation`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from src.hr.api.allocations import DailyAllocationRequest, create_daily_allocation
from src.hr.models.allocation import AllocationStatus
from src.hr.services.allocation_service import AllocationService
from src.plan.models.schedule import ProductionSchedule

TENANT = UUID("00000000-0000-0000-0000-000000000001")
OTHER_TENANT = UUID("00000000-0000-0000-0000-000000000002")


@pytest.fixture(autouse=True)
def _no_kafka(monkeypatch):
    """O serviço publica EMPLOYEE_ALLOCATED — sem broker nos unit tests."""
    async def _noop(*_a, **_k):
        return True

    monkeypatch.setattr(
        "src.hr.services.allocation_service.publish_event", _noop
    )


def _schedule(operation_id: UUID, sequence: int) -> ProductionSchedule:
    return ProductionSchedule(
        id=uuid4(),
        tenant_id=TENANT,
        order_id="4272",
        product_id=uuid4(),
        quantity=Decimal("1"),
        operation_id=operation_id,
        operation_sequence=sequence,
        scheduled_start_date=date(2026, 5, 17),
        scheduled_end_date=date(2026, 5, 20),
        scheduled_duration_hours=Decimal("8"),
    )


@pytest.mark.asyncio
async def test_create_single_allocation_resolves_operation(fake_session):
    emp = uuid4()
    op_a, op_b = uuid4(), uuid4()
    # Acabamento agendado para 2026-05-18 — duas fases, escolhe a 1ª.
    fake_session.queue_scalars([_schedule(op_a, 1), _schedule(op_b, 2)])
    fake_session.queue_scalars([Decimal("15.50")])  # taxa horária

    service = AllocationService(fake_session, TENANT)
    allocation = await service.create_single_allocation(
        employee_id=emp,
        order_id="4272",
        allocation_date=date(2026, 5, 18),
        allocated_hours=Decimal("8"),
    )

    assert allocation.operation_id == op_a
    assert allocation.employee_id == emp
    assert allocation.order_id == "4272"
    assert allocation.tenant_id == TENANT
    assert allocation.status == AllocationStatus.PLANNED
    assert allocation.hourly_rate == Decimal("15.50")
    assert allocation.estimated_cost == Decimal("124.00")  # 8 × 15.50
    assert allocation in fake_session.added
    assert fake_session.flush_calls == 1


@pytest.mark.asyncio
async def test_create_single_allocation_zero_rate_when_unpriced(fake_session):
    """Operador sem taxa em core.labor_rates → custo 0, nunca inventado."""
    fake_session.queue_scalars([_schedule(uuid4(), 1)])
    fake_session.queue_scalars([])  # sem LaborRate

    service = AllocationService(fake_session, TENANT)
    allocation = await service.create_single_allocation(
        employee_id=uuid4(),
        order_id="4272",
        allocation_date=date(2026, 5, 18),
    )

    assert allocation.hourly_rate == Decimal("0")
    assert allocation.estimated_cost == Decimal("0")


@pytest.mark.asyncio
async def test_create_single_allocation_without_schedule_raises(fake_session):
    """Sem fase agendada para o dia não há operation_id — ValueError."""
    fake_session.queue_scalars([])  # nenhuma ProductionSchedule

    service = AllocationService(fake_session, TENANT)
    with pytest.raises(ValueError, match="Sem operação agendada"):
        await service.create_single_allocation(
            employee_id=uuid4(),
            order_id="9999",
            allocation_date=date(2026, 5, 18),
        )


@pytest.mark.asyncio
async def test_daily_endpoint_returns_payload(fake_session):
    op = uuid4()
    fake_session.queue_scalars([_schedule(op, 1)])
    fake_session.queue_scalars([Decimal("12")])

    out = await create_daily_allocation(
        request=DailyAllocationRequest(
            employee_id=uuid4(),
            order_id="4272",
            allocation_date=date(2026, 5, 18),
            allocated_hours=8.0,
        ),
        tenant_id=TENANT,
        session=fake_session,
    )

    assert out.order_id == "4272"
    assert out.operation_id == str(op)
    assert out.status == "PLANNED"
    assert out.allocated_hours == 8.0
    assert fake_session.commit_calls == 1


@pytest.mark.asyncio
async def test_daily_endpoint_unknown_order_is_409(fake_session):
    from fastapi import HTTPException

    fake_session.queue_scalars([])  # sem schedule

    with pytest.raises(HTTPException) as exc:
        await create_daily_allocation(
            request=DailyAllocationRequest(
                employee_id=uuid4(),
                order_id="9999",
                allocation_date=date(2026, 5, 18),
            ),
            tenant_id=TENANT,
            session=fake_session,
        )
    assert exc.value.status_code == 409
    assert fake_session.commit_calls == 0
