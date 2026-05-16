"""Sprint Q.22.E — report generators + `/v1/reports/generate`.

The three generators aggregate domain tables into a stable report dict.
Tests drive them with a FakeSession holding canned source rows, then
exercise the endpoint that persists the result as a ``ReportRun``.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.reports.api import router as reports_router
from src.reports.generators import (
    generate_cogs_report,
    generate_inventario_report,
    generate_payroll_report,
    serialize_report,
)
from src.shared.database import get_session
from tests.reports.conftest import FakeSession

TENANT = UUID("00000000-0000-0000-0000-000000000001")
USER = UUID("11111111-1111-1111-1111-111111111111")


def _headers():
    return {"X-Tenant-Id": str(TENANT), "X-User-Id": str(USER)}


async def test_payroll_generator_aggregates_by_employee():
    session = FakeSession()
    emp_a, emp_b = uuid4(), uuid4()
    session.gen_rows["hr_allocations"] = [
        (emp_a, 40.0, 800.0),
        (emp_b, 32.5, 650.0),
    ]
    report = await generate_payroll_report(session, TENANT)

    assert report["report_type"] == "payroll"
    assert len(report["rows"]) == 2
    assert report["summary"]["employee_count"] == 2
    assert report["summary"]["total_hours"] == 72.5
    assert report["summary"]["total_labour_cost_eur"] == 1450.0


async def test_cogs_generator_sums_per_order():
    session = FakeSession()
    session.gen_rows["cost_calculations"] = [
        ("ORD-1", 1000.0, 400.0, 300.0, 200.0, 100.0),
    ]
    report = await generate_cogs_report(session, TENANT)

    assert report["report_type"] == "cogs"
    assert report["rows"][0]["order_id"] == "ORD-1"
    assert report["rows"][0]["total_cogs_eur"] == 1000.0
    assert report["summary"]["total_cogs_eur"] == 1000.0


async def test_inventario_generator_keeps_latest_per_sku():
    session = FakeSession()
    session.gen_rows["inventory_ledger_entries"] = [
        # ordered by sku_id, date desc — first row per sku wins
        ("SKU-A", 50.0, datetime(2026, 5, 10)),
        ("SKU-A", 80.0, datetime(2026, 5, 1)),
        ("SKU-B", 12.0, datetime(2026, 5, 9)),
    ]
    report = await generate_inventario_report(session, TENANT)

    rows = {r["sku_id"]: r for r in report["rows"]}
    assert rows["SKU-A"]["on_hand"] == 50.0  # most recent, not 80
    assert rows["SKU-B"]["on_hand"] == 12.0
    assert report["summary"]["sku_count"] == 2


async def test_empty_generator_is_valid_report():
    report = await generate_payroll_report(FakeSession(), TENANT)
    assert report["rows"] == []
    assert report["summary"]["total_hours"] == 0


def test_serialize_report_csv_and_json():
    report = {
        "report_type": "cogs",
        "rows": [{"order_id": "ORD-1", "total_cogs_eur": 1000.0}],
        "summary": {},
    }
    csv_text = serialize_report(report, "csv")
    assert "order_id" in csv_text and "ORD-1" in csv_text

    json_text = serialize_report(report, "json")
    assert '"report_type": "cogs"' in json_text


def _build_client(session):
    async def _fake_session():
        yield session

    app = FastAPI()
    app.include_router(reports_router)
    app.dependency_overrides[get_session] = _fake_session
    return TestClient(app)


def test_generate_endpoint_persists_run():
    session = FakeSession()
    session.gen_rows["cost_calculations"] = [("ORD-1", 500.0, 0, 0, 0, 0)]
    client = _build_client(session)

    resp = client.post(
        "/v1/reports/generate",
        json={"report_type": "cogs"},
        headers=_headers(),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "generated"
    assert body["payload"]["report_type"] == "cogs"
    assert len(session.runs) == 1
    assert any(a.entity_type == "report_run" for a in session.audit)
