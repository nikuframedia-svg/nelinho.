"""
ProdPlan ONE - Rate Models
===========================

Cost rates for labor, machines, and overhead.
Used by PROFIT module for COGS calculations.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import String, Numeric, Date, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class LaborRate(TenantBase):
    """
    Labor Rate entity.
    
    Defines hourly cost rates for employees.
    Supports time-phased rates with effective dates.
    """
    
    __tablename__ = "labor_rates"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "employee_id", "effective_date",
            name="uq_labor_rate_employee_date"
        ),
        {"schema": "core"},
    )
    
    # Employee reference
    employee_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("core.employees.id"),
        nullable=False,
        index=True,
    )
    
    # Effective date
    effective_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    valid_until: Mapped[Optional[date]] = mapped_column(Date)
    
    # Base hourly rate
    base_hourly_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 8),
        nullable=False,
    )
    
    # Burden rate (social charges, benefits %)
    burden_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        default=Decimal("0.32"),
    )
    
    # Calculated loaded rate (stored for performance)
    loaded_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 8),
        nullable=False,
    )
    
    # Currency
    currency_code: Mapped[str] = mapped_column(String(3), default="EUR")
    
    # Notes
    notes: Mapped[Optional[str]] = mapped_column(String(500))
    
    def __repr__(self) -> str:
        return f"<LaborRate {self.employee_id}: {self.loaded_rate}/h from {self.effective_date}>"
    
    @classmethod
    def calculate_loaded_rate(cls, base_rate: Decimal, burden_rate: Decimal) -> Decimal:
        """Calculate loaded rate from base and burden."""
        return base_rate * (1 + burden_rate)


class MachineRate(TenantBase):
    """
    Machine Rate entity.
    
    Defines hourly cost rates for machines.
    Includes depreciation, energy, and maintenance components.
    """
    
    __tablename__ = "machine_rates"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "machine_id", "effective_date",
            name="uq_machine_rate_machine_date"
        ),
        {"schema": "core"},
    )
    
    # Machine reference
    machine_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("core.machines.id"),
        nullable=False,
        index=True,
    )
    
    # Effective date
    effective_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    valid_until: Mapped[Optional[date]] = mapped_column(Date)
    
    # Cost components (per hour)
    depreciation_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 8),
        default=Decimal("0"),
    )
    energy_cost_per_hour: Mapped[Decimal] = mapped_column(
        Numeric(18, 8),
        default=Decimal("0"),
    )
    maintenance_cost_per_hour: Mapped[Decimal] = mapped_column(
        Numeric(18, 8),
        default=Decimal("0"),
    )
    
    # Calculated total rate (stored for performance)
    total_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 8),
        nullable=False,
    )
    
    # Currency
    currency_code: Mapped[str] = mapped_column(String(3), default="EUR")
    
    # Notes
    notes: Mapped[Optional[str]] = mapped_column(String(500))
    
    def __repr__(self) -> str:
        return f"<MachineRate {self.machine_id}: {self.total_rate}/h from {self.effective_date}>"
    
    @classmethod
    def calculate_total_rate(
        cls,
        depreciation: Decimal,
        energy: Decimal,
        maintenance: Decimal,
    ) -> Decimal:
        """Calculate total rate from components."""
        return depreciation + energy + maintenance


class OverheadRate(TenantBase):
    """
    Overhead Rate entity.
    
    Defines factory overhead allocation rate per production hour.
    Calculated from monthly overhead / available production hours.
    """
    
    __tablename__ = "overhead_rates"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "year_month",
            name="uq_overhead_rate_period"
        ),
        {"schema": "core"},
    )
    
    # Period (first day of month)
    year_month: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    # Monthly overhead components
    rent_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        default=Decimal("0"),
    )
    utilities_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        default=Decimal("0"),
    )
    management_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        default=Decimal("0"),
    )
    other_overhead_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        default=Decimal("0"),
    )
    
    # Total monthly overhead
    total_monthly_overhead: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )
    
    # Available production hours
    total_available_hours: Mapped[int] = mapped_column(nullable=False)
    
    # Calculated rate per hour
    calculated_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 8),
        nullable=False,
    )
    
    # Currency
    currency_code: Mapped[str] = mapped_column(String(3), default="EUR")
    
    # Notes
    notes: Mapped[Optional[str]] = mapped_column(String(500))
    
    def __repr__(self) -> str:
        return f"<OverheadRate {self.year_month}: {self.calculated_rate}/h>"
    
    @classmethod
    def calculate_rate(cls, total_overhead: Decimal, available_hours: int) -> Decimal:
        """Calculate overhead rate per hour."""
        if available_hours > 0:
            return total_overhead / available_hours
        return Decimal("0")


