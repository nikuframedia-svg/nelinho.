"""
ProdPlan ONE - Tenant Model
============================

Multi-tenancy foundation.
Each tenant represents a separate organization using the system.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from sqlalchemy import String, Enum as SQLEnum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.database import GlobalBase


class TenantStatus(str, Enum):
    """Tenant status."""
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    PENDING = "PENDING"
    CANCELLED = "CANCELLED"


class SubscriptionLevel(str, Enum):
    """Subscription level."""
    STARTER = "STARTER"
    PROFESSIONAL = "PROFESSIONAL"
    ENTERPRISE = "ENTERPRISE"


class Tenant(GlobalBase):
    """
    Tenant entity.
    
    Represents an organization using ProdPlan ONE.
    All other entities are scoped to a tenant.
    """
    
    __tablename__ = "tenants"
    __table_args__ = {"schema": "core"}
    
    # Basic info
    tenant_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    tenant_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
    )
    
    # Status
    status: Mapped[TenantStatus] = mapped_column(
        SQLEnum(TenantStatus, name="tenant_status"),
        default=TenantStatus.PENDING,
        nullable=False,
    )
    
    # Subscription
    subscription_level: Mapped[SubscriptionLevel] = mapped_column(
        SQLEnum(SubscriptionLevel, name="subscription_level"),
        default=SubscriptionLevel.STARTER,
        nullable=False,
    )
    
    # Contact
    contact_email: Mapped[Optional[str]] = mapped_column(String(255))
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Address
    address_line1: Mapped[Optional[str]] = mapped_column(String(255))
    address_line2: Mapped[Optional[str]] = mapped_column(String(255))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    postal_code: Mapped[Optional[str]] = mapped_column(String(20))
    country: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Settings
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    currency_code: Mapped[str] = mapped_column(String(3), default="EUR")
    locale: Mapped[str] = mapped_column(String(10), default="pt-PT")
    
    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text)
    
    # Audit
    activated_at: Mapped[Optional[datetime]] = mapped_column()
    suspended_at: Mapped[Optional[datetime]] = mapped_column()
    
    def __repr__(self) -> str:
        return f"<Tenant {self.tenant_code}: {self.tenant_name}>"
    
    @property
    def is_active(self) -> bool:
        return self.status == TenantStatus.ACTIVE
    
    @property
    def is_enterprise(self) -> bool:
        return self.subscription_level == SubscriptionLevel.ENTERPRISE










