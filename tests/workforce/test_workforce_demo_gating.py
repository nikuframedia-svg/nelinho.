"""Sprint Q.8 Fase 6 — Workforce demo-mode gating regression.

When the curated layer is unavailable, the dependency-graph endpoint
must surface a 503 to the UI by default. The synthetic demo graph is
only returned when the caller explicitly opts in via `?demo=true` —
otherwise a CEO seeing an empty database would have looked at fake
mock nodes labelled "João Silva" and thought their factory was running
fine.

These tests exercise the service directly so we don't have to spin up a
full FastAPI client; the API layer is a thin pass-through that just
converts the exception to HTTP 503.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.workforce.service import (
    WorkforceDataUnavailableError,
    WorkforceService,
)

_TENANT = uuid4()


class _FailingDB:
    """Simulates a DB session whose `execute()` always blows up — i.e.
    the curated tables are missing or the connection is severed."""

    async def execute(self, *_args, **_kwargs):
        raise RuntimeError("simulated curated layer outage")


class _EmptyDB:
    """Simulates a DB session whose `execute()` returns zero rows —
    i.e. the curated tables exist but no NELO Excel has been ingested."""

    async def execute(self, *_args, **_kwargs):
        class _R:
            def all(self):
                return []
        return _R()


@pytest.mark.asyncio
async def test_dependency_graph_raises_when_curated_outage_and_no_demo():
    svc = WorkforceService(_FailingDB(), tenant_id=_TENANT, allow_mock=False)  # type: ignore[arg-type]
    with pytest.raises(WorkforceDataUnavailableError):
        await svc.get_dependency_graph()


@pytest.mark.asyncio
async def test_dependency_graph_raises_when_curated_empty_and_no_demo():
    svc = WorkforceService(_EmptyDB(), tenant_id=_TENANT, allow_mock=False)  # type: ignore[arg-type]
    with pytest.raises(WorkforceDataUnavailableError):
        await svc.get_dependency_graph()


@pytest.mark.asyncio
async def test_dependency_graph_returns_mock_when_demo_opt_in():
    svc = WorkforceService(_FailingDB(), tenant_id=_TENANT, allow_mock=True)  # type: ignore[arg-type]
    out = await svc.get_dependency_graph()

    # The marker that the UI keys off to render the demo banner.
    assert out["fallback_mock"] is True
    assert out["source"] == "mock"
    # Mock graph carries at least the 8 demo phases; structure check
    # is enough — we don't want to pin specific labels in a smoke test.
    assert len(out["nodes"]) > 0


@pytest.mark.asyncio
async def test_cascade_impact_raises_when_curated_outage_and_no_demo():
    svc = WorkforceService(_FailingDB(), tenant_id=_TENANT, allow_mock=False)  # type: ignore[arg-type]
    with pytest.raises(WorkforceDataUnavailableError):
        await svc.calculate_cascade_impact("LAMINAGEM")


@pytest.mark.asyncio
async def test_cascade_impact_returns_mock_when_demo_opt_in():
    svc = WorkforceService(_FailingDB(), tenant_id=_TENANT, allow_mock=True)  # type: ignore[arg-type]
    out = await svc.calculate_cascade_impact("LAMINAGEM")

    # Mock cascade carries the 4 hard-coded levels.
    assert "levels" in out
    assert len(out["levels"]) == 4
