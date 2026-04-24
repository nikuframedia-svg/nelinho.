"""Sprint J follow-up — HTTPMetricsMiddleware.

Covers:

* Counter + histogram are emitted for handled requests.
* Handler exceptions are recorded as status 500 and re-raised.
* Excluded paths (``/metrics``, ``/v1/realtime/events``) are NOT
  recorded — prevents the scrape feedback loop + SSE single-bucket
  distortion.
* Path template is the matched route (e.g. ``/items/{id}``), not the
  concrete URL — keeps label cardinality bounded.
* ``in_flight`` gauge increments + decrements symmetrically.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.shared.http_metrics_middleware import HTTPMetricsMiddleware
from src.shared.metrics import (
    http_request_duration_seconds,
    http_requests_in_flight,
    http_requests_total,
    registry,
)
from prometheus_client import generate_latest


# ─── Helpers ──────────────────────────────────────────────────────────────


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(HTTPMetricsMiddleware)

    @app.get("/v1/ping")
    async def ping():
        return {"pong": True}

    @app.get("/items/{item_id}")
    async def get_item(item_id: str):
        return {"id": item_id}

    @app.get("/boom")
    async def boom():
        raise HTTPException(status_code=500, detail="simulated")

    @app.get("/kaboom")
    async def kaboom():
        raise RuntimeError("real exception")

    @app.get("/metrics")
    async def metrics():
        return {"fake": "metrics endpoint"}

    return app


def _metric_sample(
    metric_name: str,
    labels: dict[str, str] | None = None,
) -> float | None:
    """Pull a single value out of the Prometheus registry text output.
    Returns None when the (metric, labels) pair hasn't been recorded
    yet — useful for "was this NOT emitted" assertions."""
    text = generate_latest(registry).decode("utf-8")
    lookup = metric_name
    for line in text.splitlines():
        if not line.startswith(lookup):
            continue
        if labels:
            # crude label match — each label shows up as `k="v"` in the
            # exposed line. Full parser overkill here.
            if not all(f'{k}="{v}"' in line for k, v in labels.items()):
                continue
        try:
            return float(line.split()[-1])
        except (ValueError, IndexError):
            continue
    return None


# ─── Tests ────────────────────────────────────────────────────────────────


def test_counter_incremented_for_handled_request():
    client = TestClient(_make_app())
    before = _metric_sample(
        "prodplan_http_requests_total",
        {"path_template": "/v1/ping", "status": "200"},
    ) or 0
    resp = client.get("/v1/ping")
    assert resp.status_code == 200
    after = _metric_sample(
        "prodplan_http_requests_total",
        {"path_template": "/v1/ping", "status": "200"},
    ) or 0
    assert after - before == pytest.approx(1.0)


def test_template_label_is_path_format_not_concrete_url():
    client = TestClient(_make_app())
    client.get("/items/abc")
    client.get("/items/xyz")
    # Single time-series under the template — would be 2 if we used
    # the concrete URL, bloating label cardinality.
    sample = _metric_sample(
        "prodplan_http_requests_total",
        {"path_template": "/items/{item_id}", "status": "200"},
    )
    assert sample is not None
    assert sample >= 2.0


def test_http_exception_recorded_as_own_status():
    client = TestClient(_make_app())
    resp = client.get("/boom")
    assert resp.status_code == 500
    sample = _metric_sample(
        "prodplan_http_requests_total",
        {"path_template": "/boom", "status": "500"},
    )
    assert sample is not None and sample >= 1.0


def test_unhandled_exception_bubbles_up_and_records_500():
    client = TestClient(_make_app(), raise_server_exceptions=False)
    resp = client.get("/kaboom")
    assert resp.status_code == 500
    sample = _metric_sample(
        "prodplan_http_requests_total",
        {"path_template": "/kaboom", "status": "500"},
    )
    assert sample is not None and sample >= 1.0


def test_metrics_endpoint_is_excluded():
    """The FastAPI test app defines a dummy /metrics route. The
    middleware must not record anything for it."""
    client = TestClient(_make_app())
    before = _metric_sample(
        "prodplan_http_requests_total",
        {"path_template": "/metrics"},
    )
    client.get("/metrics")
    after = _metric_sample(
        "prodplan_http_requests_total",
        {"path_template": "/metrics"},
    )
    # Either both None (never recorded) or equal — NEVER higher.
    assert (before, after) == (None, None) or before == after


def test_in_flight_gauge_returns_to_baseline_after_request():
    client = TestClient(_make_app())
    before = http_requests_in_flight._value.get()
    client.get("/v1/ping")
    after = http_requests_in_flight._value.get()
    assert after == before  # decremented in finally block


def test_histogram_observes_bucketed_latency():
    client = TestClient(_make_app())
    client.get("/v1/ping")
    # The histogram's `_sum` counter should have grown by something
    # small (the handler is nearly instantaneous but still non-zero).
    labels = http_request_duration_seconds.labels(
        method="GET", path_template="/v1/ping", status="200",
    )
    assert labels._sum.get() > 0
