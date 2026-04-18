"""
Tests for src.core.services.default_configs (Sprint L.4).

Validates that:
* Every seed tuple is well-formed (uses allowed vocabularies).
* Weight sets (fitness, trust) sum to 1.0 — invariant of Blueprint v2.0 §5.5 / §4.5.
* Trust gates are monotonically increasing.
* Seeder is idempotent: a second run writes zero rows.
"""

from __future__ import annotations

import math

import pytest

from src.core.models.tenant_configuration import (
    ALLOWED_CATEGORIES,
    ALLOWED_DATA_TYPES,
    TenantConfiguration,
)
from src.core.services.default_configs import (
    DEFAULT_SEEDS,
    iter_seeds,
    seed_tenant_defaults,
)
from src.core.services.tenant_config_service import (
    TenantConfigService,
    _reset_cache_for_tests,
)


@pytest.fixture(autouse=True)
def _stub_publish(monkeypatch):
    async def fake_publish(_topic, _event):
        return True

    monkeypatch.setattr(
        "src.shared.kafka_client.publish_event",
        fake_publish,
        raising=True,
    )


@pytest.fixture(autouse=True)
def _clear_cache():
    _reset_cache_for_tests()


# ---------------------------------------------------------------------------
# Static sanity — contract with Blueprint v2.0
# ---------------------------------------------------------------------------

def test_seed_list_non_empty():
    assert len(DEFAULT_SEEDS) > 60, (
        "Blueprint v2.0 enumerates ~80+ requirements; seed list is suspiciously small"
    )


def test_all_seeds_use_allowed_vocabularies():
    for category, key, _value, data_type, _note in DEFAULT_SEEDS:
        assert category in ALLOWED_CATEGORIES, f"unknown category {category!r} for {key!r}"
        assert data_type in ALLOWED_DATA_TYPES, f"unknown data_type {data_type!r} for {key!r}"
        assert key, "key must not be empty"


def test_no_duplicate_keys_in_seed_list():
    seen: set[tuple[str, str]] = set()
    for category, key, _value, _dt, _note in DEFAULT_SEEDS:
        assert (category, key) not in seen, f"duplicate seed {category}.{key}"
        seen.add((category, key))


def test_fitness_weights_sum_to_one():
    weights = {
        k: v for c, k, v, _dt, _note in DEFAULT_SEEDS
        if c == "planning" and k.startswith("fitness.weight.")
    }
    total = sum(weights.values())
    assert math.isclose(total, 1.0, abs_tol=1e-6), (
        f"Blueprint v2.0 §5.5 requires fitness weights sum to 1.0 — got {total}: {weights}"
    )


def test_trust_weights_sum_to_one():
    weights = {
        k: v for c, k, v, _dt, _note in DEFAULT_SEEDS
        if c == "trust" and k.startswith("weights.")
    }
    total = sum(weights.values())
    assert math.isclose(total, 1.0, abs_tol=1e-6), (
        f"Blueprint v2.0 §4.5 requires Trust Index weights sum to 1.0 — got {total}"
    )


def test_trust_gates_monotonic():
    gate_order = [
        "gates.solver_suggestion_only",
        "gates.use_p90_durations",
        "gates.auto_reorder",
        "gates.auto_commit",
        "gates.quality_disposition",
    ]
    by_key = {
        k: v for c, k, v, _dt, _note in DEFAULT_SEEDS
        if c == "trust" and k.startswith("gates.")
    }
    values = [by_key[k] for k in gate_order]
    assert values == sorted(values), (
        f"Blueprint v2.0 §4.5 prescribes gates in strict ascending order; got {values}"
    )


def test_cpo_phase_budgets_do_not_exceed_total():
    # Blueprint v2.0 §5.5: total cascade budget is the sum of phase budgets.
    phases = {
        k: v for c, k, v, _dt, _note in DEFAULT_SEEDS
        if c == "planning" and k.startswith("cpo.") and k.endswith("_budget_s")
        and k != "cpo.total_budget_s"
    }
    total_entries = [
        v for c, k, v, _dt, _note in DEFAULT_SEEDS
        if c == "planning" and k == "cpo.total_budget_s"
    ]
    assert len(total_entries) == 1
    total = total_entries[0]
    assert sum(phases.values()) <= total + 1e-6, (
        f"Phase budgets {phases} exceed total {total}"
    )


def test_iter_seeds_is_a_fresh_copy():
    a = iter_seeds()
    b = iter_seeds()
    assert a == b
    a.pop()
    # mutating `a` must not affect the module-level list
    assert len(iter_seeds()) == len(DEFAULT_SEEDS)


# ---------------------------------------------------------------------------
# Seeder behaviour
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_seed_writes_all_keys_when_tenant_is_empty(fake_session, tenant_id):
    # For each seed, the service will:
    #   1. run get_category to populate the cache (empty first time per category)
    #   2. call set() → _current_row lookup (None)
    # Our FakeSession can't easily distinguish, so we queue `None` scalars
    # generously. The cache means get_category is only hit ~once per category.
    categories = {c for c, *_ in DEFAULT_SEEDS}
    for _ in categories:
        fake_session.queue_scalars([])  # first get_category per category
    for _ in DEFAULT_SEEDS:
        fake_session.queue_scalar(None)  # _current_row for each set

    svc = TenantConfigService(fake_session, tenant_id)
    written = await seed_tenant_defaults(svc)
    assert written == len(DEFAULT_SEEDS)
    # every seed produces one added row
    assert len(fake_session.added) == len(DEFAULT_SEEDS)


@pytest.mark.asyncio
async def test_seed_is_idempotent(fake_session, tenant_id):
    # First get_category returns a row matching EVERY seed key in that category.
    # Group seeds by category so we can return them all in one shot.
    by_category: dict[str, list] = {}
    for c, k, v, dt, _note in DEFAULT_SEEDS:
        by_category.setdefault(c, []).append((k, v, dt))

    for category, entries in by_category.items():
        rows = [
            TenantConfiguration(
                tenant_id=tenant_id,
                category=category,
                key=k,
                value=TenantConfiguration.wrap(v),
                data_type=dt,
                valid_from=_now(),
                created_at=_now(),
                last_modified_at=_now(),
            )
            for k, v, dt in entries
        ]
        fake_session.queue_scalars(rows)

    svc = TenantConfigService(fake_session, tenant_id)
    written = await seed_tenant_defaults(svc)
    assert written == 0
    assert fake_session.added == []  # no writes


@pytest.mark.asyncio
async def test_seed_rejects_non_idempotent_mode(fake_session, tenant_id):
    svc = TenantConfigService(fake_session, tenant_id)
    with pytest.raises(NotImplementedError):
        await seed_tenant_defaults(svc, skip_existing=False)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _now():
    from datetime import datetime
    return datetime.utcnow()
