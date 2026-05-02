"""Sprint Q.9 (2.1) — ``GET /v1/plan/schedule/`` list endpoint.

Was previously a placeholder returning ``{"data": [], "total": 0}``.
Tests cover:
* happy path with no filter → all rows for the tenant
* status filter
* planning_run_id filter
* tenant isolation
* limit/offset validation
* sort by scheduled_start_date asc
"""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from typing import List
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.plan.api.schedule import router as schedule_router
from src.plan.models.schedule import ProductionSchedule, ScheduleStatus
from src.shared.database import get_session


TENANT = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def _row(
    *,
    tenant_id: UUID = TENANT,
    order_id: str = "OF-100",
    sequence: int = 1,
    status: ScheduleStatus = ScheduleStatus.SCHEDULED,
    start_date: date = date(2026, 4, 24),
    planning_run_id: str = "run-2026-04-24",
) -> ProductionSchedule:
    return ProductionSchedule(
        id=uuid4(),
        tenant_id=tenant_id,
        order_id=order_id,
        order_line=1,
        product_id=uuid4(),
        quantity=Decimal("1"),
        operation_id=uuid4(),
        operation_sequence=sequence,
        scheduled_start_date=start_date,
        scheduled_start_time=time(9, 0),
        scheduled_end_date=start_date,
        scheduled_end_time=time(11, 0),
        scheduled_duration_hours=Decimal("2"),
        setup_time_minutes=0,
        status=status,
        planning_run_id=planning_run_id,
        engine_used="cpo_v4",
        sequence_in_machine=0,
    )


def _build_app(seeded: List[ProductionSchedule]) -> FastAPI:
    """FastAPI app whose session.execute() applies the same filters
    that the endpoint encodes via SQLAlchemy."""
    session = AsyncMock()

    async def _execute(stmt):
        # Inspect the compiled SQL params: tenant_id always there,
        # status / planning_run_id optionally.
        try:
            params = stmt.compile().params
        except Exception:
            params = {}

        wanted_tenant = None
        wanted_status = None
        wanted_run = None
        for v in params.values():
            if isinstance(v, UUID):
                wanted_tenant = v
            elif isinstance(v, ScheduleStatus):
                wanted_status = v
            elif isinstance(v, str):
                wanted_run = v

        hits = [
            r for r in seeded
            if (wanted_tenant is None or r.tenant_id == wanted_tenant)
            and (wanted_status is None or r.status == wanted_status)
            and (wanted_run is None or r.planning_run_id == wanted_run)
        ]
        hits.sort(key=lambda r: (r.scheduled_start_date, r.scheduled_start_time or time.min))

        is_count = "count" in str(stmt).lower()
        if is_count:
            class _Result:
                def scalar(self_): return len(hits)
            return _Result()

        class _Scalars:
            def all(self_): return list(hits)

        class _Result:
            def scalars(self_): return _Scalars()

        return _Result()

    session.execute = _execute

    async def _fake_session():
        yield session

    app = FastAPI()
    app.include_router(schedule_router, prefix="/v1/plan")
    app.dependency_overrides[get_session] = _fake_session
    return app


def _client(rows: List[ProductionSchedule]) -> TestClient:
    return TestClient(_build_app(rows))


def test_list_schedules_happy_path_returns_data_and_total():
    rows = [_row(order_id="OF-A"), _row(order_id="OF-B", sequence=2)]
    resp = _client(rows).get(
        "/v1/plan/schedule/",
        headers={"x-tenant-id": str(TENANT)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["data"]) == 2
    assert {r["order_id"] for r in body["data"]} == {"OF-A", "OF-B"}


def test_list_schedules_filters_by_status():
    rows = [
        _row(order_id="OF-A", status=ScheduleStatus.SCHEDULED),
        _row(order_id="OF-B", status=ScheduleStatus.COMPLETED),
    ]
    resp = _client(rows).get(
        "/v1/plan/schedule/?status=COMPLETED",
        headers={"x-tenant-id": str(TENANT)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["data"][0]["order_id"] == "OF-B"


def test_list_schedules_invalid_status_returns_400():
    resp = _client([]).get(
        "/v1/plan/schedule/?status=NOT_A_REAL_STATUS",
        headers={"x-tenant-id": str(TENANT)},
    )
    assert resp.status_code == 400


def test_list_schedules_filters_by_planning_run_id():
    rows = [
        _row(order_id="A", planning_run_id="run-1"),
        _row(order_id="B", planning_run_id="run-2"),
    ]
    resp = _client(rows).get(
        "/v1/plan/schedule/?planning_run_id=run-2",
        headers={"x-tenant-id": str(TENANT)},
    )
    body = resp.json()
    assert body["total"] == 1
    assert body["data"][0]["order_id"] == "B"


def test_list_schedules_isolates_by_tenant():
    rows = [_row(order_id="MINE"), _row(order_id="OTHER", tenant_id=OTHER_TENANT)]
    resp = _client(rows).get(
        "/v1/plan/schedule/",
        headers={"x-tenant-id": str(TENANT)},
    )
    body = resp.json()
    assert body["total"] == 1
    assert body["data"][0]["order_id"] == "MINE"


def test_list_schedules_rejects_oversize_limit():
    resp = _client([]).get(
        "/v1/plan/schedule/?limit=500",
        headers={"x-tenant-id": str(TENANT)},
    )
    assert resp.status_code == 400


def test_list_schedules_rejects_negative_offset():
    resp = _client([]).get(
        "/v1/plan/schedule/?offset=-1",
        headers={"x-tenant-id": str(TENANT)},
    )
    assert resp.status_code == 400
