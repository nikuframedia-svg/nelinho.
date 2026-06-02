"""Q.157.D — ``GET /v1/plan/schedule/worker/{id}/operations-today`` (plano LIVE).

A fila do operador deixou de ler de ``plan.production_schedules`` (Sprint H.2,
desacoplada do CPO) e passou a ler do **plano LIVE do CPO**
(``plan_schedule_commits.operations``), filtrando o operador (``employee_code``
em ``op["workers"]``) e o dia, com o estado real do overlay sobreposto.

Cobre: worker resolvido + ops do dia; sem commit → []; worker não-resolvido →
[]; overlay status aplicado. (A filtragem/ordenação pura está em
``test_q157de_operador_live.py``.)
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Dict
from unittest.mock import AsyncMock, patch
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.plan.api import schedule as sched
from src.plan.api.schedule import router as schedule_router
from src.shared.database import get_session

TENANT = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
WORKER_CODE = "77"


def _op(operation_id, start, end, order="OF-100", machine="M1", dur=150):
    return {
        "operation_id": operation_id,
        "order_id": order,
        "workers": [WORKER_CODE],
        "start_time": start,
        "end_time": end,
        "machine_id": machine,
        "duration_minutes": dur,
    }


def _make_app() -> FastAPI:
    async def _fake_session():
        yield object()  # não é usado: CommitsService/Employee são mockados

    app = FastAPI()
    app.include_router(schedule_router, prefix="/v1/plan")
    app.dependency_overrides[get_session] = _fake_session
    return app


def _commits_with(commit):
    class _C:
        def __init__(self, session, tenant_id):
            pass

        async def latest_live(self):
            return commit

        async def get_latest(self):
            return commit

    return _C


class _ExecNoOverlay:
    def __init__(self, session, tenant_id):
        pass

    async def status_map(self, ids) -> Dict:
        return {}


def _headers() -> Dict[str, str]:
    return {"X-Tenant-Id": str(TENANT)}


def test_returns_live_ops_for_worker_ordered():
    commit = SimpleNamespace(
        commit_sha256="sha-1",
        operations=[
            _op("op-late", "2026-04-24T13:00:00", "2026-04-24T15:00:00", order="OF-B"),
            _op("op-early", "2026-04-24T09:00:00", "2026-04-24T11:30:00", order="OF-A"),
        ],
    )
    client = TestClient(_make_app())
    with patch.object(sched, "CommitsService", _commits_with(commit)), \
         patch.object(sched, "OperationExecutionService", _ExecNoOverlay), \
         patch.object(sched, "_resolve_worker_code",
                      AsyncMock(return_value=WORKER_CODE)):
        resp = client.get(
            "/v1/plan/schedule/worker/77/operations-today?as_of=2026-04-24",
            headers=_headers(),
        )
    assert resp.status_code == 200
    body = resp.json()
    assert [r["order_id"] for r in body] == ["OF-A", "OF-B"]  # ordenado por start
    assert body[0]["id"] == "op-early"
    assert body[0]["status"] == "SCHEDULED"  # sem overlay
    assert body[0]["scheduled_duration_hours"] == 2.5  # 150 min


def test_no_commit_is_empty_list():
    client = TestClient(_make_app())
    with patch.object(sched, "CommitsService", _commits_with(None)), \
         patch.object(sched, "OperationExecutionService", _ExecNoOverlay), \
         patch.object(sched, "_resolve_worker_code",
                      AsyncMock(return_value=WORKER_CODE)):
        resp = client.get(
            "/v1/plan/schedule/worker/77/operations-today?as_of=2026-04-24",
            headers=_headers(),
        )
    assert resp.status_code == 200
    assert resp.json() == []


def test_unresolved_worker_is_empty_list():
    commit = SimpleNamespace(
        commit_sha256="sha-1",
        operations=[_op("op-1", "2026-04-24T09:00:00", "2026-04-24T11:00:00")],
    )
    client = TestClient(_make_app())
    with patch.object(sched, "CommitsService", _commits_with(commit)), \
         patch.object(sched, "OperationExecutionService", _ExecNoOverlay), \
         patch.object(sched, "_resolve_worker_code", AsyncMock(return_value=None)):
        resp = client.get(
            "/v1/plan/schedule/worker/some-user-uuid/operations-today?as_of=2026-04-24",
            headers=_headers(),
        )
    assert resp.status_code == 200
    assert resp.json() == []  # UUID que não é Employee → fila vazia honesta


def test_overlay_status_is_applied():
    commit = SimpleNamespace(
        commit_sha256="sha-1",
        operations=[_op("op-1", "2026-04-24T09:00:00", "2026-04-24T11:00:00")],
    )

    class _ExecInProgress:
        def __init__(self, session, tenant_id):
            pass

        async def status_map(self, ids):
            return {
                "op-1": SimpleNamespace(
                    status="IN_PROGRESS",
                    actual_start=SimpleNamespace(
                        isoformat=lambda: "2026-04-24T09:05:00"
                    ),
                    actual_end=None,
                )
            }

    client = TestClient(_make_app())
    with patch.object(sched, "CommitsService", _commits_with(commit)), \
         patch.object(sched, "OperationExecutionService", _ExecInProgress), \
         patch.object(sched, "_resolve_worker_code",
                      AsyncMock(return_value=WORKER_CODE)):
        resp = client.get(
            "/v1/plan/schedule/worker/77/operations-today?as_of=2026-04-24",
            headers=_headers(),
        )
    body = resp.json()
    assert body[0]["status"] == "IN_PROGRESS"
    assert body[0]["actual_start"] == "2026-04-24T09:05:00"
