"""Q.67.6.B2 — sub-router para `/commits*` (Sprint K + Sprint B/M + Q.5).

Endpoints:
* GET  /commits                        — list commits
* GET  /commits/{sha}                  — commit detail
* GET  /commits/{sha}/orders           — plano optimizado consumível (Q.54.D)
* GET  /commits/{from}/diff/{to}       — delta view (Sprint K.3)
* GET  /commits/{sha}/alternatives     — enriched MAP-Elites alts (Sprint M.7 WG10)
* POST /commits/{sha}/decide           — record operator decision (Sprint B CO1)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.api._cpo_common import (
    _build_narrative,
    _format_delta_pct,
    _relative_delta,
    _resolve_commit_or_404,
    _tenant_id,
)
from src.plan.cpo.commits import CommitsService
from src.shared.database import get_session

router = APIRouter()


# =============================================================================
# Response schemas (list + detail)
# =============================================================================

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
    # Q.133.A.2 — estado do plano (DRAFT|LIVE) + sinal de degradação, para o
    # grid rotular honestamente um plano não-aprovado/degradado.
    status: str = "DRAFT"
    safety_net_triggered: bool = False
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


# =============================================================================
# GET /commits + GET /commits/{sha}  (Sprint K.1)
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
# GET /commits/{sha}/orders (Q.54.D — plano optimizado consumível)
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
# GET /commits/{from}/diff/{to}  (Sprint K.3 — Delta view)
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
# GET /commits/{sha}/alternatives  (Sprint M.7 — WG10)
# =============================================================================
#
# Enriches the raw MAP-Elites alternatives stored at commit time with:
#   * deltas vs the primary commit's KPIs (human-readable percentages)
#   * a deterministic narrative explaining the trade-off
#   * optional `n` cap for smaller Timeline cards
#
# The narrative is template-based (not LLM) so the endpoint stays fast + cheap;
# Sprint S.3 will upgrade this to Instructor+Pydantic structured output.


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
# POST /commits/{sha}/decide  (Sprint B CO1 + Q.5 + R.2)
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
