"""
ProdPlan ONE - Outbox Models
============================

SQLAlchemy models for Outbox Pattern.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import String, Integer, Text, DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import Base


class EventOutbox(Base):
    """
    Outbox table for storing events before publishing to Kafka.
    
    Implements Outbox Pattern for exactly-once delivery:
    - Events are written to this table within the same transaction as business data
    - A separate dispatcher job publishes events to Kafka
    - UNIQUE constraint on (tenant_id, aggregate_id, event_type) ensures idempotency
    """
    
    __tablename__ = "event_outbox"
    
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    aggregate_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    __table_args__ = (
        {"postgresql_indexes": [
            {"name": "idx_event_outbox_pending", "postgresql_where": "status = 'pending'"}
        ]},
    )


class EventDLQ(Base):
    """
    Dead Letter Queue for events that failed to publish after max retries.
    
    Events are moved here after retry_count >= 5.
    """
    
    __tablename__ = "event_dlq"
    
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    event_outbox_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), 
        nullable=False,
        index=True
    )
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    retry_attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

