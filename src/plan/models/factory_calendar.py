"""
ProdPlan ONE — Factory Calendar (Q.53.B)
=========================================

Before Q.53.B the CPO decoder scheduled hours sequentially 24/7 — it
never skipped weekends or holidays. A plan that put Laminagem on a
Sunday was "feasible" on paper and impossible in the factory.

`FactoryCalendarDay` is the working-time master: one row per
(tenant, date). `is_working_day=False` means the decoder must not place
work there; `shift_hours` is the productive capacity of a working day
(NELO runs a single ~8h shift by default — overridable per row so a
half-day or an overtime Saturday can be modelled).

The NELO ERP has **no** holiday/calendar table (284 tables scanned, none
match feriado/calendario). The ETL in
`src/adapters/nelo/etl/calendar.py` therefore *seeds* the calendar:
Portuguese national holidays + every Saturday/Sunday are marked
non-working; the remaining weekdays are working at the default shift.

The decoder consumes this through `FactoryState.calendar` (a
`FactoryCalendar` value object) — see `src/plan/cpo/state.py`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class FactoryCalendarDay(TenantBase):
    """One calendar day for one tenant — working flag + shift capacity."""

    __tablename__ = "factory_calendar_day"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "day",
            name="uq_factory_calendar_day_tenant_day",
        ),
        {"schema": "plan"},
    )

    #: The calendar date this row describes.
    day: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    #: Whether the factory produces on this day. False for weekends and
    #: public holidays — the decoder skips non-working days entirely.
    is_working_day: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
    )

    #: Productive hours available on this day. NELO runs a single shift
    #: (~8h); a half-day or an overtime Saturday is modelled by editing
    #: this figure. 0 on a non-working day.
    shift_hours: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("8.00"),
    )

    #: Human label: "Sábado", "Domingo", "Feriado — Dia de Portugal",
    #: or empty for an ordinary working day.
    label: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover — debug aid
        kind = "work" if self.is_working_day else "off"
        return f"<FactoryCalendarDay {self.day} {kind} {self.shift_hours}h>"
