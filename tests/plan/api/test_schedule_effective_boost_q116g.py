"""Q.116.G — `_attach_effective_boost` enriquece operations com effective_boost.

A função vive em `src/plan/api/_cpo_common.py` e é chamada por
`src/plan/cpo/scheduler_run.py` *após* o commit ser gravado (para o hash
ficar determinístico). Cada op no payload recebe `effective_boost: int`
calculado a partir do stack (cliente + encomenda + barco).

Estes testes cobrem o helper isoladamente — testar o pipeline CPO+commit
inteiro precisava de FactoryState completo + ML wiring, o que está fora
do escopo deste sub-sprint (Q.116.G é só expor um campo).
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Dict, List
from uuid import uuid4

import pytest

from src.plan.api._cpo_common import _attach_effective_boost
from tests.conftest import FakeSession, TEST_TENANT_ID


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _po(legacy_id: int, product_name: str, customer_name: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        tenant_id=TEST_TENANT_ID,
        legacy_id=legacy_id,
        product_name=product_name,
        customer_name=customer_name,
    )


def _order_boost(work_order_id: int, boost: int) -> SimpleNamespace:
    return SimpleNamespace(
        work_order_id=work_order_id,
        tenant_id=TEST_TENANT_ID,
        boost=boost,
        reason="teste",
        updated_by="luis",
        updated_at=datetime.now(timezone.utc),
    )


def _boat_boost(boat_id: str, boost: int) -> SimpleNamespace:
    return SimpleNamespace(
        tenant_id=TEST_TENANT_ID,
        boat_id=boat_id,
        boost=boost,
        reason="teste",
        updated_by="luis",
        updated_at=datetime.now(timezone.utc),
    )


def _customer(name: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        tenant_id=TEST_TENANT_ID,
        customer_name=name,
        customer_code="ACME",
        segment="RETAIL",
        payment_terms="NET30",
        price_tier="STANDARD",
        credit_limit=None,
        contact_name=None,
        contact_email=None,
        contact_phone=None,
        address_line1=None,
        address_line2=None,
        city=None,
        postal_code=None,
        country=None,
        is_active=True,
        notes=None,
    )


def _client_priority(client_id, priority: int) -> SimpleNamespace:
    return SimpleNamespace(
        client_id=client_id,
        tenant_id=TEST_TENANT_ID,
        priority=priority,
        reason=None,
        updated_at=datetime.now(timezone.utc),
        updated_by="luis",
    )


# ─── Tests ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_attach_effective_boost_empty_list_is_noop():
    """Lista vazia → não chama o DB nem altera nada."""
    session = FakeSession()
    ops: List[Dict[str, Any]] = []
    await _attach_effective_boost(session, TEST_TENANT_ID, ops)
    assert ops == []


@pytest.mark.asyncio
async def test_attach_effective_boost_full_stack():
    """Cada op recebe effective_boost = client + order + boat (capped 200)."""
    session = FakeSession()
    ops = [
        {"operation_id": "1001::laminagem", "order_id": "1001", "phase_id": "laminagem"},
        {"operation_id": "1002::cura", "order_id": "1002", "phase_id": "cura"},
    ]

    customer_a = _customer("Cliente A")
    customer_b = _customer("Cliente B")

    # Sequência de execute() em _attach_effective_boost:
    # 1. ProductionOrder batch → scalars().all()
    # 2. OrderBoost batch → scalars().all()
    # 3. BoatBoost batch → scalars().all() (product_names não-vazio)
    # 4. Customer batch → scalars().all()
    # 5. ClientPriority batch → scalars().all()

    session.queue_scalar(None)
    session.queue_scalars([
        _po(1001, "K1-Vanquish-L", customer_name="Cliente A"),
        _po(1002, "C1-Vibe-L", customer_name="Cliente B"),
    ])
    session.queue_scalar(None)
    session.queue_scalars([
        _order_boost(1001, 30),  # +30
        _order_boost(1002, 50),  # +50
    ])
    session.queue_scalar(None)
    session.queue_scalars([
        _boat_boost("K1-Vanquish-L", 20),  # 1001 +20
        _boat_boost("C1-Vibe-L", 10),  # 1002 +10
    ])
    session.queue_scalar(None)
    session.queue_scalars([customer_a, customer_b])
    session.queue_scalar(None)
    session.queue_scalars([
        _client_priority(customer_a.id, 1),  # priority 1 → 100
        _client_priority(customer_b.id, 3),  # priority 3 → 60
    ])

    await _attach_effective_boost(session, TEST_TENANT_ID, ops)

    # 1001: 100 (client) + 30 (order) + 20 (boat) = 150
    # 1002: 60 (client) + 50 (order) + 10 (boat) = 120
    assert ops[0]["effective_boost"] == 150
    assert ops[1]["effective_boost"] == 120


@pytest.mark.asyncio
async def test_attach_effective_boost_missing_order_defaults_zero():
    """op com order_id sem ProductionOrder correspondente → effective_boost=0."""
    session = FakeSession()
    ops = [
        {"operation_id": "9999::pintura", "order_id": "9999"},
    ]

    # ProductionOrder batch — vazio (legacy_id 9999 não existe).
    session.queue_scalar(None)
    session.queue_scalars([])
    # OrderBoost — vazio.
    session.queue_scalar(None)
    session.queue_scalars([])
    # product_names vazio → BoatBoost branch saltado.
    # customer_names vazio → Customer/ClientPriority branch saltado.

    await _attach_effective_boost(session, TEST_TENANT_ID, ops)
    assert ops[0]["effective_boost"] == 0


@pytest.mark.asyncio
async def test_attach_effective_boost_non_numeric_order_id_safe():
    """order_id não-numérico não derruba — fica com effective_boost=0."""
    session = FakeSession()
    ops = [
        {"operation_id": "abc::laminagem", "order_id": "not-a-number"},
        {"operation_id": "2001::cura", "order_id": "2001"},
    ]
    session.queue_scalar(None)
    session.queue_scalars([_po(2001, "K1-Vanquish-L")])
    session.queue_scalar(None)
    session.queue_scalars([_order_boost(2001, 40)])
    session.queue_scalar(None)
    session.queue_scalars([])  # BoatBoost vazio
    # Customer/ClientPriority — sem customer_names, branch saltado.

    await _attach_effective_boost(session, TEST_TENANT_ID, ops)
    # "not-a-number" → 0
    assert ops[0]["effective_boost"] == 0
    # 2001: só order_boost (40), sem cliente ou barco.
    assert ops[1]["effective_boost"] == 40


@pytest.mark.asyncio
async def test_attach_effective_boost_cap_at_200():
    """Soma > 200 é capped a 200 via compute_effective_boost."""
    session = FakeSession()
    ops = [{"operation_id": "3001::p1", "order_id": "3001"}]

    customer = _customer("Mega Cliente")

    session.queue_scalar(None)
    session.queue_scalars([_po(3001, "K1-Vanquish-L", customer_name="Mega Cliente")])
    session.queue_scalar(None)
    session.queue_scalars([_order_boost(3001, 100)])  # max
    session.queue_scalar(None)
    session.queue_scalars([_boat_boost("K1-Vanquish-L", 100)])  # max
    session.queue_scalar(None)
    session.queue_scalars([customer])
    session.queue_scalar(None)
    session.queue_scalars([_client_priority(customer.id, 1)])  # 100

    await _attach_effective_boost(session, TEST_TENANT_ID, ops)
    # 100 + 100 + 100 = 300 → capped a 200.
    assert ops[0]["effective_boost"] == 200
