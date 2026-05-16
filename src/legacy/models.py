"""
ProdPlan ONE - Legacy Models
=============================

Models backing the ``/api/*`` compatibility endpoints.

``ProductionError`` maps the Nelo ERP ``OrdemFabricoErros`` table
(~89.836 rows): one row per quality defect recorded against a phase of
a production order. ``order_id`` is intentionally a bare UUID with no
FK constraint — consistent with ``ProductionOrder`` — so the ERP ingest
can land error rows even if the order is not yet migrated.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import Integer, String, Text, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class ProductionError(TenantBase):
    """A quality defect recorded against a production order phase.

    ``severity`` is the ERP's 1-3 scale: 1=minor, 2=major, 3=critical.
    """

    __tablename__ = "production_errors"
    __table_args__ = (
        Index("ix_production_errors_tenant_order", "tenant_id", "order_id"),
        Index("ix_production_errors_tenant_severity", "tenant_id", "severity"),
        Index("ix_production_errors_tenant_phase", "tenant_id", "phase_name"),
        {"schema": "plan"},
    )

    # No FK constraint — order may not be migrated yet (see module docstring).
    order_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    phase_name: Mapped[str] = mapped_column(String(255), nullable=False)
    eval_phase_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[int] = mapped_column(Integer, nullable=False)  # 1=minor 2=major 3=critical

    def __repr__(self) -> str:
        return f"<ProductionError sev={self.severity} {self.phase_name}>"
