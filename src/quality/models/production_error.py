"""Q.61.32d — `ProductionError` movido de src/legacy/models.py.

Mantém o mesmo `__tablename__` e schema (`plan.production_errors`)
para preservar a tabela existente; só o caminho de import muda.

Origem do model: Sprint Q.22.C. Os ERP records ~89.836 defeitos
contra fases de production orders; uma linha por defeito detectado
numa fase. `order_id` é UUID sem FK — consistente com `ProductionOrder`
— para o ingest ERP landar defeitos antes da migration completa da
ordem para Postgres.
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
