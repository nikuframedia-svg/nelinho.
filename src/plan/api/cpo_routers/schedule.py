"""Q.67.6.B2 — sub-router para `/schedule*` (sync + async Arq + approve).

Endpoints:
* POST /schedule              — sync run (Sprint E + Sprint K commit)
* POST /schedule/async        — Arq enqueue (Q.62.D.2)
* GET  /schedule/job/{id}     — Arq polling (Q.62.D.2)
* PUT  /schedule/job/{id}/approve — DRAFT → LIVE (Q.62.D.4)
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.governance.audit_service import audit_change
from src.plan.api._cpo_common import _resolve_commit_or_404, _tenant_id
from src.plan.cpo.commits import CommitsService
from src.shared.auth.headers import get_current_user_or_dev_header
from src.shared.auth.jwt_handler import UserContext
from src.shared.database import get_session
from src.shared.time import utc_now

router = APIRouter()

# Q.138.D — defaults do request alinhados com Blueprint v2.0 (CPOConfig).
# Constantes _UPPER_SNAKE isentas do H0 hardcode scan. Reflectidos também em
# scheduler_run._REQ_DEFAULT_* para que o sentinel funcione coerentemente.
_REQ_DEFAULT_TIME_LIMIT_S: float = 120.0   # 2 min → ~40 gerações/1500 ops
_REQ_DEFAULT_GENERATIONS_V2: int = 200     # Blueprint §5.5 FRRMAB window
_MAX_TIME_LIMIT_S: float = 600.0           # tecto: 10 min (run interactiva longa)
_MAX_GENERATIONS: int = 1000              # tecto: 1000 gerações (análise offline)


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
    # Q.138.D — via _REQ_DEFAULT_TIME_LIMIT_S / _MAX_TIME_LIMIT_S (constantes).
    time_limit_sec: float = Field(default=_REQ_DEFAULT_TIME_LIMIT_S, ge=1.0, le=_MAX_TIME_LIMIT_S)
    population_size: int = Field(default=100, ge=10, le=500)
    # Q.138.D — via _REQ_DEFAULT_GENERATIONS_V2 / _MAX_GENERATIONS (constantes).
    generations: int = Field(default=_REQ_DEFAULT_GENERATIONS_V2, ge=1, le=_MAX_GENERATIONS)
    # Q.161.A — horizonte de ordens a planear. None (default) = horizonte
    # interativo de 200 (botão responsivo). 0 = TODOS os em-produção (robô de
    # fundo, com time_limit maior). >0 = esse cap. O clamp efetivo ao pool
    # em-produção vive em state_loaders._OPEN_ORDERS_HARD_CAP. Só afeta
    # state.open_orders (ignorado quando `orders` vem explícito no request).
    plan_cap: Optional[int] = Field(default=None, ge=0)

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
    # Q.153.A2 — dívida herdada (já vencida à entrada) vs atraso novo/evitável
    # (causado pelo plano, medido para lá de hoje). Default 0 = back-compat.
    num_already_overdue: int = 0
    num_newly_late: int = 0
    tardiness_beyond_today_h: float = 0.0
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
    # Q.131.H — honestidade: ordens deixadas FORA do plano por não terem rota
    # (sem histórico nem template do ERP), e a fração de ordens planeadas. O
    # frontend mostra um aviso em vez de as omitir silenciosamente. Default
    # vazio/1.0 = back-compat (nada por planear).
    unplanned_orders: List[str] = Field(default_factory=list)
    orders_coverage: float = 1.0
    # Q.115.X7 — % alinhamento com target diário; null se sem target configurado.
    # Frontend Q.115.J/K podem usar este campo futuramente.
    revenue_alignment_pct: Optional[float] = None
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
    # Q.171.B — era user_id=Depends(_tenant_id) (placeholder): o AUTOR dos
    # commits do worker ficava o UUID do TENANT — auditoria sem ator real
    # e SoD do approve inoperante para planos async.
    user: UserContext = Depends(get_current_user_or_dev_header),
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

    # Q.171.A — dedup do caminho INTERATIVO (o robô já usa _job_id próprio):
    # sem _job_id o Arq gera id aleatório e o branch "job is None" era morto —
    # duplo-clique no "Replanear" enfileirava 2 solves. O bucket por minuto
    # dedupa cliques rápidos sem bloquear re-runs legítimos (keep_result=1h
    # bloquearia o mesmo payload durante 1 hora).
    payload = request.model_dump(mode="json")
    _digest = hashlib.sha256(
        repr(sorted(payload.items())).encode()
    ).hexdigest()[:16]
    _bucket = utc_now().strftime("%Y%m%d%H%M")
    job_key = f"cpo:{tenant_id}:{_digest}:{_bucket}"

    try:
        job = await redis.enqueue_job(
            "cpo_schedule_job",
            payload,
            str(tenant_id),
            str(user.user_id),
            _job_id=job_key,
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
        enqueued_at=utc_now().isoformat(),
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

        # Arq devolve um `JobDef` enquanto o job está na fila/a correr (só tem
        # `enqueue_time`) e um `JobResult` após terminar (tem `start_time` e
        # `finish_time`). Aceder `.start_time`/`.finish_time` num `JobDef`
        # levanta AttributeError -> 500 a cada poll do progresso. `getattr`
        # degrada para None até o job completar (started/completed só aparecem
        # quando o JobResult existe).
        enq = getattr(info, "enqueue_time", None) if info else None
        started = getattr(info, "start_time", None) if info else None
        finished = getattr(info, "finish_time", None) if info else None
        return CPOJobStatusResponse(
            job_id=job_id,
            state=job_status.value if hasattr(job_status, "value") else str(job_status),
            result=result,
            error=error_str,
            enqueued_at=(enq.isoformat() + "Z") if enq else None,
            started_at=(started.isoformat() + "Z") if started else None,
            completed_at=(finished.isoformat() + "Z") if finished else None,
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
    approver: UserContext = Depends(get_current_user_or_dev_header),
):
    """Q.62.D.4 — promove o commit do job de DRAFT para LIVE.

    O CPO scheduler cria commits com `status=DRAFT` por defeito. Approver
    revê e chama este endpoint para marcar LIVE. Decision-as-code.

    Q.132.G — write-gate "Palantir level":
      * SoD (invariante governança): o aprovador não pode ser o proponente do
        plano (`commit.author`); auto-aprovação é 403.
      * Audit (invariante 7): a transição DRAFT→LIVE escreve `audit_log` na
        MESMA transacção que o `commit.status = LIVE`.
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
    # Q.171.A — re-lê com FOR UPDATE: sem lock, 2 aprovadores em paralelo
    # passavam ambos o check e promoviam os dois (TOCTOU).
    locked = await commits.lock_by_id(commit.id)
    if locked is None:
        raise HTTPException(404, f"Commit {commit_sha[:8]} desapareceu")
    commit = locked

    prev_status = getattr(commit, "status", "DRAFT") or "DRAFT"
    if prev_status == "LIVE":
        raise HTTPException(409, f"Commit {commit_sha[:8]} already LIVE")

    # Q.132.G — SoD: o proponente (commit.author, gravado pelo worker) não pode
    # aprovar o próprio plano. Commits "system" (auto/scheduled) não têm
    # proponente humano → qualquer aprovador autorizado pode promover.
    proposer = str(getattr(commit, "author", "") or "")
    if proposer and proposer != "system" and proposer == str(approver.user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Segregação de funções: não pode aprovar o plano que propôs. "
                "Outro utilizador autorizado tem de o rever."
            ),
        )

    # Q.132.G — audit_log na MESMA tx que a mudança de estado (invariante 7).
    commit.status = "LIVE"
    await audit_change(
        db,
        tenant_id=tenant_id,
        entity_type="schedule_commit",
        entity_id=commit.id,
        action="UPDATE",
        old_values={"status": prev_status},
        new_values={"status": "LIVE"},
        actor_id=approver.user_id,
        actor_role=str(getattr(approver, "role", "") or ""),
        reason=f"approve CPO schedule {commit_sha[:8]} DRAFT->LIVE",
    )
    await db.commit()

    return CPOJobApproveResponse(
        job_id=job_id,
        commit_sha256=commit_sha,
        previous_status=prev_status,
        new_status="LIVE",
        approved_at=utc_now().isoformat(),
    )
