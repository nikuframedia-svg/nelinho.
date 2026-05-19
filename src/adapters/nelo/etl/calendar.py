"""Q.48.A — calendar mirror (ERP → plan.factory_calendar_day).

The factory capacity calendar (F10) tells the CPO scheduler which days the
factory works. Without it the scheduler assumes every day is a working day
and produces plans that ignore weekends, holidays and the August shutdown.

This mirror builds ``plan.factory_calendar_day`` from two ERP readers:

* ``list_work_days()``  → ``DIAS_TRABALHO`` (~15.6 k registered working days)
* ``list_holidays()``   → ``FERIAS`` (~29 holiday / vacation dates)

Merge rule: a date present in ``DIAS_TRABALHO`` is a working day; a date in
``FERIAS`` is a non-working holiday. When both lists contain the same date
the **holiday wins** — ``FERIAS`` is the explicit "factory closed" signal,
so it overrides a stray work-day registration.

Idempotent: upsert by ``calendar_date``. Re-running never duplicates and
the flags converge to the same value every run.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, Optional
from uuid import UUID

from src.adapters.nelo import services
from src.plan.models.factory_calendar import FactoryCalendarDay

from .runner import EtlRunner, EtlRunResult
from .sync import register_mirror

logger = logging.getLogger(__name__)


def _build_calendar(
    work_days: list,
    holidays: list,
) -> tuple[list[Dict[str, Any]], int]:
    """Merge the two ERP readers into ``plan.factory_calendar_day`` rows.

    Returns ``(rows, skipped)``. A reader row with no usable date is
    skipped + logged — never crashed (QA01 spirit: explicit, not silent).
    The holiday list overrides the work-day list on the same date.
    """
    by_date: Dict[date, Dict[str, Any]] = {}
    skipped = 0

    for wd in work_days:
        d = wd.work_date.date() if wd.work_date is not None else None
        if d is None:
            skipped += 1
            logger.warning("work-day row skipped — no date (id=%s)", wd.work_day_id)
            continue
        by_date[d] = {
            "calendar_date": d,
            "is_working_day": True,
            "is_holiday": False,
            "holiday_kind": None,
        }

    for hol in holidays:
        d = hol.holiday_date.date() if hol.holiday_date is not None else None
        if d is None:
            skipped += 1
            logger.warning("holiday row skipped — no date")
            continue
        # Holiday wins over a work-day registration for the same date.
        by_date[d] = {
            "calendar_date": d,
            "is_working_day": False,
            "is_holiday": True,
            "holiday_kind": (hol.kind or None),
        }

    return list(by_date.values()), skipped


async def mirror_calendar(
    *,
    session,
    tenant_id: UUID,
    since: Optional[date] = None,
) -> EtlRunResult:
    """Mirror the ERP work calendar into ``plan.factory_calendar_day``."""
    async with EtlRunner(session, tenant_id, source="calendar") as run:
        work_days = await services.list_work_days()
        holidays = await services.list_holidays()
        run.count_read(len(work_days) + len(holidays))

        rows, skipped = _build_calendar(work_days, holidays)
        run.count_skipped(skipped)

        await run.upsert(
            FactoryCalendarDay, rows,
            key_fields=["calendar_date"],
            update_fields=["is_working_day", "is_holiday", "holiday_kind"],
        )
        logger.info(
            "calendar mirror — %d work day(s), %d holiday(s) → %d calendar row(s)",
            len(work_days), len(holidays), len(rows),
        )
    return run.result


register_mirror("calendar", mirror_calendar)
