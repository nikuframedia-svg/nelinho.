"""
CURATED Models — Contrato 010
=============================

Factory Curated Schema:
- order: manufacturing orders
- order_phase: order × phase with times
- phase_capacity: theoretical capacity per phase
- mold: mold attributes
- mold_usage: mold assignments to orders
- quality_event: defects/errors
- skill_matrix: employee × phase skills (PII)
- cost_reference: cost per hour (sensitive)

CRITICAL: All curated tables:
- Have `ingestion_id` for filtering by active run
- Have `created_at_utc` for audit
- Have explicit business keys
"""

from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Numeric,
    Date,
    DateTime,
    Boolean,
    Index,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import Base


# ============================================================================
# QUARANTINE MIXIN (for all curated tables)
# ============================================================================

class QuarantineMixin:
    """
    Mixin for quarantine functionality.
    
    Instead of deleting problematic rows, we mark them as quarantined.
    This allows:
    - Audit trail of problematic data
    - Easy filtering (is_quarantined = FALSE)
    - Data repair workflows
    """
    
    is_quarantined: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Row is quarantined due to data quality issues"
    )
    
    quarantine_reason: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        doc="Reason for quarantine"
    )
    
    quarantine_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        doc="Machine-readable quarantine code (e.g., INVALID_TIMING, MISSING_KEY)"
    )
    
    quarantined_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="When the row was quarantined"
    )


# ============================================================================
# ORDER (Ordem de Fabrico)
# ============================================================================

class CuratedOrder(QuarantineMixin, Base):
    """
    Manufacturing order.
    
    Business key: of_id (from source system)
    """
    
    __tablename__ = "order"
    __table_args__ = (
        Index("ix_curated_order_ingestion", "ingestion_id"),
        Index("ix_curated_order_of_id", "of_id"),
        Index("ix_curated_order_produto", "produto_id"),
        {"schema": "factory_curated"},
    )
    
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    
    ingestion_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("factory_meta.ingestion_run.id"),
        nullable=False
    )
    
    # Business key
    of_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    
    # Product
    produto_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )
    
    produto_nome: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )
    
    # Model
    modelo_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )
    
    modelo_nome: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )
    
    # Dates
    data_entrada: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True
    )
    
    data_entrega_prevista: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True
    )
    
    data_conclusao: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True
    )
    
    # Quantities
    quantidade: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    
    quantidade_produzida: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    
    # Status
    estado: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )
    
    # Timestamps
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )


# ============================================================================
# ORDER PHASE (Fases da Ordem de Fabrico)
# ============================================================================

class CuratedOrderPhase(QuarantineMixin, Base):
    """
    Order × Phase with theoretical and actual times.
    
    Business key: (of_id, fase_id)
    """
    
    __tablename__ = "order_phase"
    __table_args__ = (
        Index("ix_curated_order_phase_ingestion", "ingestion_id"),
        Index("ix_curated_order_phase_of", "of_id"),
        Index("ix_curated_order_phase_fase", "fase_id"),
        Index("ix_curated_order_phase_composite", "of_id", "fase_id"),
        {"schema": "factory_curated"},
    )
    
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    
    ingestion_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("factory_meta.ingestion_run.id"),
        nullable=False
    )
    
    # Business keys
    of_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    
    fase_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    
    fase_of_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )
    
    fase_nome: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    # Times (hours)
    horas_previstas: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4),
        nullable=True
    )
    
    horas_reais: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4),
        nullable=True
    )
    
    horas_standard: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4),
        nullable=True
    )
    
    # Derived: prioritized hours
    horas_finais: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4),
        nullable=True
    )
    
    # Status
    estado: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )
    
    # Dates
    data_inicio: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True
    )
    
    data_fim: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True
    )
    
    # Sequence
    ordem: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    
    # Mold reference
    molde_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )
    
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )


# ============================================================================
# PHASE CAPACITY (Capacidade por Fase)
# ============================================================================

class CuratedPhaseCapacity(QuarantineMixin, Base):
    """
    Theoretical capacity per phase/period.
    
    Business key: (fase_id, periodo)
    """
    
    __tablename__ = "phase_capacity"
    __table_args__ = (
        Index("ix_curated_phase_capacity_ingestion", "ingestion_id"),
        Index("ix_curated_phase_capacity_fase", "fase_id"),
        {"schema": "factory_curated"},
    )
    
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    
    ingestion_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("factory_meta.ingestion_run.id"),
        nullable=False
    )
    
    fase_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    
    fase_nome: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    # Period (could be date, week, month)
    periodo: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True
    )
    
    periodo_tipo: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True
    )
    
    # Capacity
    capacidade_horas: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True
    )
    
    funcionarios_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )


# ============================================================================
# MOLD (Moldes)
# ============================================================================

class CuratedMold(QuarantineMixin, Base):
    """
    Mold master data.
    
    Business key: molde_id
    """
    
    __tablename__ = "mold"
    __table_args__ = (
        Index("ix_curated_mold_ingestion", "ingestion_id"),
        Index("ix_curated_mold_id", "molde_id"),
        {"schema": "factory_curated"},
    )
    
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    
    ingestion_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("factory_meta.ingestion_run.id"),
        nullable=False
    )
    
    molde_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    
    molde_nome: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    modelo_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )
    
    tamanho_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )
    
    tipo: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )
    
    # Status
    estado: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )
    
    em_manutencao: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )
    
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )


# ============================================================================
# MOLD USAGE (Uso de Moldes)
# ============================================================================

class CuratedMoldUsage(QuarantineMixin, Base):
    """
    Mold assignments to orders/phases.
    
    Business key: (molde_id, of_id, fase_id)
    """
    
    __tablename__ = "mold_usage"
    __table_args__ = (
        Index("ix_curated_mold_usage_ingestion", "ingestion_id"),
        Index("ix_curated_mold_usage_molde", "molde_id"),
        Index("ix_curated_mold_usage_of", "of_id"),
        {"schema": "factory_curated"},
    )
    
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    
    ingestion_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("factory_meta.ingestion_run.id"),
        nullable=False
    )
    
    molde_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    
    of_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    
    fase_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )
    
    data_uso: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True
    )
    
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )


# ============================================================================
# QUALITY EVENT (Eventos de Qualidade / Erros)
# ============================================================================

class CuratedQualityEvent(QuarantineMixin, Base):
    """
    Quality events/errors by phase/order.
    
    Business key: (of_id, fase_id, erro_tipo, data_evento)
    """
    
    __tablename__ = "quality_event"
    __table_args__ = (
        Index("ix_curated_quality_event_ingestion", "ingestion_id"),
        Index("ix_curated_quality_event_of", "of_id"),
        Index("ix_curated_quality_event_fase", "fase_id"),
        {"schema": "factory_curated"},
    )
    
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    
    ingestion_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("factory_meta.ingestion_run.id"),
        nullable=False
    )
    
    of_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    
    fase_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )
    
    erro_tipo: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    
    erro_descricao: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    quantidade: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1
    )
    
    data_evento: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True
    )
    
    molde_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )
    
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )


# ============================================================================
# SKILL MATRIX (Matriz de Competências) — PII
# ============================================================================

class CuratedSkillMatrix(QuarantineMixin, Base):
    """
    Employee × Phase skills.
    
    PII WARNING: Contains employee identifiers.
    Access restricted by RBAC.
    
    Business key: (funcionario_id, fase_id)
    """
    
    __tablename__ = "skill_matrix"
    __table_args__ = (
        Index("ix_curated_skill_matrix_ingestion", "ingestion_id"),
        Index("ix_curated_skill_matrix_funcionario", "funcionario_id"),
        Index("ix_curated_skill_matrix_fase", "fase_id"),
        {"schema": "factory_curated"},
    )
    
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    
    ingestion_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("factory_meta.ingestion_run.id"),
        nullable=False
    )
    
    # PII: Employee ID
    funcionario_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    
    # PII: Employee name (optional, prefer ID only)
    funcionario_nome: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    fase_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    
    fase_nome: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    # Skill level
    apto: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )
    
    nivel: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )


# ============================================================================
# COST REFERENCE (Custos por Hora) — SENSITIVE
# ============================================================================

