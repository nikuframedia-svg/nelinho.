"""
ProdPlan ONE — Schedule-as-Code commits (Sprint K.1)
=====================================================

Each time the CPO scheduler produces a plan, the result is stored as an
immutable commit — very much like a git commit. The chain of commits
(`parent_id` self-FK) gives us:

- Full audit trail: when was this plan produced, by whom, with which
  `trust_index`, what KPIs?
- Diff view (K.3): compare `operations` between two commits.
- Timeline (K.2): expose the MAP-Elites representatives stored alongside
  the commit so a human can pick one to execute.

The SHA-256 is deterministic over the commit's content (kpis + delta +
operations + parent_sha) so duplicate plans are detected and any tamper
with the JSONB breaks the chain.

ORM model: `plan_schedule_commits`. Created by migration 012.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import Index, Integer, String, Text, desc, select
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase

logger = logging.getLogger(__name__)


# =============================================================================
# ORM
# =============================================================================

class ScheduleCommit(TenantBase):
    """
    An immutable, hash-chained snapshot of a CPO schedule run.

    - `parent_id`: self-FK to the previous commit for this tenant (None on
      the very first commit — like git root).
    - `commit_sha256`: SHA-256 of a canonical JSON of {parent_sha256, kpis,
      operations, delta}. Same inputs → same hash → replay is verifiable.
    - `operations`: full list of scheduled ops (serializable dicts). Keeps
      the commit self-contained for diff + timeline without touching
      `production_schedule` rows.
    - `alternatives`: MAP-Elites representatives (for the Timeline endpoint).
    - `delta`: optional structured user-provided modification that led to
      this commit (POETIQ input); NULL for a plain re-plan.
    """

    __tablename__ = "plan_schedule_commits"
    __table_args__ = (
        Index("idx_commits_tenant_created", "tenant_id", "created_at"),
        Index("idx_commits_sha", "commit_sha256"),
    )

    parent_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    commit_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    author: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")

    kpis: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    operations: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    delta: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    alternatives: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    cpo_meta: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    trust_index: Mapped[float] = mapped_column(nullable=False, default=0.0)
    operations_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


# =============================================================================
# Hash computation
# =============================================================================

def compute_commit_hash(
    parent_sha256: Optional[str],
    kpis: Dict[str, Any],
    operations: List[Dict[str, Any]],
    delta: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Deterministic SHA-256 of (parent, kpis, operations, delta).

    Canonical JSON is produced via `sort_keys=True` + stable UTF-8 encode.
    """
    payload = {
        "parent_sha256": parent_sha256,
        "kpis": kpis,
        "operations": operations,
        "delta": delta or {},
    }
    canonical = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# =============================================================================
# Service
# =============================================================================

