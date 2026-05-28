"""Q.116.E — tests para os 4 endpoints LIST master-data.

Cobertura mínima: 1 happy path por endpoint, verificando o shape
exacto que o frontend (`masterDataApi.ts`) consome. Drift de campo
aqui = EmptyState no painel master-data.

Strategy: FastAPI TestClient + FakeSession (tests/conftest.py).
Override require_tenant_header + get_session + PermissionDependency
para SCHEDULE_READ. Sem DB real.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from typing import Any, Optional
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.master_data.api.lists import (
    _require_schedule_read,
    router as lists_router,
)
from src.plan.models.order import OrderStatus
from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session
from tests.conftest import FakeSession, TEST_TENANT_ID

_TENANT = str(TEST_TENANT_ID)
_HEADERS = {"X-Tenant-Id": _TENANT}


# ─── App factory ─────────────────────────────────────────────────────────────


def _minimal_app(session: FakeSession) -> TestClient:
    app = FastAPI()
    app.include_router(lists_router)

    async def _s():
        yield session

    async def _no_rbac():
        return None

    app.dependency_overrides[get_session] = _s
    app.dependency_overrides[require_tenant_header] = lambda: TEST_TENANT_ID
    app.dependency_overrides[_require_schedule_read] = _no_rbac
    return TestClient(app, raise_server_exceptions=True)


# ─── Fixtures helpers ────────────────────────────────────────────────────────


def _order(
    *,
    legacy_id: int = 1001,
    product_name: str = "K1-Vanquish-L",
    product_type: Optional[str] = "K1",
    current_phase_name: str = "Laminagem",
    status_: OrderStatus = OrderStatus.IN_PROGRESS,
    created_date: Optional[date] = None,
    transport_date: Optional[date] = None,
    completed_date: Optional[date] = None,
    customer_name: Optional[str] = None,
    cancelled_at: Optional[datetime] = None,
) -> SimpleNamespace:
    cd = date(2026, 1, 1) if created_date is None else created_date
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
        cancelled_at=cancelled_at,
        cancelled_by=None,
        cancellation_reason=None,
        customer_name=customer_name,
    )


def _employee(
    *,
    id_: Optional[Any] = None,
    name: str = "João Operador",
    job_title: Optional[str] = "Laminador",
    department: Optional[str] = "Producao",
    active: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id_ or uuid4(),
        tenant_id=TEST_TENANT_ID,
        employee_code="OP-01",
        employee_name=name,
        job_title=job_title,
        department=department,
        active=active,
    )


# ─── 1. GET /v1/work-orders ──────────────────────────────────────────────────


def test_list_work_orders_active_returns_in_progress_only():
    """Happy path: status=active filtra fora CANCELLED e fases terminais."""
    session = FakeSession()
    rows = [
        _order(
            legacy_id=10,
            product_name="K1-Vanquish-L",
            current_phase_name="Laminagem",
            customer_name="Acme Naval",
            status_=OrderStatus.IN_PROGRESS,
        ),
        _order(
            legacy_id=11,
            product_name="K2-Quattro",
            current_phase_name="Entregue",
            customer_name="Naval XYZ",
            status_=OrderStatus.COMPLETED,
        ),
        _order(
            legacy_id=12,
            product_name="C1-Vibe",
            current_phase_name="Cura",
            customer_name="Outra Empresa",
            status_=OrderStatus.CANCELLED,
        ),
    ]
    session.queue_scalars(rows)

    client = _minimal_app(session)
    resp = client.get("/v1/work-orders?status=active&limit=20", headers=_HEADERS)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list)
    # Só a IN_PROGRESS não-terminal sobrevive.
    assert len(body) == 1
    item = body[0]
    # Q.116.E fix: shape inclui modelo_id e cliente_id para Clickable.
    assert set(item.keys()) == {
        "of_id", "modelo", "modelo_id", "cliente", "cliente_id",
        "fase_actual", "status",
    }
    assert item["of_id"] == "10"
    assert item["modelo"] == "K1-Vanquish-L"
    assert item["modelo_id"] == "K1-Vanquish-L"
    assert item["cliente"] == "Acme Naval"
    # cliente_id é None porque o FakeSession não tem Customer rows queued.
    assert item["cliente_id"] is None
    assert item["fase_actual"] == "Laminagem"
    assert item["status"] == "IN_PROGRESS"


# ─── 2. GET /v1/encomendas ───────────────────────────────────────────────────


def test_list_encomendas_active_returns_non_cancelled():
    """Happy path: status=active filtra CANCELLED. Shape: encomenda_id,
    cliente, data, total_eur."""
    session = FakeSession()
    rows = [
        _order(
            legacy_id=200,
            product_name="K1-Vanquish-L",
            customer_name="Cliente Alfa",
            created_date=date(2026, 3, 15),
            status_=OrderStatus.IN_PROGRESS,
        ),
        _order(
            legacy_id=201,
            customer_name="Cliente Beta",
            created_date=date(2026, 3, 10),
            status_=OrderStatus.CANCELLED,
        ),
    ]
    session.queue_scalars(rows)

    client = _minimal_app(session)
    resp = client.get("/v1/encomendas?status=active&limit=20", headers=_HEADERS)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    item = body[0]
    # Q.116.E fix: shape inclui cliente_id para Clickable.
    assert set(item.keys()) == {
        "encomenda_id", "cliente", "cliente_id", "data", "total_eur",
    }
    assert item["encomenda_id"] == "200"
    assert item["cliente"] == "Cliente Alfa"
    assert item["cliente_id"] is None  # sem Customer queued
    assert item["data"] == "2026-03-15"
    # TODO Q.66.X — total_eur fica 0 até Encomenda separada existir.
    assert item["total_eur"] == 0.0


# ─── 3. GET /v1/master-data/boats ────────────────────────────────────────────


def test_list_boats_hides_retired_by_default():
    """Happy path: show_retired=false → barcos cancelled saem fora. Shape:
    boat_id, modelo_nome, retired_at."""
    session = FakeSession()
    cancelled_at = datetime(2026, 4, 1, 10, 0, 0, tzinfo=timezone.utc)
    rows = [
        _order(
            legacy_id=900,
            product_name="K4-Slim-S",
            completed_date=date(2026, 1, 20),
            cancelled_at=None,
            status_=OrderStatus.COMPLETED,
        ),
        _order(
            legacy_id=901,
            product_name="K1-Vanquish-XL",
            completed_date=date(2026, 2, 10),
            cancelled_at=cancelled_at,
            status_=OrderStatus.COMPLETED,
        ),
    ]
    session.queue_scalars(rows)

    client = _minimal_app(session)
    resp = client.get(
        "/v1/master-data/boats?show_retired=false&limit=20", headers=_HEADERS
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    item = body[0]
    # Q.116.E fix: shape inclui modelo_id para Clickable.
    assert set(item.keys()) == {"boat_id", "modelo_nome", "modelo_id", "retired_at"}
    assert item["boat_id"] == "900"
    assert item["modelo_nome"] == "K4-Slim-S"
    assert item["modelo_id"] == "K4-Slim-S"
    assert item["retired_at"] is None


def test_list_boats_show_retired_includes_cancelled():
    """show_retired=true → inclui barcos com cancelled_at."""
    session = FakeSession()
    cancelled_at = datetime(2026, 4, 1, 10, 0, 0, tzinfo=timezone.utc)
    rows = [
        _order(
            legacy_id=901,
            product_name="K1-Vanquish-XL",
            completed_date=date(2026, 2, 10),
            cancelled_at=cancelled_at,
            status_=OrderStatus.COMPLETED,
        ),
    ]
    session.queue_scalars(rows)

    client = _minimal_app(session)
    resp = client.get(
        "/v1/master-data/boats?show_retired=true&limit=20", headers=_HEADERS
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    assert body[0]["retired_at"] is not None


# ─── 4. GET /v1/master-data/employees ────────────────────────────────────────


def test_list_employees_hides_inactive_by_default():
    """Happy path: show_inactive=false → só active=True. Shape:
    employee_id, nome, role, active."""
    session = FakeSession()
    emp_active = _employee(
        name="Maria Costa", job_title="Pintora", active=True
    )
    emp_inactive = _employee(
        name="Pedro Silva", job_title="Reformado", active=False
    )
    session.queue_scalars([emp_active, emp_inactive])

    client = _minimal_app(session)
    resp = client.get(
        "/v1/master-data/employees?show_inactive=false&limit=20", headers=_HEADERS
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    item = body[0]
    assert set(item.keys()) == {"employee_id", "nome", "role", "active"}
    assert item["nome"] == "Maria Costa"
    assert item["role"] == "Pintora"
    assert item["active"] is True
    # employee_id é uma UUID stringificada.
    assert item["employee_id"] == str(emp_active.id)


def test_list_employees_role_fallback_to_department():
    """job_title vazio → role cai para department."""
    session = FakeSession()
    emp = _employee(
        name="Ana Sousa", job_title=None, department="Laminagem", active=True
    )
    session.queue_scalars([emp])

    client = _minimal_app(session)
    resp = client.get(
        "/v1/master-data/employees?show_inactive=false&limit=20", headers=_HEADERS
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["role"] == "Laminagem"
