"""Q.30.A — ``POST /v1/plan/schedule/{id}/start`` + ``/complete``.

O operador, no tablet, marca uma fase como iniciada e depois concluída.
A lógica de transição já vivia em ``SchedulingService.update_status`` —
estes testes cobrem os endpoints HTTP que faltavam:

* start: SCHEDULED → IN_PROGRESS, grava ``actual_start``;
* complete: IN_PROGRESS → COMPLETED, grava ``actual_end`` + ``actual_quantity``;
* completar uma fase ainda SCHEDULED → 409 (a máquina de estados proíbe
  SCHEDULED→COMPLETED directo);
* fase inexistente → 404; isolamento de tenant respeitado.
"""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from typing import Dict, List
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.plan.api.schedule import router as schedule_router
from src.plan.models.schedule import ProductionSchedule, ScheduleStatus
from src.shared.database import get_session

TENANT = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def _make_row(
    *,
    tenant_id: UUID = TENANT,
    status: ScheduleStatus = ScheduleStatus.SCHEDULED,
) -> ProductionSchedule:
    return ProductionSchedule(
        id=uuid4(),
        tenant_id=tenant_id,
        order_id="OF-100",
        order_line=1,
        product_id=uuid4(),
        quantity=Decimal("3"),
        operation_id=uuid4(),
        operation_sequence=1,
        scheduled_start_date=date(2026, 4, 24),
        scheduled_start_time=time(9, 0),
        scheduled_end_date=date(2026, 4, 24),
        scheduled_end_time=time(11, 30),
        scheduled_duration_hours=Decimal("2.5"),
        setup_time_minutes=0,
        assigned_employee_id=uuid4(),
        status=status,
        actual_start=None,
        actual_end=None,
        actual_quantity=None,
        sequence_in_machine=0,
    )


class _FakeSession:
    """Mínimo de AsyncSession: select-by-(id,tenant), flush e commit."""

    def __init__(self, rows: List[ProductionSchedule]) -> None:
        self.rows = list(rows)
        self.committed = False

    async def execute(self, stmt):  # noqa: ANN001 — test stub
        try:
            params = stmt.compile().params
        except Exception:
            params = {}
        uuids = {v for v in params.values() if isinstance(v, UUID)}
        hits = [r for r in self.rows if r.id in uuids and r.tenant_id in uuids]

        class _Result:
            def __init__(self, rows_):
                self._rows = rows_

            def scalar_one_or_none(self):
                return self._rows[0] if self._rows else None

        return _Result(hits)

    async def flush(self) -> None:
        pass

    async def commit(self) -> None:
        self.committed = True


def _make_app(rows: List[ProductionSchedule]) -> FastAPI:
    session = _FakeSession(rows)

    async def _fake_session():
        yield session

    app = FastAPI()
    app.include_router(schedule_router, prefix="/v1/plan")
    app.dependency_overrides[get_session] = _fake_session
    return app


def _headers() -> Dict[str, str]:
    return {"X-Tenant-Id": str(TENANT)}


def test_start_moves_scheduled_op_to_in_progress():
    row = _make_row(status=ScheduleStatus.SCHEDULED)
    client = TestClient(_make_app([row]))
    resp = client.post(f"/v1/plan/schedule/{row.id}/start", json={}, headers=_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "IN_PROGRESS"
    assert body["actual_start"] is not None


def test_complete_moves_in_progress_op_to_completed():
    row = _make_row(status=ScheduleStatus.IN_PROGRESS)
    client = TestClient(_make_app([row]))
    resp = client.post(
        f"/v1/plan/schedule/{row.id}/complete",
        json={"actual_quantity": 3},
        headers=_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "COMPLETED"
    assert body["actual_end"] is not None
    assert body["actual_quantity"] == 3.0


def test_full_flow_start_then_complete():
    row = _make_row(status=ScheduleStatus.SCHEDULED)
    client = TestClient(_make_app([row]))
    assert client.post(f"/v1/plan/schedule/{row.id}/start", json={}, headers=_headers()).status_code == 200
    resp = client.post(f"/v1/plan/schedule/{row.id}/complete", json={}, headers=_headers())
    assert resp.status_code == 200
    assert resp.json()["status"] == "COMPLETED"


def test_complete_on_scheduled_op_is_409():
    row = _make_row(status=ScheduleStatus.SCHEDULED)
    client = TestClient(_make_app([row]))
    resp = client.post(f"/v1/plan/schedule/{row.id}/complete", json={}, headers=_headers())
    assert resp.status_code == 409


def test_complete_unknown_op_is_404():
    client = TestClient(_make_app([]))
    resp = client.post(f"/v1/plan/schedule/{uuid4()}/complete", json={}, headers=_headers())
    assert resp.status_code == 404


def test_tenant_isolation_blocks_other_tenant_op():
    row = _make_row(tenant_id=OTHER_TENANT, status=ScheduleStatus.IN_PROGRESS)
    client = TestClient(_make_app([row]))
    resp = client.post(f"/v1/plan/schedule/{row.id}/complete", json={}, headers=_headers())
    assert resp.status_code == 404
