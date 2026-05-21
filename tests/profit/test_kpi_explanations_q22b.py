"""Sprint Q.22.B — `GET /v1/profit/kpis/snapshot-explained` KPI coverage.

Before Q.22.B the endpoint only attached an ``otd`` explanation and
left a ``# TODO`` for the rest. Q.22.B wires the three remaining KPIs
the :class:`ExplanationEngine` already supports — ``margin``,
``inventory_turnover`` and ``machine_breakdown`` — into the response.

The endpoint is exercised with ``calculate_kpis`` patched so the test
is deterministic and needs no DB. ``machine_breakdown`` runs the engine
SQL path against a fake session that yields no rows (degrades to an
empty ``topFactors`` — never a 500).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.profit.api.kpis as kpis_module
from src.profit.api.kpis import KPIMetric, router
from src.shared.database import get_session
from tests.conftest import FakeSession

TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _metric(value):
    return KPIMetric(value=value, updated_at=datetime.utcnow())


class _FakeResult:
    """Q.68.3.3 — Empty result — every KPI query yields no rows.

    The engine uses ``.all()`` (machine_breakdown) and ``.fetchall()``
    (otd) and ``.scalar()`` (counts); all degrade gracefully to "no
    data" so the test stays deterministic and DB-free. The canonical
    ``FakeSession._FakeResult`` covers ``.all()`` and ``.scalar()`` but
    not ``.fetchall()`` — this thin wrapper adds it.
    """

    def all(self):
        return []

    def fetchall(self):
        return []

    def scalar(self):
        return 0


class _KpiFakeSession(FakeSession):
    """Subclass overrides ``execute()`` to return the wider ``_FakeResult``
    above (which adds ``fetchall()``). Other surface (add/commit/flush…)
    inherits from the canonical."""

    async def execute(self, _stmt):
        self.executed += 1
        self.executed_stmts.append(_stmt)
        return _FakeResult()


def _build_app(monkeypatch, kpis_payload):
    async def _fake_calc(_session, _tenant):
        return kpis_payload

    async def _fake_session():
        yield _KpiFakeSession()

    # Patch the calculator so we control the snapshot deterministically.
    # `monkeypatch` reverts it after the test — no cross-test bleed.
    monkeypatch.setattr(kpis_module, "calculate_kpis", _fake_calc)

    app = FastAPI()
    app.include_router(router, prefix="/v1/profit")
    app.dependency_overrides[get_session] = _fake_session
    return app


def _headers():
    return {"X-Tenant-Id": str(TENANT)}


def test_snapshot_explained_includes_margin_and_turnover_and_breakdown(monkeypatch):
    """The three previously-TODO'd KPIs must now appear in explanations."""
    payload = {
        "orders_total": _metric(120.0),
        "orders_in_progress": _metric(40.0),
        "orders_completed": _metric(80.0),
    }
    client = TestClient(_build_app(monkeypatch, payload))
    resp = client.get("/v1/profit/kpis/snapshot-explained", headers=_headers())

    assert resp.status_code == 200
    explanations = resp.json()["explanations"]
    # otd is gated on orders_total > 0 (present here).
    assert "otd" in explanations
    # Q.22.B additions — always present.
    assert "margin" in explanations
    assert "inventory_turnover" in explanations
    assert "machine_breakdown" in explanations


def test_margin_explanation_has_structural_factors(monkeypatch):
    payload = {
        "orders_total": _metric(10.0),
        "orders_in_progress": _metric(3.0),
        "orders_completed": _metric(7.0),
    }
    client = TestClient(_build_app(monkeypatch, payload))
    resp = client.get("/v1/profit/kpis/snapshot-explained", headers=_headers())

    margin = resp.json()["explanations"]["margin"]
    assert margin["kpi"] == "margin"
    assert margin["advisory_mode"] is True
    names = [f["name"] for f in margin["topFactors"]]
    assert "Direct labour" in names


def test_machine_breakdown_no_data_degrades_to_empty_factors(monkeypatch):
    """No incomplete schedules → empty topFactors, still 200 (not 500)."""
    payload = {
        "orders_total": _metric(5.0),
        "orders_in_progress": _metric(1.0),
        "orders_completed": _metric(4.0),
    }
    client = TestClient(_build_app(monkeypatch, payload))
    resp = client.get("/v1/profit/kpis/snapshot-explained", headers=_headers())

    assert resp.status_code == 200
    breakdown = resp.json()["explanations"]["machine_breakdown"]
    assert breakdown["kpi"] == "machine_breakdown"
    assert breakdown["topFactors"] == []


def test_explanations_present_even_when_no_orders(monkeypatch):
    """Margin/turnover/breakdown have no data gate — present with 0 orders.

    Only ``otd`` is gated on orders_total. The Q.22.B KPIs must still
    render so the panel is never blank.
    """
    payload = {
        "orders_total": _metric(None),
        "orders_in_progress": _metric(None),
        "orders_completed": _metric(None),
    }
    client = TestClient(_build_app(monkeypatch, payload))
    resp = client.get("/v1/profit/kpis/snapshot-explained", headers=_headers())

    assert resp.status_code == 200
    explanations = resp.json()["explanations"]
    assert "otd" not in explanations  # gated — no orders
    assert "margin" in explanations
    assert "inventory_turnover" in explanations
    assert "machine_breakdown" in explanations
