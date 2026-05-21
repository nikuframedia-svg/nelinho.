"""Q.67.6.C — Coverage for ``factory_data_product.quality.runner`` + the
remaining gate branches not already pinned by ``test_quality_gates_q67_1c``.

``QualityRunner`` aggregates a set of ``QualityCheck`` defs into a single
``QualityResult``. Existing tests only walked the duplicates gate. The
branches still dark were:

* Each gate function's *passed* / *failed* branches (sheets-present, columns,
  numeric ranges, referential integrity, dates, PII).
* Exception-in-check path on ``_run_check``: a gate that raises must NOT
  crash the runner; it gets recorded with ``passed=False`` and a
  ``Check error: ...`` message, and a BLOCKING gate's exception flips the
  overall status to FAILED.
* ``QualityCheck`` instances with ``check_fn=None`` pass by default.
* ``get_check_info`` returns the metadata for a known id, ``None`` for an
  unknown id.
* ``list_checks`` returns the full registered list.

Tests here cover those branches with synthetic raw_rows so they stay fully
hermetic (no DB, no file IO).
"""

from __future__ import annotations

from uuid import uuid4

from src.factory_data_product.models.meta import (
    CheckSeverity,
    QualityGateStatus,
)
from src.factory_data_product.quality.gates import (
    QUALITY_CHECKS,
    QualityCheck,
    check_date_parseable,
    check_pii_policy,
    check_referential_integrity,
    check_required_columns_present,
    check_required_sheets_present,
    check_valid_numeric_ranges,
)
from src.factory_data_product.quality.runner import QualityRunner


# ---------------------------------------------------------------------------
# Helpers — minimal raw_row shape the gates expect
# ---------------------------------------------------------------------------


def _row(sheet: str, payload: dict, *, row_number: int = 1, bk: str | None = None) -> dict:
    out = {
        "sheet_name": sheet,
        "payload_json": payload,
        "row_number": row_number,
    }
    if bk is not None:
        out["business_key_sha256"] = bk
    return out


# ---------------------------------------------------------------------------
# Gate-level branches not yet covered
# ---------------------------------------------------------------------------


def test_check_required_sheets_present_passes_when_all_there() -> None:
    """Happy path of the sheets gate — all required sheets present ⇒ passed."""
    rows = [
        _row("OrdensFabrico", {"Of_Id": "1"}),
        _row("FasesOrdemFabrico", {"FaseOf_Id": "1"}),
        _row("Fases", {"Fase_Id": "1"}),
    ]
    res = check_required_sheets_present(rows, {})
    assert res.passed is True
    assert res.severity is CheckSeverity.BLOCKING
    assert res.message is None
    assert set(res.details["found"]) >= {"OrdensFabrico", "FasesOrdemFabrico", "Fases"}


def test_check_required_sheets_present_fails_with_missing_list() -> None:
    """Missing-sheets path lists the gap in ``details.missing``."""
    rows = [_row("OrdensFabrico", {"Of_Id": "1"})]
    res = check_required_sheets_present(rows, {})
    assert res.passed is False
    assert set(res.details["missing"]) == {"FasesOrdemFabrico", "Fases"}
    assert "Missing sheets" in res.message


def test_check_required_columns_present_flags_missing_column() -> None:
    """If a required column is missing from a sheet's payload, the gate
    fails and reports the sheet → missing-list mapping."""
    rows = [
        _row("OrdensFabrico", {"NotOfId": "x"}),
        _row("FasesOrdemFabrico", {"FaseOf_Id": "1", "FaseOf_OfId": "1", "FaseOf_FaseId": "1"}),
        _row("Fases", {"Fase_Id": "1"}),
    ]
    res = check_required_columns_present(rows, {})
    assert res.passed is False
    assert "OrdensFabrico" in res.details["missing_by_sheet"]


def test_check_required_columns_present_happy_path() -> None:
    """All required columns present ⇒ passed, no message."""
    rows = [
        _row("OrdensFabrico", {"Of_Id": "1"}),
        _row("FasesOrdemFabrico", {"FaseOf_Id": "1", "FaseOf_OfId": "1", "FaseOf_FaseId": "1"}),
        _row("Fases", {"Fase_Id": "1"}),
    ]
    res = check_required_columns_present(rows, {})
    assert res.passed is True
    assert res.details["missing_by_sheet"] == {}


