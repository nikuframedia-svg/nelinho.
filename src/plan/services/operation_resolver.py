"""Q.55.B — resolução da operação de routing a partir da fase da ordem.

``HRAllocation.operation_id`` é FK obrigatória para ``core.operations``,
mas o dev path nunca semeia essa tabela e os ``ProductionSchedule``
sintéticos raramente cobrem o dia de hoje. Atar a atribuição diária à
existência de um schedule apodrecia todos os dias — 0 das 164 ordens
IN_PROGRESS tinham schedule a cobrir hoje.

Este resolver dá uma linha ``core.operations`` válida para uma fase de
routing, com get-or-create idempotente keyed por ``(tenant_id,
operation_code)``. A criação lazy escreve ``core.audit_log`` na mesma
transacção (invariante "audit trail intact").
"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.operation import Operation
from src.governance.audit_service import audit_change
from src.plan.services.phase_classification import _norm

__all__ = ["OperationResolver", "operation_code_for_phase"]


def operation_code_for_phase(phase_name: str) -> str:
    """Código canónico e estável de ``core.operations`` para uma fase.

    Determinístico: a mesma fase dá sempre o mesmo código, por isso o
    get-or-create nunca duplica. Prefixo ``PHASE_`` para não colidir com
    códigos de operação vindos do ERP. Limitado a 50 chars
    (``Operation.operation_code`` é ``String(50)``).
    """
    norm = _norm(phase_name).replace(" ", "_").replace(".", "")
    return f"PHASE_{norm}".upper()[:50]


class OperationResolver:
    """Get-or-create de ``core.operations`` para uma fase de routing."""

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def resolve_phase_operation(self, phase_name: str) -> Operation:
        """Devolve a ``Operation`` da fase, criando-a se ainda não existir.

        Idempotente: uma segunda chamada para a mesma fase devolve a
        linha existente, sem duplicar. O caller faz o ``commit``.
        """
        code = operation_code_for_phase(phase_name)
        stmt = select(Operation).where(
            Operation.tenant_id == self.tenant_id,
            Operation.operation_code == code,
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            return existing

        # `id` explícito: o caller pode precisar dele (FK da HRAllocation)
        # antes do flush real chegar à BD.
        operation = Operation(
            id=uuid4(),
            tenant_id=self.tenant_id,
            operation_code=code,
            operation_name=phase_name,
        )
        self.session.add(operation)
        await audit_change(
            self.session,
            tenant_id=self.tenant_id,
            entity_type="operation",
            entity_id=operation.id,
            action="INSERT",
            old_values=None,
            new_values={"operation_code": code, "operation_name": phase_name},
            actor_role="system",
            reason=(
                f"Q.55.B — operacao de routing criada para a fase "
                f"'{phase_name}' (atribuicao diaria de operador)"
            ),
        )
        await self.session.flush()
        return operation
