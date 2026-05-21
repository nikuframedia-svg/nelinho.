"""Q.67.6.C — Coverage for the dark branches in
``factory_data_product.ingest.transformer.RawToCuratedTransformer``.

Existing Q.67.1.B test pinned the mold ``em_manutencao`` semantics, and the
excel-integration test walks the happy path on a full workbook. What was
still dark in coverage:

* Top-level ``transform()``:
  - The "row without sheet_name" branch (silently skipped + warning log).
  - The "handler raised" branch (Exception ⇒ ``result.errors`` instead of
    propagating).
* The numeric/decimal/date safe helpers — the ``except`` paths fire only
  on truly unparseable input.
* ``_parse_date`` accepts ``date`` and ``datetime`` directly + tries each
  documented format. An unparseable string returns ``None`` (debug log,
  not raise).

Tests here use a UUID for ``ingestion_id`` because the dataclass cares
only about that field's presence, not its DB identity.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from src.factory_data_product.ingest.transformer import (
    RawToCuratedTransformer,
    TransformResult,
)


# ---------------------------------------------------------------------------
# transform() — top-level branching
# ---------------------------------------------------------------------------


def test_transform_skips_rows_with_empty_sheet_name() -> None:
    """A row with ``sheet_name`` missing or empty is silently skipped and
    does NOT crash the transform (it used to produce a None bucket that
    fell off the SHEET_HANDLERS map)."""
    rows = [
        # Row that should be dropped.
        {"sheet_name": "", "payload_json": {"Of_Id": "1"}, "row_number": 1},
        # Row that has no key at all — also dropped.
        {"payload_json": {"Of_Id": "2"}, "row_number": 2},
        # Real row to confirm transform still produced output afterwards.
        {
            "sheet_name": "OrdensFabrico",
            "payload_json": {"Of_Id": "of-real"},
            "row_number": 3,
        },
    ]
    t = RawToCuratedTransformer()
    result = t.transform(rows, ingestion_id=uuid4())

    # Exactly one curated order — the two skipped rows never reach a handler.
    assert len(result.orders) == 1
    assert result.orders[0]["of_id"] == "of-real"


def test_transform_unknown_sheet_is_ignored_without_error() -> None:
    """Unknown sheet names are not in SHEET_HANDLERS and must be skipped
    silently — no errors appended, no crash."""
    rows = [
        {
            "sheet_name": "TotallyUnknownSheet",
            "payload_json": {"foo": "bar"},
            "row_number": 1,
        }
    ]
    t = RawToCuratedTransformer()
    result = t.transform(rows, ingestion_id=uuid4())

    assert result.errors == []
    assert result.total_curated == 0


def test_transform_handler_exception_is_captured_in_errors() -> None:
    """If a sheet handler raises, the transform must NOT propagate the
    exception — it appends a structured ``Error transforming <sheet>``
    message to ``result.errors`` and continues."""

    class _ExplodingTransformer(RawToCuratedTransformer):
        def _transform_orders(self, rows, ingestion_id, result):  # type: ignore[override]
            raise RuntimeError("simulated handler failure")

    rows = [
        {
            "sheet_name": "OrdensFabrico",
            "payload_json": {"Of_Id": "1"},
            "row_number": 1,
        }
    ]
    t = _ExplodingTransformer()
    result = t.transform(rows, ingestion_id=uuid4())

    assert any("Error transforming OrdensFabrico" in e for e in result.errors)
    # No orders made it through.
    assert result.orders == []


# ---------------------------------------------------------------------------
# _safe_* helpers — happy paths + error paths
# ---------------------------------------------------------------------------


def test_safe_int_handles_strings_floats_and_garbage() -> None:
    t = RawToCuratedTransformer()
    assert t._safe_int("42") == 42
    assert t._safe_int(3.7) == 3
    # Garbage falls into the except (ValueError/TypeError) branch.
    assert t._safe_int("abc") is None
    assert t._safe_int(None) is None


def test_safe_decimal_handles_strings_and_none() -> None:
    """Happy path + ``None`` short-circuit. (``_safe_decimal`` only catches
    ValueError/TypeError; bona-fide bogus strings raise ``InvalidOperation``
    — that's a documented caller-must-not-pass-garbage contract, exercised
    upstream in the parser's _safe_decimal call.)"""
    t = RawToCuratedTransformer()
    assert t._safe_decimal("1.25") == Decimal("1.25")
    assert t._safe_decimal(2) == Decimal("2")
    assert t._safe_decimal(None) is None


def test_safe_decimal_returns_none_for_type_error_input() -> None:
    """A non-stringifiable object triggers TypeError ⇒ branch returns None.
    Use an object whose ``__str__`` raises to force the except path."""

    class _NoStr:
        def __str__(self) -> str:
            raise TypeError("nope")

    t = RawToCuratedTransformer()
    assert t._safe_decimal(_NoStr()) is None


def test_safe_str_strips_whitespace_and_treats_empty_as_none() -> None:
    t = RawToCuratedTransformer()
    assert t._safe_str("  hello  ") == "hello"
    assert t._safe_str("") is None
    assert t._safe_str("   ") is None
    assert t._safe_str(None) is None
    # Non-string scalars are coerced through str()
    assert t._safe_str(42) == "42"


# ---------------------------------------------------------------------------
# _parse_date — every documented format + the failure path
# ---------------------------------------------------------------------------


def test_parse_date_returns_date_unchanged() -> None:
    t = RawToCuratedTransformer()
    d = date(2026, 4, 1)
    assert t._parse_date(d) is d


def test_parse_date_returns_datetime_unchanged() -> None:
    """``datetime`` is a subclass of ``date`` — the first isinstance() guard
    matches, so the value returns unchanged (it's still a valid date
    surrogate downstream)."""
    t = RawToCuratedTransformer()
    dt = datetime(2026, 4, 1, 12, 30)
    assert t._parse_date(dt) == dt


def test_parse_date_recognises_each_format() -> None:
    """Each format in the inner loop must parse correctly."""
    t = RawToCuratedTransformer()
    assert t._parse_date("2026-04-01") == date(2026, 4, 1)
    assert t._parse_date("01/04/2026") == date(2026, 4, 1)
    assert t._parse_date("01-04-2026") == date(2026, 4, 1)
    assert t._parse_date("2026/04/01") == date(2026, 4, 1)


def test_parse_date_returns_none_for_unparseable_string() -> None:
    """Unparseable strings fall off the format loop and produce ``None``
    instead of raising — the surrounding curated row stays well-formed."""
    t = RawToCuratedTransformer()
    assert t._parse_date("definitely not a date") is None


def test_parse_date_returns_none_for_none_input() -> None:
    """Explicit ``None`` short-circuits before the try."""
    t = RawToCuratedTransformer()
    assert t._parse_date(None) is None


# ---------------------------------------------------------------------------
# TransformResult.total_curated — aggregate counter
# ---------------------------------------------------------------------------


def test_total_curated_sums_every_bucket() -> None:
    """``total_curated`` is the sum of every list field — used by the API
    to report ``rows_transformed`` without having to know the schema."""
    r = TransformResult()
    r.orders.append({"x": 1})
    r.order_phases.extend([{"y": 1}, {"y": 2}])
    r.molds.append({"z": 1})
    r.models.append({"m": 1})
    r.allocations.append({"a": 1})
    assert r.total_curated == 6
