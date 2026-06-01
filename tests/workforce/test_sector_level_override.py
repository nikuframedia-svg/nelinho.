"""Q.140.D — PATCH /sector-level: override manual de nível por sector.

Mesmo padrão do PATCH /skills: escreve PreferenceRule(workforce_override,
field='sector_level') + audit_change na MESMA tx, dedupe por (employee, field,
area_group). Testes via TestClient + FakeSession; audit_change é monkeypatched
para um recorder (testamos a construção da rule, não o interno do audit).
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.shared.database import get_session
from src.workforce.employee_extras_api import router as employees_router
from tests.conftest import FakeSession

_TENANT = UUID("11111111-1111-1111-1111-111111111111")
_HEADERS = {"X-Tenant-Id": str(_TENANT)}


def _client(session: FakeSession) -> TestClient:
    async def _override():
        yield session

    app = FastAPI()
    app.include_router(employees_router)
    app.dependency_overrides[get_session] = _override
    return TestClient(app)


@pytest.fixture
def _audit_recorder(monkeypatch):
    calls = []

    async def _fake_audit(session, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(
        "src.governance.audit_service.audit_change", _fake_audit, raising=True,
    )
    return calls


def test_invalid_sector_is_404(_audit_recorder):
    session = FakeSession()
    r = _client(session).patch(
        f"/v1/workforce/employees/{uuid4()}/sector-level",
        json={"area_group": "Inexistente", "nivel": 2.0},
        headers=_HEADERS,
    )
    assert r.status_code == 404
    assert session.added == []  # nada escrito


def test_nivel_out_of_range_is_422(_audit_recorder):
    r = _client(FakeSession()).patch(
        f"/v1/workforce/employees/{uuid4()}/sector-level",
        json={"area_group": "Pintura", "nivel": 5.0},
        headers=_HEADERS,
    )
    assert r.status_code == 422


def test_creates_preference_rule_with_clamped_nivel_and_audit(_audit_recorder):
    session = FakeSession()  # select existente → None → caminho INSERT
    eid = uuid4()
    r = _client(session).patch(
        f"/v1/workforce/employees/{eid}/sector-level",
        json={"area_group": "Pintura", "nivel": 2.7, "reason": "Mestre da pintura"},
        headers=_HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["nivel"] == 2.5  # 2.7 → meio-passo
    assert body["area_group"] == "Pintura"

    # PreferenceRule escrita com o predicate certo.
    rules = [o for o in session.added if o.__class__.__name__ == "PreferenceRule"]
    assert len(rules) == 1
    pred = rules[0].predicate
    assert pred["field"] == "sector_level"
    assert pred["area_group"] == "Pintura"
    assert pred["nivel"] == 2.5
    assert pred["employee_id"] == str(eid)

    # audit_change chamado na mesma tx + commit.
    assert len(_audit_recorder) == 1
    assert _audit_recorder[0]["entity_type"] == "preference_rule"
    assert session.commit_calls == 1


def test_existing_override_updates_not_duplicates(_audit_recorder):
    eid = uuid4()

    class _ExistingRule:
        def __init__(self):
            self.predicate = {
                "employee_id": str(eid), "field": "sector_level",
                "area_group": "Laminagem", "nivel": 1.0,
            }
            self.description = "old"

    session = FakeSession()
    session.queue_scalar(_ExistingRule())  # select existente → encontra

    r = _client(session).patch(
        f"/v1/workforce/employees/{eid}/sector-level",
        json={"area_group": "Laminagem", "nivel": 2.0},
        headers=_HEADERS,
    )
    assert r.status_code == 200
    # Caminho UPDATE: NENHUMA PreferenceRule nova adicionada.
    rules = [o for o in session.added if o.__class__.__name__ == "PreferenceRule"]
    assert rules == []
    assert session.commit_calls == 1
