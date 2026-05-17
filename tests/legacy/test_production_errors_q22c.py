"""Sprint Q.22.C — `/api/errors` + `/api/errors/stats` over ProductionError.

Before Q.22.C both endpoints returned hard-coded empty structures
behind a ``# TODO: Implement when ProductionError model is available``.
Now they query the ``plan.production_errors`` table.

The production models need PostgreSQL (schemas + indexes), so these
tests drive the endpoints with a mocked session whose ``execute``
returns canned results in call order.

Covered:
* empty table → valid empty ``ErrorsResponse`` / ``ErrorsStats`` shape
* populated list → rows mapped to the frontend ``ProductionError``
  shape incl. ``severityLabel`` + camelCase keys
* stats → severity buckets + ordersWithErrors + top descriptions/phases
* a DB-unavailable error degrades to an explicit empty page (no 404/500)
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.legacy.api import router as legacy_router
from src.shared.database import get_session

TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _result(*, scalar=None, rows=None, scalars=None):
    """A stand-in for an AsyncSession result row set."""
    return SimpleNamespace(
        scalar=lambda: scalar,
        all=lambda: list(rows or []),
        scalars=lambda: SimpleNamespace(all=lambda: list(scalars or [])),
    )


def _build_app(execute_results):
    """Wire a TestClient whose session.execute yields results in order."""
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=list(execute_results))

    async def _fake_session():
        yield session

    app = FastAPI()
    app.include_router(legacy_router)
    app.dependency_overrides[get_session] = _fake_session
    return app


def _build_app_db_down():
    """A session whose execute always raises an OperationalError-like error."""
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=RuntimeError("OperationalError: refused"))

    async def _fake_session():
        yield session

    app = FastAPI()
    app.include_router(legacy_router)
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
    resp = TestClient(app).get("/api/errors", headers=_headers())

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
    resp = TestClient(app).get("/api/errors", headers=_headers())

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    first = body["data"][0]
    # Frontend ProductionError contract — camelCase keys, no extras.
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
        "/api/errors?page=1&pageSize=20", headers=_headers()
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
        "/api/errors?severity=3&phase=Laminagem&search=resina"
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
    resp = TestClient(app).get("/api/errors/stats", headers=_headers())

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
    resp = TestClient(app).get("/api/errors/stats", headers=_headers())

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["bySeverity"] == {"minor": 0, "major": 0, "critical": 0}
    assert body["ordersWithErrors"] == 0
    assert body["topDescriptions"] == []
    assert body["topPhases"] == []


def test_list_errors_db_down_returns_empty_page_not_500():
    """DB unavailable → explicit empty page, never a 404/500."""
    resp = TestClient(_build_app_db_down()).get("/api/errors", headers=_headers())

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == []
    assert body["total"] == 0


def test_errors_stats_db_down_returns_empty_stats_not_500():
    """DB unavailable → explicit empty stats, never a 404/500."""
    resp = TestClient(_build_app_db_down()).get(
        "/api/errors/stats", headers=_headers()
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["bySeverity"] == {"minor": 0, "major": 0, "critical": 0}
