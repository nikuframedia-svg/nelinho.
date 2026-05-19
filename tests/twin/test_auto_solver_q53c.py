"""Q.53.C — automatic CP-SAT solver for twin scenarios.

The auditor finding: `simulate()` only ever did a linear KPI projection
and `solve()` only ran CP-SAT when the caller passed operations/machines
explicitly. Q.53.C makes the solver run automatically when a scenario
carries a `scheduling_input` delta — and labels every result honestly
with `mode` so a linear projection is never dressed up as a real solve.

CP-SAT itself is exercised by the SchedulingAdapter suite; here we only
assert the auto-detect + honest-mode wiring, with `_run_cpsat` patched.
"""

from __future__ import annotations

from typing import Any, List
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from src.twin.models import Scenario, ScenarioDelta, ScenarioStatus
from src.twin.service import TwinService

TENANT = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

_OPS = [
    {
        "operation_id": "op1",
        "order_id": "ord1",
        "duration_minutes": 60.0,
        "sequence": 0,
    }
]
_MACHINES = [{"machine_id": "m1", "name": "Molde 1", "capacity": 1}]


def _scheduling_delta(*, scenario_id: UUID, ops=None, machines=None) -> ScenarioDelta:
    return ScenarioDelta(
        id=uuid4(),
        tenant_id=TENANT,
        scenario_id=scenario_id,
        sequence=0,
        entity_type="scheduling_input",
        entity_key="cpsat",
        patch={
            "operations": ops if ops is not None else _OPS,
            "machines": machines if machines is not None else _MACHINES,
        },
    )


def _scenario(*, deltas=None) -> Scenario:
    s = Scenario(
        id=uuid4(),
        tenant_id=TENANT,
        title="auto-solve scenario",
        description="d",
        status=ScenarioStatus.DRAFT.value,
        baseline_state={"wip_theoretical": {"value": 280}},
    )
    s.deltas = list(deltas or [])
    return s


def _db(seeded: List[Scenario]):
    db = AsyncMock()

    async def _execute(stmt):
        ids = {s.id for s in seeded}
        try:
            params = stmt.compile().params
        except Exception:
            params = {}
        wanted_id = next((v for v in params.values() if v in ids), None)
        hits = [s for s in seeded if wanted_id is None or s.id == wanted_id]

        class _Result:
            def scalar_one_or_none(self_):
                return hits[0] if hits else None

        return _Result()

    db.execute = _execute
    db.add = lambda obj: None
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.flush = AsyncMock()
    return db


# ─── _extract_scheduling_input ──────────────────────────────────────────


def test_extract_scheduling_input_returns_none_without_delta():
    sc = _scenario()
    assert TwinService._extract_scheduling_input(sc) is None


def test_extract_scheduling_input_ignores_non_scheduling_deltas():
    other = ScenarioDelta(
        id=uuid4(), tenant_id=TENANT, scenario_id=uuid4(),
        sequence=0, entity_type="capacity_adjustment",
        entity_key="A", patch={"capacity_increase_pct": 10},
    )
    sc = _scenario(deltas=[other])
    assert TwinService._extract_scheduling_input(sc) is None


def test_extract_scheduling_input_finds_ops_and_machines():
    sc = _scenario()
    sc.deltas = [_scheduling_delta(scenario_id=sc.id)]
    out = TwinService._extract_scheduling_input(sc)
    assert out is not None
    operations, machines = out
    assert operations[0]["operation_id"] == "op1"
    assert machines[0]["machine_id"] == "m1"


def test_extract_scheduling_input_skips_empty_lists():
    """A scheduling_input delta with empty lists is NOT sufficient data."""
    sc = _scenario()
    sc.deltas = [_scheduling_delta(scenario_id=sc.id, ops=[], machines=[])]
    assert TwinService._extract_scheduling_input(sc) is None


# ─── simulate() honest mode ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_simulate_without_scheduling_input_is_linear_projection():
    sc = _scenario()
    svc = TwinService(_db([sc]), TENANT)
    out = await svc.simulate(sc.id)
    assert out["mode"] == "projecao_linear"
    assert "solver" not in out
    assert "projectados linearmente" in out["mode_reason"]


@pytest.mark.asyncio
async def test_simulate_auto_runs_cpsat_when_scheduling_input_present(monkeypatch):
    sc = _scenario()
    sc.deltas = [_scheduling_delta(scenario_id=sc.id)]

    fake_schedule = {"assignments": [{"operation_id": "op1", "machine_id": "m1"}]}
    monkeypatch.setattr(
        TwinService, "_run_cpsat",
        staticmethod(lambda ops, machines, tl: fake_schedule),
    )

    svc = TwinService(_db([sc]), TENANT)
    out = await svc.simulate(sc.id)

    assert out["mode"] == "solver_cpsat"
    assert out["solver"]["status"] == "SOLVED"
    assert out["solver"]["engine"] == "cpsat"
    assert out["solver"]["schedule"] == fake_schedule


@pytest.mark.asyncio
async def test_simulate_solver_error_does_not_crash_simulation(monkeypatch):
    """If CP-SAT blows up, the linear projection still returns — the
    solver block reports SOLVER_ERROR rather than failing the whole sim."""
    sc = _scenario()
    sc.deltas = [_scheduling_delta(scenario_id=sc.id)]

    def _boom(ops, machines, tl):
        raise RuntimeError("cpsat exploded")

    monkeypatch.setattr(TwinService, "_run_cpsat", staticmethod(_boom))

    svc = TwinService(_db([sc]), TENANT)
    out = await svc.simulate(sc.id)

    assert out["solver"]["status"] == "SOLVER_ERROR"
    assert "before" in out and "after" in out


# ─── solve() auto-detect ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_solve_uses_scenario_delta_when_no_args(monkeypatch):
    sc = _scenario()
    sc.deltas = [_scheduling_delta(scenario_id=sc.id)]

    monkeypatch.setattr(
        TwinService, "_run_cpsat",
        staticmethod(lambda ops, machines, tl: {"ok": True}),
    )

    svc = TwinService(_db([sc]), TENANT)
    out = await svc.solve(sc.id)

    assert out["status"] == "SOLVED"
    assert out["input_source"] == "scenario_delta"


@pytest.mark.asyncio
async def test_solve_request_args_take_precedence(monkeypatch):
    sc = _scenario()
    sc.deltas = [_scheduling_delta(scenario_id=sc.id)]

    monkeypatch.setattr(
        TwinService, "_run_cpsat",
        staticmethod(lambda ops, machines, tl: {"ok": True}),
    )

    svc = TwinService(_db([sc]), TENANT)
    out = await svc.solve(sc.id, operations=_OPS, machines=_MACHINES)

    assert out["status"] == "SOLVED"
    assert out["input_source"] == "request"


@pytest.mark.asyncio
async def test_solve_insufficient_data_is_labelled_linear_projection():
    sc = _scenario()  # no scheduling_input delta
    svc = TwinService(_db([sc]), TENANT)
    out = await svc.solve(sc.id)
    assert out["status"] == "INSUFFICIENT_DATA"
    assert out["mode"] == "projecao_linear"
    assert "scheduling_input" in out["reason"]
