"""Q.157.D/E — fila do operador a partir do plano LIVE + overlay de picagem.

Cobre:
  D) operations_for_worker_day (puro): filtra por worker em workers[] + dia,
     ordena por start_time; _op_to_worker_response: defaults honestos.
  D) _resolve_worker_code: string não-UUID → code; UUID sem Employee → None.
  E) OperationExecutionService: start (SCHEDULED→IN_PROGRESS, cria linha),
     start inválido (IN_PROGRESS), complete (IN_PROGRESS→COMPLETED), complete
     inválido — com audit_change na mesma sessão.
"""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any, List
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from src.plan.services.cpo_commit_orders import operations_for_worker_day
from src.plan.services.operation_execution_service import OperationExecutionService
from src.plan.services.scheduling_service import InvalidScheduleTransition

TENANT = UUID("11111111-1111-1111-1111-111111111111")
DAY = date(2026, 6, 2)


def _op(operation_id, workers, start, end, order="OF-1", machine="M1", dur=120):
    return {
        "operation_id": operation_id,
        "order_id": order,
        "workers": workers,
        "start_time": start,
        "end_time": end,
        "machine_id": machine,
        "duration_minutes": dur,
    }


# ───────────────────────── D — operations_for_worker_day ──────────────────

def test_operations_for_worker_day_filters_and_orders():
    ops = [
        _op("b", ["77"], "2026-06-02T13:00:00", "2026-06-02T15:00:00"),
        _op("a", ["77", "88"], "2026-06-02T08:00:00", "2026-06-02T10:00:00"),
        _op("other-worker", ["99"], "2026-06-02T09:00:00", "2026-06-02T10:00:00"),
        _op("other-day", ["77"], "2026-06-01T08:00:00", "2026-06-01T10:00:00"),
        _op("spans-into-day", ["77"], "2026-06-01T20:00:00", "2026-06-02T04:00:00"),
    ]
    out = operations_for_worker_day(ops, "77", DAY)
    ids = [o["operation_id"] for o in out]
    # só ops do worker 77 activas no dia, ordenadas por start_time
    assert ids == ["spans-into-day", "a", "b"]


def test_operations_for_worker_day_empty_worker_or_no_match():
    ops = [_op("x", ["5"], "2026-06-02T08:00:00", "2026-06-02T10:00:00")]
    assert operations_for_worker_day(ops, "", DAY) == []
    assert operations_for_worker_day(ops, "999", DAY) == []
    assert operations_for_worker_day([], "5", DAY) == []


def test_op_to_worker_response_honest_defaults():
    from src.plan.api.schedule import _op_to_worker_response

    op = _op("op-1", ["77"], "2026-06-02T08:00:00", "2026-06-02T10:00:00", dur=90)
    resp = _op_to_worker_response(op, None)
    assert resp.id == "op-1"
    assert resp.order_id == "OF-1"
    assert resp.product_id == "OF-1"  # default honesto = order_id
    assert resp.quantity == 1.0
    assert resp.operation_sequence == 0
    assert resp.scheduled_duration_hours == 1.5  # 90 min
    assert resp.status == "SCHEDULED"  # sem overlay
    assert resp.actual_start is None

    # com overlay IN_PROGRESS
    exec_row = SimpleNamespace(
        status="IN_PROGRESS",
        actual_start=SimpleNamespace(isoformat=lambda: "2026-06-02T08:05:00"),
        actual_end=None,
    )
    resp2 = _op_to_worker_response(op, exec_row)
    assert resp2.status == "IN_PROGRESS"
    assert resp2.actual_start == "2026-06-02T08:05:00"


# ───────────────────────── D — _resolve_worker_code ───────────────────────

@pytest.mark.asyncio
async def test_resolve_worker_code_non_uuid_is_code():
    from src.plan.api.schedule import _resolve_worker_code

    # string não-UUID → tratada como employee_code directo (sem ir à BD)
    code = await _resolve_worker_code(session=None, tenant_id=TENANT, employee_id="123")
    assert code == "123"


@pytest.mark.asyncio
async def test_resolve_worker_code_uuid_without_employee_is_none():
    from src.plan.api import schedule as sched

    class _Res:
        def scalar_one_or_none(self):
            return None

    class _Sess:
        async def execute(self, stmt):
            return _Res()

    code = await sched._resolve_worker_code(
        session=_Sess(), tenant_id=TENANT, employee_id=str(uuid4()),
    )
    assert code is None  # UUID que não é Employee (ex.: user_id) → fila vazia honesta


# ───────────────────────── E — OperationExecutionService ──────────────────

class FakeSession:
    def __init__(self) -> None:
        self.added: List[Any] = []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                object.__setattr__(obj, "id", uuid4())


@pytest.mark.asyncio
async def test_start_creates_row_and_audits():
    from src.core.models.audit import AuditLog

    session = FakeSession()
    svc = OperationExecutionService(session, TENANT)
    with patch.object(svc, "_get", AsyncMock(return_value=None)):
        row = await svc.start(
            operation_id="op-1", order_id="OF-1", worker_code="77", commit_sha="abc",
        )
    assert row.status == "IN_PROGRESS"
    assert row.actual_start is not None
    assert any(isinstance(a, AuditLog) for a in session.added), "audit na mesma tx"


@pytest.mark.asyncio
async def test_start_on_in_progress_is_conflict():
    session = FakeSession()
    svc = OperationExecutionService(session, TENANT)
    existing = SimpleNamespace(id=uuid4(), status="IN_PROGRESS", actual_start=None,
                               order_id="OF-1")
    with patch.object(svc, "_get", AsyncMock(return_value=existing)):
        with pytest.raises(InvalidScheduleTransition):
            await svc.start(operation_id="op-1")


@pytest.mark.asyncio
async def test_complete_from_in_progress():
    session = FakeSession()
    svc = OperationExecutionService(session, TENANT)
    existing = SimpleNamespace(
        id=uuid4(), status="IN_PROGRESS", order_id="OF-1",
        actual_end=None, actual_quantity=None,
    )
    with patch.object(svc, "_get", AsyncMock(return_value=existing)):
        row = await svc.complete(operation_id="op-1")
    assert row.status == "COMPLETED"
    assert row.actual_end is not None


@pytest.mark.asyncio
async def test_complete_without_start_is_conflict():
    session = FakeSession()
    svc = OperationExecutionService(session, TENANT)
    with patch.object(svc, "_get", AsyncMock(return_value=None)):
        with pytest.raises(InvalidScheduleTransition):
            await svc.complete(operation_id="op-1")
