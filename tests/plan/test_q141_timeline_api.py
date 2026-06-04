"""Q.141.D — endpoint GET /v1/plan/timeline/actuals.

TestClient + monkeypatch do TimelineActualsService (sem BD). Cobre validação
(400/422), branching de granularity (raw vs day) e o caminho best-effort.
"""
from __future__ import annotations

from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.plan.api.timeline import router as timeline_router
from src.shared.database import get_session

_TENANT = UUID("11111111-1111-1111-1111-111111111111")
_HEADERS = {"X-Tenant-Id": str(_TENANT)}


def _client() -> TestClient:
    async def _override():
        yield None  # service trata session=None como best-effort

    app = FastAPI()
    app.include_router(timeline_router, prefix="/v1/plan")
    app.dependency_overrides[get_session] = _override
    return TestClient(app)


@pytest.fixture
def _stub_service(monkeypatch):
    sample_items = [
        {"of_id": "OF1", "barco_nome": "K1", "phase_id": "5", "phase_nome": "Pintura",
         "start": "2026-05-01T08:00", "duration_min": 60, "worker_id": None, "worker_nome": None},
    ]

    async def _actuals(self, from_d, to_d, *, cap=5000):
        return sample_items, False

    async def _exps(self, from_d, to_d, *, cap=5000):
        return [{"of_id": "OF1", "barco_nome": "K1", "transport_date": "2026-05-01",
                 "modelo_id": "P1", "source": "transp_of"}], False

    monkeypatch.setattr(
        "src.plan.services.timeline_actuals_service.TimelineActualsService.actuals_items",
        _actuals, raising=True,
    )
    monkeypatch.setattr(
        "src.plan.services.timeline_actuals_service.TimelineActualsService.expeditions",
        _exps, raising=True,
    )


def test_to_before_from_is_400(_stub_service):
    r = _client().get("/v1/plan/timeline/actuals",
                      params={"from": "2026-05-10", "to": "2026-05-01"}, headers=_HEADERS)
    assert r.status_code == 400


def test_range_too_large_is_400(_stub_service):
    r = _client().get("/v1/plan/timeline/actuals",
                      params={"from": "2024-01-01", "to": "2026-12-31"}, headers=_HEADERS)
    assert r.status_code == 400


def test_invalid_group_by_is_400(_stub_service):
    r = _client().get("/v1/plan/timeline/actuals",
                      params={"from": "2026-05-01", "to": "2026-05-07", "group_by": "xpto"},
                      headers=_HEADERS)
    assert r.status_code == 400


def test_invalid_date_is_422(_stub_service):
    r = _client().get("/v1/plan/timeline/actuals",
                      params={"from": "ontem", "to": "2026-05-07"}, headers=_HEADERS)
    assert r.status_code == 422


def test_requires_tenant_header(_stub_service):
    r = _client().get("/v1/plan/timeline/actuals", params={"from": "2026-05-01", "to": "2026-05-07"})
    # require_tenant_header (canónico) → 401 sem tenant (auth), não 422 (validação)
    assert r.status_code == 401


def test_short_range_auto_is_raw(_stub_service):
    r = _client().get("/v1/plan/timeline/actuals",
                      params={"from": "2026-05-01", "to": "2026-05-07"}, headers=_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["granularity"] == "raw"
    assert len(body["items"]) == 1 and body["lanes"] == []
    assert len(body["expeditions"]) == 1


def test_long_range_auto_is_day_aggregated(_stub_service):
    r = _client().get("/v1/plan/timeline/actuals",
                      params={"from": "2026-04-01", "to": "2026-05-31"}, headers=_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["granularity"] == "day"
    assert body["group_by"] == "barco"  # default
    assert body["items"] == []
    assert len(body["lanes"]) == 1
    assert body["lanes"][0]["group_key"] == "OF1"


def test_limit_param_accepted(_stub_service):
    r = _client().get(
        "/v1/plan/timeline/actuals",
        params={"from": "2026-05-01", "to": "2026-05-07", "limit": 100}, headers=_HEADERS,
    )
    assert r.status_code == 200


def test_limit_too_large_is_422(_stub_service):
    r = _client().get(
        "/v1/plan/timeline/actuals",
        params={"from": "2026-05-01", "to": "2026-05-07", "limit": 99999}, headers=_HEADERS,
    )
    assert r.status_code == 422


def test_best_effort_empty_when_no_session():
    # Sem _stub_service: session=None → service devolve vazio → 200, nunca 5xx.
    r = _client().get("/v1/plan/timeline/actuals",
                      params={"from": "2026-05-01", "to": "2026-05-07"}, headers=_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == [] and body["expeditions"] == []
