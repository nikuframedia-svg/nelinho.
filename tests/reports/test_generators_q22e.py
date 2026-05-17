"""Sprint Q.22.E — payroll / cogs / inventario report generators.

Before Q.22.E ``POST /v1/reports/generate`` returned
``status="not_implemented"`` for these three templates. Now they
delegate to ``reports.generators`` which queries the live hr / profit /
supply tables.

Covered:
* each template → status="ready" (never "not_implemented")
* generator rows are mapped into the report ``content`` + ``row_count``
* an empty source table → status="ready" with row_count=0 (ZERO MOCKS:
  no placeholder rows)
* CSV vs JSON formatting of the rows
"""

from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.reports.api import router
from src.shared.database import get_session
from tests.reports.conftest import FakeSession

TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _build_app(session):
    async def _fake_session():
        yield session

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_session] = _fake_session
    return app


def _headers():
    return {"X-Tenant-Id": str(TENANT)}


def test_payroll_generator_maps_allocation_rows():
    session = FakeSession()
    emp = uuid4()
    # (employee_id, sum(hours), sum(cost)) — the grouped payroll query.
    session.gen_rows["hr_allocations"] = [(emp, 38.5, 612.40)]
    client = TestClient(_build_app(session))

    resp = client.post(
        "/v1/reports/generate",
        headers=_headers(),
        json={"template_id": "payroll", "format": "json"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"  # not "not_implemented"
    assert body["row_count"] == 1
    rows = json.loads(body["content"])
    assert rows[0]["employee_id"] == str(emp)
    assert rows[0]["hours"] == 38.5
    assert rows[0]["labour_cost_eur"] == 612.4


def test_cogs_generator_maps_cost_rows():
    session = FakeSession()
    # (order_id, total, material, labor, machine, overhead)
    session.gen_rows["cost_calculations"] = [
        ("OF-100", 2350.0, 900.0, 800.0, 400.0, 250.0),
    ]
    client = TestClient(_build_app(session))

    resp = client.post(
        "/v1/reports/generate",
        headers=_headers(),
        json={"template_id": "cogs", "format": "json"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    rows = json.loads(body["content"])
    assert rows[0]["order_id"] == "OF-100"
    assert rows[0]["total_cogs_eur"] == 2350.0
    assert rows[0]["material_cost_eur"] == 900.0


def test_inventario_generator_keeps_latest_row_per_sku():
    session = FakeSession()
    older = datetime(2026, 5, 1)
    newer = datetime(2026, 5, 10)
    # Ordered sku_id, date desc — newest first per SKU.
    session.gen_rows["inventory_ledger_entries"] = [
        ("RESIN-01", 120.0, newer),
        ("RESIN-01", 90.0, older),
    ]
    client = TestClient(_build_app(session))

    resp = client.post(
        "/v1/reports/generate",
        headers=_headers(),
        json={"template_id": "inventario", "format": "json"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    rows = json.loads(body["content"])
    assert len(rows) == 1  # one row per SKU
    assert rows[0]["sku_id"] == "RESIN-01"
    assert rows[0]["on_hand"] == 120.0  # the newer entry wins


def test_payroll_empty_table_is_ready_with_zero_rows():
    """No allocations → status="ready", row_count=0 — no placeholder rows."""
    session = FakeSession()  # gen_rows empty → query returns []
    client = TestClient(_build_app(session))

    resp = client.post(
        "/v1/reports/generate",
        headers=_headers(),
        json={"template_id": "payroll", "format": "csv"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["row_count"] == 0
    assert body["content"] == ""  # empty CSV — no fabricated rows


def test_cogs_csv_format_has_header_and_row():
    session = FakeSession()
    session.gen_rows["cost_calculations"] = [
        ("OF-7", 1000.0, 400.0, 300.0, 200.0, 100.0),
    ]
    client = TestClient(_build_app(session))

    resp = client.post(
        "/v1/reports/generate",
        headers=_headers(),
        json={"template_id": "cogs", "format": "csv"},
    )

    assert resp.status_code == 200
    content = resp.json()["content"]
    assert "order_id" in content  # CSV header
    assert "OF-7" in content
    assert resp.json()["filename"].endswith(".csv")
