"""
ProdPlan ONE - Event Definitions
=================================

Typed event classes for all modules.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field

from ..kafka_client import EventBase


# ═══════════════════════════════════════════════════════════════════════════════
# CORE Events
# ═══════════════════════════════════════════════════════════════════════════════

class MasterDataLoadedEvent(EventBase):
    """Fired when master data is loaded/synced."""
    
    event_type: str = "MASTER_DATA_LOADED"
    source_module: str = "CORE"
    payload: Dict[str, Any] = Field(default_factory=lambda: {
        "entity_type": "",  # products, machines, employees, etc.
        "count": 0,
        "sync_type": "full",  # full or incremental
    })


class ConfigUpdatedEvent(EventBase):
    """Fired when configuration is updated (rates, parameters)."""
    
    event_type: str = "CONFIG_UPDATED"
    source_module: str = "CORE"
    payload: Dict[str, Any] = Field(default_factory=lambda: {
        "config_type": "",  # labor_rates, machine_rates, overhead_rates
        "affected_entities": [],
        "effective_from": "",
    })


class TenantConfiguredEvent(EventBase):
    """Fired when a tenant is created or configured."""
    
    event_type: str = "TENANT_CONFIGURED"
    source_module: str = "CORE"
    payload: Dict[str, Any] = Field(default_factory=lambda: {
        "tenant_name": "",
        "subscription_level": "",
        "modules_enabled": [],
    })


# ═══════════════════════════════════════════════════════════════════════════════
# PLAN Events
# ═══════════════════════════════════════════════════════════════════════════════

class ScheduleCreatedEvent(EventBase):
    """Fired when a production schedule is created."""
    
    event_type: str = "SCHEDULE_CREATED"
    source_module: str = "PLAN"
    payload: Dict[str, Any] = Field(default_factory=lambda: {
        "schedule_id": "",
        "order_ids": [],
        "operations_count": 0,
        "planning_horizon_start": "",
        "planning_horizon_end": "",
        "engine_used": "",  # heuristic, milp, cpsat
    })


class ScheduleUpdatedEvent(EventBase):
    """Fired when a schedule is updated."""
    
    event_type: str = "SCHEDULE_UPDATED"
    source_module: str = "PLAN"
    payload: Dict[str, Any] = Field(default_factory=lambda: {
        "schedule_id": "",
        "changes": [],  # list of changed operations
        "reason": "",
    })


class MRPCalculatedEvent(EventBase):
    """Fired when MRP calculation completes."""
    
    event_type: str = "MRP_CALCULATED"
    source_module: str = "PLAN"
    payload: Dict[str, Any] = Field(default_factory=lambda: {
        "mrp_run_id": "",
        "materials_analyzed": 0,
        "purchase_orders_created": 0,
        "total_po_value": 0.0,
        "currency": "EUR",
    })


class PurchaseOrderCreatedEvent(EventBase):
    """Fired when a purchase order is created."""
    
    event_type: str = "PURCHASE_ORDER_CREATED"
    source_module: str = "PLAN"
    payload: Dict[str, Any] = Field(default_factory=lambda: {
        "po_id": "",
        "po_number": "",
        "supplier_id": "",
        "material_id": "",
        "quantity": 0.0,
        "unit_cost": 0.0,
        "total_value": 0.0,
        "due_date": "",
    })


class CapacityConstraintEvent(EventBase):
    """Fired when capacity constraint is detected."""
    
    event_type: str = "CAPACITY_CONSTRAINT_DETECTED"
    source_module: str = "PLAN"
    payload: Dict[str, Any] = Field(default_factory=lambda: {
        "machine_id": "",
        "period": "",
        "available_minutes": 0,
        "required_minutes": 0,
        "utilization_percent": 0.0,
        "severity": "warning",  # warning, critical
    })


# ═══════════════════════════════════════════════════════════════════════════════
# PROFIT Events
# ═══════════════════════════════════════════════════════════════════════════════

class COGSCalculatedEvent(EventBase):
    """Fired when COGS is calculated for an order."""
    
    event_type: str = "COGS_CALCULATED"
    source_module: str = "PROFIT"
    payload: Dict[str, Any] = Field(default_factory=lambda: {
        "order_id": "",
        "cost_calculation_id": "",
        "total_cogs": 0.0,
        "cogs_per_unit": 0.0,
        "breakdown": {
            "material": 0.0,
            "labor": 0.0,
            "machine": 0.0,
            "setup": 0.0,
            "overhead": 0.0,
            "scrap": 0.0,
        },
        "currency": "EUR",
    })


class PricingRecommendedEvent(EventBase):
    """Fired when pricing recommendation is generated."""
    
    event_type: str = "PRICING_RECOMMENDED"
    source_module: str = "PROFIT"
    payload: Dict[str, Any] = Field(default_factory=lambda: {
        "order_id": "",
        "pricing_id": "",
        "strategy": "",  # cost_plus, dynamic, target_margin
        "recommended_price": 0.0,
        "gross_margin_percent": 0.0,
        "valid_until": "",
    })


class ScenarioSimulatedEvent(EventBase):
    """Fired when a profit scenario is simulated."""
    
    event_type: str = "SCENARIO_SIMULATED"
    source_module: str = "PROFIT"
    payload: Dict[str, Any] = Field(default_factory=lambda: {
        "scenario_id": "",
        "scenario_name": "",
        "base_cogs": 0.0,
        "scenario_cogs": 0.0,
        "delta_percent": 0.0,
        "recommendation": "",
    })


# ═══════════════════════════════════════════════════════════════════════════════
# HR Events
# ═══════════════════════════════════════════════════════════════════════════════

class EmployeeAllocatedEvent(EventBase):
    """Fired when employee is allocated to an operation."""
    
    event_type: str = "EMPLOYEE_ALLOCATED"
    source_module: str = "HR"
    payload: Dict[str, Any] = Field(default_factory=lambda: {
        "allocation_id": "",
        "employee_id": "",
        "employee_name": "",
        "order_id": "",
        "operation_id": "",
        "allocated_hours": 0.0,
        "estimated_cost": 0.0,
    })


class LaborCostCommittedEvent(EventBase):
    """Fired when labor cost is committed for an order."""
    
    event_type: str = "LABOR_COST_COMMITTED"
    source_module: str = "HR"
    payload: Dict[str, Any] = Field(default_factory=lambda: {
        "order_id": "",
        "total_labor_cost": 0.0,
        "total_hours": 0.0,
        "employees_assigned": 0,
        "currency": "EUR",
    })


class ProductivityRecordedEvent(EventBase):
    """Fired when productivity is recorded."""
    
    event_type: str = "PRODUCTIVITY_RECORDED"
    source_module: str = "HR"
    payload: Dict[str, Any] = Field(default_factory=lambda: {
        "employee_id": "",
        "operation_id": "",
        "actual_hours": 0.0,
        "standard_hours": 0.0,
        "efficiency_percent": 0.0,
        "quality_score": 0.0,
        "bonus_eligible": False,
    })


class MonthlyPayrollCalculatedEvent(EventBase):
    """Fired when monthly payroll is calculated."""
    
    event_type: str = "MONTHLY_PAYROLL_CALCULATED"
    source_module: str = "HR"
    payload: Dict[str, Any] = Field(default_factory=lambda: {
        "year_month": "",
        "employee_count": 0,
        "total_payroll_cost": 0.0,
        "total_bonus": 0.0,
        "currency": "EUR",
    })


__all__ = [
    # CORE
    "MasterDataLoadedEvent",
    "ConfigUpdatedEvent",
    "TenantConfiguredEvent",
    # PLAN
    "ScheduleCreatedEvent",
    "ScheduleUpdatedEvent",
    "MRPCalculatedEvent",
    "PurchaseOrderCreatedEvent",
    "CapacityConstraintEvent",
    # PROFIT
    "COGSCalculatedEvent",
    "PricingRecommendedEvent",
    "ScenarioSimulatedEvent",
    # HR
    "EmployeeAllocatedEvent",
    "LaborCostCommittedEvent",
    "ProductivityRecordedEvent",
    "MonthlyPayrollCalculatedEvent",
]










