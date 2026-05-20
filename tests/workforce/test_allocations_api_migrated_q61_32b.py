"""Q.61.32b — endpoints allocations migrados de /api/* para /v1/workforce/allocations/*.

Cobre:

* fail-closed tenant (zero UUID + missing header) para os 2 endpoints
  migrados — pin do invariante Q.12 Onda 0.1 no destino novo (a
  cobertura no destino antigo `tests/legacy/...` deixa de incluir
  allocations a partir deste sub-sprint).
* contrato 1-para-1 com o handler legacy: shape paginada e shape do
  `/stats` (uniqueEmployees/uniqueOrders/asLeader/avgPerEmployee/
  topPhases/topEmployees) preservadas.

Quando Q.61.32d apagar `src/legacy/`, este ficheiro é a única fonte
de testes para estes paths.
"""

from __future__ import annotations

from typing import AsyncIterator
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.shared.auth.headers import require_tenant_header
from src.shared.config import settings
from src.shared.database import get_session
from src.workforce.api import router as workforce_router


ZERO_UUID = "00000000-0000-0000-0000-000000000000"
DEV_TENANT = "00000000-0000-0000-0000-000000000001"
TENANT = UUID(DEV_TENANT)


async def _stub_session() -> AsyncIterator[AsyncMock]:
    sess = AsyncMock()
    yield sess


def _gate_client(monkeypatch) -> TestClient:
    monkeypatch.setattr(settings, "environment", "development", raising=False)
    app = FastAPI()
    app.include_router(workforce_router)
    app.dependency_overrides[get_session] = _stub_session
    return TestClient(app, raise_server_exceptions=False)


MIGRATED_GET_PATHS = [
    "/v1/workforce/allocations",
    "/v1/workforce/allocations/stats",
]


@pytest.mark.parametrize("path", MIGRATED_GET_PATHS)
def test_zero_uuid_rejected_at_migrated_path(monkeypatch, path):
    c = _gate_client(monkeypatch)
    resp = c.get(path, headers={"X-Tenant-Id": ZERO_UUID})
    assert resp.status_code == 401, (
        f"{path} aceitou zero UUID — fail-closed regrediu; got {resp.status_code}"
    )


@pytest.mark.parametrize("path", MIGRATED_GET_PATHS)
def test_missing_header_rejected_at_migrated_path(monkeypatch, path):
    c = _gate_client(monkeypatch)
    resp = c.get(path)
    assert resp.status_code == 401, resp.text


def test_valid_dev_tenant_passes_dep_gate_at_migrated_path(monkeypatch):
    c = _gate_client(monkeypatch)
    resp = c.get("/v1/workforce/allocations", headers={"X-Tenant-Id": DEV_TENANT})
    assert resp.status_code != 401, resp.text


def test_production_requires_jwt_at_migrated_path(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production", raising=False)
    app = FastAPI()
    app.include_router(workforce_router)
    app.dependency_overrides[get_session] = _stub_session
    c = TestClient(app, raise_server_exceptions=False)

    resp = c.get("/v1/workforce/allocations", headers={"X-Tenant-Id": DEV_TENANT})
    assert resp.status_code == 401, resp.text
    assert "JWT" in resp.json().get("detail", "")


# ─── Contrato com handler legacy (shape preservada) ───────────────────


class _StatsSession:
    """Sessão fake mínima para testar shape do `/stats`.

    Cada `.execute()` devolve um resultado que serve `scalar()` (count
    queries) ou `.all()` (top_phases/top_employees). A diferenciação é
    feita por inspecção da query string — group_by → all().
    """

    def __init__(self, counts: dict, top_phases: list, top_employees: list):
        self._counts = counts
        self._top_phases = top_phases
        self._top_employees = top_employees
        self._call_count = 0

    async def execute(self, stmt):
        text = str(stmt).lower()
        # 4 count queries em ordem: total, unique_employees, unique_orders, as_leader
        # 2 group_by queries: top_phases, top_employees
        # SQLAlchemy compila para "GROUP BY" (com espaço), não "group_by".

        if "group by" in text and "phase_name" in text:
            rows = self._top_phases

            class _Rows:
                def all(self_inner):
                    return rows

            return _Rows()

        if "group by" in text and "employee_name" in text:
            rows = self._top_employees

            class _Rows:
                def all(self_inner):
                    return rows

            return _Rows()

        # count queries — devolvem scalar
        self._call_count += 1
        order = ["total", "unique_employees", "unique_orders", "as_leader"]
        key = order[(self._call_count - 1) % len(order)]
        value = self._counts.get(key, 0)

        class _Scalar:
            def scalar(self_inner):
                return value

        return _Scalar()

    async def commit(self):
        pass


class _ListSession:
    """Sessão para o handler paginado — devolve scalar() para count,
    e scalars().all() para a query principal.
    """

    def __init__(self, allocations):
        self._allocations = list(allocations)
        self._count_returned = False

    async def execute(self, stmt):
        text = str(stmt).lower()
        if not self._count_returned and ("count" in text and "from (select" in text):
            self._count_returned = True
            count = len(self._allocations)

            class _Scalar:
                def scalar(self_inner):
                    return count

            return _Scalar()

        allocations = self._allocations

        class _R:
            def scalars(self_inner):
                return self_inner

            def all(self_inner):
                return list(allocations)

            def scalar(self_inner):
                return len(allocations)

        return _R()

    async def commit(self):
        pass


def _client_for(session) -> TestClient:
    app = FastAPI()
    app.include_router(workforce_router)
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[require_tenant_header] = lambda: TENANT
    return TestClient(app)


def test_list_allocations_paginated_shape():
    client = _client_for(_ListSession([]))
    resp = client.get("/v1/workforce/allocations?page=1&pageSize=20")
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


def test_stats_shape_matches_legacy():
    """`GET /v1/workforce/allocations/stats` devolve o shape legacy:
    `total/uniqueEmployees/uniqueOrders/asLeader/avgPerEmployee/topPhases/topEmployees`."""
    session = _StatsSession(
        counts={
            "total": 100,
            "unique_employees": 25,
            "unique_orders": 40,
            "as_leader": 10,
        },
        top_phases=[("Laminagem", 30), ("Montagem", 20)],
        top_employees=[("Joao", 15), ("Maria", 12)],
    )
    client = _client_for(session)
    resp = client.get("/v1/workforce/allocations/stats")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == {
        "total",
        "uniqueEmployees",
        "uniqueOrders",
        "asLeader",
        "avgPerEmployee",
        "topPhases",
        "topEmployees",
    }
    assert body["total"] == 100
    assert body["uniqueEmployees"] == 25
    assert body["avgPerEmployee"] == 4.0  # 100/25
    assert body["topPhases"] == [
        {"phase": "Laminagem", "count": 30},
        {"phase": "Montagem", "count": 20},
    ]
    assert body["topEmployees"] == [
        {"employee": "Joao", "count": 15},
        {"employee": "Maria", "count": 12},
    ]
