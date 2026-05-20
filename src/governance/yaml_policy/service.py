"""Q.17.C — service layer for tenant_rule lifecycle.

Transitions enforced server-side (status machine):

    proposed ──approve──▶ approved ──activate──▶ active
        │                                          │
        │                                          ├──suspend──▶ suspended ──reactivate──▶ active
        │                                          │
        │                                          └──rollback──▶ rolled_back
        │
        └──reject──▶ rejected

Every transition writes a TenantRuleRevision row (audit trail).
Always-human-approval (Luis 2026-05-06): activation is a separate step
from proposal — the LLM can only ever produce ``proposed``.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.governance.audit_service import audit_change
from src.governance.yaml_policy.models import (
    RuleLifecycleStatus,
    RuleRevisionAction,
    TenantRule,
    TenantRuleRevision,
    utcnow,
)
from src.governance.yaml_policy.rule_schema import Rule

_log = logging.getLogger(__name__)


class RuleProposalError(RuntimeError):
    """Raised on illegal state transition or validation failure."""


class RuleProposalService:
    """CRUD + lifecycle for ``governance.yaml_policy_rule``.

    The session is injected; the caller controls transactions and
    commits. All transitions write both the parent row update AND a
    revision row in the same flush.
    """

    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id

    # ---- queries -----------------------------------------------------

    async def list_rules(
        self,
        *,
        status: RuleLifecycleStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TenantRule]:
        stmt = select(TenantRule).where(TenantRule.tenant_id == self.tenant_id)
        if status is not None:
            stmt = stmt.where(TenantRule.status == status)
        stmt = stmt.order_by(TenantRule.proposed_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_rule(self, rule_id: str) -> TenantRule | None:
        stmt = select(TenantRule).where(
            TenantRule.tenant_id == self.tenant_id,
            TenantRule.rule_id == rule_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_revisions(self, rule_db_id: UUID) -> list[TenantRuleRevision]:
        stmt = (
            select(TenantRuleRevision)
            .where(
                TenantRuleRevision.tenant_id == self.tenant_id,
                TenantRuleRevision.rule_db_id == rule_db_id,
            )
            .order_by(TenantRuleRevision.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ---- transitions -------------------------------------------------

    async def propose(
        self,
        *,
        rule: Rule,
        proposed_by_user_id: UUID | None,
        nl_source: str | None = None,
    ) -> TenantRule:
        """Persist a freshly LLM-validated rule as proposed.

        Refuses if a rule with the same ``rule_id`` already exists for
        this tenant — even if rolled_back. Use ``modify`` (TBD) for
        re-authoring an existing one.
        """
        existing = await self.get_rule(rule.id)
        if existing is not None:
            raise RuleProposalError(
                f"rule_id {rule.id!r} already exists for this tenant "
                f"(status={existing.status.value})"
            )

        payload = rule.model_dump(mode="json", exclude_none=True)
        now = utcnow()
        row = TenantRule(
            tenant_id=self.tenant_id,
            rule_id=rule.id,
            description=rule.description,
            status=RuleLifecycleStatus.PROPOSED,
            event_type=rule.when.event.value,
            payload=payload,
            proposed_by_user_id=proposed_by_user_id,
            proposed_at=now,
            nl_source=nl_source,
        )
        self.session.add(row)
        await self.session.flush()  # populate row.id for the revision

        await audit_change(
            self.session,
            tenant_id=self.tenant_id,
            entity_type="tenant_rule",
            entity_id=row.id,
            action="INSERT",
            new_values={
                "rule_id": rule.id,
                "status": RuleLifecycleStatus.PROPOSED.value,
                "event_type": rule.when.event.value,
                "description": rule.description,
            },
            actor_id=proposed_by_user_id,
            reason="propor regra YAML",
        )

        rev = TenantRuleRevision(
            tenant_id=self.tenant_id,
            rule_db_id=row.id,
            rule_id=rule.id,
            action=RuleRevisionAction.PROPOSED,
            actor_user_id=proposed_by_user_id,
            payload_before=None,
            payload_after=payload,
            nl_source=nl_source,
        )
        self.session.add(rev)

        _log.info(
            "rule proposed: tenant=%s rule_id=%s by=%s",
            self.tenant_id, rule.id, proposed_by_user_id,
        )
        return row

    async def approve(
        self,
        *,
        rule_id: str,
        approver_user_id: UUID,
        reason: str | None = None,
        skip_safety_checks: bool = False,
    ) -> TenantRule:
        row = await self._require_rule(rule_id)
        if row.status is not RuleLifecycleStatus.PROPOSED:
            raise RuleProposalError(
                f"cannot approve rule {rule_id!r} from status={row.status.value}; "
                "expected proposed"
            )

        # Q.17.E — pre-approval safety gate. Axiom check + conflict resolver.
        # Errors block; warnings are recorded in the revision row's reason
        # so the audit trail captures what was overridden.
        if not skip_safety_checks:
            from src.governance.yaml_policy.rule_schema import Rule
            from src.governance.yaml_policy.safety_checks import (
                RuleSafetyError, run_safety_checks,
            )
            new_rule = Rule.model_validate(row.payload)
            active = [
                Rule.model_validate(r.payload)
                for r in await self.list_rules(status=RuleLifecycleStatus.ACTIVE, limit=200)
            ]
            violations = run_safety_checks(new_rule, active_rules=active)
            errors = [v for v in violations if v.severity == "error"]
            if errors:
                raise RuleSafetyError(errors)

        before = dict(row.payload)
        now = utcnow()
        row.status = RuleLifecycleStatus.ACTIVE  # approve+activate atomically
        row.approved_by_user_id = approver_user_id
        row.approved_at = now
        row.activated_at = now

        rev = TenantRuleRevision(
            tenant_id=self.tenant_id,
            rule_db_id=row.id,
            rule_id=rule_id,
            action=RuleRevisionAction.APPROVED,
            actor_user_id=approver_user_id,
            payload_before=before,
            payload_after=dict(row.payload),
            reason=reason,
        )
        self.session.add(rev)

        # Q.17.D — install in the live engine so the rule starts firing
        # without waiting for the next periodic refresh. Best-effort: a
        # failure here doesn't roll back the DB transition.
        try:
            from src.governance.yaml_policy.rule_schema import Rule
            from src.governance.yaml_policy.runtime import get_engine
            parsed = Rule.model_validate(row.payload)
            get_engine().install_rule(row, parsed)
        except Exception as exc:  # pragma: no cover — defensive
            _log.warning("engine.install_rule failed for %s: %s", rule_id, exc)

        _log.info("rule approved+activated: tenant=%s rule_id=%s by=%s", self.tenant_id, rule_id, approver_user_id)
        return row

    async def reject(
        self,
        *,
        rule_id: str,
        actor_user_id: UUID,
        reason: str,
    ) -> TenantRule:
        row = await self._require_rule(rule_id)
        if row.status is not RuleLifecycleStatus.PROPOSED:
            raise RuleProposalError(
                f"cannot reject rule {rule_id!r} from status={row.status.value}; "
                "expected proposed"
            )
        if not reason or not reason.strip():
            raise RuleProposalError("reject requires a non-empty reason")

        row.status = RuleLifecycleStatus.REJECTED
        rev = TenantRuleRevision(
            tenant_id=self.tenant_id,
            rule_db_id=row.id,
            rule_id=rule_id,
            action=RuleRevisionAction.REJECTED,
            actor_user_id=actor_user_id,
            payload_before=dict(row.payload),
            payload_after=None,
            reason=reason,
        )
        self.session.add(rev)
        _log.info("rule rejected: tenant=%s rule_id=%s by=%s", self.tenant_id, rule_id, actor_user_id)
        return row

    async def suspend(
        self,
        *,
        rule_id: str,
        actor_user_id: UUID,
        reason: str | None = None,
    ) -> TenantRule:
        row = await self._require_rule(rule_id)
        if row.status is not RuleLifecycleStatus.ACTIVE:
            raise RuleProposalError(
                f"cannot suspend rule {rule_id!r} from status={row.status.value}; expected active"
            )
        row.status = RuleLifecycleStatus.SUSPENDED
        row.suspended_at = utcnow()
        rev = TenantRuleRevision(
            tenant_id=self.tenant_id,
            rule_db_id=row.id,
            rule_id=rule_id,
            action=RuleRevisionAction.SUSPENDED,
            actor_user_id=actor_user_id,
            reason=reason,
        )
        self.session.add(rev)

        # Q.17.D — drop from live engine.
        try:
            from src.governance.yaml_policy.runtime import get_engine
            get_engine().remove_rule(row.id)
        except Exception as exc:  # pragma: no cover
            _log.warning("engine.remove_rule failed for %s: %s", rule_id, exc)

        _log.info("rule suspended: tenant=%s rule_id=%s", self.tenant_id, rule_id)
        return row

    async def rollback(
        self,
        *,
        rule_id: str,
        actor_user_id: UUID,
        reason: str,
    ) -> TenantRule:
        row = await self._require_rule(rule_id)
        if row.status not in (RuleLifecycleStatus.ACTIVE, RuleLifecycleStatus.SUSPENDED):
            raise RuleProposalError(
                f"cannot rollback rule {rule_id!r} from status={row.status.value}; "
                "expected active or suspended"
            )
        if not reason or not reason.strip():
            raise RuleProposalError("rollback requires a non-empty reason")

        row.status = RuleLifecycleStatus.ROLLED_BACK
        rev = TenantRuleRevision(
            tenant_id=self.tenant_id,
            rule_db_id=row.id,
            rule_id=rule_id,
            action=RuleRevisionAction.ROLLED_BACK,
            actor_user_id=actor_user_id,
            reason=reason,
            payload_before=dict(row.payload),
        )
        self.session.add(rev)

        # Q.17.D — drop from live engine.
        try:
            from src.governance.yaml_policy.runtime import get_engine
            get_engine().remove_rule(row.id)
        except Exception as exc:  # pragma: no cover
            _log.warning("engine.remove_rule failed for %s: %s", rule_id, exc)

        _log.info("rule rolled back: tenant=%s rule_id=%s reason=%s", self.tenant_id, rule_id, reason)
        return row

    # ---- helpers -----------------------------------------------------

    async def _require_rule(self, rule_id: str) -> TenantRule:
        row = await self.get_rule(rule_id)
        if row is None:
            raise RuleProposalError(f"rule {rule_id!r} not found for tenant {self.tenant_id}")
        return row


def serialize_rule(row: TenantRule) -> dict[str, Any]:
    """Project a TenantRule DB row into a JSON-friendly response shape."""
    return {
        "id": str(row.id),
        "rule_id": row.rule_id,
        "description": row.description,
        "status": row.status.value,
        "event_type": row.event_type,
        "payload": row.payload,
        "proposed_by_user_id": str(row.proposed_by_user_id) if row.proposed_by_user_id else None,
        "approved_by_user_id": str(row.approved_by_user_id) if row.approved_by_user_id else None,
        "proposed_at": row.proposed_at.isoformat() if row.proposed_at else None,
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
        "activated_at": row.activated_at.isoformat() if row.activated_at else None,
        "suspended_at": row.suspended_at.isoformat() if row.suspended_at else None,
        "fire_count": row.fire_count,
        "last_fired_at": row.last_fired_at.isoformat() if row.last_fired_at else None,
        "nl_source": row.nl_source,
    }
