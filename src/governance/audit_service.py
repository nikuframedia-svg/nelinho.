"""Q.61.18 — pipeline UNICO de auditoria.

Antes do Q.61.18 a escrita em `core.audit_log` estava espalhada:
  * Q.61.10 inseriu o primeiro consumidor inline em
    `src/shared/api/decisions.py:propose_decision`.
  * O resto dos servicos (governance.service, plan.services, workforce.*)
    nao escrevia auditoria.

Q.61.18 consolida: existe UMA forma de criar uma audit row, com a
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

O trace_id (Q.61.12) e auto-injectado via `get_trace_id()` no `reason`
ate Q.61.18.1 adicionar coluna dedicada. Tabela `core.audit_log` ainda
nao tem `trace_id`, por isso e prefixado no `reason` como
`[trace_id=<uuid>] <razao original>`. Quando Q.61.18.1 (migration)
adicionar coluna, esta funcao migra sem mexer nos call-sites.

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


def _wrap_reason_with_trace_id(reason: Optional[str]) -> Optional[str]:
    """Prefixa o reason com `[trace_id=<uuid>]` se houver trace_id no
    contexto. Quando Q.61.18.1 adicionar coluna `core.audit_log.trace_id`,
    esta funcao migra para usar a coluna directamente."""
    trace_id = get_trace_id()
    if trace_id is None:
        return reason
    if reason is None:
        return f"[trace_id={trace_id}]"
    return f"[trace_id={trace_id}] {reason}"


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
        reason: razao em PT-PT. Sera prefixado com trace_id se houver.
        ip_address: opcional, do middleware HTTP.
        user_agent: opcional, do request.

    Returns:
        A instancia `AuditLog` ja adicionada a session.
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
        reason=_wrap_reason_with_trace_id(reason),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    session.add(audit)
    return audit


__all__ = ["audit_change", "AuditAction"]
