"""Q.66.D.3 — proposer sub-service.

Lifecycle stage **propose**. Extracted from ``service.py`` (1669L god-file)
during Q.66.D.3 Fase 7. Owns:

* ``propose_decision`` / ``propose_decision_with_deferred_kafka``
* ``_propose_decision_impl`` (the shared body with the kill-switch check,
  hash-chain lock, audit_log insert and outbox row)
* ``_get_last_decision_hash`` + ``_lock_chain_for_tenant`` (chain head
  read, advisory lock) — shared with the approver/executor through the
  façade.
* ``_coerce_actor_uuid`` helper — re-exported from ``service.py`` for
  backward-compat with any import path that already touches it.

The façade ``GovernanceService.propose_decision`` delegates here.
Characterization snapshots in
``tests/governance/test_governance_service_characterization_q66_d.py``
pin the observable behaviour.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.governance.audit_service import audit_change

from .models import (
    DEFAULT_POLICIES,
    AutonomyLevel,
    DecisionRun,
    DecisionStatus,
)

logger = logging.getLogger(__name__)


def _coerce_actor_uuid(value: Optional[str]) -> Optional[UUID]:
    """Best-effort coerce a free-form actor string to UUID for audit_log.

    ``proposed_by`` / ``approved_by`` are ``String(100)`` on the model
    (sometimes a UUID, sometimes a label like ``yaml_policy:rule_xyz``).
    ``core.audit_log.actor_id`` is a UUID column — if we can't parse,
    leave it NULL and rely on ``reason`` for the human-readable trail.
    """
    if not value:
        return None
    try:
        return UUID(value)
    except (TypeError, ValueError):
        return None


class DecisionProposer:
    """Propose lifecycle stage — kill-switch check, policy lookup,
    audit-hash seeding, audit log insert, outbox enqueue.
    """

    def __init__(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        policies: Dict[str, Dict[str, Any]],
    ) -> None:
        self.db = db
        self.tenant_id = tenant_id
        self._policies = policies
        # Late-bound by the façade so we can re-use the auto-approval gate
        # and kill-switch query without duplicating them here.
        self._auto_approval_allowed = None  # type: ignore[assignment]
        self._is_kill_switch_active = None  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def propose_decision_with_deferred_kafka(
        self, **kwargs,
    ) -> tuple[Dict[str, Any], Optional[Any]]:
        """Like :meth:`propose_decision` but returns the Kafka event
        instead of publishing it.

        Sprint Q.12 Onda 2.3 — callers that wrap multiple writes in a
        single outer transaction (e.g. ``SandboxService.publish``) use
        this so the bus only sees IDs that survived the commit. The
        caller is responsible for publishing ``deferred_event`` AFTER
        their commit succeeds.

        Returns ``(decision_dict, deferred_event_or_None)`` — the event
        is ``None`` when the build failed (caller should still log the
        local commit but won't have anything to publish).
        """
        return await self._propose_decision_impl(
            defer_kafka=True, **kwargs,
        )

    async def propose_decision(
        self,
        decision_type: str,
        title: str,
        action_data: Dict[str, Any],
        proposed_by: str,
        description: Optional[str] = None,
        expected_impact: Optional[Dict[str, Any]] = None,
        risk_level: str = "medium",
        scenario_id: Optional[str] = None,
        evidence_refs: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Public propose entry — publishes Kafka eagerly (current contract)."""
        decision, _event = await self._propose_decision_impl(
            decision_type=decision_type,
            title=title,
            action_data=action_data,
            proposed_by=proposed_by,
            description=description,
            expected_impact=expected_impact,
            risk_level=risk_level,
            scenario_id=scenario_id,
            evidence_refs=evidence_refs,
            defer_kafka=False,
        )
        return decision

    # ------------------------------------------------------------------
    # Core implementation
    # ------------------------------------------------------------------

    async def _propose_decision_impl(
        self,
        decision_type: str,
        title: str,
        action_data: Dict[str, Any],
        proposed_by: str,
        description: Optional[str] = None,
        expected_impact: Optional[Dict[str, Any]] = None,
        risk_level: str = "medium",
        scenario_id: Optional[str] = None,
        evidence_refs: Optional[List[str]] = None,
        defer_kafka: bool = False,
    ) -> tuple[Dict[str, Any], Optional[Any]]:
        """Propose a new decision (shared body for both public entry points)."""
        # Q.12 Onda 2.2 — refuse new decisions whose scope is currently
        # kill-switched. Allow ``decision_type == "kill_switch"`` itself
        # through so an admin can stack a wider block on top of an
        # existing one (rollback path doesn't go through propose).
        from .service import KillSwitchActiveError

        if decision_type != "kill_switch":
            active = await self._is_kill_switch_active(decision_type=decision_type)
            if active is not None:
                raise KillSwitchActiveError(
                    scope=active.scope,
                    decision_id=active.decision_id,
                    reason=active.reason,
                )

        # Get policy (fallback to a safe default if unknown type).
        policy = self._policies.get(decision_type)
        if not policy:
            policy = {
                "decision_type": decision_type,
                "autonomy_level": AutonomyLevel.L2.value,
                "requires_approval": True,
                "required_approvers": 1,
                "requires_different_approver": True,
            }

        # Input hash (stable JSON encoding).
        input_data = {
            "decision_type": decision_type,
            "action_data": action_data,
            "expected_impact": expected_impact,
            "scenario_id": scenario_id,
        }
        input_hash = hashlib.sha256(
            json.dumps(input_data, sort_keys=True, default=str).encode()
        ).hexdigest()

        # Chain integrity: read current chain head (per-tenant advisory lock).
        last_hash = await self._get_last_decision_hash()

        decision_id_uuid = uuid4()
        policy_version = policy.get("version", "1.0.0")

        audit_hash = DecisionRun.calculate_audit_hash(
            decision_id=decision_id_uuid,
            policy_version=policy_version,
            input_hash=input_hash,
            outcome_hash=None,
            prev_hash=last_hash,
        )

        # Initial status (Sprint M.5: auto-approval gated by trust + tenant config).
        initial_status = DecisionStatus.PROPOSED.value
        if policy.get("requires_approval", True):
            initial_status = DecisionStatus.PENDING_APPROVAL.value
            if await self._auto_approval_allowed(
                decision_type=decision_type,
                risk_level=risk_level,
            ):
                initial_status = DecisionStatus.APPROVED.value
                logger.info(
                    "auto-approved decision (tenant=%s type=%s risk=%s)",
                    self.tenant_id, decision_type, risk_level,
                )

        # Persist DecisionRun + audit log + (optionally) outbox row.
        scenario_uuid = UUID(scenario_id) if scenario_id else None
        decision_run = DecisionRun(
            id=decision_id_uuid,
            tenant_id=self.tenant_id,
            decision_type=decision_type,
            title=title,
            description=description,
            status=initial_status,
            policy_version=policy_version,
            autonomy_level=policy.get("autonomy_level", AutonomyLevel.L2.value),
            action_data=action_data,
            expected_impact=expected_impact,
            risk_level=risk_level,
            scenario_id=scenario_uuid,
            evidence_refs=evidence_refs or [],
            input_snapshot_hash=input_hash,
            prev_hash=last_hash,
            audit_hash=audit_hash,
            proposed_by=proposed_by,
            # Initialise the collection eagerly: a freshly-proposed
            # decision has zero approvals, and assigning [] here stops
            # `_run_to_dict` from triggering a lazy SELECT after flush
            # (which raises greenlet_spawn in the async session).
            approvals=[],
        )

        self.db.add(decision_run)
        await audit_change(
            self.db,
            tenant_id=self.tenant_id,
            entity_type="decision_run",
            entity_id=decision_id_uuid,
            action="INSERT",
            new_values={
                "decision_type": decision_type,
                "title": title,
                "status": initial_status,
                "risk_level": risk_level,
                "autonomy_level": decision_run.autonomy_level,
            },
            actor_id=_coerce_actor_uuid(proposed_by),
            reason="propor decisão",
        )
        await self.db.flush()

        logger.info(f"Decision proposed: {decision_id_uuid} ({decision_type})")

        # Q.61.11 — outbox pattern. Antes, este sitio fazia `await
        # publish_event(...)` sincrono; se o broker Kafka nao respondia,
        # o handler bloqueava (>30s) e o worker uvicorn ficava preso.
        # Agora escrevemos uma linha em `EventOutbox` na MESMA tx que o
        # decision_run, e o dispatcher background publica quando o Kafka
        # voltar — at-least-once com idempotency_key.
        from src.shared.kafka_client import EventBase

        from .decision_query import DecisionQuery

        event = EventBase(
            event_type="DECISION_PROPOSED",
            tenant_id=self.tenant_id,
            source_module="governance",
            payload={
                "decision_id": str(decision_run.id),
                "decision_type": decision_type,
                "title": title,
                "proposed_by": proposed_by,
                "risk_level": risk_level,
                "status": decision_run.status,
                "autonomy_level": decision_run.autonomy_level,
                "action_data": action_data,
                "expected_impact": expected_impact,
                "scenario_id": scenario_id,
            },
        )

        if defer_kafka:
            # Caller (e.g. SandboxService.publish) will emit after its
            # outer commit lands. We don't touch the bus here.
            return DecisionQuery._run_to_dict(decision_run), event

        from src.shared.observability import get_trace_id
        from src.shared.outbox_models import EventOutbox

        # Q.61.12 — injecta trace_id no payload para correlacao
        # request HTTP -> event -> consumer. Quando Q.61.18 adicionar
        # coluna correlation_id no EventOutbox, esta linha migra para
        # campo dedicado; ate la, o trace_id viaja no JSONB.
        outbox_payload = dict(event.payload)
        trace_id = get_trace_id()
        if trace_id is not None:
            outbox_payload["trace_id"] = trace_id

        self.db.add(EventOutbox(
            tenant_id=self.tenant_id,
            aggregate_id=decision_run.id,
            aggregate_type="decision_run",
            event_type="DECISION_PROPOSED",
            payload=outbox_payload,
            status="pending",
        ))

        return DecisionQuery._run_to_dict(decision_run), None

    # ------------------------------------------------------------------
    # Hash-chain helpers — used by proposer + approver + executor
    # ------------------------------------------------------------------

    async def _get_last_decision_hash(self) -> Optional[str]:
        """Get the hash of the most recent decision (for chain integrity).

        Q.12 Onda 1.1 — takes a PostgreSQL transaction-level advisory
        lock keyed on the tenant before reading. Without the lock, two
        concurrent ``propose_decision`` calls would both read the same
        ``last_hash``, both compute an ``audit_hash`` rooted at the same
        ``prev_hash``, and both flush — turning the audit chain into a
        tree (which silently breaks the C5 invariant that every
        decision links to *the* prior one).

        The lock is released automatically on commit/rollback. The key
        is a stable 64-bit integer derived from the tenant UUID so two
        proposals against different tenants don't serialise against
        each other.
        """
        await self._lock_chain_for_tenant()

        stmt = (
            select(DecisionRun.audit_hash)
            .where(DecisionRun.tenant_id == self.tenant_id)
            .order_by(DecisionRun.proposed_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()
        return row

    async def _lock_chain_for_tenant(self) -> None:
        """Acquire a per-tenant advisory lock for the audit chain.

        No-op on non-PostgreSQL backends — keeps the unit tests (which
        use ``FakeSession``/sqlite) green without losing the production
        guarantee. The lock auto-releases on transaction commit/abort.
        """
        from sqlalchemy import text

        try:
            dialect = self.db.bind.dialect.name if self.db.bind else None
        except Exception:
            dialect = None
        if dialect != "postgresql":
            return

        # 64-bit signed key derived from the tenant uuid. Two callers
        # for the same tenant land on the same key; cross-tenant
        # proposals don't serialise.
        key = int.from_bytes(self.tenant_id.bytes[:8], "big", signed=True)
        try:
            await self.db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": key})
        except Exception as exc:  # pragma: no cover — backend quirks
            logger.warning(
                "advisory_xact_lock failed for tenant=%s: %s — falling "
                "back to lock-free path; chain integrity at risk.",
                self.tenant_id, exc,
            )
