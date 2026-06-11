"""Q.115.G — GET /v1/learning/affinities: scores de afinidade operador/fase.

Read-only. Alimenta o tab Aprendizagem (Q.115.O frontend).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.employee import Employee
from src.governance.models.phase_operator_affinity import PhaseOperatorAffinity
from src.plan.models.routing_template import RoutingTemplatePhase
from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/learning", tags=["Aprendizagem"])

_tenant_id = require_tenant_header


# ─── Schema ──────────────────────────────────────────────────────────────────


class AffinitySignal(BaseModel):
    operator_id: str
    # Q.173.AG — código ERP do operador (E_ID): as lanes do plano usam
    # employee_code, não UUID — o badge de afinidade comparava UUID com
    # código e nunca acendia (auditoria 2026-06-11).
    operator_code: str | None = None
    operator_name: str
    phase_id: str
    phase_name: str
    score: float
    sample_count: int
    last_computed_at: datetime


# ─── Endpoint ────────────────────────────────────────────────────────────────


@router.get("/affinities", response_model=List[AffinitySignal])
async def get_affinities(
    phase_id: Optional[str] = Query(None, description="Filtra por fase"),
    operator_id: Optional[str] = Query(None, description="Filtra por operador"),
    top: Optional[int] = Query(None, ge=1, le=200, description="Top-N por score"),
    tenant_id: UUID = Depends(_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> List[AffinitySignal]:
    """Devolve afinidades operador/fase ordenadas por score descendente.

    Retorna lista vazia se o job ainda nunca correu.
    """
    stmt = select(PhaseOperatorAffinity).where(
        PhaseOperatorAffinity.tenant_id == tenant_id
    )
    if phase_id:
        stmt = stmt.where(PhaseOperatorAffinity.phase_id == phase_id)
    if operator_id:
        try:
            oid = UUID(operator_id)
            stmt = stmt.where(PhaseOperatorAffinity.operator_id == oid)
        except ValueError:
            return []

    stmt = stmt.order_by(PhaseOperatorAffinity.score.desc())
    if top is not None:
        stmt = stmt.limit(top)

    result = await session.execute(stmt)
    affinities = result.scalars().all()

    if not affinities:
        return []

    # ── joins para nomes ─────────────────────────────────────────────────────
    operator_ids = list({a.operator_id for a in affinities})
    phase_ids = list({a.phase_id for a in affinities})

    # Nomes dos operadores
    emp_stmt = select(Employee).where(
        Employee.tenant_id == tenant_id,
        Employee.id.in_(operator_ids),
    )
    emp_result = await session.execute(emp_stmt)
    _emps = list(emp_result.scalars().all())
    emp_map: dict[UUID, str] = {e.id: e.employee_name for e in _emps}
    code_map: dict[UUID, str | None] = {
        e.id: getattr(e, "employee_code", None) for e in _emps
    }

    # Nomes das fases (primeira ocorrência por phase_id no tenant)
    phase_stmt = (
        select(RoutingTemplatePhase.phase_id, RoutingTemplatePhase.phase_name)
        .where(
            RoutingTemplatePhase.tenant_id == tenant_id,
            RoutingTemplatePhase.phase_id.in_(phase_ids),
        )
        .distinct(RoutingTemplatePhase.phase_id)
    )
    phase_result = await session.execute(phase_stmt)
    phase_map: dict[str, str] = {
        r.phase_id: (r.phase_name or r.phase_id)
        for r in phase_result.all()
    }

    return [
        AffinitySignal(
            operator_id=str(a.operator_id),
            operator_code=code_map.get(a.operator_id),
            operator_name=emp_map.get(a.operator_id, str(a.operator_id)),
            phase_id=a.phase_id,
            phase_name=phase_map.get(a.phase_id, a.phase_id),
            score=a.score,
            sample_count=a.sample_count,
            last_computed_at=a.last_computed_at,
        )
        for a in affinities
    ]
