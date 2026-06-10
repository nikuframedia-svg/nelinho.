"""Q.171.E — contrato dos helpers de tempo canónicos (src/shared/time.py).

Os 27 sites DTZ001/005/007/901 restantes foram varridos site-a-site; os
que comparam com timestamps ERP local-naive passaram a `local_now_naive()`.
Estes testes travam o contrato de cada helper (aware vs naive) para que um
refactor não troque a semântica em silêncio.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from src.shared.time import local_now_naive, local_today, utc_now, utc_now_naive


def test_utc_now_e_aware_utc():
    now = utc_now()
    assert now.tzinfo is timezone.utc


def test_utc_now_naive_e_naive_mas_instante_utc():
    naive = utc_now_naive()
    aware = utc_now()
    assert naive.tzinfo is None
    delta = abs((aware.replace(tzinfo=None) - naive).total_seconds())
    assert delta < 5.0, "utc_now_naive tem de ser o MESMO instante UTC sem tz"


def test_local_now_naive_e_naive_e_hora_local():
    naive = local_now_naive()
    assert naive.tzinfo is None
    local = datetime.now()
    assert abs((local - naive).total_seconds()) < 5.0, (
        "local_now_naive é hora LOCAL da fábrica (vs timestamps ERP)"
    )


def test_local_today_e_date_local():
    today = local_today()
    assert isinstance(today, date)
    assert today == datetime.now().date()
