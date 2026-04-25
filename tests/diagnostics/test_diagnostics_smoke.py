"""Sprint Q.7 Fase 1 — Diagnostics module smoke tests.

Validates:
* /v1/diagnostics/modules works without DB (cheap path)
* The 17 module catalogue is enumerated
* Module health rollup categorises everything as green/yellow/red
* The shared module imports cleanly (regression guard for the
  outbox_models bug Q.7 Fase 1 fixed)
"""

from __future__ import annotations

import logging
from uuid import uuid4

from fastapi.testclient import TestClient


def test_modules_endpoint_returns_17_modules():
    logging.disable(logging.CRITICAL)
    from src.main import app

    client = TestClient(app)
    r = client.get("/v1/diagnostics/modules", headers={"X-Tenant-Id": str(uuid4())})
    assert r.status_code == 200
    body = r.json()
    assert "modules" in body
    assert len(body["modules"]) == 17
    assert body["summary"]["total"] == 17
    # Every module must roll up to one of three states
    for m in body["modules"]:
        assert m["health"] in {"green", "yellow", "red"}


def test_shared_module_imports_cleanly():
    """Regression guard: outbox_models had a malformed __table_args__
    (`postgresql_indexes` is not a valid SQLAlchemy kwarg). Q.7 Fase 1
    fixed it by switching to a proper Index() declaration matching
    migration 003. If this test fails, someone reintroduced the bug.
    """
    from src.shared.outbox_models import EventDLQ, EventOutbox  # noqa: F401

    # If the import succeeded the assertion below is trivial; the value
    # of this test is the import itself raising on regressions.
    assert EventOutbox.__tablename__ == "event_outbox"


def test_module_catalogue_includes_all_17_directories():
    """The Diagnostics service catalogue must mirror the actual src/
    directory layout. New modules added without updating MODULES would
    silently disappear from the dashboard."""
    from src.diagnostics.service import MODULES

    expected = {
        "core", "plan", "profit", "hr", "copilot", "ml", "explain",
        "factory_data_product", "governance", "shared", "twin", "sandbox",
        "supply", "workforce", "dqa", "improve", "legacy",
    }
    assert set(MODULES) == expected


def test_module_health_rollup_no_red_when_app_boots():
    """If the app boots successfully (which it must, otherwise the
    TestClient fixture itself fails), there should be ZERO red modules.
    A red module = something a future commit imported wrong; this test
    catches it before merge.
    """
    logging.disable(logging.CRITICAL)
    from src.main import app

    client = TestClient(app)
    r = client.get("/v1/diagnostics/modules", headers={"X-Tenant-Id": str(uuid4())})
    body = r.json()
    red = [m for m in body["modules"] if m["health"] == "red"]
    assert red == [], (
        f"Modules failing to import: {[m['module'] for m in red]}. "
        f"Errors: {[m['import_errors'] for m in red]}"
    )
