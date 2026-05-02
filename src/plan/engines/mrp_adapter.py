"""
ProdPlan ONE - MRP Adapter
===========================

Adapter for the legacy MRP engine from base-.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from pydantic import BaseModel, Field


class RequirementSource(str, Enum):
    """Source of material requirement."""
    FORECAST = "forecast"
    CUSTOMER_ORDER = "customer_order"
    SAFETY_STOCK = "safety_stock"
    DEPENDENT_DEMAND = "dependent_demand"


@dataclass
class GrossRequirement:
    """Gross material requirement."""
    item_id: str
    period: datetime
    quantity: Decimal
    source: RequirementSource
    reference_id: Optional[str] = None


@dataclass
class InventoryPosition:
    """Current inventory position."""
    item_id: str
    on_hand: Decimal
    on_order: Decimal = Decimal("0")
    allocated: Decimal = Decimal("0")
    safety_stock: Decimal = Decimal("0")
    
    @property
    def available(self) -> Decimal:
        return self.on_hand + self.on_order - self.allocated


@dataclass
class PlannedOrder:
    """MRP planned order."""
    item_id: str
    quantity: Decimal
    start_date: datetime
    due_date: datetime
    lead_time_days: int
    is_purchase: bool = True
    supplier_id: Optional[str] = None


@dataclass
class MRPItemResult:
    """MRP result for a single item."""
    item_id: str
    periods: List[datetime]
    gross_requirements: List[Decimal]
    scheduled_receipts: List[Decimal]
    projected_on_hand: List[Decimal]
    net_requirements: List[Decimal]
    planned_order_receipts: List[Decimal]
    planned_order_releases: List[Decimal]
    planned_orders: List[PlannedOrder]


class MRPResult(BaseModel):
    """Complete MRP run result."""
    mrp_run_id: str
    status: str = "completed"
    
    items_analyzed: int = 0
    purchase_orders_created: int = 0
    production_orders_created: int = 0
    
    total_po_value: Decimal = Decimal("0")
    currency: str = "EUR"
    
    item_results: List[Dict[str, Any]] = Field(default_factory=list)
    purchase_suggestions: List[Dict[str, Any]] = Field(default_factory=list)
    production_suggestions: List[Dict[str, Any]] = Field(default_factory=list)
    
    warnings: List[str] = Field(default_factory=list)
    
    class Config:
        arbitrary_types_allowed = True


class MRPAdapter:
    """
    Adapter for MRP engine.
    
    Implements standard MRP logic:
    1. Explode BOM
    2. Netting (gross -> net requirements)
    3. Lot sizing
    4. Lead time offsetting
    """
    
    def __init__(
        self,
        planning_horizon_days: int = 90,
        period_days: int = 7,
    ):
        self.planning_horizon_days = planning_horizon_days
        self.period_days = period_days
        
        self._inventory: Dict[str, InventoryPosition] = {}
        self._requirements: Dict[str, List[GrossRequirement]] = {}
        self._lot_sizes: Dict[str, Decimal] = {}
        self._lead_times: Dict[str, int] = {}
        self._is_purchased: Dict[str, bool] = {}
        self._unit_costs: Dict[str, Decimal] = {}
    
    def set_inventory(self, item_id: str, position: InventoryPosition) -> None:
        """Set inventory position for an item."""
        self._inventory[item_id] = position
    
    def add_requirement(self, requirement: GrossRequirement) -> None:
        """Add gross requirement."""
        if requirement.item_id not in self._requirements:
            self._requirements[requirement.item_id] = []
        self._requirements[requirement.item_id].append(requirement)
    
    def set_item_parameters(
        self,
        item_id: str,
        lead_time_days: int = 7,
        lot_size: Optional[Decimal] = None,
        is_purchased: bool = True,
        unit_cost: Decimal = Decimal("0"),
    ) -> None:
        """Set MRP parameters for an item."""
        self._lead_times[item_id] = lead_time_days
        if lot_size:
            self._lot_sizes[item_id] = lot_size
        self._is_purchased[item_id] = is_purchased
        self._unit_costs[item_id] = unit_cost
    
    def _generate_periods(self, start_date: datetime) -> List[datetime]:
        """Generate planning periods."""
        periods = []
        current = start_date
        end_date = start_date + timedelta(days=self.planning_horizon_days)
        
        while current < end_date:
            periods.append(current)
            current += timedelta(days=self.period_days)
        
        return periods
    
    def _aggregate_requirements(
        self,
        item_id: str,
        periods: List[datetime],
    ) -> List[Decimal]:
        """Aggregate gross requirements into periods."""
        reqs = [Decimal("0")] * len(periods)
        
        for req in self._requirements.get(item_id, []):
            for i, period in enumerate(periods):
                period_end = period + timedelta(days=self.period_days)
                if period <= req.period < period_end:
                    reqs[i] += req.quantity
                    break
        
        return reqs
    
    def _calculate_lot_qty(self, item_id: str, net_req: Decimal) -> Decimal:
        """Calculate lot quantity."""
        lot_size = self._lot_sizes.get(item_id)
        
        if lot_size and lot_size > 0:
            # Fixed lot size
            import math
            return Decimal(str(math.ceil(float(net_req / lot_size)))) * lot_size
        
        # Lot-for-lot
        return net_req
    
    def run_mrp_item(
        self,
        item_id: str,
        start_date: datetime = None,
    ) -> MRPItemResult:
        """Run MRP for a single item."""
        start_date = start_date or datetime.now()
        periods = self._generate_periods(start_date)
        n_periods = len(periods)
        
        # Initialize arrays
        gross_reqs = self._aggregate_requirements(item_id, periods)
        scheduled_receipts = [Decimal("0")] * n_periods
        projected_on_hand = [Decimal("0")] * n_periods
        net_reqs = [Decimal("0")] * n_periods
        planned_receipts = [Decimal("0")] * n_periods
        planned_releases = [Decimal("0")] * n_periods
        planned_orders: List[PlannedOrder] = []
        
        # Get inventory and parameters
        inv = self._inventory.get(
            item_id,
            InventoryPosition(item_id, Decimal("0")),
        )
        lead_time = self._lead_times.get(item_id, 7)
        lead_periods = max(1, lead_time // self.period_days)
        is_purchase = self._is_purchased.get(item_id, True)

        # MRP calculation
        # FASE 1A.5 (CRIT-12) — start from actually available stock, not raw
        # on_hand. `inv.allocated` is qty already reserved for other demand
        # (committed but not yet shipped); ignoring it caused MRP to think
        # stock was free, skipping reorders for items already promised
        # elsewhere (e.g. on_hand=100 allocated=80 safety=50 → MRP saw 100
        # and never triggered a PO, even though only 20 are truly free).
        # `inv.on_order` is intentionally NOT subtracted here: open POs
        # already in transit feed `scheduled_receipts[t]` below at their
        # ETA period, so summing them into the starting position would
        # double-count. Mirrors `InventoryPosition.available` semantically.
        prev_poh = inv.on_hand - inv.allocated
        
        for t in range(n_periods):
            # Project on-hand
            poh_before = prev_poh - gross_reqs[t] + scheduled_receipts[t] + planned_receipts[t]
            
            # Net requirements
            net_req = max(Decimal("0"), inv.safety_stock - poh_before)
            net_reqs[t] = net_req
            
            if net_req > 0:
                # Calculate lot quantity
                lot_qty = self._calculate_lot_qty(item_id, net_req)
                planned_receipts[t] = lot_qty
                
                # Offset by lead time
                release_period = t - lead_periods
                if release_period >= 0:
                    planned_releases[release_period] = lot_qty
                
                # Create planned order
                due_date = periods[t]
                order_start = due_date - timedelta(days=lead_time)
                
                planned_orders.append(PlannedOrder(
                    item_id=item_id,
                    quantity=lot_qty,
                    start_date=order_start,
                    due_date=due_date,
                    lead_time_days=lead_time,
                    is_purchase=is_purchase,
                ))
                
                poh_before += lot_qty
            
            projected_on_hand[t] = poh_before
            prev_poh = poh_before
        
        return MRPItemResult(
            item_id=item_id,
            periods=periods,
            gross_requirements=gross_reqs,
            scheduled_receipts=scheduled_receipts,
            projected_on_hand=projected_on_hand,
            net_requirements=net_reqs,
            planned_order_receipts=planned_receipts,
            planned_order_releases=planned_releases,
            planned_orders=planned_orders,
        )
    
    def run_mrp(
        self,
        item_ids: List[str],
        start_date: datetime = None,
    ) -> MRPResult:
        """Run MRP for multiple items."""
        from uuid import uuid4
        
        start_date = start_date or datetime.now()
        mrp_run_id = f"mrp-{uuid4().hex[:8]}"
        
        item_results = []
        purchase_suggestions = []
        production_suggestions = []
        total_po_value = Decimal("0")
        
        for item_id in item_ids:
            result = self.run_mrp_item(item_id, start_date)
            
            item_results.append({
                "item_id": item_id,
                "planned_orders_count": len(result.planned_orders),
                "total_quantity": sum(po.quantity for po in result.planned_orders),
            })
            
            for po in result.planned_orders:
                unit_cost = self._unit_costs.get(item_id, Decimal("0"))
                line_total = po.quantity * unit_cost
                
                suggestion = {
                    "item_id": item_id,
                    "quantity": float(po.quantity),
                    "due_date": po.due_date.isoformat(),
                    "start_date": po.start_date.isoformat(),
                    "lead_time_days": po.lead_time_days,
                    "unit_cost": float(unit_cost),
                    "line_total": float(line_total),
                }
                
                if po.is_purchase:
                    purchase_suggestions.append(suggestion)
                    total_po_value += line_total
                else:
                    production_suggestions.append(suggestion)
        
        return MRPResult(
            mrp_run_id=mrp_run_id,
            status="completed",
            items_analyzed=len(item_ids),
            purchase_orders_created=len(purchase_suggestions),
            production_orders_created=len(production_suggestions),
            total_po_value=total_po_value,
            currency="EUR",
            item_results=item_results,
            purchase_suggestions=purchase_suggestions,
            production_suggestions=production_suggestions,
        )










