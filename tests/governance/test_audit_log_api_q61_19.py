"""Q.61.19 — GET /v1/governance/audit-logs.

Pina:
  * Endpoint montado em /v1/governance/audit-logs (via include_router).
  * Tenant scope (header obrigatorio).
  * Forma da resposta paginada.
  * Filtros (entity_type, entity_id, action, ...).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.models.audit import AuditLog
from src.governance.api import router as governance_router
from src.shared.database import get_session


TENANT = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def _row(
    entity_type: str = "decision_run",
    action: str = "INSERT",
    actor_id: UUID | None = None,
    reason: str | None = "test",
    created_at: datetime | None = None,
) -> AuditLog:
    return AuditLog(
        id=uuid4(),
        tenant_id=TENANT,
        entity_type=entity_type,
        entity_id=uuid4(),
        action=action,
        old_values=None,
        new_values={"sentinel": True},
        actor_id=actor_id,
        actor_role="operator" if actor_id else None,
        reason=reason,
        ip_address=None,
        user_agent=None,
        created_at=created_at or datetime.now(timezone.utc),
    )


class _StubSession:
    """Devolve `rows` em queries `SELECT AuditLog` e `count` em
    queries `SELECT count(*)`. Ignora filtros — testamos a API,
    o SQL e responsabilidade do Postgres real."""

    def __init__(self, rows: list[AuditLog]) -> None:
        self.rows = rows

    async def execute(self, stmt):
        sql = str(stmt).lower()
        is_count = "count" in sql

        rows = self.rows

        class _Scalars:
            def all(self_inner):
                return list(rows)

        class _R:
            def scalars(self_inner):
                return _Scalars()

            def scalar(self_inner):
                return len(rows)

        return _R()


def _app(rows: list[AuditLog]) -> FastAPI:
    app = FastAPI()
    app.include_router(governance_router)

    session = _StubSession(rows)

    async def _fake_session():
        yield session

    app.dependency_overrides[get_session] = _fake_session
    return app


def test_endpoint_returns_paginated_shape():
    rows = [_row(action="INSERT"), _row(action="UPDATE")]
    client = TestClient(_app(rows))
    resp = client.get(
        "/v1/governance/audit-logs",
        headers={"x-tenant-id": str(TENANT)},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) >= {"entries", "total", "page", "page_size"}
    assert isinstance(body["entries"], list)
    assert body["page"] == 1
    assert 1 <= body["page_size"] <= 200


def test_endpoint_requires_tenant_header():
    client = TestClient(_app([]))
    resp = client.get("/v1/governance/audit-logs")
    # Sem tenant header -> 401 (require_tenant_header).
    assert resp.status_code in (400, 401, 422)


def test_endpoint_accepts_action_filter():
    rows = [_row(action="UPDATE")]
    client = TestClient(_app(rows))
    resp = client.get(
        "/v1/governance/audit-logs?action=UPDATE",
        headers={"x-tenant-id": str(TENANT)},
    )
    assert resp.status_code == 200
    assert resp.json()["entries"][0]["action"] == "UPDATE"


def test_endpoint_rejects_invalid_action_enum():
    client = TestClient(_app([]))
    resp = client.get(
        "/v1/governance/audit-logs?action=BANANA",
        headers={"x-tenant-id": str(TENANT)},
    )
    # FastAPI/Pydantic devolve 422 para enum invalido.
    assert resp.status_code == 422


def test_endpoint_returns_entry_fields():
    """Estrutura de cada entry — frontend consome estes campos."""
    actor = uuid4()
    rows = [_row(actor_id=actor, reason="[trace_id=abc] approve")]
    client = TestClient(_app(rows))
    resp = client.get(
        "/v1/governance/audit-logs",
        headers={"x-tenant-id": str(TENANT)},
    )
    entry = resp.json()["entries"][0]
    assert {
        "id",
        "tenant_id",
        "entity_type",
        "entity_id",
        "action",
        "actor_id",
        "reason",
        "created_at",
    } <= set(entry)
    assert entry["actor_id"] == str(actor)
    assert "trace_id=abc" in entry["reason"]
