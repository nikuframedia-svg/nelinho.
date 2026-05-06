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
    """Run CPO v4 and persist the result as a Schedule-as-Code commit."""
    horizon_start = datetime.utcnow()
    horizon_end = horizon_start + timedelta(days=request.horizon_days)

    state = await FactoryState.load(db, tenant_id)

    # FASE 1B.1 (CRIT-15) — refuse to schedule when FactoryState load failed.
    # An empty state means skill_matrix={} and molds_by_model={}: the
    # scheduler would happily assign any worker to any phase, producing a
    # plan that ignores domain constraints. Better to fail loud than to
    # ship a "valid" but unsafe schedule.
    if not state.loaded_ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"FactoryState unavailable for tenant {tenant_id}: "
                f"{state.load_error or 'unknown error'}. Ingest curated "
                "data via /v1/factory-data/ingest before scheduling."
            ),
        )

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

    # FASE 0.3 (DEVA-02) — wire the active DurationModel into the routing
    # resolver. When the model exists, the standard-template fallback uses
    # `predict(...).p50_hours` instead of the legacy `horas_standard * 2.0`
    # buffer. With no active artifact, behaviour is identical to before.
    from src.ml.registry_loader import load_active_duration_predictor
    duration_predictor = await load_active_duration_predictor(db, tenant_id)
    if duration_predictor is not None:
        logger.info("CPO schedule: DurationModel active — wired into RoutingResolver")
    resolver = RoutingResolver(state, duration_predictor=duration_predictor)
    operations = resolver.resolve_many(orders, horizon_start=horizon_start)

    # FASE 1B.3 (CRIT-13) — when the resolver fell back to standards
    # because the curated semantic engine was unavailable, emit an alert
    # so the operator knows the schedule was built on 2× buffer estimates
    # rather than real history. Best-effort: never block scheduling.
    if resolver.engine_unavailable:
        try:
            from src.copilot.alerts.models import (
                CODE_ROUTING_ENGINE_UNAVAILABLE,
                CopilotAlert,
            )
            alert = CopilotAlert(
                tenant_id=tenant_id,
                severity="WARN",
                code=CODE_ROUTING_ENGINE_UNAVAILABLE,
                title="Routing engine unavailable — schedule built on 2× buffer templates",
                message_pt=(
                    "O motor de routing não conseguiu aceder à camada curada "
                    "(factory_data_product). O scheduler caiu para os templates "
                    "FasesStandardModelos com buffer 2× — durações podem divergir "
                    "até 25× da realidade. Re-ingere os dados curados e volta a planear."
                ),
                context={"resolved_orders": len(orders)},
                entity_refs=[],
            )
            db.add(alert)
            await db.flush()
        except Exception as alert_exc:  # pragma: no cover — defensive
            logger.warning("CPO schedule: failed to emit routing alert: %s", alert_exc)
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

    # Sprint Q.9 Onda 1.2 — Camada 2 wire. Build the fitness config via
    # `from_tenant_config` so per-tenant adaptive weights (learned from
    # ≥50 commits' rejected_alternatives) drive the GA. When the tenant
    # has no learned weights yet, this returns the same defaults as
    # `FitnessConfig()` — silent fallback by design.
    fitness_config = await FitnessConfig.from_tenant_config(db, tenant_id)

    # FASE 0.2 (DEVA-01) — wire the active QualityRiskModel into the GA.
    # Without this, Sprint H.1 trained but the predictor was always None
    # and the 0.10 quality_risk weight resolved to 0 every generation.
    from src.ml.registry_loader import load_active_quality_risk_predictor
    quality_risk_predictor = await load_active_quality_risk_predictor(db, tenant_id)
    if quality_risk_predictor is not None:
        fitness_config.quality_risk_predictor = quality_risk_predictor
        logger.info("CPO schedule: QualityRiskModel active — predictor wired into fitness")

    engine = CPOv4Engine(
        state=state,
        config=CPOConfig(
            population_size=request.population_size,
            generations=request.generations,
            time_limit_sec=request.time_limit_sec,
        ),
        fitness_config=fitness_config,
    )

    # Sprint C 1.1 — load current product prices so the decoder can compute
    # throughput €/day (F1). Without this lookup the fitness term stays at 0
    # and the CEO never sees the real €/day target being optimised.
    product_price_eur = await _load_product_prices(db, tenant_id)

    result = engine.schedule(
        operations, machines, horizon_start, horizon_end,
        product_price_eur=product_price_eur,
    )

    # FASE 0.3 — surface duration model wiring for observability/E2E asserts
    result.setdefault("cpo_meta", {})["duration_model_used"] = (
        duration_predictor is not None
    )

    # Q.17.F.2 — yaml_policy SCHEDULE_PROPOSE hook. Fire any tenant rules
    # that subscribe to this event; if any ``block`` action triggers,
    # refuse to commit the schedule and surface the rule's reason as 409.
    # Other actions (alert/modify_fitness/notify) are best-effort and
    # don't block the response. Failure of the engine itself is
    # swallowed — never let yaml_policy break the scheduler.
    try:
        from src.governance.yaml_policy import EventType as _YPEventType
        from src.governance.yaml_policy.engine import RuleEngine as _RuleEngine
        from src.governance.yaml_policy.runtime import get_engine as _get_yp_engine
        _yp_payload = {
            "tenant_id": str(tenant_id),
            "horizon_days": int(request.horizon_days),
            "operations_count": int(len(result.get("operations", []))),
            "fitness_score": float(result.get("fitness_score", 0.0)),
            "makespan_hours": float(result.get("makespan_hours", 0.0)),
            "tardiness_hours": float(result.get("total_tardiness_hours", 0.0)),
        }
        _yp_fired = await _get_yp_engine().on_event(
            _YPEventType.SCHEDULE_PROPOSE,
            _yp_payload,
            tenant_id=tenant_id,
            session=db,
        )
        _yp_blocks = _RuleEngine.block_results(_yp_fired)
        if _yp_blocks:
            _block = _yp_blocks[0]
            _rule_id = next(
                (r.id for r, results in _yp_fired
                 if any(rs.action == "block" for rs in results)),
                "?",
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "blocked_by_yaml_policy",
                    "rule_id": _rule_id,
                    "scope": _block.payload.get("scope"),
                    "reason_pt": _block.payload.get("reason_pt", ""),
                },
            )
        if _yp_fired:
            logger.info(
                "yaml_policy: schedule_propose fired %d rules (no blocks)",
                len(_yp_fired),
            )
    except HTTPException:
        raise  # propagate the 409 we just raised
    except Exception as _yp_exc:
        logger.warning(f"yaml_policy SCHEDULE_PROPOSE hook failed: {_yp_exc}")

    # Sprint C 1.2 — real Trust Index for this schedule commit.
    # Uses the v2 Calculator in factory scope, which reads tenant weights
    # and falls back to neutral components when no signals provider is
    # wired. The result drives the auto-commit gate in decisions.py.
    trust_index_value = await _compute_trust_index_for_schedule(db, tenant_id)

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
            trust_index=trust_index_value,  # Sprint C 1.2 — real TI from DQA calculator
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
        degraded=bool(result.get("degraded", False)),
        fallback_reason=result.get("fallback_reason"),
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
