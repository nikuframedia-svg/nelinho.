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

Three default handlers ship here. Sprint Q.9 Onda 2.3 promoted them
from "intent-only audit shims" to real writes:

* `reschedule_order`   — calls `SchedulingService.update_dates(...)` to
  move a `ProductionSchedule` row to new start/end dates.
* `mold_maintenance`   — calls `MoldService.plan_maintenance(...)` to
  register a maintenance event in the `mold_maintenance_event` table.
* `rework_routing`     — updates the `ReworkEntry.context` with the
  worker the rework is assigned to (no dedicated column existed; we
  use the structured context field so the schema stays stable).

Handlers degrade gracefully:
* Missing session → log + return intent-only result (audit shim mode)
  so background callers (Kafka consumers, batch retries) without a
  live transaction don't blow up.
* Lookup miss → log + return `{"status": "not_found", ...}` so the
  executor reports it without raising.
* Domain-service failure → propagates to the executor (which the
  caller in `execute_decision` flips to FAILED).

Each handler still increments the per-type counter so tests + R.1
dashboard observability stays the same as before.
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


def _parse_uuid(value: Any) -> Optional[UUID]:
    """Best-effort cast of action_data values to UUID.

    Returns None when the value is missing or unparsable. Callers that
    need to short-circuit should check the return value before
    proceeding to a DB call.
    """
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        return None


def _parse_datetime_or_date(value: Any):
    """Accept ISO datetime/date strings or already-parsed objects.

    Returns datetime/date depending on input. Mold maintenance tracks
    by date; scheduling rows track by datetime.
    """
    from datetime import date as _date, datetime as _dt

    if value is None:
        return None
    if isinstance(value, (_dt, _date)):
        return value
    s = str(value)
    try:
        # Datetime first (carries time-of-day for scheduling rows).
        return _dt.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        try:
            return _date.fromisoformat(s[:10])
        except ValueError:
            return None


async def _handle_reschedule_order(ctx: ActionContext) -> Dict[str, Any]:
    """Move a ProductionSchedule row to new start/end dates.

    Sprint Q.9 Onda 2.3 — was a stub that only logged intent. Now
    calls `SchedulingService.update_dates(...)` directly with the
    schedule_id from action_data. The Timeline UI's apply path
    populates `action_data` with `{schedule_id, new_start_date,
    new_end_date}` (or `new_start`/`new_end` shorthand).

    Returns `{"status": "rescheduled" | "not_found" | "no_session"}`
    so the executor + audit log can report the actual outcome.
    """
    schedule_id = _parse_uuid(
        ctx.action_data.get("schedule_id")
        or ctx.action_data.get("production_schedule_id")
    )
    new_start = _parse_datetime_or_date(
        ctx.action_data.get("new_start_date")
        or ctx.action_data.get("new_start")
        or ctx.action_data.get("new_date")
    )
    new_end = _parse_datetime_or_date(
        ctx.action_data.get("new_end_date")
        or ctx.action_data.get("new_end")
    )

    base = {
        "intent": "reschedule_order",
        "schedule_id": str(schedule_id) if schedule_id else None,
        "new_start": new_start.isoformat() if new_start else None,
        "new_end": new_end.isoformat() if new_end else None,
    }

    if ctx.session is None or schedule_id is None:
        # Audit-shim mode. No write attempted; caller decides whether
        # to flag this as a precondition failure.
        logger.info(
            "reschedule_order AUDIT — decision=%s schedule_id=%s by=%s "
            "(no session or missing id)",
            ctx.decision_id, schedule_id, ctx.executed_by,
        )
        return {**base, "status": "no_session" if ctx.session is None else "missing_id"}

    from src.plan.services.scheduling_service import SchedulingService

    svc = SchedulingService(ctx.session, ctx.tenant_id)
    row = await svc.update_dates(schedule_id, new_start=new_start, new_end=new_end)
    if row is None:
        logger.warning(
            "reschedule_order NOT_FOUND — decision=%s schedule_id=%s tenant=%s",
            ctx.decision_id, schedule_id, ctx.tenant_id,
        )
        return {**base, "status": "not_found"}

    logger.info(
        "reschedule_order OK — decision=%s schedule_id=%s by=%s",
        ctx.decision_id, schedule_id, ctx.executed_by,
    )
    return {**base, "status": "rescheduled", "order_id": str(row.order_id) if row.order_id else None}


