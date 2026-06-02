"""Q.62.D.2 + D.4 — smoke tests dos endpoints async + approve.

Cobre:
  * `POST /v1/plan/cpo/schedule/async` retorna 202 + job_id.
  * `GET /v1/plan/cpo/schedule/job/{job_id}` retorna shape do polling.
  * `PUT /v1/plan/cpo/schedule/job/{job_id}/approve` toggles DRAFT → LIVE.
  * Endpoint sync `POST /v1/plan/cpo/schedule` continua a funcionar
    (delega para `run_cpo_schedule`).

Os tests mockam Arq (enqueue_job / Job.status / Job.result) — não
levantam worker real. Cobertura do worker em si vive em
test_cpo_worker_q62_d.
"""

from __future__ import annotations

import pytest


def test_async_endpoint_registered():
    """`POST /schedule/async` deve estar no router CPO."""
    from src.plan.api.cpo import router

    paths = {r.path for r in router.routes}
    assert "/v1/plan/cpo/schedule/async" in paths, (
        f"Endpoint /schedule/async em falta. Paths: {sorted(paths)}"
    )


def test_job_status_endpoint_registered():
    """`GET /schedule/job/{job_id}` deve estar no router."""
    from src.plan.api.cpo import router

    paths = {r.path for r in router.routes}
    assert "/v1/plan/cpo/schedule/job/{job_id}" in paths


def test_approve_endpoint_registered():
    """`PUT /schedule/job/{job_id}/approve` deve estar no router."""
    from src.plan.api.cpo import router

    paths = {r.path for r in router.routes}
    assert "/v1/plan/cpo/schedule/job/{job_id}/approve" in paths


def test_legacy_sync_schedule_still_registered():
    """`POST /schedule` legacy continua a existir (backwards compat)."""
    from src.plan.api.cpo import router

    paths = {r.path for r in router.routes}
    assert "/v1/plan/cpo/schedule" in paths


def test_run_cpo_schedule_extracted():
    """`run_cpo_schedule` deve viver em scheduler_run, importavel."""
    from src.plan.cpo.scheduler_run import run_cpo_schedule
    import inspect

    assert inspect.iscoroutinefunction(run_cpo_schedule)
    sig = inspect.signature(run_cpo_schedule)
    params = list(sig.parameters)
    assert params == ["session", "tenant_id", "request"], (
        f"Assinatura inesperada: {params}"
    )


def test_schedule_commit_has_status_column():
    """Q.62.D.4 — `ScheduleCommit.status` adicionado em 057."""
    from src.plan.cpo.commits import ScheduleCommit

    assert hasattr(ScheduleCommit, "status"), (
        "ScheduleCommit.status nao foi adicionado em Q.62.D.4"
    )


def test_migration_057_adds_status_column():
    """Pin: migration 057 adiciona `status` column DRAFT|LIVE."""
    from pathlib import Path

    path = Path("alembic/versions/057_q62_d_commit_status.py")
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "add_column" in text
    assert "plan_schedule_commits" in text
    assert "DRAFT" in text
    assert "ix_plan_schedule_commits_status" in text


def test_cpo_worker_uses_extracted_run_cpo_schedule():
    """Q.62.D.2 wire — worker `cpo_schedule_job` deve chamar
    `run_cpo_schedule` (importavel de scheduler_run)."""
    from pathlib import Path

    text = Path("src/plan/cpo/worker.py").read_text(encoding="utf-8")
    assert "from src.plan.cpo.scheduler_run import run_cpo_schedule" in text
    assert "await run_cpo_schedule(session, tenant_id, request)" in text


