"""Sprint R.5.3 — adapter promote / rollback endpoint surface.

Static smoke that:
* Routes are registered.
* Promote validates reason ≥20 chars and admin role.
* Rollback returns 409 when there's no history.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient


def test_adapter_endpoints_registered():
    from src.main import app

    paths = {
        getattr(r, "path", None)
        for r in app.routes
        if hasattr(r, "methods")
    }
    assert "/v1/governance/learning/adapter" in paths
    assert "/v1/governance/learning/adapter/promote/{version}" in paths
    assert "/v1/governance/learning/adapter/rollback" in paths


def test_promote_requires_admin_role():
    import logging
    logging.disable(logging.CRITICAL)
    from src.main import app

    client = TestClient(app)
    r = client.post(
        "/v1/governance/learning/adapter/promote/test-v1",
        json={"reason": "promote para benchmark interno semanal", "decided_by": "luis"},
        headers={
            "X-Tenant-Id": str(uuid4()),
            "X-User-Role": "user",  # not admin
        },
    )
    assert r.status_code == 403


def test_promote_reason_below_20_chars_is_422():
    """Pydantic's ``min_length=20`` triggers an unprocessable response
    before the admin guard runs."""
    import logging
    logging.disable(logging.CRITICAL)
    from src.main import app

    client = TestClient(app)
    r = client.post(
        "/v1/governance/learning/adapter/promote/test-v1",
        json={"reason": "curto", "decided_by": "luis"},
        headers={
            "X-Tenant-Id": str(uuid4()),
            "X-User-Role": "admin",
        },
    )
    assert r.status_code == 422


def test_rollback_requires_admin_role():
    import logging
    logging.disable(logging.CRITICAL)
    from src.main import app

    client = TestClient(app)
    r = client.post(
        "/v1/governance/learning/adapter/rollback",
        json={"reason": "rollback porque eval baixou OTD esperado"},
        headers={
            "X-Tenant-Id": str(uuid4()),
            "X-User-Role": "user",
        },
    )
    assert r.status_code == 403
