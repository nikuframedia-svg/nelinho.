"""
Tests for src.core.services.tenant_config_service (Sprint L.2).

Strategy mirrors the governance tests: use `FakeSession` and stub the Kafka
publish call. No real DB — persistence will be validated by testcontainers in
Sprint V.2.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

import pytest

from src.core.models.tenant_configuration import TenantConfiguration
from src.core.services.tenant_config_service import (
    TenantConfigNotFoundError,
    TenantConfigService,
    TenantConfigValidationError,
    _reset_cache_for_tests,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _stub_publish(monkeypatch):
    """Replace publish_event so tests never hit Kafka."""
    calls: list[tuple[str, Any]] = []

    async def fake_publish(topic: str, event: Any) -> bool:
        calls.append((topic, event))
        return True

    # Patch at the point-of-use inside the service's lazy import.
    monkeypatch.setattr(
        "src.shared.kafka_client.publish_event",
        fake_publish,
        raising=True,
    )
    yield calls


@pytest.fixture(autouse=True)
def _clear_cache():
    _reset_cache_for_tests()
    yield
    _reset_cache_for_tests()


@pytest.fixture
def svc(fake_session, tenant_id) -> TenantConfigService:
    return TenantConfigService(fake_session, tenant_id)


def _row(
    tenant_id,
    category: str,
    key: str,
    value: Any,
    data_type: str = "int",
    valid_to: datetime | None = None,
    config_id=None,
) -> TenantConfiguration:
    return TenantConfiguration(
        id=config_id or uuid4(),
        tenant_id=tenant_id,
        category=category,
        key=key,
        value=TenantConfiguration.wrap(value),
        data_type=data_type,
        valid_from=datetime.utcnow(),
        valid_to=valid_to,
        created_at=datetime.utcnow(),
        last_modified_at=datetime.utcnow(),
    )


# ---------------------------------------------------------------------------
# get / get_category / get_typed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_returns_default_when_missing(fake_session, svc):
    fake_session.queue_scalars([])  # empty category
    assert await svc.get("planning", "cpo.ga.gen_count", default=200) == 200


@pytest.mark.asyncio
async def test_get_raises_when_missing_without_default(fake_session, svc):
    fake_session.queue_scalars([])
    with pytest.raises(TenantConfigNotFoundError):
        await svc.get("planning", "cpo.ga.gen_count")


@pytest.mark.asyncio
async def test_get_category_returns_unwrapped_values(fake_session, svc, tenant_id):
    fake_session.queue_scalars([
        _row(tenant_id, "planning", "cpo.ga.gen_count", 200),
        _row(tenant_id, "planning", "fitness.makespan_weight", 0.20, data_type="float"),
    ])
    values = await svc.get_category("planning")
    assert values == {
        "cpo.ga.gen_count": 200,
        "fitness.makespan_weight": 0.20,
    }


@pytest.mark.asyncio
async def test_get_category_uses_cache_on_second_call(fake_session, svc, tenant_id):
    # First call hits the DB; only queue one result set.
    fake_session.queue_scalars([
        _row(tenant_id, "planning", "cpo.ga.gen_count", 200),
    ])
    first = await svc.get_category("planning")
    second = await svc.get_category("planning")
    assert first == second == {"cpo.ga.gen_count": 200}
    # If cache were bypassed, the second execute would receive [] and return {}.


@pytest.mark.asyncio
async def test_get_typed_validates_type(fake_session, svc, tenant_id):
    fake_session.queue_scalars([
        _row(tenant_id, "planning", "laminagem.require_pair", True, data_type="bool"),
    ])
    assert await svc.get_typed("planning", "laminagem.require_pair", bool) is True


@pytest.mark.asyncio
async def test_get_typed_raises_on_type_mismatch(fake_session, svc, tenant_id):
    fake_session.queue_scalars([
        _row(tenant_id, "planning", "cpo.ga.gen_count", "not-an-int", data_type="int"),
    ])
    with pytest.raises(TenantConfigValidationError):
        await svc.get_typed("planning", "cpo.ga.gen_count", int)


@pytest.mark.asyncio
async def test_unknown_category_rejected(svc):
    with pytest.raises(TenantConfigValidationError):
        await svc.get_category("not_a_real_category")


# ---------------------------------------------------------------------------
# set
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_set_new_key_without_previous_row(fake_session, svc, tenant_id, _stub_publish):
    fake_session.queue_scalar(None)  # _current_row → no existing

    row = await svc.set(
        "planning", "cpo.ga.gen_count", 200,
        user_id=None, data_type="int",
    )

    assert row.tenant_id == tenant_id
    assert row.category == "planning"
    assert row.key == "cpo.ga.gen_count"
    assert row.raw_value == 200
    assert row.data_type == "int"
    assert row.valid_to is None
    assert len(fake_session.added) == 1
    assert fake_session.flush_calls == 1
    assert _stub_publish  # one CONFIG_UPDATED event published


@pytest.mark.asyncio
async def test_set_closes_previous_active_row(fake_session, svc, tenant_id):
    existing = _row(tenant_id, "planning", "cpo.ga.gen_count", 50)
    assert existing.valid_to is None
    fake_session.queue_scalar(existing)

    new_row = await svc.set(
        "planning", "cpo.ga.gen_count", 200,
        user_id=None, data_type="int",
    )

    # previous row was closed in-place
    assert existing.valid_to is not None
    # new row added
    assert new_row in fake_session.added
    assert new_row.raw_value == 200


@pytest.mark.asyncio
async def test_set_invalid_category(svc):
    with pytest.raises(TenantConfigValidationError):
        await svc.set("wrong", "k", 1, user_id=None, data_type="int")


@pytest.mark.asyncio
async def test_set_invalid_data_type(svc):
    with pytest.raises(TenantConfigValidationError):
        await svc.set("planning", "k", 1, user_id=None, data_type="bigint")


@pytest.mark.asyncio
async def test_set_invalidates_cache(fake_session, svc, tenant_id):
    # Prime the cache.
    fake_session.queue_scalars([_row(tenant_id, "planning", "k", 1)])
    await svc.get_category("planning")

    # Now set; cache should be dropped.
    fake_session.queue_scalar(None)
    await svc.set("planning", "k2", 2, user_id=None, data_type="int")

    # Next get_category should re-query (queue the new scalars).
    fake_session.queue_scalars([
        _row(tenant_id, "planning", "k", 1),
        _row(tenant_id, "planning", "k2", 2),
    ])
    values = await svc.get_category("planning")
    assert values == {"k": 1, "k2": 2}


# ---------------------------------------------------------------------------
# bulk / history / rollback / snapshot
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_set(fake_session, svc):
    # each set → one _current_row query
    fake_session.queue_scalar(None)
    fake_session.queue_scalar(None)

    written = await svc.bulk_set(
        [
            {"category": "planning", "key": "a", "value": 1, "data_type": "int"},
            {"category": "planning", "key": "b", "value": 2, "data_type": "int"},
        ],
        user_id=None,
    )
    assert len(written) == 2
    assert {r.key for r in written} == {"a", "b"}


@pytest.mark.asyncio
async def test_history_returns_ordered_rows(fake_session, svc, tenant_id):
    # The service relies on the query's ORDER BY — in the mock we just hand
    # back the rows in the order we queue them, so the test validates only
    # that the service doesn't reverse/filter them.
    r1 = _row(tenant_id, "planning", "k", 1)
    r2 = _row(tenant_id, "planning", "k", 2)
    fake_session.queue_scalars([r2, r1])
    history = await svc.history("planning", "k")
    assert [h.raw_value for h in history] == [2, 1]


@pytest.mark.asyncio
async def test_rollback_clones_historical_version(fake_session, svc, tenant_id):
    old_id = uuid4()
    old = _row(tenant_id, "planning", "k", 42, config_id=old_id)
    fake_session.queue_scalar(old)     # rollback() lookup
    fake_session.queue_scalar(None)    # set() → _current_row

    restored = await svc.rollback(old_id, user_id=None)
    assert restored.raw_value == 42
    assert restored.key == "k"
    assert restored.category == "planning"


@pytest.mark.asyncio
async def test_rollback_missing_id(fake_session, svc):
    fake_session.queue_scalar(None)
    with pytest.raises(TenantConfigNotFoundError):
        await svc.rollback(uuid4(), user_id=None)


@pytest.mark.asyncio
async def test_export_snapshot_roundtrip(fake_session, svc, tenant_id):
    fake_session.queue_scalars([
        _row(tenant_id, "planning", "a", 1, data_type="int"),
        _row(tenant_id, "mold", "maintenance_threshold_cycles", 500, data_type="int"),
    ])
    snapshot = await svc.export_snapshot()
    assert snapshot == {
        "planning": {"a": {"value": 1, "data_type": "int"}},
        "mold": {"maintenance_threshold_cycles": {"value": 500, "data_type": "int"}},
    }


@pytest.mark.asyncio
async def test_import_snapshot_writes_all(fake_session, svc):
    # 2 keys × 1 _current_row lookup each
    fake_session.queue_scalar(None)
    fake_session.queue_scalar(None)

    count = await svc.import_snapshot(
        {
            "planning": {"a": {"value": 1, "data_type": "int"}},
            "mold": {"x": {"value": 500, "data_type": "int"}},
        },
        user_id=None,
    )
    assert count == 2


# ---------------------------------------------------------------------------
# Best-effort event emission must not break writes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_set_still_succeeds_if_event_publish_fails(fake_session, svc, monkeypatch):
    async def boom(_topic, _event):
        raise RuntimeError("Kafka down")

    monkeypatch.setattr("src.shared.kafka_client.publish_event", boom, raising=True)
    fake_session.queue_scalar(None)

    row = await svc.set("planning", "k", 1, user_id=None, data_type="int")
    # Row still added; no exception bubbled up.
    assert row in fake_session.added
