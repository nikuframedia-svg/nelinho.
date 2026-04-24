"""
ProdPlan ONE — PreferenceRule Service (Sprint E.3)
===================================================

CRUD façade the `/admin/learned-rules` page sits on top of. The detector
(Camada 1) writes new rules with ``status=detected``; operators review
each one via these methods:

* ``list_rules`` — the page filters by status (detected/confirmed/
  rejected) and optionally by type (temporal_block, etc.).
* ``confirm`` — flips a rule to ``confirmed``, stamps ``confirmed_at``
  + ``confirmed_by``, optionally records review notes (a soft caveat).
* ``reject`` — flips to ``rejected`` and requires a reason so the
  detector can't just re-raise the same noise next night (future work:
  the detector consults these to suppress duplicates).
* ``update_metadata`` — allows the operator to tighten the predicate
  or confidence before confirming (e.g. narrow the rule to one phase).

Only confirmed rules are read by the CPO engine (see Sprint E.4).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.governance.models import (
    PreferenceRule,
    PreferenceRuleStatus,
    PreferenceRuleType,
)

logger = logging.getLogger(__name__)


class PreferenceRuleNotFoundError(Exception):
    """Raised when a rule id doesn't resolve inside the tenant scope."""


class PreferenceRuleInvalidTransitionError(Exception):
    """Raised when confirm/reject is called on an already-reviewed rule."""


_VALID_STATUSES = {s.value for s in PreferenceRuleStatus}
_VALID_TYPES = {t.value for t in PreferenceRuleType}


class PreferenceRuleService:
    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    # ─── Read ──────────────────────────────────────────────────────────

    async def list_rules(
        self,
        *,
        status: Optional[str] = None,
        rule_type: Optional[str] = None,
        min_confidence: Optional[float] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[PreferenceRule]:
        """Tenant-scoped listing with the filters the UI exposes."""
        if status is not None and status not in _VALID_STATUSES:
            raise ValueError(f"Unknown status '{status}'")
        if rule_type is not None and rule_type not in _VALID_TYPES:
            raise ValueError(f"Unknown type '{rule_type}'")

        conditions = [PreferenceRule.tenant_id == self.tenant_id]
        if status is not None:
            conditions.append(PreferenceRule.status == status)
        if rule_type is not None:
            conditions.append(PreferenceRule.type == rule_type)
        if min_confidence is not None:
            conditions.append(PreferenceRule.confidence >= Decimal(str(min_confidence)))

        stmt = (
            select(PreferenceRule)
            .where(and_(*conditions))
            .order_by(PreferenceRule.confidence.desc())
            .limit(max(1, min(limit, 500)))
            .offset(max(0, offset))
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_rule(self, rule_id: UUID) -> PreferenceRule:
        stmt = select(PreferenceRule).where(
            and_(
                PreferenceRule.tenant_id == self.tenant_id,
                PreferenceRule.id == rule_id,
            )
        )
        rule = (await self.session.execute(stmt)).scalar_one_or_none()
        if rule is None:
            raise PreferenceRuleNotFoundError(
                f"PreferenceRule {rule_id} not in tenant {self.tenant_id}",
            )
        return rule

    # ─── Write ─────────────────────────────────────────────────────────

    async def confirm(
        self,
        rule_id: UUID,
        *,
        confirmed_by: UUID,
        review_notes: Optional[str] = None,
    ) -> PreferenceRule:
        """Flip DETECTED → CONFIRMED and stamp the reviewer."""
        rule = await self.get_rule(rule_id)
        self._require_detected(rule, action="confirm")

        rule.status = PreferenceRuleStatus.CONFIRMED.value
        rule.confirmed_at = datetime.now(timezone.utc)
        rule.confirmed_by = confirmed_by
        if review_notes:
            rule.review_notes = review_notes
        await self.session.flush()
        logger.info(
            "PreferenceRule confirmed: tenant=%s id=%s by=%s",
            self.tenant_id, rule.id, confirmed_by,
        )
        return rule

    async def reject(
        self,
        rule_id: UUID,
        *,
        rejected_by: UUID,
        reason: str,
    ) -> PreferenceRule:
        """Flip DETECTED → REJECTED with a mandatory human reason."""
        if not reason or not reason.strip():
            raise ValueError("reject() requires a non-empty reason")
        rule = await self.get_rule(rule_id)
        self._require_detected(rule, action="reject")

        rule.status = PreferenceRuleStatus.REJECTED.value
        rule.confirmed_at = datetime.now(timezone.utc)  # generic "actioned_at"
        rule.confirmed_by = rejected_by
        rule.review_notes = reason.strip()
        await self.session.flush()
        logger.info(
            "PreferenceRule rejected: tenant=%s id=%s by=%s reason=%r",
            self.tenant_id, rule.id, rejected_by, reason[:80],
        )
        return rule

    async def update_metadata(
        self,
        rule_id: UUID,
        *,
        description: Optional[str] = None,
        predicate: Optional[Dict[str, Any]] = None,
        confidence: Optional[float] = None,
    ) -> PreferenceRule:
        """Operator-driven tweak before confirming.

        Useful when the detector description reads awkwardly or the
        operator wants to narrow the predicate (e.g. "only K4 mold on
        Fridays" instead of "all Laminagem on Fridays"). Only DETECTED
        rules can be amended — once confirmed the rule is frozen.
        """
        rule = await self.get_rule(rule_id)
        if rule.status != PreferenceRuleStatus.DETECTED.value:
            raise PreferenceRuleInvalidTransitionError(
                f"Only detected rules may be edited (current: {rule.status})"
            )
        if description is not None:
            rule.description = description
        if predicate is not None:
            rule.predicate = predicate
        if confidence is not None:
            if not (0.0 <= confidence <= 1.0):
                raise ValueError("confidence must be in [0, 1]")
            rule.confidence = Decimal(str(round(confidence, 2)))
        await self.session.flush()
        return rule

    # ─── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _require_detected(rule: PreferenceRule, *, action: str) -> None:
        if rule.status != PreferenceRuleStatus.DETECTED.value:
            raise PreferenceRuleInvalidTransitionError(
                f"Cannot {action} a rule in status '{rule.status}' "
                f"(only 'detected' rules may be reviewed)"
            )
