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


# ─── Operations (vw_pp1_operations) — for OEE ──────────────────────────


class OperationRow(_Frozen):
    """One row per OF×fase executed. Source for OEE calculation.

    `standard_time_hours` comes from `PRODUTO_FASE.PRODF_TEMPO` when the
    product has a routing declared for the phase, falling back to
    `FASES_PRODUCAO.FP_VALOR_REF_K1` (the K1-class reference). Quality
    flags (`problem_*`) capture inline categorisation per OF_FP row —
    `OFFP_PROBLEMA` child table is empty in MAR-KAYAKS; the live data
    lives on these columns.
    """

    operation_id: int  # OFFP_ID
    work_order_id: int
    phase_id: int
    phase_name: str
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    expected_at: Optional[datetime] = None
    standard_time_hours: float
    temperature: float
    humidity: float
    problem_neck: Optional[str] = None
    problem_interior_id: Optional[int] = None
    problem_paint_id: Optional[int] = None
    problem_mold_id: Optional[int] = None
    problem_lamination_id: Optional[int] = None
    problem_logged_at: Optional[datetime] = None
    is_return: bool
    severe_return: bool
    product_id: int
    shift_id: Optional[int] = None
    mold_work_order_id: Optional[int] = None
    # Q.36.A — `OFFP_OF_ID_MLD`: the mold (itself an OF) used on THIS
    # operation. Distinct from `mold_work_order_id` (`OF.OF_OF_ID_MLD`,
    # order-level). The causal detectors need the per-operation mold.
    operation_mold_id: Optional[int] = None
    product_type_name: Optional[str] = None
    phase_is_automatic: bool = False


# ─── Quality checklist (OF_CHECKLIST) — REAL rework detail ─────────────


class ChecklistRow(_Frozen):
    """One `dbo.OF_CHECKLIST` row — the real rework/defect record.

    Q.36.A — `OF_CHECKLIST` (≈3 M rows) is where MAR-KAYAKS records the
    actual defects: a free-text description, a severity, the operation to
    blame, whether the mold needs repair. The old quality mirror read the
    `OFFP_PROBS_*` columns / `OFFP_PROBLEMA` table, both empty here — so
    `rework_entry` ended up 99% uncategorised `RETURN`. This is the
    correct source.

    `operation_mold_id` is resolved by joining the flagged operation
    (`OFCH_OFFP_ID`) to `OF_FP.OFFP_OF_ID_MLD`.
    """

    checklist_id: int  # OFCH_ID
    work_order_id: Optional[int] = None  # OFCH_OF_ID
    operation_id: Optional[int] = None  # OFCH_OFFP_ID
    phase_id: Optional[int] = None  # OFCH_FP_ID
    phase_name: Optional[str] = None
    description: str  # OFCH_DESCR — the defect text
    description_en: Optional[str] = None
    severity: int  # OFCH_GRAVIDADE
    mold_repair: bool  # OFCH_MOLDE_REPARAR — defect attributable to the mold
    blame_chefe: bool  # OFCH_CULPA_CHEFE
    blame_operation_id: Optional[int] = None  # OFCH_OFFP_ID_CULPA
    resolved: bool  # OFCH_RESOLVIDO
    state: Optional[int] = None  # OFCH_ESTADO
    verified_at: Optional[datetime] = None  # OFCH_DATA_VERIFICACAO
    updated_at: Optional[datetime] = None  # OFCH_DATA_ACTUALIZACAO
    detected_at: Optional[datetime] = None  # operation end/start fallback
    operation_mold_id: Optional[int] = None  # OF_FP.OFFP_OF_ID_MLD


# ─── Operation crew (OF_FP × OFFP_EQ, windowed) ────────────────────────


class OperationCrewRow(_Frozen):
    """One (operation × operator) row, windowed by date.

    Q.36.A — `OrderLaborRow` carries the same shape but is scoped to a
    single work order. The curated ETL needs the whole crew surface over
    a date window, so this row comes from a windowed `OF_FP × OFFP_EQ`
    join (`OFFP_EQ` ≈1.4 M rows — the operator-per-operation link).
    """

    operation_id: int  # OFFP_ID
    work_order_id: int  # OFFP_OF_ID
    phase_id: int  # OFFP_FP_ID
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    operator_id: int  # OFFPEQ_E_ID
    is_chefe: bool  # OFFPEQ_CHEFE


# ─── Order labour (OF_FP × OFFP_EQ) — per-order labour cost source ─────


