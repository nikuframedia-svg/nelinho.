"""Sprint Q.12 — ShiftSchedule duration helper regression.

Lei 7/2009 (PT) — máx 8h normal, 10h com compensação. O helper
`_shift_duration_hours` é chamado pelo SQLAlchemy listener
`before_insert/before_update` que rejeita turnos > 10h.
"""

from __future__ import annotations

from datetime import time

from src.hr.models.allocation import ShiftSchedule


def test_normal_8h_shift_with_1h_break() -> None:
    duration = ShiftSchedule._shift_duration_hours(time(8, 0), time(17, 0), 60)
    assert duration == 8.0


def test_no_break_returns_gross() -> None:
    duration = ShiftSchedule._shift_duration_hours(time(8, 0), time(16, 0), 0)
    assert duration == 8.0


def test_overnight_shift_crosses_midnight() -> None:
    """Turno noturno: 22:00 → 06:00 = 8h brutas, 7h líquidas com 60min de break."""
    duration = ShiftSchedule._shift_duration_hours(time(22, 0), time(6, 0), 60)
    assert duration == 7.0


def test_zero_duration_when_end_equals_start() -> None:
    """Caso degenerado — start==end — 24h brutas (cruza meia-noite). Não negativo."""
    duration = ShiftSchedule._shift_duration_hours(time(12, 0), time(12, 0), 0)
    # end_min <= start_min ⇒ assume cruzamento → 24h brutas.
    assert duration == 24.0


def test_oversized_break_clamped_to_zero() -> None:
    """Break maior que turno não pode dar negativo."""
    duration = ShiftSchedule._shift_duration_hours(time(8, 0), time(9, 0), 120)
    assert duration == 0.0
