"""
Tests for src.core.api.tenant_config (Sprint L.3).

Uses FastAPI's TestClient against an app that mounts only the tenant_config
router + a stubbed `get_session`. Keeps the blast radius small (no main.py
import, no Kafka, no pandas/ortools).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.api.tenant_config import router as tenant_config_router
from src.core.models.tenant_configuration import TenantConfiguration
from src.core.services.tenant_config_service import _reset_cache_for_tests
from src.shared.database import get_session
from tests.conftest import FakeSession, TEST_TENANT_ID


@pytest.fixture(autouse=True)
def _stub_publish(monkeypatch):
    async def fake_publish(_topic, _event):
        return True

    monkeypatch.setattr(
        "src.shared.kafka_client.publish_event",
        fake_publish,
        raising=True,
    )


@pytest.fixture(autouse=True)
def _clear_cache():
    _reset_cache_for_tests()


@pytest.fixture
def fake_session_and_client():
    """Return (fake_session, TestClient) with a stubbed get_session dependency."""
    session = FakeSession()

    async def _override_session():
        yield session

    app = FastAPI()
    app.include_router(tenant_config_router)
    app.dependency_overrides[get_session] = _override_session

    client = TestClient(app)
    return session, client


def _row(
    tenant_id: UUID,
    category: str,
    key: str,
    value: Any,
    data_type: str = "int",
    valid_to: datetime | None = None,
    config_id: UUID | None = None,
) -> TenantConfiguration:
    return TenantConfiguration(
        id=config_id or uuid4(),
        tenant_id=tenant_id,
        category=category,
        key=key,
        value=TenantConfiguration.wrap(value),
        data_type=data_type,
        valid_from=datetime.utcnow(),
        valid_to=valid_to,
        created_at=datetime.utcnow(),
        last_modified_at=datetime.utcnow(),
    )


_HEADERS = {
    "X-Tenant-Id": str(TEST_TENANT_ID),
    "X-User-Id": "00000000-0000-0000-0000-0000000000aa",
}


# ---------------------------------------------------------------------------
# GET /{category}
# ---------------------------------------------------------------------------

def test_list_category(fake_session_and_client):
    session, client = fake_session_and_client
    session.queue_scalars([
        _row(TEST_TENANT_ID, "planning", "cpo.ga.gen_count", 200),
        _row(TEST_TENANT_ID, "planning", "fitness.makespan_weight", 0.20, data_type="float"),
    ])
    resp = client.get("/v1/config/planning", headers=_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["category"] == "planning"
    assert body["values"] == {
        "cpo.ga.gen_count": 200,
        "fitness.makespan_weight": 0.20,
    }


def test_list_category_unknown(fake_session_and_client):
    _, client = fake_session_and_client
    resp = client.get("/v1/config/not_real", headers=_HEADERS)
    assert resp.status_code == 400


def test_requires_tenant_header(fake_session_and_client):
    _, client = fake_session_and_client
    resp = client.get("/v1/config/planning")
    # Sprint S2: missing tenant header now returns 401 from auth layer
    # (semantically correct — header was Required(...) returning 422 before).
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /{category}/{key}
# ---------------------------------------------------------------------------

def test_set_key_creates_entry(fake_session_and_client):
    session, client = fake_session_and_client
    session.queue_scalar(None)  # no previous row

    resp = client.post(
        "/v1/config/planning/cpo.ga.gen_count",
        headers=_HEADERS,
        json={"value": 200, "data_type": "int"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["value"] == 200
    assert body["data_type"] == "int"
    assert body["valid_to"] is None


def test_set_key_rejects_bad_data_type(fake_session_and_client):
    session, client = fake_session_and_client
    # `set` fails before hitting the DB, so no queued rows needed.
    resp = client.post(
        "/v1/config/planning/k",
        headers=_HEADERS,
        json={"value": 1, "data_type": "bigint"},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /{category}/{key} + history
# ---------------------------------------------------------------------------

def test_get_key_returns_current(fake_session_and_client):
    session, client = fake_session_and_client
    cid = uuid4()
    session.queue_scalars([
        _row(TEST_TENANT_ID, "planning", "k", 2, config_id=cid),
        _row(
            TEST_TENANT_ID, "planning", "k", 1,
            valid_to=datetime.utcnow(),
        ),
    ])
    resp = client.get("/v1/config/planning/k", headers=_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["value"] == 2
    assert body["id"] == str(cid)


def test_get_key_404_when_missing(fake_session_and_client):
    session, client = fake_session_and_client
    session.queue_scalars([])
    resp = client.get("/v1/config/planning/k", headers=_HEADERS)
    assert resp.status_code == 404


def test_history_returns_all_versions(fake_session_and_client):
    session, client = fake_session_and_client
    session.queue_scalars([
        _row(TEST_TENANT_ID, "planning", "k", 3),
        _row(TEST_TENANT_ID, "planning", "k", 2, valid_to=datetime.utcnow()),
        _row(TEST_TENANT_ID, "planning", "k", 1, valid_to=datetime.utcnow()),
    ])
    resp = client.get("/v1/config/planning/k/history", headers=_HEADERS)
    assert resp.status_code == 200
    assert [e["value"] for e in resp.json()] == [3, 2, 1]


# ---------------------------------------------------------------------------
# PATCH /bulk
# ---------------------------------------------------------------------------

def test_bulk_set(fake_session_and_client):
    session, client = fake_session_and_client
    session.queue_scalar(None)
    session.queue_scalar(None)
    resp = client.patch(
        "/v1/config/bulk",
        headers=_HEADERS,
        json={"entries": [
            {"category": "planning", "key": "a", "value": 1, "data_type": "int"},
            {"category": "mold", "key": "maintenance_threshold_cycles", "value": 500, "data_type": "int"},
        ]},
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 2


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------

def test_export_snapshot(fake_session_and_client):
    session, client = fake_session_and_client
    session.queue_scalars([
        _row(TEST_TENANT_ID, "planning", "a", 1),
        _row(TEST_TENANT_ID, "mold", "x", 500),
    ])
    resp = client.get("/v1/config/snapshot/export", headers=_HEADERS)
    assert resp.status_code == 200
    assert resp.json() == {
        "planning": {"a": {"value": 1, "data_type": "int"}},
        "mold": {"x": {"value": 500, "data_type": "int"}},
    }


def test_import_snapshot(fake_session_and_client):
    session, client = fake_session_and_client
    session.queue_scalar(None)
    session.queue_scalar(None)
    resp = client.post(
        "/v1/config/snapshot/import",
        headers=_HEADERS,
        json={
            "planning": {"a": {"value": 1, "data_type": "int"}},
            "mold": {"x": {"value": 500, "data_type": "int"}},
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {"written": 2}


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------

def test_rollback_missing_returns_404(fake_session_and_client):
    session, client = fake_session_and_client
    session.queue_scalar(None)
    resp = client.post(
        f"/v1/config/rollback/{uuid4()}",
        headers=_HEADERS,
    )
    assert resp.status_code == 404


def test_rollback_restores_old_value(fake_session_and_client):
    session, client = fake_session_and_client
    cid = uuid4()
    old = _row(TEST_TENANT_ID, "planning", "k", 42, config_id=cid)
    session.queue_scalar(old)      # rollback lookup
    session.queue_scalar(None)     # set → _current_row
    resp = client.post(f"/v1/config/rollback/{cid}", headers=_HEADERS)
    assert resp.status_code == 200, resp.text
    assert resp.json()["value"] == 42
