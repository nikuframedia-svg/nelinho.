"""Q.61.18 + Q.66.B.1 — pipeline UNICO de auditoria.

Antes do Q.61.18 a escrita em `core.audit_log` estava espalhada:
  * Q.61.10 inseriu o primeiro consumidor inline em
    `src/shared/api/decisions.py:propose_decision`.
  * O resto dos servicos (governance.service, plan.services, workforce.*)
    nao escrevia auditoria.

Q.61.18 consolidou: existe UMA forma de criar uma audit row, com a
mesma assinatura em todo o backend:

    from src.governance.audit_service import audit_change
    await audit_change(
        session,
        entity_type="decision_run",
        entity_id=decision.id,
        action="INSERT",
        old_values=None,
        new_values={...},
        actor_id=user_id,
        reason="propose",
    )

Q.66.B.1 substituiu o hack `[trace_id=<uuid>] <reason>` por uma coluna
dedicada `core.audit_log.trace_id` (indexed). O `trace_id` continua a
vir do `get_trace_id()` (ContextVar populado pelo middleware Q.61.12)
mas e escrito directamente na coluna — o `reason` fica limpo.

Invariante 7 ("audit_log escrito na MESMA transaccao que a mudanca de
estado") fica enforced no contrato: a funcao recebe a session do
caller e faz so `session.add(audit)` — nao toca em commit. O caller
controla o boundary.
"""

from __future__ import annotations

from typing import Any, Literal, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.audit import AuditLog
from src.shared.observability import get_trace_id


AuditAction = Literal["INSERT", "UPDATE", "DELETE"]


async def audit_change(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    entity_type: str,
    entity_id: UUID,
    action: AuditAction,
    old_values: Optional[dict[str, Any]] = None,
    new_values: Optional[dict[str, Any]] = None,
    actor_id: Optional[UUID] = None,
    actor_role: Optional[str] = None,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AuditLog:
    """Cria uma linha em `core.audit_log` no contexto da `session` dada.

    Args:
        session: a session aberta pelo caller — esta funcao APENAS faz
            `session.add(audit)`. Commit fica para o caller (preserva
            o invariante de "audit_log na mesma tx que a mudanca").
        tenant_id: tenant da entidade auditada.
        entity_type: ex. "decision_run", "schedule_commit", "rule".
        entity_id: PK da entidade.
        action: INSERT | UPDATE | DELETE.
        old_values: snapshot dos campos chave antes (None se INSERT).
        new_values: snapshot dos campos chave depois (None se DELETE).
        actor_id: user_id de quem agiu (None se sistema).
        actor_role: role do actor (admin, operator, etc.).
        reason: razao em PT-PT (limpa — Q.66.B.1 ja nao prefixa
            trace_id aqui).
        ip_address: opcional, do middleware HTTP.
        user_agent: opcional, do request.

    Returns:
        A instancia `AuditLog` ja adicionada a session. O `trace_id`
        e auto-populado a partir do ContextVar (`get_trace_id()`).
    """
    audit = AuditLog(
        tenant_id=tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        old_values=old_values,
        new_values=new_values,
        actor_id=actor_id,
        actor_role=actor_role,
        reason=reason,
        trace_id=get_trace_id(),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    session.add(audit)
    return audit


__all__ = ["audit_change", "AuditAction"]
