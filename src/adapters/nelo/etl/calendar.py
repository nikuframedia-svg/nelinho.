"""Q.53.B — factory calendar seed (plan.factory_calendar_day).

The NELO ERP (MAR-KAYAKS, 284 tables) has **no** holiday / calendar
table — scanned for `feriado`, `calendario`, `dia_util`, `CALENDARIO`
and found nothing. Working time has always been implicit.

So this mirror does not *mirror* — it **seeds** the working-time
master from first principles:

* every Saturday and Sunday → non-working;
* the Portuguese **national** public holidays (fixed + Easter-derived
  movable feasts) → non-working;
* every other weekday → working at the default single ~8h shift.

It seeds a rolling window of `[today - 30d, today + horizon_days]` so
the CPO scheduler always has calendar coverage for the planning horizon
plus a little history for the adherence report. Idempotent: upsert by
`(tenant_id, day)`, so re-running just refreshes labels / flags.

Municipal holidays (Vila do Conde holds 24 June, São João) are NOT
seeded — they vary and the operator can mark them via the
`/v1/plan/calendar` API. Only the unambiguous national set is auto-seeded.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from src.plan.models.factory_calendar import FactoryCalendarDay
from src.plan.services.factory_calendar import DEFAULT_SHIFT_HOURS

from .runner import EtlRunner, EtlRunResult
from .sync import register_mirror
from src.shared.time import local_today

logger = logging.getLogger(__name__)

#: How far ahead the seed covers — long enough for any CPO horizon.
_DEFAULT_HORIZON_DAYS = 540
#: A little history so the adherence report has calendar context.
_LOOKBACK_DAYS = 30


def _easter_sunday(year: int) -> date:
    """Anonymous Gregorian (Meeus/Jones/Butcher) algorithm for Easter."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def portuguese_national_holidays(year: int) -> Dict[date, str]:
    """The Portuguese **national** public holidays for `year`.

    Fixed dates plus the three Easter-derived movable feasts. Municipal
    holidays (e.g. Vila do Conde 24 Jun) are intentionally excluded —
    they vary by município and are set manually via the calendar API.
    """
    easter = _easter_sunday(year)
    good_friday = easter - timedelta(days=2)
    corpus_christi = easter + timedelta(days=60)

    holidays: Dict[date, str] = {
        date(year, 1, 1): "Feriado — Ano Novo",
        good_friday: "Feriado — Sexta-feira Santa",
        easter: "Feriado — Páscoa",
        date(year, 4, 25): "Feriado — Dia da Liberdade",
        date(year, 5, 1): "Feriado — Dia do Trabalhador",
        corpus_christi: "Feriado — Corpo de Deus",
        date(year, 6, 10): "Feriado — Dia de Portugal",
        date(year, 8, 15): "Feriado — Assunção de Nossa Senhora",
        date(year, 10, 5): "Feriado — Implantação da República",
        date(year, 11, 1): "Feriado — Dia de Todos os Santos",
        date(year, 12, 1): "Feriado — Restauração da Independência",
        date(year, 12, 8): "Feriado — Imaculada Conceição",
        date(year, 12, 25): "Feriado — Natal",
    }
    return holidays


_WEEKDAY_LABEL = {5: "Sábado", 6: "Domingo"}


def build_calendar_rows(
    start: date,
    end: date,
    *,
    shift_hours: float = DEFAULT_SHIFT_HOURS,
) -> List[Dict[str, Any]]:
    """Build one calendar row per day in `[start, end]` (inclusive).

    Weekend → non-working. National holiday → non-working. Anything else
    → working at `shift_hours`.
    """
    # Pre-compute holidays for every year the range touches.
    holidays: Dict[date, str] = {}
    for yr in range(start.year, end.year + 1):
        holidays.update(portuguese_national_holidays(yr))

    rows: List[Dict[str, Any]] = []
    cur = start
    shift_dec = Decimal(str(shift_hours))
    while cur <= end:
        weekday = cur.weekday()
        if cur in holidays:
            rows.append({
                "day": cur,
                "is_working_day": False,
                "shift_hours": Decimal("0.00"),
                "label": holidays[cur],
            })
        elif weekday >= 5:
            rows.append({
                "day": cur,
                "is_working_day": False,
                "shift_hours": Decimal("0.00"),
                "label": _WEEKDAY_LABEL[weekday],
            })
        else:
            rows.append({
                "day": cur,
                "is_working_day": True,
                "shift_hours": shift_dec,
                "label": None,
            })
        cur += timedelta(days=1)
    return rows


async def mirror_calendar(
    *,
    session,
    tenant_id: UUID,
    since: Optional[date] = None,
    horizon_days: int = _DEFAULT_HORIZON_DAYS,
    shift_hours: float = DEFAULT_SHIFT_HOURS,
) -> EtlRunResult:
    """Seed `plan.factory_calendar_day` for a rolling window.

    Window: `[since or today-30d, today + horizon_days]`. Idempotent —
    upsert by `(tenant_id, day)`.
    """
    today = local_today()
    start = since or (today - timedelta(days=_LOOKBACK_DAYS))
    end = today + timedelta(days=horizon_days)

    async with EtlRunner(session, tenant_id, source="calendar") as run:
        rows = build_calendar_rows(start, end, shift_hours=shift_hours)
        run.count_read(len(rows))
        await run.upsert(
            FactoryCalendarDay,
            rows,
            key_fields=["day"],
            update_fields=["is_working_day", "shift_hours", "label"],
        )
        n_off = sum(1 for r in rows if not r["is_working_day"])
        logger.info(
            "calendar seed — %d day(s) [%s..%s], %d non-working",
            len(rows), start, end, n_off,
        )
    return run.result


register_mirror("calendar", mirror_calendar)
