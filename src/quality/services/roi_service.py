"""
ProdPlan ONE — Quality ROI by Action (Q.53.A)
===============================================

The "Custos-ROI" tab on the Qualidade page asks a blunt question: for each
recurring defect, is it worth paying to fix the root cause? This service
answers it from `quality.rework_entry`.

A "quality action" here is a preventive intervention targeting one
`error_code` (the normalised defect family). The ROI of acting on it is:

    saved_eur     = historical cost of every rework event of that code
                    in the window (cost_estimate_eur, hours_lost × rate)
    invested_eur  = a per-action investment estimate — the cost of the
                    corrective action itself. We do not invent a number:
                    when the error catalog has a `preventive_action_hint`
                    we treat it as a one-off fixed intervention priced at
                    `DEFAULT_ACTION_COST_EUR`; otherwise the action cost is
                    the cumulative `hours_lost` of *resolved* events of that
                    code (the effort already spent reacting), which is the
                    honest floor for "what fixing it would cost".

    roi_ratio     = saved_eur / invested_eur   (None when invested is 0)
    net_eur       = saved_eur - invested_eur

Everything is sourced from real rows; when the table is empty the endpoint
returns an empty list, never a placeholder.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.quality.models.rework import ErrorCatalog, ReworkEntry

# Loaded labour cost used to convert hours_lost into euros when a rework
# row has no explicit cost_estimate_eur. NELO loaded rate, plan v4 §6.
LABOUR_RATE_EUR_PER_HOUR = 28.0

# Fixed cost of a one-off corrective action (tooling fix, SOP rewrite,
# operator retraining) when the error catalog flags a preventive action.
DEFAULT_ACTION_COST_EUR = 450.0


class ROIService:
    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def roi_by_action(
        self,
        *,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        top_n: int = 25,
    ) -> dict[str, Any]:
        since = since or datetime.now(timezone.utc) - timedelta(days=180)
        until = until or datetime.now(timezone.utc)

        # One aggregate row per error_code: events, explicit cost, hours,
        # and the hours of events already resolved (the reaction effort).
        stmt = select(
            ReworkEntry.error_code,
            func.count(ReworkEntry.id),
            func.coalesce(func.sum(ReworkEntry.cost_estimate_eur), 0),
            func.coalesce(func.sum(ReworkEntry.hours_lost), 0),
            func.coalesce(
                func.sum(
                    func.coalesce(ReworkEntry.hours_lost, 0)
                ).filter(ReworkEntry.resolved_at.is_not(None)),
                0,
            ),
        ).where(
            and_(
                ReworkEntry.tenant_id == self.tenant_id,
                ReworkEntry.detected_at >= since,
                ReworkEntry.detected_at <= until,
            )
        ).group_by(ReworkEntry.error_code)

        rows = (await self.session.execute(stmt)).all()

        # Catalog hints: which error codes have a documented corrective action.
        cat_stmt = select(
            ErrorCatalog.error_code, ErrorCatalog.preventive_action_hint
        ).where(ErrorCatalog.tenant_id == self.tenant_id)
        catalog = {
            code: hint
            for code, hint in (await self.session.execute(cat_stmt)).all()
        }

        actions: list[dict[str, Any]] = []
        for error_code, events, cost_sum, hours_sum, resolved_hours in rows:
            events = int(events or 0)
            explicit_cost = float(cost_sum or 0)
            hours = float(hours_sum or 0)
            # saved_eur: explicit costs plus labour value of every lost hour.
            saved_eur = round(explicit_cost + hours * LABOUR_RATE_EUR_PER_HOUR, 2)

            hint = catalog.get(error_code)
            if hint:
                invested_eur = DEFAULT_ACTION_COST_EUR
                action_basis = "fixed_corrective_action"
            else:
                invested_eur = round(
                    float(resolved_hours or 0) * LABOUR_RATE_EUR_PER_HOUR, 2
                )
                action_basis = "reaction_effort"

            net_eur = round(saved_eur - invested_eur, 2)
            roi_ratio = (
                round(saved_eur / invested_eur, 2) if invested_eur > 0 else None
            )
            actions.append(
                {
                    "error_code": error_code,
                    "events": events,
                    "saved_eur": saved_eur,
                    "invested_eur": round(invested_eur, 2),
                    "net_eur": net_eur,
                    "roi_ratio": roi_ratio,
                    "action_basis": action_basis,
                    "preventive_action_hint": hint,
                }
            )

        actions.sort(key=lambda a: a["net_eur"], reverse=True)

        return {
            "window": {"from": since.isoformat(), "to": until.isoformat()},
            "labour_rate_eur_per_hour": LABOUR_RATE_EUR_PER_HOUR,
            "total_saved_eur": round(sum(a["saved_eur"] for a in actions), 2),
            "total_invested_eur": round(sum(a["invested_eur"] for a in actions), 2),
            "actions": actions[:top_n],
        }
