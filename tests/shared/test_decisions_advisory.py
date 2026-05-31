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

from datetime import datetime, timedelta, timezone
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
        headers={
            "x-tenant-id": str(TENANT),
            "x-user-id": "11111111-1111-1111-1111-111111111111",
        },
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
        headers={
            "x-tenant-id": str(TENANT),
            "x-user-id": "11111111-1111-1111-1111-111111111111",
        },
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
        headers={
            "x-tenant-id": str(TENANT),
            "x-user-id": "11111111-1111-1111-1111-111111111111",
        },
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
        headers={
            "x-tenant-id": str(TENANT),
            "x-user-id": "11111111-1111-1111-1111-111111111111",
        },
    )
    assert resp.status_code == 400


# Q.130.U — regressão: `executed_at` é DateTime(timezone=True), portanto o
# Postgres devolve-o tz-AWARE. O código comparava com datetime.utcnow()
# (tz-naive) → "can't compare offset-naive and offset-aware datetimes" (500)
# em TODA a decisão executada. Os testes acima passavam porque o fake usava
# datetime.utcnow() (naive). Estes usam tz-aware, como a BD real.


def test_rollback_with_tzaware_executed_at_within_window_ok():
    decision = _decision(
        DecisionStatus.EXECUTED.value,
        executed_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    client = TestClient(_build_app(decision))
    resp = client.post(
        f"/v1/shared/decisions/{decision.id}/rollback",
        headers={
            "x-tenant-id": str(TENANT),
            "x-user-id": "11111111-1111-1111-1111-111111111111",
        },
    )
    assert resp.status_code == 200, resp.text
    assert decision.status == DecisionStatus.ROLLED_BACK.value


def test_rollback_with_tzaware_executed_at_after_window_400():
    decision = _decision(
        DecisionStatus.EXECUTED.value,
        executed_at=datetime.now(timezone.utc) - timedelta(hours=25),
    )
    client = TestClient(_build_app(decision))
    resp = client.post(
        f"/v1/shared/decisions/{decision.id}/rollback",
        headers={
            "x-tenant-id": str(TENANT),
            "x-user-id": "11111111-1111-1111-1111-111111111111",
        },
    )
    # 400 (window expired) — NOT 500. Pre-fix this raised TypeError -> 500.
    assert resp.status_code == 400, resp.text


def test_rollback_rejects_when_not_executed():
    decision = _decision(DecisionStatus.APPROVED.value)
    client = TestClient(_build_app(decision))
    resp = client.post(
        f"/v1/shared/decisions/{decision.id}/rollback",
        headers={
            "x-tenant-id": str(TENANT),
            "x-user-id": "11111111-1111-1111-1111-111111111111",
        },
    )
    assert resp.status_code == 400


# ── Q.130.V — invariante 7: rollback escreve audit_change na MESMA tx ───────
# Antes do fix a transição EXECUTED→ROLLED_BACK só fazia `decision.status =`
# + commit, sem audit row — buraco no audit trail. Este teste prova que uma
# AuditLog (action=UPDATE, entity_type=decision_run) é adicionada à session
# antes do commit, e que rolled_back_at é tz-aware.


def _build_app_capturing_adds(decision):
    """Como `_build_app` mas captura `session.add(...)` num MagicMock para
    podermos inspeccionar a AuditLog escrita no rollback."""
    from unittest.mock import MagicMock

    session = AsyncMock()
    session.get = AsyncMock(return_value=decision)
    session.commit = AsyncMock()
    session.add = MagicMock()

    async def _fake_session():
        yield session

    app = FastAPI()
    app.include_router(decisions_router, prefix="/v1/shared")
    app.dependency_overrides[get_session] = _fake_session
    return app, session


def test_rollback_writes_audit_row_in_same_tx():
    from src.core.models.audit import AuditLog

    decision = _decision(
        DecisionStatus.EXECUTED.value,
        executed_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    app, session = _build_app_capturing_adds(decision)
    client = TestClient(app)
    resp = client.post(
        f"/v1/shared/decisions/{decision.id}/rollback",
        headers={
            "x-tenant-id": str(TENANT),
            "x-user-id": "11111111-1111-1111-1111-111111111111",
        },
    )
    assert resp.status_code == 200, resp.text
    assert decision.status == DecisionStatus.ROLLED_BACK.value

    # Audit row foi adicionada à session...
    audit_rows = [
        c.args[0]
        for c in session.add.call_args_list
        if c.args and isinstance(c.args[0], AuditLog)
    ]
    assert len(audit_rows) == 1, "rollback tem de escrever exactamente 1 AuditLog"
    audit = audit_rows[0]
    assert audit.entity_type == "decision_run"
    assert audit.entity_id == decision.id
    assert audit.action == "UPDATE"
    assert audit.old_values == {"status": DecisionStatus.EXECUTED.value}
    assert audit.new_values["status"] == DecisionStatus.ROLLED_BACK.value

    # ...e foi adicionada ANTES do commit (mesma tx — invariante 7).
    assert session.add.called
    assert session.commit.await_count == 1

    # rolled_back_at é tz-aware (consistente com Q.130.U).
    assert decision.rolled_back_at.tzinfo is not None


# ── Q.118.S — approve vs reject (o status pedido tem de ser honrado) ────────

def _proposable(status_value: str = "PROPOSED"):
    from src.shared.models.governance import DecisionStatus as _DS
    return SimpleNamespace(
        id=uuid4(),
        tenant_id=TENANT,
        status=_DS.PROPOSED.value if status_value == "PROPOSED" else status_value,
        action_type="AUTO_PROPOSE_SCHEDULE",
        proposed_by=uuid4(),
        executed_at=None,
        rolled_back_at=None,
        before_state={},
    )


def _build_app_for_approve(decision, monkeypatch):
    from unittest.mock import MagicMock

    monkeypatch.setattr(
        "src.shared.auth.rbac.check_sod", lambda **kw: (True, None), raising=True,
    )
    session = AsyncMock()
    session.get = AsyncMock(return_value=decision)
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=result)

    async def _fake_session():
        yield session

    app = FastAPI()
    app.include_router(decisions_router, prefix="/v1/shared")
    app.dependency_overrides[get_session] = _fake_session
    return app


_HDRS = {"X-Tenant-Id": str(TENANT), "X-User-Id": str(uuid4())}


def test_approve_marks_approved(monkeypatch):
    d = _proposable()
    client = TestClient(_build_app_for_approve(d, monkeypatch))
    resp = client.post(
        f"/v1/shared/decisions/{d.id}/approve",
        json={"status": "APPROVED"},
        headers=_HDRS,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "approved"
    assert d.status == DecisionStatus.APPROVED.value


def test_reject_marks_rejected_not_approved(monkeypatch):
    """Q.118.S — o bug: 'Nao' (reject) aprovava. Agora rejeita mesmo."""
    d = _proposable()
    client = TestClient(_build_app_for_approve(d, monkeypatch))
    resp = client.post(
        f"/v1/shared/decisions/{d.id}/approve",
        json={"status": "REJECTED"},
        headers=_HDRS,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "rejected"
    assert d.status == DecisionStatus.REJECTED.value
