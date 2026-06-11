"""Q.17.D — runtime rule engine.

Subscribes to the 12 whitelisted event types and dispatches actions
when triggers match. Holds an in-memory registry of active rules,
indexed by ``event_type`` for O(1) lookup. Refreshed on demand or via
periodic poll (no watchdog in v1 — DB poll every 30s is enough).

Public API:

- :class:`RuleEngine` — singleton-ish; one per tenant or one global.
- :meth:`RuleEngine.refresh` — pull active rules from DB into registry.
- :meth:`RuleEngine.on_event` — main entry point; called by the host
  application at known emission points.

Rate limiting + dedupe:

- ``rule.safety.max_fires_per_day`` enforced via in-memory daily counter.
- Dedupe key = ``(rule_id, sha256(event_payload))`` — same payload twice
  in 60s window is considered a duplicate and skipped.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.governance.yaml_policy.condition_evaluator import evaluate_all
from src.governance.yaml_policy.dispatchers import (
    DispatchContext,
    DispatchResult,
    dispatch,
)
from src.governance.yaml_policy.models import (
    RuleLifecycleStatus,
    TenantRule,
)
from src.governance.yaml_policy.rule_schema import EventType, Rule

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _payload_fingerprint(event_payload: dict[str, Any]) -> str:
    """Stable hash for dedupe — sorts keys, JSON-serialises, sha256."""
    blob = json.dumps(event_payload, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


@dataclass
class _FiringRecord:
    """Per-rule firing bookkeeping kept in memory."""

    fires_today: int = 0
    today: date = date.min
    recent_fingerprints: dict[str, datetime] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.recent_fingerprints is None:
            self.recent_fingerprints = {}


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class RuleEngine:
    """In-memory active-rule registry + event dispatcher.

    Not a singleton at module level so tests can have isolated instances.
    The host application creates one and calls ``refresh()`` at startup,
    then ``on_event(...)`` from each emission point.
    """

    DEDUPE_WINDOW_SECONDS = 60

    def __init__(self, *, ctx_factory: Any = None):
        # registry: event_type -> list[(TenantRule row, parsed Rule)]
        self._registry: dict[str, list[tuple[TenantRule, Rule]]] = defaultdict(list)
        self._fire_records: dict[str, _FiringRecord] = defaultdict(_FiringRecord)
        self._lock = asyncio.Lock()
        self._last_refresh: datetime | None = None
        self.ctx_factory = ctx_factory  # callable producing DispatchContext if needed

    @property
    def rule_count(self) -> int:
        return sum(len(v) for v in self._registry.values())

    @property
    def event_types_with_rules(self) -> list[str]:
        return [k for k, v in self._registry.items() if v]

    # ---- registry management ----------------------------------------

    async def refresh(self, session: AsyncSession, tenant_id: UUID | None = None) -> int:
        """Reload ``status=active`` rules into memory.

        Returns the new rule count. Acquires an internal lock so
        concurrent refreshes don't shred the registry mid-evaluate.
        """
        async with self._lock:
            stmt = select(TenantRule).where(TenantRule.status == RuleLifecycleStatus.ACTIVE)
            if tenant_id is not None:
                stmt = stmt.where(TenantRule.tenant_id == tenant_id)
            result = await session.execute(stmt)
            rows = list(result.scalars().all())

            new_registry: dict[str, list[tuple[TenantRule, Rule]]] = defaultdict(list)
            invalid = 0
            for row in rows:
                try:
                    rule = Rule.model_validate(row.payload)
                except Exception as exc:  # pragma: no cover — payload corruption
                    _log.warning(
                        "skipping invalid rule payload tenant=%s rule_id=%s: %s",
                        row.tenant_id, row.rule_id, exc,
                    )
                    invalid += 1
                    continue
                new_registry[rule.when.event.value].append((row, rule))

            self._registry = new_registry
            self._last_refresh = datetime.now(timezone.utc)
            _log.info(
                "engine refreshed: %d rules across %d event_types (skipped %d invalid)",
                sum(len(v) for v in new_registry.values()),
                len(new_registry), invalid,
            )
            return self.rule_count

    def install_rule(self, row: TenantRule, rule: Rule) -> None:
        """Insert a single rule into the registry without a DB roundtrip.

        Used immediately after ``RuleProposalService.approve(...)`` so
        the rule starts firing without waiting for the next refresh.
        """
        self._registry[rule.when.event.value].append((row, rule))

    def remove_rule(self, rule_db_id: UUID) -> bool:
        """Drop a rule from the registry by its DB UUID."""
        removed = False
        for event_type, entries in list(self._registry.items()):
            kept = [(r, p) for (r, p) in entries if r.id != rule_db_id]
            if len(kept) != len(entries):
                self._registry[event_type] = kept
                removed = True
        return removed

    # ---- event handling ---------------------------------------------

    async def on_event(
        self,
        event_type: EventType | str,
        payload: dict[str, Any],
        *,
        tenant_id: UUID,
        session: AsyncSession | None = None,
    ) -> list[tuple[Rule, list[DispatchResult]]]:
        """Look up rules for this event, evaluate, dispatch.

        Returns list of (rule, results) for every rule that fired. The
        caller can inspect the results — particularly to check whether
        any ``block`` action was emitted, and refuse the triggering
        operation if so.

        Pure: never raises on rule-side failures. Logs and continues.
        """
        et = event_type.value if isinstance(event_type, EventType) else event_type
        candidates = list(self._registry.get(et, []))
        if not candidates:
            return []

        fingerprint = _payload_fingerprint(payload)
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=self.DEDUPE_WINDOW_SECONDS)
        today = now.date()

        fired: list[tuple[Rule, list[DispatchResult]]] = []
        for row, rule in candidates:
            # Tenant scope check
            if row.tenant_id != tenant_id:
                continue

            # Match conditions
            if not evaluate_all(rule.when.conditions, payload):
                continue

            # Rate limit: per-day cap
            rec = self._fire_records[rule.id]
            if rec.today != today:
                rec.today = today
                rec.fires_today = 0
                rec.recent_fingerprints = {}
            # Q.168 F4.E — prune ANTES dos checks (não só após dispatch):
            # antes, fingerprints fora da janela só eram limpos quando a
            # regra voltava a DISPARAR — uma regra que deixasse de disparar
            # retinha o último lote indefinidamente (leak pequeno mas
            # acumulativo). Aqui a limpeza corre em cada avaliação, mesmo
            # quando o evento acaba rate-limited ou deduped.
            if rec.recent_fingerprints:
                rec.recent_fingerprints = {
                    fp: ts
                    for fp, ts in rec.recent_fingerprints.items()
                    if ts >= cutoff
                }
            cap = rule.safety.max_fires_per_day
            if rec.fires_today >= cap:
                _log.info(
                    "rate-limit hit: rule=%s fires_today=%d cap=%d",
                    rule.id, rec.fires_today, cap,
                )
                continue

            # Dedupe
            last_seen = rec.recent_fingerprints.get(fingerprint)
            if last_seen is not None and last_seen >= cutoff:
                _log.debug("dedupe skip: rule=%s fingerprint=%s", rule.id, fingerprint)
                continue

            # Build dispatch context
            if self.ctx_factory is not None:
                ctx = self.ctx_factory(tenant_id=tenant_id, event_type=et, payload=payload, session=session)
            else:
                ctx = DispatchContext(
                    tenant_id=tenant_id, event_type=et,
                    event_payload=payload, session=session,
                )

            results = await dispatch(rule, ctx)

            # Update bookkeeping (o prune corre antes dos checks, acima)
            rec.fires_today += 1
            rec.recent_fingerprints[fingerprint] = now

            fired.append((rule, results))
            _log.info(
                "rule fired: tenant=%s rule=%s event=%s actions=%d (fires_today=%d/%d)",
                tenant_id, rule.id, et, len(results),
                rec.fires_today, cap,
            )

        return fired

    @staticmethod
    def block_results(fired: list[tuple[Rule, list[DispatchResult]]]) -> list[DispatchResult]:
        """Helper: return the subset of dispatch results that are ``block`` actions.

        Emission points use this to decide whether to refuse the
        triggering operation::

            fired = await engine.on_event(...)
            blocks = RuleEngine.block_results(fired)
            if blocks:
                raise HTTPException(409, detail=blocks[0].payload["reason_pt"])
        """
        out: list[DispatchResult] = []
        for _rule, results in fired:
            for r in results:
                if r.action == "block":
                    out.append(r)
        return out
