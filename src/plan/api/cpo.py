"""
ProdPlan ONE — CPO v4 API (Sprint E + K)
=========================================

Sprint E endpoints (schedule the CPO v4 hyper-heuristic):
- `POST /v1/plan/cpo/schedule` — run the DRCFFS-R scheduler.

Sprint K endpoints (Schedule-as-Code + Timeline + Delta):
- `GET  /v1/plan/cpo/commits`                         — list commits
- `GET  /v1/plan/cpo/commits/{sha}`                   — commit detail
- `GET  /v1/plan/cpo/commits/{sha}/diff/{other}`      — diff between two commits
- `GET  /v1/plan/cpo/timeline`                        — MAP-Elites
                                                         representatives from
                                                         the latest commit
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.cpo.commits import CommitsService, ScheduleCommit
from src.plan.cpo.engine import CPOConfig, CPOv4Engine
from src.plan.cpo.fitness import FitnessConfig
from src.plan.cpo.state import FactoryState
from src.plan.engines.scheduling_adapter import SchedulingMachine
from src.plan.services.routing_resolver import RoutingResolver
from src.shared.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/plan/cpo", tags=["CPO v4 Scheduler"])


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


class CommitResponse(BaseModel):
    id: str
    tenant_id: str
    parent_id: Optional[str] = None
    commit_sha256: str
    short_sha: str
    author: str
    message: str
    kpis: Dict[str, Any] = Field(default_factory=dict)
    delta: Dict[str, Any] = Field(default_factory=dict)
    alternatives: List[Dict[str, Any]] = Field(default_factory=list)
    cpo_meta: Dict[str, Any] = Field(default_factory=dict)
    trust_index: float = 0.0
    operations_count: int = 0
    created_at: Optional[str] = None
    operations: Optional[List[Dict[str, Any]]] = None


class DiffResponse(BaseModel):
    from_sha: str
    to_sha: str
    added: List[Dict[str, Any]] = Field(default_factory=list)
    removed: List[Dict[str, Any]] = Field(default_factory=list)
    changed: List[Dict[str, Any]] = Field(default_factory=list)
    kpi_deltas: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, int] = Field(default_factory=dict)


class TimelineCandidate(BaseModel):
    rank: int
    fitness: float
    generation: int
    behavioral: Dict[str, float]
    chromosome: Dict[str, Any]


class TimelineResponse(BaseModel):
    commit_sha256: Optional[str]
    candidates: List[TimelineCandidate]


# =============================================================================
# Dependencies
# =============================================================================

from src.shared.auth.headers import require_tenant_header

_tenant_id = require_tenant_header


# =============================================================================
# Helpers
# =============================================================================

def _extract_mapelites_representatives(engine: CPOv4Engine, top_n: int = 10) -> List[Dict[str, Any]]:
    """Serialise the best-N MAP-Elites elites into commit-storable dicts."""
    archive = getattr(engine, "_mapelites", None)
    if archive is None or archive.is_empty():
        return []
    reps = archive.representatives(top_n)
    out: List[Dict[str, Any]] = []
    for rank, elite in enumerate(reps):
        out.append({
            "rank": rank,
            "fitness": round(float(elite.fitness), 4),
            "generation": int(elite.generation),
            "behavioral": dict(elite.behavioral),
            "chromosome": {
                "permutation": list(elite.chromosome.permutation),
                "edd_gap": int(elite.chromosome.edd_gap),
                "buffer_pct": float(elite.chromosome.buffer_pct),
                "quality_weight": float(elite.chromosome.quality_weight),
            },
        })
    return out


async def _resolve_commit_or_404(
    service: CommitsService,
    sha_or_prefix: str,
) -> ScheduleCommit:
    commit = await service.get_by_sha(sha_or_prefix)
    if commit is None:
        commit = await service.get_by_sha_prefix(sha_or_prefix)
    if commit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"commit {sha_or_prefix!r} not found",
        )
    return commit


# =============================================================================
# /schedule (Sprint E core + Sprint K commit auto-create)
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


# ─── Q.62.D.2 — async endpoint via Arq ─────────────────────────────────


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
    from arq.connections import ArqRedis, create_pool
    from src.shared.config import settings as _settings
    from arq.connections import RedisSettings

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


@router.get(
    "/schedule/job/{job_id}",
    response_model=CPOJobStatusResponse,
)
async def get_schedule_job_status(
    job_id: str,
    tenant_id: UUID = Depends(_tenant_id),
):
    """Q.62.D.2 — polling endpoint para o resultado do Arq job."""
    from arq.connections import create_pool
    from arq.jobs import Job, JobStatus
    from src.shared.config import settings as _settings
    from arq.connections import RedisSettings

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


# ─── Q.62.D.4 — approve job result (DRAFT → LIVE) ──────────────────────


class CPOJobApproveResponse(BaseModel):
    """Q.62.D.4 — PUT /schedule/job/{job_id}/approve."""

    job_id: str
    commit_sha256: str
    previous_status: str
    new_status: str
    approved_at: str


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
    from arq.connections import create_pool
    from arq.jobs import Job, JobStatus
    from arq.connections import RedisSettings
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


async def _parent_sha(service: CommitsService, commit: ScheduleCommit) -> Optional[str]:
    if commit.parent_id is None:
        return None
    # Best-effort fetch of parent's sha
    from sqlalchemy import select
    stmt = select(ScheduleCommit.commit_sha256).where(ScheduleCommit.id == commit.parent_id)
    result = await service.session.execute(stmt)
    row = result.first()
    return row[0] if row else None


async def _compute_trust_index_for_schedule(
    db: AsyncSession,
    tenant_id: UUID,
) -> float:
    """Sprint C 1.2 — compute the Trust Index for this schedule commit.

    Uses `TrustIndexV2Calculator` in factory scope (the only scope that
    makes sense for a full-horizon schedule). No signals provider is
    wired yet — the calculator falls back to neutral components
    (everything 1.0), which still exercises the v2 weights path so the
    composite isn't hardcoded to 0. Once Sprint AA.3 attaches a real
    `SignalsProvider`, this call lights up automatically.

    Returns a float in [0, 1]. On any DQA failure we log and return
    0.0 so the rest of the pipeline stays up — the approval gate then
    forces human review, which is the safer default.
    """
    try:
        from src.dqa.trust_v2 import SCOPE_FACTORY, TrustIndexV2Calculator

        calc = TrustIndexV2Calculator(db, tenant_id)
        result = await calc.compute_for_scope(SCOPE_FACTORY)
        return float(result.composite)
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("Trust Index computation failed: %s", exc)
        return 0.0


async def _load_product_prices(
    db: AsyncSession,
    tenant_id: UUID,
) -> Dict[str, float]:
    """Sprint C 1.1 — current sale prices per product (€).

    Pulls the latest-valid `ProductPricing` row per product for this
    tenant. Used by the CPO decoder to compute `throughput_eur_day`
    (F1 final wire — without this the fitness term stays at 0 and the
    €30–35K/day CEO target cannot be optimised).

    Returns `{product_id: sale_value_default_eur}` as strings → floats
    so the decoder's `product_price_eur` mapping is cheap to read.
    An empty dict is returned when no rows exist — decoder then falls
    back to `throughput_eur_day=0.0` (no-op, backwards compatible).
    """
    from datetime import date as _date
    from sqlalchemy import and_, or_, select

    from src.profit.models.pricing import ProductPricing

    today = _date.today()
    stmt = (
        select(
            ProductPricing.product_id,
            ProductPricing.sale_value_default_eur,
            ProductPricing.valid_from,
        )
        .where(
            and_(
                ProductPricing.tenant_id == tenant_id,
                ProductPricing.active.is_(True),
                ProductPricing.valid_from <= today,
                or_(
                    ProductPricing.valid_to.is_(None),
                    ProductPricing.valid_to >= today,
                ),
            )
        )
        .order_by(ProductPricing.product_id, ProductPricing.valid_from.desc())
    )
    try:
        rows = (await db.execute(stmt)).all()
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("product_pricing lookup failed, using empty map: %s", exc)
        return {}

    # Latest-valid per product (rows are ordered DESC by valid_from — keep first).
    prices: Dict[str, float] = {}
    for product_id, price, _valid_from in rows:
        key = str(product_id)
        if key not in prices:
            prices[key] = float(price)
    return prices


# =============================================================================
# /commits (Sprint K.1)
# =============================================================================

@router.get("/commits", response_model=List[CommitResponse])
async def list_commits(
    limit: int = Query(default=50, ge=1, le=500),
    tenant_id: UUID = Depends(_tenant_id),
    db: AsyncSession = Depends(get_session),
):
    """List the most recent schedule commits for the tenant."""
    service = CommitsService(db, tenant_id)
    rows = await service.list_commits(limit=limit)
    return [CommitResponse(**CommitsService.to_dict(r)) for r in rows]


@router.get("/commits/{sha}", response_model=CommitResponse)
async def get_commit(
    sha: str,
    include_operations: bool = Query(default=False),
    tenant_id: UUID = Depends(_tenant_id),
    db: AsyncSession = Depends(get_session),
):
    """Get one commit by full SHA-256 or short prefix (>=7 chars)."""
    service = CommitsService(db, tenant_id)
    commit = await _resolve_commit_or_404(service, sha)
    return CommitResponse(**CommitsService.to_dict(
        commit, include_operations=include_operations
    ))


# =============================================================================
# /commits/{sha}/orders (Sprint Q.54.D — plano optimizado consumível)
# =============================================================================
#
# A página Fábrica mostra o estado CRU do ERP (`/v1/plan/orders/active`).
# O CPO produz o plano optimizado dentro de um ScheduleCommit, mas não havia
# endpoint que o devolvesse na mesma forma que `/orders/active` para o
# frontend mostrar barco→fase→operador→molde+datas lado-a-lado.


class CommitOrderItem(BaseModel):
    """Uma ordem activa enriquecida com o plano optimizado do commit.

    Os primeiros campos são idênticos a `/v1/plan/orders/active`; os campos
    `optimized_*` / `assigned_*` / `scheduled_*` vêm do plano do CPO. Quando
    a ordem não está no plano, `in_optimized_plan=False` e os campos
    optimizados ficam a `null` (honesto — zero mocks)."""

    id: str
    hull: Optional[str] = None
    product_name: str
    product_type: Optional[str] = None
    customer_name: Optional[str] = None
    phase: Optional[str] = None
    phase_sequence: Optional[int] = None
    status: str
    created_date: Optional[str] = None
    transport_date: Optional[str] = None
    # --- plano optimizado (Q.54.D) ---
    in_optimized_plan: bool = False
    optimized_phase: Optional[str] = None
    optimized_phase_sequence: Optional[int] = None
    assigned_employee_id: Optional[str] = None
    assigned_employee_name: Optional[str] = None
    assigned_machine_id: Optional[str] = None
    scheduled_start: Optional[str] = None
    scheduled_end: Optional[str] = None


class CommitOrdersResponse(BaseModel):
    """Resposta de `GET /v1/plan/cpo/commits/{sha}/orders`."""

    commit_sha256: str
    short_sha: str
    kpis: Dict[str, Any] = Field(default_factory=dict)
    orders: List[CommitOrderItem] = Field(default_factory=list)


@router.get("/commits/{sha}/orders", response_model=CommitOrdersResponse)
async def get_commit_orders(
    sha: str,
    tenant_id: UUID = Depends(_tenant_id),
    db: AsyncSession = Depends(get_session),
):
    """Q.54.D — ordens activas + o plano optimizado do CPO, na mesma forma.

    `sha` aceita um SHA-256 completo, um prefixo curto (>=7 chars), ou a
    palavra-chave `latest` (o commit mais recente do tenant). Cada item tem
    a forma de `/v1/plan/orders/active` mais os campos optimizados do plano
    (fase/operador/máquina/datas). Junta também os KPIs do commit
    (makespan, setups, utilization, num_late_orders) na resposta.

    A junção é por `order_id` da operação ↔ `legacy_id` (nº de OF) da
    `ProductionOrder`. Campo que não resolve fica `null` — uma ordem fora
    do plano vem com `in_optimized_plan=False`.
    """
    from sqlalchemy import select as _select

    from src.core.models.employee import Employee
    from src.plan.models.order import OrderStatus, ProductionOrder
    from src.plan.services.cpo_commit_orders import merge_commit_with_orders
    from src.plan.services.phase_classification import is_completed_phase

    service = CommitsService(db, tenant_id)
    if sha == "latest":
        commit = await service.get_latest()
        if commit is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="no schedule commit yet — run /v1/plan/cpo/schedule first",
            )
    else:
        commit = await _resolve_commit_or_404(service, sha)

    # Ordens activas — mesmo filtro de /orders/active (exclui CANCELLED +
    # fases terminais). O volume é baixo (~500 ordens).
    order_rows = (
        await db.execute(
            _select(ProductionOrder).where(
                (ProductionOrder.tenant_id == tenant_id)
                & (ProductionOrder.status != OrderStatus.CANCELLED)
            )
        )
    ).scalars().all()
    active_orders = [
        o for o in order_rows if not is_completed_phase(o.current_phase_name)
    ]

    # Mapa employee_code → employee_name para resolver o operador atribuído.
    emp_rows = (
        await db.execute(
            _select(Employee).where(Employee.tenant_id == tenant_id)
        )
    ).scalars().all()
    employee_names = {
        str(e.employee_code): e.employee_name
        for e in emp_rows
        if e.employee_code
    }

    merged = merge_commit_with_orders(
        operations=list(commit.operations or []),
        orders=list(active_orders),
        employee_names=employee_names,
    )

    return CommitOrdersResponse(
        commit_sha256=commit.commit_sha256,
        short_sha=commit.commit_sha256[:12],
        kpis=dict(commit.kpis or {}),
        orders=[CommitOrderItem(**m) for m in merged],
    )


# =============================================================================
# /commits/{sha}/diff/{other} (Sprint K.3 — Delta view)
# =============================================================================

@router.get("/commits/{from_sha}/diff/{to_sha}", response_model=DiffResponse)
async def diff_commits(
    from_sha: str,
    to_sha: str,
    tenant_id: UUID = Depends(_tenant_id),
    db: AsyncSession = Depends(get_session),
):
    """Compute the delta between two commits' operations + KPIs."""
    service = CommitsService(db, tenant_id)
    try:
        diff = await service.diff(from_sha, to_sha)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return DiffResponse(**diff)


