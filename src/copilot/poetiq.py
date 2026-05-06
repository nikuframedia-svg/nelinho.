"""
ProdPlan ONE — POETIQ Loop (Sprint K.4, simplified MVP)
========================================================

Propose → Optimize → Evaluate → (Test) → Iterate → Qualify.

This is the simplified version of the plan's POETIQ loop: a single-shot
"copilot proposes a delta → CPO schedules it → we report the diff vs the
previous commit". The iterative re-prompt loop (LLM critique → refined
delta) is left as a future refinement — Sprint K's acceptance criteria
only require the one-shot pipeline.

Flow:
    1. The caller submits a **structured delta** (like the Twin's
       `DeltaApplyRequest` shape). Free-form NL → delta translation is
       handled upstream by the Copilot; here we consume the structured
       form directly so the contract is stable.
    2. The CPO scheduler runs with that delta attached. The delta flows
       into the `ScheduleCommit` and is available on the response.
    3. We compute the delta-view (K.3) between the previous commit and
       the new one.
    4. The response bundles: (a) the CPO KPIs, (b) the commit SHA, (c)
       the diff vs parent. A human then approves via governance (outside
       this module).

Score = kernel_metrics * 0.7 + llm_qual * 0.3 — included in the response
as an informational field. `llm_qual` defaults to 1.0 when the request
doesn't carry a copilot score (deterministic proposals).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.copilot.conversation_store import ConversationStore
from src.plan.cpo.commits import CommitsService
from src.plan.cpo.engine import CPOConfig, CPOv4Engine
from src.plan.cpo.fitness import FitnessConfig
from src.plan.cpo.state import FactoryState
from src.plan.engines.scheduling_adapter import SchedulingMachine
from src.plan.services.routing_resolver import RoutingResolver
from src.shared.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/copilot/poetiq", tags=["Copilot POETIQ"])


# =============================================================================
# Schemas
# =============================================================================

class POETIQDelta(BaseModel):
    """
    Structured delta the copilot (or a human) proposes to apply to the
    current factory state before scheduling.

    Same shape the Twin uses — lets the two modules share vocabulary:
    - `entity_type`: e.g. "standard_time", "capacity_adjustment",
      "quality_improvement", "skills_training", "wip_policy",
      "mold_unavailable".
    - `patch`: free-form dict interpreted by the scheduler-side handler.
      Today the Sprint E-F CPO engine stores the delta as-is on the commit;
      wiring specific patch kinds into the decoder is Sprint I / follow-up.
    """
    entity_type: str = Field(..., min_length=1)
    entity_key: str = Field(default="")
    patch: Dict[str, Any] = Field(default_factory=dict)
    description: str = Field(default="", max_length=500)


class POETIQProposeRequest(BaseModel):
    proposal: str = Field(..., min_length=1, max_length=2000,
                          description="Natural-language summary of the proposal.")
    delta: POETIQDelta
    conversation_id: Optional[UUID] = None
    llm_qual: float = Field(default=1.0, ge=0.0, le=1.0,
                            description="Quality score of the copilot's proposal (0-1).")
    # Scheduler knobs — same defaults as the /schedule endpoint
    horizon_days: int = Field(default=14, ge=1, le=180)
    time_limit_sec: float = Field(default=15.0, ge=1.0, le=300.0)
    population_size: int = Field(default=50, ge=10, le=500)
    generations: int = Field(default=20, ge=1, le=500)
    # Sprint Q.9 Onda 2.5 — opt-in iterative POETIQ loop. When True, runs
    # the Propose→Optimize→Evaluate→Iterate→Qualify loop (max 3 rounds)
    # instead of the one-shot path. Plan v4 §28 — "2-5 iterations with
    # kernel feedback". Off by default so existing callers keep their
    # latency budget.
    iterative: bool = Field(default=False)
    iterative_max_rounds: int = Field(default=3, ge=2, le=5)


class POETIQScoreBreakdown(BaseModel):
    kernel_score: float
    llm_qual: float
    total: float


class POETIQProposeResponse(BaseModel):
    conversation_id: Optional[str] = None
    status: str
    commit_sha256: Optional[str] = None
    parent_sha256: Optional[str] = None
    kpis: Dict[str, Any] = Field(default_factory=dict)
    diff: Optional[Dict[str, Any]] = None  # vs. parent commit (K.3)
    score: POETIQScoreBreakdown
    message: str = ""


# =============================================================================
# Dependencies
# =============================================================================

from src.shared.auth.headers import require_tenant_header, require_user_header

# Sprint Q.12 Onda 0.1: replaced silent zero-UUID/'copilot' defaults.
_tenant_id = require_tenant_header
_user_id = require_user_header


# =============================================================================
# Endpoint
# =============================================================================

@router.post("/propose", response_model=POETIQProposeResponse)
async def propose(
    request: POETIQProposeRequest,
    tenant_id: UUID = Depends(_tenant_id),
    user: str = Depends(_user_id),
    db: AsyncSession = Depends(get_session),
):
    """
    Run a single-shot POETIQ cycle for a copilot-supplied delta.

    Never raises for "no data" — returns a structured `status=no_data`
    instead, so the copilot can present a friendly message.
    """
    horizon_start = datetime.now(timezone.utc)
    horizon_end = horizon_start + timedelta(days=request.horizon_days)

    state = await FactoryState.load(db, tenant_id)
    orders = state.open_orders or []
    if not orders:
        return POETIQProposeResponse(
            conversation_id=str(request.conversation_id) if request.conversation_id else None,
            status="no_data",
            score=POETIQScoreBreakdown(
                kernel_score=0.0,
                llm_qual=request.llm_qual,
                total=0.0,
            ),
            message="Sem ordens abertas — corre uma ingestão primeiro.",
        )

    resolver = RoutingResolver(state)
    operations = resolver.resolve_many(orders, horizon_start=horizon_start)
    if not operations:
        return POETIQProposeResponse(
            conversation_id=str(request.conversation_id) if request.conversation_id else None,
            status="no_routing",
            score=POETIQScoreBreakdown(
                kernel_score=0.0,
                llm_qual=request.llm_qual,
                total=0.0,
            ),
            message="RoutingResolver não devolveu operações para as ordens abertas.",
        )

    # Minimal machine pool — callers wanting richer scheduling should go
    # through /v1/plan/cpo/schedule with explicit machines.
    machines = [SchedulingMachine(machine_id="MANUAL", name="Manual pool")]

    # Sprint Q.9 Onda 1.2 — Camada 2 wire (mirror of plan/api/cpo.py).
    # Adaptive weights merged in; the engine constructor will also copy
    # `state.preference_rules` into the fitness config (Camada 1 wire).
    fitness_config = await FitnessConfig.from_tenant_config(db, tenant_id)

    engine = CPOv4Engine(
        state=state,
        config=CPOConfig(
            population_size=request.population_size,
            generations=request.generations,
            time_limit_sec=request.time_limit_sec,
        ),
        fitness_config=fitness_config,
    )

    # Sprint Q.9 Onda 2.5 — opt-in iterative loop. When `iterative=True`,
    # the proposed delta runs through `run_iterative_poetiq` which can
    # request up to `iterative_max_rounds` re-optimisations (default 3),
    # adjusting horizon/generations between rounds based on the
    # critique. Each iteration shares the same engine instance so the
    # GA's adaptive memory persists across rounds. The one-shot path
    # remains the default to preserve latency for existing callers.
    if request.iterative:
        from src.copilot.poetiq_iterative import run_iterative_poetiq

        # Per-round budget — split the original time_limit so the total
        # stays within request budget. Floor at 5s so the GA always has
        # enough generations to be meaningful.
        per_round_budget = max(5.0, request.time_limit_sec / request.iterative_max_rounds)

        def _optimizer(delta: Dict[str, Any]) -> Dict[str, Any]:
            # Re-tune the engine config for this round based on hints
            # the iterator may attach (extend_horizon_days, extra_
            # generations, set_shift_mode, flip_routing_variant).
            hints = delta.get("iteration_hints") or {}
            extra_gens = int(hints.get("extra_generations", 0))
            extra_days = int(hints.get("extend_horizon_days", 0))
            engine.config.generations = request.generations + extra_gens
            engine.config.time_limit_sec = per_round_budget
            local_end = horizon_end + timedelta(days=extra_days)
            return engine.schedule(operations, machines, horizon_start, local_end)

        loop_result = run_iterative_poetiq(
            proposed_delta=request.delta.model_dump(),
            optimizer=_optimizer,
            max_iterations=request.iterative_max_rounds,
        )
        result = loop_result.schedule or {}
        # Stash loop-level metadata onto the schedule dict so the
        # downstream commit + diff path is identical to the one-shot
        # case. `iterations` and `qualified` show up on the ScheduleCommit
        # via `delta` (already includes the proposed delta) so the
        # operator can inspect.
        result["poetiq_iterations"] = loop_result.iterations
        result["poetiq_qualified"] = loop_result.qualified
        result["poetiq_final_score"] = round(loop_result.final_score, 4)
    else:
        result = engine.schedule(operations, machines, horizon_start, horizon_end)

    # Persist a commit with the delta attached
    delta_dict = request.delta.model_dump()
    commit_sha: Optional[str] = None
    parent_sha: Optional[str] = None
    diff_payload: Optional[Dict[str, Any]] = None
    try:
        commits = CommitsService(db, tenant_id)
        parent = await commits.get_latest()
        parent_sha = parent.commit_sha256 if parent else None

        from src.plan.api.cpo import _extract_mapelites_representatives
        commit = await commits.create_from_schedule(
            schedule_result=result,
            mapelites_representatives=_extract_mapelites_representatives(engine),
            delta=delta_dict,
            author=user,
            message=f"POETIQ: {request.proposal[:120]}",
            trust_index=0.0,
        )
        commit_sha = commit.commit_sha256

        # Diff vs parent (omitted when there's no parent)
        if parent is not None:
            diff_payload = await commits.diff(parent.commit_sha256, commit.commit_sha256)
    except Exception as e:
        logger.warning(f"POETIQ commit/diff failed: {e}", exc_info=True)

    # Score — plan: kernel_metrics * 0.7 + llm_qual * 0.3.
    kernel_score = _kernel_score(result)
    total_score = round(0.7 * kernel_score + 0.3 * request.llm_qual, 4)

    # Archive the turn in ConversationStore (best-effort)
    if request.conversation_id:
        summary = _conversation_summary(result, commit_sha, diff_payload)
        try:
            await ConversationStore.append_turn(
                tenant_id=tenant_id,
                conversation_id=request.conversation_id,
                user_message=request.proposal,
                assistant_message=summary,
            )
        except Exception as e:  # fire-and-forget
            logger.warning(f"POETIQ conversation append failed: {e}")

    kpis = {
        "makespan_hours": result.get("makespan_hours", 0.0),
        "total_tardiness_hours": result.get("total_tardiness_hours", 0.0),
        "num_late_orders": result.get("num_late_orders", 0),
        "setups": result.get("setups", 0),
        "avg_utilization": result.get("avg_utilization", 0.0),
        "safety_net_triggered": bool(result.get("safety_net_triggered", False)),
        "status": result.get("status", "unknown"),
    }

    return POETIQProposeResponse(
        conversation_id=str(request.conversation_id) if request.conversation_id else None,
        status="ok" if commit_sha else "ok_no_commit",
        commit_sha256=commit_sha,
        parent_sha256=parent_sha,
        kpis=kpis,
        diff=diff_payload,
        score=POETIQScoreBreakdown(
            kernel_score=round(kernel_score, 4),
            llm_qual=request.llm_qual,
            total=total_score,
        ),
        message=_conversation_summary(result, commit_sha, diff_payload),
    )


# =============================================================================
# Helpers
# =============================================================================

def _kernel_score(result: Dict[str, Any]) -> float:
    """
    Turn scheduler KPIs into a 0-1 score where **higher is better**.

    Three components, each clamped to [0, 1]:
    - No-tardy bonus (1.0 if `num_late_orders` == 0, else 0.5)
    - Utilization (`avg_utilization` / 100)
    - Safety-net penalty (0.2 if triggered, else 1.0)

    The triangle average keeps the score stable and interpretable.
    """
    no_tardy = 1.0 if int(result.get("num_late_orders", 0)) == 0 else 0.5
    util = max(0.0, min(1.0, float(result.get("avg_utilization", 0.0)) / 100.0))
    safety = 0.2 if bool(result.get("safety_net_triggered", False)) else 1.0
    return (no_tardy + util + safety) / 3.0


def _conversation_summary(
    result: Dict[str, Any],
    commit_sha: Optional[str],
    diff_payload: Optional[Dict[str, Any]],
) -> str:
    parts: List[str] = []
    parts.append(
        f"Plano simulado: makespan={result.get('makespan_hours', 0):.1f}h, "
        f"tardy={result.get('num_late_orders', 0)}, "
        f"util={result.get('avg_utilization', 0):.1f}%."
    )
    if commit_sha:
        parts.append(f"Commit {commit_sha[:12]} guardado.")
    if diff_payload and diff_payload.get("summary"):
        s = diff_payload["summary"]
        parts.append(
            f"Diff vs. plano anterior: +{s.get('added_count', 0)} / "
            f"-{s.get('removed_count', 0)} / ~{s.get('changed_count', 0)}."
        )
    return " ".join(parts)
