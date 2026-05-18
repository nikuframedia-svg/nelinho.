"""Q.36.B — quality mirror tests (OF_CHECKLIST → rework_entry).

O mirror antigo lia as colunas ``OFFP_PROBS_*`` vazias; este lê
``OF_CHECKLIST`` via ``services.list_checklist_incidents``. As funções
``_error_code`` / ``_is_mold_related`` / ``build_catalog`` / ``build_rework``
são puras. O end-to-end ``mirror_quality`` corre contra a recording fake
session (conftest) com o adaptador mockado.
"""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import AsyncMock
from uuid import NAMESPACE_DNS, UUID, uuid4, uuid5

from src.adapters.nelo.etl import quality as quality_mod
from src.adapters.nelo.etl.quality import (
    _crew_index,
    _error_code,
    _is_mold_related,
    build_catalog,
    build_rework,
    mirror_quality,
)
from src.adapters.nelo.schemas import ChecklistRow, OperationCrewRow
from src.core.models.employee import Employee, EmploymentStatus
from src.quality.models.rework import ErrorCatalog, ReworkEntry

TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _chk(**kw) -> ChecklistRow:
    base = dict(
        checklist_id=1, work_order_id=5000, operation_id=88, phase_id=18,
        phase_name="Pintura", description="Risco na pintura", description_en=None,
        severity=2, mold_repair=False, blame_chefe=False, blame_operation_id=None,
        resolved=False, state=1, verified_at=datetime(2025, 6, 1, 10, 0),
        updated_at=None, detected_at=datetime(2025, 6, 1, 10, 0),
        operation_mold_id=None,
    )
    base.update(kw)
    return ChecklistRow(**base)


# ── pure: error_code ──────────────────────────────────────────────────────


def test_error_code_slugifies_description():
    assert _error_code("Interior Enrugado") == "interior-enrugado"


def test_error_code_same_text_same_code():
    """Duas linhas com a mesma descrição → o mesmo código → uma entrada."""
    assert _error_code("Risco na pintura") == _error_code("  RISCO NA PINTURA ")


def test_error_code_empty_description_has_fallback():
    assert _error_code("") == "sem-descricao"


def test_error_code_capped_at_64_chars():
    code = _error_code("x" * 200)
    assert len(code) == 64


# ── pure: mold-related classification ─────────────────────────────────────


def test_is_mold_related_true_for_mold_repair_flag():
    assert _is_mold_related(_chk(mold_repair=True)) is True


def test_is_mold_related_true_for_mold_keyword_in_text():
    assert _is_mold_related(_chk(description="Interior enrugado")) is True
    assert _is_mold_related(_chk(description="Deformação no casco")) is True


def test_is_mold_related_false_for_plain_paint_defect():
    assert _is_mold_related(_chk(description="Risco na pintura")) is False


# ── pure: catalogue ───────────────────────────────────────────────────────


def test_build_catalog_distinct_codes():
    incidents = [
        _chk(checklist_id=1, description="Risco na pintura"),
        _chk(checklist_id=2, description="Risco na pintura"),
    ]
    catalog = build_catalog(incidents)
    assert len(catalog) == 1
    assert catalog[0]["error_code"] == "risco-na-pintura"


def test_build_catalog_severity_from_gravidade():
    """OFCH_GRAVIDADE 1/2/3 → low/medium/high."""
    catalog = build_catalog([_chk(checklist_id=1, severity=3)])
    assert catalog[0]["severity_hint"] == "high"


def test_build_catalog_higher_gravidade_lifts_severity():
    incidents = [
        _chk(checklist_id=1, description="Bolha", severity=1),
        _chk(checklist_id=2, description="Bolha", severity=3),
    ]
    catalog = build_catalog(incidents)
    assert catalog[0]["severity_hint"] == "high"


def test_build_catalog_marks_mold_related():
    catalog = build_catalog([_chk(checklist_id=1, description="Molde baço")])
    assert catalog[0]["mold_related"] is True


# ── pure: rework rows ─────────────────────────────────────────────────────


def test_build_rework_id_is_deterministic():
    """Mesmo OFCH_ID → mesmo uuid5 → re-import idempotente."""
    rows = build_rework([_chk(checklist_id=12345)])
    assert rows[0]["id"] == uuid5(NAMESPACE_DNS, "nelo-erp-ofch-12345")


def test_build_rework_carries_description_and_mold():
    rows = build_rework([
        _chk(checklist_id=1, description="Interior enrugado", operation_mold_id=777),
    ])
    assert rows[0]["error_description"] == "Interior enrugado"
    assert rows[0]["mold_id"] == "777"


def test_build_rework_mold_id_none_when_no_operation_mold():
    rows = build_rework([_chk(checklist_id=1, operation_mold_id=None)])
    assert rows[0]["mold_id"] is None


