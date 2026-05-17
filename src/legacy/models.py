"""ProdPlan ONE — Legacy models (Sprint Q.22.C).

Models backing the ``/api/*`` compatibility endpoints.

:class:`ProductionError` maps the Nelo ERP quality-defect rows (the ERP
records ~89.836 defects against phases of production orders). One row
per defect detected at a phase. ``order_id`` is intentionally a bare
UUID with **no FK constraint** — consistent with ``ProductionOrder`` —
so the ERP ingest can land error rows even when the owning order has
not yet been migrated to Postgres.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class ProductionError(TenantBase):
    """A quality defect recorded against a production-order phase.

    ``severity`` follows the ERP's 1-3 scale: 1=minor, 2=major,
    3=critical (H3 in HANDOFF — gravity scale is an unconfirmed
    hypothesis but matches the frontend ``severityLabel`` contract).

    ``phase_name`` is the phase where the defect was *produced*;
    ``eval_phase_name`` is where it was *detected* — in the NELO domain
    96.4% of defects are caught at Desmolde, so the two often differ.
    """

    __tablename__ = "production_errors"
    __table_args__ = (
        Index("ix_production_errors_tenant_order", "tenant_id", "order_id"),
        Index("ix_production_errors_tenant_severity", "tenant_id", "severity"),
        Index("ix_production_errors_tenant_phase", "tenant_id", "phase_name"),
        {"schema": "plan"},
    )

    # No FK — the order may not be migrated yet (see module docstring).
    order_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True,
    )
    phase_name: Mapped[str] = mapped_column(String(255), nullable=False)
    eval_phase_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[int] = mapped_column(Integer, nullable=False)

    def __repr__(self) -> str:
        return f"<ProductionError sev={self.severity} {self.phase_name}>"
