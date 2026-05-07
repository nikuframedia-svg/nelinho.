"""Q.17.D — process-wide singleton accessor for ``RuleEngine``.

The engine is mostly stateless apart from in-memory firing records, so
sharing one instance across the FastAPI process is fine. The runtime
guard here is small:

- :func:`get_engine` returns the singleton, creating it on first call.
- :func:`reset_engine` is for tests — drops the registry so each test
  starts clean.
- :func:`startup_refresh` is called once during FastAPI ``lifespan`` —
  loads ``status=active`` rules across all tenants into the registry.

Emission points (CPO scheduler, KPI thresholder, etc.) call
``await get_engine().on_event(...)`` from anywhere — no DI needed.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.governance.yaml_policy.dispatchers import DispatchContext
from src.governance.yaml_policy.engine import RuleEngine

_log = logging.getLogger(__name__)

_engine: RuleEngine | None = None


# ---------------------------------------------------------------------------
# Dispatch context factory — injects real callbacks (alert/kafka/config)
# ---------------------------------------------------------------------------


def _build_dispatch_context(
    *,
    tenant_id: UUID,
    event_type: str,
    payload: dict[str, Any],
    session: AsyncSession | None,
) -> DispatchContext:
    """Q.17.F.4 — assemble a DispatchContext with real callbacks.

    When ``session`` is provided, ``emit_alert`` persists a CopilotAlert
    row so the alert appears in the operator's Painel CEO immediately.
    Other callbacks (emit_kafka, set_config, create_decision) are
    progressively wired in subsequent Q.17.F sub-sprints.
    """

    async def _emit_alert(alert_payload: dict[str, Any]) -> None:
        if session is None:
            return
        try:
            from src.copilot.alerts.models import CopilotAlert, STATUS_ACTIVE
            severity_raw = str(alert_payload.get("severity", "info")).upper()
            # Map yaml_policy severity vocabulary to CopilotAlert severities
            severity = {
                "CRITICAL": "CRITICAL", "HIGH": "WARN",
                "MEDIUM": "WARN", "LOW": "INFO", "INFO": "INFO",
            }.get(severity_raw, "WARN")
            row = CopilotAlert(
                tenant_id=tenant_id,
                severity=severity,
                code=f"YAML_POLICY_{alert_payload.get('rule_id', 'unknown').upper()}",
                title=str(alert_payload.get("title", "Regra disparou"))[:255],
                message_pt=str(alert_payload.get("message_pt", "")),
                context={
                    "source_event": alert_payload.get("source_event"),
                    "rule_id": alert_payload.get("rule_id"),
                    "fired_at": alert_payload.get("fired_at", datetime.now(timezone.utc).isoformat()),
                },
                entity_refs=list(alert_payload.get("entity_refs", []) or []),
                status=STATUS_ACTIVE,
            )
            session.add(row)
            # Caller controls commit; if they don't, autocommit on
            # request close still flushes. Don't raise on persist
            # errors — alerts are best-effort.
        except Exception as exc:
            _log.warning("emit_alert via yaml_policy failed: %s", exc)

    async def _set_config(category: str, key: str, value: Any, reason: str | None) -> None:
        if session is None:
            return
        try:
            from src.core.models.tenant_configuration import SOURCE_LEARNED_RULE
            from src.core.services.tenant_config_service import TenantConfigService
            svc = TenantConfigService(session, tenant_id)
            await svc.set(
                category=category, key=key, value=value,
                user_id=None, data_type="json",
                # Sprint X.1 — flag the row as 'learned_rule' so the UI
                # can render the right provenance badge (Plan v4 §4.7).
                source=SOURCE_LEARNED_RULE,
            )
            # ``reason`` is captured in the rule's audit revision row and
            # in the dispatcher log; TenantConfigService.set has no
            # reason field today (Q.17.F.5 will add audit_reason).
            _log.debug("set_config %s.%s applied (reason=%r)", category, key, reason)
        except Exception as exc:
            _log.warning("set_config via yaml_policy failed: %s", exc)

    return DispatchContext(
        tenant_id=tenant_id,
        event_type=event_type,
        event_payload=payload,
        session=session,
        emit_alert=_emit_alert,
        emit_kafka=None,  # Q.17.F.5 — wire to outbox_dispatcher
        set_config=_set_config,
        create_decision=None,  # Q.17.F.6 — wire to governance.decisions
    )


def get_engine() -> RuleEngine:
    """Return the process-wide engine singleton (lazy-init).

    The singleton is created with ``ctx_factory`` set to
    :func:`_build_dispatch_context` so every fired rule gets real
    backend wiring (alerts persist, set_config writes through, etc.).
    """
    global _engine
    if _engine is None:
        _engine = RuleEngine(ctx_factory=_build_dispatch_context)
        _log.debug("yaml_policy.RuleEngine singleton created with dispatch factory")
    return _engine


def reset_engine() -> None:
    """Drop the singleton — for unit tests only."""
    global _engine
    _engine = None


async def startup_refresh(session: AsyncSession) -> int:
    """Pull ``status=active`` rules from DB into the engine.

    Called from FastAPI ``lifespan`` after ``init_db``. Returns the
    rule count loaded. Safe to call multiple times.
    """
    engine = get_engine()
    count = await engine.refresh(session)
    _log.info("yaml_policy engine warmed: %d active rules", count)
    return count
