"""Q.31.E — GET /v1/plan/transport/batches/{id}/manifest.

O documento de expedição: junta os dados da batch com a lista de barcos
atribuídos, para o frontend imprimir como manifesto/packing-list.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

import pytest

from src.plan.api.transport import batch_manifest
from src.plan.models.order import OrderStatus, ProductionOrder
from src.plan.models.transport import TransportBatch
from src.plan.services.transport_batch_service import (
    TransportBatchNotFoundError,
    TransportBatchService,
)

TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _batch() -> TransportBatch:
    return TransportBatch(
        id=uuid4(),
        tenant_id=TENANT,
        code="EXP-2026-05-20",
        transport_date=date(2026, 5, 20),
        destination="França — Lyon",
        status="OPEN",
        truck_capacity_units=6,
    )


def _order(hull: int) -> ProductionOrder:
    return ProductionOrder(
        id=uuid4(),
        tenant_id=TENANT,
        legacy_id=hull,
        product_name=f"K1 Vanquish {hull}",
        product_type="K1",
        current_phase_name="Acabamento",
        status=OrderStatus.IN_PROGRESS,
    )


@pytest.mark.asyncio
async def test_manifest_lists_batch_and_boats(monkeypatch, fake_session):
    batch = _batch()
    o1, o2 = _order(4272), _order(4271)

    async def _fake_get_batch(self, bid):
        return batch

    async def _fake_list_orders(self, bid):
        return [o1.id, o2.id]

    monkeypatch.setattr(TransportBatchService, "get_batch", _fake_get_batch)
    monkeypatch.setattr(TransportBatchService, "list_orders", _fake_list_orders)
    fake_session.queue_scalars([o1, o2])  # a query do manifesto

    out = await batch_manifest(
        batch_id=batch.id, tenant_id=TENANT, session=fake_session,
    )
    assert out["batch"]["code"] == "EXP-2026-05-20"
    assert out["batch"]["destination"] == "França — Lyon"
    assert out["boat_count"] == 2
    # ordenado por nº de casco
    assert [b["hull"] for b in out["boats"]] == [4271, 4272]
    assert out["boats"][0]["product_type"] == "K1"
    assert "generated_at" in out


@pytest.mark.asyncio
async def test_manifest_unknown_batch_is_404(monkeypatch, fake_session):
    from fastapi import HTTPException

    async def _raise(self, bid):
        raise TransportBatchNotFoundError("nope")

    monkeypatch.setattr(TransportBatchService, "get_batch", _raise)

    with pytest.raises(HTTPException) as exc:
        await batch_manifest(
            batch_id=uuid4(), tenant_id=TENANT, session=fake_session,
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_manifest_empty_batch_has_zero_boats(monkeypatch, fake_session):
    batch = _batch()

    async def _fake_get_batch(self, bid):
        return batch

    async def _fake_list_orders(self, bid):
        return []

    monkeypatch.setattr(TransportBatchService, "get_batch", _fake_get_batch)
    monkeypatch.setattr(TransportBatchService, "list_orders", _fake_list_orders)

    out = await batch_manifest(
        batch_id=batch.id, tenant_id=TENANT, session=fake_session,
    )
    assert out["boat_count"] == 0
    assert out["boats"] == []