# =============================================================================
# /timeline (Sprint K.2)
# =============================================================================

@router.get("/timeline", response_model=TimelineResponse)
async def get_timeline(
    commit_sha: Optional[str] = Query(default=None),
    tenant_id: UUID = Depends(_tenant_id),
    db: AsyncSession = Depends(get_session),
):
    """
    Return up to 10 MAP-Elites candidate schedules from the last commit
    (or the commit identified by `commit_sha`).
    Humans pick one to promote via a governance decision.
    """
    service = CommitsService(db, tenant_id)
    if commit_sha:
        commit = await _resolve_commit_or_404(service, commit_sha)
    else:
        commit = await service.get_latest()
    if commit is None:
        return TimelineResponse(commit_sha256=None, candidates=[])

    candidates = [
        TimelineCandidate(
            rank=int(c.get("rank", 0)),
            fitness=float(c.get("fitness", 0.0)),
            generation=int(c.get("generation", 0)),
            behavioral=dict(c.get("behavioral", {})),
            chromosome=dict(c.get("chromosome", {})),
        )
        for c in (commit.alternatives or [])
    ]
    return TimelineResponse(
        commit_sha256=commit.commit_sha256,
        candidates=candidates,
    )


# =============================================================================
# /commits/{sha}/alternatives (Sprint M.7 — WG10)
# =============================================================================
#
# Enriches the raw MAP-Elites alternatives stored at commit time with:
#   * deltas vs the primary commit's KPIs (human-readable percentages)
#   * a deterministic narrative explaining the trade-off
#   * optional `n` cap for smaller Timeline cards
#
# The narrative is template-based (not LLM) so the endpoint stays fast + cheap;
# Sprint S.3 will upgrade this to Instructor+Pydantic structured output.

