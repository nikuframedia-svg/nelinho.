"""Q.20.D — skills mirror (ERP → hr.skills + hr.employee_skills).

The competence matrix (which operator can work which phase) is read by
the workforce service and the CPO scheduler on every run. It mirrors:

* ``vw_pp1_fases_producao``  → ``hr.skills`` (one skill per phase)
* ``vw_pp1_entidade_fase``   → ``hr.employee_skills`` (~1269 worker×phase rows)

A worker×phase row whose operator or phase the mirror hasn't seen is
skipped + logged — never crashes the run. Reconciles against the curated
``factory_curated.skill_matrix`` and logs divergence.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional, Type
from uuid import UUID

from sqlalchemy import select

from src.core.models.employee import Employee
from src.factory_data_product.models.curated import CuratedSkillMatrix
from src.factory_data_product.models.meta import ActiveRun
from src.hr.models.allocation import EmployeeSkill, Skill
from src.infrastructure.erp.sqlserver import compare_shadow

from .runner import EtlRunner, EtlRunResult
from .sync import register_mirror

logger = logging.getLogger(__name__)


def _level(value: Any) -> int:
    """Clamp the ERP proficiency level to the 1..5 scale (default 1)."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 1
    return max(1, min(5, n))


async def _code_to_id(
    session, tenant_id: UUID, model: Type[Any], code_attr: str,
) -> Dict[str, UUID]:
    rows = await session.execute(
        select(getattr(model, code_attr), model.id).where(
            model.tenant_id == tenant_id
        )
    )
    return {str(code): rid for code, rid in rows}


async def mirror_skills(
    *,
    session,
    tenant_id: UUID,
    adapter,
    since: Optional[date] = None,
) -> EtlRunResult:
    """Mirror the skill catalogue + the worker×phase competence matrix."""
    async with EtlRunner(session, tenant_id, source="skills") as run:
        # 1. hr.skills — one skill per production phase.
        phases = await adapter.fetch_phases()
        run.count_read(len(phases))
        skill_rows = [
            {
                "skill_code": str(p["fase_id"]),
                "skill_name": str(p.get("fase_nome") or p["fase_id"]),
                "category": "fase",
            }
            for p in phases if p.get("fase_id") not in (None, "")
        ]
        await run.upsert(
            Skill, skill_rows,
            key_fields=["skill_code"],
            update_fields=["skill_name", "category"],
        )

        # 2. hr.employee_skills — resolve FKs via the business codes.
        skill_by_code = await _code_to_id(session, tenant_id, Skill, "skill_code")
        emp_by_code = await _code_to_id(session, tenant_id, Employee, "employee_code")

        ef_rows = await adapter.fetch_employee_phases()
        run.count_read(len(ef_rows))
        mapped: List[Dict[str, Any]] = []
        skipped = 0
        for r in ef_rows:
            emp_id = emp_by_code.get(str(r.get("entidade_id")))
            skill_id = skill_by_code.get(str(r.get("fase_id")))
            if emp_id is None or skill_id is None:
                skipped += 1
                logger.warning(
                    "skill row skipped — unknown operator=%s or phase=%s",
                    r.get("entidade_id"), r.get("fase_id"),
                )
                continue
            mapped.append({
                "employee_id": emp_id,
                "skill_id": skill_id,
                "proficiency_level": _level(r.get("nivel")),
            })
        run.count_skipped(skipped)
        await run.upsert(
            EmployeeSkill, mapped,
            key_fields=["employee_id", "skill_id"],
            update_fields=["proficiency_level"],
        )

        await _reconcile(session, ef_rows)
    return run.result


async def _reconcile(session, ef_rows: List[Dict[str, Any]]) -> None:
    """Compare the ERP skill matrix against the curated one (by
    ``operator|phase`` pair) and log divergence."""
    active_id = await session.scalar(
        select(ActiveRun.active_ingestion_id).where(ActiveRun.id == 1)
    )
    if active_id is None:
        return
    curated = (await session.execute(
        select(CuratedSkillMatrix.funcionario_id, CuratedSkillMatrix.fase_id).where(
            CuratedSkillMatrix.ingestion_id == active_id,
            CuratedSkillMatrix.is_quarantined.is_(False),
        )
    )).all()
    diff = await compare_shadow(
        [{"k": f"{r.get('entidade_id')}|{r.get('fase_id')}"} for r in ef_rows],
        [{"k": f"{fid}|{phid}"} for fid, phid in curated],
        key="k",
    )
    logger.info(
        "skills reconcile — erp=%d curated=%d match=%d only_in_erp=%d "
        "only_in_curated=%d",
        diff["live_count"], diff["curated_count"], diff["match_count"],
        len(diff["only_in_live"]), len(diff["only_in_curated"]),
    )


register_mirror("skills", mirror_skills)