def test_check_valid_numeric_ranges_flags_out_of_range_and_non_numeric() -> None:
    """The gate must catch both branches of the inner try: out-of-range
    numeric (caught by ``< min / > max``) and a non-numeric string
    (caught by ``except ValueError``)."""
    rows = [
        _row(
            "FasesOrdemFabrico",
            {"FaseOf_HorasPrevistas": 99999.0},  # out of range (>10000)
            row_number=1,
        ),
        _row(
            "FasesOrdemFabrico",
            {"FaseOf_Coeficiente": "not-a-number"},  # not numeric
            row_number=2,
        ),
    ]
    res = check_valid_numeric_ranges(rows, {})
    assert res.passed is False
    # Both branches must produce a violation entry.
    assert res.details["total_violations"] >= 2
    error_kinds = {v.get("error") for v in res.details["violations"]}
    assert "not_numeric" in error_kinds


def test_check_valid_numeric_ranges_passes_for_in_range_values() -> None:
    """Values within the configured range produce no violations."""
    rows = [
        _row("FasesOrdemFabrico", {"FaseOf_HorasPrevistas": 8.0}, row_number=1),
        _row("FasesOrdemFabrico", {"FaseOf_Coeficiente": 1.5}, row_number=2),
    ]
    res = check_valid_numeric_ranges(rows, {})
    assert res.passed is True
    assert res.details["total_violations"] == 0


def test_check_referential_integrity_flags_dangling_of_ref() -> None:
    """A FaseOrdemFabrico row that points at an Of_Id that is not in the
    OrdensFabrico master must be flagged as ``missing_order``."""
    rows = [
        _row("OrdensFabrico", {"Of_Id": "1"}),
        _row("Fases", {"Fase_Id": "1"}),
        _row(
            "FasesOrdemFabrico",
            {"FaseOf_OfId": "999", "FaseOf_FaseId": "1"},
            row_number=10,
        ),
    ]
    res = check_referential_integrity(rows, {})
    assert res.passed is False
    assert res.details["total_violations"] >= 1
    first = res.details["violations"][0]
    assert first["error"] == "missing_order"
    assert first["value"] == "999"


def test_check_referential_integrity_happy_path() -> None:
    """When every of_ref resolves to an OrdensFabrico row, the gate passes."""
    rows = [
        _row("OrdensFabrico", {"Of_Id": "1"}),
        _row("Fases", {"Fase_Id": "1"}),
        _row(
            "FasesOrdemFabrico",
            {"FaseOf_OfId": "1", "FaseOf_FaseId": "1"},
            row_number=10,
        ),
    ]
    res = check_referential_integrity(rows, {})
    assert res.passed is True
    assert res.details["total_violations"] == 0


def test_check_date_parseable_flags_unparseable_string() -> None:
    """An unparseable date string triggers a WARNING-severity finding."""
    rows = [
        _row(
            "OrdensFabrico",
            {"OF_DataEntrada": "not-a-date"},
            row_number=2,
        ),
    ]
    res = check_date_parseable(rows, {})
    assert res.passed is False
    assert res.severity is CheckSeverity.WARNING
    assert res.details["total_unparseable"] == 1


def test_check_date_parseable_accepts_iso_and_eu_formats() -> None:
    """The gate must recognise YYYY-MM-DD and DD/MM/YYYY (NELO Excel
    actually exports DD/MM/YYYY in some sheets)."""
    rows = [
        _row("OrdensFabrico", {"OF_DataEntrada": "2026-04-01"}, row_number=1),
        _row("OrdensFabrico", {"OF_DataEntrada": "01/04/2026"}, row_number=2),
    ]
    res = check_date_parseable(rows, {})
    assert res.passed is True


def test_check_pii_policy_detects_known_pii_columns() -> None:
    """PII gate is informational: ``passed`` stays True even when names
    are found, but the report enumerates the offending fields."""
    rows = [
        _row("Funcionarios", {"Funcionario_Nome": "alice"}),
        _row("Funcionarios", {"Email": "a@x.pt"}),
    ]
    res = check_pii_policy(rows, {})
    assert res.passed is True  # Warning-only gate
    detected_fields = {p["field"] for p in res.details["pii_fields_detected"]}
    assert "Funcionario_Nome" in detected_fields
    assert "Email" in detected_fields


# ---------------------------------------------------------------------------
# QualityRunner — full registry happy path
# ---------------------------------------------------------------------------


