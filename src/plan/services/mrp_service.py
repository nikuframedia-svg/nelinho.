"""
ProdPlan ONE - MRP Service
===========================

Business logic for Material Requirements Planning.
"""

import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.governance.audit_service import audit_change
from src.plan.models.mrp import MaterialRequirement, PurchaseOrder, POStatus
from src.plan.engines.mrp_adapter import MRPAdapter, GrossRequirement, InventoryPosition, RequirementSource
from src.plan.engines.bom_adapter import BOMAdapter
from src.shared.kafka_client import publish_event, Topics
from src.shared.events import MRPCalculatedEvent, PurchaseOrderCreatedEvent
from src.shared.time import local_today

logger = logging.getLogger(__name__)


class MRPService:
    """
    Service for Material Requirements Planning.
    
    Coordinates BOM explosion, inventory netting, and PO generation.
    """
    
    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id
        self._mrp_adapter = MRPAdapter()
        self._bom_adapter = BOMAdapter()
    
    async def _inventory_from_warehouse(self) -> Dict[str, Dict[str, Any]]:
        """Snapshot real de stock por product_code (Q.171.D). Best-effort:
        sem mirror → {} e o resultado declara inventory_source honesto."""
        try:
            from sqlalchemy import select

            from src.supply.models import WarehouseStock

            stmt = select(WarehouseStock).where(
                WarehouseStock.tenant_id == self.tenant_id,
            )
            rows = (await self.session.execute(stmt)).scalars().all()
        except Exception as exc:  # pragma: no cover — defensivo
            logger.warning(
                "MRP: warehouse_stock indisponível (%s) — inventário vazio", exc,
            )
            return {}
        agg: Dict[str, float] = {}
        for r in rows:
            code = str(r.product_code)
            agg[code] = agg.get(code, 0.0) + float(r.stock or 0)
        return {code: {"on_hand": qty} for code, qty in agg.items()}

    async def run_mrp(
        self,
        orders: List[Dict[str, Any]],
        inventory: Dict[str, Dict[str, Any]] = None,
        bom_data: Dict[str, Any] = None,
        planning_horizon_weeks: int = 12,
        include_safety_stock: bool = True,
    ) -> Dict[str, Any]:
        """
        Run MRP for a set of orders.
        
        Args:
            orders: List of orders with product_id, quantity, due_date
            inventory: Current inventory positions by item
            bom_data: BOM structure (items and components)
            planning_horizon_weeks: Planning horizon
            include_safety_stock: Include safety stock in requirements
        
        Returns:
            MRP results with purchase and production suggestions
        """
        mrp_run_id = f"mrp-{uuid4().hex[:8]}"
        # Q.171.D — o MRP corria SEMPRE com inventário {} (netting cego:
        # sugeria compras como se a fábrica não tivesse stock nenhum). Sem
        # inventário do caller, lê o snapshot REAL supply.warehouse_stock
        # (mirror ERP Q.52.K) agregado por product_code.
        inventory_source = "caller"
        if not inventory:
            inventory = await self._inventory_from_warehouse()
            inventory_source = (
                "warehouse_stock" if inventory else "vazio_sem_snapshot"
            )
        
        # Configure MRP adapter
        self._mrp_adapter.planning_horizon_days = planning_horizon_weeks * 7
        
        # Load BOM if provided
        if bom_data:
            self._bom_adapter.load_from_data(
                items=bom_data.get("items", []),
                components=bom_data.get("components", []),
            )
        
        # Explode BOMs and collect all requirements
        all_items = set()
        
        for order in orders:
            product_id = str(order.get("product_id", ""))
            quantity = Decimal(str(order.get("quantity", 0)))
            due_date = order.get("due_date")
            
            if isinstance(due_date, str):
                due_date = datetime.fromisoformat(due_date.replace("Z", "+00:00"))
            elif isinstance(due_date, date):
                due_date = datetime.combine(due_date, datetime.min.time())
            
            # Explode BOM
            requirements = self._bom_adapter.explode(product_id, quantity)
            
            for req in requirements:
                all_items.add(req.component_id)
                
                # Add gross requirement
                self._mrp_adapter.add_requirement(GrossRequirement(
                    item_id=req.component_id,
                    period=due_date - timedelta(days=req.cumulative_lead_time),
                    quantity=req.required_qty,
                    source=RequirementSource.CUSTOMER_ORDER,
                    reference_id=str(order.get("order_id", "")),
                ))
        
        # Set inventory positions
        for item_id, inv_data in inventory.items():
            self._mrp_adapter.set_inventory(
                item_id,
                InventoryPosition(
                    item_id=item_id,
                    on_hand=Decimal(str(inv_data.get("on_hand", 0))),
                    on_order=Decimal(str(inv_data.get("on_order", 0))),
                    allocated=Decimal(str(inv_data.get("allocated", 0))),
                    safety_stock=Decimal(str(inv_data.get("safety_stock", 0))) if include_safety_stock else Decimal("0"),
                ),
            )
        
        # Run MRP
        result = self._mrp_adapter.run_mrp(list(all_items))
        
        # Save requirements to database
        for suggestion in result.purchase_suggestions:
            requirement = MaterialRequirement(
                id=uuid4(),
                tenant_id=self.tenant_id,
                mrp_run_id=mrp_run_id,
                material_id=UUID(suggestion["item_id"]) if self._is_uuid(suggestion["item_id"]) else None,
                gross_requirement=Decimal(str(suggestion.get("quantity", 0))),
                net_requirement=Decimal(str(suggestion.get("quantity", 0))),
                order_quantity=Decimal(str(suggestion.get("quantity", 0))),
                lead_time_days=int(suggestion.get("lead_time_days", 0)),
                order_date=date.fromisoformat(suggestion["start_date"][:10]) if suggestion.get("start_date") else local_today(),
                due_date=date.fromisoformat(suggestion["due_date"][:10]) if suggestion.get("due_date") else local_today(),
                is_purchased=True,
            )
            self.session.add(requirement)
            await audit_change(
                self.session,
                tenant_id=self.tenant_id,
                entity_type="material_requirement",
                entity_id=requirement.id,
                action="INSERT",
                old_values=None,
                new_values={
                    "mrp_run_id": mrp_run_id,
                    "material_id": str(requirement.material_id) if requirement.material_id else None,
                    "net_requirement": float(requirement.net_requirement or 0),
                    "order_date": requirement.order_date.isoformat() if requirement.order_date else None,
                    "due_date": requirement.due_date.isoformat() if requirement.due_date else None,
                },
                reason="Q.66.B.3 — requisito de material planeado pelo MRP",
            )

        await self.session.flush()

        # Publish event — best-effort: Kafka em baixo não pode falhar o MRP
        # (Q.171.D; o bloco MATERIAL_REQUIREMENT_PLANNED abaixo já era assim).
        try:
            await publish_event(
                Topics.MRP_CALCULATED,
                MRPCalculatedEvent(
                    tenant_id=self.tenant_id,
                    payload={
                        "mrp_run_id": mrp_run_id,
                        "materials_analyzed": result.items_analyzed,
                        "purchase_orders_created": result.purchase_orders_created,
                        "total_po_value": float(result.total_po_value),
                        "currency": result.currency,
                    },
                ),
            )
        except Exception as exc:
            logger.warning("MRP_CALCULATED publish failed: %s", exc)

        # Per-material drill-down. Consumers filtering on MRP_CALCULATED get
        # the aggregate; UIs that want to show a list (shortage feed,
        # procurement inbox) subscribe to MATERIAL_REQUIREMENT_PLANNED and
        # read the `requirements` list. One batch envelope instead of N
        # individual events avoids flooding the bus on large BOM explosions.
        try:
            from src.shared.kafka_client import EventBase as _EventBase

            await publish_event(
                Topics.MATERIAL_REQUIREMENT_PLANNED,
                _EventBase(
                    event_type="MATERIAL_REQUIREMENT_PLANNED",
                    tenant_id=self.tenant_id,
                    source_module="plan",
                    payload={
                        "mrp_run_id": mrp_run_id,
                        "requirements": [
                            {
                                "item_id": s.get("item_id"),
                                "quantity": float(s.get("quantity", 0)),
                                "lead_time_days": int(s.get("lead_time_days", 0)),
                                "order_date": s.get("start_date"),
                                "due_date": s.get("due_date"),
                                "unit_cost": float(s.get("unit_cost", 0)),
                            }
                            for s in result.purchase_suggestions
                        ],
                        "count": len(result.purchase_suggestions),
                    },
                ),
            )
        except Exception as exc:  # pragma: no cover — best-effort
            logger.warning("MATERIAL_REQUIREMENT_PLANNED publish failed: %s", exc)
        
        return {
            "mrp_run_id": mrp_run_id,
            "status": "completed",
            # Q.171.D — base de inventário honesta: "caller" (fornecido),
            # "warehouse_stock" (snapshot ERP) ou "vazio_sem_snapshot".
            "inventory_source": inventory_source,
            "items_analyzed": result.items_analyzed,
            "purchase_orders": result.purchase_orders_created,
            "production_orders": result.production_orders_created,
            "total_po_value": float(result.total_po_value),
            "currency": result.currency,
            "purchase_suggestions": result.purchase_suggestions,
            "production_suggestions": result.production_suggestions,
            "warnings": result.warnings,
        }
    
    async def create_purchase_orders(
        self,
        mrp_run_id: str,
        suggestions: List[Dict[str, Any]],
    ) -> List[PurchaseOrder]:
        """Create purchase orders from MRP suggestions."""
        created_pos = []
        po_sequence = 1
        
        for suggestion in suggestions:
            po_number = f"PO-{datetime.now().strftime('%Y%m%d')}-{po_sequence:04d}"
            
            po = PurchaseOrder(
                id=uuid4(),
                tenant_id=self.tenant_id,
                po_number=po_number,
                supplier_id=UUID(suggestion["supplier_id"]) if suggestion.get("supplier_id") else None,
                material_id=UUID(suggestion["item_id"]) if self._is_uuid(suggestion.get("item_id", "")) else None,
                order_quantity=Decimal(str(suggestion.get("quantity", 0))),
                unit_cost=Decimal(str(suggestion.get("unit_cost", 0))),
                total_cost=Decimal(str(suggestion.get("line_total", 0))),
                order_date=date.fromisoformat(suggestion["start_date"][:10]) if suggestion.get("start_date") else local_today(),
                due_date=date.fromisoformat(suggestion["due_date"][:10]) if suggestion.get("due_date") else local_today(),
                status=POStatus.DRAFT,
                mrp_run_id=mrp_run_id,
            )

            self.session.add(po)
            await audit_change(
                self.session,
                tenant_id=self.tenant_id,
                entity_type="purchase_order",
                entity_id=po.id,
                action="INSERT",
                old_values=None,
                new_values={
                    "po_number": po_number,
                    "supplier_id": str(po.supplier_id) if po.supplier_id else None,
                    "material_id": str(po.material_id) if po.material_id else None,
                    "order_quantity": float(po.order_quantity or 0),
                    "total_cost": float(po.total_cost or 0),
                    "status": POStatus.DRAFT.value,
                    "mrp_run_id": mrp_run_id,
                },
                reason="Q.66.B.3 — purchase order criada (DRAFT)",
            )
            created_pos.append(po)
            
            # Publish event
            await publish_event(
                Topics.PURCHASE_ORDER_CREATED,
                PurchaseOrderCreatedEvent(
                    tenant_id=self.tenant_id,
                    payload={
                        "po_id": str(po.id),
                        "po_number": po_number,
                        "material_id": suggestion.get("item_id"),
                        "quantity": suggestion.get("quantity", 0),
                        "total_value": suggestion.get("line_total", 0),
                        "due_date": suggestion.get("due_date", ""),
                    },
                ),
            )
            
            po_sequence += 1
        
        await self.session.flush()
        return created_pos
    
    async def get_requirements(
        self,
        mrp_run_id: str = None,
        material_id: UUID = None,
    ) -> List[MaterialRequirement]:
        """Get material requirements."""
        query = select(MaterialRequirement).where(
            MaterialRequirement.tenant_id == self.tenant_id
        )
        
        if mrp_run_id:
            query = query.where(MaterialRequirement.mrp_run_id == mrp_run_id)
        if material_id:
            query = query.where(MaterialRequirement.material_id == material_id)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    def _is_uuid(self, value: str) -> bool:
        """Check if string is valid UUID."""
        try:
            UUID(value)
            return True
        except (ValueError, TypeError):
            return False










