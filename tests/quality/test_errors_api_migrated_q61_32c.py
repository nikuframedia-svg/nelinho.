"""Q.61.32c — endpoints errors migrados de /api/* para /v1/quality/errors/*.

Junta:

1. **fail-closed tenant** (zero UUID + missing header + prod-mode JWT)
   nos 2 paths novos — pin do invariante Q.12 Onda 0.1 / Q.18.A.4.
2. **Cobertura comportamental herdada** do `test_production_errors_q22c.py`
   (Sprint Q.22.C): empty/populated, pagination, filter params, stats
   aggregation, DB-down fail-soft. Migrado para os paths novos.

Quando Q.61.32d apagar `src/legacy/`, este ficheiro é a única fonte
de testes para estes paths.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import AsyncIterator
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.quality.api import router as quality_router
from src.shared.config import settings
from src.shared.database import get_session


ZERO_UUID = "00000000-0000-0000-0000-000000000000"
DEV_TENANT = "00000000-0000-0000-0000-000000000001"
TENANT = UUID(DEV_TENANT)


# ─── Fail-closed tenant (Q.12 Onda 0.1 / Q.18.A.4) ────────────────────


async def _stub_session() -> AsyncIterator[AsyncMock]:
    sess = AsyncMock()
    yield sess


def _gate_client(monkeypatch) -> TestClient:
    monkeypatch.setattr(settings, "environment", "development", raising=False)
    app = FastAPI()
    app.include_router(quality_router)
    app.dependency_overrides[get_session] = _stub_session
    return TestClient(app, raise_server_exceptions=False)


MIGRATED_GET_PATHS = [
    "/v1/quality/errors",
    "/v1/quality/errors/stats",
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
    resp = c.get("/v1/quality/errors", headers={"X-Tenant-Id": DEV_TENANT})
    assert resp.status_code != 401, resp.text


def test_production_requires_jwt_at_migrated_path(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production", raising=False)
    app = FastAPI()
    app.include_router(quality_router)
    app.dependency_overrides[get_session] = _stub_session
    c = TestClient(app, raise_server_exceptions=False)

    resp = c.get("/v1/quality/errors", headers={"X-Tenant-Id": DEV_TENANT})
    assert resp.status_code == 401, resp.text
    assert "JWT" in resp.json().get("detail", "")


# ─── Cobertura comportamental Q.22.C migrada ──────────────────────────


def _result(*, scalar=None, rows=None, scalars=None):
    """A stand-in for an AsyncSession result row set."""
    return SimpleNamespace(
        scalar=lambda: scalar,
        all=lambda: list(rows or []),
        scalars=lambda: SimpleNamespace(all=lambda: list(scalars or [])),
    )


def _build_app(execute_results):
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=list(execute_results))

    async def _fake_session():
        yield session

    app = FastAPI()
    app.include_router(quality_router)
    app.dependency_overrides[get_session] = _fake_session
    return app


def _build_app_db_down():
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=RuntimeError("OperationalError: refused"))

    async def _fake_session():
        yield session

    app = FastAPI()
    app.include_router(quality_router)
    app.dependency_overrides[get_session] = _fake_session
    return app


def _error_row(severity=2, order_id=None):
    return SimpleNamespace(
        id=uuid4(),
        order_id=order_id,
        phase_name="Laminagem",
        eval_phase_name="Desmolde",
        description="Bolha de resina",
        severity=severity,
    )


def _headers():
    return {"X-Tenant-Id": str(TENANT)}


def test_list_errors_empty():
    app = _build_app([_result(scalar=0), _result(scalars=[])])
    resp = TestClient(app).get("/v1/quality/errors", headers=_headers())

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == []
    assert body["total"] == 0
    assert body["totalPages"] == 0
    assert body["hasNextPage"] is False
    assert body["hasPreviousPage"] is False


def test_list_errors_maps_rows_to_frontend_shape():
    rows = [_error_row(severity=3, order_id=uuid4()), _error_row(severity=1)]
    app = _build_app([_result(scalar=2), _result(scalars=rows)])
    resp = TestClient(app).get("/v1/quality/errors", headers=_headers())

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    first = body["data"][0]
    assert set(first) == {
        "id", "orderId", "phaseName", "evalPhaseName",
        "description", "severity", "severityLabel",
    }
    assert first["severity"] == 3
    assert first["severityLabel"] == "Critical"
    assert first["phaseName"] == "Laminagem"
    assert first["evalPhaseName"] == "Desmolde"
    assert body["data"][1]["severityLabel"] == "Minor"
    assert body["data"][1]["orderId"] is None


def test_list_errors_pagination_flags():
    """page 1 of 3 → hasNextPage True, hasPreviousPage False."""
    rows = [_error_row() for _ in range(20)]
    app = _build_app([_result(scalar=50), _result(scalars=rows)])
    resp = TestClient(app).get(
        "/v1/quality/errors?page=1&pageSize=20", headers=_headers()
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["totalPages"] == 3
    assert body["hasNextPage"] is True
    assert body["hasPreviousPage"] is False


def test_list_errors_accepts_frontend_filter_params():
    """severity / phase / search / sortBy must not 422 — frontend sends them."""
    app = _build_app([_result(scalar=0), _result(scalars=[])])
    resp = TestClient(app).get(
        "/v1/quality/errors?severity=3&phase=Laminagem&search=resina"
        "&sortBy=description&sortOrder=asc",
        headers=_headers(),
    )
    assert resp.status_code == 200


def test_errors_stats_aggregates():
    app = _build_app([
        _result(scalar=10),                                  # total
        _result(rows=[(1, 5), (2, 3), (3, 2)]),              # by severity
        _result(scalar=7),                                   # ordersWithErrors
        _result(rows=[("Bolha de resina", 4)]),              # topDescriptions
        _result(rows=[("Laminagem", 6)]),                    # topPhases
    ])
    resp = TestClient(app).get("/v1/quality/errors/stats", headers=_headers())

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 10
    assert body["bySeverity"] == {"minor": 5, "major": 3, "critical": 2}
    assert body["ordersWithErrors"] == 7
    assert body["topDescriptions"] == [{"description": "Bolha de resina", "count": 4}]
    assert body["topPhases"] == [{"phase": "Laminagem", "count": 6}]


def test_errors_stats_empty_table():
    app = _build_app([
        _result(scalar=0),
        _result(rows=[]),
        _result(scalar=0),
        _result(rows=[]),
        _result(rows=[]),
    ])
    resp = TestClient(app).get("/v1/quality/errors/stats", headers=_headers())

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["bySeverity"] == {"minor": 0, "major": 0, "critical": 0}
    assert body["ordersWithErrors"] == 0
    assert body["topDescriptions"] == []
    assert body["topPhases"] == []


def test_list_errors_db_down_returns_empty_page_not_500():
    """DB unavailable → explicit empty page, never a 404/500."""
    resp = TestClient(_build_app_db_down()).get(
        "/v1/quality/errors", headers=_headers()
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == []
    assert body["total"] == 0


def test_errors_stats_db_down_returns_empty_stats_not_500():
    """DB unavailable → explicit empty stats, never a 404/500."""
    resp = TestClient(_build_app_db_down()).get(
        "/v1/quality/errors/stats", headers=_headers()
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["bySeverity"] == {"minor": 0, "major": 0, "critical": 0}
