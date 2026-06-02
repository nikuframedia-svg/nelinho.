"""Q.157.E — Overlay de execução de operações do plano LIVE.

A fila do operador (``/operador``) passou a ler do plano LIVE do CPO
(``plan_schedule_commits.operations`` — Q.157.D), que é **imutável** (hash-chain
de auditoria). Não se pode escrever o progresso real (COMECEI/ACABEI) dentro do
commit sem o corromper.

Esta tabela é um *overlay* leve, desacoplado do commit: regista o estado de
execução de cada operação (por ``operation_id`` do commit) sem tocar no plano.
A fila junta (LEFT) o plano com este overlay para mostrar ``status``/``actual_*``;
sem linha → ``SCHEDULED`` honesto.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class OperationExecution(TenantBase):
    """Estado de execução real de uma operação do plano LIVE (Q.157.E)."""

    __tablename__ = "operation_execution"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "operation_id",
            name="uq_operation_execution_op",
        ),
        {"schema": "plan"},
    )

    # Handle da operação no commit LIVE (decoder `operation_id`, string estável).
    operation_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    # OF / nº barco (= legacy_id), para audit/leitura.
    order_id: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    # Operador (employee_code) que executou — o que vive em `op["workers"]`.
    worker_code: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    # Proveniência: o commit de onde a operação foi lida.
    commit_sha256: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="SCHEDULED",
    )
    actual_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    actual_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    actual_quantity: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 6), nullable=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<OperationExecution op={self.operation_id} "
            f"status={self.status} worker={self.worker_code}>"
        )
