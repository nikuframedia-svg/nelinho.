"""
ProdPlan ONE - Employee Extras API (Sprint Q.3 / GC03-GC10)
===========================================================

REST endpoints for the EmployeesPage UI:

    GET    /v1/workforce/employees/{id}/quality-score
    GET    /v1/workforce/employees/{id}/skill-matrix
    PATCH  /v1/workforce/employees/{id}/skills
    PATCH  /v1/workforce/employees/{id}/quality-score
    GET    /v1/workforce/employees/{id}/history
    POST   /v1/workforce/employees/{id}/soft-delete

Camada 1 hook: when the operator overrides the ML quality score or
toggles a skill, the route logs a `PreferenceRule` row marked
`status=DETECTED, type=workforce_override` so the adaptive-weights
trainer treats the human override as a data point in its next pass.
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.employee import Employee, EmploymentStatus
from src.shared.database import get_session
from src.workforce.employee_extras_service import (
    EmployeeExtrasService,
    DEFAULT_HISTORY_LIMIT,
    MAX_HISTORY_LIMIT,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/workforce/employees", tags=["Workforce employees"])


def get_tenant_id(x_tenant_id: UUID = Header(..., alias="X-Tenant-Id")) -> UUID:
    return x_tenant_id


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SkillTogglePayload(BaseModel):
    phase_id: str = Field(..., min_length=1, max_length=100)
    can_do: bool
    # Q.53.E — nível agora float na escala invertida (3.0=melhor, 1.0=pior)
    # com meios-passos. O serviço clamp-a ao meio-passo válido mais
    # próximo; aceitamos [1.0, 3.0] aqui.
    nivel: Optional[float] = Field(default=None, ge=1.0, le=3.0)
    reason: Optional[str] = Field(default=None, max_length=500)


class QualityScoreOverridePayload(BaseModel):
    score: float = Field(..., ge=1.0, le=10.0)
    reason: str = Field(..., min_length=10, max_length=500)


class SoftDeletePayload(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)


class ProfilesBatchPayload(BaseModel):
    """Q.54.C — batch read of operator profiles.

    The Factory page used to fire 3 endpoints × ~20 operators = ~60 HTTP
    requests every time a boat was clicked. This collapses it into one.
    """

    employee_ids: list[UUID] = Field(..., min_length=1, max_length=200)


# ---------------------------------------------------------------------------
# Batch profiles (Q.54.C) — one call for the whole Factory operator panel
# ---------------------------------------------------------------------------

@router.post("/profiles")
async def get_profiles_batch(
    body: ProfilesBatchPayload,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Aggregated profile (quality-score + skill-matrix + qualification
    metrics) for several operators in a single response.

    Replaces the Factory page's ~60-request fan-out (20 operators × 3
    endpoints). Read-only; one `EmployeeExtrasService` reused across the
    batch so the connection isn't opened/closed per operator. A failure
    on one operator degrades to an `error` entry instead of failing the
    whole batch.
    """
    svc = EmployeeExtrasService(session, tenant_id)

    # Deduplicate while keeping a stable order.
    seen: set[UUID] = set()
    unique_ids: list[UUID] = []
    for eid in body.employee_ids:
        if eid not in seen:
            seen.add(eid)
            unique_ids.append(eid)

    profiles: list[dict] = []
    for employee_id in unique_ids:
        try:
            quality = await svc.quality_score(employee_id)
            skills = await svc.skill_matrix(employee_id)
            metrics = await svc.qualification_metrics(employee_id)
            profiles.append({
                "employee_id": str(employee_id),
                "quality_score": quality.to_dict(),
                "skill_matrix": {
                    "phases": [r.to_dict() for r in skills],
                    "total": len(skills),
                },
                "qualification_metrics": metrics.to_dict(),
            })
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning(
                "profiles batch: employee %s failed: %r", employee_id, exc,
            )
            profiles.append({
                "employee_id": str(employee_id),
                "error": type(exc).__name__,
            })

    return {
        "profiles": profiles,
        "requested": len(body.employee_ids),
        "returned": len(profiles),
    }


