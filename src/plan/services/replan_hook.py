"""
ProdPlan ONE — Replan Hook (Sprint P.14 / PL16)
================================================

Blueprint PL16 — "if capacity increases → automatic replan of distribution".
Also covers routing changes (Sprint P.4/P.5 admins editing templates) and
new transport batches (Sprint P.2).

Consumes the `CONFIG_UPDATED` event stream. When the configuration key
indicates a planning-relevant change, we queue a `trigger_reschedule_job`
via APScheduler — reusing the existing per-tenant scheduler infrastructure
so the job runs off the event-consumer thread.

Design:
* `should_trigger_replan(event_payload)` is a pure predicate tests can
  exercise without APScheduler / Kafka setup.
* `handle_config_updated(payload)` is the async callback invoked by the
  Kafka consumer in production; it calls the predicate and then schedules
  the replan via `trigger_reschedule`.

No state is kept inside this module — the scheduler owns the job queue.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


# Categories/keys that MUST trigger a replan. Anything under these prefixes
# in TenantConfigurationrows flows through to us via the CONFIG_UPDATED event.
TRIGGERING_CATEGORIES = {"planning", "workforce"}

# Inside those categories the specific keys the decoder reads:
TRIGGERING_KEY_PREFIXES = (
    "routing.templates",        # new routing templates admitted
    "routing.",                 # any A/B routing change
    "machine_capacity_h_day",   # PL16 capacity bump
    "laminagem.",               # dual-resource on/off
    "transport.",               # batch size / schedule
    "queue_time.",              # queue gaps altered
    "buffer.",                  # post-Desmolde buffer changes
    "fitness.weight.",          # fitness weights re-balanced
    "mapelites.",               # grid resolution tweaks
    "cpo.",                     # GA hyper-params / budget changes
    "worker_count",             # workforce expands
)


def should_trigger_replan(event_payload: Dict[str, Any]) -> bool:
    """Return True when the CONFIG_UPDATED payload warrants a replan.

    We look at `payload.config_type` for the legacy rate-config events
    ("labor_rates", …) and at `payload.config_type` plus `affected_entities`
    for Sprint L-style events (config_type="tenant_configuration.<category>").
    """
    config_type = str(event_payload.get("config_type") or "")

    # Sprint L events embed the category after a dot.
    # e.g. config_type="tenant_configuration.planning"
    if config_type.startswith("tenant_configuration."):
        category = config_type.split(".", 1)[1]
        if category not in TRIGGERING_CATEGORIES:
            return False
        keys: list = event_payload.get("affected_entities") or []
        return any(
            any(str(k).startswith(prefix) for prefix in TRIGGERING_KEY_PREFIXES)
            for k in keys
        )

    # Legacy rate-config events — capacity bumps come through here via
    # `config_type="machine_rates"` (when a machine's capacity changes).
    if config_type in {"machine_rates", "labor_rates"}:
        return True
    return False


async def handle_config_updated(
    payload: Dict[str, Any],
    *,
    tenant_id: UUID,
    scheduler_hook: Optional[Any] = None,
) -> bool:
    """Event callback: triggers a replan when the payload warrants it.

    `scheduler_hook` is the function that enqueues the actual replan job —
    injected so tests can assert it was called without spinning APScheduler.
    Production callers pass `trigger_reschedule` from `plan.services.replan_service`
    (not yet built; Sprint P shipping stub).
    """
    if not should_trigger_replan(payload):
        return False

    logger.info(
        "replan_hook: config change triggers replan (tenant=%s, type=%s, keys=%s)",
        tenant_id,
        payload.get("config_type"),
        payload.get("affected_entities"),
    )
    if scheduler_hook is None:
        return False
    try:
        await _maybe_await(
            scheduler_hook(tenant_id=tenant_id, reason="CAPACITY_CHANGE", payload=payload)
        )
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("replan_hook: scheduler_hook failed: %s", exc)
        return False
    return True


async def _maybe_await(result: Any) -> Any:
    import inspect

    if inspect.isawaitable(result):
        return await result
    return result