async def _handle_mold_maintenance(ctx: ActionContext) -> Dict[str, Any]:
    """Register a planned maintenance event for a mould.

    Sprint Q.9 Onda 2.3 — calls `MoldService.plan_maintenance(...)`.
    Expects `action_data["mold_id"]` (UUID) and either
    `action_data["planned_date"]` (ISO date) or `new_date`. Optional:
    `maintenance_type` (default "preventive"), `technician_id`,
    `comments` / `reason`.

    Returns `{"status": "planned" | "no_session" | "missing_id"}`.
    """
    mold_id = _parse_uuid(ctx.action_data.get("mold_id"))
    planned_date_raw = (
        ctx.action_data.get("planned_date")
        or ctx.action_data.get("new_date")
    )
    planned = _parse_datetime_or_date(planned_date_raw)
    # Accept datetime → coerce to its date component (the model column
    # is `Date`). `_parse_datetime_or_date` returns datetime first
    # because the scheduling row also calls it; for the mould table we
    # only keep the date component.
    from datetime import datetime as _dt
    if isinstance(planned, _dt):
        planned = planned.date()

    maintenance_type = ctx.action_data.get("maintenance_type") or "preventive"
    technician_id = _parse_uuid(ctx.action_data.get("technician_id"))
    comments = ctx.action_data.get("comments") or ctx.action_data.get("reason")

    base = {
        "intent": "mold_maintenance",
        "mold_id": str(mold_id) if mold_id else None,
        "planned_date": planned.isoformat() if planned else None,
        "maintenance_type": maintenance_type,
    }

    if ctx.session is None or mold_id is None or planned is None:
        logger.info(
            "mold_maintenance AUDIT — decision=%s mold_id=%s planned=%s by=%s "
            "(missing session/id/date)",
            ctx.decision_id, mold_id, planned, ctx.executed_by,
        )
        if ctx.session is None:
            return {**base, "status": "no_session"}
        if mold_id is None:
            return {**base, "status": "missing_mold_id"}
        return {**base, "status": "missing_planned_date"}

    from src.plan.services.mold_service import MoldService

    svc = MoldService(ctx.session, ctx.tenant_id)
    event = await svc.plan_maintenance(
        mold_id=mold_id,
        planned_date=planned,
        maintenance_type=maintenance_type,
        technician_id=technician_id,
        comments=comments,
    )
    logger.info(
        "mold_maintenance OK — decision=%s event=%s mold=%s by=%s",
        ctx.decision_id, event.id, mold_id, ctx.executed_by,
    )
    return {**base, "status": "planned", "event_id": str(event.id)}


async def _handle_rework_routing(ctx: ActionContext) -> Dict[str, Any]:
    """Assign an existing ReworkEntry to a specific worker.

    Sprint Q.9 Onda 2.3 — looks up the ReworkEntry by id and writes
    the assignment into its `context` jsonb (no dedicated column
    existed). The QA02 auto-route-to-causer rule (`should_route_to_
    causer`) covers the *suggestion* path; this handler covers the
    explicit *assignment* path triggered by a manager approval.

    Returns `{"status": "routed" | "not_found" | "no_session"}`.
    """
    rework_id = _parse_uuid(ctx.action_data.get("rework_id"))
    assigned_to = _parse_uuid(
        ctx.action_data.get("assigned_to")
        or ctx.action_data.get("worker_id")
    )

    base = {
        "intent": "rework_routing",
        "rework_id": str(rework_id) if rework_id else None,
        "assigned_to": str(assigned_to) if assigned_to else None,
    }

    if ctx.session is None or rework_id is None:
        logger.info(
            "rework_routing AUDIT — decision=%s rework=%s assigned_to=%s by=%s "
            "(no session or missing id)",
            ctx.decision_id, rework_id, assigned_to, ctx.executed_by,
        )
        return {
            **base,
            "status": "no_session" if ctx.session is None else "missing_rework_id",
        }

    from sqlalchemy import select as _sel
    from src.quality.models.rework import ReworkEntry

    stmt = _sel(ReworkEntry).where(
        ReworkEntry.id == rework_id,
        ReworkEntry.tenant_id == ctx.tenant_id,
    )
    row = (await ctx.session.execute(stmt)).scalar_one_or_none()
    if row is None:
        logger.warning(
            "rework_routing NOT_FOUND — decision=%s rework=%s tenant=%s",
            ctx.decision_id, rework_id, ctx.tenant_id,
        )
        return {**base, "status": "not_found"}

    # Update the structured context — non-destructive merge so any
    # earlier annotations the operator added survive.
    new_context = dict(row.context or {})
    if assigned_to is not None:
        new_context["assigned_to"] = str(assigned_to)
    new_context["routed_decision_id"] = str(ctx.decision_id)
    new_context["routed_by"] = ctx.executed_by
    row.context = new_context

    await ctx.session.flush()
    logger.info(
        "rework_routing OK — decision=%s rework=%s assigned_to=%s by=%s",
        ctx.decision_id, rework_id, assigned_to, ctx.executed_by,
    )
    return {**base, "status": "routed"}


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
