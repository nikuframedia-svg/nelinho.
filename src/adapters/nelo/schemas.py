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
    product_type_name: Optional[str] = None
    phase_is_automatic: bool = False


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


# ─── Checklist defects (OF_CHECKLIST) — canonical root-cause source ─────


class ChecklistIncidentRow(_Frozen):
    """One defect logged on the ERP quality checklist (`OF_CHECKLIST`).

    Unlike `OF_FP` (which only knows the phase a rework *happened* in),
    `OF_CHECKLIST` is the canonical root-cause source: it separates the
    phase that **caused** the defect (`OFCH_FP_ID`) from the phase that
    **detected** it (`OFCH_FP_ID_CHK`) — distinct in 78.5% of rows — and
    points at the culprit operation (`OFCH_OFFP_ID_CULPA`), from which the
    responsible operator/chefe is resolved via `OFFP_EQ`.

    Only real defects are surfaced (`OFCH_GRAVIDADE >= 1`); gravidade 0 is
    an "Ok" checklist tick, not a defect.
    """

    checklist_id: int  # OFCH_ID
    work_order_id: int  # OFCH_OF_ID
    phase_id_causer: int  # OFCH_FP_ID — fase que CAUSOU
    phase_id_detector: Optional[int] = None  # OFCH_FP_ID_CHK — fase que DETECTOU
    gravidade: int  # OFCH_GRAVIDADE (1/2/3)
    estado: Optional[int] = None  # OFCH_ESTADO
    culpa_chefe: bool = False  # OFCH_CULPA_CHEFE — culpa atribuída ao chefe
    molde_reparar: bool = False  # OFCH_MOLDE_REPARAR
    detector_op_id: Optional[int] = None  # OFCH_OFFP_ID — operação onde detectado
    causer_op_id: Optional[int] = None  # OFCH_OFFP_ID_CULPA — operação culpada
    description: Optional[str] = None  # OFCH_DESCR
    detected_at: Optional[datetime] = None
    product_id: Optional[int] = None  # OF_P_ID
    product_type_name: Optional[str] = None  # TP_NOME (disciplina)
    causer_chefe_eid: Optional[int] = None  # OFFPEQ_E_ID (chefe da op culpada)
    causer_operator_eid: Optional[int] = None  # OFFPEQ_E_ID (operário da op culpada)
    mold_work_order_id: Optional[int] = None  # OF_OF_ID_MLD — OF do molde em que o barco foi fabricado


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


class ProductStockRow(_Frozen):
    """Stock cache from `dbo.PRODUTO` — `P_STOCK` / `P_STOCKMIN` per product.

    The ERP keeps a per-product on-hand cache directly on the catalogue
    row, so a current snapshot does not need to fold the 12M-row
    `MOVIMENTO` ledger. Quantities are in the product's own unit.
    """

    product_id: int  # P_ID
    stock: float  # P_STOCK — on-hand
    stock_min: float  # P_STOCKMIN — minimum


class WarehouseStockRow(_Frozen):
    """One row of `dbo.produto_stocks_por_armazem` — the ERP's own
    per-warehouse on-hand view (`P_ID` × `Armazem`).

    This is the granular truth the factory uses: stock split across the
    ~20 warehouses (Laminagem, Pintura, Montagem, Camião Nelo…). It does
    not necessarily sum to `PRODUTO.P_STOCK`, which is a separate cached
    aggregate maintained by the ERP.
    """

    product_id: int  # P_ID
    warehouse_id: int  # Armazem_Id
    warehouse_name: str  # Armazem
    stock: float  # Stock — on-hand in that warehouse


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


# ─── ERP config variables (dbo.VARIAVEIS) ───────────────────────────────


class ErpVariableRow(_Frozen):
    """One `dbo.VARIAVEIS` row — variável de configuração do ERP.

    `var_value` é `nvarchar` no ERP (texto), por isso fica `str` aqui — o
    consumidor converte (ex.: VAR_ID=2 = '1.065' = factor de M.O., Q.167.F).
    """

    var_id: int
    var_value: Optional[str] = None
    var_description: Optional[str] = None


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


# ─── Phase history (FasesOf) — historico de fases por OF ───────────────


class FasesOfHistoryRow(_Frozen):
    """Uma linha de `dbo.FasesOf` — execucao de fase por OF.

    Q.115.T: fonte para `plan.fases_of_history`. Alta cardinalidade (~2.6M).
    Campos nullable: fase_fim (fase pode estar em curso), worker_id, mold_id.
    """

    of_id: str          # OF_Id (texto — ERP usa string nesta tabela)
    phase_id: str       # FaseOf_Id (codigo da fase)
    fase_inicio: datetime
    fase_fim: Optional[datetime] = None
    worker_id: Optional[int] = None   # WorkerId (entidade ERP) — pode ser None
    mold_id: Optional[str] = None     # MoldeId


# ─── Worker assignments (WorkerAssignment) — atribuicoes operador/fase ─


class WorkerAssignmentRow(_Frozen):
    """Uma linha de `dbo.WorkerAssignment` — atribuicao de operador a fase.

    Q.115.T: fonte para `hr.worker_phase_assignment`.
    assignment_type derivado pelo ETL: 'actual' se Iniciado_Em presente,
    'planned' se so Atribuido_Em.
    """

    worker_id: Optional[int] = None   # WorkerId (entidade ERP) — nullable no ERP
    of_id: str            # OF_Id
    phase_id: str         # FaseOf_Id
    assigned_at: datetime # Atribuido_Em
    started_at: Optional[datetime] = None   # Iniciado_Em
    ended_at: Optional[datetime] = None     # Terminado_Em
    tipo: Optional[str] = None              # Tipo (string ERP, pode ser None)


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
