"""Sprint C 4.1 / WG1 — ActionExecutor dispatcher.

Covers:
* Registry: register + reject duplicate + list registered types
* Known decision_type → handler invoked + counter incremented
* Unknown decision_type → `no_handler` result + counter untouched
* Handler failure → exception propagates (caller flips to FAILED)
* `_build_default_executor` ships the 3 built-in handlers
* The built-in handlers read their expected keys from `action_data`
* Integration: GovernanceService.execute_decision routes to the
  registered handler (verified via a spy executor)
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from src.governance.action_executor import (
    ActionContext,
    ActionExecutor,
    _build_default_executor,
    _handle_mold_maintenance,
    _handle_reschedule_order,
    _handle_rework_routing,
)


TENANT = UUID("11111111-1111-1111-1111-111111111111")


def _ctx(
    decision_type: str = "reschedule_order",
    action_data: dict | None = None,
) -> ActionContext:
    return ActionContext(
        decision_id=uuid4(),
        decision_type=decision_type,
        tenant_id=TENANT,
        action_data=action_data or {},
        executed_by="alice",
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_registry_starts_empty():
    executor = ActionExecutor()
    assert executor.registered_types() == []
    assert executor.invocation_counts == {}


def test_register_then_list():
    async def _noop(ctx):
        return {}
    executor = ActionExecutor()
    executor.register("reschedule_order", _noop)
    executor.register("mold_maintenance", _noop)
    assert set(executor.registered_types()) == {"reschedule_order", "mold_maintenance"}


def test_register_rejects_duplicate_without_overwrite():
    async def _noop(ctx):
        return {}
    executor = ActionExecutor()
    executor.register("reschedule_order", _noop)
    with pytest.raises(ValueError, match="already registered"):
        executor.register("reschedule_order", _noop)


def test_register_allows_overwrite_when_requested():
    async def _a(ctx):
        return {"marker": "a"}

    async def _b(ctx):
        return {"marker": "b"}

    executor = ActionExecutor()
    executor.register("reschedule_order", _a)
    executor.register("reschedule_order", _b, overwrite=True)
    result = asyncio.run(executor.dispatch(_ctx("reschedule_order")))
    assert result["result"]["marker"] == "b"


# ---------------------------------------------------------------------------
# Dispatch paths
# ---------------------------------------------------------------------------


def test_dispatch_known_type_invokes_handler_and_increments_counter():
    captured = {}

    async def _h(ctx: ActionContext):
        captured["decision_id"] = ctx.decision_id
        captured["action_data"] = ctx.action_data
        return {"ok": True}

    executor = ActionExecutor()
    executor.register("reschedule_order", _h)
    ctx = _ctx("reschedule_order", action_data={"order_id": "OF1"})

    result = asyncio.run(executor.dispatch(ctx))

    assert result["status"] == "handled"
    assert result["decision_type"] == "reschedule_order"
    assert result["result"] == {"ok": True}
    assert captured["decision_id"] == ctx.decision_id
    assert captured["action_data"] == {"order_id": "OF1"}
    assert executor.invocation_counts["reschedule_order"] == 1


def test_dispatch_unknown_type_returns_no_handler_without_counter_change():
    executor = ActionExecutor()
    result = asyncio.run(executor.dispatch(_ctx("mystery_type")))
    assert result["status"] == "no_handler"
    assert result["decision_type"] == "mystery_type"
    assert executor.invocation_counts == {}


def test_dispatch_propagates_handler_exceptions():
    async def _boom(ctx):
        raise RuntimeError("handler blew up")

    executor = ActionExecutor()
    executor.register("reschedule_order", _boom)

    with pytest.raises(RuntimeError, match="handler blew up"):
        asyncio.run(executor.dispatch(_ctx("reschedule_order")))
    # Counter still incremented — the attempt counts even when it fails,
    # so observability captures "we tried, it broke".
    assert executor.invocation_counts["reschedule_order"] == 1


# ---------------------------------------------------------------------------
# Default executor built-ins
# ---------------------------------------------------------------------------


def test_default_executor_ships_three_built_in_types():
    executor = _build_default_executor()
    assert set(executor.registered_types()) == {
        "reschedule_order", "mold_maintenance", "rework_routing",
    }


def test_reschedule_order_handler_echoes_expected_fields():
    ctx = _ctx("reschedule_order", action_data={
        "order_id": "OF-42", "new_start_date": "2026-05-01",
    })
    result = asyncio.run(_handle_reschedule_order(ctx))
    assert result["intent"] == "reschedule_order"
    assert result["order_id"] == "OF-42"
    assert result["new_date"] == "2026-05-01"


def test_mold_maintenance_handler_echoes_expected_fields():
    ctx = _ctx("mold_maintenance", action_data={
        "mold_id": "M-K1-06", "reason": "scheduled deep clean",
    })
    result = asyncio.run(_handle_mold_maintenance(ctx))
    assert result["intent"] == "mold_maintenance"
    assert result["mold_id"] == "M-K1-06"
    assert result["reason"] == "scheduled deep clean"


def test_rework_routing_handler_echoes_expected_fields():
    ctx = _ctx("rework_routing", action_data={
        "rework_id": "RW-7", "assigned_to": "paulo",
    })
    result = asyncio.run(_handle_rework_routing(ctx))
    assert result["intent"] == "rework_routing"
    assert result["rework_id"] == "RW-7"
    assert result["assigned_to"] == "paulo"


# ---------------------------------------------------------------------------
# Integration — GovernanceService.execute_decision uses the executor
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_decision_routes_to_registered_handler(monkeypatch):
    from src.governance.models import DecisionStatus
    from src.governance.service import GovernanceService
    from tests.governance.test_service import _make_decision_run
    from tests.conftest import FakeSession

    run = _make_decision_run(
        tenant_id=TENANT,
        status=DecisionStatus.APPROVED.value,
        decision_type="reschedule_order",
    )
    session = FakeSession()
    session.queue_scalar(run)

    svc = GovernanceService(session, TENANT)

    # Swap the module-level default executor for a spy so we can assert
    # the route without relying on the real handler side effects.
    spy = ActionExecutor()
    calls = []

    async def _spy_handler(ctx):
        calls.append(ctx.decision_type)
        return {"spy": True}

    spy.register("reschedule_order", _spy_handler)
    svc.action_executor = spy

    # Silence Kafka publish so the test stays isolated.
    async def _noop(*a, **kw):
        return True
    monkeypatch.setattr(
        "src.shared.kafka_client.publish_event", _noop, raising=True,
    )

    await svc.execute_decision(str(run.id), executed_by="bob")
    assert calls == ["reschedule_order"]
    assert spy.invocation_counts["reschedule_order"] == 1


@pytest.mark.asyncio
async def test_execute_decision_with_unknown_type_succeeds_without_handler(
    monkeypatch,
):
    """Advisory-mode path: unknown decision_type still lands as EXECUTED
    because the announcement (Kafka event + audit chain) is the primary
    commitment."""
    from src.governance.models import DecisionStatus
    from src.governance.service import GovernanceService
    from tests.governance.test_service import _make_decision_run
    from tests.conftest import FakeSession

    run = _make_decision_run(
        tenant_id=TENANT,
        status=DecisionStatus.APPROVED.value,
        decision_type="unknown_future_type",
    )
    session = FakeSession()
    session.queue_scalar(run)
    svc = GovernanceService(session, TENANT)
    svc.action_executor = ActionExecutor()  # empty registry

    async def _noop(*a, **kw):
        return True
    monkeypatch.setattr(
        "src.shared.kafka_client.publish_event", _noop, raising=True,
    )

    result = await svc.execute_decision(str(run.id), executed_by="bob")
    assert result["status"] == DecisionStatus.EXECUTED.value
