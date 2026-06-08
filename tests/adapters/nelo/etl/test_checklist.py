"""Q.167.A — checklist root-cause mirror tests.

``build_rework_from_checklist`` is pure: the spec is that the causer phase
(``OFCH_FP_ID``) and the detector phase (``OFCH_FP_ID_CHK``) stay distinct,
that the responsible operator is resolved per ``OFCH_CULPA_CHEFE``, and the
culprit / detector operations carry through. The end-to-end ``mirror_checklist``
runs against the recording fake session with the adapter + employee lookup mocked.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock
from uuid import NAMESPACE_DNS, UUID, uuid5

from src.adapters.nelo.etl import checklist as checklist_mod
from src.adapters.nelo.etl.checklist import build_rework_from_checklist, mirror_checklist
from src.adapters.nelo.schemas import ChecklistIncidentRow
from src.quality.models.rework import ReworkEntry

TENANT = UUID("00000000-0000-0000-0000-000000000001")
U_OPER = UUID("00000000-0000-0000-0000-0000000000aa")
U_CHEFE = UUID("00000000-0000-0000-0000-0000000000bb")
BY_CODE = {"500": U_OPER, "900": U_CHEFE}


def _inc(**kw) -> ChecklistIncidentRow:
    base = dict(
        checklist_id=1, work_order_id=141898, phase_id_causer=1,
        phase_id_detector=6, gravidade=2, estado=3, culpa_chefe=False,
        molde_reparar=False, detector_op_id=222, causer_op_id=111,
        description="risco no casco", detected_at=datetime(2025, 3, 1, 10, 0),
        product_id=900, product_type_name="K1",
        causer_chefe_eid=900, causer_operator_eid=500,
    )
    base.update(kw)
    return ChecklistIncidentRow(**base)


# ── pure: the whole point — causer ≠ detector ─────────────────────────────


def test_build_preserves_causer_vs_detector_split():
    """OFCH_FP_ID (causou) e OFCH_FP_ID_CHK (detectou) ficam DISTINTOS —
    o bug que esta campanha corrige (a ETL antiga colapsava ambos)."""
    row = build_rework_from_checklist([_inc(phase_id_causer=1, phase_id_detector=6)], BY_CODE)[0]
    assert row["phase_id_causer"] == "1"
    assert row["phase_id_rework"] == "6"


def test_build_falls_back_to_causer_when_detector_null():
    row = build_rework_from_checklist([_inc(phase_id_detector=None)], BY_CODE)[0]
    assert row["phase_id_rework"] == row["phase_id_causer"] == "1"


# ── pure: culpa_chefe semantics ───────────────────────────────────────────


def test_causer_is_operator_when_not_culpa_chefe():
    row = build_rework_from_checklist([_inc(culpa_chefe=False)], BY_CODE)[0]
    assert row["causer_employee_id"] == U_OPER
    assert row["chefe_employee_id"] == U_CHEFE


def test_causer_is_chefe_when_culpa_chefe():
    """OFCH_CULPA_CHEFE=1 → o chefe é o culpado."""
    row = build_rework_from_checklist([_inc(culpa_chefe=True)], BY_CODE)[0]
    assert row["causer_employee_id"] == U_CHEFE
    assert row["chefe_employee_id"] == U_CHEFE


def test_unknown_employee_code_resolves_to_none():
    row = build_rework_from_checklist([_inc(causer_operator_eid=99999)], {})[0]
    assert row["causer_employee_id"] is None


# ── pure: culpability chain + ids ─────────────────────────────────────────


def test_original_and_rework_op_ids_carry_through():
    row = build_rework_from_checklist([_inc(causer_op_id=111, detector_op_id=222)], BY_CODE)[0]
    assert row["original_op_id"] == "111"   # OFCH_OFFP_ID_CULPA — a op culpada
    assert row["rework_op_id"] == "222"     # OFCH_OFFP_ID — onde detectado


def test_null_culprit_op_leaves_original_op_id_none():
    row = build_rework_from_checklist([_inc(causer_op_id=None)], BY_CODE)[0]
    assert row["original_op_id"] is None


def test_id_is_deterministic_on_checklist_id():
    """uuid5 de OFCH_ID — namespace distinto do OFFP do mirror de qualidade."""
    row = build_rework_from_checklist([_inc(checklist_id=777)], BY_CODE)[0]
    assert row["id"] == uuid5(NAMESPACE_DNS, "nelo-erp-ofch-777")


def test_context_carries_gravidade_and_source():
    row = build_rework_from_checklist([_inc(gravidade=2)], BY_CODE)[0]
    assert row["context"]["gravidade_raw"] == 2
    assert row["context"]["severity_hint"] == "medium"
    assert row["context"]["source"] == "erp_of_checklist"


def test_skips_incident_with_no_detected_at():
    assert build_rework_from_checklist([_inc(detected_at=None)], BY_CODE) == []


# ── end-to-end mirror ─────────────────────────────────────────────────────


async def test_mirror_checklist_imports_defects(monkeypatch, recording_session):
    monkeypatch.setattr(
        checklist_mod.services, "list_checklist_incidents",
        AsyncMock(return_value=[
            _inc(checklist_id=1, phase_id_causer=1, phase_id_detector=6),
            _inc(checklist_id=2, phase_id_causer=18, phase_id_detector=18),
            _inc(checklist_id=3, detected_at=None),   # no date → skipped
        ]),
    )
    monkeypatch.setattr(
        checklist_mod, "_employee_id_by_code", AsyncMock(return_value=BY_CODE),
    )
    result = await mirror_checklist(session=recording_session, tenant_id=TENANT, since=None)

    assert result.status == "ok"
    assert result.rows_read == 3
    assert result.rows_skipped == 1
    rework = [o for o in recording_session.added if isinstance(o, ReworkEntry)]
    assert len(rework) == 2
    # the canonical split survived end-to-end
    split = next(r for r in rework if r.error_code == "CHK-P1")
    assert (split.phase_id_causer, split.phase_id_rework) == ("1", "6")
