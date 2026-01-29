"""
ProdPlan ONE - Audit Log Model
===============================

Complete audit trail for all tenant data changes.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import Base


class AuditLog(Base):
    """
    Audit Log entity.
    
    Records all data changes for compliance and debugging.
    Not tenant-scoped (contains tenant_id as data, not filter).
    """
    
    __tablename__ = "audit_log"
    __table_args__ = {"schema": "core"}
    
    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    # Tenant
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    
    # Entity reference
    entity_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    entity_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    
    # Action
    action: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )  # INSERT, UPDATE, DELETE
    
    # Data
    old_values: Mapped[Optional[dict]] = mapped_column(JSONB)
    new_values: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # Actor
    actor_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True))
    actor_role: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Context
    reason: Mapped[Optional[str]] = mapped_column(Text)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )
    
    def __repr__(self) -> str:
        return f"<AuditLog {self.action} {self.entity_type}:{self.entity_id}>"










