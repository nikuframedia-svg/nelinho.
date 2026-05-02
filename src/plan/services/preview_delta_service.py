"""
ProdPlan ONE - Schedule Preview-Delta (Sprint Q.4 / PL01-PL24)
==============================================================

Cheap "what-if" calculator the drag-and-drop UI calls when the operator
moves a boat between phase columns (Layer 1) or assigns a worker to a
boat (Layer 2). Sub-second by design — does NOT run GA/CP-SAT.

Approach::

    latest_commit = get_latest()
    schedule = build_schedule_dict(latest_commit)         # KPIs + operations
    schedule_after = apply_in_memory_mutation(schedule, change)
    fitness_delta = compute_fitness(schedule_after) - compute_fitness(schedule)
    conflicts    = detect_hard_conflicts(schedule_after, change)
    warnings     = detect_soft_warnings(schedule_after, change)

The conflicts are the load-bearing signal — fitness deltas in v2 are
small (<0.05) for single-op moves so the operator should anchor on
*"what breaks"* not *"how much better"*. Each conflict/warning carries
a string `message` that the UI renders verbatim under the suggestion.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.cpo.commits import CommitsService, ScheduleCommit, compute_commit_hash
from src.plan.cpo.fitness import FitnessConfig, compute_fitness
from src.plan.cpo.state import normalize_phase_code

logger = logging.getLogger(__name__)


# Phases where running with a single worker triggers a preview warning
# (88.5% historical pair). Mirrors `FactoryState.PAIR_PREFERRED_PHASES`
# after Sprint Q.8 — solo runs are allowed by the decoder but worth
# flagging in the operator preview.
PAIR_PREFERRED_PHASES: tuple[str, ...] = ("LAMINAGEM",)
# Backwards-compat alias so existing tests keep importing the old name.
PAIR_REQUIRED_PHASES: tuple[str, ...] = PAIR_PREFERRED_PHASES


@dataclass
class PreviewMutation:
    """The change the operator wants to preview."""

    operation_id: str
    new_phase_id: Optional[str] = None
    new_worker_ids: Optional[list[str]] = None


@dataclass
class PreviewIssue:
    """A conflict or warning surfaced by the delta calculator."""

    type: str
    severity: str  # "conflict" (hard) or "warning" (soft)
    message: str
    related_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "severity": self.severity,
            "message": self.message,
            "related_ids": self.related_ids,
        }


@dataclass
class PreviewResult:
    """Response shape consumed by the SchedulingPage drop handler."""

    operation_id: str
    base_commit_sha: Optional[str]
    fitness_before: float
    fitness_after: float
    fitness_delta: float            # negative is improvement
    throughput_eur_before: float
    throughput_eur_after: float
    throughput_eur_delta: float
    conflicts: list[PreviewIssue]
    warnings: list[PreviewIssue]
    pair_rule_violation: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "base_commit_sha": self.base_commit_sha,
            "fitness_before": round(self.fitness_before, 4),
            "fitness_after": round(self.fitness_after, 4),
            "fitness_delta": round(self.fitness_delta, 4),
            "throughput_eur_before": round(self.throughput_eur_before, 2),
            "throughput_eur_after": round(self.throughput_eur_after, 2),
            "throughput_eur_delta": round(self.throughput_eur_delta, 2),
            "conflicts": [c.to_dict() for c in self.conflicts],
            "warnings": [w.to_dict() for w in self.warnings],
            "pair_rule_violation": self.pair_rule_violation,
        }


class PreviewDeltaService:
    """In-memory schedule mutation + fitness/conflict scoring."""

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    # ─────────────────────────────────────────────────────────────────────
    # Public surface
    # ─────────────────────────────────────────────────────────────────────

    async def preview(self, mutation: PreviewMutation) -> PreviewResult:
        commit, schedule_before = await self._load_base_schedule()

        if not _find_op(schedule_before, mutation.operation_id):
            raise ValueError(
                f"operation_id {mutation.operation_id} not in latest commit"
            )

        schedule_after = copy.deepcopy(schedule_before)
        _apply_mutation(schedule_after, mutation)

        cfg = FitnessConfig(use_v2_weights=True)
        fitness_before = compute_fitness(schedule_before, cfg)
        fitness_after = compute_fitness(schedule_after, cfg)

        thr_before = float(schedule_before.get("throughput_eur_day", 0) or 0)
        thr_after = float(schedule_after.get("throughput_eur_day", 0) or 0)

        conflicts = _detect_conflicts(schedule_after, mutation)
        warnings = _detect_warnings(schedule_after, mutation)
        pair_violation = any(
            i.type == "pair_rule" for i in (conflicts + warnings)
        )

        return PreviewResult(
            operation_id=mutation.operation_id,
            base_commit_sha=commit.commit_sha256 if commit else None,
            fitness_before=fitness_before,
            fitness_after=fitness_after,
            fitness_delta=fitness_after - fitness_before,
            throughput_eur_before=thr_before,
            throughput_eur_after=thr_after,
            throughput_eur_delta=thr_after - thr_before,
            conflicts=conflicts,
            warnings=warnings,
            pair_rule_violation=pair_violation,
        )

    async def apply(
        self,
        mutation: PreviewMutation,
        *,
        author: str,
        reason: str,
    ) -> ScheduleCommit:
        """Persist the mutation as a new ScheduleCommit (child of the latest).

        The new commit's `delta` field carries the structured mutation +
        the operator's reason, so Camada 1 can mine the rejected/accepted
        outcome later.
        """
        commit, schedule_before = await self._load_base_schedule()
        if commit is None:
            raise ValueError("no base commit; cannot apply move")
        if not _find_op(schedule_before, mutation.operation_id):
            raise ValueError(
                f"operation_id {mutation.operation_id} not in latest commit"
            )

        schedule_after = copy.deepcopy(schedule_before)
        _apply_mutation(schedule_after, mutation)

        # Recompute aggregate KPIs cheaply — we only know what we changed.
        new_kpis = dict(commit.kpis or {})
        new_kpis["throughput_eur_day"] = schedule_after.get(
            "throughput_eur_day", new_kpis.get("throughput_eur_day", 0),
        )

        ops_after = list(schedule_after.get("operations") or [])
        delta = {
            "kind": "preview_apply",
            "operation_id": mutation.operation_id,
            "new_phase_id": mutation.new_phase_id,
            "new_worker_ids": mutation.new_worker_ids,
            "reason": reason,
            "applied_at": datetime.now(timezone.utc).isoformat(),
        }

        new_sha = compute_commit_hash(
            parent_sha256=commit.commit_sha256,
            kpis=new_kpis,
            operations=ops_after,
            delta=delta,
        )

        new_commit = ScheduleCommit(
            tenant_id=self.tenant_id,
            parent_id=commit.id,
            commit_sha256=new_sha,
            author=author,
            message=f"preview-apply by {author}: {reason[:100]}",
            kpis=new_kpis,
            operations=ops_after,
            delta=delta,
            alternatives=[],
            cpo_meta={"source": "preview_delta_service"},
            trust_index=float(commit.trust_index or 0.0),
            operations_count=len(ops_after),
        )
        self.session.add(new_commit)
        await self.session.flush()
        await self.session.commit()
        logger.info(
            "preview-apply commit %s parent=%s op=%s",
            new_sha[:12], commit.commit_sha256[:12], mutation.operation_id,
        )
        return new_commit

    # ─────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────

    async def _load_base_schedule(
        self,
    ) -> tuple[Optional[ScheduleCommit], dict[str, Any]]:
        svc = CommitsService(self.session, self.tenant_id)
        commit = await svc.get_latest()
        if commit is None:
            return None, {"operations": [], "makespan_hours": 0,
                           "total_tardiness_hours": 0, "setups": 0,
                           "throughput_eur_day": 0, "quality_risk": 0}
        schedule = dict(commit.kpis or {})
        schedule["operations"] = list(commit.operations or [])
        return commit, schedule


# ─────────────────────────────────────────────────────────────────────────
# Pure helpers (free functions for unit testing)
# ─────────────────────────────────────────────────────────────────────────

def _find_op(schedule: dict[str, Any], op_id: str) -> Optional[dict[str, Any]]:
    for op in schedule.get("operations") or []:
        if str(op.get("id") or op.get("operation_id") or "") == op_id:
            return op
    return None


def _apply_mutation(schedule: dict[str, Any], mutation: PreviewMutation) -> None:
    """In-place mutation of the schedule dict's operations list."""
    op = _find_op(schedule, mutation.operation_id)
    if op is None:
        return
    if mutation.new_phase_id is not None:
        op["phase_id"] = mutation.new_phase_id
    if mutation.new_worker_ids is not None:
        op["workers"] = list(mutation.new_worker_ids)


