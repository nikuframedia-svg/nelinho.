"""Per-boat trajectory + forward projection for `FactoryMapService`.

Holds `TrajectoryMixin`:
* `boat_view()` — one order's full curated trajectory + LATE_VS_TRANSPORT /
  AT_RISK_VS_TRANSPORT risk flags.
* `projection()` — 7-day load heatmap extrapolated from historical median
  durations per phase (does NOT call the CPO engine).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.factory_data_product.services.factory_map.risk_flags import RiskFlag


class TrajectoryMixin:
    """`FactoryMapService` boat_view + projection methods."""

    session: AsyncSession
    tenant_id: UUID

    # ─── N.2 Per-boat view ────────────────────────────────────────────────

    async def boat_view(self, *, of_id: str) -> Optional[dict[str, Any]]:
        """Fetch the trajectory of a single order.

        Returns None when the order isn't in our tenant scope.
        """
        # Lazy imports so a non-schedule request never pulls plan deps.
        from src.plan.models.order import OrderStatus, ProductionOrder
        from src.factory_data_product.models.curated import CuratedOrderPhase

        legacy_id: Optional[int] = None
        try:
            legacy_id = int(of_id)
        except ValueError:
            pass

        conditions = [ProductionOrder.tenant_id == self.tenant_id]
        if legacy_id is not None:
            conditions.append(ProductionOrder.legacy_id == legacy_id)
        else:
            # Fall back to product_name exact match if of_id is non-numeric.
            conditions.append(ProductionOrder.product_name == of_id)

        order_row = (
            await self.session.execute(
                select(ProductionOrder).where(and_(*conditions)).limit(1)
            )
        ).scalar_one_or_none()
        if order_row is None:
            return None

        # Curated trajectory (may be empty if no curated ingest has happened).
        traj_rows = list(
            (
                await self.session.execute(
                    select(CuratedOrderPhase)
                    .where(CuratedOrderPhase.of_id == str(order_row.legacy_id))
                    .order_by(CuratedOrderPhase.ordem)
                )
            ).scalars().all()
        )

        trajectory = [
            {
                "phase_id": p.fase_id,
                "phase_name": p.fase_nome,
                "seq": p.ordem,
                "start": p.data_inicio.isoformat() if p.data_inicio else None,
                "end": p.data_fim.isoformat() if p.data_fim else None,
                "horas_reais": float(p.horas_reais) if p.horas_reais is not None else None,
                "horas_previstas": float(p.horas_previstas) if p.horas_previstas is not None else None,
                "estado": p.estado,
                "mold_id": p.molde_id,
            }
            for p in traj_rows
        ]

        # Risk flags
        flags: list[RiskFlag] = []
        if order_row.transport_date and order_row.completed_date is None:
            days_to_transport = (order_row.transport_date - date.today()).days
            if days_to_transport < 0:
                flags.append(RiskFlag(
                    code="LATE_VS_TRANSPORT",
                    severity="HIGH",
                    message=f"Transport date {days_to_transport*-1}d in the past and boat still in production",
                    evidence={"days_overdue": -days_to_transport},
                ))
            elif days_to_transport <= 3 and (
                not trajectory or any(t["end"] is None for t in trajectory)
            ):
                flags.append(RiskFlag(
                    code="AT_RISK_VS_TRANSPORT",
                    severity="MED",
                    message=f"Transport in {days_to_transport}d, open phases remain",
                    evidence={"days_to_transport": days_to_transport},
                ))

        return {
            "of_id": str(order_row.legacy_id),
            "product_name": order_row.product_name,
            "product_type": order_row.product_type,
            "current_phase": order_row.current_phase_name,
            "status": order_row.status if isinstance(order_row.status, str) else order_row.status.value,
            "created_date": order_row.created_date.isoformat() if order_row.created_date else None,
            "completed_date": order_row.completed_date.isoformat() if order_row.completed_date else None,
            "transport_date": order_row.transport_date.isoformat() if order_row.transport_date else None,
            "trajectory": trajectory,
            "risk_flags": [
                {"code": f.code, "severity": f.severity, "message": f.message, "evidence": f.evidence}
                for f in flags
            ],
        }

    # ─── N.3 Projection ───────────────────────────────────────────────────

    async def projection(self, *, days_ahead: int = 7) -> dict[str, Any]:
        """Lightweight forward heatmap.

        Takes every currently open ProductionOrder, walks its **remaining**
        phases using historical median durations per (model_id, phase_id),
        and buckets projected load into daily slots up to `days_ahead`.

        This intentionally does NOT call `CPOv4Engine.schedule()` — that
        path is multi-second and blocked on Sprint P. An honest "based on
        historical averages" view is cheaper and sufficient for the UI
        until the full CPO cascade lands.
        """
        from src.factory_data_product.models.curated import CuratedOrderPhase
        from src.plan.models.order import OrderStatus, ProductionOrder

        # Historical median duration per phase (1 round-trip).
        hist_stmt = (
            select(
                CuratedOrderPhase.fase_id,
                func.avg(CuratedOrderPhase.horas_reais).label("avg_h"),
                func.count(CuratedOrderPhase.id).label("sample"),
            )
            .where(CuratedOrderPhase.horas_reais.is_not(None))
            .group_by(CuratedOrderPhase.fase_id)
        )
        hist_rows = (await self.session.execute(hist_stmt)).all()
        median_h = {r[0]: float(r[1] or 0) for r in hist_rows if r[1] is not None}

        # Open orders
        open_orders = list(
            (
                await self.session.execute(
                    select(ProductionOrder).where(
                        and_(
                            ProductionOrder.tenant_id == self.tenant_id,
                            ProductionOrder.completed_date.is_(None),
                        )
                    )
                )
            ).scalars().all()
        )

        # Build heatmap: phase × day → projected load hours
        today = date.today()
        heatmap: dict[tuple[str, str], float] = {}
        for order in open_orders:
            current_phase = order.current_phase_name or "?"
            # For MVP we attribute the whole remaining work to the current
            # phase over the next N working days, spread linearly. Refining
            # with a full routing walk is Sprint P territory.
            duration_h = median_h.get(current_phase, 8.0)
            days_for_order = max(1, min(days_ahead, int(duration_h // 8) + 1))
            for d in range(days_for_order):
                day = today + timedelta(days=d)
                heatmap[(current_phase, day.isoformat())] = (
                    heatmap.get((current_phase, day.isoformat()), 0.0)
                    + duration_h / days_for_order
                )

        points = [
            {"phase_id": p, "date": d, "load_hours": round(h, 2)}
            for (p, d), h in sorted(heatmap.items(), key=lambda kv: (kv[0][1], kv[0][0]))
        ]
        return {
            "method": "historical_avg_durations",
            "days_ahead": days_ahead,
            "sample_size_per_phase": {
                r[0]: int(r[2]) for r in hist_rows if r[2] is not None
            },
            "open_orders_projected": len(open_orders),
            "points": points,
        }