def _relative_delta(a: Any, b: Any) -> Optional[float]:
    """(b-a)/|a| as a fraction. Returns None when either value is non-numeric
    or `a` is zero (undefined %)."""
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        return None
    if a == 0:
        return None
    return (float(b) - float(a)) / abs(float(a))


def _format_delta_pct(delta: Optional[float]) -> Optional[str]:
    if delta is None:
        return None
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta * 100:.1f}%"


def _build_narrative(vs_primary: Dict[str, Optional[str]]) -> str:
    """Template-based trade-off summary. Picks the two most salient dimensions
    (largest |delta|) and describes them in PT-PT."""
    labels = {
        "avg_utilization": "utilização média",
        "total_tardiness_hours": "atraso total",
        "num_late_orders": "ordens em atraso",
    }
    parts: List[tuple[float, str]] = []
    for key, fmt in vs_primary.items():
        if fmt is None:
            continue
        try:
            # "+5.2%" → 5.2
            magnitude = abs(float(fmt.rstrip("%")))
        except ValueError:
            continue
        parts.append((magnitude, f"{labels.get(key, key)}: {fmt}"))
    if not parts:
        return "Trade-off indisponível (KPIs não comparáveis)."
    parts.sort(reverse=True)
    return "Trade-offs principais — " + "; ".join(p[1] for p in parts[:3]) + "."