def _detect_conflicts(
    schedule: dict[str, Any],
    mutation: PreviewMutation,
) -> list[PreviewIssue]:
    """Hard issues that should block the move (worker double-booking, etc.)."""
    out: list[PreviewIssue] = []
    op = _find_op(schedule, mutation.operation_id)
    if op is None:
        return out

    # Worker double-booking: any other op overlapping this op's time window
    # that shares a worker_id.
    if mutation.new_worker_ids:
        start = _ts(op.get("start"))
        end = _ts(op.get("end"))
        if start is not None and end is not None:
            for other in schedule.get("operations") or []:
                if other is op:
                    continue
                other_workers = set(other.get("workers") or [])
                clash = other_workers.intersection(mutation.new_worker_ids)
                if not clash:
                    continue
                o_start = _ts(other.get("start"))
                o_end = _ts(other.get("end"))
                if o_start is None or o_end is None:
                    continue
                if start < o_end and end > o_start:
                    out.append(
                        PreviewIssue(
                            type="worker_double_booking",
                            severity="conflict",
                            message=(
                                f"Worker(s) {sorted(clash)} já estão atribuídos "
                                f"a outra operação que sobrepõe esta janela."
                            ),
                            related_ids=[
                                str(other.get("id") or other.get("operation_id") or "")
                            ],
                        )
                    )
    return out


