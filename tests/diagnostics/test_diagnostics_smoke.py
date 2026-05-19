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
    # Onda 1.5 — module health rolls up to one of four states; "unknown"
    # was added so accidentally-deleted modules surface (previously they
    # were silently marked green).
    for m in body["modules"]:
        assert m["health"] in {"green", "yellow", "red", "unknown"}


def test_shared_module_imports_cleanly():
    """Regression guard: outbox_models had a malformed __table_args__
    (`postgresql_indexes` is not a valid SQLAlchemy kwarg). Q.7 Fase 1
    fixed it by switching to a proper Index() declaration matching
    migration 003. If this test fails, someone reintroduced the bug.
    """
    from src.shared.outbox_models import EventDLQ, EventOutbox

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


# Onda 4.3 — coverage for the two endpoints the original suite never
# exercised (/infrastructure and /full). The original smoke only hit
# /modules + a tablename invariant; bugs in Kafka check, the global
# wait_for, or the /full agg-and-shape contract slipped through.

def test_modules_response_has_complete_per_module_shape():
    """Every module entry must surface the keys the dashboard reads —
    not just a `health` string. The /modules endpoint promised these in
    Sprint Q.7 Fase 1 but no test pinned the contract."""
    logging.disable(logging.CRITICAL)
    from src.main import app

    client = TestClient(app)
    r = client.get("/v1/diagnostics/modules", headers={"X-Tenant-Id": str(uuid4())})
    assert r.status_code == 200
    body = r.json()
    expected_keys = {
        "module", "src_files", "test_files", "routes",
        "todo_count", "import_errors", "import_error_count", "health",
    }
    for m in body["modules"]:
        missing = expected_keys - set(m.keys())
        assert not missing, f"module {m.get('module')} missing keys: {missing}"
        # Type contract — the frontend depends on these being numeric.
        assert isinstance(m["src_files"], int)
        assert isinstance(m["test_files"], int)
        assert isinstance(m["routes"], int)
        assert isinstance(m["todo_count"], int)
        assert isinstance(m["import_errors"], list)


def test_full_endpoint_returns_sampled_at_and_aggregated_shape():
    """Onda 1.6 added `sampled_at` to /full so the dashboard can tell
    cached snapshots from fresh ones. This test pins that, plus the
    overall shape (modules + infra + trust + commits)."""
    logging.disable(logging.CRITICAL)
    from src.main import app

    client = TestClient(app)
    r = client.get("/v1/diagnostics/full", headers={"X-Tenant-Id": str(uuid4())})
    # Whatever happens internally (DB unavailable, Kafka down), /full
    # MUST 200 with isolated subchecks; that's the whole "best-effort"
    # design point of the endpoint.
    assert r.status_code == 200
    body = r.json()
    assert "sampled_at" in body, "Onda 1.6 regression: /full lost sampled_at"
    # Top-level shape
    for key in ("modules", "modules_summary", "infrastructure",
                "trust_index", "commits"):
        assert key in body, f"/full missing top-level key {key}"
    # Modules summary now includes the `unknown` bucket added in 1.5.
    assert "unknown" in body["modules_summary"]
    # Infrastructure block has items + summary.
    assert "items" in body["infrastructure"]
    assert "summary" in body["infrastructure"]


def test_infrastructure_endpoint_returns_sampled_at_and_4_components():
    """The 4 components are postgres, redis, kafka, ollama. Each must
    surface `healthy` (bool) and `detail` (string). Onda 1.6 added the
    sampled_at field; we lock that here too."""
    logging.disable(logging.CRITICAL)
    from src.main import app

    client = TestClient(app)
    r = client.get(
        "/v1/diagnostics/infrastructure",
        headers={"X-Tenant-Id": str(uuid4())},
    )
    assert r.status_code == 200
    body = r.json()
    assert "sampled_at" in body
    assert len(body["items"]) == 4  # postgres, redis, kafka, ollama
    components = {item["component"] for item in body["items"]}
    assert components == {"postgresql", "redis", "kafka", "ollama"}
    for item in body["items"]:
        assert "healthy" in item
        assert isinstance(item["healthy"], bool)
        assert "detail" in item
        # Onda 2.2 — sanitised; detail is short and never includes raw
        # exception args. The longest legitimate detail today is the
        # Kafka metadata string (~40 chars).
        assert len(item["detail"]) < 200