class AlternativeEnriched(BaseModel):
    rank: int
    fitness: float
    generation: int
    descriptor: Dict[str, Any]
    vs_primary: Dict[str, Optional[str]]
    trade_off_narrative: str


class AlternativesResponse(BaseModel):
    commit_sha256: str
    primary_kpis: Dict[str, Any]
    alternatives: List[AlternativeEnriched]


@router.get("/commits/{sha}/alternatives", response_model=AlternativesResponse)
async def get_alternatives(
    sha: str,
    n: int = Query(default=8, ge=1, le=50, description="Max alternatives to return"),
    tenant_id: UUID = Depends(_tenant_id),
    db: AsyncSession = Depends(get_session),
):
    """Enriched MAP-Elites alternatives for WG10.

    Each alternative ships with `vs_primary` deltas (as percentage strings the
    frontend can display directly) and a deterministic `trade_off_narrative`
    describing the two most salient differences.
    """
    service = CommitsService(db, tenant_id)
    commit = await _resolve_commit_or_404(service, sha)

    primary_kpis = dict(commit.kpis or {})
    raw_alts = list(commit.alternatives or [])[:n]

    enriched: List[AlternativeEnriched] = []
    for c in raw_alts:
        behavioral = dict(c.get("behavioral") or {})
        # Behavioural descriptors overlap with primary KPIs on several axes;
        # compute %-deltas where both sides are numeric.
        vs: Dict[str, Optional[str]] = {}
        for key in behavioral:
            vs[key] = _format_delta_pct(
                _relative_delta(primary_kpis.get(key), behavioral.get(key))
            )
        enriched.append(AlternativeEnriched(
            rank=int(c.get("rank", 0)),
            fitness=float(c.get("fitness", 0.0)),
            generation=int(c.get("generation", 0)),
            descriptor=behavioral,
            vs_primary=vs,
            trade_off_narrative=_build_narrative(vs),
        ))

    return AlternativesResponse(
        commit_sha256=commit.commit_sha256,
        primary_kpis=primary_kpis,
        alternatives=enriched,
    )


