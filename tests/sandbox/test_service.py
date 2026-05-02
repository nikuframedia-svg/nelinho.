"""Sprint Q.10 Fase B.4 — SandboxService unit tests.

Cover the CRUD + simulate + publish paths with a mocked AsyncSession.
The publish path also exercises the GovernanceService integration
(which is replaced with a fake that returns a deterministic decision id).
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from src.sandbox.models import SandboxScenario, SandboxScenarioStatus
from src.sandbox.service import (
    SandboxNotFoundError,
    SandboxService,
    SandboxStateError,
)


TENANT = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def _scenario(*, tenant_id: UUID = TENANT, status: str = "draft") -> SandboxScenario:
    s = SandboxScenario(
        id=uuid4(),
        tenant_id=tenant_id,
        title="My Sandbox",
        description="d",
        status=status,
        before_state={"wip_theoretical": {"value": 1500, "status": "OK"}},
    )
    s.created_at = datetime.utcnow()
    s.updated_at = datetime.utcnow()
    return s


def _stub_session(seeded):
    """Same pattern used in tests/twin/test_service.py."""
    session = AsyncMock()

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
            def scalar(self_):
                return len(hits)
            def scalars(self_):
                class _S:
                    def all(_self): return list(hits)
                return _S()
        return _Result()

    session.execute = _execute
    session.add = lambda obj: None
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_create_scenario_persists_with_tenant():
    session = _stub_session([])
    svc = SandboxService(session, TENANT)
    s = await svc.create_scenario(title="X", description="y")
    assert s.tenant_id == TENANT
    assert s.status == SandboxScenarioStatus.DRAFT.value
    session.flush.assert_awaited()
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_get_scenario_isolates_by_tenant():
    sc = _scenario(tenant_id=OTHER_TENANT)
    session = _stub_session([sc])
    svc = SandboxService(session, TENANT)
    out = await svc.get_scenario(sc.id)
    assert out is None


@pytest.mark.asyncio
async def test_apply_suggestion_seeds_after_state():
    sc = _scenario()
    session = _stub_session([sc])
    svc = SandboxService(session, TENANT)
    suggestion = {
        "id": "sug_001",
        "estimated_impact": {"oee": {"delta": 3.5, "confidence": 0.85}},
    }
    out = await svc.apply_suggestion(sc.id, suggestion)
    assert out.suggestion_id == "sug_001"
    assert out.after_state is not None
    assert out.after_state["estimated_impact"]["oee"]["delta"] == 3.5


@pytest.mark.asyncio
async def test_apply_suggestion_rejects_unknown_scenario():
    session = _stub_session([])
    svc = SandboxService(session, TENANT)
    with pytest.raises(SandboxNotFoundError):
        await svc.apply_suggestion(uuid4(), {"id": "x", "estimated_impact": {}})


@pytest.mark.asyncio
async def test_simulate_marks_simulated_and_computes_summary():
    sc = _scenario()
    sc.after_state = {
        "estimated_impact": {
            "wip_theoretical": {"delta": -100, "confidence": 0.9},
            "lead_time_observed_days": {"delta": -3, "confidence": 0.75},
        },
    }
    session = _stub_session([sc])
    svc = SandboxService(session, TENANT)
    out = await svc.simulate(sc.id)
    assert out.status == SandboxScenarioStatus.SIMULATED.value
    assert "wip_theoretical" in out.impact
    assert out.impact["wip_theoretical"]["delta"] == -100


@pytest.mark.asyncio
async def test_simulate_rejects_published_scenario():
    sc = _scenario(status=SandboxScenarioStatus.PUBLISHED.value)
    session = _stub_session([sc])
    svc = SandboxService(session, TENANT)
    with pytest.raises(SandboxStateError):
        await svc.simulate(sc.id)


@pytest.mark.asyncio
async def test_publish_creates_real_decision_id(monkeypatch):
    """publish must call GovernanceService.propose_decision and store the
    returned decision id on the scenario — no more mock UUID."""
    sc = _scenario(status=SandboxScenarioStatus.SIMULATED.value)
    sc.impact = {"wip_theoretical": {"delta": -100}}
    session = _stub_session([sc])

    fake_decision_id = uuid4()

    class _FakeGov:
        def __init__(self, *a, **kw): pass
        async def propose_decision(self, **kwargs):
            return {"id": str(fake_decision_id)}

    monkeypatch.setattr(
        "src.governance.service.GovernanceService", _FakeGov,
    )

    svc = SandboxService(session, TENANT)
    out = await svc.publish(sc.id, proposed_by="luis")
    assert out.status == SandboxScenarioStatus.PUBLISHED.value
    assert out.decision_id == fake_decision_id
    assert out.published_at is not None


@pytest.mark.asyncio
async def test_publish_rejects_unsimulated_scenario():
    sc = _scenario(status=SandboxScenarioStatus.DRAFT.value)
    session = _stub_session([sc])
    svc = SandboxService(session, TENANT)
    with pytest.raises(SandboxStateError):
        await svc.publish(sc.id, proposed_by="luis")