@pytest.mark.asyncio
async def test_async_endpoint_returns_202_and_job_id(monkeypatch):
    """Mock arq.create_pool + enqueue_job; verifica response shape."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from unittest.mock import AsyncMock, MagicMock
    from uuid import UUID

    from src.plan.api.cpo import router as cpo_router
    from src.shared.auth.headers import require_tenant_header
    from src.shared.config import settings

    monkeypatch.setattr(settings, "environment", "development", raising=False)

    # Mock arq pool: enqueue_job retorna um job com job_id fixo.
    fake_job = MagicMock(job_id="job-abc-123")
    fake_pool = AsyncMock()
    fake_pool.enqueue_job = AsyncMock(return_value=fake_job)
    fake_pool.close = AsyncMock(return_value=None)

    async def _fake_create_pool(*_args, **_kwargs):
        return fake_pool

    monkeypatch.setattr(
        "arq.connections.create_pool", _fake_create_pool,
    )

    app = FastAPI()
    app.include_router(cpo_router)
    dev_tenant = UUID("00000000-0000-0000-0000-000000000001")
    app.dependency_overrides[require_tenant_header] = lambda: dev_tenant

    client = TestClient(app)
    resp = client.post(
        "/v1/plan/cpo/schedule/async",
        headers={"X-Tenant-Id": str(dev_tenant)},
        json={"horizon_days": 7},
    )

    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["job_id"] == "job-abc-123"
    assert body["status_url"].endswith("/job/job-abc-123")
    assert "enqueued_at" in body

    # Confirma que enqueue_job foi chamado com o nome correcto.
    fake_pool.enqueue_job.assert_awaited_once()
    call_args = fake_pool.enqueue_job.await_args
    assert call_args.args[0] == "cpo_schedule_job"


@pytest.mark.asyncio
async def test_job_status_in_progress_jobdef_has_no_start_time(monkeypatch):
    """Regressão (auditoria 2026-06-02): enquanto o job corre, o arq devolve um
    `JobDef` que só tem `enqueue_time` — `start_time`/`finish_time` só existem no
    `JobResult` (após completar). Aceder `.start_time` num `JobDef` levantava
    AttributeError -> 500 a cada poll do progresso do replan. O endpoint tem de
    devolver 200 com `started_at`/`completed_at` a None até completar.
    """
    from datetime import datetime, timezone
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from unittest.mock import AsyncMock
    from uuid import UUID

    from arq.jobs import JobStatus

    from src.plan.api.cpo import router as cpo_router
    from src.shared.auth.headers import require_tenant_header
    from src.shared.config import settings

    monkeypatch.setattr(settings, "environment", "development", raising=False)

    fake_pool = AsyncMock()
    fake_pool.close = AsyncMock(return_value=None)

    async def _fake_create_pool(*_args, **_kwargs):
        return fake_pool

    monkeypatch.setattr("arq.connections.create_pool", _fake_create_pool)

    class _FakeJobDef:
        """Como o arq `JobDef` em curso: só `enqueue_time` (sem start/finish)."""

        def __init__(self) -> None:
            self.enqueue_time = datetime(2026, 6, 2, 0, 0, tzinfo=timezone.utc)
        # start_time / finish_time omitidos de propósito (AttributeError)

    class _FakeJob:
        def __init__(self, job_id, redis=None):
            self.job_id = job_id

        async def status(self):
            return JobStatus.in_progress

        async def info(self):
            return _FakeJobDef()

        async def result(self, *_args, **_kwargs):  # pragma: no cover
            raise AssertionError("result() nao deve ser chamado em in_progress")

    monkeypatch.setattr("arq.jobs.Job", _FakeJob)

    app = FastAPI()
    app.include_router(cpo_router)
    dev_tenant = UUID("00000000-0000-0000-0000-000000000001")
    app.dependency_overrides[require_tenant_header] = lambda: dev_tenant

    client = TestClient(app)
    resp = client.get(
        "/v1/plan/cpo/schedule/job/job-xyz-789",
        headers={"X-Tenant-Id": str(dev_tenant)},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["job_id"] == "job-xyz-789"
    assert body["state"] == "in_progress"
    assert body["enqueued_at"] is not None
    assert body["started_at"] is None
    assert body["completed_at"] is None
