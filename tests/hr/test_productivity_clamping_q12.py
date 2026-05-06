"""Sprint Q.12 — Productivity service clamping regression.

Antes a eficiência podia dar 200% (standard 16h, actual 8h) e o
`bonus_eligible` (>=100%) ficava trivialmente true. Agora clamped em
[0, 100].
"""

from __future__ import annotations

from decimal import Decimal

from src.hr.services.productivity_service import _clamp_pct


def test_clamp_above_100() -> None:
    assert _clamp_pct(Decimal("250")) == Decimal("100")


def test_clamp_below_zero() -> None:
    assert _clamp_pct(Decimal("-5")) == Decimal("0")


def test_clamp_within_range_unchanged() -> None:
    assert _clamp_pct(Decimal("57.3")) == Decimal("57.3")


def test_clamp_exactly_100() -> None:
    assert _clamp_pct(Decimal("100")) == Decimal("100")


def test_clamp_exactly_zero() -> None:
    assert _clamp_pct(Decimal("0")) == Decimal("0")
