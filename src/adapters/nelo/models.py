"""SQLAlchemy 2.0 read-only models for NELO MAR-KAYAKS DB.

Source: SQL Server `fabrica.nelo.eu:1039`, DB `MAR-KAYAKS`, schema `dbo`.
Discovered 2026-05-12 by `scripts/discover_mar_kayaks.py` —
see `agent_docs/mar_kayaks_schema_discovery.md` for full schema reference.

Conventions
-----------
- All classes are READ-ONLY. Never call `session.add()`, `session.commit()`
  on these models against the source DB. If you mirror them locally, do so
  via an ETL pipeline that owns its own SQLAlchemy session.
- Class names in English snake_case (`WorkOrder`, `ProductionPhase`).
- Column attribute names in English snake_case but mapped explicitly to
  the original PT-PT physical column via `mapped_column(..., name="OF_DATA")`.
  This keeps Python code readable while preserving the SQL identity.
- Only operationally-relevant columns are mapped. Audit columns (criador,
  actualizador, dataactualizacao) are mapped where useful; ornamental
  legacy fields are skipped to keep the surface small.
- All FKs are declared with `ForeignKey("schema.table.column")` referencing
  the dbo schema explicitly.
- `relationship()` is set up only where there's a DECLARED FK on the source
  (per `mar_kayaks_schema_discovery.md`). Implicit relations (by naming)
  are noted in comments but not wired up — validate the join before using.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for the NELO adapter — read-only."""


# ─── Production phases (work centres) ───────────────────────────────────


