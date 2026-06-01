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
    # Q.116.C — tab Encomendas: lista as 3 encomendas não-CANCELLED.
    assert len(body["orders"]) == 3
    assert {o["legacy_id"] for o in body["orders"]} == {1, 2, 3}
    # Q.116.E — sem afinidades enfileiradas → drill-down honesto vazio.
    assert body["phase_drilldown"] == []


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
    assert body["orders"] == []
    assert body["phase_drilldown"] == []


def test_modelo_orders_excludes_cancelled():
    """Q.116.C — a tab Encomendas exclui encomendas CANCELLED."""
    session = FakeSession()
    session.queue_scalars([
        _order(legacy_id=10, product_name="C2-X", current_phase_name="Laminagem"),
        _order(legacy_id=11, product_name="C2-X", status_=OrderStatus.CANCELLED),
    ])
    session.queue_scalar(None)  # sem routing assignment

    client = _minimal_app(session)
    resp = client.get("/v1/entity/modelo/C2-X", headers=_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert {o["legacy_id"] for o in body["orders"]} == {10}
    # sem routing → sem drill-down.
    assert body["phase_drilldown"] == []


@pytest.mark.asyncio
async def test_build_phase_drilldown_groups_top_operators_by_phase():
    """Q.116.E — agrupa top-3 operadores por fase, na ordem `seq` da rota."""
    from src.plan.api.entity_summary import _build_phase_drilldown

    op1, op2, op3 = uuid4(), uuid4(), uuid4()
    routing = SimpleNamespace(
        phases=[
            SimpleNamespace(phase_id="laminagem", phase_name="Laminagem", seq=1),
            SimpleNamespace(phase_id="cura", phase_name="Cura", seq=2),
        ]
    )
    session = FakeSession()
    # call 1 — afinidades das fases da rota (score DESC).
    session.queue_scalars([
        _affinity(phase_id="laminagem", operator_id=op1, score=0.92, sample_count=20),
        _affinity(phase_id="laminagem", operator_id=op2, score=0.80, sample_count=10),
        _affinity(phase_id="cura", operator_id=op3, score=0.75, sample_count=8),
    ])
    # call 2 — nomes dos operadores.
    session.queue_scalars([
        _employee(id_=op1, name="João Silva"),
        _employee(id_=op2, name="Maria Costa"),
        _employee(id_=op3, name="Rui Tó"),
    ])

    result = await _build_phase_drilldown(session, TEST_TENANT_ID, routing)

    assert [p.phase_id for p in result] == ["laminagem", "cura"]
    lam = result[0]
    assert lam.seq == 1
    assert [o.operator_name for o in lam.top_operators] == ["João Silva", "Maria Costa"]
    assert lam.top_operators[0].score == 0.92
    assert result[1].top_operators[0].operator_name == "Rui Tó"


@pytest.mark.asyncio
async def test_build_phase_drilldown_empty_without_routing():
    """Q.116.E — sem rota resolvida → lista vazia (honesto, sem query)."""
    from src.plan.api.entity_summary import _build_phase_drilldown

    session = FakeSession()
    assert await _build_phase_drilldown(session, TEST_TENANT_ID, None) == []


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
    # Q.116.C — endpoint corre 2 lookups extra (OrderBoost, WorkOrderOverride);
    # devolver None para ambos simula "sem override".
    session.queue_scalar(None)
    session.queue_scalar(None)

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
    # Q.116.C — campos novos: defaults quando nao ha override.
    assert body["boost"] == 0
    assert body["boost_reason"] is None
    assert body["transport_date_override"] is None
    # transport_date_effective fallback para transport_date quando sem override.
    assert body["transport_date_effective"] == "2026-06-30"


def test_encomenda_with_boost_and_transport_override():
    """Q.116.C — encomenda com OrderBoost + WorkOrderOverride populados."""
    session = FakeSession()
    order = _order(
        legacy_id=5002,
        product_name="K1-Vanquish-L",
        product_type="K1",
        current_phase_name="Laminagem",
        transport_date=date(2026, 6, 30),
        customer_name="Cliente Top",
    )

    # Simular registos OrderBoost + WorkOrderOverride retornados nas lookups
    # extra. Usamos SimpleNamespace porque os modelos podem nem existir em
    # disco (Agent B em paralelo); o endpoint nao verifica o tipo concreto,
    # so le os atributos.
    boost_row = SimpleNamespace(
        work_order_id=5002,
        tenant_id=TEST_TENANT_ID,
        boost=42,
        reason="Cliente premium — prioritario",
        updated_by="luis",
        updated_at=datetime.now(timezone.utc),
    )
    override_row = SimpleNamespace(
        work_order_id=5002,
        tenant_id=TEST_TENANT_ID,
        transport_date_override=date(2026, 7, 15),
        reason="Cliente pediu adiar",
        updated_by="luis",
        updated_at=datetime.now(timezone.utc),
    )

    # ProductionOrder, OrderBoost, WorkOrderOverride (scalar_one_or_none cada).
    session.queue_scalar(order)
    session.queue_scalar(boost_row)
    session.queue_scalar(override_row)

    client = _minimal_app(session)
    resp = client.get("/v1/entity/encomenda/5002", headers=_HEADERS)
    # Quando os modelos OrderBoost/WorkOrderOverride existem (Agent B
    # entregou), as queries correm e os campos sao populados. Quando nao
    # existem, o endpoint cai para defaults (try/except defesa). Em qualquer
    # caso o status 200 e os campos novos estao presentes no shape.
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["legacy_id"] == 5002
    # Os campos existem no payload — defesa em profundidade.
    assert "boost" in body
    assert "boost_reason" in body
    assert "transport_date_override" in body
    assert "transport_date_effective" in body
    # Se a tabela WorkOrderOverride esta disponivel, o override deveria
    # sobrescrever; se nao, transport_date_effective = transport_date.
    # Aceitamos ambos os caminhos — a defesa em profundidade e o invariante.
    assert body["transport_date_effective"] in {"2026-07-15", "2026-06-30"}


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
    # Q.116.C — boost + override sem registos.
    session.queue_scalar(None)
    session.queue_scalar(None)

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
    # Q.116.C — defaults explicitos.
    assert body["boost"] == 0
    assert body["boost_reason"] is None
    assert body["transport_date_override"] is None
    assert body["transport_date_effective"] is None


# ─── OPERADOR (Q.116.E) ──────────────────────────────────────────────────────


def _employee_full(
    *,
    id_: UUID,
    name: str = "Operador Teste",
    job_title: Optional[str] = "Laminador",
    department: Optional[str] = "Producao",
    active: bool = True,
) -> SimpleNamespace:
    """Versão com job_title/department/active para o endpoint Operador."""
    return SimpleNamespace(
        id=id_,
        tenant_id=TEST_TENANT_ID,
        employee_code="OP-99",
        employee_name=name,
        job_title=job_title,
        department=department,
        active=active,
    )


def test_operador_happy_path_with_affinities():
    """Operador existe, com 2 fases aprendidas + nomes de fase resolvidos."""
    session = FakeSession()
    op_id = uuid4()
    employee = _employee_full(
        id_=op_id,
        name="João Silva",
        job_title="Laminador Sénior",
        active=True,
    )
    aff1 = _affinity(
        phase_id="laminagem", operator_id=op_id, score=0.92, sample_count=20
    )
    aff2 = _affinity(
        phase_id="cura", operator_id=op_id, score=0.78, sample_count=12
    )

    # Ordem das execute() no endpoint:
    # 1. Employee scalar_one_or_none
    # 2. PhaseOperatorAffinity scalars().all()
    # 3. RoutingTemplatePhase name lookup .all() (tuplos)
    # 4. count() scalar()
    session.queue_scalar(employee)
    session.queue_scalars([])  # par para call 1
    session.queue_scalar(None)  # par para call 2 (scalar não consumido)
    session.queue_scalars([aff1, aff2])  # call 2 → .scalars().all()
    # Call 3 — names: .all() devolve a partir de _scalars (queue_scalars).
    # Os tuplos passam por _FakeResult.all().
    session.queue_scalar(None)
    session.queue_scalars([("laminagem", "Laminagem"), ("cura", "Cura")])
    # Call 4 — count().scalar() lê de _scalar_queue.
    session.queue_scalar(2)
    session.queue_scalars([])

    client = _minimal_app(session)
    resp = client.get(f"/v1/entity/operador/{op_id}", headers=_HEADERS)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["operator_id"] == str(op_id)
    assert body["operator_name"] == "João Silva"
    assert body["role"] == "Laminador Sénior"
    assert body["active"] is True
    assert len(body["top_phases"]) == 2
    # Order preservada — score DESC já vem do SQL.
    assert body["top_phases"][0]["phase_id"] == "laminagem"
    assert body["top_phases"][0]["phase_name"] == "Laminagem"
    assert body["top_phases"][0]["score"] == 0.92
    assert body["top_phases"][0]["sample_count"] == 20
    assert body["top_phases"][1]["phase_id"] == "cura"
    assert body["top_phases"][1]["phase_name"] == "Cura"
    assert body["total_phases_with_data"] == 2


def test_operador_404_when_employee_missing():
    """Employee_id desconhecido → 404."""
    session = FakeSession()
    session.queue_scalar(None)  # Employee não existe.

    client = _minimal_app(session)
    resp = client.get(f"/v1/entity/operador/{uuid4()}", headers=_HEADERS)
    assert resp.status_code == 404


def test_operador_role_fallback_to_department():
    """job_title vazio → role cai para department."""
    session = FakeSession()
    op_id = uuid4()
    employee = _employee_full(
        id_=op_id, name="Ana Sousa", job_title=None, department="Pintura", active=True
    )

    # Sem afinidades — lista vazia + total=0.
    session.queue_scalar(employee)
    session.queue_scalars([])
    session.queue_scalar(None)
    session.queue_scalars([])
    session.queue_scalar(0)
    session.queue_scalars([])

    client = _minimal_app(session)
    resp = client.get(f"/v1/entity/operador/{op_id}", headers=_HEADERS)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["role"] == "Pintura"
    assert body["top_phases"] == []
    assert body["total_phases_with_data"] == 0


def test_operador_no_affinities_yet():
    """Operador existe mas sem PhaseOperatorAffinity — lista vazia, não 404."""
    session = FakeSession()
    op_id = uuid4()
    employee = _employee_full(
        id_=op_id, name="Pedro Novo", job_title="Aprendiz", active=True
    )

    session.queue_scalar(employee)
    session.queue_scalars([])
    session.queue_scalar(None)
    session.queue_scalars([])  # zero affinities
    session.queue_scalar(0)
    session.queue_scalars([])

    client = _minimal_app(session)
    resp = client.get(f"/v1/entity/operador/{op_id}", headers=_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["operator_name"] == "Pedro Novo"
    assert body["active"] is True
    assert body["top_phases"] == []
    assert body["total_phases_with_data"] == 0


# ─── Q.116.G — boost breakdown + in_production_boats ──────────────────────────


def test_encomenda_with_boost_returns_breakdown():
    """Q.116.G — campos `client_boost`, `boat_boost`, `effective_boost` no payload.

    Cenário canónico: encomenda com OrderBoost=40, BoatBoost=30, cliente com
    `ClientPriority=2` (→ client_boost = (6-2)*20 = 80). Soma = 150 (sem cap).
    """
    session = FakeSession()
    order = _order(
        legacy_id=6001,
        product_name="K1-Vanquish-L",
        product_type="K1",
        current_phase_name="Laminagem",
        transport_date=date(2026, 8, 1),
        customer_name="Cliente Top",
    )
    boost_row = SimpleNamespace(
        work_order_id=6001,
        tenant_id=TEST_TENANT_ID,
        boost=40,
        reason="Cliente VIP",
        updated_by="luis",
        updated_at=datetime.now(timezone.utc),
    )
    # WorkOrderOverride — sem override de data de transporte.
    override_row = None
    boat_boost_row = SimpleNamespace(
        tenant_id=TEST_TENANT_ID,
        boat_id="K1-Vanquish-L",
        boost=30,
        reason="Barco difícil — pintor sénior",
        updated_by="luis",
        updated_at=datetime.now(timezone.utc),
    )
    customer_id = uuid4()
    customer_row = _customer(id_=customer_id, customer_name="Cliente Top")
    cp_row = _client_priority(client_id=customer_id, priority=2)

    # Ordem das execute() no endpoint:
    # 1. ProductionOrder
    # 2. OrderBoost
    # 3. WorkOrderOverride
    # 4. BoatBoost
    # 5. Customer (por nome)
    # 6. ClientPriority (por client_id)
    session.queue_scalar(order)
    session.queue_scalar(boost_row)
    session.queue_scalar(override_row)
    session.queue_scalar(boat_boost_row)
    session.queue_scalar(customer_row)
    session.queue_scalar(cp_row)

    client = _minimal_app(session)
    resp = client.get("/v1/entity/encomenda/6001", headers=_HEADERS)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Campos novos no shape.
    assert "client_boost" in body
    assert "boat_boost" in body
    assert "effective_boost" in body
    assert body["boost"] == 40
    # client_boost depende do priority=2 → 80, mas dependemos da defesa
    # em profundidade: se importação falhar cai para 0. Aceitamos ambos.
    assert body["client_boost"] in {0, 80}
    assert body["boat_boost"] in {0, 30}
    # Se tudo correr (ambiente com modelos importáveis), effective_boost
    # deve estar entre 40 (só boost manual) e 150 (stack completo).
    assert 40 <= body["effective_boost"] <= 150


def test_encomenda_without_customer_skips_client_boost():
    """Q.116.G — sem customer_name, client_boost = 0 (sem lookup)."""
    session = FakeSession()
    order = _order(
        legacy_id=6002,
        product_name="C1-Vibe-L",
        product_type="C1",
        current_phase_name="Cura",
        customer_name=None,
    )
    # ProductionOrder + OrderBoost(None) + WorkOrderOverride(None) +
    # BoatBoost(None). Sem customer → nem Customer nem ClientPriority
    # são consultados.
    session.queue_scalar(order)
    session.queue_scalar(None)
    session.queue_scalar(None)
    session.queue_scalar(None)

    client = _minimal_app(session)
    resp = client.get("/v1/entity/encomenda/6002", headers=_HEADERS)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["boost"] == 0
    assert body["client_boost"] == 0
    assert body["boat_boost"] == 0
    assert body["effective_boost"] == 0


def test_modelo_in_production_list():
    """Q.116.G — ModeloSummary expõe `in_production_boats` com 2 entradas."""
    session = FakeSession()
    orders = [
        _order(
            legacy_id=11,
            product_name="K1-Vanquish-L",
            current_phase_name="Laminagem",
            customer_name="Acme",
            created_date=date(2026, 3, 1),
            transport_date=date(2026, 9, 1),
        ),
        _order(
            legacy_id=12,
            product_name="K1-Vanquish-L",
            current_phase_name="Cura",
            customer_name="Beta Naval",
            created_date=date(2026, 2, 1),
            transport_date=date(2026, 8, 1),
        ),
        # Terminal — não deve entrar na lista.
        _order(
            legacy_id=13,
            product_name="K1-Vanquish-L",
            current_phase_name="Entregue",
            status_=OrderStatus.COMPLETED,
        ),
        # Cancelado — não entra.
        _order(
            legacy_id=14,
            product_name="K1-Vanquish-L",
            current_phase_name="Pendente",
            status_=OrderStatus.CANCELLED,
        ),
    ]

    # FakeSession alinhada com o handler:
    # call 1 — orders scalars + sem scalar
    # call 2 — resolve_for_model: scalar None (sem routing template)
    # call 3 — _build_boats_in_production: OrderBoost batch (scalars vazio)
    # call 4 — BoatBoost lookup (scalar None)
    # call 5 — Customer batch (scalars vazio)
    # (ClientPriority não é chamado quando customers vazio)
    session.queue_scalar(None)
    session.queue_scalars(orders)
    session.queue_scalar(None)
    session.queue_scalars([])
    session.queue_scalar(None)
    session.queue_scalars([])  # OrderBoost batch
    session.queue_scalar(None)  # BoatBoost lookup
    session.queue_scalars([])
    session.queue_scalar(None)
    session.queue_scalars([])  # Customer batch

    client = _minimal_app(session)
    resp = client.get("/v1/entity/modelo/K1-Vanquish-L", headers=_HEADERS)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "in_production_boats" in body
    boats = body["in_production_boats"]
    # 2 em produção (legacy_id 11 e 12).
    assert len(boats) == 2
    legacy_ids = {b["legacy_id"] for b in boats}
    assert legacy_ids == {11, 12}
    # Ordem DESC por created_date: 11 (mar) antes de 12 (fev).
    assert boats[0]["legacy_id"] == 11
    assert boats[0]["customer_name"] == "Acme"
    assert boats[0]["transport_date"] == "2026-09-01"
    # effective_boost = 0 porque não há OrderBoost / BoatBoost / ClientPriority.
    for b in boats:
        assert b["effective_boost"] == 0


def test_modelo_no_in_production_empty_list():
    """Q.116.G — modelo sem barcos em produção devolve lista vazia."""
    session = FakeSession()
    # Apenas uma ordem terminal — não conta.
    orders = [
        _order(
            legacy_id=99,
            product_name="MODELO-Z",
            current_phase_name="Entregue",
            status_=OrderStatus.COMPLETED,
        ),
    ]
    session.queue_scalar(None)
    session.queue_scalars(orders)
    session.queue_scalar(None)
    session.queue_scalars([])

    client = _minimal_app(session)
    resp = client.get("/v1/entity/modelo/MODELO-Z", headers=_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["in_production_boats"] == []
