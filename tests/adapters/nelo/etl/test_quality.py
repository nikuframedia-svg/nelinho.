"""Q.20.E — quality mirror tests.

``_problem_codes`` / ``_is_incident`` / ``build_catalog`` are pure. The
end-to-end ``mirror_quality`` runs against the recording fake session
(conftest) with the adapter mocked.

Q.167.E — o mirror já NÃO escreve ``rework_entry`` (a fonte única de defeitos
é o checklist). Os testes garantem que só o ``error_catalog`` é escrito.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock
from uuid import UUID

from src.adapters.nelo.etl import quality as quality_mod
from src.adapters.nelo.etl.quality import (
    _is_incident,
    _problem_codes,
    build_catalog,
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


# ── end-to-end mirror (Q.167.E: catálogo SÓ, zero rework) ─────────────────


async def test_mirror_quality_writes_catalogue_not_rework(monkeypatch, recording_session):
    """Q.167.E — o mirror escreve o vocabulário (`error_catalog`) mas NUNCA
    `rework_entry` (a fonte única de defeitos é o checklist)."""
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
    assert rework == []                                # Q.167.E — zero dupla contagem


async def test_mirror_quality_clean_window_is_noop(monkeypatch, recording_session):
    monkeypatch.setattr(
        quality_mod.services, "list_operations",
        AsyncMock(return_value=[_op(operation_id=1), _op(operation_id=2)]),
    )
    result = await mirror_quality(session=recording_session, tenant_id=TENANT, since=None)
    assert result.status == "ok"
    assert result.rows_skipped == 2
    assert [o for o in recording_session.added if isinstance(o, ReworkEntry)] == []
