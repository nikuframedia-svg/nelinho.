"""Q.53.B — factory calendar value object + holiday seed.

Covers the `FactoryCalendar` walk logic (forward/backward across
weekends + holidays) and the ETL seed builder. Pure unit tests — no DB.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from src.adapters.nelo.etl.calendar import (
    _easter_sunday,
    build_calendar_rows,
    portuguese_national_holidays,
)
from src.plan.services.factory_calendar import FactoryCalendar


# ─── Holiday computation ─────────────────────────────────────────────────


def test_easter_sunday_known_dates():
    """Meeus/Jones/Butcher against published Easter dates."""
    assert _easter_sunday(2026) == date(2026, 4, 5)
    assert _easter_sunday(2025) == date(2025, 4, 20)
    assert _easter_sunday(2024) == date(2024, 3, 31)


def test_portuguese_holidays_include_fixed_and_movable():
    holidays = portuguese_national_holidays(2026)
    # Fixed
    assert date(2026, 1, 1) in holidays      # Ano Novo
    assert date(2026, 4, 25) in holidays     # Dia da Liberdade
    assert date(2026, 12, 25) in holidays    # Natal
    assert date(2026, 6, 10) in holidays     # Dia de Portugal
    # Movable — Good Friday 2 days before Easter (2026-04-05)
    assert date(2026, 4, 3) in holidays      # Sexta-feira Santa
    # 13 national holidays in total
    assert len(holidays) == 13


# ─── Calendar row builder ────────────────────────────────────────────────


def test_build_calendar_rows_marks_weekends_off():
    # 2026-05-09 is a Saturday, 2026-05-10 a Sunday.
    rows = build_calendar_rows(date(2026, 5, 9), date(2026, 5, 11))
    by_day = {r["day"]: r for r in rows}
    assert by_day[date(2026, 5, 9)]["is_working_day"] is False
    assert by_day[date(2026, 5, 9)]["label"] == "Sábado"
    assert by_day[date(2026, 5, 10)]["is_working_day"] is False
    # Monday is a normal working day
    assert by_day[date(2026, 5, 11)]["is_working_day"] is True
    assert float(by_day[date(2026, 5, 11)]["shift_hours"]) == 8.0


def test_build_calendar_rows_marks_holiday_off():
    # 2026-04-25 (Dia da Liberdade) is a Saturday this year — still a
    # holiday label takes precedence is fine; pick 2026-06-10 (Wednesday).
    rows = build_calendar_rows(date(2026, 6, 10), date(2026, 6, 10))
    assert rows[0]["is_working_day"] is False
    assert "Portugal" in rows[0]["label"]


# ─── FactoryCalendar walk ────────────────────────────────────────────────


def _weekday_only_calendar() -> FactoryCalendar:
    """Calendar with no DB rows — pure Mon-Fri fallback."""
    return FactoryCalendar(default_shift_hours=8.0)


def test_calendar_fallback_weekend_is_non_working():
    cal = _weekday_only_calendar()
    assert cal.is_working_day(date(2026, 5, 9)) is False   # Sat
    assert cal.is_working_day(date(2026, 5, 10)) is False  # Sun
    assert cal.is_working_day(date(2026, 5, 11)) is True   # Mon


def test_next_and_prev_working_day_skip_weekend():
    cal = _weekday_only_calendar()
    # Friday + skip → Monday
    assert cal.next_working_day(date(2026, 5, 9)) == date(2026, 5, 11)
    assert cal.prev_working_day(date(2026, 5, 10)) == date(2026, 5, 8)


def test_add_working_hours_within_one_shift():
    cal = _weekday_only_calendar()
    # Monday 08:00 + 4h → Monday 12:00
    start = datetime(2026, 5, 11, 8, 0)
    assert cal.add_working_hours(start, 4.0) == datetime(2026, 5, 11, 12, 0)


def test_add_working_hours_spills_into_next_working_day():
    cal = _weekday_only_calendar()
    # Friday 08:00 + 12h work (8h Fri + 4h next) → skips Sat/Sun → Mon 12:00
    start = datetime(2026, 5, 8, 8, 0)  # Friday
    result = cal.add_working_hours(start, 12.0)
    assert result == datetime(2026, 5, 11, 12, 0)


def test_add_working_hours_never_lands_on_weekend():
    """Property-style: 200 random durations from a Friday never end on
    a Saturday or Sunday."""
    cal = _weekday_only_calendar()
    start = datetime(2026, 5, 8, 8, 0)  # Friday
    for hours in range(1, 201):
        end = cal.add_working_hours(start, float(hours))
        assert end.weekday() < 5, f"{hours}h landed on weekday {end.weekday()}"


def test_subtract_working_hours_skips_weekend():
    cal = _weekday_only_calendar()
    # Monday 12:00 - 12h → 4h Mon + 8h Friday → Friday 08:00
    end = datetime(2026, 5, 11, 12, 0)
    result = cal.subtract_working_hours(end, 12.0)
    assert result == datetime(2026, 5, 8, 8, 0)


def test_add_and_subtract_are_inverse():
    """Walking N hours forward then N back returns to the start."""
    cal = _weekday_only_calendar()
    start = datetime(2026, 5, 11, 8, 0)  # Monday
    for hours in (1.0, 7.5, 16.0, 40.0, 83.0):
        end = cal.add_working_hours(start, hours)
        back = cal.subtract_working_hours(end, hours)
        assert back == start, f"{hours}h round-trip drifted to {back}"


def test_calendar_with_explicit_holiday_row():
    """A DB-style row marking a Wednesday off is respected by the walk."""
    cal = FactoryCalendar(default_shift_hours=8.0)
    cal.days[date(2026, 5, 13)] = (False, 0.0)  # Wed marked off
    # Tue 08:00 + 12h: 8h Tue, Wed skipped, 4h Thu → Thu 12:00
    start = datetime(2026, 5, 12, 8, 0)
    result = cal.add_working_hours(start, 12.0)
    assert result == datetime(2026, 5, 14, 12, 0)
