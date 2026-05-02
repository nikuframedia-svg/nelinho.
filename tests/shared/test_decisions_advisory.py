"""Sprint Q.9 (2.2/2.3) — execute / rollback advisory mode endpoints.

Until Sprint G ties the ERP side, the decisions endpoints update the
audit trail and publish realtime events but do NOT physically mutate
the ERP / schedule. Tests:
* execute happy path → status EXECUTED, advisory_mode True
* execute on non-APPROVED → 400
* rollback happy path → status ROLLED_BACK, advisory_mode True
* rollback after 24h window → 400
* rollback on non-EXECUTED → 400
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.shared.api.decisions import router as decisions_router
from src.shared.database import get_session
from src.shared.models.governance import DecisionStatus


TENANT = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def _decision(status_value: str, *, executed_at: datetime | None = None):
    return SimpleNamespace(
        id=uuid4(),
        tenant_id=TENANT,
        status=status_value,
        executed_at=executed_at,
        rolled_back_at=None,
        before_state={"workers": ["w1", "w2"]},
    )


def _build_app(decision):
    session = AsyncMock()
    session.get = AsyncMock(return_value=decision)
    session.commit = AsyncMock()

    async def _fake_session():
        yield session

    app = FastAPI()
    app.include_router(decisions_router, prefix="/v1/shared")
    app.dependency_overrides[get_session] = _fake_session
    return app


@pytest.fixture(autouse=True)
def _stub_publish(monkeypatch):
    """Don't hit Kafka in tests — return success silently."""
    async def fake_publish(_topic, _event):
        return True

    monkeypatch.setattr(
        "src.shared.kafka_client.publish_event", fake_publish, raising=True,
    )


def test_execute_advisory_marks_executed_and_publishes():
    decision = _decision(DecisionStatus.APPROVED.value)
    client = TestClient(_build_app(decision))
    resp = client.post(
        f"/v1/shared/decisions/{decision.id}/execute",
        headers={"x-tenant-id": str(TENANT)},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "executed"
    assert body["advisory_mode"] is True
    assert decision.status == DecisionStatus.EXECUTED.value
    assert decision.executed_at is not None


def test_execute_rejects_when_not_approved():
    decision = _decision(DecisionStatus.PROPOSED.value)
    client = TestClient(_build_app(decision))
    resp = client.post(
        f"/v1/shared/decisions/{decision.id}/execute",
        headers={"x-tenant-id": str(TENANT)},
    )
    assert resp.status_code == 400


def test_rollback_advisory_marks_rolled_back_and_returns_before_state():
    decision = _decision(
        DecisionStatus.EXECUTED.value,
        executed_at=datetime.utcnow() - timedelta(hours=1),
    )
    client = TestClient(_build_app(decision))
    resp = client.post(
        f"/v1/shared/decisions/{decision.id}/rollback",
        headers={"x-tenant-id": str(TENANT)},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "rolled_back"
    assert body["advisory_mode"] is True
    assert body["before_state"] == {"workers": ["w1", "w2"]}
    assert decision.status == DecisionStatus.ROLLED_BACK.value


def test_rollback_rejects_after_24h_window():
    decision = _decision(
        DecisionStatus.EXECUTED.value,
        executed_at=datetime.utcnow() - timedelta(hours=25),
    )
    client = TestClient(_build_app(decision))
    resp = client.post(
        f"/v1/shared/decisions/{decision.id}/rollback",
        headers={"x-tenant-id": str(TENANT)},
    )
    assert resp.status_code == 400


def test_rollback_rejects_when_not_executed():
    decision = _decision(DecisionStatus.APPROVED.value)
    client = TestClient(_build_app(decision))
    resp = client.post(
        f"/v1/shared/decisions/{decision.id}/rollback",
        headers={"x-tenant-id": str(TENANT)},
    )
    assert resp.status_code == 400
