"""
ProdPlan ONE — Transport batch state (Q.38.A)
==============================================

Testa o cálculo de `ready` / `in_prod` / `at_risk` no endpoint
`GET /v1/plan/transport/batches` (`src.plan.api.transport.list_batches`).

Q.38.A — `_batch_state_counts` separa ordens prontas (fase administrativa)
das que estão em produção, e marca em risco as não-prontas quando o
`transport_date` da batch está a ≤ 3 dias. O endpoint resolve as ordens de
cada batch via `transport_batch_assignment`.

Sem Postgres: `FakeSession` (de `tests/conftest.py`) com queue de scalars.
ZERO MOCKS de lógica de negócio — só o transporte de dados é fake.
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest

from src.plan.api.transport import _batch_state_counts, list_batches
from src.plan.models.order import OrderStatus, ProductionOrder
from src.plan.models.transport import TransportBatch, TransportBatchAssignment
from tests.conftest import TEST_TENANT_ID, FakeSession

TODAY = date.today()


# ---------------------------------------------------------------------------
# Builders DAMP — cada teste lê como spec independente
# ---------------------------------------------------------------------------

def _order(phase: str, transport_date: date | None = None) -> ProductionOrder:
    o = ProductionOrder()
    o.id = uuid4()
    o.tenant_id = TEST_TENANT_ID
    o.legacy_id = abs(hash((phase, str(transport_date), str(uuid4())))) % 1_000_000
    o.product_name = "Kayak Test"
    o.product_type = "K1"
    o.current_phase_name = phase
    o.transport_date = transport_date
    o.status = OrderStatus.IN_PROGRESS
    return o


def _batch(transport_date: date, code: str = "B-TEST") -> TransportBatch:
    b = TransportBatch()
    b.id = uuid4()
    b.tenant_id = TEST_TENANT_ID
    b.code = code
    b.transport_date = transport_date
    b.truck_capacity_units = 50
    b.priority = 100
    b.destination = "Vila do Conde"
    b.status = "OPEN"
    return b


def _assignment(batch_id, order_id) -> TransportBatchAssignment:
    a = TransportBatchAssignment()
    a.id = uuid4()
    a.tenant_id = TEST_TENANT_ID
    a.batch_id = batch_id
    a.order_id = order_id
    return a


# ===========================================================================
# Q.38.A — _batch_state_counts (função pura)
# ===========================================================================

def test_ready_counts_administrative_phases():
    """Ordens em fases administrativas contam como `ready`."""
    orders = [
        _order("Entregue"),
        _order("Armazem"),   # ERP grava sem acento
        _order("Embalado"),
    ]
    ready, in_prod, at_risk = _batch_state_counts(TODAY + timedelta(days=10), orders)
    assert ready == 3
    assert in_prod == 0
    assert at_risk == 0


def test_in_prod_counts_production_phases():
    """Ordens em fases de produção contam como `in_prod`, não `ready`."""
    orders = [
        _order("Laminagem"),
        _order("Acabamentos"),
    ]
    ready, in_prod, at_risk = _batch_state_counts(TODAY + timedelta(days=10), orders)
    assert ready == 0
    assert in_prod == 2
    # Data longe → sem risco.
    assert at_risk == 0


def test_at_risk_when_transport_within_three_days():
    """Ordens não-prontas ficam `at_risk` quando o transporte é ≤ 3 dias."""
    orders = [
        _order("Laminagem"),
        _order("Acabamentos"),
        _order("Entregue"),   # pronta — nunca em risco
    ]
    ready, in_prod, at_risk = _batch_state_counts(TODAY + timedelta(days=2), orders)
    assert ready == 1
    assert in_prod == 2
    assert at_risk == 2


def test_at_risk_zero_when_transport_far_off():
    """Transporte a > 3 dias → nenhuma ordem em risco."""
    orders = [_order("Laminagem"), _order("Acabamentos")]
    _, in_prod, at_risk = _batch_state_counts(TODAY + timedelta(days=7), orders)
    assert in_prod == 2
    assert at_risk == 0


def test_at_risk_includes_past_transport_dates():
    """Transporte já passado é, por maioria de razão, em risco."""
    orders = [_order("Laminagem")]
    _, _, at_risk = _batch_state_counts(TODAY - timedelta(days=1), orders)
    assert at_risk == 1


def test_at_risk_zero_without_transport_date():
    """Sem `transport_date` na batch não há risco calculável."""
    orders = [_order("Laminagem")]
    ready, in_prod, at_risk = _batch_state_counts(None, orders)
    assert in_prod == 1
    assert at_risk == 0


def test_unknown_phase_counts_as_in_prod():
    """Fase desconhecida é conservadora — conta como produção, não pronta."""
    orders = [_order("FaseInventada")]
    ready, in_prod, _ = _batch_state_counts(TODAY + timedelta(days=10), orders)
    assert ready == 0
    assert in_prod == 1


def test_empty_batch_is_all_zero():
    ready, in_prod, at_risk = _batch_state_counts(TODAY, [])
    assert (ready, in_prod, at_risk) == (0, 0, 0)


# ===========================================================================
# Q.38.A — endpoint list_batches com assignments explícitos
# ===========================================================================

@pytest.mark.asyncio
async def test_endpoint_counts_explicit_assignments():
    """Batch com linhas em transport_batch_assignment → contagens corretas."""
    batch_date = TODAY + timedelta(days=2)
    batch = _batch(batch_date)

    laminagem = _order("Laminagem")
    entregue = _order("Entregue")

    session = FakeSession()
    session.queue_scalars([batch])                          # svc.list_batches
    session.queue_scalars([                                 # svc.orders_by_batch
        _assignment(batch.id, laminagem.id),
        _assignment(batch.id, entregue.id),
    ])
    session.queue_scalars([laminagem, entregue])            # production_orders

    result = await list_batches(tenant_id=TEST_TENANT_ID, session=session)

    assert len(result) == 1
    out = result[0]
    assert out.assigned_orders_count == 2
    assert out.ready == 1      # Entregue
    assert out.in_prod == 1    # Laminagem
    assert out.at_risk == 1    # Laminagem, transporte a 2 dias


@pytest.mark.asyncio
async def test_endpoint_batch_without_assignments_is_zero():
    """Q.38.A — batch sem assignments explícitos → contagens a zero."""
    batch = _batch(TODAY + timedelta(days=1))

    session = FakeSession()
    session.queue_scalars([batch])   # svc.list_batches
    session.queue_scalars([])        # svc.orders_by_batch
    session.queue_scalars([_order("Laminagem")])  # production_orders

    result = await list_batches(tenant_id=TEST_TENANT_ID, session=session)

    out = result[0]
    assert out.assigned_orders_count == 0
    assert out.ready == 0
    assert out.in_prod == 0
    assert out.at_risk == 0
