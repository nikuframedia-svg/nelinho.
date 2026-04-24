"""
ProdPlan ONE — Action Executor (Sprint C 4.1 / WG1)
====================================================

After `GovernanceService.execute_decision` flips a decision to EXECUTED
and emits the Kafka event, this module is responsible for turning the
decision's `action_data` into a concrete change on the factory's state
(a rescheduled order, a mould marked for maintenance, a rework routed
to a new worker).

Design: a tiny registry (`decision_type → async handler`). Handlers are
plain async callables — the registry is populated at import time by
domain services that want to participate. Unknown decision types are
silently ignored so the rest of the pipeline stays up: the Kafka event
is still fired (downstream listeners can react), and the status stays
EXECUTED with the audit hash intact. That matches the blueprint §4.3
Advisory-Mode spec: the announcement IS the primary commitment; the
state mutation is the best-effort fan-out.

Failures inside a registered handler DO bubble up so the caller can
flip status to FAILED + rollback the hash chain (the caller in
`execute_decision` already catches + retries that path).

Three default handlers land here as thin audit shims until Sprint D
wires the real domain services:

* `reschedule_order`   — records intent; a later release will call the
  real SchedulingService once it exposes an idempotent apply method.
* `mold_maintenance`   — records intent; will call
  MoldService.register_maintenance_event when that exists.
* `rework_routing`     — records intent; will call ReworkService.reassign.

Each stub logs the action + increments a per-type counter so tests
can assert the right handler was invoked.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


ActionHandler = Callable[["ActionContext"], Awaitable[Dict[str, Any]]]


class ActionContext:
    """Everything a handler needs without importing the DecisionRun model.

    Holds the decision's identifiers, `action_data` payload, and the
    session so handlers that need to write to the DB can reuse the
    existing transaction.
    """

    def __init__(
        self,
        *,
        decision_id: UUID,
        decision_type: str,
        tenant_id: UUID,
        action_data: Dict[str, Any],
        executed_by: str,
        session: Any = None,
    ) -> None:
        self.decision_id = decision_id
        self.decision_type = decision_type
        self.tenant_id = tenant_id
        self.action_data = dict(action_data or {})
        self.executed_by = executed_by
        self.session = session


class ActionExecutor:
    """Registry + dispatch for decision-type handlers.

    Callers instantiate once (or use the module-level `default_executor`)
    and call `dispatch(ctx)` after the DB status flip. Handlers are
    registered via `register(decision_type, handler)` at import time.
    """

    def __init__(self) -> None:
        self._handlers: Dict[str, ActionHandler] = {}
        # Per-type invocation counter — useful for tests + observability.
        self.invocation_counts: Dict[str, int] = {}

    def register(
        self,
        decision_type: str,
        handler: ActionHandler,
        *,
        overwrite: bool = False,
    ) -> None:
        """Attach a handler to a decision_type."""
        if not overwrite and decision_type in self._handlers:
            raise ValueError(
                f"Handler for {decision_type!r} already registered; "
                f"pass overwrite=True to replace"
            )
        self._handlers[decision_type] = handler

    def registered_types(self) -> List[str]:
        return sorted(self._handlers.keys())

    async def dispatch(self, ctx: ActionContext) -> Dict[str, Any]:
        """Find the handler for `ctx.decision_type` and invoke it.

        Returns a result dict with at least `{"status": ...}`:
          * `"status": "handled"`     — handler ran cleanly
          * `"status": "no_handler"`  — no handler registered; caller
            decides whether that's acceptable (today yes — advisory
            mode; later we may require registration)

        If the handler raises, the exception propagates. The caller is
        expected to flip the decision to FAILED and log.
        """
        handler = self._handlers.get(ctx.decision_type)
        if handler is None:
            logger.info(
                "ActionExecutor: no handler for decision_type=%r — "
                "audit trail kept, domain state unchanged (decision_id=%s)",
                ctx.decision_type, ctx.decision_id,
            )
            return {"status": "no_handler", "decision_type": ctx.decision_type}

        self.invocation_counts[ctx.decision_type] = (
            self.invocation_counts.get(ctx.decision_type, 0) + 1
        )
        logger.info(
            "ActionExecutor: dispatching decision_type=%r (decision_id=%s)",
            ctx.decision_type, ctx.decision_id,
        )
        result = await handler(ctx)
        return {"status": "handled", "decision_type": ctx.decision_type, "result": result}


# ─── Built-in handlers — thin audit shims ────────────────────────────


async def _handle_reschedule_order(ctx: ActionContext) -> Dict[str, Any]:
    """Record the intent to reschedule an order. Real apply-reschedule
    lives in SchedulingService once it exposes an idempotent method —
    until then we log + echo the action_data so the event listeners
    downstream (Timeline UI, audit sinks) have something to display.
    """
    order_id = ctx.action_data.get("order_id")
    new_date = ctx.action_data.get("new_start_date") or ctx.action_data.get("new_date")
    logger.info(
        "reschedule_order INTENT — decision=%s order=%s new_date=%s by=%s",
        ctx.decision_id, order_id, new_date, ctx.executed_by,
    )
    return {
        "intent": "reschedule_order",
        "order_id": order_id,
        "new_date": str(new_date) if new_date else None,
    }


async def _handle_mold_maintenance(ctx: ActionContext) -> Dict[str, Any]:
    """Record the intent to enter a mould into maintenance. Real call
    is `MoldService.register_maintenance_event` when that lands.
    """
    mold_id = ctx.action_data.get("mold_id") or ctx.action_data.get("mold_code")
    reason = ctx.action_data.get("reason")
    logger.info(
        "mold_maintenance INTENT — decision=%s mold=%s reason=%s by=%s",
        ctx.decision_id, mold_id, reason, ctx.executed_by,
    )
    return {
        "intent": "mold_maintenance",
        "mold_id": mold_id,
        "reason": reason,
    }


async def _handle_rework_routing(ctx: ActionContext) -> Dict[str, Any]:
    """Record the intent to route a rework entry. Real call is
    `ReworkService.reassign` when that lands.
    """
    rework_id = ctx.action_data.get("rework_id")
    assigned_to = ctx.action_data.get("assigned_to") or ctx.action_data.get("worker_id")
    logger.info(
        "rework_routing INTENT — decision=%s rework=%s assigned_to=%s by=%s",
        ctx.decision_id, rework_id, assigned_to, ctx.executed_by,
    )
    return {
        "intent": "rework_routing",
        "rework_id": rework_id,
        "assigned_to": assigned_to,
    }


def _build_default_executor() -> ActionExecutor:
    """Produce a fresh ActionExecutor with the three built-in handlers.

    Tests use this to get a clean registry per-run rather than sharing
    the module-level singleton.
    """
    executor = ActionExecutor()
    executor.register("reschedule_order", _handle_reschedule_order)
    executor.register("mold_maintenance", _handle_mold_maintenance)
    executor.register("rework_routing", _handle_rework_routing)
    return executor


# Module-level singleton the GovernanceService consumes by default.
default_executor: ActionExecutor = _build_default_executor()
