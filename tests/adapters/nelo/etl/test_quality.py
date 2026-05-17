"""Q.20.E — quality mirror tests.

``_problem_codes`` / ``_is_incident`` / ``build_catalog`` / ``build_rework``
are pure. The end-to-end ``mirror_quality`` runs against the recording
fake session (conftest) with the adapter mocked.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock
from uuid import NAMESPACE_DNS, UUID, uuid5

from src.adapters.nelo.etl import quality as quality_mod
from src.adapters.nelo.etl.quality import (
    _is_incident,
    _problem_codes,
    build_catalog,
    build_rework,
    mirror_quality,
)
from src.adapters.nelo.schemas import OperationRow
from src.quality.models.rework import ErrorCatalog, ReworkEntry

TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _op(**kw) -> OperationRow:
    base = dict(
        operation_id=1, work_order_id=5000, phase_id=18, phase_name="Pintura",
        start_at=datetime(2025, 1, 1, 8, 0), end_at=datetime(2025, 1, 1, 14, 0),
        expected_at=None, standard_time_hours=6.0, temperature=21.0,
        humidity=55.0, problem_neck=None, problem_interior_id=None,
        problem_paint_id=None, problem_mold_id=None, problem_lamination_id=None,
        problem_logged_at=None, is_return=False, severe_return=False,
        product_id=900, shift_id=None, mold_work_order_id=None,
        product_type_name="K1", phase_is_automatic=False,
    )
    base.update(kw)
    return OperationRow(**base)


# ── pure: problem codes ───────────────────────────────────────────────────


def test_problem_codes_extracts_each_category():
    op = _op(problem_paint_id=7, problem_mold_id=3, problem_neck="gola torta")
    codes = dict(_problem_codes(op))
    assert codes["PAINT-7"]
    assert codes["MOLD-3"]
    assert codes["NECK"]


def test_problem_codes_empty_for_clean_operation():
    assert _problem_codes(_op()) == []


# ── pure: incident detection ──────────────────────────────────────────────


def test_is_incident_true_for_rework():
    """OFFP_RETURN set → rework → incident, even with no problem code."""
    assert _is_incident(_op(is_return=True)) is True


def test_is_incident_true_for_problem_only():
    assert _is_incident(_op(problem_mold_id=2)) is True


def test_is_incident_false_for_clean_operation():
    assert _is_incident(_op()) is False


# ── pure: catalogue ───────────────────────────────────────────────────────


def test_build_catalog_distinct_codes():
    ops = [_op(problem_paint_id=7), _op(operation_id=2, problem_paint_id=7)]
    catalog = build_catalog(ops)
    assert len(catalog) == 1                  # same code → one entry
    assert catalog[0]["error_code"] == "PAINT-7"


def test_build_catalog_severe_return_lifts_severity():
    ops = [
        _op(problem_mold_id=1, severe_return=False),
        _op(operation_id=2, problem_mold_id=1, severe_return=True),
    ]
    catalog = build_catalog(ops)
    assert catalog[0]["severity_hint"] == "high"
    assert catalog[0]["mold_related"] is True


# ── pure: rework rows ─────────────────────────────────────────────────────


def test_build_rework_id_is_deterministic():
    """Same operation id → same uuid5 → idempotent re-import."""
    op = _op(operation_id=12345, is_return=True)
    rows = build_rework([op])
    assert rows[0]["id"] == uuid5(NAMESPACE_DNS, "nelo-erp-offp-12345")


def test_build_rework_plain_return_uses_return_code():
    """A rework with no categorised problem still produces a row."""
    rows = build_rework([_op(is_return=True)])
    assert len(rows) == 1
    assert rows[0]["error_code"] == "RETURN"


def test_build_rework_skips_clean_operations():
    assert build_rework([_op()]) == []


def test_build_rework_detected_at_falls_back_to_end_at():
    """No problem_logged_at → use end_at for detected_at."""
    rows = build_rework([_op(is_return=True, problem_logged_at=None)])
    assert rows[0]["detected_at"].year == 2025


# ── end-to-end mirror ─────────────────────────────────────────────────────


async def test_mirror_quality_imports_incidents(monkeypatch, recording_session):
    monkeypatch.setattr(
        quality_mod.services, "list_operations",
        AsyncMock(return_value=[
            _op(operation_id=1, problem_paint_id=7, is_return=True),
            _op(operation_id=2, problem_mold_id=3, severe_return=True),
            _op(operation_id=3),                       # clean → skipped
        ]),
    )
    result = await mirror_quality(session=recording_session, tenant_id=TENANT, since=None)

    assert result.status == "ok"
    assert result.rows_read == 3
    assert result.rows_skipped == 1                    # the clean operation
    catalog = [o for o in recording_session.added if isinstance(o, ErrorCatalog)]
    rework = [o for o in recording_session.added if isinstance(o, ReworkEntry)]
    assert {c.error_code for c in catalog} == {"PAINT-7", "MOLD-3"}
    assert len(rework) == 2


async def test_mirror_quality_clean_window_is_noop(monkeypatch, recording_session):
    monkeypatch.setattr(
        quality_mod.services, "list_operations",
        AsyncMock(return_value=[_op(operation_id=1), _op(operation_id=2)]),
    )
    result = await mirror_quality(session=recording_session, tenant_id=TENANT, since=None)
    assert result.status == "ok"
    assert result.rows_skipped == 2
    assert [o for o in recording_session.added if isinstance(o, ReworkEntry)] == []
