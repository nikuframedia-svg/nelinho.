"""Q.61.32a — endpoints orders migrados de /api/* para /v1/plan/orders/*.

Cobre:

* fail-closed tenant (zero UUID → 401, header em falta → 401) para os
  3 endpoints migrados — pin do invariante Q.12 Onda 0.1 no destino
  novo (a cobertura no destino antigo desaparece quando Q.61.32d
  apagar `src/legacy/`).
* contrato 1-para-1 com o handler legacy: shape da resposta paginada,
  shape de `/stats`, 200/404 do lookup por `legacy_id`.
* registo de rotas: `/orders/stats` continua a ser resolvido pelo
  handler estático (não pelo parametrizado `{order_id:int}`) e
  `/orders/active` (Q.54.B) coexiste sem ambiguidade.

Os handlers vivem agora em `src/plan/api/orders.py`. Quando Q.61.32d
apagar `src/legacy/`, este ficheiro fica como única fonte de testes
para estes paths.
"""

from __future__ import annotations

from datetime import date
from typing import AsyncIterator
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.plan.api.orders import router as orders_router
from src.plan.models.order import OrderStatus, ProductionOrder
from src.shared.auth.headers import require_tenant_header
from src.shared.config import settings
from src.shared.database import get_session


ZERO_UUID = "00000000-0000-0000-0000-000000000000"
DEV_TENANT = "00000000-0000-0000-0000-000000000001"
TENANT = UUID(DEV_TENANT)


# ─── Fixtures ──────────────────────────────────────────────────────────


async def _stub_session() -> AsyncIterator[AsyncMock]:
    """Sessão stub para os testes de gate — nunca toca DB."""
    sess = AsyncMock()
    yield sess


def _gate_client(monkeypatch) -> TestClient:
    """App isolada com `orders_router` montado sob `/v1/plan`."""
    monkeypatch.setattr(settings, "environment", "development", raising=False)
    app = FastAPI()
    app.include_router(orders_router, prefix="/v1/plan")
    app.dependency_overrides[get_session] = _stub_session
    # raise_server_exceptions=False: queremos só ver o status do gate,
    # não bubble-up de erros do handler (AsyncMock não simula execute()).
    return TestClient(app, raise_server_exceptions=False)


# ─── Fail-closed tenant (Q.12 Onda 0.1) ───────────────────────────────


MIGRATED_GET_PATHS = [
    "/v1/plan/orders",
    "/v1/plan/orders/stats",
    "/v1/plan/orders/123",  # by legacy_id
]


@pytest.mark.parametrize("path", MIGRATED_GET_PATHS)
def test_zero_uuid_rejected_at_migrated_path(monkeypatch, path):
    """Zero-UUID continua proibido — exactamente como em /api/orders."""
    c = _gate_client(monkeypatch)
    resp = c.get(path, headers={"X-Tenant-Id": ZERO_UUID})
    assert resp.status_code == 401, (
        f"{path} aceitou zero UUID — fail-closed regrediu; got {resp.status_code}"
    )


@pytest.mark.parametrize("path", MIGRATED_GET_PATHS)
def test_missing_header_rejected_at_migrated_path(monkeypatch, path):
    """Header em falta → 401 (require_tenant_header garante)."""
    c = _gate_client(monkeypatch)
    resp = c.get(path)
    assert resp.status_code == 401, resp.text


def test_valid_dev_tenant_passes_dep_gate_at_migrated_path(monkeypatch):
    """Tenant válido (non-zero) passa o gate."""
    c = _gate_client(monkeypatch)
    resp = c.get("/v1/plan/orders", headers={"X-Tenant-Id": DEV_TENANT})
    # 200 se o handler tolera AsyncMock; senão 5xx. O ponto é "não 401".
    assert resp.status_code != 401, resp.text


def test_production_requires_jwt_at_migrated_path(monkeypatch):
    """Em produção, header isolado é insuficiente — JWT obrigatório."""
    monkeypatch.setattr(settings, "environment", "production", raising=False)
    app = FastAPI()
    app.include_router(orders_router, prefix="/v1/plan")
    app.dependency_overrides[get_session] = _stub_session
    c = TestClient(app, raise_server_exceptions=False)

    resp = c.get("/v1/plan/orders", headers={"X-Tenant-Id": DEV_TENANT})
    assert resp.status_code == 401, resp.text
    assert "JWT" in resp.json().get("detail", "")


# ─── Contrato com o handler legacy (shape preservada) ─────────────────


def _order(
    legacy_id: int, phase: str, status: OrderStatus, product_type: str = "K1"
) -> ProductionOrder:
    return ProductionOrder(
        id=uuid4(),
        tenant_id=TENANT,
        legacy_id=legacy_id,
        product_id=legacy_id,
        product_name="K1 Vanquish",
        product_type=product_type,
        current_phase_name=phase,
        status=status,
        created_date=date(2026, 5, 1),
    )