# =============================================================================
# Sprint B CO1 — record a decision on a commit's alternatives
# =============================================================================


class CommitDecisionRequest(BaseModel):
    """Body for `POST /v1/plan/cpo/commits/{sha}/decide`.

    * `chosen_alt_idx` — index into `commit.alternatives` the operator picked,
      or `None` when accepting the primary commit without ranking.
    * `rejected_alt_idxs` — the alternatives they explicitly declined. Each
      becomes a `rejected_alternatives` entry with KPIs + delta vs chosen.
    * `reason` — free-text rationale the operator can optionally give
      ("too many setups", "laminagem overloaded on Friday").
    * `decided_by` — who made the call (falls back to "unknown" when the
      auth layer isn't wired yet; Sprint D replaces this with the real user).
    """

    chosen_alt_idx: Optional[int] = Field(default=None, ge=0)
    rejected_alt_idxs: List[int] = Field(default_factory=list)
    reason: Optional[str] = Field(default=None, max_length=500)
    decided_by: str = Field(default="unknown", max_length=255)

    # Sprint Q.5 — categorical rejection signal (mirrors
    # `src.governance.models.RejectionCategory`). Required by the API
    # validator below when `rejected_alt_idxs` is non-empty so the
    # PreferenceRuleDetector has a tagged feature on every rejection.
    rejection_category: Optional[str] = Field(
        default=None,
        description=(
            "One of COST | QUALITY | CUSTOMER | CAPACITY | MOLD | "
            "WORKFORCE | OTHER. Required when rejected_alt_idxs is non-empty."
        ),
        max_length=32,
    )


