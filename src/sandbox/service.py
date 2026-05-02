"""
ProdPlan ONE - Sandbox Service
================================

Service layer for sandbox scenarios. Sprint Q.10 Fase B.

Replaces the in-memory ``sandbox_store`` dict in ``api.py`` with a
real DB-backed CRUD that respects ``tenant_id`` isolation. ``publish``
creates a real ``SharedDecisionRun`` via ``GovernanceService`` instead
of returning a mock UUID.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.sandbox.models import SandboxScenario, SandboxScenarioStatus

logger = logging.getLogger(__name__)


class SandboxNotFoundError(Exception):
    """Raised when a scenario id doesn't belong to the current tenant."""


class SandboxStateError(Exception):
    """Raised when an operation is invalid for the scenario's status."""


class SandboxService:
    """CRUD + simulate + publish for sandbox scenarios."""

    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id

    # ── CRUD ──────────────────────────────────────────────────────────

    async def list_scenarios(
        self,
        *,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[SandboxScenario]:
        stmt = select(SandboxScenario).where(
            SandboxScenario.tenant_id == self.tenant_id,
        )
        if status:
            stmt = stmt.where(SandboxScenario.status == status)
        stmt = stmt.order_by(SandboxScenario.created_at.desc()).limit(limit).offset(offset)
        rows = (await self.session.execute(stmt)).scalars().all()
        return list(rows)

    async def get_scenario(self, scenario_id: UUID) -> Optional[SandboxScenario]:
        stmt = select(SandboxScenario).where(
            and_(
                SandboxScenario.id == scenario_id,
                SandboxScenario.tenant_id == self.tenant_id,
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def create_scenario(
        self,
        *,
        title: str,
        description: Optional[str] = None,
        suggestion_id: Optional[str] = None,
        before_state: Optional[Dict[str, Any]] = None,
    ) -> SandboxScenario:
        scenario = SandboxScenario(
            tenant_id=self.tenant_id,
            title=title,
            description=description,
            suggestion_id=suggestion_id,
            before_state=before_state or {},
            status=SandboxScenarioStatus.DRAFT.value,
        )
        self.session.add(scenario)
        await self.session.flush()
        await self.session.commit()
        await self.session.refresh(scenario)
        return scenario

    # ── Apply suggestion / simulate ───────────────────────────────────

    async def apply_suggestion(
        self,
        scenario_id: UUID,
        suggestion: Dict[str, Any],
    ) -> SandboxScenario:
        """Stamp the suggestion's ``estimated_impact`` onto the scenario's
        ``after_state`` so the next ``simulate`` call has something to
        diff. The caller (typically the ``improve`` module) hands in the
        already-fetched suggestion dict — the sandbox service does not
        depend on the improve schema."""
        scenario = await self.get_scenario(scenario_id)
        if scenario is None:
            raise SandboxNotFoundError(str(scenario_id))

        scenario.suggestion_id = suggestion.get("id")
        scenario.after_state = {
            "estimated_impact": suggestion.get("estimated_impact", {}),
            "applied_at": datetime.utcnow().isoformat(),
        }
        scenario.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(scenario)
        return scenario

    async def simulate(self, scenario_id: UUID) -> SandboxScenario:
        """Compute the impact diff between ``before_state`` and
        ``after_state``. Doesn't run the CPO — the heavy simulation
        lives in the Twin module; sandbox is a quick-look projection."""
        scenario = await self.get_scenario(scenario_id)
        if scenario is None:
            raise SandboxNotFoundError(str(scenario_id))
        if scenario.status not in {
            SandboxScenarioStatus.DRAFT.value,
            SandboxScenarioStatus.SIMULATED.value,
        }:
            raise SandboxStateError(
                f"cannot simulate scenario in status {scenario.status!r}"
            )

        # Mark simulating
        scenario.status = SandboxScenarioStatus.SIMULATING.value
        await self.session.commit()

        before = scenario.before_state or {}
        after = scenario.after_state or {}
        impact_payload = (after.get("estimated_impact") or {}) if isinstance(after, dict) else {}

        # Lightweight impact summary: the keys overlap that have numeric
        # 'delta' fields.
        summary: Dict[str, Any] = {}
        for kpi, info in impact_payload.items():
            if isinstance(info, dict) and "delta" in info:
                summary[kpi] = {
                    "delta": info["delta"],
                    "confidence": info.get("confidence"),
                    "before": _extract_number(before.get(kpi)),
                }

        scenario.impact = summary
        scenario.status = SandboxScenarioStatus.SIMULATED.value
        scenario.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(scenario)
        return scenario

    # ── Publish to governance ─────────────────────────────────────────

    async def publish(
        self,
        scenario_id: UUID,
        *,
        proposed_by: str,
    ) -> SandboxScenario:
        """Create a real ``SharedDecisionRun`` (advisory) and link it.

        Sprint Q.10 — replaces the previous mock ``decision_id`` with
        a live record. Until Sprint G the decision runs in advisory
        mode so the ERP isn't touched.
        """
        from src.governance.service import GovernanceService

        scenario = await self.get_scenario(scenario_id)
        if scenario is None:
            raise SandboxNotFoundError(str(scenario_id))
        if scenario.status != SandboxScenarioStatus.SIMULATED.value:
            raise SandboxStateError(
                "scenario must be SIMULATED before publish; "
                f"current status: {scenario.status}"
            )

        gov = GovernanceService(self.session, self.tenant_id)
        decision = await gov.propose_decision(
            decision_type="sandbox_publish",
            title=f"Sandbox: {scenario.title}",
            description=scenario.description,
            action_data={
                "sandbox_scenario_id": str(scenario.id),
                "before_state": scenario.before_state,
                "after_state": scenario.after_state,
                "impact": scenario.impact,
            },
            proposed_by=proposed_by,
            expected_impact=scenario.impact,
            scenario_id=str(scenario.id),
        )

        scenario.status = SandboxScenarioStatus.PUBLISHED.value
        scenario.published_at = datetime.utcnow()
        scenario.decision_id = UUID(decision["id"]) if isinstance(decision.get("id"), str) else decision.get("id")
        scenario.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(scenario)
        return scenario

    # ── Internals ─────────────────────────────────────────────────────

    async def count_by_tenant(self) -> int:
        stmt = select(func.count(SandboxScenario.id)).where(
            SandboxScenario.tenant_id == self.tenant_id,
        )
        return int((await self.session.execute(stmt)).scalar() or 0)


def _extract_number(value: Any) -> Optional[float]:
    """Pull a numeric value out of either a primitive or a metric dict."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        v = value.get("value")
        if isinstance(v, (int, float)):
            return float(v)
    return None
