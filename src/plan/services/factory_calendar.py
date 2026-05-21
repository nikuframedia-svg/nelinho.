"""
ProdPlan ONE — Factory Calendar value object + loader (Q.53.B)
===============================================================

`FactoryCalendar` is an in-memory, read-only view of
`plan.factory_calendar_day` for one tenant. It answers the two questions
the scheduler needs:

* `is_working_day(d)` — does the factory produce on day `d`?
* `next_working_day(d)` / `prev_working_day(d)` — skip weekends/holidays.
* `add_working_hours(start, hours)` — walk a duration forward across the
  calendar, only consuming productive shift hours.
* `subtract_working_hours(end, hours)` — the same walk backwards, used by
  the backward scheduler.

Outside the seeded range the calendar falls back to a Mon-Fri default
(weekend = non-working, weekday = working at `default_shift_hours`), so a
schedule that runs past the seed horizon still behaves sanely instead of
crashing or treating Sundays as workdays.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Dict, Optional, Tuple
from uuid import UUID

logger = logging.getLogger(__name__)

#: NELO runs a single ~8h shift. The decoder treats this as the
#: productive capacity of an ordinary working day.
DEFAULT_SHIFT_HOURS = 8.0

#: Shift starts at 08:00 — matches the HORIZON_START convention used
#: across the CPO tests and the ERP `OFFP_DATAINICIO` modal hour.
DEFAULT_SHIFT_START = time(8, 0)


@dataclass
class FactoryCalendar:
    """Read-only working-time view for one tenant.

    `days` maps a `date` to `(is_working_day, shift_hours)`. Any date not
    present falls back to the Mon-Fri default.
    """

    tenant_id: Optional[UUID] = None
    days: Dict[date, Tuple[bool, float]] = field(default_factory=dict)
    default_shift_hours: float = DEFAULT_SHIFT_HOURS
    shift_start: time = DEFAULT_SHIFT_START
    #: True once `load()` actually read rows from the DB. False means the
    #: calendar is running purely on the Mon-Fri fallback.
    loaded_ok: bool = False

    # ------------------------------------------------------------------
    # Day-level queries
    # ------------------------------------------------------------------

    def _day_info(self, d: date) -> Tuple[bool, float]:
        """`(is_working, shift_hours)` for `d`, falling back to Mon-Fri."""
        if d in self.days:
            return self.days[d]
        # Fallback: weekday is a working day, weekend is not.
        is_weekend = d.weekday() >= 5  # 5=Sat, 6=Sun
        if is_weekend:
            return (False, 0.0)
        return (True, self.default_shift_hours)

    def is_working_day(self, d: date) -> bool:
        return self._day_info(d)[0]

    def shift_hours(self, d: date) -> float:
        working, hours = self._day_info(d)
        return hours if working else 0.0

    def next_working_day(self, d: date) -> date:
        """First working day on or after `d`."""
        cur = d
        # Guard against a pathological all-off calendar.
        for _ in range(366):
            if self.is_working_day(cur):
                return cur
            cur = cur + timedelta(days=1)
        return cur

    def prev_working_day(self, d: date) -> date:
        """Last working day on or before `d`."""
        cur = d
        for _ in range(366):
            if self.is_working_day(cur):
                return cur
            cur = cur - timedelta(days=1)
        return cur

    # ------------------------------------------------------------------
    # Duration walks — the part the decoder / backward scheduler use
    # ------------------------------------------------------------------

    def add_working_hours(self, start: datetime, hours: float) -> datetime:
        """Walk `hours` of productive time forward from `start`.

        Only shift hours of working days are consumed: a gap that lands
        on a Sunday is *not* charged, the work simply resumes Monday
        08:00. A zero/negative duration returns `start` unchanged after
        snapping into a working window.
        """
        cur = self._snap_into_shift(start)
        remaining = max(0.0, float(hours))
        if remaining <= 0.0:
            return cur

        # Guard: cap the walk so a corrupt input can't loop forever.
        for _ in range(100_000):
            day = cur.date()
            shift_h = self.shift_hours(day)
            if shift_h <= 0.0:
                cur = datetime.combine(
                    self.next_working_day(day + timedelta(days=1)),
                    self.shift_start,
                )
                continue
            shift_end = datetime.combine(day, self.shift_start) + timedelta(
                hours=shift_h
            )
            hours_left_today = (shift_end - cur).total_seconds() / 3600.0
            if remaining <= hours_left_today:
                return cur + timedelta(hours=remaining)
            remaining -= hours_left_today
            cur = datetime.combine(
                self.next_working_day(day + timedelta(days=1)),
                self.shift_start,
            )
        logger.warning("add_working_hours hit walk cap — returning best effort")
        return cur

    def subtract_working_hours(self, end: datetime, hours: float) -> datetime:
        """Walk `hours` of productive time backward from `end`.

        Mirror of `add_working_hours`: used by the backward scheduler to
        find the latest start that still meets a delivery date.
        """
        cur = self._snap_into_shift(end, backward=True)
        remaining = max(0.0, float(hours))
        if remaining <= 0.0:
            return cur

        for _ in range(100_000):
            day = cur.date()
            shift_h = self.shift_hours(day)
            shift_start_dt = datetime.combine(day, self.shift_start)
            if shift_h <= 0.0 or cur <= shift_start_dt:
                prev = self.prev_working_day(day - timedelta(days=1))
                cur = datetime.combine(prev, self.shift_start) + timedelta(
                    hours=self.shift_hours(prev)
                )
                continue
            hours_left_today = (cur - shift_start_dt).total_seconds() / 3600.0
            if remaining <= hours_left_today:
                return cur - timedelta(hours=remaining)
            remaining -= hours_left_today
            prev = self.prev_working_day(day - timedelta(days=1))
            cur = datetime.combine(prev, self.shift_start) + timedelta(
                hours=self.shift_hours(prev)
            )
        logger.warning("subtract_working_hours hit walk cap — best effort")
        return cur

    def _snap_into_shift(
        self, moment: datetime, *, backward: bool = False,
    ) -> datetime:
        """Move `moment` onto a valid working-shift instant.

        Forward: if `moment` is before the shift, jump to shift start; if
        after the shift / on a non-working day, jump to the next shift
        start. Backward: clamp to the shift end of the nearest working
        day on or before `moment`.
        """
        day = moment.date()
        if not backward:
            working_day = self.next_working_day(day)
            shift_start_dt = datetime.combine(working_day, self.shift_start)
            if working_day != day:
                return shift_start_dt
            shift_h = self.shift_hours(day)
            shift_end_dt = shift_start_dt + timedelta(hours=shift_h)
            if moment < shift_start_dt:
                return shift_start_dt
            if moment >= shift_end_dt:
                nxt = self.next_working_day(day + timedelta(days=1))
                return datetime.combine(nxt, self.shift_start)
            return moment
        # backward
        working_day = self.prev_working_day(day)
        shift_start_dt = datetime.combine(working_day, self.shift_start)
        shift_end_dt = shift_start_dt + timedelta(
            hours=self.shift_hours(working_day)
        )
        if working_day != day:
            return shift_end_dt
        if moment > shift_end_dt:
            return shift_end_dt
        if moment <= shift_start_dt:
            prev = self.prev_working_day(day - timedelta(days=1))
            return datetime.combine(prev, self.shift_start) + timedelta(
                hours=self.shift_hours(prev)
            )
        return moment

    # ------------------------------------------------------------------
    # Loader
    # ------------------------------------------------------------------

    @classmethod
    async def load(
        cls,
        session,
        tenant_id: UUID,
        default_shift_hours: float = DEFAULT_SHIFT_HOURS,
    ) -> "FactoryCalendar":
        """Load the calendar rows for `tenant_id` from the DB.

        Best-effort: a missing table / empty calendar returns a
        fallback-only calendar (`loaded_ok=False`) so the scheduler still
        runs — it just behaves as Mon-Fri until the ETL seeds the table.
        """
        cal = cls(tenant_id=tenant_id, default_shift_hours=default_shift_hours)
        if session is None:
            return cal
        try:
            from sqlalchemy import select

            from src.plan.models.factory_calendar import FactoryCalendarDay

            stmt = select(FactoryCalendarDay).where(
                FactoryCalendarDay.tenant_id == tenant_id
            )
            rows = (await session.execute(stmt)).scalars().all()
        except Exception as exc:  # pragma: no cover — defensive (table absent)
            logger.debug("factory_calendar DB load skipped: %s", exc)
            return cal

        for row in rows:
            cal.days[row.day] = (
                bool(row.is_working_day),
                float(row.shift_hours or 0.0),
            )
        cal.loaded_ok = bool(rows)
        logger.info(
            "FactoryCalendar loaded: %d day(s) for tenant=%s",
            len(cal.days), tenant_id,
        )
        return cal
