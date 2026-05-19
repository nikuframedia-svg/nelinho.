"""
ProdPlan ONE — Factory Capacity Calendar (Sprint Q.48.A / F10)
================================================================

The CPO scheduler used to assume every calendar day is a working day with
a fixed 8h capacity. A plan that ignores the factory's real calendar —
weekends, holidays, the August shutdown — is a plan that fails on contact
with reality.

This table is the **factory capacity calendar**: one row per date, saying
whether the factory works that day. It is populated from the NELO ERP by
the ``calendar`` ETL mirror, which reads:

* ``DIAS_TRABALHO`` (~15.6 k rows) — every registered working day;
* ``FERIAS`` (~29 rows) — holiday / vacation dates.

A date present in ``DIAS_TRABALHO`` is a working day; a date in ``FERIAS``
is a non-working day (``is_holiday=True``). When the two disagree, the
holiday wins — the ERP's holiday list is the explicit "factory closed"
signal.

The scheduler reads this through ``FactoryState.working_days`` and refuses
to place an operation's start on a non-working day. That makes operator
unavailability a *capacity constraint* (Spelke axiom 1): a closed day has
zero capacity, exactly like a worker with no matching skill (axiom 5) is
unavailable for a slot.
"""

from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, Date, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class FactoryCalendarDay(TenantBase):
    """One calendar date and whether the factory works it.

    Unique per ``(tenant_id, calendar_date)``. ``is_working_day`` is the
    field the scheduler gates on; ``is_holiday`` records *why* a day is
    closed (so the calendar can be explained, not just obeyed).
    """

    __tablename__ = "factory_calendar_day"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "calendar_date",
            name="uq_factory_calendar_day_date",
        ),
        Index("ix_factory_calendar_day_tenant_date", "tenant_id", "calendar_date"),
        {"schema": "plan"},
    )

    #: The calendar date this row describes.
    calendar_date: Mapped[date] = mapped_column(Date, nullable=False)

    #: ``True`` when the factory operates on this date. The decoder will
    #: not start an operation on a date where this is ``False``.
    is_working_day: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
    )

    #: ``True`` when the date is a holiday / vacation day (from ``FERIAS``).
    #: A holiday is always a non-working day; this flag records the reason.
    is_holiday: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
    )

    #: Raw ERP holiday kind ("Férias" / "Feriado") when ``is_holiday`` is
    #: ``True``. Free text — the ERP dictionary is not formally confirmed,
    #: so no enum is invented.
    holiday_kind: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