class CommitDecisionResponse(BaseModel):
    commit_sha256: str
    rejected_alternatives: List[Dict[str, Any]]
    user_preference_signal: Dict[str, Any]


@router.post(
    "/commits/{sha}/decide",
    response_model=CommitDecisionResponse,
    status_code=status.HTTP_200_OK,
)
async def decide_on_commit(
    sha: str,
    body: CommitDecisionRequest,
    tenant_id: UUID = Depends(_tenant_id),
    db: AsyncSession = Depends(get_session),
):
    """Record the operator's accept/reject choice on a commit's alternatives.

    This is the single most important endpoint of the learning system —
    each call creates a fresh data point for every MAP-Elites alternative
    the operator declined (KPIs + delta vs chosen + weekday/hour). The
    PreferenceRuleDetector (Sprint C) walks these rows nightly and turns
    recurring rejection patterns into actionable rules.
    """
    # Sprint Q.5 — categorical rejection signal mandatory when alts rejected
    if body.rejected_alt_idxs and not body.rejection_category:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "rejection_category is required when rejected_alt_idxs is "
                "non-empty (one of COST, QUALITY, CUSTOMER, CAPACITY, MOLD, "
                "WORKFORCE, OTHER)"
            ),
        )
    if body.rejection_category:
        try:
            from src.governance.models import RejectionCategory
            RejectionCategory(body.rejection_category)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"unknown rejection_category={body.rejection_category!r}; "
                    "allowed: COST, QUALITY, CUSTOMER, CAPACITY, MOLD, "
                    "WORKFORCE, OTHER"
                ),
            )
    # Sprint R.2 — free-text rationale mandatory (≥10 chars) when there
    # are rejections, so the DPO/Camada-3 dataset has clean training
    # signal. The category answers "why category", the reason answers
    # "why this plan specifically". Validated AFTER category checks so
    # the user gets the more obvious "fix your category" error first.
    if body.rejected_alt_idxs:
        reason_text = (body.reason or "").strip()
        if len(reason_text) < 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "reason is required and must have ≥10 characters when "
                    "rejected_alt_idxs is non-empty (Camada 3 needs clean "
                    "rationale to learn from)"
                ),
            )

    service = CommitsService(db, tenant_id)
    commit = await _resolve_commit_or_404(service, sha)

    # Tag the categorical signal into `reason` so it survives in the
    # commit row even before `record_decision` learns about the field
    # natively. Format: "[CAT:COST] free text" — the detector can split
    # on the prefix without ambiguity. This stays a temporary shim until
    # `ScheduleCommit.user_preference_signal.rejection_category` is wired
    # explicitly in a follow-up.
    decision_reason = body.reason
    if body.rejection_category:
        prefix = f"[CAT:{body.rejection_category}]"
        decision_reason = (
            f"{prefix} {body.reason}" if body.reason else prefix
        )

    try:
        updated = await service.record_decision(
            commit_id=commit.id,
            chosen_alt_idx=body.chosen_alt_idx,
            rejected_alt_idxs=body.rejected_alt_idxs,
            decided_by=body.decided_by,
            reason=decision_reason,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return CommitDecisionResponse(
        commit_sha256=updated.commit_sha256,
        rejected_alternatives=list(updated.rejected_alternatives or []),
        user_preference_signal=dict(updated.user_preference_signal or {}),
    )


# =============================================================================
# Sprint Q.13.A — Plan v4 §6.2: alternative worker pairs for an op
# =============================================================================

class WorkerPairItem(BaseModel):
    """One ranked pair candidate. The frontend §6.2 promise renders these
    side-by-side with their score so the manager sees, e.g.:

    "Paulo Gomes + Maria Silva (8.2) OU João Costa + Ana Reis (6.1)"
    """
    chefe_id: str = Field(..., description="ERP employee_id of the team leader")
    partner_id: Optional[str] = Field(
        default=None,
        description="ERP employee_id of the partner (null for solo fallback "
                    "in PREFERRED-only phases like Laminagem post-Q.8)",
    )
    score: float = Field(
        ..., ge=0.0, le=10.0,
        description="Display score 0-10 (higher is better). 10 = lowest cost "
                    "in the pool; 0 = highest cost. Rounded to 0.1.",
    )


class WorkerPairsResponse(BaseModel):
    operation_id: str
    phase_id: Optional[str] = None
    needs_pair: bool = Field(
        ..., description="True iff the phase is in PAIR_REQUIRED or "
                          "PAIR_PREFERRED — when False, the response is empty.",
    )
    pairs: List[WorkerPairItem]


@router.get(
    "/operations/{operation_id}/worker-pairs",
    response_model=WorkerPairsResponse,
)
async def get_worker_pairs(
    operation_id: str,
    top_n: int = Query(default=3, ge=1, le=10),
    tenant_id: UUID = Depends(_tenant_id),
    db: AsyncSession = Depends(get_session),
):
    """Sprint Q.13.A — top-N pair candidates for an op.

    Plan v4 §6.2 promises the manager sees alternative worker pairs
    BEFORE confirming an assignment, with scores. This endpoint backs
    the `<WorkerPairCard>` component on DragDropPlanner.

    Resolves the op from the latest ScheduleCommit (so the operator
    is choosing between alternatives for an already-planned op, not
    a hypothetical one). The phase + skill pool are read from the
    loaded `FactoryState`. Returns `needs_pair=False` + empty pairs
    list when the op's phase doesn't need a pair (the frontend then
    renders the single-worker UI).
    """
    state = await FactoryState.load(db, tenant_id)
    commits = CommitsService(db, tenant_id)
    parent = await commits.get_latest()
    if parent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no schedule commit yet — run /v1/plan/cpo/schedule first",
        )

    target_op = None
    for op_dict in (parent.operations or []):
        if str(op_dict.get("operation_id") or "") == operation_id:
            target_op = op_dict
            break
    if target_op is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"operation_id {operation_id!r} not found in latest commit",
        )

    # Build a thin SchedulingOperation just for pair_assignment lookup —
    # we only need phase_id + operation_id, not the full op.
    from src.plan.cpo.pair_assignment import (
        needs_pair_assignment,
        rank_pairs,
    )
    from src.plan.engines.scheduling_adapter import SchedulingOperation

    op = SchedulingOperation(
        operation_id=operation_id,
        order_id=str(target_op.get("order_id") or ""),
        product_id=str(target_op.get("product_id") or ""),
        sequence=int(target_op.get("sequence") or 0),
        operation_code=str(target_op.get("operation_code") or ""),
        duration_minutes=float(target_op.get("duration_minutes") or 0),
        machine_id=target_op.get("machine_id"),
        phase_id=str(target_op.get("phase_id") or ""),
    )

    needs = needs_pair_assignment(op, state)
    if not needs:
        return WorkerPairsResponse(
            operation_id=operation_id,
            phase_id=op.phase_id,
            needs_pair=False,
            pairs=[],
        )

    ranked = rank_pairs(op, state, top_n=top_n)
    return WorkerPairsResponse(
        operation_id=operation_id,
        phase_id=op.phase_id,
        needs_pair=True,
        pairs=[
            WorkerPairItem(
                chefe_id=str(p["chefe_id"]),
                partner_id=str(p["partner_id"]) if p["partner_id"] else None,
                score=float(p["score"]),
            )
            for p in ranked
        ],
    )
