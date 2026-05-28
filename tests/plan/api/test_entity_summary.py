"""Q.116.A — tests for /v1/entity/* endpoints.

Cada endpoint cobre 3 cenários:
  1. Happy path — entidade existe, dados secundários presentes.
  2. 404 — entidade principal não existe.
  3. Sem dados secundários — entidade existe mas listas vazias (não 404).

Strategy: FastAPI TestClient + FakeSession (tests/conftest.py). Override
require_tenant_header + get_session. Não toca DB real.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, List, Optional
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.plan.api.entity_summary import router as entity_router
from src.plan.models.order import OrderStatus
from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session
from tests.conftest import FakeSession, TEST_TENANT_ID

_TENANT = str(TEST_TENANT_ID)
_HEADERS = {"X-Tenant-Id": _TENANT}


# ─── App factory ─────────────────────────────────────────────────────────────


def _minimal_app(session: FakeSession) -> TestClient:
    app = FastAPI()
    app.include_router(entity_router)

    async def _s():
        yield session

    app.dependency_overrides[get_session] = _s
    app.dependency_overrides[require_tenant_header] = lambda: TEST_TENANT_ID
    return TestClient(app, raise_server_exceptions=True)


# ─── Helpers ─────────────────────────────────────────────────────────────────


_UNSET = object()


def _order(
    *,
    legacy_id: int = 1001,
    product_name: str = "K1-Vanquish-L",
    product_type: Optional[str] = "K1",
    current_phase_name: str = "Laminagem",
    status_: OrderStatus = OrderStatus.IN_PROGRESS,
    created_date: Any = _UNSET,
    transport_date: Optional[date] = None,
    completed_date: Optional[date] = None,
    customer_name: Optional[str] = None,
) -> SimpleNamespace:
    cd = date(2026, 1, 1) if created_date is _UNSET else created_date
    return SimpleNamespace(
        id=uuid4(),
        tenant_id=TEST_TENANT_ID,
        legacy_id=legacy_id,
        product_id=None,
        product_name=product_name,
        product_type=product_type,
        current_phase_id=None,
        current_phase_name=current_phase_name,
        created_date=cd,
        transport_date=transport_date,
        completed_date=completed_date,
        status=status_,
        cancelled_at=None,
        cancelled_by=None,
        cancellation_reason=None,
        customer_name=customer_name,
    )


def _customer(
    *,
    id_: Optional[UUID] = None,
    customer_name: str = "Acme Náutica",
    customer_code: str = "ACME-01",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id_ or uuid4(),
        tenant_id=TEST_TENANT_ID,
        customer_code=customer_code,
        customer_name=customer_name,
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


def _client_priority(*, client_id: UUID, priority: int = 2) -> SimpleNamespace:
    return SimpleNamespace(
        client_id=client_id,
        tenant_id=TEST_TENANT_ID,
        priority=priority,
        reason=None,
        updated_at=datetime.now(timezone.utc),
        updated_by="operador_teste",
    )


def _affinity(
    *,
    phase_id: str = "laminagem",
    operator_id: Optional[UUID] = None,
    score: float = 0.85,
    sample_count: int = 12,
) -> SimpleNamespace:
    return SimpleNamespace(
        tenant_id=TEST_TENANT_ID,
        operator_id=operator_id or uuid4(),
        phase_id=phase_id,
        score=score,
        sample_count=sample_count,
        last_computed_at=datetime.now(timezone.utc),
    )


def _employee(*, id_: UUID, name: str = "João Operador") -> SimpleNamespace:
    return SimpleNamespace(
        id=id_,
        tenant_id=TEST_TENANT_ID,
        employee_code="OP-01",
        employee_name=name,
    )


def _boat_score(
    *,
    boat_id: str = "K1-Vanquish-L",
    phase_id: str = "laminagem",
    score: float = 0.45,
    sample_count: int = 8,
) -> SimpleNamespace:
    return SimpleNamespace(
        tenant_id=TEST_TENANT_ID,
        boat_id=boat_id,
        phase_id=phase_id,
        score=score,
        sample_count=sample_count,
        last_computed_at=datetime.now(timezone.utc),
    )


def _template(
    *,
    id_: Optional[UUID] = None,
    code: str = "ROUTING-0001",
    name: str = "Rota K1 Standard",
    phase_count: int = 2,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id_ or uuid4(),
        tenant_id=TEST_TENANT_ID,
        code=code,
        name=name,
        description=None,
        phase_count=phase_count,
        active=True,
        model_coverage=100,
    )


def _template_phase(
    *,
    template_id: UUID,
    seq: int,
    phase_id: str,
    phase_name: str,
    duration_p50_h: Optional[Decimal] = Decimal("4.5"),
    can_skip: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        tenant_id=TEST_TENANT_ID,
        template_id=template_id,
        seq=seq,
        phase_id=phase_id,
        phase_name=phase_name,
        duration_p50_h=duration_p50_h,
        duration_p90_h=None,
        requires_mold=False,
        team_size_default=1,
        can_skip=can_skip,
        alternative_group_id=None,
    )


def _model_routing_assignment(
    *, model_id: str, primary_template_id: UUID
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        tenant_id=TEST_TENANT_ID,
        model_id=model_id,
        primary_template_id=primary_template_id,
        alt_template_id=None,
    )


# ─── MODELO ──────────────────────────────────────────────────────────────────


def test_modelo_happy_path_with_routing():
    """Modelo com encomendas + routing template — preenche tudo."""
    session = FakeSession()
    template_id = uuid4()

    orders = [
        _order(legacy_id=1, product_name="K1-Vanquish-L", current_phase_name="Laminagem"),
        _order(legacy_id=2, product_name="K1-Vanquish-L", current_phase_name="Entregue",
               status_=OrderStatus.COMPLETED),
        _order(legacy_id=3, product_name="K1-Vanquish-L", current_phase_name="Cura"),
    ]
    template = _template(id_=template_id, code="ROUTING-0001", name="Rota K1", phase_count=2)
    phases = [
        _template_phase(template_id=template_id, seq=1, phase_id="laminagem",
                        phase_name="Laminagem", duration_p50_h=Decimal("4.5")),
        _template_phase(template_id=template_id, seq=2, phase_id="cura",
                        phase_name="Cura", duration_p50_h=Decimal("15.0")),
    ]
    routing_assignment = _model_routing_assignment(
        model_id="K1-Vanquish-L", primary_template_id=template_id
    )

    # FakeSession.execute pops one item from EACH queue per call. Aligned:
    # call 1 (orders scalars), call 2 (routing assignment scalar),
    # call 3 (template scalar), call 4 (phases scalars).
    session.queue_scalar(None)              # call 1 — não consumido
    session.queue_scalars(orders)           # call 1 → scalars().all()
    session.queue_scalar(routing_assignment)  # call 2 → scalar_one_or_none
    session.queue_scalars([])               # call 2 — não consumido
    session.queue_scalar(template)          # call 3 → scalar_one_or_none
    session.queue_scalars([])               # call 3 — não consumido
    session.queue_scalar(None)              # call 4 — não consumido
    session.queue_scalars(phases)           # call 4 → scalars().all()

    client = _minimal_app(session)
    resp = client.get("/v1/entity/modelo/K1-Vanquish-L", headers=_HEADERS)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["model_id"] == "K1-Vanquish-L"
    assert body["model_name"] == "K1-Vanquish-L"
    assert body["product_type"] == "K1"
    # 2 IN_PROGRESS (Laminagem + Cura), 1 COMPLETED (Entregue)
    assert body["active_orders_count"] == 2
    # 2 IN_PROGRESS não-terminais
    assert body["in_production_count"] == 2
    assert body["routing_template"] is not None
    assert body["routing_template"]["code"] == "ROUTING-0001"
    assert len(body["routing_template"]["phases"]) == 2
    assert body["routing_template"]["phases"][0]["phase_id"] == "laminagem"
    assert body["routing_template"]["phases"][0]["duration_p50_h"] == 4.5


def test_modelo_without_routing_template_returns_none():
    """Modelo existe (tem encomendas) mas sem routing template — não 404."""
    session = FakeSession()
    session.queue_scalars([
        _order(legacy_id=42, product_name="MODELO-X", product_type="C2"),
    ])
    # resolve_for_model → ModelRoutingAssignment não encontra → scalar None.
    session.queue_scalar(None)

    client = _minimal_app(session)
    resp = client.get("/v1/entity/modelo/MODELO-X", headers=_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["model_id"] == "MODELO-X"
    assert body["routing_template"] is None
    assert body["product_type"] == "C2"
    assert body["active_orders_count"] == 1


def test_modelo_no_orders_no_routing():
    """Sem encomendas E sem routing — devolve estrutura vazia (não 404)."""
    session = FakeSession()
    session.queue_scalars([])  # zero orders
    session.queue_scalar(None)  # zero routing assignment

    client = _minimal_app(session)
    resp = client.get("/v1/entity/modelo/UNKNOWN", headers=_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["model_id"] == "UNKNOWN"
    assert body["model_name"] == "UNKNOWN"
    assert body["product_type"] is None
    assert body["routing_template"] is None
    assert body["active_orders_count"] == 0
    assert body["in_production_count"] == 0


# ─── FASE ────────────────────────────────────────────────────────────────────


def test_fase_happy_path_with_all_data():
    """Fase com nome de template + afinidades + boat scores."""
    session = FakeSession()
    op1 = uuid4()
    op2 = uuid4()

    # FakeSession.execute() pops one item from EACH queue per call. Para
    # alinhar com a sequência de execute() do endpoint (call 1 usa scalar,
    # calls 2-4 usam scalars), enfileiramos uma scalars=[] na posição 1
    # para empurrar os reais para as posições certas.
    # 1. phase_name lookup (RoutingTemplatePhase) → scalar_one_or_none.
    session.queue_scalar("Laminagem")
    session.queue_scalars([])  # par para a call 1 (scalars vazio, não consumido).
    # 2. affinities (PhaseOperatorAffinity) → scalars().all().
    session.queue_scalars([
        _affinity(operator_id=op1, score=0.92, sample_count=20),
        _affinity(operator_id=op2, score=0.81, sample_count=15),
    ])
    # 3. employees lookup → scalars().all().
    session.queue_scalars([
        _employee(id_=op1, name="João Silva"),
        _employee(id_=op2, name="Maria Costa"),
    ])
    # 4. boat scores → scalars().all().
    session.queue_scalars([
        _boat_score(boat_id="K4-Slim-S", score=0.30, sample_count=5),
        _boat_score(boat_id="C1-Vibe-L", score=0.42, sample_count=8),
    ])

    client = _minimal_app(session)
    # "LAMINAGEM" está em NELO_CURING_GAPS_SEED como from/to → vão aparecer.
    resp = client.get("/v1/entity/fase/laminagem", headers=_HEADERS)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["phase_id"] == "laminagem"
    assert body["phase_name"] == "Laminagem"
    assert len(body["top_operators"]) == 2
    # Order kept from queue (score DESC simulated).
    assert body["top_operators"][0]["operator_name"] == "João Silva"
    assert body["top_operators"][0]["score"] == 0.92
    assert len(body["difficult_boats"]) == 2
    assert body["difficult_boats"][0]["boat_id"] == "K4-Slim-S"
    # NELO_CURING_GAPS_SEED tem ("LAMINAGEM","CURA",15.0,…) — laminagem → CURA é out.
    out_phases = [g["to_phase"] for g in body["curing_gaps_out"]]
    assert "CURA" in out_phases


def test_fase_404_when_no_data_anywhere():
    """Fase totalmente desconhecida — 404."""
    session = FakeSession()
    # phase_name lookup → None.
    session.queue_scalar(None)
    # affinities → vazio.
    session.queue_scalars([])
    # boat scores → vazio.
    session.queue_scalars([])

    client = _minimal_app(session)
    # "fase_inventada" não está em NELO_CURING_GAPS_SEED.
    resp = client.get("/v1/entity/fase/fase_inventada", headers=_HEADERS)
    assert resp.status_code == 404


def test_fase_only_curing_gap_no_404():
    """Fase só conhecida via NELO_CURING_GAPS_SEED — não 404."""
    session = FakeSession()
    session.queue_scalar(None)       # phase_name lookup
    session.queue_scalars([])         # affinities
    session.queue_scalars([])         # boat scores

    client = _minimal_app(session)
    # "cura" é destino de várias gaps no SEED (LAMINAGEM→CURA).
    resp = client.get("/v1/entity/fase/cura", headers=_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["phase_name"] == "cura"  # fallback ao phase_id
    assert body["top_operators"] == []
    assert body["difficult_boats"] == []
    assert len(body["curing_gaps_in"]) >= 1
    from_phases = [g["from_phase"] for g in body["curing_gaps_in"]]
    assert "LAMINAGEM" in from_phases


# ─── CLIENTE ─────────────────────────────────────────────────────────────────


def test_cliente_happy_path_with_orders():
    """Cliente existe + prioridade + encomendas associadas."""
    session = FakeSession()
    customer_id = uuid4()
    cust = _customer(id_=customer_id, customer_name="Acme Náutica")
    cp = _client_priority(client_id=customer_id, priority=1)
    orders = [
        _order(legacy_id=101, customer_name="Acme Náutica",
               current_phase_name="Laminagem"),
        _order(legacy_id=102, customer_name="Acme Náutica",
               current_phase_name="Entregue", status_=OrderStatus.COMPLETED),
        _order(legacy_id=103, customer_name="Outro Cliente",
               current_phase_name="Cura"),
    ]

    # FakeSession.execute pops 1 from EACH queue per call. Aligned:
    # call 1 (customer scalar), call 2 (cp scalar), call 3 (orders scalars).
    session.queue_scalar(cust)
    session.queue_scalars([])
    session.queue_scalar(cp)
    session.queue_scalars([])
    session.queue_scalar(None)
    session.queue_scalars(orders)

    client = _minimal_app(session)
    resp = client.get(f"/v1/entity/cliente/{customer_id}", headers=_HEADERS)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["customer_id"] == str(customer_id)
    assert body["customer_name"] == "Acme Náutica"
    assert body["priority"] == 1
    # 2 do "Acme Náutica" (1 in_progress não-terminal + 1 entregue).
    # active_orders_count conta só os não-terminais.
    assert body["active_orders_count"] == 1
    # `orders` lista todas as não-CANCELLED até 20: 2.
    assert len(body["orders"]) == 2
    assert {o["legacy_id"] for o in body["orders"]} == {101, 102}


def test_cliente_404_when_customer_missing():
    """customer_id desconhecido → 404."""
    session = FakeSession()
    session.queue_scalar(None)  # customer lookup → not found

    client = _minimal_app(session)
    resp = client.get(f"/v1/entity/cliente/{uuid4()}", headers=_HEADERS)
    assert resp.status_code == 404


def test_cliente_no_priority_no_orders():
    """Cliente existe mas sem prioridade nem encomendas — listas vazias, 200."""
    session = FakeSession()
    customer_id = uuid4()
    # Aligned: call 1 (customer scalar), call 2 (priority scalar None),
    # call 3 (orders scalars vazio).
    session.queue_scalar(_customer(id_=customer_id, customer_name="Cliente Novo"))
    session.queue_scalars([])
    session.queue_scalar(None)
    session.queue_scalars([])
    session.queue_scalar(None)
    session.queue_scalars([])

    client = _minimal_app(session)
    resp = client.get(f"/v1/entity/cliente/{customer_id}", headers=_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["priority"] is None
    assert body["active_orders_count"] == 0
    assert body["orders"] == []


# ─── ENCOMENDA ───────────────────────────────────────────────────────────────


def test_encomenda_happy_path():
    """Encomenda existe — devolve shape completo."""
    session = FakeSession()
    order = _order(
        legacy_id=5001,
        product_name="K2-Quattro-M",
        product_type="K2",
        current_phase_name="Pintura Acabamento",
        created_date=date(2026, 1, 15),
        transport_date=date(2026, 6, 30),
        customer_name="Naval XYZ",
    )
    session.queue_scalar(order)

    client = _minimal_app(session)
    resp = client.get("/v1/entity/encomenda/5001", headers=_HEADERS)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["legacy_id"] == 5001
    assert body["product_name"] == "K2-Quattro-M"
    assert body["product_type"] == "K2"
    assert body["customer_name"] == "Naval XYZ"
    assert body["current_phase_name"] == "Pintura Acabamento"
    assert body["created_date"] == "2026-01-15"
    assert body["transport_date"] == "2026-06-30"
    assert body["completed_date"] is None
    assert body["status"] == "IN_PROGRESS"
    # phase_history vazio até sync.WorkOrderPhase (TODO documentado).
    assert body["phase_history"] == []


def test_encomenda_404_when_missing():
    session = FakeSession()
    session.queue_scalar(None)

    client = _minimal_app(session)
    resp = client.get("/v1/entity/encomenda/99999", headers=_HEADERS)
    assert resp.status_code == 404


def test_encomenda_no_dates_no_customer():
    """Encomenda mínima — sem datas + sem customer_name → campos null honestos."""
    session = FakeSession()
    order = _order(
        legacy_id=7,
        product_name="C1-Vibe",
        product_type=None,
        current_phase_name="Pendente",
        created_date=None,
        transport_date=None,
        completed_date=None,
        customer_name=None,
    )
    session.queue_scalar(order)

    client = _minimal_app(session)
    resp = client.get("/v1/entity/encomenda/7", headers=_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["legacy_id"] == 7
    assert body["customer_name"] is None
    assert body["product_type"] is None
    assert body["created_date"] is None
    assert body["transport_date"] is None
    assert body["completed_date"] is None
    assert body["phase_history"] == []
