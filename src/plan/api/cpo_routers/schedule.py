"""Q.67.6.B2 — sub-router para `/schedule*` (sync + async Arq + approve).

Endpoints:
* POST /schedule              — sync run (Sprint E + Sprint K commit)
* POST /schedule/async        — Arq enqueue (Q.62.D.2)
* GET  /schedule/job/{id}     — Arq polling (Q.62.D.2)
* PUT  /schedule/job/{id}/approve — DRAFT → LIVE (Q.62.D.4)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.api._cpo_common import _resolve_commit_or_404, _tenant_id
from src.plan.cpo.commits import CommitsService
from src.shared.database import get_session

router = APIRouter()


# =============================================================================
# Request / response schemas
# =============================================================================

class MachineInput(BaseModel):
    machine_id: str
    name: str = ""
    capacity: int = 1
    speed_factor: float = 1.0
    centro_custo: str = ""


class CPOScheduleRequest(BaseModel):
    orders: Optional[List[Dict[str, Any]]] = None
    machines: Optional[List[MachineInput]] = None
    horizon_days: int = Field(default=30, ge=1, le=180)
    time_limit_sec: float = Field(default=30.0, ge=1.0, le=300.0)
    population_size: int = Field(default=100, ge=10, le=500)
    generations: int = Field(default=50, ge=1, le=500)

    # Sprint K — optional commit metadata
    author: str = Field(default="system")
    message: str = Field(default="", max_length=2000)
    delta: Optional[Dict[str, Any]] = None  # Sprint K.4 POETIQ


class CPOScheduleResponse(BaseModel):
    tenant_id: str
    engine_used: str
    status: str
    solve_time_sec: float
    makespan_hours: float
    total_tardiness_hours: float
    num_late_orders: int
    setups: int
    avg_utilization: float
    safety_net_triggered: bool = False
    # FASE 1B.2 (CRIT-14) — `degraded=True` means the result came from a
    # fallback path (e.g. CPO v4 raised internally and we returned a
    # heuristic plan). Frontend should warn the user and admins should
    # check the logs / alerts. `fallback_reason` carries a short tag
    # describing what went wrong.
    degraded: bool = False
    fallback_reason: Optional[str] = None
    cpo_meta: Dict[str, Any] = Field(default_factory=dict)
    operations: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    infeasible_op_ids: List[str] = Field(default_factory=list)
    # Sprint K — commit trail
    commit_sha256: Optional[str] = None
    parent_sha256: Optional[str] = None


class CPOScheduleEnqueueResponse(BaseModel):
    """Q.62.D.2 — 202 response do POST /schedule/async."""

    job_id: str
    status_url: str
    enqueued_at: str


class CPOJobStatusResponse(BaseModel):
    """Q.62.D.2 — GET /schedule/job/{job_id} polling response.

    `state` é um dos: deferred (na queue), in_progress, complete, failed,
    not_found.
    """

    job_id: str
    state: str
    result: Optional[Dict[str, Any]] = None  # CPOScheduleResponse dict
    error: Optional[str] = None
    enqueued_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class CPOJobApproveResponse(BaseModel):
    """Q.62.D.4 — PUT /schedule/job/{job_id}/approve."""

    job_id: str
    commit_sha256: str
    previous_status: str
    new_status: str
    approved_at: str


# =============================================================================
# POST /schedule (sync)
# =============================================================================

@router.post("/schedule", response_model=CPOScheduleResponse)
async def schedule_cpo(
    request: CPOScheduleRequest,
    tenant_id: UUID = Depends(_tenant_id),
    db: AsyncSession = Depends(get_session),
):
    """Run CPO v4 syncronamente + persist o resultado como commit.

    Q.62.D.2 — body extraído para `src/plan/cpo/scheduler_run.py`.
    Endpoint sync continua a funcionar (backwards compat para tests +
    clientes legacy). Para o cliente novo que quer non-blocking, ver
    `POST /schedule/async` + `GET /schedule/job/{job_id}`.
    """
    from src.plan.cpo.scheduler_run import run_cpo_schedule

    result_dict = await run_cpo_schedule(db, tenant_id, request)
    return CPOScheduleResponse(**result_dict)


# =============================================================================
# POST /schedule/async (Q.62.D.2 — Arq enqueue)
# =============================================================================

@router.post(
    "/schedule/async",
    response_model=CPOScheduleEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def schedule_cpo_async(
    request: CPOScheduleRequest,
    tenant_id: UUID = Depends(_tenant_id),
    user_id: UUID = Depends(_tenant_id),  # placeholder — same gate
):
    """Q.62.D.2 — enfileira o CPO scheduler num Arq worker.

    Retorna 202 imediato com `job_id`. Cliente faz polling em
    `GET /v1/plan/cpo/schedule/job/{job_id}` para obter o resultado.

    Worker DEVE estar a correr:
        arq src.plan.cpo.worker.WorkerSettings

    Se o worker não está disponível, o job fica na queue até alguém o
    drainar. 503 só se Redis estiver completamente offline.
    """
    from arq.connections import ArqRedis, RedisSettings, create_pool

    from src.shared.config import settings as _settings

    try:
        redis: ArqRedis = await create_pool(
            RedisSettings.from_dsn(_settings.redis_url),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Arq queue unavailable (Redis): {exc}",
        )

    try:
        job = await redis.enqueue_job(
            "cpo_schedule_job",
            request.model_dump(mode="json"),
            str(tenant_id),
            str(user_id),
        )
    finally:
        await redis.close()

    if job is None:
        # Arq retorna None se o job ja existe pelo job_id (deduping).
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job already enqueued (idempotency).",
        )

    return CPOScheduleEnqueueResponse(
        job_id=job.job_id,
        status_url=f"/v1/plan/cpo/schedule/job/{job.job_id}",
        enqueued_at=datetime.utcnow().isoformat() + "Z",
    )


# =============================================================================
# GET /schedule/job/{job_id} (Q.62.D.2 — Arq polling)
# =============================================================================

@router.get(
    "/schedule/job/{job_id}",
    response_model=CPOJobStatusResponse,
)
async def get_schedule_job_status(
    job_id: str,
    tenant_id: UUID = Depends(_tenant_id),
):
    """Q.62.D.2 — polling endpoint para o resultado do Arq job."""
    from arq.connections import RedisSettings, create_pool
    from arq.jobs import Job, JobStatus

    from src.shared.config import settings as _settings

    try:
        redis = await create_pool(
            RedisSettings.from_dsn(_settings.redis_url),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Arq queue unavailable (Redis): {exc}",
        )

    try:
        job = Job(job_id, redis=redis)
        job_status = await job.status()

        if job_status is JobStatus.not_found:
            return CPOJobStatusResponse(job_id=job_id, state="not_found")

        info = await job.info()
        result: Optional[Dict[str, Any]] = None
        error_str: Optional[str] = None

        if job_status is JobStatus.complete:
            try:
                raw_result = await job.result(timeout=0.1)
                if isinstance(raw_result, dict):
                    result = raw_result
            except Exception as exc:
                # job completou mas com erro — `result()` re-raises.
                error_str = str(exc)

        return CPOJobStatusResponse(
            job_id=job_id,
            state=job_status.value if hasattr(job_status, "value") else str(job_status),
            result=result,
            error=error_str,
            enqueued_at=(info.enqueue_time.isoformat() + "Z") if info and info.enqueue_time else None,
            started_at=(info.start_time.isoformat() + "Z") if info and info.start_time else None,
            completed_at=(info.finish_time.isoformat() + "Z") if info and info.finish_time else None,
        )
    finally:
        await redis.close()


# =============================================================================
# PUT /schedule/job/{job_id}/approve (Q.62.D.4 — DRAFT → LIVE)
# =============================================================================

@router.put(
    "/schedule/job/{job_id}/approve",
    response_model=CPOJobApproveResponse,
)
async def approve_schedule_job(
    job_id: str,
    tenant_id: UUID = Depends(_tenant_id),
    db: AsyncSession = Depends(get_session),
):
    """Q.62.D.4 — promove o commit do job de DRAFT para LIVE.

    O CPO scheduler cria commits com `status=DRAFT` por defeito. Approver
    revê e chama este endpoint para marcar LIVE. Decision-as-code.
    """
    from arq.connections import RedisSettings, create_pool
    from arq.jobs import Job, JobStatus

    from src.shared.config import settings as _settings

    # 1. Lookup do job e extracção do commit_sha256.
    redis = await create_pool(RedisSettings.from_dsn(_settings.redis_url))
    try:
        job = Job(job_id, redis=redis)
        job_status = await job.status()
        if job_status is JobStatus.not_found:
            raise HTTPException(404, f"Job {job_id} not found in Arq queue")
        if job_status is not JobStatus.complete:
            raise HTTPException(
                409,
                f"Job {job_id} state is {job_status.value if hasattr(job_status, 'value') else job_status}; cannot approve until complete.",
            )
        result = await job.result(timeout=0.1)
    finally:
        await redis.close()

    commit_sha = (result or {}).get("commit_sha256")
    if not commit_sha:
        raise HTTPException(
            500, f"Job {job_id} complete but has no commit_sha256 in result"
        )

    # 2. Toggle ScheduleCommit.status DRAFT → LIVE.
    commits = CommitsService(db, tenant_id)
    commit = await _resolve_commit_or_404(commits, commit_sha)

    prev_status = getattr(commit, "status", "DRAFT") or "DRAFT"
    if prev_status == "LIVE":
        raise HTTPException(409, f"Commit {commit_sha[:8]} already LIVE")

    commit.status = "LIVE"
    await db.commit()

    return CPOJobApproveResponse(
        job_id=job_id,
        commit_sha256=commit_sha,
        previous_status=prev_status,
        new_status="LIVE",
        approved_at=datetime.utcnow().isoformat() + "Z",
    )
