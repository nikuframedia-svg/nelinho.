"""Q.20.D — skills mirror tests.

`_level` is pure. The end-to-end mirror runs against a live Postgres
(marked ``integration``): it seeds employees, runs the mirror, asserts
hr.skills / hr.employee_skills, then rolls back.
"""

from __future__ import annotations

import pytest

from src.infrastructure.erp.etl.skills import _level, mirror_skills


# ── pure ──────────────────────────────────────────────────────────────────


def test_level_clamps_to_1_5():
    assert _level(0) == 1
    assert _level(3) == 3
    assert _level(9) == 5
    assert _level(None) == 1
    assert _level("x") == 1


# ── integration ───────────────────────────────────────────────────────────


class _FakeAdapter:
    async def fetch_phases(self, **_kw):
        return [
            {"fase_id": "LAM", "fase_nome": "Laminagem"},
            {"fase_id": "ACAB", "fase_nome": "Acabamento"},
        ]

    async def fetch_employee_phases(self, **_kw):
        return [
            {"entidade_id": "SK-E1", "fase_id": "LAM", "apto": 1, "nivel": 4},
            {"entidade_id": "SK-E1", "fase_id": "ACAB", "apto": 1, "nivel": 2},
            {"entidade_id": "SK-E2", "fase_id": "LAM", "apto": 1, "nivel": 3},
            # unknown operator → skipped, not crash
            {"entidade_id": "GHOST", "fase_id": "LAM", "apto": 1, "nivel": 1},
            # unknown phase → skipped
            {"entidade_id": "SK-E1", "fase_id": "NOPHASE", "apto": 1, "nivel": 1},
        ]


@pytest.mark.integration
async def test_mirror_skills_end_to_end():
    from datetime import date
    from uuid import UUID

    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from src.core.models.employee import Employee
    from src.hr.models.allocation import EmployeeSkill, Skill
    from src.shared.config import settings

    tenant = UUID("00000000-0000-0000-0000-000000000001")
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            session.add_all([
                Employee(tenant_id=tenant, employee_code="SK-E1",
                         employee_name="Op Um", hire_date=date(2020, 1, 1)),
                Employee(tenant_id=tenant, employee_code="SK-E2",
                         employee_name="Op Dois", hire_date=date(2020, 1, 1)),
            ])
            await session.flush()

            result = await mirror_skills(
                session=session, tenant_id=tenant, adapter=_FakeAdapter(), since=None,
            )
            assert result.status == "ok"
            assert result.rows_skipped == 2   # GHOST operator + NOPHASE phase

            skills = (await session.execute(
                select(Skill).where(
                    Skill.tenant_id == tenant, Skill.skill_code.in_(["LAM", "ACAB"])
                )
            )).scalars().all()
            assert len(skills) == 2
            skill_ids = {s.id for s in skills}

            emp_skills = (await session.execute(
                select(EmployeeSkill).where(EmployeeSkill.skill_id.in_(skill_ids))
            )).scalars().all()
            assert len(emp_skills) == 3   # E1×2 + E2×1
            levels = sorted(es.proficiency_level for es in emp_skills)
            assert levels == [2, 3, 4]

            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.integration
async def test_mirror_skills_idempotent():
    """Second run of the skills mirror inserts nothing new."""
    from datetime import date
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from src.core.models.employee import Employee
    from src.shared.config import settings

    tenant = UUID("00000000-0000-0000-0000-000000000001")
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            session.add(Employee(tenant_id=tenant, employee_code="SK-E1",
                                 employee_name="Op Um", hire_date=date(2020, 1, 1)))
            session.add(Employee(tenant_id=tenant, employee_code="SK-E2",
                                 employee_name="Op Dois", hire_date=date(2020, 1, 1)))
            await session.flush()

            first = await mirror_skills(
                session=session, tenant_id=tenant, adapter=_FakeAdapter(), since=None,
            )
            second = await mirror_skills(
                session=session, tenant_id=tenant, adapter=_FakeAdapter(), since=None,
            )
            assert first.rows_inserted > 0
            assert second.rows_inserted == 0
            assert second.rows_updated == 0

            await session.rollback()
    finally:
        await engine.dispose()
