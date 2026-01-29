"""
RAW Models — Contrato 010
=========================

Factory Raw Schema:
- excel_row: generic table to capture any Excel sheet

CRITICAL: RAW is APPEND-ONLY.
- Never UPDATE
- Never DELETE
- All historical data is preserved
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    DateTime,
    Index,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import Base


class ExcelRow(Base):
    """
    Generic RAW storage for Excel data.
    
    APPEND-ONLY: This table is never updated or deleted.
    
    Each row captures:
    - Which ingestion it came from
    - Which sheet
    - Which row number
    - Row hash for deduplication
    - Business key hash for fast lookups
    - Full payload as JSON
    
    This design allows:
    - Any Excel schema to be captured
    - Schema evolution without migrations
    - Full audit trail
    - Idempotent re-processing
    """
    
    __tablename__ = "excel_row"
    __table_args__ = (
        # Primary index for filtering by ingestion
        Index("ix_excel_row_ingestion", "ingestion_id"),
        # Composite index for sheet queries
        Index("ix_excel_row_ingestion_sheet", "ingestion_id", "sheet_name"),
        # Business key lookup (when available)
        Index("ix_excel_row_business_key", "ingestion_id", "business_key_sha256"),
        # Row hash for deduplication
        Index("ix_excel_row_hash", "row_sha256"),
        {"schema": "factory_raw"},
    )
    
    # Composite PK: ingestion + sheet + row_number
    # This ensures uniqueness within an ingestion
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    
    # Which ingestion this row belongs to
    ingestion_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("factory_meta.ingestion_run.id"),
        nullable=False
    )
    
    # Source sheet name (as-is from Excel)
    sheet_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    # Row number (1-based, as in Excel)
    row_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    
    # SHA256 of the entire row payload
    row_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False
    )
    
    # SHA256 of business key fields (if identifiable)
    # NULL if sheet doesn't have a clear business key
    business_key_sha256: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True
    )
    
    # The actual data as JSONB
    # Format: {"col_name": value, ...}
    # Values are normalized: strings, numbers, nulls, booleans
    payload_json: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False
    )
    
    # When this row was ingested
    ingested_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )


# ============================================================================
# PYDANTIC SCHEMAS
# ============================================================================

class ExcelRowCreate(BaseModel):
    """Schema for creating an Excel row."""
    
    ingestion_id: UUID
    sheet_name: str
    row_number: int
    row_sha256: str
    business_key_sha256: Optional[str] = None
    payload_json: Dict[str, Any]


class ExcelRowResponse(BaseModel):
    """Schema for Excel row response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    ingestion_id: UUID
    sheet_name: str
    row_number: int
    row_sha256: str
    business_key_sha256: Optional[str] = None
    payload_json: Dict[str, Any]
    ingested_at_utc: datetime


