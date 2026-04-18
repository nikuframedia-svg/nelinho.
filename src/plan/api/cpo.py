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

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.cpo.commits import CommitsService, ScheduleCommit
from src.plan.cpo.engine import CPOConfig, CPOv4Engine
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

def _tenant_id(
    x_tenant_id: UUID = Header(default=UUID("00000000-0000-0000-0000-000000000000")),
) -> UUID:
    return x_tenant_id


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
    """Run CPO v4 and persist the result as a Schedule-as-Code commit."""
    horizon_start = datetime.utcnow()
    horizon_end = horizon_start + timedelta(days=request.horizon_days)

    state = await FactoryState.load(db, tenant_id)

    orders = request.orders or state.open_orders
    if not orders:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No orders available. Either provide `orders` in the request "
                "or ingest data via /v1/factory-data/ingest to populate the "
                "curated layer."
            ),
        )

    resolver = RoutingResolver(state)
    operations = resolver.resolve_many(orders, horizon_start=horizon_start)
    if not operations:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Routing resolver returned no operations. No history or "
                "standard template found for these orders."
            ),
        )

    if request.machines:
        machines = [
            SchedulingMachine(
                machine_id=m.machine_id,
                name=m.name or m.machine_id,
                capacity=m.capacity,
                speed_factor=m.speed_factor,
                centro_custo=m.centro_custo,
            )
            for m in request.machines
        ]
    else:
        machines = [SchedulingMachine(machine_id="MANUAL", name="Manual pool")]

    engine = CPOv4Engine(
        state=state,
        config=CPOConfig(
            population_size=request.population_size,
            generations=request.generations,
            time_limit_sec=request.time_limit_sec,
        ),
    )

    result = engine.schedule(operations, machines, horizon_start, horizon_end)

    # Sprint K — persist a commit
    commit_sha: Optional[str] = None
    parent_sha: Optional[str] = None
    try:
        commits = CommitsService(db, tenant_id)
        alternatives = _extract_mapelites_representatives(engine)
        commit = await commits.create_from_schedule(
            schedule_result=result,
            mapelites_representatives=alternatives,
            delta=request.delta,
            author=request.author,
            message=request.message,
            trust_index=0.0,  # full TI calculation lives in DQA (Fase C3 of the old plan)
        )
        commit_sha = commit.commit_sha256
        parent_sha = await _parent_sha(commits, commit)
    except Exception as e:
        # Never let commit persistence block a working schedule.
        logger.warning(f"Schedule-as-Code commit failed: {e}", exc_info=True)

    return CPOScheduleResponse(
        tenant_id=str(tenant_id),
        engine_used=result.get("engine_used", "cpo_v4"),
        status=result.get("status", "unknown"),
        solve_time_sec=float(result.get("solve_time_sec", 0.0)),
        makespan_hours=float(result.get("makespan_hours", 0.0)),
        total_tardiness_hours=float(result.get("total_tardiness_hours", 0.0)),
        num_late_orders=int(result.get("num_late_orders", 0)),
        setups=int(result.get("setups", 0)),
        avg_utilization=float(result.get("avg_utilization", 0.0)),
        safety_net_triggered=bool(result.get("safety_net_triggered", False)),
        cpo_meta=result.get("cpo_meta", {}),
        operations=result.get("operations", []),
        warnings=list(result.get("warnings", [])),
        infeasible_op_ids=list(result.get("infeasible_op_ids", [])),
        commit_sha256=commit_sha,
        parent_sha256=parent_sha,
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
