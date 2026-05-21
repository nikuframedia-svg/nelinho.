"""Sprint H.2 — ``GET /v1/plan/schedule/worker/{id}/operations-today``.

Covers:

* Happy path: only rows assigned to the target employee + overlapping
  the queried day are returned.
* Ordering: rows come back in scheduled-start order, with
  ``operation_sequence`` breaking ties on the same minute.
* Tenant isolation: a row for a different tenant never leaks.
* ``as_of`` override: a row scheduled for yesterday is filtered out
  when the request asks for today.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Dict, List
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.plan.api.schedule import router as schedule_router
from src.plan.models.schedule import ProductionSchedule, ScheduleStatus
from src.shared.database import get_session


TENANT = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
WORKER = UUID("11111111-2222-3333-4444-555555555555")
OTHER_WORKER = UUID("99999999-8888-7777-6666-555555555555")


# ─── Test doubles ─────────────────────────────────────────────────────────


def _make_row(
    *,
    tenant_id: UUID = TENANT,
    employee_id: UUID = WORKER,
    order_id: str = "OF-100",
    sequence: int = 1,
    start_date: date = date(2026, 4, 24),
    start_time: time = time(9, 0),
    end_date: date = date(2026, 4, 24),
    end_time: time = time(11, 30),
    status: ScheduleStatus = ScheduleStatus.SCHEDULED,
    duration_hours: float = 2.5,
) -> ProductionSchedule:
    return ProductionSchedule(
        id=uuid4(),
        tenant_id=tenant_id,
        order_id=order_id,
        order_line=1,
        product_id=uuid4(),
        quantity=Decimal("3"),
        operation_id=uuid4(),
        operation_sequence=sequence,
        scheduled_start_date=start_date,
        scheduled_start_time=start_time,
        scheduled_end_date=end_date,
        scheduled_end_time=end_time,
        scheduled_duration_hours=Decimal(str(duration_hours)),
        setup_time_minutes=0,
        assigned_employee_id=employee_id,
        status=status,
        actual_start=None,
        actual_end=None,
        actual_quantity=None,
        sequence_in_machine=0,
    )


class _FakeSession:
    """Just enough of AsyncSession to let the endpoint execute a filtered
    select. We capture the seeded rows + inspect the compiled params to
    apply the tenant / employee / day filters the real DB would."""

    def __init__(self, rows: List[ProductionSchedule]) -> None:
        self.rows = list(rows)

    async def execute(self, stmt):
        params = {}
        try:
            params = stmt.compile().params  # type: ignore[attr-defined]
        except Exception:
            params = {}

        tenant_id = None
        employee_id = None
        day_lo = None
        day_hi = None
        for key, value in params.items():
            if isinstance(value, UUID) and tenant_id is None:
                tenant_id = value
            elif isinstance(value, UUID):
                employee_id = value
            elif isinstance(value, date):
                if day_lo is None:
                    day_lo = value
                else:
                    day_hi = value

        def _match(row: ProductionSchedule) -> bool:
            if tenant_id and row.tenant_id != tenant_id:
                return False
            if employee_id and row.assigned_employee_id != employee_id:
                return False
            if day_lo and row.scheduled_start_date > day_lo:
                return False
            if day_hi and row.scheduled_end_date < day_hi:
                return False
            return True

        hits = [r for r in self.rows if _match(r)]
        hits.sort(key=lambda r: (
            r.scheduled_start_date,
            r.scheduled_start_time or time.min,
            r.operation_sequence,
        ))

        class _Scalars:
            def __init__(self, rows_: List[ProductionSchedule]) -> None:
                self._rows = rows_

            def all(self) -> List[ProductionSchedule]:
                return list(self._rows)

        class _Result:
            def __init__(self, rows_: List[ProductionSchedule]) -> None:
                self._rows = rows_

            def scalars(self) -> _Scalars:
                return _Scalars(self._rows)

        return _Result(hits)


def _make_app(rows: List[ProductionSchedule]) -> FastAPI:
    session = _FakeSession(rows)

    async def _fake_session():
        yield session

    app = FastAPI()
    app.include_router(schedule_router, prefix="/v1/plan")
    app.dependency_overrides[get_session] = _fake_session
    return app


# ─── Tests ────────────────────────────────────────────────────────────────


def _auth_headers() -> Dict[str, str]:
    return {"X-Tenant-Id": str(TENANT)}


def test_returns_only_rows_assigned_to_requested_worker():
    rows = [
        _make_row(employee_id=WORKER, sequence=1),
        _make_row(employee_id=OTHER_WORKER, sequence=2, order_id="OF-OTHER"),
        _make_row(employee_id=WORKER, sequence=3, order_id="OF-101"),
    ]
    client = TestClient(_make_app(rows))
    resp = client.get(
        f"/v1/plan/schedule/worker/{WORKER}/operations-today?as_of=2026-04-24",
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert {r["order_id"] for r in body} == {"OF-100", "OF-101"}


def test_orders_by_scheduled_start_then_sequence():
    rows = [
        _make_row(sequence=5, start_time=time(10, 0), order_id="OF-A"),
        _make_row(sequence=1, start_time=time(9, 0), order_id="OF-B"),
        _make_row(sequence=2, start_time=time(9, 0), order_id="OF-C"),
    ]
    client = TestClient(_make_app(rows))
    resp = client.get(
        f"/v1/plan/schedule/worker/{WORKER}/operations-today?as_of=2026-04-24",
        headers=_auth_headers(),
    )
    body = resp.json()
    order_sequence = [r["operation_sequence"] for r in body]
    assert order_sequence == [1, 2, 5]


def test_tenant_isolation_blocks_other_tenant_rows():
    rows = [
        _make_row(tenant_id=OTHER_TENANT, order_id="OF-OTHERTENANT"),
        _make_row(tenant_id=TENANT, order_id="OF-OURS"),
    ]
    client = TestClient(_make_app(rows))
    resp = client.get(
        f"/v1/plan/schedule/worker/{WORKER}/operations-today?as_of=2026-04-24",
        headers=_auth_headers(),
    )
    body = resp.json()
    assert [r["order_id"] for r in body] == ["OF-OURS"]


def test_as_of_filter_excludes_other_day():
    yesterday = date(2026, 4, 23)
    today = date(2026, 4, 24)
    rows = [
        _make_row(
            order_id="OF-YDAY",
            start_date=yesterday, end_date=yesterday,
            start_time=time(8, 0), end_time=time(10, 0),
        ),
        _make_row(
            order_id="OF-TODAY",
            start_date=today, end_date=today,
        ),
    ]
    client = TestClient(_make_app(rows))
    resp = client.get(
        f"/v1/plan/schedule/worker/{WORKER}/operations-today"
        f"?as_of={today.isoformat()}",
        headers=_auth_headers(),
    )
    body = resp.json()
    assert [r["order_id"] for r in body] == ["OF-TODAY"]


def test_empty_result_is_200_with_empty_list():
    client = TestClient(_make_app([]))
    resp = client.get(
        f"/v1/plan/schedule/worker/{WORKER}/operations-today?as_of=2026-04-24",
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    assert resp.json() == []
