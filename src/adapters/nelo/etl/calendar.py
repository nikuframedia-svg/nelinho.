"""Q.53.B / Q.174.F3 — factory calendar seed (plan.factory_calendar_day).

Q.174.F3 — afinal o ERP TEM calendário oficial: ``DIAS_TRABALHO``
(15.637 linhas, 2016→2078, 13k dias FUTUROS pré-carregados; é a fonte
de ``Report_ProducaoCapacidade``). O scan antigo procurou `feriado`/
`calendario`/`dia_util` e falhou o nome. Quando o espelho
``factory_raw.dias_trabalho`` existe e cobre a janela, os dias úteis
vêm DE LÁ (apanha paragens locais — ex. S. João 24/6 — e pontes que o
gerador nunca soube); o gerador (Seg-Sex + feriados nacionais PT)
fica como fallback para BDs sem o mirror.

Janela rolante `[today - 30d, today + horizon_days]`; idempotente
(upsert por `(tenant_id, day)`). O operador continua a poder marcar
dias via `/v1/plan/calendar` (a API escreve por cima do seed).
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


async def _canonical_working_days(
    session, start: date, end: date,
) -> Optional[set]:
    """Q.174.F3 — dias úteis OFICIAIS de ``factory_raw.dias_trabalho``.

    Devolve o set de dias úteis na janela, ou ``None`` quando o espelho não
    existe OU não cobre a janela até ``end`` (BD dev sem mirror / horizonte
    além de 2078) — o caller cai no gerador. Best-effort, nunca rebenta o seed.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError
    try:
        probe = await session.execute(text(
            "SELECT to_regclass('factory_raw.dias_trabalho') IS NOT NULL"
        ))
        scalar_fn = getattr(probe, "scalar", None)
        if not (callable(scalar_fn) and scalar_fn()):
            return None
        cov = await session.execute(text(
            'SELECT MAX(CAST(NULLIF("DTRB_DATA", \'\') AS timestamp))::date '
            "FROM factory_raw.dias_trabalho"
        ))
        max_day = cov.scalar()
        if max_day is None or max_day < end:
            logger.info(
                "calendar: dias_trabalho não cobre a janela (max=%s < %s) — "
                "gerador", max_day, end,
            )
            return None
        rows = await session.execute(text(
            'SELECT DISTINCT CAST(NULLIF("DTRB_DATA", \'\') AS timestamp)::date '
            "FROM factory_raw.dias_trabalho "
            'WHERE CAST(NULLIF("DTRB_DATA", \'\') AS timestamp)::date '
            "      BETWEEN :s AND :e"
        ), {"s": start, "e": end})
        return {r[0] for r in rows.fetchall()}
    except SQLAlchemyError as exc:  # pragma: no cover — outage
        logger.debug("calendar: dias_trabalho indisponível (%s)", exc)
        return None


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
    upsert by `(tenant_id, day)`. Q.174.F3: dias úteis canónicos de
    ``DIAS_TRABALHO`` quando espelhado; gerador como fallback.
    """
    today = local_today()
    start = since or (today - timedelta(days=_LOOKBACK_DAYS))
    end = today + timedelta(days=horizon_days)

    async with EtlRunner(session, tenant_id, source="calendar") as run:
        rows = build_calendar_rows(start, end, shift_hours=shift_hours)
        canonical = await _canonical_working_days(session, start, end)
        source = "gerador"
        if canonical is not None:
            source = "dias_trabalho"
            shift_dec = Decimal(str(shift_hours))
            for r in rows:
                util = r["day"] in canonical
                if util:
                    r["is_working_day"] = True
                    r["shift_hours"] = shift_dec
                    r["label"] = None
                else:
                    # mantém o nome gerado (Sábado/feriado nacional) quando
                    # existe; senão é paragem que SÓ o ERP conhece.
                    r["is_working_day"] = False
                    r["shift_hours"] = Decimal("0.00")
                    r["label"] = r["label"] or "Paragem (ERP)"
        run.count_read(len(rows))
        await run.upsert(
            FactoryCalendarDay,
            rows,
            key_fields=["day"],
            update_fields=["is_working_day", "shift_hours", "label"],
        )
        n_off = sum(1 for r in rows if not r["is_working_day"])
        logger.info(
            "calendar seed (%s) — %d day(s) [%s..%s], %d non-working",
            source, len(rows), start, end, n_off,
        )
    return run.result


register_mirror("calendar", mirror_calendar)
