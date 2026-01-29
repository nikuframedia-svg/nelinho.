"""
META Models — Contrato 010
==========================

Factory Meta Schema:
- ingestion_run: tracks each ingestion attempt
- active_run: singleton pointing to active ingestion
- quality_check_result: individual check results

CRITICAL: These tables control data visibility and audit.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    BigInteger,
    Boolean,
    DateTime,
    Enum as SQLEnum,
    Index,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.database import Base


# ============================================================================
# ENUMS
# ============================================================================

class SourceType(str, Enum):
    """How the file was received."""
    UPLOAD = "upload"       # Manual upload via API
    WATCHER = "watcher"     # File watcher detected
    SCHEDULE = "schedule"   # Scheduled import


class IngestionStatus(str, Enum):
    """Status of an ingestion run."""
    RECEIVED = "received"       # File received, not yet processed
    VALIDATING = "validating"   # Running quality gates
    FAILED = "failed"           # Quality gates failed (blocking)
    CURATING = "curating"       # Transforming to curated
    SUCCEEDED = "succeeded"     # Successfully processed
    SKIPPED = "skipped"         # Skipped (duplicate)


class QualityGateStatus(str, Enum):
    """Overall quality gate status."""
    PENDING = "pending"     # Not yet run
    PASSED = "passed"       # All blocking checks passed
    FAILED = "failed"       # At least one blocking check failed


class CheckSeverity(str, Enum):
    """Severity of a quality check."""
    BLOCKING = "blocking"   # Fails ingestion if not passed
    WARNING = "warning"     # Logged but doesn't fail
    INFO = "info"           # Informational only


# ============================================================================
# SQLALCHEMY MODELS
# ============================================================================

class IngestionRun(Base):
    """
    Tracks each ingestion attempt.
    
    CRITICAL: This is the core audit table.
    Every piece of data traces back to an ingestion_run.
    """
    
    __tablename__ = "ingestion_run"
    __table_args__ = (
        Index("ix_ingestion_run_file_sha256", "file_sha256"),
        Index("ix_ingestion_run_status", "status"),
        Index("ix_ingestion_run_created_at", "created_at_utc"),
        {"schema": "factory_meta"},
    )
    
    # PK
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    
    # Timestamp
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    
    # Who created
    created_by: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    # Source
    source_type: Mapped[SourceType] = mapped_column(
        SQLEnum(SourceType),
        nullable=False
    )
    
    # File info
    file_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )
    
    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False
    )
    
    file_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False
    )
    
    # Status
    status: Mapped[IngestionStatus] = mapped_column(
        SQLEnum(IngestionStatus),
        nullable=False,
        default=IngestionStatus.RECEIVED
    )
    
    # Idempotency: if this is a duplicate, point to original
    duplicate_of_ingestion_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("factory_meta.ingestion_run.id"),
        nullable=True
    )
    
    # Quality
    quality_gate_status: Mapped[QualityGateStatus] = mapped_column(
        SQLEnum(QualityGateStatus),
        nullable=False,
        default=QualityGateStatus.PENDING
    )
    
    quality_report_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True
    )
    
    # Notes
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    # Stats
    total_rows_raw: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )
    
    total_rows_curated: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )
    
    # Timing
    started_at_utc: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    completed_at_utc: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    duration_seconds: Mapped[Optional[float]] = mapped_column(
        nullable=True
    )
    
    # Relationships
    quality_checks: Mapped[List["QualityCheckResult"]] = relationship(
        "QualityCheckResult",
        back_populates="ingestion_run",
        cascade="all, delete-orphan",
    )


class ActiveRun(Base):
    """
    Singleton table pointing to the active ingestion.
    
    CRITICAL: This is how we do logical rollback.
    - To rollback: UPDATE active_ingestion_id to a previous run
    - All views filter by active_ingestion_id
    - RAW data is never deleted
    """
    
    __tablename__ = "active_run"
    __table_args__ = {"schema": "factory_meta"}
    
    # Singleton ID (always 1)
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        default=1
    )
    
    # Active ingestion
    active_ingestion_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("factory_meta.ingestion_run.id"),
        nullable=False
    )
    
    # When activated
    activated_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    
    # Who activated
    activated_by: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )


class ActivationHistory(Base):
    """
    History of activations for audit.
    
    Every time active_run changes, we record it here.
    """
    
    __tablename__ = "activation_history"
    __table_args__ = (
        Index("ix_activation_history_ingestion", "ingestion_id"),
        {"schema": "factory_meta"},
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
    
    activated_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    
    activated_by: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    deactivated_at_utc: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    deactivated_by: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )


class QualityCheckResult(Base):
    """
    Individual quality check result.
    
    Each check is recorded with:
    - check_id: stable identifier (e.g., "required_sheets_present")
    - severity: blocking, warning, or info
    - passed: True/False
    - details_json: specific details about the check
    """
    
    __tablename__ = "quality_check_result"
    __table_args__ = (
        Index("ix_quality_check_ingestion", "ingestion_id"),
        Index("ix_quality_check_check_id", "check_id"),
        {"schema": "factory_meta"},
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
    
    check_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    
    severity: Mapped[CheckSeverity] = mapped_column(
        SQLEnum(CheckSeverity),
        nullable=False
    )
    
    passed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False
    )
    
    details_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True
    )
    
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    
    # Relationship
    ingestion_run: Mapped["IngestionRun"] = relationship(
        "IngestionRun",
        back_populates="quality_checks",
    )


# ============================================================================
# PYDANTIC SCHEMAS
# ============================================================================

class IngestionRunCreate(BaseModel):
    """Schema for creating an ingestion run."""
    
    source_type: SourceType
    file_name: str
    file_size_bytes: int
    file_sha256: str
    created_by: str


class IngestionRunResponse(BaseModel):
    """Schema for ingestion run response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    created_at_utc: datetime
    created_by: str
    source_type: SourceType
    file_name: str
    file_size_bytes: int
    file_sha256: str
    status: IngestionStatus
    quality_gate_status: QualityGateStatus
    duplicate_of_ingestion_id: Optional[UUID] = None
    total_rows_raw: int
    total_rows_curated: int
    duration_seconds: Optional[float] = None


class ActiveRunResponse(BaseModel):
    """Schema for active run response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    active_ingestion_id: UUID
    activated_at_utc: datetime
    activated_by: str


class QualityCheckResponse(BaseModel):
    """Schema for quality check response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    check_id: str
    severity: CheckSeverity
    passed: bool
    details: Optional[Dict[str, Any]] = None


