"""Q.61.34 — GET /v1/outbox/status (observabilidade do backlog).

Pina:
  * Tenant header obrigatorio (consistente com o resto da app).
  * Shape da resposta (pending/published/failed/dlq/oldest_pending_age/
    retry_pending/tenant_id).
  * Counts agregam correctamente por status.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.shared.api.outbox_status import router as outbox_router
from src.shared.database import get_session


TENANT = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


class _StubSession:
    """Devolve counts e oldest_pending fixos para o teste."""

    def __init__(
        self,
        pending: int = 0,
        published: int = 0,
        failed: int = 0,
        dlq: int = 0,
        retry_pending: int = 0,
        oldest_pending: datetime | None = None,
    ):
        # cada chamada a execute() vai buscar o proximo elemento.
        self._queue: list[Any] = [
            pending,          # _count("pending")
            published,        # _count("published")
            failed,           # _count("failed")
            dlq,              # dlq_q
            oldest_pending,   # oldest_q (scalar — pode ser None)
            retry_pending,    # retry_q
        ]

    async def execute(self, _stmt):
        value = self._queue.pop(0) if self._queue else None

        class _R:
            def scalar(self_inner):
                return value

        return _R()


def _app(session: _StubSession) -> FastAPI:
    app = FastAPI()
    app.include_router(outbox_router)

    async def _fake_session():
        yield session

    app.dependency_overrides[get_session] = _fake_session
    return app


def test_status_requires_tenant_header():
    client = TestClient(_app(_StubSession()))
    resp = client.get("/v1/outbox/status")
    assert resp.status_code in (400, 401, 422)


def test_status_returns_zeros_when_outbox_empty():
    client = TestClient(_app(_StubSession()))
    resp = client.get(
        "/v1/outbox/status",
        headers={"x-tenant-id": str(TENANT)},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["pending"] == 0
    assert body["published"] == 0
    assert body["failed"] == 0
    assert body["dlq"] == 0
    assert body["retry_pending"] == 0
    assert body["oldest_pending_age_seconds"] is None
    assert body["tenant_id"] == str(TENANT)


def test_status_returns_actual_counts():
    session = _StubSession(
        pending=12,
        published=2050,
        failed=3,
        dlq=3,
        retry_pending=5,
    )
    client = TestClient(_app(session))
    resp = client.get(
        "/v1/outbox/status",
        headers={"x-tenant-id": str(TENANT)},
    )
    body = resp.json()
    assert body["pending"] == 12
    assert body["published"] == 2050
    assert body["failed"] == 3
    assert body["dlq"] == 3
    assert body["retry_pending"] == 5


def test_status_computes_oldest_pending_age():
    """Quando ha pending, oldest_pending_age_seconds reflecte idade."""
    five_minutes_ago = datetime.now(timezone.utc) - timedelta(seconds=300)
    session = _StubSession(
        pending=1,
        oldest_pending=five_minutes_ago,
    )
    client = TestClient(_app(session))
    resp = client.get(
        "/v1/outbox/status",
        headers={"x-tenant-id": str(TENANT)},
    )
    age = resp.json()["oldest_pending_age_seconds"]
    assert age is not None
    # Permite 2s de tolerancia (test setup + clock skew).
    assert 298 <= age <= 305


def test_status_include_all_tenants_clears_tenant_id():
    """`?include_all_tenants=true` devolve `tenant_id: null` no body."""
    client = TestClient(_app(_StubSession()))
    resp = client.get(
        "/v1/outbox/status?include_all_tenants=true",
        headers={"x-tenant-id": str(TENANT)},
    )
    assert resp.status_code == 200
    assert resp.json()["tenant_id"] is None