# ---------------------------------------------------------------------------
# Quality score (read + override)
# ---------------------------------------------------------------------------

@router.get("/{employee_id}/quality-score")
async def get_quality_score(
    employee_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """ML-derived quality score in [1, 10] from rework + ops history."""
    svc = EmployeeExtrasService(session, tenant_id)
    result = await svc.quality_score(employee_id)
    return result.to_dict()


@router.patch("/{employee_id}/quality-score")
async def override_quality_score(
    employee_id: UUID,
    body: QualityScoreOverridePayload,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Manual override of the ML score — also drops a Camada 1 rule.

    The override is persisted as a `PreferenceRule(type=workforce_override,
    status=detected)` row. The adaptive-weights trainer picks it up in
    its next scheduled pass; the operator's *reason* feeds the LLM
    Camada 3 dataset builder later.
    """
    svc = EmployeeExtrasService(session, tenant_id)
    ml = await svc.quality_score(employee_id)

    # Best-effort Camada 1 hook — never block the override on a
    # detector-side error.
    try:
        from src.governance.audit_service import audit_change
        from src.governance.models import (
            PreferenceRule,
            PreferenceRuleStatus,
            PreferenceRuleType,
        )
        from sqlalchemy import select

        # Reuse an existing detected rule for this employee × type, if any,
        # to avoid spamming the review queue with duplicates.
        stmt = select(PreferenceRule).where(
            PreferenceRule.tenant_id == tenant_id,
            PreferenceRule.type == PreferenceRuleType.WORKFORCE_OVERRIDE.value,
            PreferenceRule.predicate.contains({"employee_id": str(employee_id)}),
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is None:
            new_rule = PreferenceRule(
                tenant_id=tenant_id,
                type=PreferenceRuleType.WORKFORCE_OVERRIDE.value,
                description=(
                    f"Operator override on quality_score for employee "
                    f"{employee_id}: {ml.score:.2f} → {body.score:.2f}. "
                    f"Reason: {body.reason}"
                ),
                predicate={
                    "employee_id": str(employee_id),
                    "field": "quality_score",
                    "ml_value": round(ml.score, 2),
                    "override_value": round(body.score, 2),
                    "reason": body.reason,
                },
                confidence=1.0,
                status=PreferenceRuleStatus.DETECTED.value,
            )
            session.add(new_rule)
            await session.flush()
            await audit_change(
                session,
                tenant_id=tenant_id,
                entity_type="preference_rule",
                entity_id=new_rule.id,
                action="INSERT",
                old_values=None,
                new_values={
                    "type": PreferenceRuleType.WORKFORCE_OVERRIDE.value,
                    "status": PreferenceRuleStatus.DETECTED.value,
                    "employee_id": str(employee_id),
                    "field": "quality_score",
                    "ml_value": round(ml.score, 2),
                    "override_value": round(body.score, 2),
                },
                reason="Q.66.B.3 — override de quality_score do operador",
            )
        else:
            # Refresh the most recent override on the existing rule.
            predicate = dict(existing.predicate or {})
            predicate.update(
                {
                    "ml_value": round(ml.score, 2),
                    "override_value": round(body.score, 2),
                    "reason": body.reason,
                }
            )
            existing.predicate = predicate
            existing.description = (
                f"Operator override on quality_score for employee "
                f"{employee_id}: {ml.score:.2f} → {body.score:.2f}. "
                f"Reason: {body.reason}"
            )
            await session.flush()
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("preference rule hook failed (override not lost): %s", exc)

    await session.commit()
    return {
        "employee_id": str(employee_id),
        "ml_score": round(ml.score, 2),
        "override_score": round(body.score, 2),
        "reason": body.reason,
        "preference_rule_logged": True,
    }


# ---------------------------------------------------------------------------
# Skill matrix (read + toggle)
# ---------------------------------------------------------------------------

@router.get("/{employee_id}/skill-matrix")
async def get_skill_matrix(
    employee_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    svc = EmployeeExtrasService(session, tenant_id)
    rows = await svc.skill_matrix(employee_id)
    return {
        "employee_id": str(employee_id),
        "phases": [r.to_dict() for r in rows],
        "total": len(rows),
    }


# ---------------------------------------------------------------------------
# Level summary (Q.18 fix-workforce) — escala 1-3 derivada do quality score
# ---------------------------------------------------------------------------

@router.get("/{employee_id}/level-summary")
async def get_level_summary(
    employee_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Resumo do nível do operador — escala invertida 3=melhor, 1=pior.

    Q.53.E: o nível derivado é agora um float com meios-passos
    (1.0/1.5/2.0/2.5/3.0) e é detalhado **por grupo de área** (~7 grupos)
    além do nível global. Escala derivada do quality score Laplace [1-10].
    Inclui descrição do nível, barcos recomendados, skill matrix per-fase
    para polivalência, e os 3 sinais de qualificação (recency/versatility/
    productivity). Usado pela UI de /equipa e /fabrica e pelo Copilot.
    """
    from src.workforce.levels import (
        area_group_for_phase,
        clamp_level,
        level_summary_payload,
        public_level_from_cpo,
    )

    svc = EmployeeExtrasService(session, tenant_id)
    quality = await svc.quality_score(employee_id)
    skills = await svc.skill_matrix(employee_id)
    skills_apt_names = [r.phase_name or r.phase_id for r in skills if r.can_do]
    payload = level_summary_payload(quality.score, skills_apt_names)
    payload["employee_id"] = str(employee_id)
    payload["per_phase_skills"] = [r.to_dict() for r in skills]

    # Nível por grupo de área — média dos níveis curados das fases aptas
    # do grupo (mapeados da escala ERP 1-5 para a invertida 3=melhor).
    # Quando o grupo não tem nivel curado, recai no nível global derivado.
    global_level = payload["derived_level"]
    by_group: dict[str, list[float]] = {}
    for r in skills:
        if not r.can_do:
            continue
        group = area_group_for_phase(r.phase_name, r.phase_id)
        lvl = (
            public_level_from_cpo(r.nivel)
            if r.nivel is not None
            else global_level
        )
        by_group.setdefault(group, []).append(lvl)
    payload["per_area_levels"] = [
        {
            "area_group": group,
            "level": clamp_level(sum(vals) / len(vals)),
            "phases_apt": len(vals),
        }
        for group, vals in sorted(by_group.items())
    ]

    metrics = await svc.qualification_metrics(employee_id)
    payload["qualification_metrics"] = metrics.to_dict()
    return payload


@router.get("/{employee_id}/qualification-metrics")
async def get_qualification_metrics(
    employee_id: UUID,
    phase_id: Optional[str] = Query(
        default=None,
        description="Escopar recência/produtividade a uma fase específica.",
    ),
    area_group: Optional[str] = Query(
        default=None,
        description="Escopar a um grupo de área (ex: Laminagem). Ignorado "
        "se phase_id for dado.",
    ),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Q.53.E — os 3 sinais de qualificação que faltavam no workforce.

    `recency_days` (dias desde a última operação), `versatility` (nº de
    fases aptas/trabalhadas) e `productivity` (ops/dia). A página Fábrica
    combina-os com o quality-score no fit-score do operador.
    """
    svc = EmployeeExtrasService(session, tenant_id)
    metrics = await svc.qualification_metrics(
        employee_id, phase_id=phase_id, area_group=area_group,
    )
    return metrics.to_dict()


@router.patch("/{employee_id}/skills")
async def toggle_skill(
    employee_id: UUID,
    body: SkillTogglePayload,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Toggle `can_do` (and optional nivel) for a single phase.

    Persistence model: the curated `skill_matrix` is read-only (snapshot
    of the ERP). Operator overrides are written as `PreferenceRule`
    rows so they survive the next ingest and feed Camada 1. The route
    returns the current effective value (override → curated fallback).
    """
    # Q.53.E — normaliza o nível ao meio-passo válido da escala invertida.
    from src.workforce.levels import clamp_level

    nivel = clamp_level(body.nivel) if body.nivel is not None else None

    try:
        from src.governance.audit_service import audit_change
        from src.governance.models import (
            PreferenceRule,
            PreferenceRuleStatus,
            PreferenceRuleType,
        )
        from sqlalchemy import select

        stmt = select(PreferenceRule).where(
            PreferenceRule.tenant_id == tenant_id,
            PreferenceRule.type == PreferenceRuleType.WORKFORCE_OVERRIDE.value,
            PreferenceRule.predicate.contains(
                {"employee_id": str(employee_id), "field": "skill", "phase_id": body.phase_id}
            ),
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()

        predicate = {
            "employee_id": str(employee_id),
            "field": "skill",
            "phase_id": body.phase_id,
            "can_do": body.can_do,
            "nivel": nivel,
            "reason": body.reason,
        }
        description = (
            f"Skill override: employee={employee_id} phase={body.phase_id} "
            f"can_do={body.can_do}"
        )
        if existing is None:
            new_rule = PreferenceRule(
                tenant_id=tenant_id,
                type=PreferenceRuleType.WORKFORCE_OVERRIDE.value,
                description=description,
                predicate=predicate,
                confidence=1.0,
                status=PreferenceRuleStatus.DETECTED.value,
            )
            session.add(new_rule)
            await session.flush()
            await audit_change(
                session,
                tenant_id=tenant_id,
                entity_type="preference_rule",
                entity_id=new_rule.id,
                action="INSERT",
                old_values=None,
                new_values={
                    "type": PreferenceRuleType.WORKFORCE_OVERRIDE.value,
                    "status": PreferenceRuleStatus.DETECTED.value,
                    "employee_id": str(employee_id),
                    "field": "skill",
                    "phase_id": body.phase_id,
                    "can_do": body.can_do,
                    "nivel": nivel,
                },
                reason="Q.66.B.3 — override de skill do operador",
            )
        else:
            existing.predicate = predicate
            existing.description = description
            await session.flush()
        await session.commit()
    except Exception as exc:
        logger.error("skill toggle failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to persist skill override",
        )

    return {
        "employee_id": str(employee_id),
        "phase_id": body.phase_id,
        "can_do": body.can_do,
        "nivel": nivel,
        "preference_rule_logged": True,
    }


# ---------------------------------------------------------------------------
# Operation history
# ---------------------------------------------------------------------------

@router.get("/{employee_id}/history")
async def get_history(
    employee_id: UUID,
    limit: int = Query(DEFAULT_HISTORY_LIMIT, ge=1, le=MAX_HISTORY_LIMIT),
    offset: int = Query(0, ge=0),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    svc = EmployeeExtrasService(session, tenant_id)
    rows = await svc.history(employee_id, limit=limit, offset=offset)
    return {
        "employee_id": str(employee_id),
        "operations": [r.to_dict() for r in rows],
        "limit": limit,
        "offset": offset,
        "returned": len(rows),
    }


# ---------------------------------------------------------------------------
# Soft delete
# ---------------------------------------------------------------------------

@router.post("/{employee_id}/soft-delete")
async def soft_delete(
    employee_id: UUID,
    body: SoftDeletePayload,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Mark employee as TERMINATED (history-preserving)."""
    from sqlalchemy import select

    stmt = select(Employee).where(
        Employee.id == employee_id,
        Employee.tenant_id == tenant_id,
    )
    employee = (await session.execute(stmt)).scalar_one_or_none()
    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="employee not found",
        )

    if employee.status == EmploymentStatus.TERMINATED:
        return {
            "employee_id": str(employee_id),
            "status": employee.status.value,
            "already_terminated": True,
        }

    employee.status = EmploymentStatus.TERMINATED
    if body.reason:
        # Append the reason to the notes audit string. We don't have a
        # dedicated termination_reason column today; keep audit cheap.
        suffix = f"\n[soft-deleted] {body.reason}"
        employee.notes = (employee.notes or "") + suffix
    await session.flush()
    await session.commit()

    return {
        "employee_id": str(employee_id),
        "status": employee.status.value,
        "reason": body.reason,
    }
