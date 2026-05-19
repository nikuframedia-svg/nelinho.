"""Q.48.A — calendar mirror tests (F10, factory capacity calendar).

``_build_calendar`` is a pure merge of the two ERP readers. The
end-to-end ``mirror_calendar`` runs against the recording fake session
(conftest) with the adapter mocked — no SQL Server, no Postgres.
"""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import AsyncMock
from uuid import UUID

from src.adapters.nelo.etl import calendar as cal_mod
from src.adapters.nelo.etl.calendar import _build_calendar, mirror_calendar
from src.adapters.nelo.schemas import HolidayRow, WorkDayRow
from src.plan.models.factory_calendar import FactoryCalendarDay

TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _wd(work_day_id: int, y: int, m: int, d: int) -> WorkDayRow:
    return WorkDayRow(work_day_id=work_day_id, work_date=datetime(y, m, d, 0, 0))


def _hol(y: int, m: int, d: int, kind: str = "Feriado") -> HolidayRow:
    return HolidayRow(holiday_date=datetime(y, m, d, 0, 0), kind=kind)


# ── pure merge ────────────────────────────────────────────────────────────


def test_build_calendar_work_days_become_working_rows():
    rows, skipped = _build_calendar(
        [_wd(1, 2026, 5, 18), _wd(2, 2026, 5, 19)], [],
    )
    assert skipped == 0
    by_date = {r["calendar_date"]: r for r in rows}
    assert by_date[date(2026, 5, 18)]["is_working_day"] is True
    assert by_date[date(2026, 5, 18)]["is_holiday"] is False
    assert by_date[date(2026, 5, 19)]["is_working_day"] is True


def test_build_calendar_holidays_become_non_working_rows():
    rows, _ = _build_calendar([], [_hol(2026, 12, 25, "Feriado")])
    row = rows[0]
    assert row["calendar_date"] == date(2026, 12, 25)
    assert row["is_working_day"] is False
    assert row["is_holiday"] is True
    assert row["holiday_kind"] == "Feriado"


def test_build_calendar_holiday_overrides_work_day_on_same_date():
    """A date in both lists is closed — FERIAS is the explicit signal."""
    rows, _ = _build_calendar(
        [_wd(1, 2026, 8, 15)], [_hol(2026, 8, 15, "Férias")],
    )
    assert len(rows) == 1
    assert rows[0]["is_working_day"] is False
    assert rows[0]["is_holiday"] is True
    assert rows[0]["holiday_kind"] == "Férias"


def test_build_calendar_dedupes_repeated_work_days():
    rows, _ = _build_calendar(
        [_wd(1, 2026, 5, 18), _wd(2, 2026, 5, 18)], [],
    )
    assert len(rows) == 1
    assert rows[0]["calendar_date"] == date(2026, 5, 18)


# ── end-to-end mirror ─────────────────────────────────────────────────────


async def test_mirror_calendar_inserts_merged_calendar(monkeypatch, recording_session):
    monkeypatch.setattr(
        cal_mod.services, "list_work_days",
        AsyncMock(return_value=[_wd(1, 2026, 5, 18), _wd(2, 2026, 5, 19)]),
    )
    monkeypatch.setattr(
        cal_mod.services, "list_holidays",
        AsyncMock(return_value=[_hol(2026, 5, 19, "Feriado")]),
    )
    result = await mirror_calendar(session=recording_session, tenant_id=TENANT, since=None)

    assert result.status == "ok"
    assert result.rows_read == 3  # 2 work days + 1 holiday read
    days = [o for o in recording_session.added if isinstance(o, FactoryCalendarDay)]
    by_date = {d.calendar_date: d for d in days}
    # 5-18 stays a working day; 5-19 is overridden to a holiday.
    assert by_date[date(2026, 5, 18)].is_working_day is True
    assert by_date[date(2026, 5, 19)].is_working_day is False
    assert by_date[date(2026, 5, 19)].is_holiday is True
    assert result.rows_inserted == 2


async def test_mirror_calendar_empty_source_is_clean(monkeypatch, recording_session):
    monkeypatch.setattr(
        cal_mod.services, "list_work_days", AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        cal_mod.services, "list_holidays", AsyncMock(return_value=[]),
    )
    result = await mirror_calendar(session=recording_session, tenant_id=TENANT, since=None)
    assert result.status == "ok"
    assert result.rows_read == 0
    assert result.rows_inserted == 0