class ProductionPhase(Base):
    """`dbo.FASES_PRODUCAO` — 71 rows. The factory's work centre master.

    Each phase has K1/K2/K4 reference times (`fp_valor_ref_k{1,2,4}`) for
    the boat classes. Self-referencing via `FP_FP_ID` to model phase
    families (e.g. variants of Laminagem grouped under a parent phase).
    """

    __tablename__ = "FASES_PRODUCAO"
    __table_args__ = {"schema": "dbo"}

    id: Mapped[int] = mapped_column("FP_ID", Integer, primary_key=True)
    name: Mapped[str] = mapped_column("FP_NOME", String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column("FP_DESCRICAO", String)
    sequence: Mapped[int] = mapped_column("FP_SEQUENCIA", Integer, nullable=False)
    is_production: Mapped[bool] = mapped_column("FP_PRODUCAO", Boolean, nullable=False)
    is_automatic: Mapped[bool] = mapped_column("FP_AUTOMATICA", Boolean, nullable=False)
    parent_phase_id: Mapped[Optional[int]] = mapped_column(
        "FP_FP_ID", Integer, ForeignKey("dbo.FASES_PRODUCAO.FP_ID")
    )
    hour_coefficient: Mapped[float] = mapped_column("FP_HORA_COEF", Float, nullable=False)
    color: Mapped[Optional[str]] = mapped_column("FP_COR", String(6))
    can_repeat: Mapped[bool] = mapped_column("FP_PODE_REPETIR", Boolean, nullable=False)
    planning_enabled: Mapped[bool] = mapped_column("FP_PLANEAMENTO", Boolean, nullable=False)
    product_id: Mapped[Optional[int]] = mapped_column(
        "FP_P_ID", Integer, ForeignKey("dbo.PRODUTO.P_ID")
    )
    k1_reference_time: Mapped[float] = mapped_column("FP_VALOR_REF_K1", Float, nullable=False)
    k2_reference_time: Mapped[float] = mapped_column("FP_VALOR_REF_K2", Float, nullable=False)
    k4_reference_time: Mapped[float] = mapped_column("FP_VALOR_REF_K4", Float, nullable=False)

    parent: Mapped[Optional["ProductionPhase"]] = relationship(
        "ProductionPhase", remote_side="ProductionPhase.id", back_populates="children"
    )
    children: Mapped[list["ProductionPhase"]] = relationship(
        "ProductionPhase", back_populates="parent"
    )
    product: Mapped[Optional["Product"]] = relationship(
        "Product", foreign_keys=[product_id], back_populates="phases"
    )


# ─── Entities (people, customers, suppliers, operators) ─────────────────


class Entity(Base):
    """`dbo.ENTIDADE` — 8 936 rows. Hub: clients, suppliers, operators, athletes.

    The role is encoded via `E_ENT_ID` (→ ENTIDADE_TIPO) and bit flags
    (`E_NELO` internal employee, `E_TRANSPORTADOR` carrier, etc.). For
    operator workforce, the level lives in `E_NIVEL` (1-3).
    """

    __tablename__ = "ENTIDADE"
    __table_args__ = {"schema": "dbo"}

    id: Mapped[int] = mapped_column("E_ID", Integer, primary_key=True)
    name: Mapped[str] = mapped_column("E_NOME", String, nullable=False)
    email: Mapped[Optional[str]] = mapped_column("E_EMAIL", String)
    phone: Mapped[Optional[str]] = mapped_column("E_TELEFONE", String)
    vat: Mapped[Optional[str]] = mapped_column("E_CONTRIBUINTE", String)
    country: Mapped[Optional[str]] = mapped_column("E_PAIS", String)
    city: Mapped[Optional[str]] = mapped_column("E_CIDADE", String)
    address: Mapped[Optional[str]] = mapped_column("E_MORADA", String)
    postal_code: Mapped[Optional[str]] = mapped_column("E_CODIGOPOSTAL", String(50))
    # Implicit lookup: E_ENT_ID → ENTIDADE_TIPO (not modelled here).
    entity_type_id: Mapped[Optional[int]] = mapped_column("E_ENT_ID", Integer)
    team_id: Mapped[Optional[int]] = mapped_column("E_EQ_ID", Integer)
    bond_type_id: Mapped[Optional[int]] = mapped_column("E_TV_ID", Integer)
    active: Mapped[bool] = mapped_column("E_ACTIVO", Boolean, nullable=False)
    cost_per_hour: Mapped[float] = mapped_column("E_CUSTOHORA", Float, nullable=False)
    entry_date: Mapped[Optional[datetime]] = mapped_column("E_DATAENTRADA", DateTime)
    is_supervisor: Mapped[bool] = mapped_column("E_CHEFE", Boolean, nullable=False)
    is_internal: Mapped[bool] = mapped_column("E_NELO", Boolean, nullable=False)
    is_carrier: Mapped[bool] = mapped_column("E_TRANSPORTADOR", Boolean, nullable=False)
    # Operator skill level (CLAUDE.md: 1-3 níveis).
    level: Mapped[int] = mapped_column("E_NIVEL", Integer, nullable=False)
    productivity: Mapped[float] = mapped_column("E_PRODUTIVIDADE", Float, nullable=False)
    rfid_card: Mapped[Optional[str]] = mapped_column("E_CARTAO_RFID", String(12))

    # Reverse rels — populated by FK-out from other tables
    work_orders: Mapped[list["WorkOrder"]] = relationship(
        "WorkOrder",
        foreign_keys="WorkOrder.customer_entity_id",
        back_populates="customer_entity",
    )


# ─── Products (catalog + BOM + routing) ─────────────────────────────────


class Product(Base):
    """`dbo.PRODUTO` — 14 016 rows. Catalog: boats, components, accessories.

    Self-references via `P_P_ID` (parent / generic family). Cost cache in
    `P_CUSTO_CACHE`. K1/K2/K4 classification lives in `P_TP_ID` (→
    `PRODUTO_TIPO`).
    """

    __tablename__ = "PRODUTO"
    __table_args__ = {"schema": "dbo"}

    id: Mapped[int] = mapped_column("P_ID", Integer, primary_key=True)
    name: Mapped[str] = mapped_column("P_NOME", String, nullable=False)
    name_en: Mapped[Optional[str]] = mapped_column("P_NOME_EN", String)
    description: Mapped[Optional[str]] = mapped_column("P_DESCRICAO", String)
    cost_price: Mapped[float] = mapped_column("P_PRECOCUSTO", Float, nullable=False)
    sale_price: Mapped[float] = mapped_column("P_PRECOVENDA", Float, nullable=False)
    coefficient: Mapped[float] = mapped_column("P_COEFICIENTE", Float, nullable=False)
    stock: Mapped[float] = mapped_column("P_STOCK", Float, nullable=False)
    stock_min: Mapped[float] = mapped_column("P_STOCKMIN", Float, nullable=False)
    weight_lamination: Mapped[float] = mapped_column("P_PESOLAM", Float, nullable=False)
    weight_finished: Mapped[float] = mapped_column("P_PESOACAB", Float, nullable=False)
    qty_deck: Mapped[float] = mapped_column("P_QTDDECK", Float, nullable=False)
    qty_hull: Mapped[float] = mapped_column("P_QTDCASCO", Float, nullable=False)
    in_house: Mapped[bool] = mapped_column("P_FABRICOINTERNO", Boolean, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column("P_DATACRIACAO", DateTime)
    active: Mapped[bool] = mapped_column("P_ACTIVO", Boolean, nullable=False)
    discontinued: Mapped[bool] = mapped_column("P_DESCONTINUADO", Boolean, nullable=False)
    cost_cache: Mapped[Optional[float]] = mapped_column("P_CUSTO_CACHE", Float)
    # Implicit lookups (no declared FK): type_id → PRODUTO_TIPO,
    # size_id → PRODUTO_TAMANHO, model_id → PRODUTO_MODELO,
    # unit_id → UNIDADE, discipline_type_id → PRODUTO_TIPO.
    type_id: Mapped[Optional[int]] = mapped_column("P_TP_ID", Integer)
    size_id: Mapped[Optional[int]] = mapped_column("P_TAM_ID", Integer)
    model_id: Mapped[Optional[int]] = mapped_column("P_M_ID", Integer)
    unit_id: Mapped[Optional[int]] = mapped_column("P_UNI_ID", Integer)
    parent_product_id: Mapped[Optional[int]] = mapped_column(
        "P_P_ID", Integer, ForeignKey("dbo.PRODUTO.P_ID")
    )
    responsible_entity_id: Mapped[Optional[int]] = mapped_column(
        "P_E_ID_RESP", Integer, ForeignKey("dbo.ENTIDADE.E_ID")
    )
    length_mm: Mapped[float] = mapped_column("P_COMPRIMENTO", Float, nullable=False)
    width_mm: Mapped[float] = mapped_column("P_LARGURA", Float, nullable=False)
    height_mm: Mapped[float] = mapped_column("P_ALTURA", Float, nullable=False)

    parent: Mapped[Optional["Product"]] = relationship(
        "Product", remote_side="Product.id", back_populates="children"
    )
    children: Mapped[list["Product"]] = relationship(
        "Product", back_populates="parent"
    )
    responsible_entity: Mapped[Optional["Entity"]] = relationship(
        "Entity", foreign_keys=[responsible_entity_id]
    )
    routings: Mapped[list["ProductPhase"]] = relationship(
        "ProductPhase",
        foreign_keys="ProductPhase.product_id",
        back_populates="product",
    )
    bom_items: Mapped[list["ProductComponent"]] = relationship(
        "ProductComponent",
        foreign_keys="ProductComponent.product_id",
        back_populates="product",
    )
    phases: Mapped[list["ProductionPhase"]] = relationship(
        "ProductionPhase",
        foreign_keys="ProductionPhase.product_id",
        back_populates="product",
    )


class ProductPhase(Base):
    """`dbo.PRODUTO_FASE` — 42 811 rows. Per-product routing (operation order).

    One row per (product, phase, sequence). `prodf_tempo` is the duration
    in hours but cura/secagem phases override via FASES_PRODUCAO K1/K2/K4
    reference times.
    """

    __tablename__ = "PRODUTO_FASE"
    __table_args__ = {"schema": "dbo"}

    id: Mapped[int] = mapped_column("PRODF_ID", Integer, primary_key=True)
    product_id: Mapped[Optional[int]] = mapped_column(
        "PRODF_P_ID", Integer, ForeignKey("dbo.PRODUTO.P_ID")
    )
    phase_id: Mapped[Optional[int]] = mapped_column(
        "PRODF_FP_ID", Integer, ForeignKey("dbo.FASES_PRODUCAO.FP_ID")
    )
    description: Mapped[Optional[str]] = mapped_column("PRODF_DESCRICAO", String)
    sequence: Mapped[int] = mapped_column("PRODF_SEQUENCIA", Integer, nullable=False)
    time_hours: Mapped[float] = mapped_column("PRODF_TEMPO", Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column("PRODF_DATA", DateTime, nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column("PRODF_DATAACTUALIZACAO", DateTime)
    deleted_at: Mapped[Optional[datetime]] = mapped_column("PRODF_DATA_ELIMINADO", DateTime)
    stock: Mapped[float] = mapped_column("PRODF_STOCK", Float, nullable=False)
    automatic: Mapped[bool] = mapped_column("PRODF_AUTOMATICA", Boolean, nullable=False)
    in_production: Mapped[bool] = mapped_column("PRODF_FABRICO", Boolean, nullable=False)
    coefficient: Mapped[float] = mapped_column("PRODF_COEFICIENTE", Float, nullable=False)
    coefficient_x: Mapped[float] = mapped_column("PRODF_COEFICIENTE_X", Float, nullable=False)
    planning_enabled: Mapped[bool] = mapped_column("PRODF_PLANEAMENTO", Boolean, nullable=False)
    parent_routing_id: Mapped[Optional[int]] = mapped_column(
        "PRODF_PRODF_ID", Integer, ForeignKey("dbo.PRODUTO_FASE.PRODF_ID")
    )
    layer_type_id: Mapped[Optional[int]] = mapped_column("PRODF_TPCAM_ID", Integer)

    product: Mapped[Optional["Product"]] = relationship(
        "Product", foreign_keys=[product_id], back_populates="routings"
    )
    phase: Mapped[Optional["ProductionPhase"]] = relationship(
        "ProductionPhase", foreign_keys=[phase_id]
    )
    parent: Mapped[Optional["ProductPhase"]] = relationship(
        "ProductPhase", remote_side="ProductPhase.id"
    )


class ProductComponent(Base):
    """`dbo.PRODUTO_COMPONENTE` — 117 900 rows. BOM (parent → component).

    `COMP_P_ID` is the parent product, `COMP_P_P_ID` is the component.
    `COMP_FP_ID` identifies the phase where the component is consumed.
    `COMP_ELIMINADO` is a soft-delete timestamp — filter where NULL for
    active BOM lines.
    """

    __tablename__ = "PRODUTO_COMPONENTE"
    __table_args__ = {"schema": "dbo"}

    id: Mapped[int] = mapped_column("COMP_ID", Integer, primary_key=True)
    product_id: Mapped[Optional[int]] = mapped_column(
        "COMP_P_ID", Integer, ForeignKey("dbo.PRODUTO.P_ID")
    )
    component_product_id: Mapped[int] = mapped_column(
        "COMP_P_P_ID", Integer, ForeignKey("dbo.PRODUTO.P_ID"), nullable=False
    )
    quantity: Mapped[float] = mapped_column("COMP_QUANTIDADE", Float, nullable=False)
    component_type_id: Mapped[int] = mapped_column("COMP_TPCOMP_ID", Integer, nullable=False)
    observations: Mapped[Optional[str]] = mapped_column("COMP_OBS", String)
    changed_at: Mapped[Optional[datetime]] = mapped_column("COMP_DATA_ALT", DateTime)
    is_final_phase: Mapped[bool] = mapped_column("COMP_FASE_FINAL", Boolean, nullable=False)
    configurable: Mapped[bool] = mapped_column("COMP_CONFIGURAVEL", Boolean, nullable=False)
    phase_id: Mapped[Optional[int]] = mapped_column(
        "COMP_FP_ID", Integer, ForeignKey("dbo.FASES_PRODUCAO.FP_ID")
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column("COMP_ELIMINADO", DateTime)

    product: Mapped[Optional["Product"]] = relationship(
        "Product", foreign_keys=[product_id], back_populates="bom_items"
    )
    component_product: Mapped["Product"] = relationship(
        "Product", foreign_keys=[component_product_id]
    )
    phase: Mapped[Optional["ProductionPhase"]] = relationship(
        "ProductionPhase", foreign_keys=[phase_id]
    )


# ─── Work orders (transactional core) ───────────────────────────────────


class WorkOrder(Base):
    """`dbo.ORDEMFABRICO` — 441 392 rows. THE central transactional table.

    Each WO links to a customer order (`OF_ENC_ID` → ENCOMENDA), a product
    (`OF_P_ID`), a current phase pointer (`OF_FP_ID`), and an entity
    (`OF_E_ID`). Dates: `OF_DATAINICIO/FIM` are actual, `OF_DATATRANSPORTE`
    is the planned ship date. `OF_COEFICIENTE` is in EUR (CLAUDE.md
    invariant — coefficient is money, never time).
    """

    __tablename__ = "ORDEMFABRICO"
    __table_args__ = {"schema": "dbo"}

    id: Mapped[int] = mapped_column("OF_ID", Integer, primary_key=True)
    ordered_at: Mapped[datetime] = mapped_column("OF_DATA", DateTime, nullable=False)
    transport_date: Mapped[Optional[datetime]] = mapped_column("OF_DATATRANSPORTE", DateTime)
    delivery_date: Mapped[Optional[datetime]] = mapped_column("OF_DATAENTREGA", DateTime)
    start_date: Mapped[Optional[datetime]] = mapped_column("OF_DATAINICIO", DateTime)
    end_date: Mapped[Optional[datetime]] = mapped_column("OF_DATAFIM", DateTime)
    payment_date: Mapped[Optional[datetime]] = mapped_column("OF_DATAPAGAMENTO", DateTime)
    observations: Mapped[Optional[str]] = mapped_column("OF_OBSERVACOES", String)
    cost_price: Mapped[float] = mapped_column("OF_PRECOCUSTO", Float, nullable=False)
    sale_price: Mapped[float] = mapped_column("OF_PRECOVENDA", Float, nullable=False)
    customer_name: Mapped[Optional[str]] = mapped_column("OF_NOME", String)
    delivery_address: Mapped[Optional[str]] = mapped_column("OF_MORADAENTREGA", String)
    reference: Mapped[Optional[str]] = mapped_column("OF_REFERENCIA", String)
    customer_phone: Mapped[Optional[str]] = mapped_column("OF_TELEFONE", String)
    customer_email: Mapped[Optional[str]] = mapped_column("OF_EMAIL", String)
    discount: Mapped[float] = mapped_column("OF_DESCONTO", Float, nullable=False)
    paid_amount: Mapped[float] = mapped_column("OF_VALORPAGO", Float, nullable=False)
    # CoeficienteX é DINHEIRO (€) — CLAUDE.md invariant #5.
    coefficient: Mapped[float] = mapped_column("OF_COEFICIENTE", Float, nullable=False)
    is_paid: Mapped[bool] = mapped_column("OF_PAGO", Boolean, nullable=False)
    supervised: Mapped[bool] = mapped_column("OF_SUPERVISAO", Boolean, nullable=False)
    supervised_lamination: Mapped[bool] = mapped_column(
        "OF_SUPERVISAOLAMINAGEM", Boolean, nullable=False
    )
    sequence: Mapped[int] = mapped_column("OF_SEQUENCIA", Integer, nullable=False)
    type_of_use_id: Mapped[Optional[int]] = mapped_column("OF_OFTU_ID", Integer)
    shift_id: Mapped[Optional[int]] = mapped_column("OF_TURN_ID", Integer)
    encomenda_id: Mapped[Optional[int]] = mapped_column("OF_ENC_ID", Integer)
    product_id: Mapped[int] = mapped_column(
        "OF_P_ID", Integer, ForeignKey("dbo.PRODUTO.P_ID"), nullable=False
    )
    customer_entity_id: Mapped[Optional[int]] = mapped_column(
        "OF_E_ID", Integer, ForeignKey("dbo.ENTIDADE.E_ID")
    )
    ordering_entity_id: Mapped[Optional[int]] = mapped_column(
        "OF_E_ID_ENC", Integer, ForeignKey("dbo.ENTIDADE.E_ID")
    )
    parent_work_order_id: Mapped[Optional[int]] = mapped_column(
        "OF_OF_ID_MLD", Integer, ForeignKey("dbo.ORDEMFABRICO.OF_ID")
    )
    current_phase_id: Mapped[int] = mapped_column(
        "OF_FP_ID", Integer, ForeignKey("dbo.FASES_PRODUCAO.FP_ID"), nullable=False
    )
    warehouse_id: Mapped[int] = mapped_column("OF_ARM_ID", Integer, nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column("OF_DATAACTUALIZACAO", DateTime)
    cost_cache: Mapped[Optional[float]] = mapped_column("OF_CUSTOS_CACHE", Float)

    product: Mapped["Product"] = relationship("Product", foreign_keys=[product_id])
    customer_entity: Mapped[Optional["Entity"]] = relationship(
        "Entity", foreign_keys=[customer_entity_id], back_populates="work_orders"
    )
    ordering_entity: Mapped[Optional["Entity"]] = relationship(
        "Entity", foreign_keys=[ordering_entity_id]
    )
    current_phase: Mapped["ProductionPhase"] = relationship(
        "ProductionPhase", foreign_keys=[current_phase_id]
    )
    parent: Mapped[Optional["WorkOrder"]] = relationship(
        "WorkOrder", remote_side="WorkOrder.id"
    )
    phases: Mapped[list["WorkOrderPhase"]] = relationship(
        "WorkOrderPhase",
        foreign_keys="WorkOrderPhase.work_order_id",
        back_populates="work_order",
    )


class WorkOrderPhase(Base):
    """`dbo.OF_FP` — 2 627 279 rows. WO × phase execution log.

    Quality is captured INLINE in this row (despite OFFP_PROBLEMA child
    table existing with 0 rows): `OFFP_PROBS_GOLA`, `OFFP_PROBS_INTERIOR`,
    `OFFP_PROBS_PINTURA`, `OFFP_PROBS_MOLDE`, `OFFP_PROBS_LAMINAGEM`,
    `OFFP_PROBS_DATA`. Cura/secagem environment in `OFFP_TEMPERATURA` /
    `OFFP_HUMIDADE`. `OFFP_OFFP_ID_RETURN` is the rework chain pointer.
    """

    __tablename__ = "OF_FP"
    __table_args__ = {"schema": "dbo"}

    id: Mapped[int] = mapped_column("OFFP_ID", Integer, primary_key=True)
    work_order_id: Mapped[int] = mapped_column(
        "OFFP_OF_ID", Integer, ForeignKey("dbo.ORDEMFABRICO.OF_ID"), nullable=False
    )
    phase_id: Mapped[int] = mapped_column(
        "OFFP_FP_ID", Integer, ForeignKey("dbo.FASES_PRODUCAO.FP_ID"), nullable=False
    )
    problems_text: Mapped[Optional[str]] = mapped_column("OFFP_PROBLEMAS", String)
    observations: Mapped[Optional[str]] = mapped_column("OFFP_OBSERVACOES", String)
    start_at: Mapped[Optional[datetime]] = mapped_column("OFFP_DATAINICIO", DateTime)
    end_at: Mapped[Optional[datetime]] = mapped_column("OFFP_DATAFIM", DateTime)
    expected_at: Mapped[Optional[datetime]] = mapped_column("OFFP_DATA_PREVISTA", DateTime)
    delivered_at: Mapped[Optional[datetime]] = mapped_column("OFFP_DATA_ENTREGA", DateTime)
    weight: Mapped[float] = mapped_column("OFFP_PESO", Float, nullable=False)
    util_count: Mapped[int] = mapped_column("OFFP_NUMUTIL", Integer, nullable=False)
    sequence: Mapped[Optional[datetime]] = mapped_column("OFFP_SEQUENCIA", DateTime)
    # Implicit FK OFFP_OFFPCL_ID → OFFP_CL (lookup not modelled here).
    class_id: Mapped[Optional[int]] = mapped_column("OFFP_OFFPCL_ID", Integer)
    rework_hours: Mapped[float] = mapped_column("OFFP_HORAS_REP", Float, nullable=False)
    rework_hours_real: Mapped[float] = mapped_column("OFFP_HORAS_REP_REAL", Float, nullable=False)
    temperature: Mapped[float] = mapped_column("OFFP_TEMPERATURA", Float, nullable=False)
    humidity: Mapped[float] = mapped_column("OFFP_HUMIDADE", Float, nullable=False)
    # Inline quality flags — present even though OFFP_PROBLEMA child table is empty.
    problem_neck: Mapped[Optional[str]] = mapped_column("OFFP_PROBS_GOLA", String(2000))
    problem_interior_id: Mapped[Optional[int]] = mapped_column("OFFP_PROBS_INTERIOR", Integer)
    problem_paint_id: Mapped[Optional[int]] = mapped_column("OFFP_PROBS_PINTURA", Integer)
    problem_mold_id: Mapped[Optional[int]] = mapped_column("OFFP_PROBS_MOLDE", Integer)
    problem_lamination_id: Mapped[Optional[int]] = mapped_column(
        "OFFP_PROBS_LAMINAGEM", Integer
    )
    problem_logged_at: Mapped[Optional[datetime]] = mapped_column("OFFP_PROBS_DATA", DateTime)
    is_return: Mapped[bool] = mapped_column("OFFP_RETURN", Boolean, nullable=False)
    return_phase_id: Mapped[Optional[int]] = mapped_column(
        "OFFP_OFFP_ID_RETURN", Integer, ForeignKey("dbo.OF_FP.OFFP_ID")
    )
    coefficient: Mapped[float] = mapped_column("OFFP_COEFICIENTE", Float, nullable=False)
    coefficient_x: Mapped[float] = mapped_column("OFFP_COEFICIENTE_X", Float, nullable=False)
    layer_type_id: Mapped[Optional[int]] = mapped_column("OFFP_TPCAM_ID", Integer)
    planning_enabled: Mapped[bool] = mapped_column("OFFP_PLANEAMENTO", Boolean, nullable=False)
    severe_return: Mapped[bool] = mapped_column("OFFP_RETORNO_GRAVE", Boolean, nullable=False)

    work_order: Mapped["WorkOrder"] = relationship(
        "WorkOrder", foreign_keys=[work_order_id], back_populates="phases"
    )
    phase: Mapped["ProductionPhase"] = relationship(
        "ProductionPhase", foreign_keys=[phase_id]
    )
    return_phase: Mapped[Optional["WorkOrderPhase"]] = relationship(
        "WorkOrderPhase", remote_side="WorkOrderPhase.id"
    )


# ─── Movements (stock + WIP ledger) ─────────────────────────────────────


class Movement(Base):
    """`dbo.MOVIMENTO` — 12 392 449 rows. Stock + WIP ledger (huge).

    Each row is one inventory event: receipt, issue, transfer, consumption.
    Linked to WO via `MOV_OF_ID` (implicit; no declared FK), to OF×fase via
    `MOV_OFFP_ID`, and to a movement type lookup `MOV_TPMOV_ID`. For WIP
    accounting, the work order phase linkage is what matters.

    **Filter before SELECT** — full table is 12M+ rows. Always constrain
    by `moved_at` window.
    """

    __tablename__ = "MOVIMENTO"
    __table_args__ = {"schema": "dbo"}

    id: Mapped[int] = mapped_column("MOV_ID", Integer, primary_key=True)
    moved_at: Mapped[Optional[datetime]] = mapped_column("MOV_DATA", DateTime)
    exit_date: Mapped[Optional[datetime]] = mapped_column("MOV_DATASAIDA", DateTime)
    quantity: Mapped[float] = mapped_column("MOV_QUANTIDADE", Float, nullable=False)
    unit_price: Mapped[float] = mapped_column("MOV_PRECOUNITARIO", Float, nullable=False)
    sale_price: Mapped[float] = mapped_column("MOV_PRECOVENDA", Float, nullable=False)
    discount: Mapped[float] = mapped_column("MOV_DESCONTO", Float, nullable=False)
    observations: Mapped[Optional[str]] = mapped_column("MOV_OBSERVACOES", String)
    problem: Mapped[Optional[str]] = mapped_column("MOV_PROBLEMA", String)
    # Implicit FK MOV_OF_ID → ORDEMFABRICO (no declared constraint).
    work_order_id: Mapped[Optional[int]] = mapped_column("MOV_OF_ID", Integer)
    entity_id: Mapped[Optional[int]] = mapped_column(
        "MOV_E_ID", Integer, ForeignKey("dbo.ENTIDADE.E_ID")
    )
    # Implicit FK MOV_P_ID → PRODUTO.
    product_id: Mapped[Optional[int]] = mapped_column("MOV_P_ID", Integer)
    # Implicit FK MOV_TPMOV_ID → MOVIMENTO_TIPO.
    movement_type_id: Mapped[int] = mapped_column("MOV_TPMOV_ID", Integer, nullable=False)
    parent_movement_id: Mapped[Optional[int]] = mapped_column(
        "MOV_MOV_ID", Integer, ForeignKey("dbo.MOVIMENTO.MOV_ID")
    )
    # Implicit FK MOV_ARM_ID → ARMAZEM.
    warehouse_id: Mapped[Optional[int]] = mapped_column("MOV_ARM_ID", Integer)
    phase_id: Mapped[Optional[int]] = mapped_column(
        "MOV_FP_ID", Integer, ForeignKey("dbo.FASES_PRODUCAO.FP_ID")
    )
    # Implicit FK MOV_OFFP_ID → OF_FP.
    work_order_phase_id: Mapped[Optional[int]] = mapped_column("MOV_OFFP_ID", Integer)
    batch: Mapped[Optional[str]] = mapped_column("MOV_LOTE", String)
    is_adjustment: Mapped[bool] = mapped_column("MOV_ACERTO", Boolean, nullable=False)
    is_defective: Mapped[bool] = mapped_column("MOV_DEFEITUOSO", Boolean, nullable=False)
    is_satisfied: Mapped[bool] = mapped_column("MOV_SATISFEITO", Boolean, nullable=False)
    approved_at: Mapped[Optional[datetime]] = mapped_column("MOV_DATA_APROVADO", DateTime)
    approving_entity_id: Mapped[Optional[int]] = mapped_column(
        "MOV_E_ID_APROVA", Integer, ForeignKey("dbo.ENTIDADE.E_ID")
    )
    responsible_entity_id: Mapped[Optional[int]] = mapped_column(
        "MOV_E_ID_RESPONSAVEL", Integer, ForeignKey("dbo.ENTIDADE.E_ID")
    )

    entity: Mapped[Optional["Entity"]] = relationship(
        "Entity", foreign_keys=[entity_id]
    )
    approving_entity: Mapped[Optional["Entity"]] = relationship(
        "Entity", foreign_keys=[approving_entity_id]
    )
    responsible_entity: Mapped[Optional["Entity"]] = relationship(
        "Entity", foreign_keys=[responsible_entity_id]
    )
    parent_movement: Mapped[Optional["Movement"]] = relationship(
        "Movement", remote_side="Movement.id"
    )
    phase: Mapped[Optional["ProductionPhase"]] = relationship(
        "ProductionPhase", foreign_keys=[phase_id]
    )
