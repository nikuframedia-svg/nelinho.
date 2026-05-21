"""Sprint Q.10 Fase A.1 — TwinService unit tests.

Cover the CRUD + simulate + solve + hash paths without hitting a real
database. Uses AsyncMock for the session and a simple in-memory store
for scenarios so the tests can chain create → apply_delta → simulate
in the same way the production flow does.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from src.twin.models import Scenario, ScenarioDelta, ScenarioStatus
from src.twin.service import TwinService


TENANT = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def _stub_scenario(*, tenant_id: UUID = TENANT, deltas=None, status=None) -> Scenario:
    s = Scenario(
        id=uuid4(),
        tenant_id=tenant_id,
        title="t",
        description="d",
        status=(status or ScenarioStatus.DRAFT.value),
        baseline_state={"throughput_eur_day": {"value": 30000.0}, "wip": {"value": 280}},
    )
    s.deltas = list(deltas or [])
    return s


def _stub_db(seeded: List[Scenario]):
    """A session.execute() stub that filters by tenant + scenario_id like
    SQLAlchemy would. Returns a result whose .scalar_one_or_none() and
    .scalars().all() honour the same filter.
    """
    db = AsyncMock()

    async def _execute(stmt):
        try:
            params = stmt.compile().params
        except Exception:
            params = {}

        wanted_tenant = None
        wanted_id = None
        wanted_status = None
        for v in params.values():
            if isinstance(v, UUID):
                if wanted_tenant is None:
                    wanted_tenant = v
                else:
                    wanted_id = v
            elif isinstance(v, str):
                wanted_status = v

        # We can't reliably tell the order — try both
        ids = {s.id for s in seeded}
        if wanted_tenant in ids:
            wanted_id, wanted_tenant = wanted_tenant, wanted_id

        hits = [
            s for s in seeded
            if (wanted_tenant is None or s.tenant_id == wanted_tenant)
            and (wanted_id is None or s.id == wanted_id)
            and (wanted_status is None or s.status == wanted_status)
        ]

        class _Result:
            def scalar_one_or_none(self_):
                return hits[0] if hits else None

            def scalars(self_):
                class _S:
                    def all(_self):
                        return list(hits)
                return _S()

        return _Result()

    db.execute = _execute
    db.add = lambda obj: None
    db.delete = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_create_scenario_persists_to_db():
    db = _stub_db([])
    svc = TwinService(db, TENANT)
    s = await svc.create_scenario(title="My scenario", description="x", created_by="luis")
    assert s.tenant_id == TENANT
    assert s.title == "My scenario"
    assert s.status == ScenarioStatus.DRAFT.value
    db.flush.assert_awaited()
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_apply_delta_appends_with_incrementing_sequence():
    """Calling apply_delta twice on the same scenario yields sequences
    0 and 1 — the autoincrement comes from max(existing) + 1.

    Q.54.I — usa `entity_type` reais (a validação Q.54.I rejeita tipos
    fora da whitelist); o patch fica vazio para não accionar a validação
    numérica — este teste só exercita o auto-incremento da sequência."""
    existing_delta = ScenarioDelta(
        id=uuid4(), tenant_id=TENANT, scenario_id=uuid4(),
        sequence=0, entity_type="capacity_adjustment", entity_key="A", patch={},
    )
    sc = _stub_scenario(deltas=[existing_delta])
    existing_delta.scenario_id = sc.id

    db = _stub_db([sc])
    svc = TwinService(db, TENANT)

    new_delta = await svc.apply_delta(
        scenario_id=sc.id,
        entity_type="standard_time", entity_key="B", patch={},
        applied_by="luis",
    )
    assert new_delta.sequence == 1


@pytest.mark.asyncio
async def test_apply_delta_rejects_unknown_scenario():
    db = _stub_db([])
    svc = TwinService(db, TENANT)
    with pytest.raises(ValueError, match="not found"):
        await svc.apply_delta(
            scenario_id=uuid4(),
            entity_type="m", entity_key="x", patch={},
        )


@pytest.mark.asyncio
async def test_get_scenario_isolates_by_tenant():
    """A scenario belonging to OTHER_TENANT is invisible to TENANT."""
    sc = _stub_scenario(tenant_id=OTHER_TENANT)
    db = _stub_db([sc])
    svc = TwinService(db, TENANT)
    out = await svc.get_scenario(sc.id)
    assert out is None


@pytest.mark.asyncio
async def test_simulate_returns_before_after_and_delta_summary():
    sc = _stub_scenario()
    db = _stub_db([sc])
    svc = TwinService(db, TENANT)
    result = await svc.simulate(sc.id)
    assert "before" in result and "after" in result
    assert "delta_summary" in result
    assert "simulated_at" in result
    # No deltas applied → after equals before for non-metadata keys
    assert result["before"] == result["after"]


@pytest.mark.asyncio
async def test_simulate_marks_scenario_simulated():
    sc = _stub_scenario()
    db = _stub_db([sc])
    svc = TwinService(db, TENANT)
    await svc.simulate(sc.id)
    assert sc.status == ScenarioStatus.SIMULATED.value
    assert sc.simulated_at is not None
    assert sc.scenario_hash  # populated


@pytest.mark.asyncio
async def test_solve_returns_insufficient_data_without_operations():
    """Without operations[] / machines[], the solver short-circuits
    rather than fabricating mock KPIs."""
    sc = _stub_scenario()
    db = _stub_db([sc])
    svc = TwinService(db, TENANT)
    out = await svc.solve(sc.id)
    assert out["status"] == "INSUFFICIENT_DATA"
    assert "projected_kpis" in out


@pytest.mark.asyncio
async def test_calculate_scenario_hash_is_deterministic():
    """Same baseline + same deltas → identical hash."""
    sc = _stub_scenario()
    svc = TwinService(_stub_db([sc]), TENANT)
    h1 = svc._calculate_scenario_hash(sc)
    h2 = svc._calculate_scenario_hash(sc)
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex


@pytest.mark.asyncio
async def test_calculate_scenario_hash_differs_when_baseline_changes():
    sc1 = _stub_scenario()
    sc2 = _stub_scenario()
    sc2.baseline_state = {"throughput_eur_day": {"value": 99999.0}}
    svc = TwinService(_stub_db([]), TENANT)
    assert svc._calculate_scenario_hash(sc1) != svc._calculate_scenario_hash(sc2)


@pytest.mark.asyncio
async def test_delete_scenario_returns_false_when_not_found():
    db = _stub_db([])
    svc = TwinService(db, TENANT)
    assert await svc.delete_scenario(uuid4()) is False
