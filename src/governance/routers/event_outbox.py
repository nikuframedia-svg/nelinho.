"""Event outbox ledger viewer — Onda 14 N.

Q.67.6.B5 — split from the legacy ``src/governance/api.py``. Reads the
generic event-outbox (``EventOutbox`` rows in :mod:`src.shared.outbox_models`)
so operators can inspect pending/sent/failed events.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session

router = APIRouter(tags=["Governance"])


@router.get("/event-outbox")
async def list_event_outbox(
    status_filter: Optional[str] = None,
    limit: int = 50,
    tenant_id: UUID = Depends(require_tenant_header),
    db: AsyncSession = Depends(get_session),
):
    """Lista eventos do outbox (pending/sent/failed)."""
    from sqlalchemy import select as _sa_select

    from src.shared.outbox_models import EventOutbox

    stmt = _sa_select(EventOutbox).where(EventOutbox.tenant_id == tenant_id)
    if status_filter:
        stmt = stmt.where(EventOutbox.status == status_filter)
    stmt = stmt.order_by(EventOutbox.created_at.desc()).limit(max(1, min(limit, 200)))
    rows = (await db.execute(stmt)).scalars().all()
    return {
        "items": [
            {
                "id": str(r.id),
                "event_type": r.event_type,
                "status": r.status,
                "aggregate_id": str(r.aggregate_id) if getattr(r, "aggregate_id", None) else None,
                "payload_keys": list(r.payload.keys()) if isinstance(r.payload, dict) else [],
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
        "count": len(rows),
    }


__all__ = ["router"]
