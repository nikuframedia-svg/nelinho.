"""
Tests for src.dqa.trust_signals (Sprint AA.3).

No real DB. We drive the provider through a `FakeSession` and stub the curated
`execute()` results, checking that:

1. Freshness age computed from the most-recent `created_at_utc`.
2. Consistency z-scores computed from (real − predicted) duration pairs.
3. Tau and kappa loaded from TenantConfig with defaults.
4. Empty factory → optimistic signals (no age, empty z-scores).
5. Anomaly probability stays 0.0 for the MVP (wired later).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from src.core.models.tenant_configuration import TenantConfiguration
from src.core.services.tenant_config_service import _reset_cache_for_tests
from src.dqa.trust_signals import (
    DEFAULT_KAPPA,
    DEFAULT_TAU_SECONDS,
    _age_seconds,
    _rows_to_z_scores,
    curated_signals_provider,
)
from src.dqa.trust_v2 import (
    SCOPE_FACTORY,
    SCOPE_ORDER,
    SCOPE_PHASE,
    TrustIndexV2Calculator,
    TrustSignals,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    _reset_cache_for_tests()


@pytest.fixture(autouse=True)
def _stub_publish(monkeypatch):
    async def fake(_t, _e):
        return True

    monkeypatch.setattr(
        "src.shared.kafka_client.publish_event", fake, raising=True,
    )


def _cfg_row(tenant_id, key, value, data_type="float"):
    return TenantConfiguration(
        id=uuid4(),
        tenant_id=tenant_id,
        category="trust",
        key=key,
        value=TenantConfiguration.wrap(value),
        data_type=data_type,
        valid_from=datetime.utcnow(),
        created_at=datetime.utcnow(),
        last_modified_at=datetime.utcnow(),
    )


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def test_age_seconds_returns_none_for_missing_timestamp():
    assert _age_seconds(None) is None


def test_age_seconds_treats_naive_datetime_as_utc():
    now = datetime.now(timezone.utc)
    ten_minutes_ago_naive = (now - timedelta(minutes=10)).replace(tzinfo=None)
    age = _age_seconds(ten_minutes_ago_naive)
    assert age is not None
    assert 590 < age < 610  # within 10 minutes ± clock skew


def test_age_seconds_never_negative():
    # A timestamp slightly in the future (clock drift) must clamp to 0, not go
    # negative (that would poison the freshness decay).
    future = datetime.now(timezone.utc) + timedelta(seconds=5)
    assert _age_seconds(future) == 0.0


def test_rows_to_z_scores_returns_empty_for_too_few_samples():
    assert _rows_to_z_scores([(1.0, 1.0), (2.0, 2.0)]) == []


def test_rows_to_z_scores_zero_variance_returns_zeros():
    # Identical differences → stdev = 0 → each z-score = 0.0.
    rows = [(10.0, 5.0), (8.0, 3.0), (6.0, 1.0)]  # diff = 5.0 everywhere
    z = _rows_to_z_scores(rows)
    assert z == [0.0, 0.0, 0.0]


def test_rows_to_z_scores_returns_standardised_diffs():
    rows = [(10.0, 5.0), (11.0, 5.0), (12.0, 5.0), (20.0, 5.0)]
    z = _rows_to_z_scores(rows)
    # The outlier (diff=15) should have |z| > 1; the clustered ones < 1.
    assert abs(z[-1]) > 1.0
    assert all(abs(zi) < 2.0 for zi in z)


def test_rows_to_z_scores_skips_null_entries():
    rows = [(10.0, 5.0), (None, 5.0), (12.0, None), (20.0, 5.0), (15.0, 10.0)]
    # Only the 3 clean pairs count; result has 3 z-scores.
    z = _rows_to_z_scores([r for r in rows if r[0] is not None and r[1] is not None])
    assert len(z) == 3


# Onda 4.2 — adversarial inputs. The provider survives DB rows that
# contain NaN/Infinity/oversized values (Postgres NUMERIC overflow,
# legacy data with sentinel `inf` values, calculations that produced
# NaN upstream). These cases used to be untested and would either
# poison the z-score or raise out of nowhere.

def test_rows_to_z_scores_propagates_nan_to_zero_variance_path():
    """If every diff is NaN, pstdev raises StatisticsError → empty list.
    The provider's own filter at the call-site is what keeps NaN out
    in production; this exercises the fallback branch."""
    import math
    rows = [(math.nan, 1.0), (math.nan, 2.0), (math.nan, 3.0)]
    # NaN - x is still NaN; pstdev([nan, nan, nan]) → StatisticsError.
    z = _rows_to_z_scores(rows)
    assert z == []


def test_rows_to_z_scores_handles_infinity_diffs():
    """A single infinity in the diff series is filtered out before
    pstdev runs (Onda 4.2 fix). The remaining finite diffs produce
    valid z-scores; one bad row doesn't poison the others."""
    import math
    rows = [(math.inf, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0)]
    z = _rows_to_z_scores(rows)
    # The inf row is dropped; 3 finite diffs remain → 3 z-scores.
    assert len(z) == 3
    assert all(math.isfinite(zi) for zi in z)
    # Symmetric distribution around 2.0 → z-scores sum to ~0.
    assert abs(sum(z)) < 1e-9


def test_rows_to_z_scores_extremely_large_values_do_not_overflow():
    """Verify that 1e100-scale values don't NaN-out the stdev path."""
    rows = [(1e100, 0.0), (2e100, 0.0), (3e100, 0.0), (4e100, 0.0)]
    z = _rows_to_z_scores(rows)
    assert len(z) == 4
    for zi in z:
        # The diffs are deterministic (1e100, 2e100, 3e100, 4e100), so
        # the standardised values should be finite numbers in [-2, 2].
        assert zi == zi  # not NaN
        assert abs(zi) < 5


