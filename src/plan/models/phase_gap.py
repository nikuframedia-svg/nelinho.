"""
ProdPlan ONE — Phase Transition Gap (curing / drying constraints)
===================================================================

16 transitions in the Nelo routing graph require a **mandatory minimum
wait** between two consecutive phases — resin cure, paint dry, glue set.
These are physical constraints, NOT queue time to minimise: scheduling a
lamination-to-curing step in 0h creates a plan that can't exist.

Source: Blueprint v2.0 §3.8 (CPO). Each row is derived from the
historical modal gap between predecessor end and successor start for
every transition with n_observations ≥ 100.

The decoder and CP-SAT constraint builder both consume this table
through `FactoryState.phase_transition_gaps`.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class PhaseTransitionGap(TenantBase):
    """Mandatory minimum wait between two consecutive phases."""

    __tablename__ = "phase_transition_gap"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "from_phase_code", "to_phase_code",
            name="uq_phase_transition_gap_pair",
        ),
        {"schema": "plan"},
    )

    from_phase_code: Mapped[str] = mapped_column(String(64), nullable=False)
    to_phase_code: Mapped[str] = mapped_column(String(64), nullable=False)

    min_gap_hours: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
    )

    reason: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    n_observations: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
