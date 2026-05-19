"""
ProdPlan ONE — `/v1/activity/recent` endpoint
=============================================

Lightweight read of the most recent events from `event_outbox` for the
LiveActivityFeed UI (`frontend/src/components/activity/LiveActivityFeed.tsx`).

This is a polling fallback while the SSE stream (`/v1/realtime/events`)
is unavailable (e.g. Kafka offline). When `event_outbox` table is empty
or missing (e.g. a fresh dev DB before any event has been emitted), the
endpoint returns `{"items": []}` instead of erroring — the consumer
shows an empty state.

Sprint Q.15.D / KNOWN_ISSUES bringup-fix-2026-05-07.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.exc import ProgrammingError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/activity", tags=["Activity"])


# Map outbox `event_type` (envelope) → UI `type` enum used by
# LiveActivityFeed. Same shape as `EVENT_TEMPLATES` in
# `frontend/src/components/notifications/NotificationsPanel.tsx` but
# coarser: the recent-activity feed only shows the icon family, not a
# full action.
_TYPE_MAP: Dict[str, str] = {
    "INGESTION_COMPLETED": "ingest",
    "INGESTION_FAILED": "ingest",
    "DATA_QUALITY_CHANGED": "quality",
    "QUALITY_RISK_SCORED": "quality",
    "MOLD_MAINT_DUE": "alert",
    "MOLD_HEALTH_DEGRADED": "alert",
    "MATERIAL_SHORTAGE_DETECTED": "alert",
    "CAPACITY_CONSTRAINT_DETECTED": "alert",
    "SCHEDULE_CREATED": "scenario",
    "SCHEDULE_UPDATED": "scenario",
    "SCENARIO_SIMULATED": "scenario",
    "DECISION_PROPOSED": "user",
    "DECISION_APPROVED": "user",
    "DECISION_EXECUTED": "system",
    "DECISION_ROLLED_BACK": "system",
    "EMPLOYEE_ALLOCATED": "user",
    "REWORK_ENTRY_CREATED": "quality",
}

_STATUS_MAP: Dict[str, str] = {
    "INGESTION_COMPLETED": "success",
    "INGESTION_FAILED": "error",
    "DECISION_APPROVED": "success",
    "DECISION_EXECUTED": "success",
    "DECISION_ROLLED_BACK": "warning",
    "MOLD_MAINT_DUE": "warning",
    "MOLD_HEALTH_DEGRADED": "warning",
    "MATERIAL_SHORTAGE_DETECTED": "error",
    "CAPACITY_CONSTRAINT_DETECTED": "error",
    "QUALITY_RISK_SCORED": "warning",
}


def _title_for(event_type: str, payload: Dict[str, Any]) -> str:
    # Short, PT-PT human title. Keep aligned with NotificationsPanel
    # templates but more compact (this is a feed, not a toast).
    titles: Dict[str, str] = {
        "INGESTION_COMPLETED": "Ingestão concluída",
        "INGESTION_FAILED": "Ingestão falhou",
        "DATA_QUALITY_CHANGED": "Trust Index actualizado",
        "QUALITY_RISK_SCORED": "Risco de qualidade",
        "MOLD_MAINT_DUE": "Molde precisa manutenção",
        "MOLD_HEALTH_DEGRADED": "Saúde do molde a degradar",
        "MATERIAL_SHORTAGE_DETECTED": "Rotura de material",
        "CAPACITY_CONSTRAINT_DETECTED": "Gargalo de capacidade",
        "SCHEDULE_CREATED": "Novo plano publicado",
        "SCHEDULE_UPDATED": "Plano actualizado",
        "SCENARIO_SIMULATED": "Cenário simulado",
        "DECISION_PROPOSED": "Decisão proposta",
        "DECISION_APPROVED": "Decisão aprovada",
        "DECISION_EXECUTED": "Decisão executada",
        "DECISION_ROLLED_BACK": "Decisão revertida",
        "EMPLOYEE_ALLOCATED": "Trabalhador alocado",
        "REWORK_ENTRY_CREATED": "Retrabalho registado",
    }
    return titles.get(event_type, event_type.replace("_", " ").title())


def _description_for(event_type: str, payload: Dict[str, Any]) -> Optional[str]:
    # Compact description. Returns None if we don't have a good template;
    # the frontend hides the description line when absent.
    if not isinstance(payload, dict):
        return None
    if event_type == "INGESTION_COMPLETED":
        rows = payload.get("total_rows_curated") or payload.get("total_rows_raw")
        return f"{rows} linhas processadas" if rows else None
    if event_type == "MOLD_MAINT_DUE":
        m = payload.get("mold_code") or payload.get("mold_id")
        return f"Molde {m}" if m else None
    if event_type == "MATERIAL_SHORTAGE_DETECTED":
        sku = payload.get("material_code") or payload.get("sku")
        days = payload.get("days_to_stockout")
        if sku and days is not None:
            return f"{sku} — {days}d até stockout"
        return sku
    if event_type == "DECISION_PROPOSED":
        dt = payload.get("decision_type") or "Decisão"
        return f"{dt}"
    return None


def _link_for(event_type: str, payload: Dict[str, Any]) -> Optional[str]:
    # Frontend route to navigate to when the user clicks the item.
    routes: Dict[str, str] = {
        "INGESTION_COMPLETED": "/admin/data-quality",
        "INGESTION_FAILED": "/admin/data-ingestion",
        "DATA_QUALITY_CHANGED": "/admin/data-quality",
        "MOLD_MAINT_DUE": "/plan/mrp",
        "MATERIAL_SHORTAGE_DETECTED": "/supply/inventory",
        "CAPACITY_CONSTRAINT_DETECTED": "/inbox",
        "SCHEDULE_CREATED": "/plan/timeline",
        "SCHEDULE_UPDATED": "/plan/scheduling",
        "SCENARIO_SIMULATED": "/twin",
        "DECISION_PROPOSED": "/decisions",
        "DECISION_APPROVED": "/decisions",
        "DECISION_EXECUTED": "/decisions",
    }
    return routes.get(event_type)


class ActivityItem(BaseModel):
    """Shape mirrors `frontend/src/components/activity/LiveActivityFeed.tsx`."""

    id: str
    type: str
    title: str
    description: Optional[str] = None
    timestamp: datetime
    status: Optional[str] = None
    link: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ActivityResponse(BaseModel):
    items: List[ActivityItem]


# Map audit-log `entity_type` → UI `type` icon family, used by the
# audit-log fallback below. Audit rows are the authoritative trail of
# every state change (project invariant #7) — so the feed is never empty
# when the factory has actually done something.
_AUDIT_TYPE_MAP: Dict[str, str] = {
    "production_order": "scenario",
    "production_schedule": "scenario",
    "schedule_commit": "scenario",
    "decision": "user",
    "decision_pr": "user",
    "rework_entry": "quality",
    "employee": "user",
    "mold": "alert",
    "ingestion_run": "ingest",
    "yaml_rule": "system",
    "preference_rule": "system",
}

_AUDIT_ACTION_LABEL: Dict[str, str] = {
    "INSERT": "criado",
    "UPDATE": "actualizado",
    "DELETE": "removido",
}


async def _from_audit_log(
    session: AsyncSession, limit: int,
) -> List[ActivityItem]:
    """Fallback feed built from `core.audit_log`.

    Used when `event_outbox` has no rows (the common case in dev and
    whenever the outbox dispatcher has drained it). The audit log is
    written in the same transaction as every state change, so it's the
    honest source of "what the factory did recently".
    """
    stmt = text(
        """
        SELECT id, entity_type, entity_id, action, reason,
               actor_role, created_at
        FROM core.audit_log
        ORDER BY created_at DESC
        LIMIT :limit
        """
    )
    try:
        rows = (await session.execute(stmt, {"limit": limit})).fetchall()
    except (ProgrammingError, OperationalError) as exc:
        logger.info(
            "activity/recent: core.audit_log unavailable (%s)",
            type(exc).__name__,
        )
        return []

    items: List[ActivityItem] = []
    for row in rows:
        try:
            entity_type = str(row[1] or "")
            action = str(row[3] or "")
            reason = row[4]
            created_at = row[6]
            if isinstance(created_at, datetime) and created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            human_entity = entity_type.replace("_", " ").capitalize()
            action_label = _AUDIT_ACTION_LABEL.get(action, action.lower())
            items.append(
                ActivityItem(
                    id=str(row[0]),
                    type=_AUDIT_TYPE_MAP.get(entity_type, "system"),
                    title=f"{human_entity} {action_label}",
                    description=reason or None,
                    timestamp=created_at,
                    status="success" if action == "INSERT" else None,
                    link=None,
                    metadata={"source": "audit_log", "entity_id": str(row[2])},
                )
            )
        except Exception:
            logger.exception("activity/recent: skipping malformed audit row")
            continue
    return items


@router.get("/recent", response_model=ActivityResponse)
async def recent_activity(
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> ActivityResponse:
    """Return the most recent events for the LiveActivityFeed.

    Primary source is `event_outbox`. Q.54.E — when the outbox is empty
    (dev, or after the dispatcher drained it) we fall back to
    `core.audit_log`, which records every state change. Only a genuinely
    quiet factory with zero audit history returns `{"items": []}`.
    """
    stmt = text(
        """
        SELECT id, tenant_id, event_type, payload, created_at
        FROM event_outbox
        ORDER BY created_at DESC
        LIMIT :limit
        """
    )
    try:
        result = await session.execute(stmt, {"limit": limit})
        rows = result.fetchall()
    except (ProgrammingError, OperationalError) as exc:
        # Table missing (UndefinedTable from postgres) or transient DB
        # error — try the audit-log fallback before giving up.
        logger.info(
            "activity/recent: event_outbox unavailable (%s); trying audit_log",
            type(exc).__name__,
        )
        # A failed statement leaves the asyncpg transaction aborted —
        # every subsequent query raises InFailedSQLTransactionError until
        # we roll back. Do that before the fallback so it actually runs.
        await session.rollback()
        return ActivityResponse(items=await _from_audit_log(session, limit))

    items: List[ActivityItem] = []
    for row in rows:
        try:
            row_id = str(row[0])
            event_type = row[2]
            payload = row[3] or {}
            created_at = row[4]
            if isinstance(created_at, datetime) and created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            items.append(
                ActivityItem(
                    id=row_id,
                    type=_TYPE_MAP.get(event_type, "system"),
                    title=_title_for(event_type, payload),
                    description=_description_for(event_type, payload),
                    timestamp=created_at,
                    status=_STATUS_MAP.get(event_type),
                    link=_link_for(event_type, payload),
                )
            )
        except Exception:
            # One bad row shouldn't kill the feed.
            logger.exception("activity/recent: skipping malformed row")
            continue

    # Q.54.E — outbox present but empty → fall back to the audit log so
    # the feed reflects real factory activity instead of a blank panel.
    if not items:
        items = await _from_audit_log(session, limit)

    return ActivityResponse(items=items)
