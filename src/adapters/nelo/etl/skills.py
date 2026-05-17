"""Q.20.D — skills mirror (ERP → hr.skills + hr.employee_skills).

The competence matrix (which operator can work which phase) feeds the
workforce service and the CPO skill-match Spelke axiom on every run.
This mirror imports:

* ``list_phases()``        → ``hr.skills`` (one skill per production phase)
* ``list_entity_phases()`` → ``hr.employee_skills`` (~1 269 worker×phase rows)

FKs are resolved via business codes — ``skill_code`` is the ERP phase id,
``employee_code`` the ERP entity id. A worker×phase row whose operator or
phase the mirror has not seen is skipped + logged, never crashed (QA01
spirit: explicit, not silent).

Prerequisite: run the ``master`` mirror first so ``core.employees`` is
populated — without it every employee_skill row is skipped.

Idempotent: upsert by business key. Re-running never duplicates.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional, Type
from uuid import UUID

from sqlalchemy import select

from src.adapters.nelo import services
from src.adapters.nelo.schemas import EntityPhaseRow, PhaseRow
from src.core.models.employee import Employee
from src.hr.models.allocation import EmployeeSkill, Skill

from .runner import EtlRunner, EtlRunResult
from .sync import register_mirror

logger = logging.getLogger(__name__)


def _proficiency(value: Any) -> int:
    """Clamp the ERP proficiency (``EFP_PRODUTIVIDADE``) to the 1..5
    ProficiencyLevel scale. Defaults to 1 (BEGINNER) when unparseable."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 1
    return max(1, min(5, n))


def _map_skill(row: PhaseRow) -> Optional[Dict[str, Any]]:
    """ERP phase row → ``hr.skills`` column dict — one skill per phase."""
    if row.phase_id in (None, ""):
        return None
    return {
        "skill_code": str(row.phase_id),
        "skill_name": str(row.phase_name or row.phase_id),
        "category": "fase",
    }


async def _code_to_id(
    session, tenant_id: UUID, model: Type[Any], code_attr: str,
) -> Dict[str, UUID]:
    """Map a model's business code → row UUID, scoped to the tenant."""
    rows = await session.execute(
        select(getattr(model, code_attr), model.id).where(
            model.tenant_id == tenant_id
        )
    )
    return {str(code): rid for code, rid in rows}


def _map_employee_skills(
    rows: List[EntityPhaseRow],
    emp_by_code: Dict[str, UUID],
    skill_by_code: Dict[str, UUID],
) -> tuple[List[Dict[str, Any]], int]:
    """Worker×phase rows → ``hr.employee_skills`` dicts. Returns
    (mapped, skipped). A row whose operator or phase is unknown is
    skipped + logged."""
    mapped: List[Dict[str, Any]] = []
    skipped = 0
    for r in rows:
        emp_id = emp_by_code.get(str(r.entity_id))
        skill_id = skill_by_code.get(str(r.phase_id))
        if emp_id is None or skill_id is None:
            skipped += 1
            logger.warning(
                "employee_skill row skipped — unknown operator=%s or phase=%s",
                r.entity_id, r.phase_id,
            )
            continue
        mapped.append({
            "employee_id": emp_id,
            "skill_id": skill_id,
            "proficiency_level": _proficiency(r.proficiency),
        })
    return mapped, skipped


async def mirror_skills(
    *,
    session,
    tenant_id: UUID,
    since: Optional[date] = None,
    source=services,
) -> EtlRunResult:
    """Mirror the skill catalogue + the worker×phase competence matrix."""
    async with EtlRunner(session, tenant_id, source="skills") as run:
        # 1. hr.skills — one skill per production phase.
        phases = await source.list_phases()
        run.count_read(len(phases))
        skill_rows = [m for m in (_map_skill(p) for p in phases) if m is not None]
        run.count_skipped(len(phases) - len(skill_rows))
        await run.upsert(
            Skill, skill_rows,
            key_fields=["skill_code"],
            update_fields=["skill_name", "category"],
        )

        # 2. hr.employee_skills — resolve FKs via the business codes.
        skill_by_code = await _code_to_id(session, tenant_id, Skill, "skill_code")
        emp_by_code = await _code_to_id(session, tenant_id, Employee, "employee_code")

        ef_rows = await source.list_entity_phases()
        run.count_read(len(ef_rows))
        mapped, skipped = _map_employee_skills(ef_rows, emp_by_code, skill_by_code)
        run.count_skipped(skipped)
        await run.upsert(
            EmployeeSkill, mapped,
            key_fields=["employee_id", "skill_id"],
            update_fields=["proficiency_level"],
        )
        logger.info(
            "skills mirror — %d skills, %d employee_skill rows (%d skipped)",
            len(skill_rows), len(mapped), skipped,
        )
    return run.result


register_mirror("skills", mirror_skills)
