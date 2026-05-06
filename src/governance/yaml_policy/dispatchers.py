"""Q.17.D — action dispatchers.

Each :class:`ActionType` has one async dispatcher. Inputs:

- ``rule``: the validated :class:`Rule` whose ``then[*]`` triggered.
- ``params``: ``then[i].params`` (already validated against per-action
  param whitelist).
- ``event_payload``: the original event dict that matched.
- ``ctx``: :class:`DispatchContext` carrying tenant_id, session, etc.

Dispatchers are intentionally **thin**: they log + emit a structured
event into the existing infrastructure (Kafka, alerts, decisions). The
heavy logic lives in the destination service, not here. This keeps the
engine non-invasive — adding a new rule never modifies CPO/quality/etc.

For Q.17.D MVP all 9 dispatchers are stubbed to log + return a
``DispatchResult`` describing what *would* happen. Full wiring to each
destination subsystem is incremental Q.17.D.x follow-ups.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from uuid import UUID

from src.governance.yaml_policy.rule_schema import ActionType, Rule

_log = logging.getLogger(__name__)


@dataclass
class DispatchContext:
    """Per-event context passed to all dispatchers in a fire."""

    tenant_id: UUID
    event_type: str
    event_payload: dict[str, Any]
    session: Any = None  # AsyncSession or None when running engine-only

    # Optional callbacks injected by the host application. Stay None in
    # tests so dispatchers don't need a full backend up.
    emit_alert: Callable[[dict[str, Any]], Awaitable[None]] | None = None
    emit_kafka: Callable[[str, dict[str, Any]], Awaitable[None]] | None = None
    set_config: Callable[[str, str, Any, str | None], Awaitable[None]] | None = None
    create_decision: Callable[[dict[str, Any]], Awaitable[str]] | None = None


@dataclass
class DispatchResult:
    """Structured outcome of an action dispatch.

    ``status`` semantics:
    - ``ok``      — fully wired, side-effect happened
    - ``stubbed`` — handler ran (logged) but the side-effect path is not
      yet connected to the destination subsystem. The frontend surfaces
      this as an amber warning so the operator knows the rule logs but
      doesn't actually enforce.
    - ``skipped`` — handler decided to no-op (e.g. callback missing in
      this context).
    - ``failed``  — exception during dispatch.
    """

    action: str
    status: str  # "ok" | "stubbed" | "skipped" | "failed"
    detail: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


# Q.17.F.1 — wiring matrix. Tells the frontend / admin which actions
# actually take effect today vs which only log. Single source of truth
# for the "is this rule going to do anything" question. Update as
# dispatchers get wired to real subsystems in follow-up sub-sprints.
ACTION_WIRING: dict[str, dict[str, Any]] = {
    "alert":               {"wired": True,  "destination": "CopilotAlert row via runtime._build_dispatch_context"},
    "block":               {"wired": True,  "destination": "engine.block_results() + caller HTTPException 409"},
    "modify_fitness":      {"wired": True,  "destination": "set_config callback → ConfigStore → CPO reads on next schedule"},
    "reassign_worker":     {"wired": False, "destination": "Kafka prodplan.workforce.reassign_requested (consumer TBD)"},
    "propose_maintenance": {"wired": False, "destination": "create_decision callback → governance.decisions (Q.17.F.6)"},
    "notify":              {"wired": False, "destination": "Kafka prodplan.realtime.{channel} (consumer TBD)"},
    "set_config":          {"wired": True,  "destination": "ConfigStore.set() — write-through to tenant_configuration"},
    "create_decision":     {"wired": False, "destination": "governance.decisions table (Q.17.F.6)"},
    "pause_writes":        {"wired": False, "destination": "router middleware (Q.18.D scope)"},
}


def _stubbed_or_ok(action: str, has_callback: bool = True) -> str:
    """Decide ok vs stubbed based on the wiring matrix + callback presence.

    A dispatcher reports ``stubbed`` when the wiring matrix says the
    destination isn't connected yet, OR when the optional callback is
    missing in the context (e.g. running in tests without a session).
    """
    if not ACTION_WIRING.get(action, {}).get("wired", False):
        return "stubbed"
    if not has_callback:
        return "stubbed"
    return "ok"


# ---------------------------------------------------------------------------
# Individual dispatchers
# ---------------------------------------------------------------------------


async def _dispatch_alert(rule: Rule, params: dict[str, Any], ctx: DispatchContext) -> DispatchResult:
    payload = {
        "tenant_id": str(ctx.tenant_id),
        "rule_id": rule.id,
        "severity": params.get("severity", "info"),
        "title": params.get("title", rule.description[:80]),
        "message_pt": params.get("message_pt", ""),
        "entity_refs": params.get("entity_refs", []),
        "source_event": ctx.event_type,
        "fired_at": datetime.now(timezone.utc).isoformat(),
    }
    if ctx.emit_alert is not None:
        await ctx.emit_alert(payload)
    _log.info(
        "yaml_policy.alert tenant=%s rule=%s severity=%s title=%r",
        ctx.tenant_id, rule.id, payload["severity"], payload["title"],
    )
    return DispatchResult(
        action="alert",
        status=_stubbed_or_ok("alert", has_callback=ctx.emit_alert is not None),
        payload=payload,
        detail=None if ctx.emit_alert is not None else "no alert callback in context",
    )


async def _dispatch_block(rule: Rule, params: dict[str, Any], ctx: DispatchContext) -> DispatchResult:
    """Refuse the proposed action by raising the structured outcome.

    The host emission point is responsible for inspecting the result
    list after dispatch and rejecting if any action is ``block``.
    """
    payload = {
        "rule_id": rule.id,
        "scope": params.get("scope", "operation"),
        "reason_pt": params.get("reason_pt", ""),
    }
    _log.warning(
        "yaml_policy.block tenant=%s rule=%s scope=%s reason=%r",
        ctx.tenant_id, rule.id, payload["scope"], payload["reason_pt"],
    )
    # block is structurally always "ok" — the engine reports it via
    # block_results() and the caller is responsible for refusing the
    # triggering operation. No external callback needed.
    return DispatchResult(action="block", status="ok", payload=payload)


async def _dispatch_modify_fitness(rule: Rule, params: dict[str, Any], ctx: DispatchContext) -> DispatchResult:
    """Multiply a fitness weight by ``multiplier`` (bounded ±50% at validation)."""
    payload = {
        "weight_key": params.get("weight_key"),
        "multiplier": float(params.get("multiplier", 1.0)),
    }
    if ctx.set_config is not None:
        # Persist override into ConfigStore — CPO reads weights from there.
        await ctx.set_config(
            "planning",
            f"fitness.weight.{payload['weight_key']}",
            payload["multiplier"],
            f"yaml_policy rule {rule.id}",
        )
    _log.info(
        "yaml_policy.modify_fitness tenant=%s rule=%s weight=%s multiplier=%.3f",
        ctx.tenant_id, rule.id, payload["weight_key"], payload["multiplier"],
    )
    return DispatchResult(
        action="modify_fitness",
        status=_stubbed_or_ok("modify_fitness", has_callback=ctx.set_config is not None),
        payload=payload,
        detail=None if ctx.set_config is not None else "no set_config callback in context",
    )


async def _dispatch_reassign_worker(rule: Rule, params: dict[str, Any], ctx: DispatchContext) -> DispatchResult:
    """Substitute the operator on a phase. Emits Kafka event for the scheduler."""
    payload = {
        "phase_id": params.get("phase_id"),
        "replacement_worker_id": params.get("replacement_worker_id"),
        "reason_pt": params.get("reason_pt", ""),
    }
    if ctx.emit_kafka is not None:
        await ctx.emit_kafka("prodplan.workforce.reassign_requested", {
            "tenant_id": str(ctx.tenant_id),
            "rule_id": rule.id,
            **payload,
        })
    _log.info(
        "yaml_policy.reassign_worker tenant=%s rule=%s phase=%s -> worker=%s",
        ctx.tenant_id, rule.id, payload["phase_id"], payload["replacement_worker_id"],
    )
    return DispatchResult(
        action="reassign_worker",
        status=_stubbed_or_ok("reassign_worker", has_callback=ctx.emit_kafka is not None),
        payload=payload,
        detail="kafka topic emitted but no consumer wired yet",
    )


async def _dispatch_propose_maintenance(rule: Rule, params: dict[str, Any], ctx: DispatchContext) -> DispatchResult:
    payload = {
        "mold_id": params.get("mold_id"),
        "maintenance_type": params.get("maintenance_type", "preventive"),
        "scheduled_date": params.get("scheduled_date"),
        "reason_pt": params.get("reason_pt", ""),
    }
    if ctx.create_decision is not None:
        decision_id = await ctx.create_decision({
            "decision_type": "mold_maintenance",
            "title": f"Manutenção sugerida: {payload['mold_id']}",
            "risk_level": "medium",
            "action_data": payload,
            "source_rule": rule.id,
        })
        payload["decision_id"] = decision_id
    _log.info(
        "yaml_policy.propose_maintenance tenant=%s rule=%s mold=%s type=%s",
        ctx.tenant_id, rule.id, payload["mold_id"], payload["maintenance_type"],
    )
    return DispatchResult(
        action="propose_maintenance",
        status=_stubbed_or_ok("propose_maintenance", has_callback=ctx.create_decision is not None),
        payload=payload,
        detail="not yet wired to governance.decisions",
    )


async def _dispatch_notify(rule: Rule, params: dict[str, Any], ctx: DispatchContext) -> DispatchResult:
    """Push to a SSE channel (alerts/timeline/dashboard/governance)."""
    channel = params.get("channel", "alerts")
    topic = params.get("topic", f"yaml_policy.{rule.id}")
    payload = {
        "channel": channel,
        "topic": topic,
        "payload": params.get("payload", {}),
    }
    if ctx.emit_kafka is not None:
        await ctx.emit_kafka(f"prodplan.realtime.{channel}", {
            "tenant_id": str(ctx.tenant_id),
            "rule_id": rule.id,
            "topic": topic,
            **payload,
        })
    _log.info(
        "yaml_policy.notify tenant=%s rule=%s channel=%s topic=%s",
        ctx.tenant_id, rule.id, channel, topic,
    )
    return DispatchResult(
        action="notify",
        status=_stubbed_or_ok("notify", has_callback=ctx.emit_kafka is not None),
        payload=payload,
        detail="kafka topic emitted but realtime bridge consumer is per-tenant",
    )


async def _dispatch_set_config(rule: Rule, params: dict[str, Any], ctx: DispatchContext) -> DispatchResult:
    payload = {
        "category": params.get("category"),
        "key": params.get("key"),
        "value": params.get("value"),
        "reason_pt": params.get("reason_pt", ""),
    }
    if ctx.set_config is not None:
        await ctx.set_config(
            payload["category"], payload["key"], payload["value"],
            f"yaml_policy rule {rule.id}: {payload['reason_pt']}",
        )
    _log.info(
        "yaml_policy.set_config tenant=%s rule=%s %s.%s=%r",
        ctx.tenant_id, rule.id, payload["category"], payload["key"], payload["value"],
    )
    return DispatchResult(
        action="set_config",
        status=_stubbed_or_ok("set_config", has_callback=ctx.set_config is not None),
        payload=payload,
        detail=None if ctx.set_config is not None else "no set_config callback in context",
    )


async def _dispatch_create_decision(rule: Rule, params: dict[str, Any], ctx: DispatchContext) -> DispatchResult:
    payload = {
        "decision_type": params.get("decision_type"),
        "title": params.get("title", rule.description[:80]),
        "risk_level": params.get("risk_level", "low"),
        "action_data": params.get("action_data", {}),
    }
    if ctx.create_decision is not None:
        decision_id = await ctx.create_decision({
            **payload,
            "source_rule": rule.id,
        })
        payload["decision_id"] = decision_id
    _log.info(
        "yaml_policy.create_decision tenant=%s rule=%s type=%s risk=%s",
        ctx.tenant_id, rule.id, payload["decision_type"], payload["risk_level"],
    )
    return DispatchResult(
        action="create_decision",
        status=_stubbed_or_ok("create_decision", has_callback=ctx.create_decision is not None),
        payload=payload,
        detail="not yet wired to governance.decisions",
    )


async def _dispatch_pause_writes(rule: Rule, params: dict[str, Any], ctx: DispatchContext) -> DispatchResult:
    """Toggle a fail-closed flag for the given route prefix.

    Q.17.D MVP: log + emit. Real implementation requires hooking into
    each affected router's middleware. Out of scope for this sub-sprint;
    Q.18 covers route-level write gates.
    """
    payload = {
        "route_prefix": params.get("route_prefix"),
        "duration_minutes": int(params.get("duration_minutes", 15)),
        "reason_pt": params.get("reason_pt", ""),
    }
    _log.warning(
        "yaml_policy.pause_writes tenant=%s rule=%s prefix=%s dur=%dm (NOT YET WIRED)",
        ctx.tenant_id, rule.id, payload["route_prefix"], payload["duration_minutes"],
    )
    return DispatchResult(
        action="pause_writes",
        status="stubbed",
        payload=payload,
        detail="not yet wired to router middleware",
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


_DISPATCHERS: dict[ActionType, Callable[[Rule, dict[str, Any], DispatchContext], Awaitable[DispatchResult]]] = {
    ActionType.ALERT: _dispatch_alert,
    ActionType.BLOCK: _dispatch_block,
    ActionType.MODIFY_FITNESS: _dispatch_modify_fitness,
    ActionType.REASSIGN_WORKER: _dispatch_reassign_worker,
    ActionType.PROPOSE_MAINTENANCE: _dispatch_propose_maintenance,
    ActionType.NOTIFY: _dispatch_notify,
    ActionType.SET_CONFIG: _dispatch_set_config,
    ActionType.CREATE_DECISION: _dispatch_create_decision,
    ActionType.PAUSE_WRITES: _dispatch_pause_writes,
}


async def dispatch(rule: Rule, ctx: DispatchContext) -> list[DispatchResult]:
    """Run every action in ``rule.then[*]`` in declaration order.

    Returns the list of results in the same order. The engine inspects
    these to know if any ``block`` fired (so the caller can refuse the
    triggering operation).
    """
    results: list[DispatchResult] = []
    for step in rule.then:
        handler = _DISPATCHERS.get(step.action)
        if handler is None:
            # Cannot happen — schema validation rejects unknown actions.
            results.append(DispatchResult(
                action=step.action.value, status="failed",
                detail=f"no dispatcher for {step.action.value}",
            ))
            continue
        try:
            results.append(await handler(rule, step.params, ctx))
        except Exception as exc:  # pragma: no cover - safety net
            _log.exception(
                "dispatcher %s raised for rule=%s",
                step.action.value, rule.id,
            )
            results.append(DispatchResult(
                action=step.action.value, status="failed",
                detail=str(exc),
            ))
    return results