class CommitsService:
    """CRUD + creation hook for ScheduleCommit rows."""

    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id

    # -------------------- Create ------------------------------------- #

    async def create_from_schedule(
        self,
        *,
        schedule_result: Dict[str, Any],
        mapelites_representatives: Optional[List[Dict[str, Any]]] = None,
        delta: Optional[Dict[str, Any]] = None,
        author: str = "system",
        message: str = "",
        trust_index: float = 0.0,
    ) -> ScheduleCommit:
        """Persist a commit from the output of `CPOv4Engine.schedule()`."""
        operations = list(schedule_result.get("operations") or [])
        kpis = _extract_kpis(schedule_result)
        cpo_meta = schedule_result.get("cpo_meta") or {}

        parent = await self.get_latest()
        parent_sha = parent.commit_sha256 if parent else None
        parent_id = parent.id if parent else None

        sha = compute_commit_hash(
            parent_sha256=parent_sha,
            kpis=kpis,
            operations=operations,
            delta=delta,
        )

        commit = ScheduleCommit(
            id=uuid4(),
            tenant_id=self.tenant_id,
            parent_id=parent_id,
            commit_sha256=sha,
            author=author,
            message=message or _auto_message(delta, cpo_meta),
            kpis=kpis,
            operations=operations,
            delta=delta or {},
            alternatives=list(mapelites_representatives or []),
            cpo_meta=cpo_meta,
            trust_index=float(trust_index),
            operations_count=len(operations),
        )
        self.session.add(commit)
        await self.session.flush()
        logger.info(
            f"Created schedule commit {sha[:12]} parent={str(parent_sha or '-')[:12]} "
            f"ops={len(operations)} tenant={self.tenant_id}"
        )
        return commit

    # -------------------- Retrieve ----------------------------------- #

    async def get_by_sha(self, sha: str) -> Optional[ScheduleCommit]:
        stmt = select(ScheduleCommit).where(
            (ScheduleCommit.tenant_id == self.tenant_id)
            & (ScheduleCommit.commit_sha256 == sha)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_sha_prefix(self, prefix: str) -> Optional[ScheduleCommit]:
        """Support short-hash lookups like `abc1234` (>=7 chars)."""
        if len(prefix) < 7:
            return None
        stmt = select(ScheduleCommit).where(
            (ScheduleCommit.tenant_id == self.tenant_id)
            & (ScheduleCommit.commit_sha256.like(f"{prefix}%"))
        ).limit(2)
        rows = list((await self.session.execute(stmt)).scalars().all())
        return rows[0] if len(rows) == 1 else None

    async def get_latest(self) -> Optional[ScheduleCommit]:
        stmt = (
            select(ScheduleCommit)
            .where(ScheduleCommit.tenant_id == self.tenant_id)
            .order_by(desc(ScheduleCommit.created_at))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_commits(self, limit: int = 50) -> List[ScheduleCommit]:
        stmt = (
            select(ScheduleCommit)
            .where(ScheduleCommit.tenant_id == self.tenant_id)
            .order_by(desc(ScheduleCommit.created_at))
            .limit(max(1, min(limit, 500)))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -------------------- Diff --------------------------------------- #

    async def diff(
        self,
        from_sha: str,
        to_sha: str,
    ) -> Dict[str, Any]:
        """Compare the operations of two commits. Returns the delta dict."""
        a = await self._resolve_commit(from_sha)
        b = await self._resolve_commit(to_sha)
        if a is None or b is None:
            raise ValueError(
                f"commit_not_found: from={from_sha} a={a is not None} "
                f"to={to_sha} b={b is not None}"
            )
        return compute_operations_diff(a, b)

    async def _resolve_commit(self, sha: str) -> Optional[ScheduleCommit]:
        return await self.get_by_sha(sha) or await self.get_by_sha_prefix(sha)

    # -------------------- Serialisation ----------------------------- #

    @staticmethod
    def to_dict(commit: ScheduleCommit, *, include_operations: bool = False) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "id": str(commit.id),
            "tenant_id": str(commit.tenant_id),
            "parent_id": str(commit.parent_id) if commit.parent_id else None,
            "commit_sha256": commit.commit_sha256,
            "short_sha": commit.commit_sha256[:12],
            "author": commit.author,
            "message": commit.message,
            "kpis": commit.kpis or {},
            "delta": commit.delta or {},
            "alternatives": commit.alternatives or [],
            "cpo_meta": commit.cpo_meta or {},
            "trust_index": commit.trust_index,
            "operations_count": commit.operations_count,
            "created_at": commit.created_at.isoformat() if commit.created_at else None,
        }
        if include_operations:
            out["operations"] = commit.operations or []
        return out


# =============================================================================
# Diff computation (self-contained, unit-tested)
# =============================================================================

def compute_operations_diff(
    a: ScheduleCommit,
    b: ScheduleCommit,
) -> Dict[str, Any]:
    """
    Compare two commits' `operations` lists, indexed by `operation_id`.

    Output:
        {
          "from_sha": ..., "to_sha": ...,
          "added":    [op],          # in b not in a
          "removed":  [op],          # in a not in b
          "changed":  [{op_id, field, before, after}],
          "kpi_deltas": {kpi: (from, to, delta)},
        }
    """
    by_id_a = {op.get("operation_id"): op for op in (a.operations or [])}
    by_id_b = {op.get("operation_id"): op for op in (b.operations or [])}

    added_ids = set(by_id_b) - set(by_id_a)
    removed_ids = set(by_id_a) - set(by_id_b)

    changed: List[Dict[str, Any]] = []
    for op_id in sorted(set(by_id_a) & set(by_id_b)):
        if op_id is None:
            continue
        op_a, op_b = by_id_a[op_id], by_id_b[op_id]
        for field in ("start_time", "end_time", "machine_id", "mold_id", "workers"):
            if op_a.get(field) != op_b.get(field):
                changed.append({
                    "operation_id": op_id,
                    "field": field,
                    "before": op_a.get(field),
                    "after": op_b.get(field),
                })

    kpi_deltas: Dict[str, Any] = {}
    for key in set(a.kpis or {}).union(b.kpis or {}):
        va = (a.kpis or {}).get(key)
        vb = (b.kpis or {}).get(key)
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            kpi_deltas[key] = {"from": va, "to": vb, "delta": round(vb - va, 4)}
        elif va != vb:
            kpi_deltas[key] = {"from": va, "to": vb, "delta": None}

    return {
        "from_sha": a.commit_sha256,
        "to_sha": b.commit_sha256,
        "added": [by_id_b[op_id] for op_id in sorted(added_ids)],
        "removed": [by_id_a[op_id] for op_id in sorted(removed_ids)],
        "changed": changed,
        "kpi_deltas": kpi_deltas,
        "summary": {
            "added_count": len(added_ids),
            "removed_count": len(removed_ids),
            "changed_count": len(changed),
        },
    }


# =============================================================================
# Helpers
# =============================================================================

def _extract_kpis(schedule_result: Dict[str, Any]) -> Dict[str, Any]:
    """Pull a concise KPI subset from the scheduler output for the commit."""
    return {
        "makespan_hours": schedule_result.get("makespan_hours", 0.0),
        "total_tardiness_hours": schedule_result.get("total_tardiness_hours", 0.0),
        "num_late_orders": schedule_result.get("num_late_orders", 0),
        "setups": schedule_result.get("setups", 0),
        "avg_utilization": schedule_result.get("avg_utilization", 0.0),
        "solve_time_sec": schedule_result.get("solve_time_sec", 0.0),
        "status": schedule_result.get("status", "unknown"),
        "safety_net_triggered": bool(schedule_result.get("safety_net_triggered", False)),
    }


def _auto_message(delta: Optional[Dict[str, Any]], cpo_meta: Dict[str, Any]) -> str:
    if delta:
        entity = delta.get("entity_type") or "custom"
        return f"Scheduled with {entity} delta"
    gen = cpo_meta.get("generations_run")
    if gen:
        return f"Scheduled ({gen} generations, best_fitness={cpo_meta.get('best_fitness')})"
    return "Scheduled"