def _detect_warnings(
    schedule: dict[str, Any],
    mutation: PreviewMutation,
) -> list[PreviewIssue]:
    """Soft issues — operator can override after seeing the consequence."""
    out: list[PreviewIssue] = []
    op = _find_op(schedule, mutation.operation_id)
    if op is None:
        return out

    phase = normalize_phase_code(
        op.get("phase_id") or op.get("phase_name") or ""
    )

    # Pair preference (Plan v4 §3.4 + Sprint Q.8): 88.5% of Laminagem ops
    # historically use 2 workers; solo is allowed but flagged.
    if any(p in phase for p in PAIR_PREFERRED_PHASES):
        worker_count = len(op.get("workers") or [])
        if worker_count < 2:
            out.append(
                PreviewIssue(
                    type="pair_rule",
                    severity="warning",
                    message=(
                        f"{phase} costuma correr com 2 workers (88.5% histórico); "
                        f"actual={worker_count}."
                    ),
                )
            )

    # Quality-risk override: if op has a per-op risk score above the v2.0
    # hard threshold (0.40), surface it.
    risk = float(op.get("quality_risk", 0) or 0)
    if risk >= 0.40:
        out.append(
            PreviewIssue(
                type="quality_risk_high",
                severity="warning",
                message=(
                    f"P(erro)={risk:.2f} acima do threshold v2.0 (0.40). "
                    f"Considera trocar para um worker com score mais alto."
                ),
            )
        )

    return out


def _ts(value: Any) -> Optional[datetime]:
    """Parse an ISO string or pass through a datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None
