"""Q.67.3.E — pin test for the "doesn't run the CPO" comment in
``sandbox/service.py``.

The sandbox is a quick-look projection: it applies
``estimated_impact`` to ``after_state`` and computes a diff. It must
NEVER touch the real CPO engine — heavy simulation lives in Twin.

We pin this by monkey-patching ``CPOv4Engine.schedule`` (the only
public entrypoint on the CPO engine) and asserting it stays
un-invoked across the full ``simulate()`` happy path.

We also pin that the ``Q.67.5.C`` marker stays inside the
``simulate()`` docstring so the bloqueio doesn't drift away from the
code that embodies it.
"""

from __future__ import annotations

import inspect
from datetime import datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from src.sandbox.models import SandboxScenario, SandboxScenarioStatus
from src.sandbox.service import SandboxService


TENANT = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def _scenario() -> SandboxScenario:
    s = SandboxScenario(
        id=uuid4(),
        tenant_id=TENANT,
        title="Q.67.3.E pin",
        description="d",
        status=SandboxScenarioStatus.DRAFT.value,
        before_state={"wip_theoretical": {"value": 1500, "status": "OK"}},
    )
    s.after_state = {
        "estimated_impact": {
            "wip_theoretical": {"delta": -100, "confidence": 0.9},
        },
    }
    s.created_at = datetime.utcnow()
    s.updated_at = datetime.utcnow()
    s.version = 0
    return s


def _stub_session(seeded):
    """Same CAS-aware fake used in tests/sandbox/test_service.py."""
    session = AsyncMock()

    async def _execute(stmt):
        try:
            params = stmt.compile().params
        except Exception:
            params = {}
        is_update = stmt.__class__.__name__.lower().startswith("update")

        wanted_tenant = None
        wanted_id = None
        wanted_status = None
        for v in params.values():
            if isinstance(v, UUID):
                if wanted_tenant is None:
                    wanted_tenant = v
                else:
                    wanted_id = v
            elif isinstance(v, str) and not is_update:
                wanted_status = v

        ids = {s.id for s in seeded}
        if wanted_tenant in ids:
            wanted_id, wanted_tenant = wanted_tenant, wanted_id

        hits = [
            s
            for s in seeded
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
                    def all(_self):
                        return list(hits)

                return _S()

            @property
            def rowcount(self_):
                return len(hits)

        return _Result()

    session.execute = _execute
    session.add = lambda obj: None
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_sandbox_simulate_does_not_invoke_cpo_q67_3e(monkeypatch):
    """``SandboxService.simulate()`` must NOT call into the CPO
    engine. The heavy simulation lives in Twin; sandbox is a
    quick-look projection only (cf. Q.67.5.C decision)."""
    from src.plan.cpo.engine import CPOv4Engine

    cpo_called: dict[str, int] = {"count": 0}

    def _spy(self, *args, **kwargs):
        cpo_called["count"] += 1
        raise AssertionError(
            "Q.67.3.E violated: SandboxService.simulate() called "
            "CPOv4Engine.schedule(). Sandbox must stay a quick-look "
            "projection; heavy simulation belongs in Twin."
        )

    monkeypatch.setattr(CPOv4Engine, "schedule", _spy, raising=True)

    sc = _scenario()
    session = _stub_session([sc])
    svc = SandboxService(session, TENANT)

    out = await svc.simulate(sc.id)

    assert cpo_called["count"] == 0
    assert out.status == SandboxScenarioStatus.SIMULATED.value
    # The projection diff was computed locally, not by the CPO.
    assert "wip_theoretical" in (out.impact or {})


def test_sandbox_simulate_carries_q67_5c_marker() -> None:
    """Meta-test: the ``simulate()`` docstring must carry the
    Q.67.5.C marker + the explicit pointer at Twin / CPO async
    entrypoints. Drift on this comment means the auto-approval
    boundary has been re-opened without re-acknowledging the
    decision in ``src/sandbox/CLAUDE.md``."""
    source = inspect.getsource(SandboxService.simulate)

    assert "Q.67.5.C" in source, (
        "SandboxService.simulate lost its Q.67.5.C marker — restore "
        "the bloqueio comment before merging."
    )
    assert "trust_index" in source, (
        "SandboxService.simulate lost the trust_index reference — "
        "Q.67.5.C explicitly pins that sandbox does NOT compute it."
    )
    # Both real paths to auto-approval must stay grep-able.
    assert "/v1/plan/cpo/schedule" in source
    assert "/v1/twin/scenarios" in source
