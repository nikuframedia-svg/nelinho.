"""Q.66.D.3 — executor sub-service.

Lifecycle stage **execute**. Extracted from ``service.py`` during
Q.66.D.3 Fase 7. Owns:

* ``execute_decision`` (status flip + outcome hash + audit hash refresh)
* ``_dispatch_action`` (route action_data through the ActionExecutor
  registry; downgrade to EXECUTED_PARTIAL on advisory-shim outcomes)
* ``_publish_decision_executed`` (best-effort Kafka announce)
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

from .models import DecisionRun, DecisionStatus

logger = logging.getLogger(__name__)


class DecisionExecutor:
    """Execute lifecycle stage — guard ``status == APPROVED``, compute
    outcome hash, dispatch via ``action_executor``, announce on Kafka.
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
        # Late-bound by the façade — tests inject via
        # ``svc.action_executor = ...`` so we read it back through the
        # façade rather than off our local copy.
        self._facade_ref = None  # type: ignore[assignment]

    async def execute_decision(
        self,
        decision_id: str,
        executed_by: str,
    ) -> Dict[str, Any]:
        """Execute an approved decision.

        Sprint A WG1: in addition to the existing status/audit updates,
        this method publishes a `DECISION_EXECUTED` Kafka event. The
        event carries the full audit trail (decision_id, input/outcome
        hashes, action_data) so downstream consumers — the
        ActionExecutor dispatcher, the frontend Timeline and the audit
        log — can react without re-reading the DB.

        The full action dispatch (actually applying `action_data` to
        the FactoryState) is out of scope here — it belongs to the
        Sprint B CO1 work alongside `rejected_alternatives`. What WG1
        guarantees today is that *the decision is announced* and the
        audit hash chain is refreshed; the listener fan-out is the
        implementation boundary for a proper ActionExecutor in the
        next sprint.
        """
        from .service import ApprovalRequiredError
        from .decision_query import DecisionQuery

        decision_run = await self._get_decision_run(decision_id)
        if not decision_run:
            raise ValueError(f"Decision {decision_id} not found")

        if decision_run.status != DecisionStatus.APPROVED.value:
            raise ApprovalRequiredError(
                f"Decision {decision_id} must be approved before execution "
                f"(current status: {decision_run.status})"
            )

        decision_run.status = DecisionStatus.EXECUTING.value

        try:
            outcome_data = {
                "action_data": decision_run.action_data,
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "executed_by": executed_by,
            }
            outcome_hash = hashlib.sha256(
                json.dumps(outcome_data, sort_keys=True, default=str).encode()
            ).hexdigest()

            decision_run.status = DecisionStatus.EXECUTED.value
            decision_run.executed_at = datetime.now(timezone.utc)
            decision_run.executed_by = executed_by
            decision_run.outcome_hash = outcome_hash
            decision_run.audit_hash = DecisionRun.calculate_audit_hash(
                decision_id=decision_run.id,
                policy_version=decision_run.policy_version,
                input_hash=decision_run.input_snapshot_hash,
                outcome_hash=outcome_hash,
                prev_hash=decision_run.prev_hash,
            )

            await self.db.flush()
            logger.info(f"Decision {decision_id} executed by {executed_by}")

            # WG1 — announce the executed decision on the event bus.
            # Best-effort: the DB update is the source of truth, so a
            # Kafka publish failure should not unwind the execution.
            await self._publish_decision_executed(decision_run, executed_by)

            # Sprint C 4.1 — dispatch to the ActionExecutor registry.
            # A handler that's registered for this decision_type applies
            # the action to domain state; unknown types stay "announced
            # only" (advisory mode, §4.3 blueprint). Handler failures
            # bubble up → we catch below and flip the status to FAILED.
            await self._dispatch_action(decision_run, executed_by)

        except Exception as e:
            decision_run.status = DecisionStatus.FAILED.value
            await self.db.flush()
            logger.error(f"Decision {decision_id} execution failed: {e}")
            raise

        return DecisionQuery._run_to_dict(decision_run)

    async def _dispatch_action(
        self,
        decision_run: "DecisionRun",
        executed_by: str,
    ) -> None:
        """Route the decision's `action_data` to its registered handler.

        Uses the module-level `default_executor` unless the caller
        overrides via ``facade.action_executor`` (dependency-injected
        for tests). A handler failure propagates — the calling
        `execute_decision` turns that into status=FAILED.

        Sprint Q.12 Onda 2.1 — when the handler returns a known
        "advisory shim" status (``no_session`` / ``missing_id`` /
        ``not_found`` / ``no_handler``) we flip the decision to
        :attr:`DecisionStatus.EXECUTED_PARTIAL` instead of leaving it
        EXECUTED.
        """
        from src.governance.action_executor import (
            ActionContext,
            default_executor,
        )

        # Tests inject via facade.action_executor = ...; honour that
        # override before falling back to the registry default.
        injected = (
            getattr(self._facade_ref, "action_executor", None)
            if self._facade_ref is not None
            else None
        )
        executor = injected or default_executor

        ctx = ActionContext(
            decision_id=decision_run.id,
            decision_type=decision_run.decision_type,
            tenant_id=decision_run.tenant_id,
            action_data=decision_run.action_data or {},
            executed_by=executed_by,
            session=self.db,
        )
        # dispatch is best-effort for "no_handler" (advisory mode) but
        # strict for handler failures — they propagate.
        outcome = await executor.dispatch(ctx)

        # ``outcome`` shape: {"status": "handled" | "no_handler",
        # "decision_type": ..., "result": {...}}. The inner ``result``
        # carries the handler's own status string. Anything that says
        # "I didn't actually mutate the domain" downgrades the
        # decision to EXECUTED_PARTIAL so reviewers can find it later.
        if not isinstance(outcome, dict):
            return
        if outcome.get("status") == "no_handler":
            decision_run.status = DecisionStatus.EXECUTED_PARTIAL.value
            return
        result = outcome.get("result")
        if isinstance(result, dict):
            inner = result.get("status")
            if inner in {
                "no_session", "missing_id", "missing_mold_id",
                "missing_planned_date", "missing_rework_id", "not_found",
            }:
                logger.warning(
                    "decision %s: handler returned %r — flipping to "
                    "EXECUTED_PARTIAL (domain state unchanged)",
                    decision_run.id, inner,
                )
                decision_run.status = DecisionStatus.EXECUTED_PARTIAL.value

    async def _publish_decision_executed(
        self,
        decision_run: "DecisionRun",
        executed_by: str,
    ) -> None:
        """Publish a DECISION_EXECUTED event. Best-effort: logs +
        swallows on Kafka failure so an outage of the message bus
        doesn't break the decision execution path itself.
        """
        try:
            from src.shared.kafka_client import EventBase, Topics, publish_event

            event = EventBase(
                event_type="DECISION_EXECUTED",
                tenant_id=decision_run.tenant_id,
                source_module="governance",
                payload={
                    "decision_id": str(decision_run.id),
                    "decision_type": decision_run.decision_type,
                    "risk_level": decision_run.risk_level,
                    "executed_by": executed_by,
                    "action_data": decision_run.action_data,
                    "outcome_hash": decision_run.outcome_hash,
                    "audit_hash": decision_run.audit_hash,
                },
            )
            await publish_event(Topics.DECISION_EXECUTED, event)
        except Exception as exc:  # pragma: no cover — bus outage non-fatal
            logger.warning(
                "DECISION_EXECUTED publish failed for %s: %s",
                decision_run.id, exc,
            )

    # ------------------------------------------------------------------
    # Shared lookup helper (mirror of the query module)
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