class _PaginatedSession:
    """Sessão fake para o handler paginado.

    Devolve `_orders` para a query principal e o `count(...)` corre por
    cima da subquery — para isso simulamos um `scalar()` que devolve o
    tamanho da lista de orders.
    """

    def __init__(self, orders, by_id: ProductionOrder | None = None):
        self._orders = list(orders)
        self._by_id = by_id
        # Cache da última query para dedicir o tipo de resultado
        self._last_stmt = ""

    async def execute(self, stmt):
        text = str(stmt).lower()
        self._last_stmt = text

        # 1. `select(func.count()).select_from(subquery)` → scalar() = total
        if "count(*)" in text or "count(" in text and "anon_" in text:
            orders = self._orders

            class _Scalar:
                async def __aenter__(self_inner):
                    return self_inner

                def scalar(self_inner):
                    return len(orders)

                async def scalar_one_or_none(self_inner):
                    return len(orders)

            r = _Scalar()
            # SQLAlchemy result API: .scalar() é sync no Result
            class _Result:
                def scalar(self_inner):
                    return len(orders)

                def scalar_one_or_none(self_inner):
                    return len(orders)

            return _Result()

        # 2. group_by(current_phase_name) → phase distribution
        if "group_by" in text or "current_phase_name" in text and "count" in text:
            rows = []

            class _RowsResult:
                def all(self_inner):
                    return rows

                def scalars(self_inner):
                    class _S:
                        def all(self_s):
                            return rows

                    return _S()

                def scalar(self_inner):
                    return 0

            return _RowsResult()

        # 3. select(ProductionOrder).where(legacy_id == X) → scalar_one_or_none
        if "legacy_id" in text and self._by_id is not None:
            class _ByIdResult:
                def __init__(self, order):
                    self._order = order

                def scalar_one_or_none(self_inner):
                    return self_inner._order

            return _ByIdResult(self._by_id)

        # 4. fallback — query principal
        orders = self._orders

        class _R:
            def scalars(self_inner):
                return self_inner

            def all(self_inner):
                return list(orders)

            def scalar_one_or_none(self_inner):
                return orders[0] if orders else None

            def scalar(self_inner):
                return len(orders)

        return _R()

    async def commit(self):
        pass


def _client_for(session) -> TestClient:
    app = FastAPI()
    app.include_router(orders_router, prefix="/v1/plan")
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[require_tenant_header] = lambda: TENANT
    return TestClient(app)


def test_list_orders_paginated_shape():
    """`GET /v1/plan/orders` devolve {data, total, page, pageSize, totalPages, ...}."""
    orders = [
        _order(1, "Laminagem", OrderStatus.IN_PROGRESS),
        _order(2, "Montagem", OrderStatus.IN_PROGRESS),
    ]
    client = _client_for(_PaginatedSession(orders))
    resp = client.get("/v1/plan/orders?page=1&pageSize=20")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) >= {
        "data",
        "total",
        "page",
        "pageSize",
        "totalPages",
        "hasNextPage",
        "hasPreviousPage",
    }
    assert body["page"] == 1
    assert body["pageSize"] == 20
    assert body["total"] == 2
    assert len(body["data"]) == 2
    # 1-para-1 com legacy: campos camelCase chegam preservados.
    row = body["data"][0]
    assert {
        "id",
        "productId",
        "productName",
        "productType",
        "currentPhaseId",
        "currentPhaseName",
        "createdDate",
        "completedDate",
        "transportDate",
        "status",
    } <= row.keys()


def test_get_order_by_legacy_id_returns_404_when_missing():
    """`GET /v1/plan/orders/{int}` → 404 com detail."""
    client = _client_for(_PaginatedSession([], by_id=None))
    resp = client.get("/v1/plan/orders/999999")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Order not found"


def test_get_order_by_legacy_id_returns_payload_when_found():
    """`GET /v1/plan/orders/{int}` → payload single (não envolvido em data[])."""
    order = _order(4271, "Laminagem", OrderStatus.IN_PROGRESS)
    client = _client_for(_PaginatedSession([], by_id=order))
    resp = client.get("/v1/plan/orders/4271")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "4271"
    assert body["productName"] == "K1 Vanquish"
    assert body["currentPhaseName"] == "Laminagem"


def test_stats_route_resolves_to_static_handler_not_int_param():
    """`/v1/plan/orders/stats` é resolvido pelo handler estático (não
    `/orders/{order_id:int}`) — `stats` não parse-a como int.

    Regressão: registar `/orders/{order_id:int}` antes de `/orders/stats`
    devolveria 422 ("stats" não é int). A ordem actual do ficheiro
    (`stats` antes do parametrizado) protege contra isto.
    """
    client = _client_for(_PaginatedSession([]))
    resp = client.get("/v1/plan/orders/stats")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) >= {
        "total",
        "inProgress",
        "completed",
        "withTransport",
        "phaseDistribution",
    }


def test_active_orders_endpoint_coexists_with_new_paginated_root():
    """`/v1/plan/orders/active` (Q.54.B) continua a funcionar — não
    foi sombreado pelo handler novo de `/v1/plan/orders`."""
    # Usar dependency override completo para sessão que serve /orders/active
    client = _client_for(_PaginatedSession([]))
    resp = client.get("/v1/plan/orders/active")
    # 200 OK com lista flat (não a estrutura paginada).
    assert resp.status_code == 200, resp.text
    # `/orders/active` devolve list[dict], não dict com `data` key.
    assert isinstance(resp.json(), list)
