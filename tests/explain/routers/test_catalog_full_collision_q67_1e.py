"""Q.67.1.E — Route-collision fix on `src/explain/routers/catalog_full.py`.

The bug pinned in Q.66.D.4c: ``/catalog/blocked/full`` and
``/catalog/available/full`` were declared AFTER ``/catalog/{metric_id}/full``,
so FastAPI matched the generic path-param route first with ``metric_id="blocked"``
or ``metric_id="available"`` and returned 404.

The fix re-orders the routes so the specific literal paths are declared
BEFORE the generic ``/catalog/{metric_id}/full``. These three tests pin
the new behaviour.

The legacy characterization test
``tests/explain/test_api_characterization_q66_d.py`` still pins the
pre-fix 404 behaviour — Luis updates that one when he consolidates this
sub-sprint.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.explain.routers.catalog_full import router


@pytest.fixture
def client() -> TestClient:
    """Mount just the catalog_full router on a bare FastAPI app.

    No tenant gate / DB session overrides needed — these endpoints
    are stateless reads of the in-memory ``METRIC_CATALOG``.
    """
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ============================================================================
# /catalog/blocked/full — specific literal route, must match BEFORE generic
# ============================================================================

def test_blocked_full_resolves_to_specific_handler(client):
    """GET /v1/explain/catalog/blocked/full returns the blocked-metrics dict.

    Pre-fix this returned 404 with detail "Metric 'blocked' not found"
    because the generic path-param route shadowed it.
    """
    resp = client.get("/v1/explain/catalog/blocked/full")
    assert resp.status_code == 200, (
        f"expected 200 from specific blocked/full handler, "
        f"got {resp.status_code} body={resp.json()}"
    )
    body = resp.json()
    # Specific handler returns {"blocked": [...], "total": N, "message": "..."}.
    # Generic handler would return a metric dict with "id"/"name"/... keys.
    assert "blocked" in body, (
        f"response missing 'blocked' key — route still collides with "
        f"/catalog/{{metric_id}}/full. body keys={list(body.keys())}"
    )
    assert isinstance(body["blocked"], list)
    assert "total" in body
    assert body["total"] == len(body["blocked"])
    assert "message" in body


# ============================================================================
# /catalog/available/full — twin of blocked/full
# ============================================================================

def test_available_full_resolves_to_specific_handler(client):
    """GET /v1/explain/catalog/available/full returns the available-metrics dict.

    Pre-fix: 404 with "Metric 'available' not found".
    """
    resp = client.get("/v1/explain/catalog/available/full")
    assert resp.status_code == 200, (
        f"expected 200 from specific available/full handler, "
        f"got {resp.status_code} body={resp.json()}"
    )
    body = resp.json()
    assert "available" in body, (
        f"response missing 'available' key — route still collides with "
        f"/catalog/{{metric_id}}/full. body keys={list(body.keys())}"
    )
    assert isinstance(body["available"], list)
    assert "total" in body
    assert body["total"] == len(body["available"])


# ============================================================================
# /catalog/{metric_id}/full — generic still works for real / unknown metric_id
# ============================================================================

def test_generic_metric_full_still_works_after_reorder(client):
    """Generic route still resolves once the literal paths are out of scope.

    Either:
    * 200 if the metric_id is a real catalog entry; or
    * 404 with detail "Metric '...' not found in catalog." for an unknown id.

    Anything else (e.g. 422 from a path-param parse error, or a body shape
    matching blocked/available) means the reorder broke the generic route.
    """
    resp = client.get("/v1/explain/catalog/this_is_not_a_real_metric/full")
    assert resp.status_code in (200, 404), (
        f"generic /catalog/{{metric_id}}/full broke after reorder — "
        f"got {resp.status_code} body={resp.json()}"
    )
    if resp.status_code == 404:
        detail = resp.json().get("detail", "")
        assert "not found" in detail.lower(), (
            f"unexpected 404 detail: {detail!r}"
        )
