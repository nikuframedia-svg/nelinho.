"""Q.143.A — `TransportBatchService.refresh_from_orders()`.

Deriva camiões reais a partir das `production_orders`:
  * cria um camião OPEN por `transport_date` futura e atribui as ordens dessa
    data até à capacidade (overflow contado, não atribuído);
  * **idempotente** — nunca reatribui uma ordem já colocada (preserva o
    drag-drop manual e corridas anteriores);
  * nunca toca em camiões FROZEN/DISPATCHED.

DAMP > DRY — cada teste lê como uma spec independente.
"""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from src.plan.models.order import OrderStatus, ProductionOrder
from src.plan.services.transport_batch_service import TransportBatchService

TENANT = UUID("00000000-0000-0000-0000-000000000001")
TODAY = date(2026, 6, 1)


def _order(transport_date: date) -> ProductionOrder:
    return ProductionOrder(
        id=uuid4(),
        tenant_id=TENANT,
        legacy_id=int(uuid4().int % 10_000_000),
        product_name="K1 Vanquish",
        product_type="K1",
        current_phase_name="Acabamento",
        transport_date=transport_date,
        status=OrderStatus.IN_PROGRESS,
    )


def _batch(transport_date: date, *, status: str = "OPEN", cap: int = 50):
    return SimpleNamespace(
        id=uuid4(),
        tenant_id=TENANT,
        code=f"SHP-{transport_date.isoformat()}",
        transport_date=transport_date,
        truck_capacity_units=cap,
        status=status,
    )


def _wire(
    svc: TransportBatchService,
    *,
    existing_batches=None,
    existing_assignments=None,
):
    """Substitui os métodos de query/mutação por fakes que registam chamadas."""
    created: list = []
    assigned: list = []  # (batch_id, order_id)
    batches = list(existing_batches or [])

    async def _orders_by_batch():
        return dict(existing_assignments or {})

    async def _list_batches(*, since=None, until=None, status=None):
        return list(batches)

    async def _create_batch(*, code, transport_date, truck_capacity_units=50,
                            priority=100, destination=None):
        b = _batch(transport_date, cap=truck_capacity_units)
        b.code = code
        created.append(b)
        batches.append(b)
        return b

    async def _assign_order(*, batch_id, order_id):
        assigned.append((batch_id, order_id))
        return SimpleNamespace(batch_id=batch_id, order_id=order_id)

    removed: list = []  # Q.173.W — (batch_id, order_id) largados

    async def _remove_order(*, batch_id, order_id):
        removed.append((batch_id, order_id))
        # reflete a remoção no mapa para o resto do fluxo
        ids = (existing_assignments or {}).get(batch_id)
        if ids and order_id in ids:
            ids.remove(order_id)
        return True

    svc.orders_by_batch = _orders_by_batch  # type: ignore[assignment]
    svc.list_batches = _list_batches  # type: ignore[assignment]
    svc.create_batch = _create_batch  # type: ignore[assignment]
    svc.assign_order = _assign_order  # type: ignore[assignment]
    svc.remove_order = _remove_order  # type: ignore[assignment]
    return created, assigned, removed


@pytest.mark.asyncio
async def test_creates_batch_and_assigns_up_to_capacity(fake_session):
    d = TODAY + timedelta(days=5)
    orders = [_order(d) for _ in range(3)]
    fake_session.queue_scalars(orders)  # o único select (ordens elegíveis)

    svc = TransportBatchService(fake_session, TENANT)
    created, assigned, _removed = _wire(svc)

    summary = await svc.refresh_from_orders(default_capacity=2, today=TODAY)

    assert summary["batches_created"] == 1
    assert summary["orders_assigned"] == 2  # cabem 2 de 3
    assert summary["overflow"] == 1
    assert len(created) == 1
    assert len(assigned) == 2


@pytest.mark.asyncio
async def test_idempotent_does_not_reassign_already_placed_orders(fake_session):
    """2ª corrida (ordens já atribuídas) → 0 novas atribuições, 0 camiões."""
    d = TODAY + timedelta(days=3)
    orders = [_order(d) for _ in range(2)]
    # Q.173.W — 2 selects: lookup do release (datas batem → 0 largadas) +
    # ordens elegíveis do fluxo principal.
    fake_session.queue_scalars(orders)
    fake_session.queue_scalars(orders)

    existing = _batch(d)
    # ambas as ordens já estão atribuídas a este camião
    assignments = {existing.id: [o.id for o in orders]}

    svc = TransportBatchService(fake_session, TENANT)
    created, assigned, _removed = _wire(
        svc, existing_batches=[existing], existing_assignments=assignments,
    )

    summary = await svc.refresh_from_orders(default_capacity=50, today=TODAY)

    assert summary["batches_created"] == 0
    assert summary["orders_assigned"] == 0
    assert assigned == []  # nada reatribuído — drag-drop manual preservado


