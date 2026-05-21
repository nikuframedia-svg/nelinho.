"""Q.61.12 — trace_id end-to-end.

Pina o esqueleto:
  * TraceIdMiddleware injecta a header (echo) e mete o valor em
    ContextVar.
  * `get_trace_id()` devolve o valor da request actual.
  * Quando o cliente nao envia, o middleware gera UUID hex.
  * Quando o cliente envia, o middleware respeita.
  * O propose flow guarda trace_id no payload do EventOutbox (Q.61.11
    + Q.61.12 — until Q.61.18 adiciona coluna dedicada).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.shared.observability import (
    HEADER,
    TraceIdMiddleware,
    get_trace_id,
)


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(TraceIdMiddleware)

    @app.get("/echo")
    async def echo():
        return {"trace_id": get_trace_id()}

    return app


def test_middleware_generates_uuid_when_client_omits_header():
    client = TestClient(_app())
    resp = client.get("/echo")
    assert resp.status_code == 200
    body = resp.json()
    # Backend gerou um trace_id e devolveu-o no body + header.
    assert body["trace_id"] is not None
    assert len(body["trace_id"]) >= 16  # uuid hex tem 32
    assert resp.headers[HEADER] == body["trace_id"]


def test_middleware_respects_client_provided_header():
    client = TestClient(_app())
    given = "abc-123-test-trace"
    resp = client.get("/echo", headers={HEADER: given})
    assert resp.status_code == 200
    assert resp.json()["trace_id"] == given
    assert resp.headers[HEADER] == given


def test_get_trace_id_returns_none_outside_request_context():
    """Fora de uma request HTTP, ContextVar nao tem valor — devolve None."""
    assert get_trace_id() is None


def test_two_requests_have_independent_trace_ids():
    """ContextVar nao vaza entre requests."""
    client = TestClient(_app())
    r1 = client.get("/echo")
    r2 = client.get("/echo")
    assert r1.json()["trace_id"] != r2.json()["trace_id"]


# ─── Integration com governance.propose (Q.61.11+Q.61.12) ───────────────


@pytest.mark.asyncio
async def test_propose_propagates_trace_id_into_outbox_payload(
    fake_session, tenant_id, monkeypatch,
):
    """Q.61.12: propose dentro de uma request HTTP com trace_id mete
    o valor no payload da row EventOutbox.

    Mockamos o ContextVar via `set_trace_id` directamente; o
    middleware HTTP nao precisa de correr para isto.
    """
    from src.governance.service import GovernanceService
    from src.shared.observability import set_trace_id, reset_trace_id
    from src.shared.outbox_models import EventOutbox

    fake_session.queue_scalar(None)  # _get_last_decision_hash
    svc = GovernanceService(fake_session, tenant_id)

    token = set_trace_id("test-trace-q61-12")
    try:
        await svc.propose_decision(
            decision_type="scenario_publish",
            title="Trace test",
            action_data={"k": "v"},
            proposed_by="alice",
        )
    finally:
        reset_trace_id(token)

    outbox_rows = [o for o in fake_session.added if isinstance(o, EventOutbox)]
    assert len(outbox_rows) == 1
    assert outbox_rows[0].payload.get("trace_id") == "test-trace-q61-12"
