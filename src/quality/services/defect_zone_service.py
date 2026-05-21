"""
ProdPlan ONE — Defect Zone Aggregation (Q.53.A)
=================================================

Aggregates `quality.rework_entry` by hull zone for the "Mapa do casco" SVG
on the Qualidade page. Each kayak hull is split into a fixed set of zones
(casco, conves, cockpit, interior, acabamento, molde, montagem, outro); the
SVG shades a zone by its defect count.

The `location_zone` column (migration 055) carries the zone for new rows.
Legacy / un-tagged rows are mapped on the fly with `derive_zone`, the exact
same heuristic the migration backfill uses, so a row that arrived before
the column existed still lands on the right zone.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.quality.models.rework import ReworkEntry

# Canonical hull zones. The frontend SVG references exactly these keys.
HULL_ZONES: tuple[str, ...] = (
    "casco",
    "conves",
    "cockpit",
    "interior",
    "acabamento",
    "molde",
    "montagem",
    "outro",
)


def derive_zone(error_code: Optional[str], phase_name: Optional[str]) -> str:
    """Best-effort hull zone from an error code + checklist phase name.

    Mirrors the SQL backfill in migration 055 so historical rows without a
    persisted `location_zone` map to the same bucket.
    """
    code = (error_code or "").lower()
    if code.startswith(("laminagem", "interior", "gel", "massaresina",
                         "excesso-de-resina")):
        return "casco"
    if code.startswith("pintura"):
        return "acabamento"
    if code.startswith("molde"):
        return "molde"
    if code.startswith("danos"):
        return "conves"
    if code.startswith("falta"):
        return "montagem"

    phase = (phase_name or "").lower()
    if "lamina" in phase:
        return "casco"
    if "pintura" in phase:
        return "acabamento"
    # "desmolde" must be tested before the broader "molde" substring.
    if "desmolde" in phase:
        return "conves"
    if "molde" in phase:
        return "molde"
    if "lixagem" in phase:
        return "acabamento"
    if "montagem" in phase:
        return "montagem"
    return "outro"


class DefectZoneService:
    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def zones(
        self,
        *,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """Defect count + cost per hull zone over the window.

        Always returns every zone in `HULL_ZONES` (count 0 when clean) so
        the SVG can render the full hull without missing-key gaps.
        """
        since = since or datetime.now(timezone.utc) - timedelta(days=90)
        until = until or datetime.now(timezone.utc)

        # Coalesce the persisted zone with the derived one so rows that
        # predate the column still aggregate correctly.
        stmt = select(
            ReworkEntry.location_zone,
            ReworkEntry.error_code,
            ReworkEntry.context,
            ReworkEntry.cost_estimate_eur,
            ReworkEntry.hours_lost,
        ).where(
            and_(
                ReworkEntry.tenant_id == self.tenant_id,
                ReworkEntry.detected_at >= since,
                ReworkEntry.detected_at <= until,
            )
        )
        rows = (await self.session.execute(stmt)).all()

        buckets: dict[str, dict[str, float]] = {
            z: {"events": 0, "cost_eur": 0.0, "hours_lost": 0.0}
            for z in HULL_ZONES
        }
        for location_zone, error_code, context, cost, hours in rows:
            zone = location_zone
            if zone not in buckets:
                phase_name = (context or {}).get("phase_name") if context else None
                zone = derive_zone(error_code, phase_name)
            b = buckets[zone]
            b["events"] += 1
            b["cost_eur"] += float(cost or 0)
            b["hours_lost"] += float(hours or 0)

        total_events = sum(b["events"] for b in buckets.values()) or 1
        items = [
            {
                "zone": zone,
                "events": int(b["events"]),
                "cost_eur": round(b["cost_eur"], 2),
                "hours_lost": round(b["hours_lost"], 2),
                "share_pct": round(100.0 * b["events"] / total_events, 2),
            }
            for zone, b in buckets.items()
        ]
        items.sort(key=lambda d: d["events"], reverse=True)

        return {
            "window": {"from": since.isoformat(), "to": until.isoformat()},
            "total_events": sum(i["events"] for i in items),
            "zones": items,
        }