def test_runner_with_minimal_clean_input_marks_overall_passed() -> None:
    """A small but internally-consistent input passes every BLOCKING gate;
    overall status is PASSED, ``failed_blocking`` == 0."""
    rows = [
        _row(
            "OrdensFabrico",
            {"Of_Id": "1"},
            row_number=1,
            bk="of-1",
        ),
        _row(
            "FasesOrdemFabrico",
            {
                "FaseOf_Id": "1",
                "FaseOf_OfId": "1",
                "FaseOf_FaseId": "1",
                "FaseOf_HorasPrevistas": 8.0,
            },
            row_number=1,
            bk="fof-1",
        ),
        _row("Fases", {"Fase_Id": "1"}, row_number=1, bk="f-1"),
    ]
    runner = QualityRunner()
    out = runner.run_all_checks(uuid4(), rows)
    assert out.overall_status == QualityGateStatus.PASSED
    assert out.failed_blocking == 0


# ---------------------------------------------------------------------------
# QualityRunner — exception in a check is captured, not raised
# ---------------------------------------------------------------------------


def _raises_check_fn(*_a, **_k):
    raise RuntimeError("boom in gate")


def test_runner_records_exception_from_blocking_check_as_failure() -> None:
    """A BLOCKING gate that raises:

    * does NOT bubble up,
    * is recorded with ``passed=False`` and ``message``=``"Check error: ..."``,
    * counts toward ``failed_blocking`` ⇒ overall status FAILED.
    """
    broken = QualityCheck(
        check_id="broken_blocking",
        name="Broken",
        description="Always raises",
        severity=CheckSeverity.BLOCKING,
        check_fn=_raises_check_fn,
    )
    runner = QualityRunner(checks={"broken_blocking": broken})
    out = runner.run_all_checks(uuid4(), [])

    assert out.failed_blocking == 1
    assert out.overall_status == QualityGateStatus.FAILED
    entry = out.checks[0]
    assert entry["passed"] is False
    assert "Check error" in entry["message"]
    assert "boom" in entry["details"]["error"]


def test_runner_records_exception_from_warning_check_without_flipping_status() -> None:
    """A WARNING gate that raises must still be recorded but the runner
    only logs the error; overall status stays PASSED (no blocking failure)."""
    broken = QualityCheck(
        check_id="broken_warning",
        name="Broken WARN",
        description="Always raises",
        severity=CheckSeverity.WARNING,
        check_fn=_raises_check_fn,
    )
    runner = QualityRunner(checks={"broken_warning": broken})
    out = runner.run_all_checks(uuid4(), [])

    assert out.failed_blocking == 0
    # The runner branches on ``check.severity == BLOCKING`` in the except —
    # non-blocking exceptions are logged-only and don't increment counters.
    assert out.overall_status == QualityGateStatus.PASSED


# ---------------------------------------------------------------------------
# QualityRunner — checks with no check_fn pass by default
# ---------------------------------------------------------------------------


def test_runner_passes_check_with_no_check_fn() -> None:
    """A QualityCheck whose ``check_fn`` is None is considered passed —
    used by stubs that haven't shipped their logic yet."""
    stub = QualityCheck(
        check_id="stub_only",
        name="Stub",
        description="No check function",
        severity=CheckSeverity.WARNING,
        check_fn=None,
    )
    runner = QualityRunner(checks={"stub_only": stub})
    out = runner.run_all_checks(uuid4(), [])

    assert out.failed_blocking == 0
    assert out.passed_checks == 1
    entry = out.checks[0]
    assert entry["passed"] is True
    assert entry["details"]["note"] == "No check function defined"


# ---------------------------------------------------------------------------
# QualityRunner — get_check_info + list_checks
# ---------------------------------------------------------------------------


def test_get_check_info_returns_metadata_for_known_id() -> None:
    """``get_check_info`` echoes the ``QualityCheck`` metadata."""
    runner = QualityRunner()
    info = runner.get_check_info("required_sheets_present")
    assert info is not None
    assert info["check_id"] == "required_sheets_present"
    assert info["name"] == "Required Sheets Present"
    assert info["severity"] == "blocking"


def test_get_check_info_returns_none_for_unknown_id() -> None:
    """Unknown id ⇒ None (defensive contract for the API layer)."""
    runner = QualityRunner()
    assert runner.get_check_info("__nope__") is None


def test_list_checks_enumerates_registered_checks() -> None:
    """``list_checks`` returns one entry per registered ``QualityCheck``."""
    runner = QualityRunner()
    listed = runner.list_checks()
    listed_ids = {entry["check_id"] for entry in listed}
    assert listed_ids == set(QUALITY_CHECKS.keys())
    # Every entry has the canonical 4 metadata fields.
    for entry in listed:
        assert {"check_id", "name", "description", "severity"} <= entry.keys()
