"""Q.20.D — skills mirror tests.

``_proficiency`` / ``_map_skill`` / ``_map_employee_skills`` are pure.
The end-to-end ``mirror_skills`` runs against the recording fake session
(conftest) with the adapter mocked.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from src.adapters.nelo.etl import skills as skills_mod
from src.adapters.nelo.etl.skills import (
    _map_employee_skills,
    _map_skill,
    _proficiency,
    mirror_skills,
)
from src.adapters.nelo.schemas import EntityPhaseRow, PhaseRow
from src.core.models.employee import Employee, EmploymentStatus
from src.hr.models.allocation import EmployeeSkill, Skill

TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _phase(**kw) -> PhaseRow:
    base = dict(
        phase_id=1, phase_name="Laminagem", phase_description=None,
        sequence=10, is_production=True, is_automatic=False, can_repeat=False,
        parent_phase_id=None, hour_coefficient=1.0, k1_reference_hours=4.0,
        k2_reference_hours=5.0, k4_reference_hours=8.0,
    )
    base.update(kw)
    return PhaseRow(**base)


def _ef(**kw) -> EntityPhaseRow:
    base = dict(
        entity_phase_id=1, entity_id=101, phase_id=1, proficiency=3,
        is_supervisor=False, qualified=True, start_date=datetime(2018, 1, 1),
        end_date=None,
    )
    base.update(kw)
    return EntityPhaseRow(**base)


# ── pure: proficiency clamp ───────────────────────────────────────────────


def test_proficiency_clamps_to_1_5():
    assert _proficiency(3) == 3
    assert _proficiency(0) == 1       # below scale → 1
    assert _proficiency(99) == 5      # above scale → 5
    assert _proficiency(None) == 1    # unparseable → 1
    assert _proficiency("x") == 1


# ── pure: skill mapping ───────────────────────────────────────────────────


def test_map_skill_uses_phase_id_as_code():
    mapped = _map_skill(_phase(phase_id=36, phase_name="Laminagem"))
    assert mapped["skill_code"] == "36"
    assert mapped["skill_name"] == "Laminagem"
    assert mapped["category"] == "fase"


# ── pure: employee_skill mapping ──────────────────────────────────────────


def test_map_employee_skills_resolves_fks():
    emp_uuid, skill_uuid = uuid4(), uuid4()
    mapped, skipped = _map_employee_skills(
        [_ef(entity_id=101, phase_id=1, proficiency=4)],
        emp_by_code={"101": emp_uuid},
        skill_by_code={"1": skill_uuid},
    )
    assert skipped == 0
    assert mapped[0]["employee_id"] == emp_uuid
    assert mapped[0]["skill_id"] == skill_uuid
    assert mapped[0]["proficiency_level"] == 4


def test_map_employee_skills_skips_unknown_operator():
    """A row referencing an operator the master mirror never imported is
    skipped, not crashed."""
    mapped, skipped = _map_employee_skills(
        [_ef(entity_id=999, phase_id=1)],
        emp_by_code={},                       # operator 999 unknown
        skill_by_code={"1": uuid4()},
    )
    assert mapped == []
    assert skipped == 1


def test_map_employee_skills_skips_unknown_phase():
    mapped, skipped = _map_employee_skills(
        [_ef(entity_id=101, phase_id=888)],
        emp_by_code={"101": uuid4()},
        skill_by_code={},                     # phase 888 unknown
    )
    assert mapped == []
    assert skipped == 1


# ── end-to-end mirror ─────────────────────────────────────────────────────


async def test_mirror_skills_builds_catalogue_and_matrix(monkeypatch, recording_session):
    """With employees pre-loaded, the mirror writes skills + the
    worker×phase matrix and resolves every FK."""
    session = recording_session
    # Pre-load two employees (the master mirror would have done this).
    emp_a = Employee(
        tenant_id=TENANT, id=uuid4(), employee_code="101",
        employee_name="Op Um", hire_date=datetime(2018, 1, 1).date(),
        status=EmploymentStatus.ACTIVE,
    )
    emp_b = Employee(
        tenant_id=TENANT, id=uuid4(), employee_code="102",
        employee_name="Op Dois", hire_date=datetime(2018, 1, 1).date(),
        status=EmploymentStatus.ACTIVE,
    )
    session.added.extend([emp_a, emp_b])

    monkeypatch.setattr(
        skills_mod.services, "list_phases",
        AsyncMock(return_value=[
            _phase(phase_id=1, phase_name="Laminagem"),
            _phase(phase_id=2, phase_name="Cura"),
        ]),
    )
    monkeypatch.setattr(
        skills_mod.services, "list_entity_phases",
        AsyncMock(return_value=[
            _ef(entity_id=101, phase_id=1, proficiency=4),
            _ef(entity_id=102, phase_id=2, proficiency=2),
        ]),
    )

    result = await mirror_skills(session=session, tenant_id=TENANT, since=None)

    assert result.status == "ok"
    skills = [o for o in session.added if isinstance(o, Skill)]
    emp_skills = [o for o in session.added if isinstance(o, EmployeeSkill)]
    assert {s.skill_code for s in skills} == {"1", "2"}
    assert len(emp_skills) == 2
    assert {es.proficiency_level for es in emp_skills} == {4, 2}


async def test_mirror_skills_skips_rows_for_missing_employees(monkeypatch, recording_session):
    """Without the master mirror first, every employee_skill row points
    at an unknown operator → all skipped, mirror still succeeds."""
    monkeypatch.setattr(
        skills_mod.services, "list_phases",
        AsyncMock(return_value=[_phase(phase_id=1)]),
    )
    monkeypatch.setattr(
        skills_mod.services, "list_entity_phases",
        AsyncMock(return_value=[_ef(entity_id=101, phase_id=1)]),
    )
    result = await mirror_skills(
        session=recording_session, tenant_id=TENANT, since=None,
    )
    assert result.status == "ok"
    assert result.rows_skipped == 1
    assert [o for o in recording_session.added if isinstance(o, EmployeeSkill)] == []
