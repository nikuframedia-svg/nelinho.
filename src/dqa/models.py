"""
ProdPlan ONE - DQA Models
=========================

SQLAlchemy models for Data Quality Autopilot.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Float, String, Integer, Text, DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class TrustIndexSnapshot(TenantBase):
    """
    Historical snapshots of TrustIndex for entities.
    
    Tracks TrustIndex over time for auditing and trend analysis.
    """
    
    __tablename__ = "trust_index_snapshots"
    __table_args__ = {"schema": "dqa"}
    
    entity_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    trust_index: Mapped[float] = mapped_column(Float, nullable=False)
    components: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Metadata
    issues_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    repair_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class DataQualityIssue(TenantBase):
    """
    Detected data quality issues.
    
    Tracks issues found during TrustIndex evaluation.
    """
    
    __tablename__ = "data_quality_issues"
    __table_args__ = {"schema": "dqa"}
    
    entity_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    
    issue_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "missing_field", "out_of_range", "latency"
    field_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    issue_description: Mapped[str] = mapped_column(Text, nullable=False)
    
    # severity values are populated from OFCH_GRAVIDADE via the
    # mapping in factory_data_product/ingest/gravidade.py
    # (1→"low", 2→"medium", 3→"high"); confirmed with NELO CEO 2026-04-26.
    # (Comment refresh — Onda 3.4: file moved out of curated_transformer.py.)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")  # "low", "medium", "high"
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class AutoRepairLog(TenantBase):
    """
    Log of auto-repair actions.
    
    Tracks repairs applied by AutoRepairEngine.
    """
    
    __tablename__ = "auto_repair_logs"
    __table_args__ = {"schema": "dqa"}
    
    entity_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    
    trust_index_before: Mapped[float] = mapped_column(Float, nullable=False)
    trust_index_after: Mapped[float] = mapped_column(Float, nullable=False)
    
    repair_actions: Mapped[dict] = mapped_column(JSONB, nullable=False)  # List of repair actions
    
    # Metadata
    repair_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)










