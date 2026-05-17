"""Q.17.F.9 — tests for the in-memory write-pause registry."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.governance.yaml_policy import pause_registry


@pytest.fixture(autouse=True)
def _reset_registry():
    pause_registry.reset_for_tests()
    yield
    pause_registry.reset_for_tests()


def test_register_then_is_paused_matches_prefix():
    tenant = uuid4()
    pause_registry.register_pause(tenant, "/v1/plan", 15, "Throughput crítico")

    hit = pause_registry.is_paused(tenant, "/v1/plan/cpo/schedule")
    assert hit is not None
    assert hit.route_prefix == "/v1/plan"
    assert hit.reason_pt == "Throughput crítico"


def test_is_paused_miss_for_unrelated_path():
    tenant = uuid4()
    pause_registry.register_pause(tenant, "/v1/plan", 15, "x")
    assert pause_registry.is_paused(tenant, "/v1/quality/rework") is None


def test_is_paused_isolates_tenants():
    tenant_a, tenant_b = uuid4(), uuid4()
    pause_registry.register_pause(tenant_a, "/v1/plan", 15, "x")
    assert pause_registry.is_paused(tenant_b, "/v1/plan/cpo") is None


def test_expired_pause_is_dropped_on_read():
    tenant = uuid4()
    pause_registry.register_pause(tenant, "/v1/plan", 15, "x")
    # Force expiry by rewriting the entry with a past timestamp.
    key = (tenant, "/v1/plan")
    stale = pause_registry.PauseInfo(
        tenant_id=tenant,
        route_prefix="/v1/plan",
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        reason_pt="x",
    )
    pause_registry._PAUSES[key] = stale

    assert pause_registry.is_paused(tenant, "/v1/plan/cpo") is None
    assert pause_registry.active_pauses(tenant) == []


def test_longest_prefix_wins():
    tenant = uuid4()
    pause_registry.register_pause(tenant, "/v1", 15, "amplo")
    pause_registry.register_pause(tenant, "/v1/plan/cpo", 15, "específico")

    hit = pause_registry.is_paused(tenant, "/v1/plan/cpo/schedule")
    assert hit is not None
    assert hit.route_prefix == "/v1/plan/cpo"


def test_register_pause_returns_future_expiry():
    tenant = uuid4()
    before = datetime.now(timezone.utc)
    expires = pause_registry.register_pause(tenant, "/v1/plan", 30, "x")
    assert expires > before + timedelta(minutes=29)
