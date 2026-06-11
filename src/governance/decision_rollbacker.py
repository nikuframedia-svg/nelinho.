"""Q.66.D.3 — rollbacker + kill-switch sub-service.

Lifecycle stages **rollback** + **kill_switch**. Extracted from
``service.py`` during Q.66.D.3 Fase 7. Owns:

* ``rollback_decision`` (status flip + audit + Kafka announce)
* ``_publish_decision_rolled_back``
* ``activate_kill_switch`` (the admin "arm" path — auto-executes the
  underlying decision_type=kill_switch DecisionRun)
* ``_record_kill_switch_active`` (durable block row, idempotent per scope)
* ``is_kill_switch_active`` (scope lookup: ``all`` + ``decision_type:foo``)
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.governance.audit_service import audit_change

from .decision_proposer import _coerce_actor_uuid
from .models import (
    DecisionRun,
    DecisionStatus,
    KillSwitchActive,
)

logger = logging.getLogger(__name__)


class DecisionRollbacker:
    """Rollback + kill-switch arming.

    Rollback path: flips an EXECUTED decision to ROLLED_BACK and emits a
    DECISION_ROLLED_BACK event. The actual state revert (applying
    ``before_state`` to the FactoryState / DB) lives in the
    ActionExecutor.

    Kill-switch path: ``activate_kill_switch`` proposes a
    ``decision_type=kill_switch`` DecisionRun, auto-executes it (the
    kill_switch policy bypasses approval) and inserts/refreshes a
    ``KillSwitchActive`` row. Subsequent ``propose_decision`` calls
    against the same scope raise :class:`KillSwitchActiveError`.
    """

    def __init__(self, db: AsyncSession, tenant_id: UUID) -> None:
        self.db = db
        self.tenant_id = tenant_id
        # Late-bound by the façade to re-enter through the public surface
        # (so external monkey-patches / subclasses still take effect).
        self._propose_decision_via_facade = None  # type: ignore[assignment]
        self._get_decision_via_facade = None  # type: ignore[assignment]
        self._facade_ref = None  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------

    async def rollback_decision(
        self,
        decision_id: str,
        rolled_back_by: str,
        reason: str,
    ) -> Dict[str, Any]:
        """Rollback an executed decision.

        Sprint C 1.4 (WG2) — in addition to the status flip + audit
        bookkeeping, this emits a `DECISION_ROLLED_BACK` Kafka event
        carrying the parent commit chain so downstream listeners (the
        future ActionExecutor rollback handler, the Timeline UI, audit
        sinks) can act on the reversal without re-reading the DB.

        The actual state revert lives in the ActionExecutor — Sprint
        C 4.1 wires that dispatcher. Right now the contract is
        "announce the rollback; database status is source of truth".
        """
        from .decision_query import DecisionQuery

        decision_run = await self._get_decision_run(decision_id)
        if not decision_run:
            raise ValueError(f"Decision {decision_id} not found")

        if decision_run.status != DecisionStatus.EXECUTED.value:
            raise ValueError(
                f"Only executed decisions can be rolled back "
                f"(current: {decision_run.status})"
            )

        if not reason or len(reason) < 10:
            raise ValueError("Rollback reason is required (min 10 characters)")

        decision_run.status = DecisionStatus.ROLLED_BACK.value
        decision_run.rolled_back_at = datetime.now(timezone.utc)
        decision_run.rolled_back_by = rolled_back_by
        decision_run.rollback_reason = reason

        await self.db.flush()
        logger.info(
            f"Decision {decision_id} rolled back by {rolled_back_by}: {reason}"
        )

        # WG2 — announce on the event bus. Best-effort as with execute_decision.
        await self._publish_decision_rolled_back(decision_run, rolled_back_by, reason)

        return DecisionQuery._run_to_dict(decision_run)

    async def _publish_decision_rolled_back(
        self,
        decision_run: "DecisionRun",
        rolled_back_by: str,
        reason: str,
    ) -> None:
        """Publish a DECISION_ROLLED_BACK event. Best-effort — swallows
        Kafka failures so a broker outage doesn't re-break the rollback
        path the operator just used to recover.
        """
        try:
            from src.shared.kafka_client import EventBase, Topics, publish_event

            event = EventBase(
                event_type="DECISION_ROLLED_BACK",
                tenant_id=decision_run.tenant_id,
                source_module="governance",
                payload={
                    "decision_id": str(decision_run.id),
                    "decision_type": decision_run.decision_type,
                    "rolled_back_by": rolled_back_by,
                    "reason": reason,
                    "action_data": decision_run.action_data,
                    "outcome_hash": decision_run.outcome_hash,
                    "audit_hash": decision_run.audit_hash,
                },
            )
            await publish_event(Topics.DECISION_ROLLED_BACK, event)
        except Exception as exc:  # pragma: no cover — bus outage non-fatal
            logger.warning(
                "DECISION_ROLLED_BACK publish failed for %s: %s",
                decision_run.id, exc,
            )

    # ------------------------------------------------------------------
    # Kill switch — activate + state
    # ------------------------------------------------------------------

    async def activate_kill_switch(
        self,
        scope: str,
        activated_by: str,
        reason: str,
    ) -> Dict[str, Any]:
        """Activate kill switch (no approval required).

        Sprint Q.12 Onda 1.3 — recomputes ``audit_hash`` to honour the
        chain integrity check. Sprint Q.12 Onda 2.2 — also persists a
        ``KillSwitchActive`` row so subsequent decisions can be
        rejected by :func:`assert_no_active_kill_switch`. The previous
        version printed a warning log and called it done; nothing in
        the pipeline actually consulted that warning.
        """
        decision = await self._propose_decision_via_facade(
            decision_type="kill_switch",
            title=f"KILL SWITCH: {scope}",
            action_data={"scope": scope, "reason": reason},
            proposed_by=activated_by,
            risk_level="critical",
        )

        # Auto-execute (kill switch policy bypasses approval).
        run = await self._get_decision_run(decision["id"])
        if run:
            outcome_data = {
                "action_data": run.action_data,
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "executed_by": activated_by,
                "kill_switch_scope": scope,
            }
            outcome_hash = hashlib.sha256(
                json.dumps(outcome_data, sort_keys=True, default=str).encode()
            ).hexdigest()

            run.status = DecisionStatus.EXECUTED.value
            run.executed_at = datetime.now(timezone.utc)
            run.executed_by = activated_by
            run.outcome_hash = outcome_hash
            run.audit_hash = DecisionRun.calculate_audit_hash(
                decision_id=run.id,
                policy_version=run.policy_version,
                input_hash=run.input_snapshot_hash,
                outcome_hash=outcome_hash,
                prev_hash=run.prev_hash,
            )

            # Sprint Q.12 Onda 2.2 — durable block. Idempotent: if the
            # scope is already active we refresh the metadata rather
            # than inserting a duplicate row.
            await self._record_kill_switch_active(
                scope=scope,
                decision_id=run.id,
                activated_by=activated_by,
                reason=reason,
            )

            await self.db.flush()

        logger.critical(
            f"KILL SWITCH ACTIVATED by {activated_by}: {scope} - {reason}"
        )

        return await self._get_decision_via_facade(decision["id"])

    async def _record_kill_switch_active(
        self,
        *,
        scope: str,
        decision_id: UUID,
        activated_by: str,
        reason: str,
    ) -> None:
        """Insert/refresh the durable kill-switch row.

        Composite PK is ``(tenant_id, scope)`` so re-activating the
        same scope just updates the metadata (latest decision_id and
        ``activated_at``) — there's no semantic to having two rows for
        the same active scope.
        """
        existing = await self.db.execute(
            select(KillSwitchActive).where(
                and_(
                    KillSwitchActive.tenant_id == self.tenant_id,
                    KillSwitchActive.scope == scope,
                )
            )
        )
        row = existing.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        # Composite PK (tenant_id, scope) — use decision_id as
        # entity_id since the kill-switch row has no surrogate UUID.
        audit_snapshot = {
            "scope": scope,
            "decision_id": str(decision_id),
            "activated_by": activated_by,
            "reason": reason,
        }
        if row is None:
            ks_row = KillSwitchActive(
                tenant_id=self.tenant_id, scope=scope, decision_id=decision_id,
                activated_at=now, activated_by=activated_by, reason=reason,
            )
            self.db.add(ks_row)
            await audit_change(
                self.db, tenant_id=self.tenant_id, entity_type="kill_switch",
                entity_id=decision_id, action="INSERT",
                new_values=audit_snapshot,
                actor_id=_coerce_actor_uuid(activated_by),
                reason="activação de kill switch",
            )
        else:
            row.decision_id = decision_id
            row.activated_at = now
            row.activated_by = activated_by
            row.reason = reason
            row.deactivated_at = None
            row.deactivated_by = None
            await audit_change(
                self.db, tenant_id=self.tenant_id, entity_type="kill_switch",
                entity_id=decision_id, action="UPDATE",
                new_values=audit_snapshot,
                actor_id=_coerce_actor_uuid(activated_by),
                reason="reactivação de kill switch",
            )

    async def is_kill_switch_active(
        self,
        *,
        decision_type: Optional[str] = None,
    ) -> Optional[KillSwitchActive]:
        """Return the active kill-switch row that covers ``decision_type``.

        Scope semantics:
          * ``"all"``                  — blocks every decision_type.
          * ``"decision_type:foo"``    — blocks only ``decision_type=foo``.
          * any other free-form scope is matched literally.

        Returns the first matching active row, or ``None``.
        """
        scopes = ["all"]
        if decision_type:
            scopes.append(f"decision_type:{decision_type}")

        # Q.168 F4.E — com 2+ scopes ativos (ex.: "all" + "decision_type:X")
        # o `.limit(1)` sem ORDER BY devolvia um qualquer de forma
        # não-determinística — o bloqueio funcionava, mas a auditoria de
        # "qual kill switch bloqueou" variava entre execuções. Devolve
        # determinìsticamente o ativado mais recentemente.
        stmt = select(KillSwitchActive).where(
            and_(
                KillSwitchActive.tenant_id == self.tenant_id,
                KillSwitchActive.scope.in_(scopes),
                KillSwitchActive.deactivated_at.is_(None),
            )
        ).order_by(KillSwitchActive.activated_at.desc()).limit(1)
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()
        # Defensive — unit tests with FakeSession queue a single
        # scalar per call site; if the test feeds something other than
        # a ``KillSwitchActive`` row through this path treat it as "no
        # active kill switch" rather than crashing on the attribute
        # access.
        if not isinstance(row, KillSwitchActive):
            return None
        return row

    # ------------------------------------------------------------------
    # Shared lookup helper
    # ------------------------------------------------------------------

    async def _get_decision_run(self, decision_id: str) -> Optional[DecisionRun]:
        """Fetch a DecisionRun by ID, tenant-scoped.

        Routes through the façade when one was wired up — that's the
        path the characterization tests use to monkey-patch the
        ``activate_kill_switch`` flow into looking up the in-memory
        DecisionRun that was just ``self.db.add(...)``-ed.
        """
        # Walk through the façade *each call* so test monkey-patches
        # of `svc._get_decision_run` after construction take effect.
        facade = getattr(self, "_facade_ref", None)
        if facade is not None and hasattr(facade, "_get_decision_run"):
            return await facade._get_decision_run(decision_id)
        try:
            uid = UUID(decision_id) if isinstance(decision_id, str) else decision_id
        except ValueError:
            return None
        stmt = select(DecisionRun).where(
            and_(DecisionRun.id == uid, DecisionRun.tenant_id == self.tenant_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
