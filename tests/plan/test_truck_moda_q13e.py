"""Sprint Q.13.E E.2 — Truck `complete_truck` detector targets moda=26.

Plan v4 §3.6: NELO trucks have a ceiling of 50 boats but the real-world
load distribution clusters at 26 (moda). The previous detector
suggested "fill the truck" up to 50, which:

  * Demanded a production rate the schedule couldn't sustain.
  * Made the suggestion list feel hallucinatory ("we never load 50").

These tests pin the contract:
  * The detector triggers when `assigned < moda` (not just < capacity*0.5).
  * The suggested number of boats is `moda - assigned`, capped by
    available unassigned orders.
  * The "what" / "why" copy mentions the modal target.
  * When `assigned >= moda`, no suggestion fires.
"""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

from src.plan.services.transport_suggestions import (
    DEFAULT_TRUCK_CAPACITY,
    DEFAULT_TRUCK_CAPACITY_MODA,
    TransportSuggestionsService,
)


_TENANT = UUID("11111111-1111-1111-1111-111111111111")


def test_default_truck_capacity_moda_is_26():
    """The seed value lives in default_configs.py; the constant in
    transport_suggestions mirrors it for callers that bypass ConfigStore."""
    assert DEFAULT_TRUCK_CAPACITY_MODA == 26
    assert DEFAULT_TRUCK_CAPACITY == 50


def _batch(*, capacity_override: int = 0, code: str = "B-1"):
    return SimpleNamespace(
        id=uuid4(),
        code=code,
        truck_capacity_units=capacity_override,
        priority=1,
        transport_date=date.today() + timedelta(days=1),
        status="OPEN",
    )


def _order(idx: int):
    return SimpleNamespace(id=uuid4(), order_number=f"OF-{idx:03d}")


def test_complete_truck_targets_moda_not_ceiling():
    """When 18 of 26 modal slots are filled, suggest +8 (not +32 toward 50)."""
    svc = TransportSuggestionsService(
        session=None,  # type: ignore[arg-type]
        tenant_id=_TENANT,
    )
    batch = _batch(capacity_override=50)
    unassigned = [_order(i) for i in range(40)]

    suggestions = svc._detect_complete_truck(batch, assigned=18, unassigned=unassigned)
    assert len(suggestions) == 1
    suggestion = suggestions[0]
    # 26 - 18 = 8 boats to top up
    assert suggestion.affected_order_ids is None or len(suggestion.affected_order_ids) == 8
    assert "26 barcos" in suggestion.what or "26" in suggestion.what


def test_no_complete_truck_when_at_or_above_moda():
    """26 == moda → no suggestion. 30 > moda → also no suggestion."""
    svc = TransportSuggestionsService(
        session=None,  # type: ignore[arg-type]
        tenant_id=_TENANT,
    )
    batch = _batch(capacity_override=50)
    unassigned = [_order(i) for i in range(20)]

    assert svc._detect_complete_truck(batch, assigned=26, unassigned=unassigned) == []
    assert svc._detect_complete_truck(batch, assigned=30, unassigned=unassigned) == []


def test_complete_truck_caps_to_unassigned_pool():
    """Slack = 26 - 5 = 21 boats wanted, but only 3 unassigned available.
    Suggestion proposes 3 (the available pool), not 21."""
    svc = TransportSuggestionsService(
        session=None,  # type: ignore[arg-type]
        tenant_id=_TENANT,
    )
    batch = _batch(capacity_override=50)
    unassigned = [_order(i) for i in range(3)]

    suggestions = svc._detect_complete_truck(batch, assigned=5, unassigned=unassigned)
    assert len(suggestions) == 1
    # Caps at the available unassigned (3), not at the slack (21)
    assert "3 barco" in suggestions[0].what


def test_complete_truck_respects_lower_batch_capacity_override():
    """If the batch was set to a lower capacity than moda (rare — small
    truck), suggestions cap at the batch capacity, not at moda."""
    svc = TransportSuggestionsService(
        session=None,  # type: ignore[arg-type]
        tenant_id=_TENANT,
    )
    batch = _batch(capacity_override=15)  # smaller-than-moda truck
    unassigned = [_order(i) for i in range(40)]

    suggestions = svc._detect_complete_truck(batch, assigned=10, unassigned=unassigned)
    assert len(suggestions) == 1
    # 15 - 10 = 5 boats, since min(moda=26, capacity=15) = 15
    assert "5 barco" in suggestions[0].what


def test_complete_truck_skips_empty_batch():
    """`assigned == 0` must NOT fire complete_truck — the swap detector
    or a fresh-batch flow handles empty batches differently."""
    svc = TransportSuggestionsService(
        session=None,  # type: ignore[arg-type]
        tenant_id=_TENANT,
    )
    batch = _batch(capacity_override=50)
    unassigned = [_order(i) for i in range(20)]

    assert svc._detect_complete_truck(batch, assigned=0, unassigned=unassigned) == []