@pytest.mark.asyncio
async def test_does_not_clobber_manual_move(fake_session):
    """Uma ordem movida à mão para OUTRO camião não volta para o do seu dia.

    Q.173.W — o drag manual SINCRONIZA a promessa da ordem com a data do
    camião (_sync_order_promise), por isso o release de obsoletos não a
    larga (datas batem) e o refresh não a reatribui (já colocada)."""
    d = TODAY + timedelta(days=4)
    o_moved, o_free = _order(d + timedelta(days=1)), _order(d)
    # 2 selects: lookup do release + elegíveis do fluxo principal.
    fake_session.queue_scalars([o_moved])
    fake_session.queue_scalars([o_moved, o_free])

    day_batch = _batch(d)
    other_batch = _batch(d + timedelta(days=1))
    # o_moved foi arrastado para other_batch; a promessa seguiu o camião
    assignments = {other_batch.id: [o_moved.id]}

    svc = TransportBatchService(fake_session, TENANT)
    created, assigned, removed = _wire(
        svc,
        existing_batches=[day_batch, other_batch],
        existing_assignments=assignments,
    )

    summary = await svc.refresh_from_orders(default_capacity=50, today=TODAY)

    assert summary["orders_assigned"] == 1  # só a livre
    assigned_ids = {oid for _, oid in assigned}
    assert o_moved.id not in assigned_ids
    assert o_free.id in assigned_ids


@pytest.mark.asyncio
async def test_skips_frozen_batch(fake_session):
    d = TODAY + timedelta(days=6)
    orders = [_order(d) for _ in range(2)]
    fake_session.queue_scalars(orders)

    frozen = _batch(d, status="FROZEN")

    svc = TransportBatchService(fake_session, TENANT)
    created, assigned, _removed = _wire(svc, existing_batches=[frozen])

    summary = await svc.refresh_from_orders(default_capacity=50, today=TODAY)

    assert summary["batches_created"] == 0
    assert summary["orders_assigned"] == 0
    assert assigned == []


@pytest.mark.asyncio
async def test_one_batch_per_distinct_date(fake_session):
    d1 = TODAY + timedelta(days=2)
    d2 = TODAY + timedelta(days=9)
    orders = [_order(d1), _order(d1), _order(d2)]
    fake_session.queue_scalars(orders)

    svc = TransportBatchService(fake_session, TENANT)
    created, assigned, _removed = _wire(svc)

    summary = await svc.refresh_from_orders(default_capacity=50, today=TODAY)

    assert summary["batches_created"] == 2
    assert summary["orders_assigned"] == 3
    assert {b.transport_date for b in created} == {d1, d2}


@pytest.mark.asyncio
async def test_q173w_release_de_assignments_obsoletos(fake_session):
    """Q.173.W — promessa mudou no ERP → o camião antigo larga a ordem e o
    refresh coloca-a no camião da data nova. Era o camião SHP-2026-06-19
    com 45/50 assignments de datas já mudadas (auditoria 2026-06-11)."""
    d_old, d_new = TODAY + timedelta(days=2), TODAY + timedelta(days=9)
    o = _order(d_new)  # a promessa atual é d_new
    fake_session.queue_scalars([o])       # lookup do release
    fake_session.queue_scalars([o])       # elegíveis do fluxo principal

    old_batch = _batch(d_old)
    assignments = {old_batch.id: [o.id]}  # ...mas está presa ao camião antigo

    svc = TransportBatchService(fake_session, TENANT)
    created, assigned, removed = _wire(
        svc, existing_batches=[old_batch], existing_assignments=assignments,
    )

    summary = await svc.refresh_from_orders(default_capacity=50, today=TODAY)

    assert summary["orders_released"] == 1
    assert removed == [(old_batch.id, o.id)]
    # re-colocada no camião da data NOVA (criado pelo refresh)
    assert summary["orders_assigned"] == 1
    assert any(b.transport_date == d_new for b in created)
