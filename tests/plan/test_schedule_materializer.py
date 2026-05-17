"""Tests for src.plan.services.schedule_materializer.

The materializer turns a CPO `result` dict into `plan.production_schedules`
rows. These tests inject a scripted FakeSession (no live Postgres) and
assert the in-memory logic: per-order sequencing, repeated-phase dedup,
the skip path for orders with no resolvable product, and `_parse_dt`.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import pytest

from src.core.models.operation import Operation
from src.plan.models.schedule import ProductionSchedule
from src.plan.services.schedule_materializer import (
    _parse_dt,
    materialize_cpo_schedule,
)

TENANT = UUID("11111111-1111-1111-1111-111111111111")
PRODUCT_UUID = UUID("22222222-2222-2222-2222-222222222222")


class _FakeResult:
    """Result stub supporting both `.scalar_one_or_none()` and `.all()`."""

    def __init__(self, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = rows or []

    def scalar_one_or_none(self):
        return self._scalar

    def all(self):
        return self._rows


class _FakeSession:
    """Returns canned results FIFO; records added rows; assigns UUIDs on flush."""

    def __init__(self, results):
        self._results = list(results)
        self.added: list = []
        self.committed = False

    async def execute(self, statement):
        if self._results:
            return self._results.pop(0)
        return _FakeResult()

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        for obj in self.added:
            if isinstance(obj, Operation) and obj.id is None:
                obj.id = uuid4()

    async def commit(self):
        self.committed = True


def _op(order_id, phase_id, name, start, end, dur_min=120.0):
    return {
        "operation_id": f"{order_id}::{phase_id}",
        "order_id": order_id,
        "phase_id": phase_id,
        "setup_family": name,
        "start_time": start,
        "end_time": end,
        "duration_minutes": dur_min,
    }


def _schedules(session):
    return [o for o in session.added if isinstance(o, ProductionSchedule)]


# ---------------------------------------------------------------------------
# Happy path — one order, two phases
# ---------------------------------------------------------------------------

class TestMaterialize:
    @pytest.mark.asyncio
    async def test_two_phases_become_two_rows_sequenced_by_start(self):
        ops = [
            _op("100", "20", "Pintura", "2026-05-17T14:00:00", "2026-05-17T16:00:00"),
            _op("100", "10", "Laminagem", "2026-05-17T08:00:00", "2026-05-17T10:00:00"),
        ]
        # execute order: PO.product_id, Product.id, Operation existing, delete
        session = _FakeSession([
            _FakeResult(scalar=5),
            _FakeResult(scalar=PRODUCT_UUID),
            _FakeResult(rows=[]),
            _FakeResult(),
        ])

        summary = await materialize_cpo_schedule(
            session, TENANT, {"operations": ops}, planning_run_id="sha-abc",
        )

        assert summary == {"rows": 2, "operations_created": 2, "orders_skipped": 0}
        assert session.committed is True

        rows = sorted(_schedules(session), key=lambda r: r.operation_sequence)
        assert len(rows) == 2
        # sequence follows start time, not the order they arrived in
        assert rows[0].operation_sequence == 1
        assert rows[0].scheduled_start_time.hour == 8
        assert rows[1].operation_sequence == 2
        assert rows[1].scheduled_start_time.hour == 14
        assert rows[0].product_id == PRODUCT_UUID
        assert rows[0].engine_used == "cpo_v4"
        assert rows[0].planning_run_id == "sha-abc"

    @pytest.mark.asyncio
    async def test_order_without_product_is_skipped(self):
        ops = [_op("200", "10", "Laminagem", "2026-05-17T08:00:00", "2026-05-17T10:00:00")]
        # PO.product_id resolves None → _resolve_product_uuid stops after 1 query
        session = _FakeSession([
            _FakeResult(scalar=None),
            _FakeResult(rows=[]),  # Operation existing
            _FakeResult(),         # delete
        ])

        summary = await materialize_cpo_schedule(
            session, TENANT, {"operations": ops}, planning_run_id="sha-x",
        )

        assert summary["rows"] == 0
        assert summary["orders_skipped"] == 1
        assert _schedules(session) == []

    @pytest.mark.asyncio
    async def test_repeated_phase_in_one_order_is_deduped(self):
        # Two ops share phase_id "10" — the (tenant, order, operation, run)
        # unique key forbids two rows, so the second is dropped.
        ops = [
            _op("100", "10", "Laminagem", "2026-05-17T08:00:00", "2026-05-17T10:00:00"),
            _op("100", "10", "Laminagem", "2026-05-17T12:00:00", "2026-05-17T14:00:00"),
        ]
        session = _FakeSession([
            _FakeResult(scalar=5),
            _FakeResult(scalar=PRODUCT_UUID),
            _FakeResult(rows=[]),
            _FakeResult(),
        ])

        summary = await materialize_cpo_schedule(
            session, TENANT, {"operations": ops}, planning_run_id="sha-y",
        )

        assert summary["rows"] == 1
        assert len(_schedules(session)) == 1

    @pytest.mark.asyncio
    async def test_empty_operations_returns_zeroes(self):
        session = _FakeSession([])
        summary = await materialize_cpo_schedule(
            session, TENANT, {"operations": []}, planning_run_id="sha-z",
        )
        assert summary == {"rows": 0, "operations_created": 0, "orders_skipped": 0}
        assert session.committed is False


# ---------------------------------------------------------------------------
# _parse_dt
# ---------------------------------------------------------------------------

class TestParseDt:
    def test_parses_iso_string(self):
        assert _parse_dt("2026-05-17T08:30:00") == datetime(2026, 5, 17, 8, 30, 0)

    def test_passes_through_datetime(self):
        dt = datetime(2026, 5, 17, 9, 0, 0)
        assert _parse_dt(dt) is dt

    def test_garbage_returns_none(self):
        assert _parse_dt("not-a-date") is None
        assert _parse_dt(None) is None
