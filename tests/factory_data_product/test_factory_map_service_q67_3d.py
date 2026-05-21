"""
Q.67.3.D — Coverage tests for `FactoryMapService` covering the branches the
original test file did not reach:

* `_snapshot_cache_get` TTL expiry.
* `boat_view` lookup by `product_name` (non-numeric of_id).
* `boat_view` returns None when neither lookup mode matches.
* `_safe_semantic` error paths (no service / missing method / raising method).
* `_bottlenecks_from_orders` fallback when the curated layer is empty.
* `_trust_payload` exception branch returning structured "unavailable".

These exercise read-only behaviour with the queue-based `FakeSession` from
`tests/conftest.py`. No real DB.
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from src.factory_data_product.services.factory_map_service import (
    Availability,
    FactoryMapService,
    RiskFlag,
    _reset_snapshot_cache_for_tests,
    _snapshot_cache,
    _snapshot_cache_get,
    _snapshot_cache_put,
)
from tests.conftest import FakeSession, TEST_TENANT_ID


# ---------------------------------------------------------------------------
# Fixtures — reset the module-level snapshot cache between tests.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_snapshot_cache():
    _reset_snapshot_cache_for_tests()
    yield
    _reset_snapshot_cache_for_tests()


def _queue(session, *, scalar=None, scalars=None):
    """Match the helper used in the existing factory_map test file."""
    session.queue_scalar(scalar)
    session.queue_scalars(scalars if scalars is not None else [])


# ---------------------------------------------------------------------------
# Snapshot cache: hit, miss, expiry
# ---------------------------------------------------------------------------


def test_snapshot_cache_get_returns_none_on_cold_cache():
    """Cold cache → None. Foundational invariant for the cache wrapper."""
    assert _snapshot_cache_get(TEST_TENANT_ID) is None


def test_snapshot_cache_put_and_get_roundtrip():
    """Put + same-tenant get returns the stored payload (within TTL)."""
    payload = {"hello": "world"}
    _snapshot_cache_put(TEST_TENANT_ID, payload)
    assert _snapshot_cache_get(TEST_TENANT_ID) == payload


def test_snapshot_cache_expires_after_ttl():
    """Past the TTL the entry is evicted on the next get. We force expiry
    by rewriting the stored expiry timestamp into the past — much faster
    than waiting 45s."""
    _snapshot_cache_put(TEST_TENANT_ID, {"x": 1})
    # Force the stored expiry into the past.
    _, payload = _snapshot_cache[str(TEST_TENANT_ID)]
    _snapshot_cache[str(TEST_TENANT_ID)] = (time.monotonic() - 1.0, payload)
    assert _snapshot_cache_get(TEST_TENANT_ID) is None
    # And the entry must be removed (next put/get starts cold).
    assert str(TEST_TENANT_ID) not in _snapshot_cache


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


def test_availability_all_false_by_default():
    """A bare Availability is all-False — the snapshot only flips a flag
    once a source actually returns data, so the default must NOT lie."""
    a = Availability()
    d = a.as_dict()
    assert all(v is False for v in d.values())
    assert d["pricing"] is False  # pricing depends on a Sprint Q.0 ship


def test_risk_flag_carries_evidence_payload():
    """RiskFlag.evidence is a free-form dict the API echoes back so the
    frontend can render contextual numbers (days overdue, etc.)."""
    flag = RiskFlag(
        code="LATE_VS_TRANSPORT", severity="HIGH",
        message="Boat overdue", evidence={"days_overdue": 3},
    )
    assert flag.evidence == {"days_overdue": 3}
    assert flag.code == "LATE_VS_TRANSPORT"


# ---------------------------------------------------------------------------
# `_safe_semantic` — defensive paths
# ---------------------------------------------------------------------------


def test_safe_semantic_returns_none_when_service_not_injected():
    """No semantic service → None. The snapshot uses this everywhere; a
    raise here would 500 the entire Factory Map."""
    svc = FactoryMapService(FakeSession(), TEST_TENANT_ID, semantic_service=None)
    assert svc._safe_semantic("get_wip") is None


def test_safe_semantic_returns_none_when_method_missing():
    """An injected but partial semantic service must not crash the call;
    a missing attribute returns None instead of AttributeError."""
    partial = SimpleNamespace()  # no methods
    svc = FactoryMapService(FakeSession(), TEST_TENANT_ID, semantic_service=partial)
    assert svc._safe_semantic("get_wip") is None


def test_safe_semantic_swallows_method_exception():
    """If the semantic method itself blows up, `_safe_semantic` returns
    None and logs the failure — the snapshot continues."""
    class _BoomSemantic:
        def get_wip(self):
            raise RuntimeError("backend down")

    svc = FactoryMapService(
        FakeSession(), TEST_TENANT_ID, semantic_service=_BoomSemantic(),
    )
    assert svc._safe_semantic("get_wip") is None


# ---------------------------------------------------------------------------
# boat_view — non-numeric of_id + missing-order branches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_boat_view_falls_back_to_product_name_for_non_numeric_of_id():
    """If `of_id` isn't an integer, the lookup falls back to
    `product_name` equality. Returns the order if found."""
    session = FakeSession()
    order = SimpleNamespace(
        legacy_id=4242,
        product_name="K1 Vanquish",
        product_type="K1",
        current_phase_name="Laminagem",
        status="IN_PROGRESS",
        created_date=date.today() - timedelta(days=5),
        completed_date=None,
        transport_date=None,
    )
    _queue(session, scalar=order)          # ProductionOrder by product_name
    _queue(session, scalars=[])            # empty trajectory

    svc = FactoryMapService(session, TEST_TENANT_ID)
    result = await svc.boat_view(of_id="K1 Vanquish")
    assert result is not None
    assert result["of_id"] == "4242"
    assert result["product_name"] == "K1 Vanquish"
    # No transport_date → no risk flag fired.
    assert result["risk_flags"] == []


@pytest.mark.asyncio
async def test_boat_view_returns_none_for_non_numeric_when_not_found():
    """Non-numeric of_id that doesn't match any product_name → None
    (mirrors the missing-id case for numeric of_id)."""
    session = FakeSession()
    _queue(session, scalar=None)
    svc = FactoryMapService(session, TEST_TENANT_ID)
    assert await svc.boat_view(of_id="DOES_NOT_EXIST") is None


@pytest.mark.asyncio
async def test_boat_view_serialises_full_trajectory_row():
    """A populated CuratedOrderPhase row must serialise every public field
    exactly: phase_id, phase_name, seq, start/end, horas, estado, mold_id.
    The frontend reads these names verbatim."""
    session = FakeSession()
    order = SimpleNamespace(
        legacy_id=77,
        product_name="K2",
        product_type="K2",
        current_phase_name="Pintura",
        status="IN_PROGRESS",
        created_date=date(2026, 1, 1),
        completed_date=None,
        transport_date=None,
    )
    phase = SimpleNamespace(
        fase_id="F-PIN", fase_nome="Pintura", ordem=3,
        data_inicio=date(2026, 1, 5), data_fim=date(2026, 1, 7),
        horas_reais=Decimal("4.50"), horas_previstas=Decimal("3.00"),
        estado="DONE", molde_id="M-3",
    )
    _queue(session, scalar=order)
    _queue(session, scalars=[phase])

    svc = FactoryMapService(session, TEST_TENANT_ID)
    result = await svc.boat_view(of_id="77")
    assert result is not None
    assert len(result["trajectory"]) == 1
    t = result["trajectory"][0]
    assert t["phase_id"] == "F-PIN"
    assert t["phase_name"] == "Pintura"
    assert t["seq"] == 3
    assert t["start"] == "2026-01-05"
    assert t["end"] == "2026-01-07"
    assert t["horas_reais"] == 4.5
    assert t["horas_previstas"] == 3.0
    assert t["estado"] == "DONE"
    assert t["mold_id"] == "M-3"


# ---------------------------------------------------------------------------
# `_bottlenecks_from_orders` — fallback when curated phases empty
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bottlenecks_from_db_falls_back_to_orders_when_curated_empty():
    """When the curated `order_phase` backlog query returns no rows, the
    service falls back to grouping IN_PROGRESS ProductionOrders by phase
    name. The busiest phase is flagged `is_critical=True`."""
    session = FakeSession()
    # 1st query: backlog from CuratedOrderPhase → empty (triggers fallback).
    _queue(session, scalars=[])
    # 2nd query: ProductionOrder GROUP BY current_phase_name.
    _queue(session, scalars=[
        ("Laminagem", 5),
        ("Pintura", 2),
        ("Cura", 3),
    ])
    svc = FactoryMapService(session, TEST_TENANT_ID)
    rows = await svc._bottlenecks_from_db(top_n=5)
    assert rows  # non-empty
    by_name = {r["fase_nome"]: r for r in rows}
    # Busiest is Laminagem (5 barcos) — must be flagged critical.
    assert by_name["Laminagem"]["score"] == 5
    assert by_name["Laminagem"]["is_critical"] is True
    # Sorted descending by score.
    scores = [r["score"] for r in rows]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_bottlenecks_from_orders_returns_empty_when_no_in_progress():
    """No IN_PROGRESS orders → empty list (no false signal)."""
    session = FakeSession()
    _queue(session, scalars=[])  # empty curated backlog
    _queue(session, scalars=[])  # empty order grouping
    svc = FactoryMapService(session, TEST_TENANT_ID)
    rows = await svc._bottlenecks_from_db(top_n=5)
    assert rows == []


# ---------------------------------------------------------------------------
# `_trust_payload` — exception branch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trust_payload_returns_structured_unavailable_on_failure():
    """When the trust index calculator raises, `_trust_payload` returns
    `{composite: None, error: <ExceptionType>}` — never leaks the raw
    message (Onda 2.2 invariant)."""
    svc = FactoryMapService(FakeSession(), TEST_TENANT_ID)
    with patch(
        "src.dqa.trust_v2.TrustIndexV2Calculator.compute_for_scope",
        new=AsyncMock(side_effect=RuntimeError("db gone")),
    ):
        result = await svc._trust_payload()
    assert result["composite"] is None
    assert "error" in result
    # Exception TYPE only, not the message.
    assert "db gone" not in result["error"]


# ---------------------------------------------------------------------------
# `_throughput_eur_day` — exception branch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_throughput_eur_day_returns_unavailable_on_service_failure():
    """Identical contract to `_trust_payload`: type-only error key,
    structured `status=unavailable`."""
    svc = FactoryMapService(FakeSession(), TEST_TENANT_ID)
    with patch(
        "src.profit.services.throughput_service.ThroughputService.load_targets",
        new=AsyncMock(side_effect=ValueError("missing config")),
    ):
        result = await svc._throughput_eur_day()
    assert result["status"] == "unavailable"
    assert "reason" in result
    assert "missing config" not in result["reason"]
