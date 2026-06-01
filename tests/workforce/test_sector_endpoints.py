"""Q.140.C — endpoints read de sectores + nível por sector por colaborador.

Bate nos routers via TestClient e monkeypatcha o SectorPreferenceService
(teste de wiring, sem DB). Cobre: lista dos 7 sectores; ranking de sector
inválido → 404; ranking vazio → 200 com {ranking:[],total:0} (nunca 500);
sector-levels devolve sempre os 7 grupos; X-Tenant-Id obrigatório.
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.shared.database import get_session
from src.workforce.employee_extras_api import router as employees_router
from src.workforce.levels import AREA_GROUPS
from src.workforce.sector_preference_api import router as sectors_router
from tests.conftest import FakeSession

_TENANT = UUID("11111111-1111-1111-1111-111111111111")
_HEADERS = {"X-Tenant-Id": str(_TENANT)}


def _client() -> TestClient:
    async def _override():
        yield FakeSession()

    app = FastAPI()
    app.include_router(sectors_router)
    app.include_router(employees_router)
    app.dependency_overrides[get_session] = _override
    return TestClient(app)


@pytest.fixture
def _stub_service(monkeypatch):
    async def _ranking(self, area_group, *, limit=100):
        # ranking não-vazio só para Laminagem; restantes vazios.
        if area_group == "Laminagem":
            return {
                "area_group": area_group,
                "level_scale": {"best": 3.0},
                "ranking": [
                    {"rank": 1, "employee_id": str(uuid4()), "employee_name": "Hugo",
                     "effective_level": 3.0, "source": "derived", "ops_total": 9000},
                ],
                "total": 1,
            }
        return {"area_group": area_group, "level_scale": {"best": 3.0}, "ranking": [], "total": 0}

    async def _per_emp(self, employee_id):
        return {
            "employee_id": str(employee_id),
            "employee_name": "Hugo",
            "employee_code": "27641",
            "level_scale": {"best": 3.0},
            "sectors": [{"area_group": g, "apt": g == "Laminagem"} for g in AREA_GROUPS],
        }

    monkeypatch.setattr(
        "src.workforce.sector_preference_service.SectorPreferenceService.sector_ranking",
        _ranking, raising=True,
    )
    monkeypatch.setattr(
        "src.workforce.sector_preference_service.SectorPreferenceService.per_employee_sector_levels",
        _per_emp, raising=True,
    )


def test_list_sectors_returns_seven_groups():
    r = _client().get("/v1/workforce/sectors", headers=_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["sectors"] == list(AREA_GROUPS)
    assert len(body["sectors"]) == 7
    assert body["level_scale"]["convention"] == "3=melhor, 1=pior"


def test_ranking_invalid_sector_is_404(_stub_service):
    r = _client().get(
        "/v1/workforce/sectors/ranking", params={"area_group": "Inexistente"}, headers=_HEADERS,
    )
    assert r.status_code == 404


def test_ranking_valid_sector_ok(_stub_service):
    r = _client().get(
        "/v1/workforce/sectors/ranking", params={"area_group": "Laminagem"}, headers=_HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["ranking"][0]["rank"] == 1


def test_ranking_empty_sector_is_200_not_500(_stub_service):
    # Cura/Moldes (com barra no nome) sem histórico → 200 vazio, não erro.
    r = _client().get(
        "/v1/workforce/sectors/ranking", params={"area_group": "Cura/Moldes"}, headers=_HEADERS,
    )
    assert r.status_code == 200
    assert r.json() == {
        "area_group": "Cura/Moldes", "level_scale": {"best": 3.0},
        "ranking": [], "total": 0,
    }


def test_ranking_requires_tenant_header(_stub_service):
    r = _client().get("/v1/workforce/sectors/ranking", params={"area_group": "Laminagem"})
    assert r.status_code == 422  # X-Tenant-Id em falta


def test_sector_levels_returns_seven_groups(_stub_service):
    eid = uuid4()
    r = _client().get(f"/v1/workforce/employees/{eid}/sector-levels", headers=_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert {s["area_group"] for s in body["sectors"]} == set(AREA_GROUPS)
    assert body["employee_code"] == "27641"