class CuratedCostReference(QuarantineMixin, Base):
    """
    Cost per hour/center.

    SENSITIVE: Cost data requires explicit authorization.
    Access restricted by RBAC.

    Business key: (centro_custo, periodo)

    DEPRECATED (Sprint Q.8 Fase 4): the source `Folha_IA_extra.xlsx`
    has no cost-per-hour sheet, so this table is never populated. Cost
    targets and per-hour values now live in `TenantConfig` under the
    `cost.*` namespace (see `dashboard_metrics_service`). The ORM is
    kept to avoid breaking existing migrations/imports — drop in a
    future sprint after confirming no downstream consumers grew up
    around it.
    """
    
    __tablename__ = "cost_reference"
    __table_args__ = (
        Index("ix_curated_cost_reference_ingestion", "ingestion_id"),
        Index("ix_curated_cost_reference_centro", "centro_custo"),
        {"schema": "factory_curated"},
    )
    
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    
    ingestion_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("factory_meta.ingestion_run.id"),
        nullable=False
    )
    
    centro_custo: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    
    fase_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )
    
    periodo: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True
    )
    
    # SENSITIVE: Cost value
    valor_hora_eur: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True
    )
    
    moeda: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="EUR"
    )

    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )


# ============================================================================
# ALLOCATION (Funcionarios × Fase Ordem Fabrico) — Sprint Q.8 Fase 2
# ============================================================================
# Source: Excel sheet `FuncionariosFaseOrdemFabrico` — 423,769 rows
# representing the historical pairing of WHO worked on WHICH phase of WHICH
# order. Required for: workforce utilization reports, per-worker phase
# history (used by `EmployeeExtrasService` and `worker_ranking_service`),
# and pair-rate analytics that drive `PAIR_REQUIRED_PHASES`.
# Excel only carries 3 fields (FaseOfId, FuncionarioId, Chefe); hours are
# derived downstream by joining with `CuratedOrderPhase.horas_reais` and
# splitting across the workers allocated to the same fase_of_id.

class CuratedAllocation(QuarantineMixin, Base):
    """
    Historical worker × order-phase allocation.

    PII WARNING: contains employee identifier — RBAC restricted.
    Business key: (fase_of_id, funcionario_id)
    """

    __tablename__ = "allocation"
    __table_args__ = (
        Index("ix_curated_allocation_ingestion", "ingestion_id"),
        Index("ix_curated_allocation_fase_of", "fase_of_id"),
        Index("ix_curated_allocation_funcionario", "funcionario_id"),
        Index(
            "ix_curated_allocation_composite",
            "fase_of_id",
            "funcionario_id",
        ),
        {"schema": "factory_curated"},
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    ingestion_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("factory_meta.ingestion_run.id"),
        nullable=False,
    )

    # FK → CuratedOrderPhase.fase_of_id (the row in the order-phase grid).
    # NOT a hard FK because the loaders for the two tables are independent
    # and we want partial ingest to still land allocation rows.
    fase_of_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # PII: ERP employee code (string-cast for cross-sheet join consistency).
    funcionario_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # True when this worker was the leader (`Chefe`) of the pair / crew.
    # Single-worker phases still set this to True for the lone worker.
    is_chefe: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


# ============================================================================
# MODELO (Catálogo de Produtos) — Sprint Q.8 Fase 3
# ============================================================================
# Source: Excel sheet `Modelos` — 899 rows. Note: the sheet is named
# "Modelos" but its rows are the product catalogue (with `Produto_*`
# prefixes); each product row links to a `ModeloId` + `TamanhoId`. We
# keep the curated table named `modelo` because that's the stable
# planning concept (a model can have many products / sizes), and store
# the per-product attributes as nullable columns so the dimension is
# self-contained.

class CuratedModelo(QuarantineMixin, Base):
    """
    Product / model dimension.

    Business key: produto_id (the ERP `Produto_Id`).
    """

    __tablename__ = "modelo"
    __table_args__ = (
        Index("ix_curated_modelo_ingestion", "ingestion_id"),
        Index("ix_curated_modelo_produto", "produto_id"),
        Index("ix_curated_modelo_modelo_id", "modelo_id"),
        {"schema": "factory_curated"},
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    ingestion_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("factory_meta.ingestion_run.id"),
        nullable=False,
    )

    # Business key: ERP Produto_Id (one row per product variant).
    produto_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    produto_nome: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Parent model + size dimensions (denormalised; no FK because the
    # matching dimension tables don't exist yet — Sprint Q.8 only
    # materialises the catalogue, not the model/size sub-dims).
    modelo_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    tamanho_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Physical / process attributes used by planners and quality.
    peso_desmolde_kg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 3),
        nullable=True,
    )

    peso_acabamento_kg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 3),
        nullable=True,
    )

    qtd_gel_deck: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 3),
        nullable=True,
    )

    qtd_gel_casco: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 3),
        nullable=True,
    )

    numero_pocos_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


