"""Q.66.D.3 — query + read-side sub-service.

Read-side helpers + payload-edit path. Extracted from ``service.py``
during Q.66.D.3 Fase 7. Owns:

* ``get_decision`` / ``list_decisions``
* ``get_timeline`` (Sprint M.1 — anti-fatigue grouped pending list)
* ``modify_payload`` (Sprint M.4) + ``_mark_chain_invalidated``
* ``get_audit_timeline`` (Sprint M.6 — cross-decision events)
* ``get_audit_pack`` + hash-chain verification (read-side):
  ``_verify_hash_chain`` + ``_fetch_decision_by_audit_hash``
* Shared helpers ``_run_to_dict`` (re-exported through the façade) and
  ``_get_decision_run`` (also used by other sub-services).

The hash-chain helpers here are READ-side: they walk back to verify.
The WRITE-side (taking the per-tenant advisory lock + computing the
next hash) lives in ``decision_proposer``.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import DecisionRun, DecisionStatus

logger = logging.getLogger(__name__)


# Risk severity ordering — duplicated from approver so the query module
# can sort timeline buckets without a circular import.
RISK_ORDER: Dict[str, int] = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _aware(dt: Optional[datetime]) -> datetime:
    """Coerce naive datetimes to UTC so subtraction works across both kinds."""
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _isoformat(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _impact_magnitude(expected_impact: Optional[Dict[str, Any]]) -> float:
    """Reduce an `expected_impact` dict to a single float so `min_impact`
    can filter against it. Picks the first numeric value (or the
    `magnitude` / `delta` / `abs_euro` key when present); returns 0.0
    when nothing is numeric."""
    if not expected_impact:
        return 0.0
    for key in ("magnitude", "delta", "abs_euro", "impact", "score"):
        if key in expected_impact and isinstance(expected_impact[key], (int, float)):
            return abs(float(expected_impact[key]))
    for value in expected_impact.values():
        if isinstance(value, (int, float)):
            return abs(float(value))
    return 0.0


def _group_sort_key(key: str, group_by: str) -> tuple:
    """Deterministic ordering of group buckets. Risk levels sort
    high→low so the worst fires float to the top."""
    if group_by == "risk_level":
        return (-RISK_ORDER.get(key, -1),)
    return (key,)


class DecisionQuery:
    """Read-side queries + payload edits + hash-chain verification."""

    # Hash-chain verification walks back this many decisions before
    # giving up. 100 covers the audit window most reviewers care about
    # (last week of decisions on a busy tenant) without making the
    # audit-pack endpoint pathologically slow on first run.
    _HASH_CHAIN_VERIFY_DEPTH: int = 100

    def __init__(self, db: AsyncSession, tenant_id: UUID) -> None:
        self.db = db
        self.tenant_id = tenant_id

    # ------------------------------------------------------------------
    # Simple reads
    # ------------------------------------------------------------------

    async def get_decision(self, decision_id: str) -> Optional[Dict[str, Any]]:
        """Get a decision by ID."""
        run = await self._get_decision_run(decision_id)
        return self._run_to_dict(run) if run else None

    async def list_decisions(
        self,
        status: Optional[str] = None,
        decision_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List decisions with optional filters."""
        stmt = select(DecisionRun).where(DecisionRun.tenant_id == self.tenant_id)

        if status:
            stmt = stmt.where(DecisionRun.status == status)
        if decision_type:
            stmt = stmt.where(DecisionRun.decision_type == decision_type)

        stmt = stmt.order_by(DecisionRun.proposed_at.desc()).offset(offset).limit(limit)

        result = await self.db.execute(stmt)
        runs = result.scalars().all()
        return [self._run_to_dict(r) for r in runs]

    # ------------------------------------------------------------------
    # Sprint M.1 — Timeline (grouped by criticality / risk / type / status)
    # ------------------------------------------------------------------

    async def get_timeline(
        self,
        *,
        group_by: str = "criticality",
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        actor_id: Optional[str] = None,
        autonomy_level: Optional[str] = None,
        min_impact: Optional[float] = None,
        hide_low_risk: bool = False,
        max_per_user_shown: Optional[int] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """Return pending decisions bucketed by the requested dimension.

        `group_by` ∈ {"criticality", "risk_level", "decision_type", "status"}.
        "criticality" is an alias for risk_level (kept for Blueprint wording).

        Anti-fatigue knobs (`min_impact`, `hide_low_risk`,
        `max_per_user_shown`) thin the returned list without mutating
        the backing data — the aggregated KPIs are computed over the
        unfiltered population so the admin can see what's *hidden*.
        """
        group_by = "risk_level" if group_by == "criticality" else group_by
        if group_by not in {"risk_level", "decision_type", "status"}:
            raise ValueError(
                f"Unsupported group_by '{group_by}'. "
                "Allowed: criticality|risk_level|decision_type|status"
            )

        # Select ALL decisions in the window that are still waiting for
        # a human (PROPOSED + PENDING_APPROVAL). APPROVED-but-not-yet-
        # EXECUTED decisions aren't user-blocking so we exclude them.
        conditions = [
            DecisionRun.tenant_id == self.tenant_id,
            DecisionRun.status.in_(
                [
                    DecisionStatus.PROPOSED.value,
                    DecisionStatus.PENDING_APPROVAL.value,
                ]
            ),
        ]
        if since:
            conditions.append(DecisionRun.proposed_at >= since)
        if until:
            conditions.append(DecisionRun.proposed_at <= until)
        if actor_id:
            conditions.append(DecisionRun.proposed_by == actor_id)
        if autonomy_level:
            conditions.append(DecisionRun.autonomy_level == autonomy_level)

        stmt = (
            select(DecisionRun)
            .where(and_(*conditions))
            .order_by(DecisionRun.proposed_at.desc())
        )
        all_rows = list((await self.db.execute(stmt)).scalars().all())

        # Aggregated KPIs — computed BEFORE filters so the UI can show
        # what's being hidden.
        now = datetime.now(timezone.utc)
        overdue_threshold_h = 24.0  # configurable later (Sprint L)
        waiting_hours: List[float] = []
        overdue = 0
        for r in all_rows:
            waited_h = (now - _aware(r.proposed_at)).total_seconds() / 3600.0
            waiting_hours.append(max(0.0, waited_h))
            if waited_h >= overdue_threshold_h:
                overdue += 1
        avg_waiting_h = (
            sum(waiting_hours) / len(waiting_hours) if waiting_hours else 0.0
        )

        # Anti-fatigue filters.
        filtered = all_rows
        if hide_low_risk:
            filtered = [r for r in filtered if (r.risk_level or "").lower() != "low"]
        if min_impact is not None:
            filtered = [
                r for r in filtered
                if _impact_magnitude(r.expected_impact) >= float(min_impact)
            ]

        # Bucketisation.
        buckets: Dict[str, List[DecisionRun]] = {}
        for r in filtered:
            key = self._bucket_key(r, group_by)
            buckets.setdefault(key, []).append(r)

        # Per-user cap inside each bucket: keep N most recent per proposer.
        if max_per_user_shown is not None:
            capped: Dict[str, List[DecisionRun]] = {}
            for k, rows in buckets.items():
                seen_per_user: Dict[str, int] = {}
                out: List[DecisionRun] = []
                for r in rows:
                    count = seen_per_user.get(r.proposed_by, 0)
                    if count < max_per_user_shown:
                        seen_per_user[r.proposed_by] = count + 1
                        out.append(r)
                capped[k] = out
            buckets = capped

        # Pagination: we flatten buckets in group-key order for cursoring.
        offset = max(0, (page - 1) * page_size)
        flat: List[DecisionRun] = []
        for rows in buckets.values():
            flat.extend(rows)
        page_rows = flat[offset: offset + page_size]

        # Re-group the paged rows so the response shape is stable.
        groups_out: Dict[str, List[DecisionRun]] = {}
        for r in page_rows:
            k = self._bucket_key(r, group_by)
            groups_out.setdefault(k, []).append(r)

        return {
            "group_by": group_by,
            "groups": [
                {
                    "key": k,
                    "count": len(rows),
                    "decisions": [self._run_to_dict(r) for r in rows],
                }
                for k, rows in sorted(
                    groups_out.items(),
                    key=lambda kv: _group_sort_key(kv[0], group_by),
                )
            ],
            "total": len(all_rows),
            "shown": len(flat),
            "aggregated_kpis": {
                "pending_count": len(all_rows),
                "overdue_count": overdue,
                "avg_waiting_h": round(avg_waiting_h, 2),
            },
        }

    @staticmethod
    def _bucket_key(run: DecisionRun, group_by: str) -> str:
        if group_by == "risk_level":
            return (run.risk_level or "medium").lower()
        if group_by == "decision_type":
            return run.decision_type
        if group_by == "status":
            return run.status
        return "unknown"

    # ------------------------------------------------------------------
    # Sprint M.4 — Modify payload before approval
    # ------------------------------------------------------------------

    async def modify_payload(
        self,
        *,
        decision_id: str,
        patch: Dict[str, Any],
        modified_by: str,
        reason: str,
    ) -> Dict[str, Any]:
        """Replace whitelisted fields of `action_data` before approval.

        Only decisions in PROPOSED/PENDING_APPROVAL can be modified.
        Previous payload is preserved under
        ``action_data.__modifications__`` with
        ``{modified_by, modified_at, reason, before_hash, after_hash}``
        so the audit trail survives.

        The full set of allowed fields per `decision_type` is currently
        unrestricted — a Sprint R hook will tighten it per type (e.g.
        schedule decisions let edd_gap/buffer_pct through but never
        `operations`).
        """
        if len(reason or "") < 10:
            raise ValueError("Modification reason required (min 10 characters)")

        decision_run = await self._get_decision_run(decision_id)
        if not decision_run:
            raise ValueError(f"Decision {decision_id} not found")

        if decision_run.status not in (
            DecisionStatus.PROPOSED.value,
            DecisionStatus.PENDING_APPROVAL.value,
        ):
            raise ValueError(
                f"Decision {decision_id} is not editable "
                f"(status: {decision_run.status})"
            )

        before = dict(decision_run.action_data or {})
        before_hash = hashlib.sha256(
            json.dumps(before, sort_keys=True, default=str).encode()
        ).hexdigest()

        # Shallow merge; callers pass the fields they want to override.
        new_data = dict(before)
        new_data.update(patch or {})
        after_hash = hashlib.sha256(
            json.dumps(
                {k: v for k, v in new_data.items() if k != "__modifications__"},
                sort_keys=True, default=str,
            ).encode()
        ).hexdigest()

        history = list(new_data.get("__modifications__") or [])
        history.append({
            "modified_by": modified_by,
            "modified_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "before_hash": before_hash,
            "after_hash": after_hash,
        })
        new_data["__modifications__"] = history

        decision_run.action_data = new_data
        decision_run.input_snapshot_hash = after_hash
        old_audit_hash = decision_run.audit_hash
        # Re-hash the audit chain so tamper detection stays consistent.
        decision_run.audit_hash = DecisionRun.calculate_audit_hash(
            decision_id=decision_run.id,
            policy_version=decision_run.policy_version,
            input_hash=after_hash,
            outcome_hash=decision_run.outcome_hash,
            prev_hash=decision_run.prev_hash,
        )

        # Sprint Q.12 Onda 1.5 — every later decision that pinned its
        # ``prev_hash`` to ``old_audit_hash`` now references a row
        # whose hash we just changed. Flag them so audit tooling can
        # show the break instead of pretending the chain is intact.
        await self._mark_chain_invalidated(decision_run.id, old_audit_hash)

        await self.db.flush()
        return self._run_to_dict(decision_run)

    async def _mark_chain_invalidated(
        self,
        modifier_id: UUID,
        old_audit_hash: str,
    ) -> None:
        """Tag descendants whose ``prev_hash`` we just orphaned.

        Walks ``DecisionRun`` rows for the current tenant where
        ``prev_hash == old_audit_hash`` and stamps the chain-invalidation
        columns. The ``modifier_id`` is recorded so a forensic timeline
        can reconstruct *which* edit broke each link.

        No-op when no descendants exist (e.g. modifying the most recent
        decision before any further proposals landed).
        """
        from sqlalchemy import update

        stmt = (
            update(DecisionRun)
            .where(
                and_(
                    DecisionRun.tenant_id == self.tenant_id,
                    DecisionRun.prev_hash == old_audit_hash,
                    DecisionRun.id != modifier_id,
                )
            )
            .values(
                chain_invalidated=True,
                chain_invalidated_at=datetime.now(timezone.utc),
                chain_invalidated_by_modify_id=modifier_id,
            )
        )
        await self.db.execute(stmt)

    # ------------------------------------------------------------------
    # Sprint M.6 — Cross-decision audit timeline
    # ------------------------------------------------------------------

    async def get_audit_timeline(
        self,
        *,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        actor: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """Chronological event stream across all decisions.

        Events: `proposed`, `approval_<action>`, `executed`, `rolled_back`.
        Unlike `get_audit_pack(decision_id)` which returns a
        single-decision timeline, this is the cross-cutting view a
        reviewer uses to ask "what happened to us in the last hour?".
        """
        stmt = select(DecisionRun).where(DecisionRun.tenant_id == self.tenant_id)
        if since:
            stmt = stmt.where(DecisionRun.proposed_at >= since)
        if until:
            stmt = stmt.where(DecisionRun.proposed_at <= until)
        stmt = stmt.order_by(DecisionRun.proposed_at.desc()).limit(max(10, limit))
        rows = list((await self.db.execute(stmt)).scalars().all())

        events: List[Dict[str, Any]] = []
        for r in rows:
            if (not actor) or r.proposed_by == actor:
                events.append({
                    "event": "proposed",
                    "at": _isoformat(r.proposed_at),
                    "by": r.proposed_by,
                    "decision_id": str(r.id),
                    "decision_type": r.decision_type,
                    "risk_level": r.risk_level,
                })
            for a in (r.approvals or []):
                if (not actor) or a.approved_by == actor:
                    events.append({
                        "event": f"approval_{a.action}",
                        "at": _isoformat(a.approved_at),
                        "by": a.approved_by,
                        "decision_id": str(r.id),
                        "reason": a.reason,
                    })
            if r.executed_at and ((not actor) or r.executed_by == actor):
                events.append({
                    "event": "executed",
                    "at": _isoformat(r.executed_at),
                    "by": r.executed_by,
                    "decision_id": str(r.id),
                })
            if r.rolled_back_at and ((not actor) or r.rolled_back_by == actor):
                events.append({
                    "event": "rolled_back",
                    "at": _isoformat(r.rolled_back_at),
                    "by": r.rolled_back_by,
                    "decision_id": str(r.id),
                    "reason": r.rollback_reason,
                })

        # Sort globally newest-first.
        events.sort(key=lambda e: e.get("at") or "", reverse=True)
        return events[:limit]

    # ------------------------------------------------------------------
    # Audit pack + hash chain verification (read side)
    # ------------------------------------------------------------------

    async def get_audit_pack(self, decision_id: str) -> Dict[str, Any]:
        """Get complete audit pack for compliance.

        Sprint Q.12 Onda 1.2 — ``hash_chain_valid`` used to be a
        hardcoded ``True``. Now we walk back through the chain
        recomputing each link's audit hash from its inputs. If any
        ``calculate_audit_hash`` recomputation disagrees with the
        stored value the chain is reported as broken with the offending
        decision id surfaced for forensics.
        """
        run = await self._get_decision_run(decision_id)
        if not run:
            raise ValueError(f"Decision {decision_id} not found")

        d = self._run_to_dict(run)
        timeline = [
            {"event": "proposed", "at": str(run.proposed_at), "by": run.proposed_by}
        ]
        for a in run.approvals:
            timeline.append({
                "event": f"approval_{a.action}",
                "at": str(a.approved_at),
                "by": a.approved_by,
                "reason": a.reason,
            })
        if run.executed_at:
            timeline.append({
                "event": "executed",
                "at": str(run.executed_at),
                "by": run.executed_by,
            })
        if run.rolled_back_at:
            timeline.append({
                "event": "rolled_back",
                "at": str(run.rolled_back_at),
                "by": run.rolled_back_by,
                "reason": run.rollback_reason,
            })

        chain_status = await self._verify_hash_chain(run)

        return {
            "decision": d,
            "verification": {
                "audit_hash": run.audit_hash,
                "input_hash": run.input_snapshot_hash,
                "outcome_hash": run.outcome_hash,
                "prev_hash": run.prev_hash,
                **chain_status,
            },
            "timeline": timeline,
            "evidence": run.evidence_refs or [],
        }

    async def _verify_hash_chain(self, run: "DecisionRun") -> Dict[str, Any]:
        """Recompute ``run`` and its predecessors' audit hashes.

        Returns a dict with:
          * ``hash_chain_valid``: True iff every recomputed audit_hash
            matches the stored one within the verification window.
          * ``hash_chain_depth``: how many links we actually walked.
          * ``hash_chain_break_at``: the decision id where the
            recomputation first disagreed (None when valid).
          * ``hash_chain_truncated``: True when we stopped before
            reaching the genesis (prev_hash=NULL); the chain *might*
            still be valid further back, the caller just doesn't know.
        """
        depth = 0
        broken_at: Optional[str] = None
        current: Optional[DecisionRun] = run

        while current is not None and depth < self._HASH_CHAIN_VERIFY_DEPTH:
            recomputed = DecisionRun.calculate_audit_hash(
                decision_id=current.id,
                policy_version=current.policy_version,
                input_hash=current.input_snapshot_hash,
                outcome_hash=current.outcome_hash,
                prev_hash=current.prev_hash,
            )
            if recomputed != current.audit_hash:
                broken_at = str(current.id)
                break
            depth += 1
            if current.prev_hash is None:
                # Reached genesis — full verification complete.
                current = None
                break
            current = await self._fetch_decision_by_audit_hash(current.prev_hash)
            if current is None:
                # Predecessor missing — that's also a chain break.
                broken_at = run.prev_hash if depth == 0 else "missing-predecessor"
                break

        truncated = (
            broken_at is None
            and current is not None
            and depth >= self._HASH_CHAIN_VERIFY_DEPTH
        )
        return {
            "hash_chain_valid": broken_at is None,
            "hash_chain_depth": depth,
            "hash_chain_break_at": broken_at,
            "hash_chain_truncated": truncated,
        }

    async def _fetch_decision_by_audit_hash(
        self, audit_hash: str,
    ) -> Optional["DecisionRun"]:
        """Look up the decision whose ``audit_hash`` equals the argument.

        Used by :meth:`_verify_hash_chain` to walk backward through the
        ledger. Tenant-scoped so cross-tenant chain references can't be
        used to spoof verification.
        """
        stmt = select(DecisionRun).where(
            and_(
                DecisionRun.tenant_id == self.tenant_id,
                DecisionRun.audit_hash == audit_hash,
            )
        ).limit(1)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Shared helpers used by every sub-service (and re-exported via the
    # façade for tests that monkey-patch GovernanceService._run_to_dict
    # or call svc._get_decision_run directly).
    # ------------------------------------------------------------------

    async def _get_decision_run(self, decision_id: str) -> Optional[DecisionRun]:
        """Fetch a DecisionRun by ID, tenant-scoped."""
        try:
            uid = UUID(decision_id) if isinstance(decision_id, str) else decision_id
        except ValueError:
            return None
        stmt = select(DecisionRun).where(
            and_(DecisionRun.id == uid, DecisionRun.tenant_id == self.tenant_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    def _run_to_dict(run: DecisionRun) -> Dict[str, Any]:
        """Convert DecisionRun ORM object to dict."""
        return {
            "id": str(run.id),
            "tenant_id": str(run.tenant_id),
            "decision_type": run.decision_type,
            "title": run.title,
            "description": run.description,
            "status": run.status,
            "policy_version": run.policy_version,
            "autonomy_level": run.autonomy_level,
            "action_data": run.action_data,
            "expected_impact": run.expected_impact,
            "risk_level": run.risk_level,
            "scenario_id": str(run.scenario_id) if run.scenario_id else None,
            "evidence_refs": run.evidence_refs or [],
            "input_snapshot_hash": run.input_snapshot_hash,
            "prev_hash": run.prev_hash,
            "audit_hash": run.audit_hash,
            "proposed_at": run.proposed_at.isoformat() if run.proposed_at else None,
            "proposed_by": run.proposed_by,
            "approved_at": run.approved_at.isoformat() if run.approved_at else None,
            "executed_at": run.executed_at.isoformat() if run.executed_at else None,
            "executed_by": run.executed_by,
            "rolled_back_at": run.rolled_back_at.isoformat() if run.rolled_back_at else None,
            "rolled_back_by": run.rolled_back_by,
            "rollback_reason": run.rollback_reason,
            "approvals": [
                {
                    "id": str(a.id),
                    "action": a.action,
                    "approved_by": a.approved_by,
                    "approved_at": a.approved_at.isoformat() if a.approved_at else None,
                    "reason": a.reason,
                    "approver_role": a.approver_role,
                    "conditions": a.conditions,
                }
                for a in (run.approvals or [])
            ],
        }
