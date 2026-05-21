"""Q.54.B — reconciliação do estado das ordens de produção.

O ``ProductionOrder.status`` herdado do SQLite legacy estava preso em
``IN_PROGRESS`` para as 521 ordens — incluindo as 329 "Entregue", 26
"Armazem" e 2 "Embalado" cujos barcos já saíram do chão de fábrica. Os
escritores (``seed_nelo_demo``, ``migrate_sqlite_to_postgres``) já passaram
a derivar o estado da fase; esta função fecha o ciclo nas linhas que já
estão na base — corre idempotente e escreve ``core.audit_log`` em cada
transição, na MESMA transacção (invariante "audit trail intact").

Pode ser chamada por um job de sync ou por um script de manutenção.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.audit import AuditLog
from src.plan.models.order import OrderStatus, ProductionOrder
from src.plan.services.phase_classification import phase_status

logger = logging.getLogger(__name__)


@dataclass
class ReconcileResult:
    """Tally de uma reconciliação."""

    scanned: int = 0
    transitioned: int = 0
    transitions: list[dict] = field(default_factory=list)

    def __repr__(self) -> str:
        return (
            f"<ReconcileResult scanned={self.scanned} "
            f"transitioned={self.transitioned}>"
        )


async def reconcile_order_statuses(
    session: AsyncSession,
    tenant_id: UUID,
) -> ReconcileResult:
    """Faz o ``status`` das ordens convergir com a fase actual.

    Para cada ordem cujo estado derivado da fase (:func:`phase_status`)
    difere do estado guardado, transiciona-o e escreve uma linha de
    ``audit_log`` na mesma sessão. Ordens ``CANCELLED`` não são tocadas —
    o cancelamento é uma decisão humana/ERP, não inferível da fase.

    Idempotente: uma segunda passagem sem mudanças de fase devolve
    ``transitioned=0``. O caller faz o ``commit``.
    """
    result = ReconcileResult()

    stmt = select(ProductionOrder).where(
        ProductionOrder.tenant_id == tenant_id,
        ProductionOrder.status != OrderStatus.CANCELLED,
    )
    orders = (await session.execute(stmt)).scalars().all()
    result.scanned = len(orders)

    for order in orders:
        desired = phase_status(order.current_phase_name)
        current = order.status
        # `status` é guardado como string; normaliza para comparar.
        current_value = current.value if hasattr(current, "value") else str(current)
        if current_value == desired.value:
            continue

        session.add(AuditLog(
            tenant_id=tenant_id,
            entity_type="production_order",
            entity_id=order.id,
            action="UPDATE",
            old_values={"status": current_value},
            new_values={"status": desired.value},
            actor_role="system",
            reason=(
                f"Q.54.B reconcile — estado derivado da fase "
                f"'{order.current_phase_name}'"
            ),
        ))
        order.status = desired
        result.transitioned += 1
        result.transitions.append({
            "order_id": str(order.id),
            "legacy_id": order.legacy_id,
            "phase": order.current_phase_name,
            "from": current_value,
            "to": desired.value,
        })

    logger.info(
        "reconcile_order_statuses tenant=%s scanned=%d transitioned=%d",
        tenant_id, result.scanned, result.transitioned,
    )
    return result
