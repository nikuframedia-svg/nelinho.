"""Sprint D.1 — SSE endpoint smoke tests.

Running a real SSE end-to-end through `TestClient` requires the
`httpx.AsyncClient` + stream context, which is slow and fragile. We
cover the important paths via the router itself (schema, validation,
status codes) + bridge-level integration (which we already cover in
`test_realtime_bridge.py`).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.shared.realtime import router
from src.shared.realtime.bridge import RealtimeBridge


@pytest.fixture
def app() -> FastAPI:
    RealtimeBridge.reset_for_tests()
    _app = FastAPI()
    _app.include_router(router)
    return _app


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


def test_channels_endpoint_lists_all_channels(client):
    resp = client.get("/v1/realtime/channels")
    assert resp.status_code == 200
    body = resp.json()
    # Sprint Q.14.B added `rule_firing` (Postgres NOTIFY-sourced).
    assert set(body.keys()) == {
        "alerts", "dashboard", "governance", "rule_firing", "timeline",
    }
    # Alerts should include MOLD_MAINT_DUE.
    assert "prodplan.mold.maint_due" in body["alerts"]
    # rule_firing should expose the synthetic topic.
    assert "prodplan.governance.rule_firing_proposed" in body["rule_firing"]


def test_health_endpoint_reports_bridge_snapshot(client):
    resp = client.get("/v1/realtime/health")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"healthy", "started", "subscribers", "total_topics"}


def test_events_rejects_unknown_channel(client):
    resp = client.get(
        f"/v1/realtime/events?tenant_id={uuid4()}&channels=no_such_channel",
    )
    assert resp.status_code == 400
    assert "unknown channel" in resp.json()["detail"]


def test_events_rejects_missing_channels(client):
    resp = client.get(f"/v1/realtime/events?tenant_id={uuid4()}")
    assert resp.status_code == 422  # FastAPI missing-query validation


def test_events_rejects_empty_channels_csv(client):
    resp = client.get(
        f"/v1/realtime/events?tenant_id={uuid4()}&channels=,,",
    )
    assert resp.status_code == 400
    assert "at least one channel" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_events_no_503_and_flags_degraded_when_bridge_unhealthy():
    """Q.59.A — an unhealthy bridge (Kafka down) no longer answers 503.

    `EventSource` cannot read an HTTP status, so a 503 just made the
    browser reconnect forever — a single backend log showed 982 such
    503s. The endpoint now always serves the stream; its `connected`
    handshake carries `degraded: true` so the client leans on polling.

    We call the route directly and pull only the FIRST SSE item — never
    consume the (infinite) stream through `TestClient`, which deadlocks.
    The bridge is never started here, so it is unhealthy by construction.
    """
    from src.shared.realtime.api import stream_events

    RealtimeBridge.reset_for_tests()
    assert RealtimeBridge.instance().healthy is False

    # Before Q.59.A this raised HTTPException(503). It must not now.
    response = await stream_events(tenant_id=uuid4(), channels="alerts")

    first = await response.body_iterator.__anext__()
    text = first.decode() if isinstance(first, (bytes, bytearray)) else str(first)
    assert "connected" in text
    assert '"degraded": true' in text


def test_events_rejects_invalid_tenant_uuid(client):
    resp = client.get(
        "/v1/realtime/events?tenant_id=not-a-uuid&channels=alerts",
    )
    assert resp.status_code == 422


def test_parse_channels_normalises_and_dedupes():
    from src.shared.realtime.api import _parse_channels

    assert _parse_channels("alerts,Alerts,  ALERTS ") == ["alerts"]
    assert _parse_channels("alerts, timeline") == ["alerts", "timeline"]
