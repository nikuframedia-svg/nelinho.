"""
ProdPlan ONE - Digital Twin Models
==================================

SQLAlchemy models for persisting Twin scenarios.

Replaces in-memory scenarios_store with database-backed storage.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    Integer,
    Float,
    Boolean,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.database import TenantBase

import enum


class ScenarioStatus(str, enum.Enum):
    """Status of a scenario."""
    DRAFT = "draft"
    SIMULATING = "simulating"
    SIMULATED = "simulated"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    ERROR = "error"


class Scenario(TenantBase):
    """
    Digital Twin Scenario.
    
    Represents a "what-if" scenario with deltas applied to baseline state.
    """
    
    __tablename__ = "twin_scenarios"
    __table_args__ = (
        Index("ix_twin_scenarios_tenant_status", "tenant_id", "status"),
        Index("ix_twin_scenarios_created_at", "created_at"),
        {"schema": "twin"},
    )
    
    # Identity
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ScenarioStatus.DRAFT.value,
    )
    
    # Relationships
    base_scenario_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("twin.twin_scenarios.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Baseline state snapshot (from Factory Data Product)
    baseline_state: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    baseline_ingestion_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="Factory Data Product ingestion_id used for baseline",
    )
    
    # Simulation result
    simulation_result: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    simulated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Hash for reproducibility
    scenario_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="SHA256 hash of baseline + deltas for reproducibility",
    )
    
    # Audit
    created_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Relationships
    deltas: Mapped[List["ScenarioDelta"]] = relationship(
        "ScenarioDelta",
        back_populates="scenario",
        cascade="all, delete-orphan",
        order_by="ScenarioDelta.sequence",
        lazy="selectin",
    )
    
    def __repr__(self) -> str:
        return f"<Scenario(id={self.id}, title={self.title}, status={self.status})>"


class ScenarioDelta(TenantBase):
    """
    Delta (change) applied to a scenario.
    
    Each delta represents a modification to the baseline state.
    """
    
    __tablename__ = "twin_scenario_deltas"
    __table_args__ = (
        Index("ix_twin_deltas_scenario", "scenario_id"),
        {"schema": "twin"},
    )
    
    # Parent scenario
    scenario_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("twin.twin_scenarios.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Delta definition
    sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Order in which deltas are applied",
    )
    entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type of entity being modified (standard_time, capacity, etc.)",
    )
    entity_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Identifier of the entity being modified",
    )
    patch: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Changes to apply to the entity",
    )
    
    # Metadata
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    applied_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Relationship
    scenario: Mapped["Scenario"] = relationship(
        "Scenario",
        back_populates="deltas",
    )
    
    def __repr__(self) -> str:
        return f"<ScenarioDelta(id={self.id}, entity_type={self.entity_type}, entity_key={self.entity_key})>"


class ScenarioComparison(TenantBase):
    """
    Comparison between two scenarios.
    
    Stores the results of comparing scenario KPIs.
    """
    
    __tablename__ = "twin_scenario_comparisons"
    __table_args__ = (
        Index("ix_twin_comparisons_scenarios", "scenario_id", "baseline_scenario_id"),
        {"schema": "twin"},
    )
    
    # Scenarios being compared
    scenario_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("twin.twin_scenarios.id", ondelete="CASCADE"),
        nullable=False,
    )
    baseline_scenario_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("twin.twin_scenarios.id", ondelete="SET NULL"),
        nullable=True,
        comment="If null, comparison is against factory baseline",
    )
    
    # Comparison results
    comparison_result: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    
    # KPI deltas
    kpi_deltas: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Delta for each KPI (scenario - baseline)",
    )
    
    # Metadata
    compared_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
    compared_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    def __repr__(self) -> str:
        return f"<ScenarioComparison(scenario={self.scenario_id}, baseline={self.baseline_scenario_id})>"

