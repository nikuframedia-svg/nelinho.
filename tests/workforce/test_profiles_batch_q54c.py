"""Sprint Q.54.C — endpoint batch de perfis de operador.

A auditoria: a página Fábrica, ao clicar num barco, disparava ~60 pedidos
HTTP (20 operadores × 3 endpoints: quality-score / skill-matrix /
qualification-metrics). O `POST /v1/workforce/employees/profiles` colapsa
tudo numa só resposta.

Estes testes batem no router via TestClient e monkeypatcham o
`EmployeeExtrasService` — teste unitário de wiring, não tocam DB.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.shared.database import get_session
from src.workforce.employee_extras_api import router as employee_extras_router
from src.workforce.employee_extras_service import (
    QualificationMetrics,
    QualityScoreResult,
    SkillMatrixRow,
)
from tests.conftest import FakeSession

_TENANT = UUID("11111111-1111-1111-1111-111111111111")
_HEADERS = {"X-Tenant-Id": str(_TENANT)}


def _client(session: FakeSession) -> TestClient:
    async def _override():
        yield session

    app = FastAPI()
    app.include_router(employee_extras_router)
    app.dependency_overrides[get_session] = _override
    return TestClient(app)


@pytest.fixture
def _stub_service(monkeypatch):
    """EmployeeExtrasService whose three reads return canned data."""

    async def _quality(self, employee_id):
        return QualityScoreResult(
            employee_id=employee_id, score=8.5, defects=2, operations=40,
            defect_rate=0.06, method="laplace_smoothed",
        )

    async def _skills(self, employee_id):
        return [
            SkillMatrixRow(
                phase_id="F1", phase_name="Laminagem", can_do=True,
                nivel=2, ops_count=12, last_used_at=None,
            ),
        ]

    async def _metrics(self, employee_id, *, phase_id=None, area_group=None):
        return QualificationMetrics(
            employee_id=employee_id, recency_days=3, versatility=5,
            productivity=1.5, ops_total=30, scope=None,
        )

    monkeypatch.setattr(
        "src.workforce.employee_extras_service.EmployeeExtrasService.quality_score",
        _quality, raising=True,
    )
    monkeypatch.setattr(
        "src.workforce.employee_extras_service.EmployeeExtrasService.skill_matrix",
        _skills, raising=True,
    )
    monkeypatch.setattr(
        "src.workforce.employee_extras_service.EmployeeExtrasService.qualification_metrics",
        _metrics, raising=True,
    )


def test_profiles_batch_requires_tenant_header(_stub_service):
    resp = _client(FakeSession()).post(
        "/v1/workforce/employees/profiles",
        json={"employee_ids": [str(uuid4())]},
    )
    # require_tenant_header (canónico) → 401 sem tenant (auth), não 422 (validação)
    assert resp.status_code == 401


def test_profiles_batch_empty_list_rejected(_stub_service):
    resp = _client(FakeSession()).post(
        "/v1/workforce/employees/profiles",
        json={"employee_ids": []},
        headers=_HEADERS,
    )
    assert resp.status_code == 422


def test_profiles_batch_aggregates_three_sources_per_employee(_stub_service):
    ids = [str(uuid4()) for _ in range(3)]
    resp = _client(FakeSession()).post(
        "/v1/workforce/employees/profiles",
        json={"employee_ids": ids},
        headers=_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["requested"] == 3
    assert body["returned"] == 3
    profile = body["profiles"][0]
    # All three sub-reads aggregated into one entry.
    assert profile["quality_score"]["score"] == 8.5
    assert profile["skill_matrix"]["total"] == 1
    assert profile["skill_matrix"]["phases"][0]["phase_id"] == "F1"
    assert profile["qualification_metrics"]["recency_days"] == 3
    assert profile["qualification_metrics"]["versatility"] == 5


def test_profiles_batch_deduplicates_ids(_stub_service):
    eid = str(uuid4())
    resp = _client(FakeSession()).post(
        "/v1/workforce/employees/profiles",
        json={"employee_ids": [eid, eid, eid]},
        headers=_HEADERS,
    )
    assert resp.status_code == 200
    body = resp.json()
    # Requested counts the raw list; returned is the deduplicated set.
    assert body["requested"] == 3
    assert body["returned"] == 1


def test_profiles_batch_one_failure_does_not_kill_batch(monkeypatch):
    """A failing operator degrades to an `error` entry; others still return."""
    good_id = uuid4()
    bad_id = uuid4()

    async def _quality(self, employee_id):
        if employee_id == bad_id:
            raise RuntimeError("simulated DB hiccup")
        return QualityScoreResult(
            employee_id=employee_id, score=9.0, defects=0, operations=10,
            defect_rate=0.0, method="laplace_smoothed",
        )

    async def _skills(self, employee_id):
        return []

    async def _metrics(self, employee_id, *, phase_id=None, area_group=None):
        return QualificationMetrics(
            employee_id=employee_id, recency_days=None, versatility=0,
            productivity=None, ops_total=0, scope=None,
        )

    monkeypatch.setattr(
        "src.workforce.employee_extras_service.EmployeeExtrasService.quality_score",
        _quality, raising=True,
    )
    monkeypatch.setattr(
        "src.workforce.employee_extras_service.EmployeeExtrasService.skill_matrix",
        _skills, raising=True,
    )
    monkeypatch.setattr(
        "src.workforce.employee_extras_service.EmployeeExtrasService.qualification_metrics",
        _metrics, raising=True,
    )

    resp = _client(FakeSession()).post(
        "/v1/workforce/employees/profiles",
        json={"employee_ids": [str(good_id), str(bad_id)]},
        headers=_HEADERS,
    )
    assert resp.status_code == 200
    by_id = {p["employee_id"]: p for p in resp.json()["profiles"]}
    assert "error" in by_id[str(bad_id)]
    assert "quality_score" in by_id[str(good_id)]