def test_build_rework_causer_none_when_no_crew():
    """Sem crew nem mapa de empregados, o causador fica None — honesto."""
    rows = build_rework([_chk(checklist_id=1)])
    assert rows[0]["causer_employee_id"] is None


def test_build_rework_resolves_causer_via_blame_operation():
    """OFCH_OFFP_ID_CULPA → OFFP_EQ → core.employees."""
    emp_uuid = uuid4()
    crew = [OperationCrewRow(
        operation_id=70, work_order_id=5000, phase_id=18,
        operator_id=42, is_chefe=False,
    )]
    rows = build_rework(
        [_chk(checklist_id=1, blame_operation_id=70)],
        crew_by_op=_crew_index(crew),
        employee_by_code={"42": emp_uuid},
    )
    assert rows[0]["causer_employee_id"] == emp_uuid


def test_build_rework_falls_back_to_operation_id_for_causer():
    """Sem operação culpada explícita, usa a operação do incidente."""
    emp_uuid = uuid4()
    crew = [OperationCrewRow(
        operation_id=88, work_order_id=5000, phase_id=18,
        operator_id=99, is_chefe=True,
    )]
    rows = build_rework(
        [_chk(checklist_id=1, operation_id=88, blame_operation_id=None)],
        crew_by_op=_crew_index(crew),
        employee_by_code={"99": emp_uuid},
    )
    assert rows[0]["causer_employee_id"] == emp_uuid


def test_crew_index_prefers_chefe():
    """Quando uma operação tem vários operadores, o chefe ganha."""
    crew = [
        OperationCrewRow(operation_id=5, work_order_id=1, phase_id=2,
                         operator_id=10, is_chefe=False),
        OperationCrewRow(operation_id=5, work_order_id=1, phase_id=2,
                         operator_id=11, is_chefe=True),
    ]
    index = _crew_index(crew)
    assert index[5].operator_id == 11


def test_build_rework_detected_at_falls_back_to_verified_at():
    rows = build_rework([_chk(checklist_id=1, detected_at=None,
                              verified_at=datetime(2025, 3, 4, 9, 0))])
    assert rows[0]["detected_at"].year == 2025
    assert rows[0]["detected_at"].month == 3


# ── end-to-end mirror ─────────────────────────────────────────────────────


async def test_mirror_quality_imports_checklist_incidents(monkeypatch, recording_session):
    monkeypatch.setattr(
        quality_mod.services, "list_checklist_incidents",
        AsyncMock(return_value=[
            _chk(checklist_id=1, description="Risco na pintura", severity=2),
            _chk(checklist_id=2, description="Molde baço", severity=3,
                 mold_repair=True, operation_mold_id=300),
        ]),
    )
    monkeypatch.setattr(
        quality_mod.services, "list_operation_crew",
        AsyncMock(return_value=[]),
    )
    result = await mirror_quality(session=recording_session, tenant_id=TENANT, since=None)

    assert result.status == "ok"
    assert result.rows_read == 2
    catalog = [o for o in recording_session.added if isinstance(o, ErrorCatalog)]
    rework = [o for o in recording_session.added if isinstance(o, ReworkEntry)]
    assert {c.error_code for c in catalog} == {"risco-na-pintura", "molde-baço"}
    assert len(rework) == 2
    mold_row = next(r for r in rework if r.error_code == "molde-baço")
    assert mold_row.mold_id == "300"


async def test_mirror_quality_resolves_causer_from_crew(monkeypatch, recording_session):
    """O mirror lê core.employees da sessão para resolver o causador."""
    emp = Employee(
        id=uuid4(), tenant_id=TENANT, employee_code="42",
        employee_name="Operador 42", hire_date=date(2020, 1, 1),
        status=EmploymentStatus.ACTIVE,
    )
    recording_session.add(emp)
    monkeypatch.setattr(
        quality_mod.services, "list_checklist_incidents",
        AsyncMock(return_value=[
            _chk(checklist_id=1, operation_id=88, blame_operation_id=70),
        ]),
    )
    monkeypatch.setattr(
        quality_mod.services, "list_operation_crew",
        AsyncMock(return_value=[
            OperationCrewRow(operation_id=70, work_order_id=5000, phase_id=18,
                             operator_id=42, is_chefe=False),
        ]),
    )
    await mirror_quality(session=recording_session, tenant_id=TENANT, since=None)
    rework = [o for o in recording_session.added if isinstance(o, ReworkEntry)]
    assert len(rework) == 1
    assert rework[0].causer_employee_id == emp.id


async def test_mirror_quality_empty_window_is_noop(monkeypatch, recording_session):
    monkeypatch.setattr(
        quality_mod.services, "list_checklist_incidents",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        quality_mod.services, "list_operation_crew",
        AsyncMock(return_value=[]),
    )
    result = await mirror_quality(session=recording_session, tenant_id=TENANT, since=None)
    assert result.status == "ok"
    assert result.rows_read == 0
    assert [o for o in recording_session.added if isinstance(o, ReworkEntry)] == []
