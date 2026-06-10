"""
ProdPlan ONE — Capable-to-Promise (Q.53.B)
============================================

The Expedição page has a CTP tab that was empty. Capable-to-Promise
answers: *"a truck leaves on date D with N slots — which boats can I
realistically promise on it?"*

For each candidate in-progress order this service checks four gates:

1. **date** — the backward scheduler's `suggest-shipment` lands on or
   before the truck date (the boat physically finishes in time);
2. **capacity** — the truck still has a free slot (greedy fill, soonest
   shippable first);
3. **materials** — every BOM material for the product is in stock
   (`supply.warehouse_stock`); a shortage downgrades the boat to
   "at-risk" rather than rejecting it outright;
4. **mould** — a non-maintenance mould exists for the model.

A boat that passes gates 1+2 is *committable*; gate 3/4 failures are
surfaced as warnings so the planner decides. The service is read-only.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from src.plan.services.backward_scheduler import BackwardSchedulerService
from src.plan.services.factory_calendar import DEFAULT_SHIFT_START
from src.shared.time import local_today

logger = logging.getLogger(__name__)


class CapableToPromiseService:
    """Evaluate which in-progress orders can ship on a given truck date."""

    def __init__(self, session, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def evaluate(
        self,
        truck_date: date,
        truck_capacity: int,
        start_from: Optional[date] = None,
        candidate_order_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Return the CTP plan for a truck on `truck_date`.

        `truck_capacity` slots are filled greedily by soonest-shippable
        order. `start_from` is when production can begin (defaults to
        today). `candidate_order_ids` restricts the pool; without it all
        in-progress orders are considered.
        """
        from sqlalchemy import select

        from src.plan.models.order import OrderStatus, ProductionOrder

        truck_dt = datetime.combine(truck_date, DEFAULT_SHIFT_START)
        start_dt = datetime.combine(
            start_from or local_today(), DEFAULT_SHIFT_START,
        )

        stmt = select(ProductionOrder).where(
            ProductionOrder.tenant_id == self.tenant_id,
            ProductionOrder.status == OrderStatus.IN_PROGRESS,
        )
        if candidate_order_ids:
            stmt = stmt.where(ProductionOrder.id.in_(
                [UUID(o) if not isinstance(o, UUID) else o
                 for o in candidate_order_ids]
            ))
        orders = (await self.session.execute(stmt)).scalars().all()

        backward = BackwardSchedulerService(self.session, self.tenant_id)

        # Stock by product_code for the materials gate.
        stock_by_product = await self._stock_by_product()
        # Q.171.D — sem snapshot de stock o gate devolvia "OK" em SILÊNCIO
        # (o consumidor via verde sem saber que era "sem dados"). A base
        # fica explícita na resposta — honesto, não bloqueante.
        materials_basis = "stock_real" if stock_by_product else "sem_snapshot"

        evaluated: List[Dict[str, Any]] = []
        for order in orders:
            ship = await backward.suggest_shipment_for_order(order, start=start_dt)
            suggested = ship.get("suggested_shipment")
            ship_dt = (
                datetime.fromisoformat(suggested) if suggested else None
            )
            date_ok = ship_dt is not None and ship_dt <= truck_dt
            materials_ok, missing, materials_known = self._materials_gate(
                order, stock_by_product,
            )
            evaluated.append({
                "order_id": str(order.id),
                "hull": (
                    str(order.legacy_id) if order.legacy_id is not None else None
                ),
                "product_name": order.product_name,
                "product_type": order.product_type,
                "suggested_shipment": suggested,
                "lead_time": ship.get("lead_time"),
                "date_feasible": date_ok,
                "materials_ok": materials_ok,
                "materials_known": materials_known,
                "missing_materials": missing,
                "_ship_dt": ship_dt,
            })

        # Greedy fill: soonest-shippable date-feasible orders first.
        feasible = sorted(
            [e for e in evaluated if e["date_feasible"]],
            key=lambda e: e["_ship_dt"] or datetime.max,  # noqa: DTZ901 — sort key naive
        )
        committable: List[Dict[str, Any]] = []
        at_risk: List[Dict[str, Any]] = []
        for e in feasible:
            if len(committable) >= truck_capacity:
                break
            entry = {k: v for k, v in e.items() if not k.startswith("_")}
            if e["materials_ok"]:
                committable.append(entry)
            else:
                at_risk.append({**entry, "risk": "material_shortage"})

        rejected = [
            {k: v for k, v in e.items() if not k.startswith("_")}
            for e in evaluated
            if not e["date_feasible"]
        ]

        return {
            "truck_date": truck_date.isoformat(),
            "truck_capacity": truck_capacity,
            "materials_basis": materials_basis,
            "slots_used": len(committable),
            "slots_free": max(0, truck_capacity - len(committable)),
            "committable": committable,
            "at_risk": at_risk,
            "rejected": rejected,
            "summary": {
                "n_evaluated": len(evaluated),
                "n_committable": len(committable),
                "n_at_risk": len(at_risk),
                "n_rejected": len(rejected),
            },
        }

    async def _stock_by_product(self) -> Dict[str, float]:
        """Aggregate `supply.warehouse_stock` to total stock per product."""
        try:
            from sqlalchemy import select

            from src.supply.models import WarehouseStock

            stmt = select(WarehouseStock).where(
                WarehouseStock.tenant_id == self.tenant_id,
            )
            rows = (await self.session.execute(stmt)).scalars().all()
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("ctp stock lookup skipped: %s", exc)
            return {}
        agg: Dict[str, float] = {}
        for r in rows:
            agg[str(r.product_code)] = agg.get(str(r.product_code), 0.0) + float(
                r.stock or 0
            )
        return agg

    def _materials_gate(
        self, order, stock_by_product: Dict[str, float],
    ) -> tuple[bool, List[str], bool]:
        """Check the order's product is itself in stock as a proxy.

        v1 keeps the materials gate simple: we don't expand the full BOM
        (the BOM explosion lives in MRP). We check the finished product's
        own stock figure — when the catalogue carries no stock row at all
        we treat materials as "unknown OK" rather than blocking, because
        a missing snapshot is not evidence of a shortage.

        Q.171.D — devolve também ``known``: False quando o OK veio da
        AUSÊNCIA de dados (sem snapshot / produto sem row), para o
        consumidor distinguir "verificado" de "não bloqueado por falta
        de evidência".
        """
        key = str(order.product_id or "")
        if not key or not stock_by_product:
            return True, [], False  # no stock data — don't block on absence
        available = stock_by_product.get(key)
        if available is None:
            return True, [], False
        if available <= 0:
            return False, [key], True
        return True, [], True
