"""
ProdPlan ONE - Defect-by-zone hull map (Sub-sprint Q.46.B / F11)
==================================================================

O root-cause de qualidade já analisa defeitos por worker/model/mold/phase
(`RootCauseAnalyzer`), mas nunca pela **zona do casco** onde o defeito foi
marcado. O campo `ReworkEntry.location_zone` (Q.46.A) — populado pelo
mirror a partir de `OFCH_LOCAL` × `PROBS_LOCAL` — torna isso possível.

`DefectZoneService.zone_map` faz o rollup factory-wide de retrabalho por
zona: um mapa de calor / Pareto que responde "onde no barco a fábrica
falha", não só "quanto". Eventos sem zona marcada (`location_zone` NULL)
contam para `events_without_zone` — o sinal de honestidade: se a cobertura
é baixa, o Pareto é parcial, não um facto.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.quality.models.rework import ReworkEntry


class DefectZoneService:
    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def zone_map(
        self,
        *,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        top_n: int = 25,
    ) -> dict[str, Any]:
        """Heatmap / Pareto de retrabalho por zona do casco.

        Para cada zona: nº de eventos, custo € e horas perdidas, ordens
        afectadas, e a quota cumulativa do Pareto. As zonas vêm ordenadas
        por nº de eventos (a zona que mais falha primeiro).
        """
        since = since or datetime.now(timezone.utc) - timedelta(days=90)
        until = until or datetime.now(timezone.utc)

        stmt = select(ReworkEntry).where(
            and_(
                ReworkEntry.tenant_id == self.tenant_id,
                ReworkEntry.detected_at >= since,
                ReworkEntry.detected_at <= until,
            )
        )
        rows = list((await self.session.execute(stmt)).scalars().all())

        total_events = len(rows)
        events_with_zone = sum(1 for r in rows if r.location_zone)

        # Agregação por zona — eventos sem zona não entram no breakdown
        # (contam para `events_without_zone`).
        buckets: dict[str, dict[str, Any]] = {}
        for row in rows:
            zone = row.location_zone
            if not zone:
                continue
            b = buckets.setdefault(
                zone,
                {"events": 0, "cost_estimate_eur": Decimal("0"),
                 "hours_lost": Decimal("0"), "_orders": set()},
            )
            b["events"] += 1
            if row.cost_estimate_eur is not None:
                b["cost_estimate_eur"] += Decimal(str(row.cost_estimate_eur))
            if row.hours_lost is not None:
                b["hours_lost"] += Decimal(str(row.hours_lost))
            if row.of_id:
                b["_orders"].add(row.of_id)

        # Ordena por nº de eventos descendente — a zona que mais falha
        # primeiro — e calcula a quota cumulativa do Pareto.
        ordered = sorted(
            buckets.items(), key=lambda kv: kv[1]["events"], reverse=True,
        )
        zoned_events = events_with_zone or 1
        cumulative = 0
        zones: list[dict[str, Any]] = []
        for zone, b in ordered:
            cumulative += b["events"]
            zones.append({
                "zone": zone,
                "events": b["events"],
                "share_pct": round(100.0 * b["events"] / zoned_events, 2),
                "cumulative_pct": round(100.0 * cumulative / zoned_events, 2),
                "cost_estimate_eur": float(b["cost_estimate_eur"]),
                "hours_lost": float(b["hours_lost"]),
                "affected_orders": len(b["_orders"]),
            })

        coverage = (
            round(100.0 * events_with_zone / total_events, 2)
            if total_events else 0.0
        )

        return {
            "window": {"from": since.isoformat(), "to": until.isoformat()},
            "total_events": total_events,
            "events_with_zone": events_with_zone,
            "events_without_zone": total_events - events_with_zone,
            "zone_coverage_pct": coverage,
            "distinct_zones": len(zones),
            "zones": zones[: max(1, top_n)],
        }