class OrderLaborRow(_Frozen):
    """One row per (phase execution × operator) of a single work order.

    Source for the per-order labour cost (Q.26.C.2): `OF_FP` joined to
    `OFFP_EQ` (the operation↔operator link — its only payload columns are
    the operator id and the `chefe` flag; there is **no** per-operator
    hours column). Labour hours come from the elapsed `start_at→end_at`
    of the `OF_FP` row. Phases with no operator in `OFFP_EQ` (e.g. Cura)
    never reach here — the join is inner.
    """

    operation_id: int  # OFFP_ID
    work_order_id: int  # OFFP_OF_ID
    phase_id: int  # OFFP_FP_ID
    phase_name: str
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    is_return: bool  # OFFP_RETURN — retrabalho
    operator_id: int  # OFFPEQ_E_ID
    is_chefe: bool  # OFFPEQ_CHEFE


# ─── Phases (vw_pp1_phases) — master of work centres ───────────────────


class PhaseRow(_Frozen):
    """One production phase (work centre) from `dbo.FASES_PRODUCAO`.

    The `phase_id` is the join key every routing / operation / skill row
    references. K1/K2/K4 reference hours are class-specific standards
    (never the actual time — see `OperationRow`).
    """

    phase_id: int  # FP_ID
    phase_name: str
    phase_description: Optional[str] = None
    sequence: int
    is_production: bool
    is_automatic: bool
    can_repeat: bool
    parent_phase_id: Optional[int] = None
    hour_coefficient: float
    k1_reference_hours: float
    k2_reference_hours: float
    k4_reference_hours: float


# ─── Products (vw_pp1_products) — catalogue ────────────────────────────


class ProductRow(_Frozen):
    """One `dbo.PRODUTO` row — the product catalogue (boats + components).

    `product_type_id` (`P_TP_ID`) points at `PRODUTO_TIPO`; the master
    mirror classifies finished-good vs semi-finished from it. `cost_price`
    is € (NEVER a coefficient — see CLAUDE.md).
    """

    product_id: int  # P_ID
    product_name: str
    product_name_en: Optional[str] = None
    product_type_id: Optional[int] = None
    active: bool
    discontinued: bool
    in_house: bool
    cost_price: float


# ─── Entities / operators (vw_pp1_entities) ────────────────────────────


class EntityRow(_Frozen):
    """One row of `dbo.ENTIDADE` — the polymorphic hub (people, clients,
    suppliers, operators).

    For master-data sync only the operator-relevant columns are exposed.
    `is_internal` (`E_NELO`) flags a NELO employee; `cost_per_hour`
    (`E_CUSTOHORA`) is € — useful for COGS, never for scheduling time.
    """

    entity_id: int  # E_ID
    name: str
    active: bool
    is_internal: bool
    is_carrier: bool
    is_supervisor: bool
    cost_per_hour: float
    level: int
    productivity: float
    entity_type_id: Optional[int] = None
    entity_type_name: Optional[str] = None
    entry_date: Optional[datetime] = None
    country: Optional[str] = None
    email: Optional[str] = None


# ─── Skill matrix (vw_pp1_entity_phases) ───────────────────────────────


class EntityPhaseRow(_Frozen):
    """One `dbo.ENTIDADE_FASE` row — operator × phase competence.

    `qualified` (`EFP_QUALIFICADO`) and `proficiency` (`EFP_PRODUTIVIDADE`,
    1..5-ish) drive the Spelke skill-match axiom. `is_supervisor`
    (`EFP_CHEFE`) marks the operator as a chefe for that phase.
    """

    entity_phase_id: int  # EFP_ID
    entity_id: int
    phase_id: int
    proficiency: int
    is_supervisor: bool
    qualified: bool
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


# ─── Molds (vw_pp1_molds) ──────────────────────────────────────────────


class MoldRow(_Frozen):
    """One `dbo.MOLDES` row. The ERP knows only ~91 molds (the full ~510
    live in Excel); this is the ERP-side catalogue used for reconciliation
    and pocket-count enrichment. `MOLDES` has no maintenance columns.
    """

    mold_id: int  # MLD_ID
    mold_name: str
    mold_type_id: int
    usage_count: int
    acquired_at: Optional[datetime] = None


# ─── Mold movements (vw_pp1_mold_movements) ────────────────────────────


class MoldMovementRow(_Frozen):
    """One `dbo.MOLDES_MOV` row — the mold-movement ledger.

    Q.38.A — `MOLDES_MOV` (~3.7 k rows) records every movement of a mold
    (the resource): a movement type, when it happened, and the entity
    (`MLDU_E_ID`) involved. `mold_id` (`MLDU_MLD_ID`) is the FK back to
    `MOLDES.MLD_ID` — the ERP-side mold catalogue. The movement-type
    dictionary (`MLDU_TP_ID`) is not yet confirmed by the CEO, so it is
    surfaced as the raw int; no derived label is invented here.
    """

    mold_movement_id: int  # MLDU_ID
    moved_at: Optional[datetime] = None  # MLDU_DATA
    movement_type_id: int  # MLDU_TP_ID
    mold_id: int  # MLDU_MLD_ID → MOLDES.MLD_ID
    entity_id: int  # MLDU_E_ID


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
