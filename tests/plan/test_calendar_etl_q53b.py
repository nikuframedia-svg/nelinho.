"""Q.53.B — calendar ETL mirror seed.

The NELO ERP has no holiday table, so the mirror seeds the working
calendar. These tests cover the row builder and the mirror's
registration; the full DB upsert path is exercised by the ETL runner's
own suite.
"""

from __future__ import annotations

from datetime import date

from src.adapters.nelo.etl.calendar import build_calendar_rows, mirror_calendar
from src.adapters.nelo.etl.sync import registered_mirrors


def test_calendar_mirror_is_registered():
    assert "calendar" in registered_mirrors()


def test_build_calendar_rows_full_week_count():
    # A full ISO week Mon 2026-05-11 .. Sun 2026-05-17.
    rows = build_calendar_rows(date(2026, 5, 11), date(2026, 5, 17))
    assert len(rows) == 7
    working = [r for r in rows if r["is_working_day"]]
    off = [r for r in rows if not r["is_working_day"]]
    assert len(working) == 5   # Mon-Fri
    assert len(off) == 2       # Sat-Sun


def test_build_calendar_rows_inclusive_bounds():
    rows = build_calendar_rows(date(2026, 5, 11), date(2026, 5, 11))
    assert len(rows) == 1
    assert rows[0]["day"] == date(2026, 5, 11)


def test_build_calendar_rows_custom_shift_hours():
    rows = build_calendar_rows(
        date(2026, 5, 11), date(2026, 5, 11), shift_hours=10.0,
    )
    assert float(rows[0]["shift_hours"]) == 10.0


def test_build_calendar_rows_spans_year_boundary():
    """Holiday lookup must cover every year the window touches."""
    rows = build_calendar_rows(date(2025, 12, 30), date(2026, 1, 2))
    by_day = {r["day"]: r for r in rows}
    # 2026-01-01 Ano Novo is a holiday.
    assert by_day[date(2026, 1, 1)]["is_working_day"] is False
    assert "Ano Novo" in by_day[date(2026, 1, 1)]["label"]
