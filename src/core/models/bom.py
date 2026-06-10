"""
ProdPlan ONE - BOM Model
=========================

Bill of Materials structure.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import String, Numeric, Integer, ForeignKey, Date, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase
from src.shared.time import local_today


class BOMItem(TenantBase):
    """
    BOM Item entity.
    
    Represents a parent-component relationship in the Bill of Materials.
    Supports multi-level BOMs with effectivity dates.
    """
    
    __tablename__ = "bom_items"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "parent_product_id", "component_product_id", "sequence",
            name="uq_bom_parent_component_seq"
        ),
        {"schema": "core"},
    )
    
    # Parent product
    parent_product_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("core.products.id"),
        nullable=False,
        index=True,
    )
    
    # Component product
    component_product_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("core.products.id"),
        nullable=False,
        index=True,
    )
    
    # Quantity
    quantity_per: Mapped[Decimal] = mapped_column(
        Numeric(18, 6),
        nullable=False,
    )
    
    # Unit of measure
    unit_of_measure: Mapped[str] = mapped_column(String(10), default="UN")
    
    # Sequencing
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    
    # Operation link (which operation consumes this component)
    operation_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("core.operations.id"),
    )
    
    # Scrap factor (e.g., 1.02 = 2% expected scrap)
    scrap_factor: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        default=Decimal("1.0"),
    )
    
    # Effectivity dates
    effective_from: Mapped[Optional[date]] = mapped_column(Date)
    effective_to: Mapped[Optional[date]] = mapped_column(Date)
    
    # BOM version
    bom_version: Mapped[int] = mapped_column(Integer, default=1)
    
    # Position reference (for assembly instructions)
    position_ref: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Notes
    notes: Mapped[Optional[str]] = mapped_column(String(500))
    
    def __repr__(self) -> str:
        return f"<BOMItem {self.parent_product_id} -> {self.component_product_id}: {self.quantity_per}>"
    
    @property
    def quantity_with_scrap(self) -> Decimal:
        """Calculate quantity including scrap allowance."""
        return self.quantity_per * self.scrap_factor
    
    def is_effective(self, as_of_date: date = None) -> bool:
        """Check if BOM item is effective on given date."""
        as_of_date = as_of_date or local_today()
        
        if self.effective_from and as_of_date < self.effective_from:
            return False
        if self.effective_to and as_of_date > self.effective_to:
            return False
        return True










