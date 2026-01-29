"""
ProdPlan ONE - Partner Models
==============================

Customers and Suppliers.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID

from sqlalchemy import String, Numeric, Integer, Enum as SQLEnum, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class CustomerSegment(str, Enum):
    """Customer segment classification."""
    RETAIL = "RETAIL"
    WHOLESALE = "WHOLESALE"
    BULK = "BULK"
    OEM = "OEM"
    DISTRIBUTOR = "DISTRIBUTOR"


class PaymentTerms(str, Enum):
    """Payment terms."""
    PREPAID = "PREPAID"
    NET15 = "NET15"
    NET30 = "NET30"
    NET45 = "NET45"
    NET60 = "NET60"
    NET90 = "NET90"


class PriceTier(str, Enum):
    """Price tier for customers."""
    ECONOMY = "ECONOMY"
    STANDARD = "STANDARD"
    PREMIUM = "PREMIUM"
    VIP = "VIP"


class Customer(TenantBase):
    """
    Customer entity.
    
    Represents buyers of finished goods.
    """
    
    __tablename__ = "customers"
    __table_args__ = {"schema": "core"}
    
    # Identification
    customer_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Classification
    segment: Mapped[CustomerSegment] = mapped_column(
        SQLEnum(CustomerSegment, name="customer_segment"),
        default=CustomerSegment.RETAIL,
        nullable=False,
    )
    
    # Terms
    payment_terms: Mapped[PaymentTerms] = mapped_column(
        SQLEnum(PaymentTerms, name="payment_terms"),
        default=PaymentTerms.NET30,
        nullable=False,
    )
    price_tier: Mapped[PriceTier] = mapped_column(
        SQLEnum(PriceTier, name="price_tier"),
        default=PriceTier.STANDARD,
        nullable=False,
    )
    
    # Credit
    credit_limit: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    
    # Contact
    contact_name: Mapped[Optional[str]] = mapped_column(String(255))
    contact_email: Mapped[Optional[str]] = mapped_column(String(255))
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Address
    address_line1: Mapped[Optional[str]] = mapped_column(String(255))
    address_line2: Mapped[Optional[str]] = mapped_column(String(255))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    postal_code: Mapped[Optional[str]] = mapped_column(String(20))
    country: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Active
    is_active: Mapped[bool] = mapped_column(default=True)
    
    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text)
    
    def __repr__(self) -> str:
        return f"<Customer {self.customer_code}: {self.customer_name}>"


class MaterialCategory(str, Enum):
    """Material category for suppliers."""
    STEEL = "STEEL"
    WOOD = "WOOD"
    PACKAGING = "PACKAGING"
    CONSUMABLES = "CONSUMABLES"
    COMPONENTS = "COMPONENTS"
    OTHER = "OTHER"


class Supplier(TenantBase):
    """
    Supplier entity.
    
    Represents vendors of raw materials and components.
    """
    
    __tablename__ = "suppliers"
    __table_args__ = {"schema": "core"}
    
    # Identification
    supplier_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    supplier_name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Classification
    material_category: Mapped[MaterialCategory] = mapped_column(
        SQLEnum(MaterialCategory, name="material_category"),
        default=MaterialCategory.OTHER,
        nullable=False,
    )
    
    # Lead time
    lead_time_days: Mapped[int] = mapped_column(Integer, default=7)
    
    # Terms
    payment_terms: Mapped[PaymentTerms] = mapped_column(
        SQLEnum(PaymentTerms, name="payment_terms"),
        default=PaymentTerms.NET30,
        nullable=False,
    )
    
    # Contact
    contact_name: Mapped[Optional[str]] = mapped_column(String(255))
    contact_email: Mapped[Optional[str]] = mapped_column(String(255))
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Address
    address_line1: Mapped[Optional[str]] = mapped_column(String(255))
    address_line2: Mapped[Optional[str]] = mapped_column(String(255))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    postal_code: Mapped[Optional[str]] = mapped_column(String(20))
    country: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Quality rating (1-5)
    quality_rating: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Active
    is_active: Mapped[bool] = mapped_column(default=True)
    is_preferred: Mapped[bool] = mapped_column(default=False)
    
    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text)
    
    def __repr__(self) -> str:
        return f"<Supplier {self.supplier_code}: {self.supplier_name}>"










