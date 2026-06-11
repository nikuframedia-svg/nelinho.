"""Q.157.E — serviço do overlay de execução (picagem) das operações LIVE.

A fila do operador lê do plano LIVE imutável (Q.157.D). O progresso real
(COMECEI/ACABEI) vive neste overlay (``plan.operation_execution``), não no
commit. Máquina de estados: ausência de linha ≡ ``SCHEDULED`` →
``IN_PROGRESS`` (start) → ``COMPLETED`` (complete). Cada transição escreve
``audit_change`` na MESMA tx (invariante #7).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Iterable, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.governance.audit_service import audit_change
from src.plan.models.operation_execution import OperationExecution
from src.plan.services.scheduling_service import InvalidScheduleTransition

logger = logging.getLogger(__name__)

# Ator de auditoria do tablet (sem login real em dev). Distinto do _SYSTEM_ACTOR
# do auto_propose para o audit trail separar a origem.
_TABLET_ACTOR = UUID("00000000-0000-0000-0000-000000000003")


class OperationExecutionService:
    """Lê/escreve o estado de execução real das operações do plano LIVE."""

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def status_map(
        self, operation_ids: Iterable[str],
    ) -> Dict[str, OperationExecution]:
        """`{operation_id: OperationExecution}` para as ops dadas (batch)."""
        ids: List[str] = sorted({str(o).strip() for o in operation_ids if o})
        if not ids:
            return {}
        rows = (
            await self.session.execute(
                select(OperationExecution).where(
                    OperationExecution.tenant_id == self.tenant_id,
                    OperationExecution.operation_id.in_(ids),
                )
            )
        ).scalars().all()
        return {r.operation_id: r for r in rows}

    async def _get(self, operation_id: str) -> Optional[OperationExecution]:
        return (
            await self.session.execute(
                select(OperationExecution).where(
                    OperationExecution.tenant_id == self.tenant_id,
                    OperationExecution.operation_id == str(operation_id),
                )
            )
        ).scalar_one_or_none()

    async def start(
        self,
        *,
        operation_id: str,
        order_id: str = "",
        worker_code: str = "",
        commit_sha: str = "",
        actual_start: Optional[datetime] = None,
    ) -> OperationExecution:
        """SCHEDULED→IN_PROGRESS (cria a linha se ainda não existir)."""
        when = actual_start or datetime.now(timezone.utc)
        row = await self._get(operation_id)
        if row is None:
            row = OperationExecution(
                tenant_id=self.tenant_id,
                operation_id=str(operation_id),
                order_id=str(order_id or ""),
                worker_code=str(worker_code or ""),
                commit_sha256=str(commit_sha or ""),
                status="IN_PROGRESS",
                actual_start=when,
            )
            self.session.add(row)  # noqa: audit_coverage — audit_change() abaixo (mesma tx, L99)
            action = "INSERT"
        elif row.status == "SCHEDULED":
            row.status = "IN_PROGRESS"
            row.actual_start = when
            action = "UPDATE"
        else:
            raise InvalidScheduleTransition(
                f"Operação {operation_id}: {row.status}→IN_PROGRESS inválido"
            )
        await self.session.flush()
        await audit_change(
            self.session,
            tenant_id=self.tenant_id,
            entity_type="operation_execution",
            entity_id=row.id,
            action=action,
            new_values={
                "operation_id": str(operation_id),
                "order_id": row.order_id,
                "status": "IN_PROGRESS",
                "actual_start": when.isoformat(),
            },
            actor_id=_TABLET_ACTOR,
            reason="Q.157.E operador iniciou operação (plano LIVE)",
        )
        return row

    async def complete(
        self,
        *,
        operation_id: str,
        actual_end: Optional[datetime] = None,
        actual_quantity: Optional[Decimal] = None,
    ) -> OperationExecution:
        """IN_PROGRESS→COMPLETED. 409 se não está IN_PROGRESS / não existe."""
        row = await self._get(operation_id)
        if row is None or row.status != "IN_PROGRESS":
            current = row.status if row is not None else "SCHEDULED"
            raise InvalidScheduleTransition(
                f"Operação {operation_id}: {current}→COMPLETED inválido"
            )
        when = actual_end or datetime.now(timezone.utc)
        row.status = "COMPLETED"
        row.actual_end = when
        if actual_quantity is not None:
            row.actual_quantity = actual_quantity
        await self.session.flush()
        await audit_change(
            self.session,
            tenant_id=self.tenant_id,
            entity_type="operation_execution",
            entity_id=row.id,
            action="UPDATE",
            new_values={
                "operation_id": str(operation_id),
                "status": "COMPLETED",
                "actual_end": when.isoformat(),
                "actual_quantity": (
                    float(actual_quantity) if actual_quantity is not None else None
                ),
            },
            actor_id=_TABLET_ACTOR,
            reason="Q.157.E operador concluiu operação (plano LIVE)",
        )
        return row
