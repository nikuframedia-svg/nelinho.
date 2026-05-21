"""Q.68.4.E — `src/plan/services/transport_batch_service.py` a 40%. O
serviço alimenta o decoder com "quem viaja junto" — o fitness penaliza
batches espalhados (truck consolidation). Sem testes, qualquer regressão
ao `assign_order` (idempotência) ou `freeze`/`dispatch` (state machine)
silencia o sinal.

Testes:

* `create_batch()` → status='OPEN' + audit.
* `assign_order()` cria link novo + audita.
* `assign_order()` é idempotente (re-assign mesma ordem ao mesmo batch).
* `assign_order()` muda batch_id quando a ordem migra entre batches.
* `remove_order()` retorna True quando existe, False quando não.
* `freeze()` / `dispatch()` flipam status.
* `get_batch()` levanta TransportBatchNotFoundError quando não existe.
* `orders_by_batch()` agrega `{batch: [order, …]}`.
* `compute_truck_consolidation_penalty_h()` — invariante CEO Truck moda=26
  (12h tolerance + span shrunk to 0 quando 1 order).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from src.plan.models.transport import TransportBatch, TransportBatchAssignment
from src.plan.services.transport_batch_service import (
    TransportBatchNotFoundError,
    TransportBatchService,
    compute_truck_consolidation_penalty_h,
)


TENANT = UUID("11111111-1111-1111-1111-111111111111")


# ─── Helpers ──────────────────────────────────────────────────────────────


def _build_service(session) -> TransportBatchService:
    return TransportBatchService(session=session, tenant_id=TENANT)


def _batch(code: str = "B-1", status: str = "OPEN") -> TransportBatch:
    return TransportBatch(
        id=uuid4(),
        tenant_id=TENANT,
        code=code,
        transport_date=date.today() + timedelta(days=3),
        truck_capacity_units=50,
        priority=100,
        status=status,
    )


# ─── create_batch ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_batch_inserts_open_status(fake_session):
    svc = _build_service(fake_session)
    out = await svc.create_batch(
        code="TRK-A",
        transport_date=date.today() + timedelta(days=2),
        truck_capacity_units=42,
        priority=10,
        destination="Cliente X",
    )
    assert out.status == "OPEN"
    assert out.code == "TRK-A"
    assert out.truck_capacity_units == 42
    assert out.priority == 10
    types_added = [type(o).__name__ for o in fake_session.added]
    assert "TransportBatch" in types_added
    assert "AuditLog" in types_added


# ─── assign_order ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_assign_order_creates_new_link_when_absent(fake_session):
    fake_session.queue_scalar(None)
    svc = _build_service(fake_session)
    batch_id = uuid4()
    order_id = uuid4()
    link = await svc.assign_order(batch_id=batch_id, order_id=order_id)
    assert link.batch_id == batch_id
    assert link.order_id == order_id
    types_added = [type(o).__name__ for o in fake_session.added]
    assert "TransportBatchAssignment" in types_added
    assert "AuditLog" in types_added


@pytest.mark.asyncio
async def test_assign_order_idempotent_same_batch(fake_session):
    """Mesma ordem, mesmo batch → retorna o link existente sem novo INSERT."""
    batch_id = uuid4()
    order_id = uuid4()
    existing = TransportBatchAssignment(
        id=uuid4(),
        tenant_id=TENANT,
        batch_id=batch_id,
        order_id=order_id,
    )
    fake_session.queue_scalar(existing)
    svc = _build_service(fake_session)
    out = await svc.assign_order(batch_id=batch_id, order_id=order_id)
    assert out is existing
    # Nenhum INSERT novo.
    new_links = [o for o in fake_session.added if isinstance(o, TransportBatchAssignment)]
    assert new_links == []


@pytest.mark.asyncio
async def test_assign_order_reassigns_when_batch_differs(fake_session):
    """Ordem já noutro batch → muda `batch_id` no link existente sem
    duplicar."""
    old_batch = uuid4()
    new_batch = uuid4()
    order_id = uuid4()
    existing = TransportBatchAssignment(
        id=uuid4(),
        tenant_id=TENANT,
        batch_id=old_batch,
        order_id=order_id,
    )
    fake_session.queue_scalar(existing)
    svc = _build_service(fake_session)
    out = await svc.assign_order(batch_id=new_batch, order_id=order_id)
    assert out.batch_id == new_batch


# ─── remove_order ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_remove_order_returns_true_when_link_existed(fake_session):
    link = TransportBatchAssignment(
        id=uuid4(),
        tenant_id=TENANT,
        batch_id=uuid4(),
        order_id=uuid4(),
    )
    fake_session.queue_scalar(link)
    svc = _build_service(fake_session)
    out = await svc.remove_order(batch_id=link.batch_id, order_id=link.order_id)
    assert out is True
    assert link in fake_session.deleted


@pytest.mark.asyncio
async def test_remove_order_returns_false_when_no_link(fake_session):
    fake_session.queue_scalar(None)
    svc = _build_service(fake_session)
    out = await svc.remove_order(batch_id=uuid4(), order_id=uuid4())
    assert out is False


# ─── freeze / dispatch / get_batch ────────────────────────────────────────


@pytest.mark.asyncio
async def test_freeze_flips_status(fake_session):
    b = _batch(status="OPEN")
    fake_session.queue_scalar(b)
    svc = _build_service(fake_session)
    out = await svc.freeze(b.id)
    assert out.status == "FROZEN"


@pytest.mark.asyncio
async def test_dispatch_flips_status(fake_session):
    b = _batch(status="FROZEN")
    fake_session.queue_scalar(b)
    svc = _build_service(fake_session)
    out = await svc.dispatch(b.id)
    assert out.status == "DISPATCHED"


@pytest.mark.asyncio
async def test_get_batch_raises_when_absent(fake_session):
    fake_session.queue_scalar(None)
    svc = _build_service(fake_session)
    with pytest.raises(TransportBatchNotFoundError):
        await svc.get_batch(uuid4())


# ─── orders_by_batch + helpers ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_orders_by_batch_groups_assignments(fake_session):
    b1, b2 = uuid4(), uuid4()
    o1, o2, o3 = uuid4(), uuid4(), uuid4()
    rows = [
        TransportBatchAssignment(id=uuid4(), tenant_id=TENANT, batch_id=b1, order_id=o1),
        TransportBatchAssignment(id=uuid4(), tenant_id=TENANT, batch_id=b1, order_id=o2),
        TransportBatchAssignment(id=uuid4(), tenant_id=TENANT, batch_id=b2, order_id=o3),
    ]
    fake_session.queue_scalars(rows)
    svc = _build_service(fake_session)
    out = await svc.orders_by_batch()
    assert set(out.keys()) == {b1, b2}
    assert sorted(out[b1]) == sorted([o1, o2])
    assert out[b2] == [o3]


# ─── compute_truck_consolidation_penalty_h (invariante CEO) ───────────────


def test_consolidation_penalty_zero_when_one_order_per_batch():
    """1 ordem por batch → span=0 → penalidade=0 (nada para consolidar)."""
    finish = datetime(2026, 5, 1, 14, 0)
    ops_by_order = {"o1": [{"end": finish}]}
    orders_by_batch = {"B1": ["o1"]}
    pen = compute_truck_consolidation_penalty_h(ops_by_order, orders_by_batch)
    assert pen == 0.0


def test_consolidation_penalty_zero_within_tolerance():
    """Span < 12h tolerance → penalidade=0."""
    t1 = datetime(2026, 5, 1, 8, 0)
    t2 = datetime(2026, 5, 1, 14, 0)  # 6h depois
    ops_by_order = {"o1": [{"end": t1}], "o2": [{"end": t2}]}
    orders_by_batch = {"B1": ["o1", "o2"]}
    pen = compute_truck_consolidation_penalty_h(ops_by_order, orders_by_batch, tolerance_h=12)
    assert pen == 0.0


def test_consolidation_penalty_above_tolerance_accrues():
    """Span 20h, tolerância 12h → penalidade 8h."""
    t1 = datetime(2026, 5, 1, 0, 0)
    t2 = datetime(2026, 5, 1, 20, 0)
    ops_by_order = {"o1": [{"end": t1}], "o2": [{"end": t2}]}
    orders_by_batch = {"B1": ["o1", "o2"]}
    pen = compute_truck_consolidation_penalty_h(ops_by_order, orders_by_batch, tolerance_h=12)
    assert pen == pytest.approx(8.0)


def test_consolidation_penalty_empty_input():
    """Sem batches → 0.0."""
    assert compute_truck_consolidation_penalty_h({}, {}) == 0.0
