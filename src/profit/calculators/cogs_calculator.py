"""
ProdPlan ONE - COGS Calculator
===============================

Cost of Goods Sold calculation with 6 components:
1. Material Cost
2. Labor Cost
3. Machine Cost
4. Setup Cost
5. Overhead Allocation
6. Scrap/Rework Cost
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional
from uuid import UUID


@dataclass
class CostComponent:
    """Single cost component."""
    name: str
    total: Decimal
    per_unit: Decimal
    percent: Decimal = Decimal("0")
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CostBreakdown:
    """Complete cost breakdown."""
    material: CostComponent
    labor: CostComponent
    machine: CostComponent
    setup: CostComponent
    overhead: CostComponent
    scrap: CostComponent
    
    def to_dict(self) -> Dict[str, Any]:
        total = self.total_cogs
        
        def component_dict(c: CostComponent) -> Dict[str, Any]:
            return {
                "total": float(c.total),
                "per_unit": float(c.per_unit),
                "percent": float(c.total / total * 100) if total > 0 else 0,
                "details": c.details,
            }
        
        return {
            "material": component_dict(self.material),
            "labor": component_dict(self.labor),
            "machine": component_dict(self.machine),
            "setup": component_dict(self.setup),
            "overhead": component_dict(self.overhead),
            "scrap": component_dict(self.scrap),
        }
    
    @property
    def total_cogs(self) -> Decimal:
        return (
            self.material.total +
            self.labor.total +
            self.machine.total +
            self.setup.total +
            self.overhead.total +
            self.scrap.total
        )

    def per_piece_breakdown(self) -> Dict[str, float]:
        """Sprint Q.1 / CS01 — flat per-piece costs for the `/cogs/{sku}/breakdown`
        endpoint. Totals always sum to `total_cogs / qty` within rounding."""
        total_per_unit = (
            self.material.per_unit +
            self.labor.per_unit +
            self.machine.per_unit +
            self.setup.per_unit +
            self.overhead.per_unit +
            self.scrap.per_unit
        )
        return {
            "material_per_unit": float(self.material.per_unit),
            "labor_per_unit": float(self.labor.per_unit),
            "machine_per_unit": float(self.machine.per_unit),
            "setup_per_unit": float(self.setup.per_unit),
            "overhead_per_unit": float(self.overhead.per_unit),
            "scrap_per_unit": float(self.scrap.per_unit),
            "total_per_unit": float(total_per_unit),
        }


@dataclass
class COGSResult:
    """Complete COGS calculation result."""
    order_id: str
    product_id: str
    quantity: Decimal
    
    total_cogs: Decimal
    cogs_per_unit: Decimal
    
    breakdown: CostBreakdown
    
    currency: str = "EUR"
    calculated_at: str = ""
    
    assumptions: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "product_id": self.product_id,
            "quantity": float(self.quantity),
            "total_cogs": float(self.total_cogs),
            "cogs_per_unit": float(self.cogs_per_unit),
            "breakdown": self.breakdown.to_dict(),
            "currency": self.currency,
            "calculated_at": self.calculated_at,
            "assumptions": self.assumptions,
            "warnings": self.warnings,
        }


class COGSCalculator:
    """
    COGS Calculator Engine.
    
    Calculates complete Cost of Goods Sold with 6 components.
    
    Usage:
        calc = COGSCalculator()
        result = calc.calculate(
            order_id="PO-001",
            product_id="K1-VANQUISH",
            quantity=500,
            bom_costs={"steel": 4513.75, "wood": 3750.00, "packaging": 125.00},
            labor_allocations=[
                {"employee_id": "emp-001", "hours": 25, "rate": 12.375},
                {"employee_id": "emp-002", "hours": 160, "rate": 9.90},
            ],
            machine_usage=[
                {"machine_id": "PUNCH-01", "hours": 25, "rate": 3.50},
                {"machine_id": "GRIND-05", "hours": 60, "rate": 6.30},
            ],
            setup_activities=[
                {"description": "Tool changeover", "minutes": 15, "labor_rate": 12.375, "machine_rate": 3.50},
            ],
            overhead_rate=1.654,
            total_production_hours=210,
            scrap_rate=0.02,
        )
    """
    
    # Sprint Q.12 — defaults extraídos do código onde estavam
    # hardcoded (50% recuperáveis, 10% rework time). Cada NELO BU pode
    # passar valores específicos via `tenant_config["cogs.scrap.*"]`.
    DEFAULT_SCRAP_RECOVERY_RATE = Decimal("0.5")
    DEFAULT_SCRAP_REWORK_FACTOR = Decimal("0.1")

    def __init__(
        self,
        currency: str = "EUR",
        scrap_recovery_rate: Optional[Decimal] = None,
        scrap_rework_factor: Optional[Decimal] = None,
    ):
        self.currency = currency
        self.scrap_recovery_rate = (
            scrap_recovery_rate
            if scrap_recovery_rate is not None
            else self.DEFAULT_SCRAP_RECOVERY_RATE
        )
        self.scrap_rework_factor = (
            scrap_rework_factor
            if scrap_rework_factor is not None
            else self.DEFAULT_SCRAP_REWORK_FACTOR
        )
    
    def calculate(
        self,
        order_id: str,
        product_id: str,
        quantity: Decimal,
        bom_costs: Dict[str, Decimal] = None,
        labor_allocations: List[Dict[str, Any]] = None,
        machine_usage: List[Dict[str, Any]] = None,
        setup_activities: List[Dict[str, Any]] = None,
        overhead_rate: Decimal = Decimal("0"),
        total_production_hours: Decimal = Decimal("0"),
        scrap_rate: Decimal = Decimal("0.02"),
    ) -> COGSResult:
        """
        Calculate complete COGS for an order.
        
        Args:
            order_id: Production order ID
            product_id: Product being manufactured
            quantity: Quantity to produce
            bom_costs: Material costs from BOM explosion {material_id: cost}
            labor_allocations: List of labor allocations with hours and rates
            machine_usage: List of machine usage with hours and rates
            setup_activities: List of setup activities with times and rates
            overhead_rate: Overhead rate per production hour
            total_production_hours: Total production hours for overhead allocation
            scrap_rate: Expected scrap rate (e.g., 0.02 = 2%)
        
        Returns:
            COGSResult with complete breakdown
        """
        from datetime import datetime
        
        quantity = Decimal(str(quantity))
        bom_costs = bom_costs or {}
        labor_allocations = labor_allocations or []
        machine_usage = machine_usage or []
        setup_activities = setup_activities or []
        overhead_rate = Decimal(str(overhead_rate))
        total_production_hours = Decimal(str(total_production_hours))
        scrap_rate = Decimal(str(scrap_rate))
        
        warnings = []
        
        # 1. Material Cost
        material = self._calculate_material_cost(bom_costs, quantity)
        
        # 2. Labor Cost
        labor = self._calculate_labor_cost(labor_allocations, quantity)
        
        # 3. Machine Cost
        machine = self._calculate_machine_cost(machine_usage, quantity)
        
        # 4. Setup Cost
        setup = self._calculate_setup_cost(setup_activities, quantity)
        
        # 5. Overhead Allocation
        overhead = self._calculate_overhead_cost(
            overhead_rate, total_production_hours, quantity
        )
        
        # 6. Scrap/Rework Cost
        material_per_unit = material.per_unit
        scrap = self._calculate_scrap_cost(
            scrap_rate, quantity, material_per_unit, labor.per_unit
        )
        
        # Create breakdown
        breakdown = CostBreakdown(
            material=material,
            labor=labor,
            machine=machine,
            setup=setup,
            overhead=overhead,
            scrap=scrap,
        )
        
        # Calculate totals
        total_cogs = breakdown.total_cogs
        cogs_per_unit = total_cogs / quantity if quantity > 0 else Decimal("0")
        
        # Round
        total_cogs = total_cogs.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        cogs_per_unit = cogs_per_unit.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        
        return COGSResult(
            order_id=order_id,
            product_id=product_id,
            quantity=quantity,
            total_cogs=total_cogs,
            cogs_per_unit=cogs_per_unit,
            breakdown=breakdown,
            currency=self.currency,
            calculated_at=datetime.utcnow().isoformat(),
            assumptions={
                "scrap_rate": float(scrap_rate),
                "overhead_rate": float(overhead_rate),
            },
            warnings=warnings,
        )
    
    def _calculate_material_cost(
        self,
        bom_costs: Dict[str, Decimal],
        quantity: Decimal,
    ) -> CostComponent:
        """Calculate material cost from BOM."""
        total = Decimal("0")
        details = {}
        
        for material_id, cost in bom_costs.items():
            cost = Decimal(str(cost))
            total += cost
            details[material_id] = float(cost)
        
        per_unit = total / quantity if quantity > 0 else Decimal("0")
        
        return CostComponent(
            name="Material",
            total=total,
            per_unit=per_unit,
            details={"materials": details},
        )
    
    def _calculate_labor_cost(
        self,
        allocations: List[Dict[str, Any]],
        quantity: Decimal,
    ) -> CostComponent:
        """Calculate labor cost from allocations."""
        total = Decimal("0")
        details = []
        
        for alloc in allocations:
            hours = Decimal(str(alloc.get("hours", 0)))
            rate = Decimal(str(alloc.get("rate", 0)))
            cost = hours * rate
            total += cost
            
            details.append({
                "employee_id": alloc.get("employee_id", ""),
                "employee_name": alloc.get("employee_name", ""),
                "hours": float(hours),
                "rate": float(rate),
                "cost": float(cost),
            })
        
        per_unit = total / quantity if quantity > 0 else Decimal("0")
        
        return CostComponent(
            name="Labor",
            total=total,
            per_unit=per_unit,
            details={"allocations": details},
        )
    
    def _calculate_machine_cost(
        self,
        usage: List[Dict[str, Any]],
        quantity: Decimal,
    ) -> CostComponent:
        """Calculate machine cost from usage."""
        total = Decimal("0")
        details = []
        
        for u in usage:
            hours = Decimal(str(u.get("hours", 0)))
            rate = Decimal(str(u.get("rate", 0)))
            cost = hours * rate
            total += cost
            
            details.append({
                "machine_id": u.get("machine_id", ""),
                "machine_name": u.get("machine_name", ""),
                "hours": float(hours),
                "rate": float(rate),
                "cost": float(cost),
            })
        
        per_unit = total / quantity if quantity > 0 else Decimal("0")
        
        return CostComponent(
            name="Machine",
            total=total,
            per_unit=per_unit,
            details={"usage": details},
        )
    
    def _calculate_setup_cost(
        self,
        activities: List[Dict[str, Any]],
        quantity: Decimal,
    ) -> CostComponent:
        """Calculate setup cost from activities."""
        total = Decimal("0")
        details = []
        
        for activity in activities:
            minutes = Decimal(str(activity.get("minutes", 0)))
            hours = minutes / 60
            
            labor_rate = Decimal(str(activity.get("labor_rate", 0)))
            machine_rate = Decimal(str(activity.get("machine_rate", 0)))
            
            labor_cost = hours * labor_rate
            machine_cost = hours * machine_rate
            activity_cost = labor_cost + machine_cost
            total += activity_cost
            
            details.append({
                "description": activity.get("description", ""),
                "minutes": float(minutes),
                "labor_cost": float(labor_cost),
                "machine_cost": float(machine_cost),
                "total": float(activity_cost),
            })
        
        per_unit = total / quantity if quantity > 0 else Decimal("0")
        
        return CostComponent(
            name="Setup",
            total=total,
            per_unit=per_unit,
            details={"activities": details},
        )
    
    def _calculate_overhead_cost(
        self,
        overhead_rate: Decimal,
        production_hours: Decimal,
        quantity: Decimal,
    ) -> CostComponent:
        """Calculate overhead allocation."""
        total = overhead_rate * production_hours
        per_unit = total / quantity if quantity > 0 else Decimal("0")
        
        return CostComponent(
            name="Overhead",
            total=total,
            per_unit=per_unit,
            details={
                "rate_per_hour": float(overhead_rate),
                "production_hours": float(production_hours),
            },
        )
    
    def _calculate_scrap_cost(
        self,
        scrap_rate: Decimal,
        quantity: Decimal,
        material_per_unit: Decimal,
        labor_per_unit: Decimal,
    ) -> CostComponent:
        """Calculate scrap/rework cost.

        Sprint Q.12 — `recovery_rate` e `rework_factor` agora vêm do
        constructor (parametrizáveis por tenant) em vez de hardcoded
        50% / 10%. COGS antes podia estar 5–20% errado conforme produto.
        """
        expected_scrap_units = quantity * scrap_rate

        # Material lost
        material_loss = expected_scrap_units * material_per_unit

        # Rework labor — fracções configuráveis por tenant.
        recoverable_units = expected_scrap_units * self.scrap_recovery_rate
        rework_cost = recoverable_units * labor_per_unit * self.scrap_rework_factor

        total = material_loss + rework_cost
        per_unit = total / quantity if quantity > 0 else Decimal("0")

        return CostComponent(
            name="Scrap/Rework",
            total=total,
            per_unit=per_unit,
            details={
                "scrap_rate": float(scrap_rate),
                "scrap_recovery_rate": float(self.scrap_recovery_rate),
                "scrap_rework_factor": float(self.scrap_rework_factor),
                "expected_scrap_units": float(expected_scrap_units),
                "material_loss": float(material_loss),
                "rework_cost": float(rework_cost),
            },
        )










