"""Pydantic schemas for the NELO MAR-KAYAKS read-only adapter.

These types are the public contract of `src.adapters.nelo.services`. Each
schema mirrors one of the `vw_pp1_*` views (see `agent_docs/views_pp1.sql`)
and uses English snake_case fields — never expose the PT-PT physical names
upstream.

All schemas are READ-ONLY (`model_config.frozen=True`). They are constructed
from `cursor.fetchall()` row mappings; consumers (FastAPI endpoints, CPO
adapters, etc.) should never mutate them.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)


# ─── Orders (vw_pp1_orders) ─────────────────────────────────────────────


class OrderRow(_Frozen):
    work_order_id: int
    ordered_at: Optional[datetime] = None
    transport_date: Optional[datetime] = None
    delivery_date: Optional[datetime] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    customer_name: Optional[str] = None
    reference: Optional[str] = None
    cost_price: float
    sale_price: float
    discount: float
    paid_amount: float
    coefficient_eur: float
    is_paid: bool
    supervised: bool
    sequence: int
    product_id: int
    customer_entity_id: Optional[int] = None
    current_phase_id: int
    warehouse_id: int
    encomenda_id: Optional[int] = None
    encomenda_state: Optional[str] = None
    customer_full_name: Optional[str] = None
    customer_country: Optional[str] = None


# ─── Routings (vw_pp1_routings) ─────────────────────────────────────────


class RoutingRow(_Frozen):
    routing_id: int
    product_id: Optional[int] = None
    phase_id: Optional[int] = None
    phase_name: str
    phase_description: Optional[str] = None
    routing_description: Optional[str] = None
    sequence: int
    time_hours: float
    phase_hour_coefficient: float
    k1_reference_hours: float
    k2_reference_hours: float
    k4_reference_hours: float
    phase_is_production: bool
    phase_is_automatic: bool
    phase_can_repeat: bool
    routing_in_production: bool
    routing_coefficient: float
    routing_coefficient_x: float
    layer_type_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


# ─── BOM (vw_pp1_bom) ───────────────────────────────────────────────────


class BomRow(_Frozen):
    bom_id: int
    parent_product_id: Optional[int] = None
    parent_product_name: Optional[str] = None
    parent_product_name_en: Optional[str] = None
    component_product_id: int
    component_product_name: str
    component_product_name_en: Optional[str] = None
    component_unit_id: Optional[int] = None
    component_stock: float
    component_stock_min: float
    component_cost_price: float
    quantity: float
    component_type_id: int
    consumption_phase_id: Optional[int] = None
    is_final_phase: bool
    configurable: bool
    is_unique: bool
    list_id: Optional[int] = None
    observations: Optional[str] = None
    changed_at: Optional[datetime] = None


# ─── Schedule (vw_pp1_schedule) ─────────────────────────────────────────


class ScheduleRow(_Frozen):
    schedule_id: int
    day: date
    start_hour: int
    end_hour: int
    headcount: int
    transport_id: Optional[int] = None
    shift_hours: int


# ─── Movements (vw_pp1_movements) ───────────────────────────────────────


class MovementRow(_Frozen):
    movement_id: int
    moved_at: Optional[datetime] = None
    exit_date: Optional[datetime] = None
    quantity: float
    unit_price: float
    sale_price: float
    discount: float
    movement_type_id: int
    work_order_id: Optional[int] = None
    work_order_phase_id: Optional[int] = None
    product_id: Optional[int] = None
    entity_id: Optional[int] = None
    warehouse_id: Optional[int] = None
    phase_id: Optional[int] = None
    routing_id: Optional[int] = None
    parent_movement_id: Optional[int] = None
    batch: Optional[str] = None
    balance_quantity: float
    is_adjustment: bool
    is_defective: bool
    is_satisfied: bool
    approved_at: Optional[datetime] = None
    observations: Optional[str] = None
    problem: Optional[str] = None


# ─── Aggregate helpers ──────────────────────────────────────────────────


class ProductOrderCount(_Frozen):
    """Top-N product × order count, returned by `top_products_by_orders()`."""

    product_id: int
    product_name: str
    product_name_en: Optional[str] = None
    order_count: int


class HealthCheckResult(_Frozen):
    """Aggregate snapshot for the health-check entrypoint."""

    open_orders_count: int
    top_products: list[ProductOrderCount]
    current_schedule: list[ScheduleRow]
    movements_last_30d: int