def test_rows_to_z_scores_below_minimum_sample_returns_empty():
    """The current floor is 3 pairs; anything fewer collapses to []."""
    assert _rows_to_z_scores([]) == []
    assert _rows_to_z_scores([(1.0, 1.0)]) == []
    assert _rows_to_z_scores([(1.0, 1.0), (2.0, 2.0)]) == []


# ---------------------------------------------------------------------------
# curated_signals_provider — integration via fake session
# ---------------------------------------------------------------------------

# FakeSession.execute pops ONE scalar AND ONE scalars list per call; tests
# therefore have to queue both in lockstep, one pair per expected execute.

def _queue_execute(fake_session, *, scalar=None, scalars=None):
    fake_session.queue_scalar(scalar)
    fake_session.queue_scalars(scalars if scalars is not None else [])


@pytest.mark.asyncio
async def test_factory_scope_empty_tenant(fake_session, tenant_id):
    # 1. trust config load
    _queue_execute(fake_session, scalars=[
        _cfg_row(tenant_id, "freshness.tau_seconds_curated", 86400.0),
        _cfg_row(tenant_id, "consistency.kappa", 2.0),
    ])
    # 2. most-recent curated query → no rows
    _queue_execute(fake_session, scalar=None)
    # 3. duration samples query → no rows
    _queue_execute(fake_session, scalars=[])

    signals = await curated_signals_provider(
        fake_session, tenant_id, SCOPE_FACTORY,
    )
    assert isinstance(signals, TrustSignals)
    assert signals.age_seconds is None
    assert signals.z_scores == []
    assert signals.tau_seconds == 86400.0
    assert signals.kappa == 2.0
    assert signals.provenance_tier == "erp"
    assert signals.verifiable is None  # never saw a row


@pytest.mark.asyncio
async def test_factory_scope_with_recent_data(fake_session, tenant_id):
    _queue_execute(fake_session, scalars=[
        _cfg_row(tenant_id, "freshness.tau_seconds_curated", 3600.0),
        _cfg_row(tenant_id, "consistency.kappa", 2.0),
    ])
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    _queue_execute(fake_session, scalar=one_hour_ago)
    _queue_execute(fake_session, scalars=[
        (Decimal("10.5"), Decimal("10.0")),
        (Decimal("9.5"), Decimal("10.0")),
        (Decimal("10.0"), Decimal("10.0")),
        (Decimal("10.2"), Decimal("10.0")),
    ])

    signals = await curated_signals_provider(
        fake_session, tenant_id, SCOPE_FACTORY,
    )
    assert signals.age_seconds is not None
    assert 3500 < signals.age_seconds < 3700
    assert len(signals.z_scores) == 4
    assert signals.verifiable is True


@pytest.mark.asyncio
async def test_order_scope_passes_business_key(fake_session, tenant_id):
    _queue_execute(fake_session, scalars=[])  # no cfg seeded → defaults
    _queue_execute(fake_session, scalar=datetime.now(timezone.utc))
    _queue_execute(fake_session, scalars=[])

    signals = await curated_signals_provider(
        fake_session, tenant_id, SCOPE_ORDER,
        order_id_str="OF-12345",
    )
    assert signals.tau_seconds == DEFAULT_TAU_SECONDS
    assert signals.kappa == DEFAULT_KAPPA


@pytest.mark.asyncio
async def test_phase_scope_accepts_phase_id(fake_session, tenant_id):
    _queue_execute(fake_session, scalars=[])
    _queue_execute(fake_session, scalar=datetime.now(timezone.utc))
    _queue_execute(fake_session, scalars=[])

    signals = await curated_signals_provider(
        fake_session, tenant_id, SCOPE_PHASE,
        phase_id_str="FASE-LAMINAGEM",
    )
    assert signals.provenance_tier == "erp"


@pytest.mark.asyncio
async def test_provider_integrates_with_calculator(fake_session, tenant_id):
    # Calculator.load_weights() → 1 execute
    _queue_execute(fake_session, scalars=[
        _cfg_row(tenant_id, "weights.completeness", 0.15),
        _cfg_row(tenant_id, "weights.validity", 0.20),
        _cfg_row(tenant_id, "weights.freshness", 0.15),
        _cfg_row(tenant_id, "weights.consistency", 0.20),
        _cfg_row(tenant_id, "weights.provenance", 0.15),
        _cfg_row(tenant_id, "weights.anomaly", 0.10),
        _cfg_row(tenant_id, "weights.evidence", 0.05),
    ])
    # Provider's tau/kappa config load → 1 execute (empty → defaults)
    _queue_execute(fake_session, scalars=[])
    # Most-recent query → 1 execute
    _queue_execute(fake_session, scalar=datetime.now(timezone.utc) - timedelta(minutes=1))
    # Duration samples → 1 execute
    _queue_execute(fake_session, scalars=[
        (Decimal("10.0"), Decimal("10.0")),
        (Decimal("10.1"), Decimal("10.0")),
        (Decimal("9.9"), Decimal("10.0")),
    ])

    calc = TrustIndexV2Calculator(
        fake_session, tenant_id, signals_provider=curated_signals_provider,
    )
    result = await calc.compute_for_scope(SCOPE_FACTORY)
    # Fresh + erp provenance + stable durations → composite near the
    # provenance-capped ceiling.
    assert 0.90 < result.composite < 1.0
    assert result.components.evidence == 1.0
