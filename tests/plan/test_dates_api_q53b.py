"""Q.53.B — date-aware planning API + services.

Covers the calendar / start-by / suggest-shipment / adherence / ctp
endpoints through the FastAPI router with a faked DB session, plus the
adherence and CTP services directly.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.plan.api.dates import router as dates_router
from src.plan.models.factory_calendar import FactoryCalendarDay
from src.plan.models.order import OrderStatus, ProductionOrder
from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session

TENANT = UUID("00000000-0000-0000-0000-000000000001")


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None


class _QueuedSession:
    """Async session that returns queued result sets in FIFO order."""

    def __init__(self, queue):
        self._queue = list(queue)

    async def execute(self, _stmt):
        if not self._queue:
            return _Result([])
        return _Result(self._queue.pop(0))

    async def commit(self):
        pass


def _app(session) -> FastAPI:
    app = FastAPI()
    app.include_router(dates_router, prefix="/v1/plan")
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[require_tenant_header] = lambda: TENANT
    return app


def _cal_day(day: date, working: bool, label=None) -> FactoryCalendarDay:
    return FactoryCalendarDay(
        id=uuid4(),
        tenant_id=TENANT,
        day=day,
        is_working_day=working,
        shift_hours=Decimal("8.00") if working else Decimal("0.00"),
        label=label,
    )


def _order(**kw) -> ProductionOrder:
    defaults = dict(
        id=uuid4(),
        tenant_id=TENANT,
        legacy_id=kw.pop("legacy_id", 1001),
        product_id=kw.pop("product_id", 55),
        product_name="K1 Vanquish",
        product_type="K1",
        current_phase_name="Laminagem",
        status=OrderStatus.IN_PROGRESS,
        transport_date=kw.pop("transport_date", None),
    )
    defaults.update(kw)
    return ProductionOrder(**defaults)


# ─── Calendar endpoint ───────────────────────────────────────────────────


def test_get_calendar_returns_seeded_days():
    days = [
        _cal_day(date(2026, 5, 11), True),
        _cal_day(date(2026, 5, 12), True),
        _cal_day(date(2026, 5, 16), False, "Sábado"),
    ]
    client = TestClient(_app(_QueuedSession([days])))
    resp = client.get(
        "/v1/plan/calendar",
        params={"from_date": "2026-05-11", "to_date": "2026-05-20"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 3
    assert body["working_days"] == 2
    assert body["non_working_days"] == 1


def test_get_calendar_empty_is_explicit_not_500():
    client = TestClient(_app(_QueuedSession([[]])))
    resp = client.get("/v1/plan/calendar")
    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_get_calendar_rejects_inverted_window():
    client = TestClient(_app(_QueuedSession([[]])))
    resp = client.get(
        "/v1/plan/calendar",
        params={"from_date": "2026-05-20", "to_date": "2026-05-10"},
    )
    assert resp.status_code == 400


# ─── start-by endpoint ───────────────────────────────────────────────────


def test_start_by_order_not_found_is_404():
    client = TestClient(_app(_QueuedSession([[]])))
    resp = client.get(f"/v1/plan/orders/{uuid4()}/start-by")
    assert resp.status_code == 404


def test_start_by_order_without_transport_date():
    order = _order(transport_date=None)
    # 1st execute: load order. start_by_for_order returns early — no
    # further queries.
    client = TestClient(_app(_QueuedSession([[order]])))
    resp = client.get(f"/v1/plan/orders/{order.id}/start-by")
    assert resp.status_code == 200
    body = resp.json()
    assert body["start_by"] is None
    assert "transporte" in body["reason"].lower()


def test_start_by_order_without_routing_template():
    order = _order(transport_date=datetime(2026, 7, 1, 8, 0))
    # execute order calls: load order, then routing assignment (empty),
    # any-template (empty), then phase gaps (empty), calendar (empty).
    session = _QueuedSession([[order], [], [], [], []])
    client = TestClient(_app(session))
    resp = client.get(f"/v1/plan/orders/{order.id}/start-by")
    assert resp.status_code == 200
    body = resp.json()
    # No routing → lead time unknown, explicit reason.
    assert body["start_by"] is None
    assert "routing" in body["reason"].lower()


# ─── suggest-shipment endpoint ───────────────────────────────────────────


def test_suggest_shipment_without_routing_template():
    order = _order(transport_date=datetime(2026, 7, 1, 8, 0))
    session = _QueuedSession([[order], [], [], [], []])
    client = TestClient(_app(session))
    resp = client.get(f"/v1/plan/orders/{order.id}/suggest-shipment")
    assert resp.status_code == 200
    body = resp.json()
    assert body["suggested_shipment"] is None
    assert body["transport_date"] == "2026-07-01"


# ─── adherence endpoint ──────────────────────────────────────────────────


def test_adherence_no_committed_plan_is_explicit():
    # execute calls: commit (none), production_schedules (empty),
    # rework (empty).
    session = _QueuedSession([[], [], []])
    client = TestClient(_app(session))
    resp = client.get("/v1/plan/adherence")
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_committed_plan"] is False
    assert body["phases"] == []
    assert body["summary"]["total_planned_ops"] == 0


# ─── ctp endpoint ────────────────────────────────────────────────────────


def test_ctp_with_no_orders_returns_empty_plan():
    # execute: orders (empty), then stock lookup (empty).
    session = _QueuedSession([[], []])
    client = TestClient(_app(session))
    resp = client.post(
        "/v1/plan/ctp",
        json={"truck_date": "2026-08-01", "truck_capacity": 6},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["truck_capacity"] == 6
    assert body["slots_used"] == 0
    assert body["committable"] == []
    assert body["summary"]["n_evaluated"] == 0


def test_ctp_rejects_bad_capacity():
    session = _QueuedSession([[], []])
    client = TestClient(_app(session))
    resp = client.post(
        "/v1/plan/ctp",
        json={"truck_date": "2026-08-01", "truck_capacity": 0},
    )
    assert resp.status_code == 422
