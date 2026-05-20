"""Q.66.E.3 — `GET /v1/observability/agent-actions` (paginated, filtros).

Endpoint Honeycomb-style sobre `core.agent_actions`. Permite consultar
todas as chamadas do copiloto registadas (intent, model, latency,
outcome, escalated, trace_id) com filtros + paginacao.

Filtros:
  * intent (ex: "kpi_current", "schedule_propose")
  * user_id (UUID — ver tudo o que UM utilizador despoletou)
  * outcome (success | error | timeout | skipped — enum validado)
  * escalated (true = gerou DecisionRun)
  * trace_id (substring; cola com audit_log Q.66.B.1)
  * since / until (datetime ISO — janela temporal)

Pattern: copiado de `src/governance/audit_log_api.py` (Q.61.19) —
mesmo skeleton paginated + Pydantic page model + and_(*filters).

Read-only. Tenant-scoped por design (require_tenant_header garante).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.agent_action import AgentAction
from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session


router = APIRouter(prefix="/v1/observability", tags=["Observability"])


# ─── schemas ───────────────────────────────────────────────────────────


class AgentActionEntry(BaseModel):
    """Uma linha da tabela core.agent_actions."""

    id: UUID
    tenant_id: UUID
    user_id: Optional[UUID] = None
    intent: str
    model: Optional[str] = None
    latency_ms: int
    outcome: str
    escalated: bool
    decision_run_id: Optional[UUID] = None
    trace_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AgentActionPage(BaseModel):
    """Resposta paginada."""

    entries: list[AgentActionEntry]
    total: int
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)


# ─── endpoint ──────────────────────────────────────────────────────────


@router.get("/agent-actions", response_model=AgentActionPage)
async def list_agent_actions(
    intent: Optional[str] = Query(None, description="ex: kpi_current"),
    user_id: Optional[UUID] = Query(None),
    outcome: Optional[Literal["success", "error", "timeout", "skipped"]] = Query(
        None,
    ),
    escalated: Optional[bool] = Query(None),
    trace_id: Optional[str] = Query(None, description="substring do trace_id"),
    since: Optional[datetime] = Query(None, description="ISO 8601"),
    until: Optional[datetime] = Query(None, description="ISO 8601"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> AgentActionPage:
    """Lista chamadas do copiloto com filtros + paginacao.

    Tenant-scoped (require_tenant_header garante + RLS reforca em
    Postgres). Ordenacao: created_at DESC (mais recente primeiro).
    """
    filters = [AgentAction.tenant_id == tenant_id]
    if intent is not None:
        filters.append(AgentAction.intent == intent)
    if user_id is not None:
        filters.append(AgentAction.user_id == user_id)
    if outcome is not None:
        filters.append(AgentAction.outcome == outcome)
    if escalated is not None:
        filters.append(AgentAction.escalated == escalated)
    if trace_id is not None:
        # Substring match para suportar partial trace ids (Q.66.B.1
        # usa 32 hex chars; durante debug as vezes so se tem prefixo).
        filters.append(AgentAction.trace_id.like(f"%{trace_id}%"))
    if since is not None:
        filters.append(AgentAction.created_at >= since)
    if until is not None:
        filters.append(AgentAction.created_at <= until)

    where = and_(*filters)

    count_q = select(func.count()).select_from(AgentAction).where(where)
    total = (await session.execute(count_q)).scalar() or 0

    page_q = (
        select(AgentAction)
        .where(where)
        .order_by(desc(AgentAction.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await session.execute(page_q)).scalars().all()

    return AgentActionPage(
        entries=[AgentActionEntry.model_validate(r) for r in rows],
        total=int(total),
        page=page,
        page_size=page_size,
    )


__all__ = ["router"]
