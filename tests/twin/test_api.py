"""Sprint Q.10 Fase A.2 — Twin API endpoint tests.

The TwinService is mocked end-to-end so the tests only assert wiring
(routes, status codes, payload shape, dependency overrides). Unit
behaviour of the service is covered by `test_service.py`.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Optional
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.twin.api import (
    get_current_user,
    get_tenant_id,
    get_twin_service,
    router as twin_router,
)
from src.twin.models import ScenarioStatus


TENANT = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TEST_USER = "test_user"


def _scenario_obj(*, status: str = ScenarioStatus.DRAFT.value):
    return SimpleNamespace(
        id=uuid4(),
        tenant_id=TENANT,
        title="My Scenario",
        description="desc",
        status=status,
        deltas=[],
        baseline_state={"throughput_eur_day": {"value": 30000.0}},
        simulation_result=None,
        scenario_hash=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        simulated_at=None,
        base_scenario_id=None,
        created_by="luis",
    )


def _build_app(service):
    app = FastAPI()
    app.include_router(twin_router)

    async def _override():
        return service

    # Sprint Q.12 Onda 0.1: tenant + user header guards now 401 on
    # missing headers; tests inject them via dependency_overrides so we
    # don't have to thread them through every request.
    app.dependency_overrides[get_twin_service] = _override
    app.dependency_overrides[get_tenant_id] = lambda: TENANT
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    return app


def test_baseline_endpoint_returns_available_and_blocked_buckets():
    service = AsyncMock()
    # _create_baseline_state is sync — must be a regular Mock-like attr
    service._create_baseline_state = lambda: {
        "throughput_eur_day": {"value": 30000.0, "status": "OK"},
        "oee": {"status": "BLOCKED", "reason": "no machine data"},
        "_metadata": {"data_version": "test"},
    }
    client = TestClient(_build_app(service))
    resp = client.get("/v1/twin/baseline")
    assert resp.status_code == 200
    body = resp.json()
    assert "throughput_eur_day" in body["available_metrics"]
    assert "oee" in body["blocked_metrics"]
    assert body["summary"]["available_count"] == 1
    assert body["summary"]["blocked_count"] == 1


def test_create_scenario_returns_201_and_persists():
    service = AsyncMock()
    sc = _scenario_obj()
    service.create_scenario = AsyncMock(return_value=sc)
    client = TestClient(_build_app(service))
    resp = client.post(
        "/v1/twin/scenarios",
        json={"title": "Test", "description": "d"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["title"] == "My Scenario"
    assert body["status"] == ScenarioStatus.DRAFT.value


def test_list_scenarios_with_status_filter():
    service = AsyncMock()
    sc1 = _scenario_obj()
    sc2 = _scenario_obj(status=ScenarioStatus.SIMULATED.value)
    service.list_scenarios = AsyncMock(return_value=[sc1, sc2])
    client = TestClient(_build_app(service))
    resp = client.get("/v1/twin/scenarios")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2


def test_apply_delta_returns_delta_count():
    service = AsyncMock()
    sc = _scenario_obj()
    delta_obj = SimpleNamespace(id=uuid4())
    service.apply_delta = AsyncMock(return_value=delta_obj)
    sc.deltas = [SimpleNamespace(id=uuid4())]  # after apply
    service.get_scenario = AsyncMock(return_value=sc)
    client = TestClient(_build_app(service))
    resp = client.post(
        f"/v1/twin/scenarios/{sc.id}/apply-delta",
        json={
            "entity_type": "machine", "entity_key": "M1",
            "patch": {"available": False},
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["delta_count"] == 1
    assert body["scenario_id"] == str(sc.id)


def test_simulate_scenario_returns_simulation_result():
    service = AsyncMock()
    sc_id = uuid4()
    service.simulate = AsyncMock(return_value={
        "before": {"x": 1},
        "after": {"x": 2},
        "delta_summary": {"x": 1},
        "simulated_at": datetime.utcnow().isoformat(),
    })
    client = TestClient(_build_app(service))
    resp = client.post(f"/v1/twin/scenarios/{sc_id}/simulate")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "simulated"
    assert "kpis" in body
    assert "comparison" in body


def test_solve_without_operations_returns_insufficient_data():
    service = AsyncMock()
    sc_id = uuid4()
    service.solve = AsyncMock(return_value={
        "scenario_id": str(sc_id),
        "objective": "maximize_oee",
        "status": "INSUFFICIENT_DATA",
        "projected_kpis": {},
        "solved_at": datetime.utcnow().isoformat(),
    })
    client = TestClient(_build_app(service))
    resp = client.post(
        f"/v1/twin/scenarios/{sc_id}/solve",
        json={},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "INSUFFICIENT_DATA"


def test_delete_scenario_returns_204():
    service = AsyncMock()
    service.delete_scenario = AsyncMock(return_value=True)
    client = TestClient(_build_app(service))
    resp = client.delete(f"/v1/twin/scenarios/{uuid4()}")
    assert resp.status_code == 204


def test_delete_scenario_unknown_returns_404():
    service = AsyncMock()
    service.delete_scenario = AsyncMock(return_value=False)
    client = TestClient(_build_app(service))
    resp = client.delete(f"/v1/twin/scenarios/{uuid4()}")
    assert resp.status_code == 404
