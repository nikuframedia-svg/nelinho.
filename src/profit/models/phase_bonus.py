"""
ProdPlan ONE — Phase Bonus Payout
==================================

Houses the per-(product, phase) monetary bonus paid to workers when they
complete that phase for that product. Sourced from the ERP field
`ProdutoFase_CoeficienteX` in `FasesStandardModelos` (15.445 rows).

Historically the code assumed `CoeficienteX` was the second worker's
time — it is not. The CEO confirmed on 2026-04-22 that this field is
the bonus (€) copied into each OF when it's created. This model is the
canonical home for that value going forward (Sprint A / CX4).

Downstream uses:
  * `src/profit/services/cost_service.py` — CS01 worker cost per part
  * payroll aggregation per worker per period
  * CS03 margin calculation (revenue − labor − materials − shipping)
"""

from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class PhaseBonusPayout(TenantBase):
    """Monetary bonus paid per (product × phase) — ERP CoeficienteX."""

    __tablename__ = "phase_bonus_payout"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "product_id", "phase_id", "valid_from",
            name="uq_phase_bonus_payout_validity",
        ),
        {"schema": "profit"},
    )

    product_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("core.products.id"),
        nullable=False,
    )
    phase_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
    )

    bonus_eur: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
    )
    currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="EUR",
    )

    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="ERP_STANDARD",
    )
