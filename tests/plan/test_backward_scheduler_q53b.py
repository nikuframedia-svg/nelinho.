"""Q.53.B — backward scheduler: lead time + start-by + suggest-shipment.

Pure unit tests over the functional core (`compute_lead_time`,
`start_by`, `suggest_shipment`). No DB.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from src.plan.services.backward_scheduler import (
    PhaseStep,
    compute_lead_time,
    start_by,
    suggest_shipment,
)
from src.plan.services.factory_calendar import FactoryCalendar


def _no_gaps(_from, _to):
    return 0.0


def _lam_cura_gap(from_phase, to_phase):
    """Curing gap: 15h after LAMINAGEM."""
    if "LAMINAGEM" in str(from_phase).upper() and "CURA" in str(to_phase).upper():
        return 15.0
    return 0.0


def _phases_simple():
    return [
        PhaseStep("p1", "LAMINAGEM", 8.0, seq=1),
        PhaseStep("p2", "CURA", 4.0, seq=2),
        PhaseStep("p3", "MONTAGEM", 8.0, seq=3),
    ]


# ─── Lead time ───────────────────────────────────────────────────────────


def test_lead_time_sums_work_hours():
    bd = compute_lead_time(_phases_simple(), _no_gaps)
    assert bd.work_hours == 20.0
    assert bd.curing_gap_hours == 0.0
    assert bd.total_hours == 20.0
    assert bd.n_phases == 3


def test_lead_time_adds_curing_gaps():
    bd = compute_lead_time(_phases_simple(), _lam_cura_gap)
    assert bd.work_hours == 20.0
    assert bd.curing_gap_hours == 15.0   # LAMINAGEM→CURA
    assert bd.total_hours == 35.0


def test_lead_time_breakdown_steps_are_audit_friendly():
    bd = compute_lead_time(_phases_simple(), _lam_cura_gap)
    assert len(bd.steps) == 3
    # The CURA step carries the 15h gap charged before it.
    cura = next(s for s in bd.steps if s["phase_name"] == "CURA")
    assert cura["curing_gap_hours"] == 15.0


# ─── start-by ────────────────────────────────────────────────────────────


def test_start_by_pulls_target_back_by_lead_time():
    cal = FactoryCalendar(default_shift_hours=8.0)
    # Target: Friday 2026-05-15 08:00. 20h work, no curing.
    target = datetime(2026, 5, 15, 8, 0)
    start, bd = start_by(target, _phases_simple(), _no_gaps, cal)
    # 20h work backward through Mon-Fri 8h shifts:
    #   8h Thu + 8h Wed + 4h Tue → Tue 2026-05-12 12:00
    assert start == datetime(2026, 5, 12, 12, 0)
    assert bd.total_hours == 20.0


def test_start_by_with_curing_gap_starts_no_later():
    """A 15h wall-clock curing gap can only pull the start earlier or
    leave it equal (when calendar snapping absorbs a sub-shift remainder)
    — it can never push the start LATER."""
    cal = FactoryCalendar(default_shift_hours=8.0)
    # Mid-shift target so the gap crosses into the previous working day
    # instead of being collapsed by the shift-end snap.
    target = datetime(2026, 5, 15, 14, 0)  # Friday 14:00
    start_no_gap, _ = start_by(target, _phases_simple(), _no_gaps, cal)
    start_gap, bd = start_by(target, _phases_simple(), _lam_cura_gap, cal)
    assert start_gap <= start_no_gap
    assert bd.curing_gap_hours == 15.0
    # 15h back from Fri 14:00 crosses Thursday → the gap genuinely bites.
    assert start_gap < start_no_gap


# ─── suggest-shipment ────────────────────────────────────────────────────


def test_suggest_shipment_walks_forward_through_calendar():
    cal = FactoryCalendar(default_shift_hours=8.0)
    # Start Monday 2026-05-11 08:00, 20h work.
    start = datetime(2026, 5, 11, 8, 0)
    ship, bd = suggest_shipment(start, _phases_simple(), _no_gaps, cal)
    # 8h Mon + 8h Tue + 4h Wed → Wed 2026-05-13 12:00
    assert ship == datetime(2026, 5, 13, 12, 0)


def test_suggest_shipment_never_lands_on_weekend():
    cal = FactoryCalendar(default_shift_hours=8.0)
    start = datetime(2026, 5, 8, 8, 0)  # Friday
    ship, _ = suggest_shipment(start, _phases_simple(), _no_gaps, cal)
    assert ship.weekday() < 5


def test_start_by_and_suggest_shipment_are_consistent():
    """If start-by says start at S to hit target T, then suggesting a
    shipment from S must land on/before T."""
    cal = FactoryCalendar(default_shift_hours=8.0)
    target = datetime(2026, 5, 22, 8, 0)
    start, _ = start_by(target, _phases_simple(), _lam_cura_gap, cal)
    ship, _ = suggest_shipment(start, _phases_simple(), _lam_cura_gap, cal)
    assert ship <= target


def test_empty_routing_yields_zero_lead_time():
    bd = compute_lead_time([], _no_gaps)
    assert bd.total_hours == 0.0
    assert bd.n_phases == 0
