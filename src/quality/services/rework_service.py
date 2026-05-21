"""
ProdPlan ONE - Rework Service (Sprint R.1)
===========================================

CRUD + auto-routing for `ReworkEntry`. Implements QA02 — for a rework
whose rework phase is Pintura, the scheduler is hinted to assign the
rework op back to the original causer.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.quality.models.rework import ErrorCatalog, ReworkEntry

logger = logging.getLogger(__name__)

# QA02 — phases that trigger auto-routing the rework op back to the causer.
AUTO_ROUTE_CAUSER_PHASE_KEYWORDS = ("pintura",)


class ReworkNotFoundError(Exception):
    pass


class ReworkService:
    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def record(
        self,
        *,
        of_id: str,
        error_code: str,
        detected_at: datetime,
        original_op_id: Optional[str] = None,
        rework_op_id: Optional[str] = None,
        model_id: Optional[str] = None,
        causer_employee_id: Optional[UUID] = None,
        chefe_employee_id: Optional[UUID] = None,
        phase_id_causer: Optional[str] = None,
        phase_id_rework: Optional[str] = None,
        error_description: Optional[str] = None,
        root_cause_category: Optional[str] = None,
        mold_id: Optional[str] = None,
        material_lot_id: Optional[str] = None,
        supplier_id: Optional[UUID] = None,
        detected_by: Optional[str] = None,
        cost_estimate_eur: Optional[Decimal] = None,
        hours_lost: Optional[Decimal] = None,
        context: Optional[dict] = None,
        notes: Optional[str] = None,
    ) -> ReworkEntry:
        row = ReworkEntry(
            id=uuid4(),
            tenant_id=self.tenant_id,
            original_op_id=original_op_id,
            rework_op_id=rework_op_id,
            of_id=of_id,
            model_id=model_id,
            causer_employee_id=causer_employee_id,
            chefe_employee_id=chefe_employee_id,
            phase_id_causer=phase_id_causer,
            phase_id_rework=phase_id_rework,
            error_code=error_code,
            error_description=error_description,
            root_cause_category=root_cause_category,
            mold_id=mold_id,
            material_lot_id=material_lot_id,
            supplier_id=supplier_id,
            detected_at=detected_at,
            detected_by=detected_by,
            cost_estimate_eur=cost_estimate_eur,
            hours_lost=hours_lost,
            context=context or {},
            notes=notes,
        )
        # Q.66.B.3: ReworkEntry e evento operacional (detecao de retrabalho
        # com causer/chefe/mold/custo), nao state autoritativo de governance —
        # auditoria propria via Kafka REWORK_ENTRY_CREATED + tabela quality.
        self.session.add(row)  # noqa: audit_coverage  # quality event, kafka-audited, not gov state
        await self.session.flush()

        try:
            from src.shared.kafka_client import EventBase, Topics, publish_event

            await publish_event(
                Topics.REWORK_ENTRY_CREATED,
                EventBase(
                    event_type="REWORK_ENTRY_CREATED",
                    tenant_id=self.tenant_id,
                    source_module="quality",
                    payload={
                        "rework_id": str(row.id),
                        "of_id": row.of_id,
                        "error_code": row.error_code,
                        "original_op_id": row.original_op_id,
                        "rework_op_id": row.rework_op_id,
                        "causer_employee_id": str(row.causer_employee_id) if row.causer_employee_id else None,
                        "phase_id_causer": row.phase_id_causer,
                        "phase_id_rework": row.phase_id_rework,
                        "detected_at": row.detected_at.isoformat() if row.detected_at else None,
                        "detected_by": row.detected_by,
                        "cost_estimate_eur": float(row.cost_estimate_eur) if row.cost_estimate_eur is not None else None,
                        "hours_lost": float(row.hours_lost) if row.hours_lost is not None else None,
                    },
                ),
            )
        except Exception as exc:  # pragma: no cover — best-effort
            logger.warning("REWORK_ENTRY_CREATED publish failed for %s: %s", row.id, exc)

        return row

    async def list_rework(
        self,
        *,
        of_id: Optional[str] = None,
        phase_id: Optional[str] = None,
        mold_id: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[ReworkEntry]:
        stmt = select(ReworkEntry).where(ReworkEntry.tenant_id == self.tenant_id)
        if of_id:
            stmt = stmt.where(ReworkEntry.of_id == of_id)
        if phase_id:
            stmt = stmt.where(
                (ReworkEntry.phase_id_rework == phase_id)
                | (ReworkEntry.phase_id_causer == phase_id)
            )
        if mold_id:
            stmt = stmt.where(ReworkEntry.mold_id == mold_id)
        if since:
            stmt = stmt.where(ReworkEntry.detected_at >= since)
        if until:
            stmt = stmt.where(ReworkEntry.detected_at <= until)
        stmt = stmt.order_by(ReworkEntry.detected_at.desc()).limit(max(1, min(limit, 500)))
        return list((await self.session.execute(stmt)).scalars().all())

    async def resolve(
        self,
        *,
        rework_id: UUID,
        resolved_by: Optional[str] = None,
    ) -> ReworkEntry:
        stmt = select(ReworkEntry).where(
            and_(
                ReworkEntry.tenant_id == self.tenant_id,
                ReworkEntry.id == rework_id,
            )
        )
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise ReworkNotFoundError(str(rework_id))
        row.resolved_at = datetime.now(timezone.utc)
        row.resolved_by = resolved_by
        await self.session.flush()
        return row

    # ─── QA02 — auto-routing hint for Pintura rework ──────────────────────

    @staticmethod
    def should_route_to_causer(phase_id_rework: Optional[str]) -> bool:
        """Pintura rework flows back to the causer (QA02)."""
        if not phase_id_rework:
            return False
        lowered = str(phase_id_rework).lower()
        return any(keyword in lowered for keyword in AUTO_ROUTE_CAUSER_PHASE_KEYWORDS)


class ErrorCatalogService:
    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def upsert(
        self,
        *,
        error_code: str,
        name: str,
        description: Optional[str] = None,
        typical_phase: Optional[str] = None,
        severity_hint: str = "medium",
        preventive_action_hint: Optional[str] = None,
        mold_related: bool = False,
    ) -> ErrorCatalog:
        stmt = select(ErrorCatalog).where(
            and_(
                ErrorCatalog.tenant_id == self.tenant_id,
                ErrorCatalog.error_code == error_code,
            )
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            existing.name = name
            existing.description = description
            existing.typical_phase = typical_phase
            existing.severity_hint = severity_hint
            existing.preventive_action_hint = preventive_action_hint
            existing.mold_related = mold_related
            await self.session.flush()
            return existing
        row = ErrorCatalog(
            id=uuid4(),
            tenant_id=self.tenant_id,
            error_code=error_code,
            name=name,
            description=description,
            typical_phase=typical_phase,
            severity_hint=severity_hint,
            preventive_action_hint=preventive_action_hint,
            mold_related=mold_related,
            active=True,
        )
        # Q.66.B.3: ErrorCatalog upsert e seed/sync da taxonomia de erros
        # (admin config raramente alterada, severity_hint + preventive_action),
        # nao state operacional autoritativo. ReworkEntry e que e o evento.
        self.session.add(row)  # noqa: audit_coverage  # taxonomy upsert, not gov state
        await self.session.flush()
        return row

    async def list_codes(self, *, mold_related_only: bool = False) -> list[ErrorCatalog]:
        stmt = select(ErrorCatalog).where(
            and_(
                ErrorCatalog.tenant_id == self.tenant_id,
                ErrorCatalog.active.is_(True),
            )
        )
        if mold_related_only:
            stmt = stmt.where(ErrorCatalog.mold_related.is_(True))
        stmt = stmt.order_by(ErrorCatalog.error_code)
        return list((await self.session.execute(stmt)).scalars().all())
