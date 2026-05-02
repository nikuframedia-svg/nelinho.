"""
ProdPlan ONE - BOM Adapter
===========================

Adapter for BOM explosion from base-.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Set


class BOMCycleError(ValueError):
    """Raised when BOM explosion detects a cycle in the parent→child graph.

    The ``path`` attribute is the ancestor chain that closed the cycle,
    e.g. ``['A', 'B', 'C', 'A']`` when ``A`` reappears after ``A→B→C``.
    """

    def __init__(self, path: List[str]):
        self.path = path
        super().__init__(f"BOM cycle detected: {' -> '.join(path)}")


class BOMItemType(str, Enum):
    """BOM item type."""
    FINISHED_GOOD = "finished_good"
    SEMI_FINISHED = "semi_finished"
    RAW_MATERIAL = "raw_material"
    PACKAGING = "packaging"


@dataclass
class BOMComponent:
    """Component in BOM."""
    parent_id: str
    component_id: str
    quantity_per: Decimal
    sequence: int = 0
    scrap_factor: Decimal = Decimal("1.0")


@dataclass
class BOMItem:
    """Item master data."""
    item_id: str
    name: str
    item_type: BOMItemType = BOMItemType.RAW_MATERIAL
    lead_time_days: int = 0
    cost_per_unit: Decimal = Decimal("0")


@dataclass
class ExplodedRequirement:
    """Result of BOM explosion."""
    component_id: str
    component_name: str
    required_qty: Decimal
    level: int
    parent_id: Optional[str] = None
    lead_time_days: int = 0
    cumulative_lead_time: int = 0
    is_purchased: bool = True


class BOMAdapter:
    """
    Adapter for BOM explosion.
    
    Handles multi-level BOM structure and component requirements.
    """
    
    def __init__(self):
        self._items: Dict[str, BOMItem] = {}
        self._components: List[BOMComponent] = []
        self._parent_map: Dict[str, List[BOMComponent]] = {}
    
    def add_item(self, item: BOMItem) -> None:
        """Add item to master data."""
        self._items[item.item_id] = item
    
    def add_component(self, component: BOMComponent) -> None:
        """Add BOM component relationship."""
        self._components.append(component)
        
        if component.parent_id not in self._parent_map:
            self._parent_map[component.parent_id] = []
        self._parent_map[component.parent_id].append(component)
    
    def load_from_data(
        self,
        items: List[Dict],
        components: List[Dict],
    ) -> None:
        """Load BOM from dictionaries."""
        for item_data in items:
            item = BOMItem(
                item_id=str(item_data["item_id"]),
                name=str(item_data.get("name", item_data["item_id"])),
                item_type=BOMItemType(item_data.get("item_type", "raw_material")),
                lead_time_days=int(item_data.get("lead_time_days", 0)),
                cost_per_unit=Decimal(str(item_data.get("cost_per_unit", 0))),
            )
            self.add_item(item)
        
        for comp_data in components:
            comp = BOMComponent(
                parent_id=str(comp_data["parent_id"]),
                component_id=str(comp_data["component_id"]),
                quantity_per=Decimal(str(comp_data["quantity_per"])),
                sequence=int(comp_data.get("sequence", 0)),
                scrap_factor=Decimal(str(comp_data.get("scrap_factor", 1.0))),
            )
            self.add_component(comp)
    
    def explode(
        self,
        item_id: str,
        quantity: Decimal,
        max_levels: int = 10,
    ) -> List[ExplodedRequirement]:
        """
        Explode BOM for an item.
        
        Returns flat list of all components needed.
        """
        requirements: List[ExplodedRequirement] = []

        # FASE 1A.4 (CRIT-11) — proper cycle detection. The previous
        # implementation keyed `visited` by `(current_id, level)`, so a
        # cycle A→B→A would still be traversed (each visit got a new
        # level). With max_levels=10 the recursion stopped, but the BOM
        # was silently mis-exploded. Now we track the *ancestor path*
        # of the current DFS frame: a node already in the path means a
        # cycle, raise loudly. `visited` becomes a level-agnostic set
        # used only to skip already-fully-expanded subtrees.
        visited: Set[str] = set()
        ancestors: List[str] = []

        def _explode_recursive(
            current_id: str,
            current_qty: Decimal,
            level: int,
            parent_id: Optional[str],
            cumulative_lt: int,
        ):
            if level > max_levels:
                return
            if current_id in ancestors:
                raise BOMCycleError(ancestors + [current_id])

            ancestors.append(current_id)
            try:
                # Get item info
                item = self._items.get(current_id)
                item_name = item.name if item else current_id
                item_lt = item.lead_time_days if item else 0
                item_type = item.item_type if item else BOMItemType.RAW_MATERIAL

                is_purchased = item_type in (
                    BOMItemType.RAW_MATERIAL,
                    BOMItemType.PACKAGING,
                )

                # Add requirement
                requirements.append(ExplodedRequirement(
                    component_id=current_id,
                    component_name=item_name,
                    required_qty=current_qty,
                    level=level,
                    parent_id=parent_id,
                    lead_time_days=item_lt,
                    cumulative_lead_time=cumulative_lt + item_lt,
                    is_purchased=is_purchased,
                ))

                visited.add(current_id)

                # Get children
                children = self._parent_map.get(current_id, [])

                for child in children:
                    child_qty = current_qty * child.quantity_per * child.scrap_factor
                    _explode_recursive(
                        child.component_id,
                        child_qty,
                        level + 1,
                        current_id,
                        cumulative_lt + item_lt,
                    )
            finally:
                ancestors.pop()

        _explode_recursive(item_id, quantity, 0, None, 0)

        return requirements
    
    def get_leaf_requirements(
        self,
        item_id: str,
        quantity: Decimal,
    ) -> Dict[str, Decimal]:
        """
        Get aggregated requirements for leaf items only.
        
        Returns dict of {component_id: total_quantity}.
        """
        requirements = self.explode(item_id, quantity)
        
        leaf_items: Dict[str, Decimal] = {}
        
        for req in requirements:
            # Check if this is a leaf (no children)
            if req.component_id not in self._parent_map:
                if req.component_id not in leaf_items:
                    leaf_items[req.component_id] = Decimal("0")
                leaf_items[req.component_id] += req.required_qty
        
        return leaf_items
    
    def calculate_material_cost(
        self,
        item_id: str,
        quantity: Decimal,
    ) -> Decimal:
        """Calculate total material cost for an item."""
        leaf_reqs = self.get_leaf_requirements(item_id, quantity)
        
        total_cost = Decimal("0")
        for comp_id, qty in leaf_reqs.items():
            item = self._items.get(comp_id)
            if item:
                total_cost += qty * item.cost_per_unit
        
        return total_cost
    
    def get_cumulative_lead_time(self, item_id: str) -> int:
        """Get maximum cumulative lead time (critical path)."""
        requirements = self.explode(item_id, Decimal("1"))
        
        if not requirements:
            return 0
        
        return max(req.cumulative_lead_time for req in requirements)










