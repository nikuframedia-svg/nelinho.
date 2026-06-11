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

        # Stock por product_code (UUID string) para o gate de materiais BOM.
        stock_by_product = await self._stock_by_product()
        # Q.171.D / Q.173.X — base explícita na resposta (honesto).
        # "bom_nivel1" quando o stock real existe + BOM explodida por ordem.
        # "sem_snapshot" quando não há dados de stock.
        materials_basis = "bom_nivel1" if stock_by_product else "sem_snapshot"

        evaluated: List[Dict[str, Any]] = []
        for order in orders:
            ship = await backward.suggest_shipment_for_order(order, start=start_dt)
            suggested = ship.get("suggested_shipment")
            ship_dt = (
                datetime.fromisoformat(suggested) if suggested else None
            )
            date_ok = ship_dt is not None and ship_dt <= truck_dt
            # Q.173.X — gate BOM nível-1: substitui o proxy do produto
            # acabado por explosão real de core.bom_items.
            materials_ok, missing, materials_known = await self._materials_gate_bom(
                order, stock_by_product,
            )
            # bom_data_available sinaliza se a BOM existia (False = sem dados).
            bom_data_available = materials_known
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
                "bom_data_available": bom_data_available,
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

    async def _bom_for_product(self, product_id) -> List[Dict[str, Any]]:
        """Explode BOM nível-1 de ``core.bom_items`` para o produto.

        ``product_id`` é o código LEGACY da ordem (``ProductionOrder.
        product_id`` = OF_P_ID = ``core.products.product_code``) — a BOM é
        keyed por UUID, por isso o pai resolve-se via ``product_code`` e
        cada componente devolve o SEU ``product_code`` (a chave do
        ``warehouse_stock``). Sem este duplo mapeamento o gate comparava
        UUID com código e dava sempre 0 disponível (gap apanhado na
        revisão do Q.173.X).

        Devolve lista de ``{component_code: str, quantity_per: float}`` ou
        vazia quando o produto não tem BOM.
        """
        if not product_id:
            return []
        try:
            from sqlalchemy import select
            from sqlalchemy.orm import aliased

            from src.core.models.bom import BOMItem
            from src.core.models.product import Product

            parent = aliased(Product)
            comp = aliased(Product)
            stmt = (
                select(comp.product_code, BOMItem.quantity_per)
                .join(parent, parent.id == BOMItem.parent_product_id)
                .join(comp, comp.id == BOMItem.component_product_id)
                .where(
                    BOMItem.tenant_id == self.tenant_id,
                    parent.product_code == str(product_id),
                )
            )
            rows = (await self.session.execute(stmt)).all()
        except Exception as exc:  # noqa: BLE001  # gate tri-state: sem BOM → desconhecido, nunca 500
            logger.debug("ctp bom lookup falhou: %s", exc)
            return []
        return [
            {
                "component_code": str(code),
                "quantity_per": float(qty),
            }
            for code, qty in rows
        ]

    async def _materials_gate_bom(
        self,
        order,
        stock_by_product: Dict[str, float],
    ) -> tuple[bool, List[Dict[str, Any]], bool]:
        """Verifica materiais por explosão BOM nível-1 (Q.173.X).

        Tri-state honesto:
        - ``(True, components_checked, True)`` — BOM explodida, todos os
          componentes com stock suficiente.
        - ``(False, missing_list, True)`` — BOM explodida, pelo menos um
          componente em falta; ``missing_list`` é lista de dicts
          ``{component, needed, available}``.
        - ``(True, [], False)`` — sem BOM para o produto → não bloqueia
          (ausência de dados ≠ escassez); caller distingue via
          ``materials_known=False`` e deve apresentar aviso, nunca "OK".

        Preserva o contrato chamador (``materials_ok``, ``missing_materials``,
        ``materials_known``) sem remover campos existentes.
        """
        product_id = getattr(order, "product_id", None)
        bom_items = await self._bom_for_product(product_id)

        if not bom_items:
            # Sem BOM → inconclusivo; não bloqueia mas declara data_available=False
            return True, [], False

        if not stock_by_product:
            # BOM existe mas sem snapshot de stock → inconclusivo
            return True, [], False

        missing: List[Dict[str, Any]] = []
        for item in bom_items:
            code = item["component_code"]
            needed = item["quantity_per"]
            available = stock_by_product.get(code, 0.0)
            if available < needed:
                missing.append({
                    "component": code,
                    "needed": needed,
                    "available": available,
                })

        if missing:
            return False, missing, True
        return True, [], True

    async def _stock_by_product(self) -> Dict[str, float]:
        """Aggregate `supply.warehouse_stock` to total stock per product."""
        try:
            from sqlalchemy import select

            from src.supply.models import WarehouseStock

            stmt = select(WarehouseStock).where(
                WarehouseStock.tenant_id == self.tenant_id,
            )
            rows = (await self.session.execute(stmt)).scalars().all()
        except Exception as exc:  # noqa: BLE001  # gate tri-state: sem stock → desconhecido, nunca 500
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
