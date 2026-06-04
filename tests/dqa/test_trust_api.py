"""
Tests for src.dqa.api (Sprint AA.4).

Mounts only the DQA router (and a stubbed `get_session`) so we don't drag
main.py's optional deps into the test process. Verifies:

* 400 on unknown scope
* 422 when X-Tenant-Id is missing
* Happy path returns components + weights + effective_gates
* Prometheus gauge is updated with the composite score
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.models.tenant_configuration import TenantConfiguration
from src.core.services.tenant_config_service import _reset_cache_for_tests
from src.dqa.api import router as dqa_router
from src.shared.database import get_session
from src.shared.metrics import trust_index_score
from tests.conftest import TEST_TENANT_ID, FakeSession


@pytest.fixture(autouse=True)
def _stub_publish(monkeypatch):
    async def fake(_t, _e):
        return True

    monkeypatch.setattr(
        "src.shared.kafka_client.publish_event", fake, raising=True,
    )


@pytest.fixture(autouse=True)
def _clear_cache():
    _reset_cache_for_tests()


@pytest.fixture
def fake_session_and_client():
    session = FakeSession()

    async def _override():
        yield session

    app = FastAPI()
    app.include_router(dqa_router)
    app.dependency_overrides[get_session] = _override
    return session, TestClient(app)


def _queue_execute(fake_session, *, scalar=None, scalars=None):
    fake_session.queue_scalar(scalar)
    fake_session.queue_scalars(scalars if scalars is not None else [])


def _cfg_row(tid, key, value, dt="float"):
    return TenantConfiguration(
        id=uuid4(), tenant_id=tid, category="trust", key=key,
        value=TenantConfiguration.wrap(value),
        data_type=dt,
        valid_from=datetime.utcnow(),
        created_at=datetime.utcnow(),
        last_modified_at=datetime.utcnow(),
    )


_HEADERS = {"X-Tenant-Id": str(TEST_TENANT_ID)}


def test_unknown_scope_returns_400(fake_session_and_client):
    _, client = fake_session_and_client
    resp = client.get("/v1/dqa/trust-index?scope=nonsense", headers=_HEADERS)
    assert resp.status_code == 400


def test_missing_tenant_header_returns_401(fake_session_and_client):
    _, client = fake_session_and_client
    resp = client.get("/v1/dqa/trust-index?scope=factory")
    # require_tenant_header (canónico) → 401 sem tenant (auth), não 422 (validação)
    assert resp.status_code == 401


def test_trust_index_happy_path(fake_session_and_client):
    session, client = fake_session_and_client

    # 1. Calculator.load_weights() — read category "trust"
    _queue_execute(session, scalars=[
        _cfg_row(TEST_TENANT_ID, "weights.completeness", 0.15),
        _cfg_row(TEST_TENANT_ID, "weights.validity", 0.20),
        _cfg_row(TEST_TENANT_ID, "weights.freshness", 0.15),
        _cfg_row(TEST_TENANT_ID, "weights.consistency", 0.20),
        _cfg_row(TEST_TENANT_ID, "weights.provenance", 0.15),
        _cfg_row(TEST_TENANT_ID, "weights.anomaly", 0.10),
        _cfg_row(TEST_TENANT_ID, "weights.evidence", 0.05),
    ])
    # 2. curated_signals_provider — tau/kappa config load (empty → defaults)
    _queue_execute(session, scalars=[])
    # 3. most-recent curated query → no data
    _queue_execute(session, scalar=None)
    # 4. duration samples → empty
    _queue_execute(session, scalars=[])
    # 5. load_gate_config — read category "trust" (cache is already warm from
    #    step 1, so this might not hit the DB; queue a no-op in case)
    _queue_execute(session, scalars=[])

    resp = client.get("/v1/dqa/trust-index?scope=factory", headers=_HEADERS)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["scope"] == "factory"
    assert body["scope_id"] is None

    # With no real data: completeness, validity default to 1.0; freshness 1.0
    # (no age); consistency 1.0 (no z-scores); provenance 0.70 (erp);
    # anomaly 1.0; evidence 1.0 (None → optimistic) → composite = 0.955
    assert 0.95 <= body["composite"] <= 0.96

    # All 7+1 components present
    expected_keys = {
        "completeness", "validity", "freshness", "consistency",
        "provenance", "anomaly", "evidence", "causal_coherence",
    }
    assert expected_keys <= set(body["components"])

    # Effective gates: at 0.955 every gate clears (≥ 0.80)
    assert body["effective_gates"]["quality_disposition"] is True
    assert body["effective_gates"]["auto_commit"] is True


def test_prometheus_gauge_is_updated(fake_session_and_client):
    session, client = fake_session_and_client
    for _ in range(5):  # load_weights + tau/kappa + most-recent + samples + gate cfg
        _queue_execute(session, scalars=[])

    before_samples = list(trust_index_score.collect())
    resp = client.get("/v1/dqa/trust-index?scope=factory", headers=_HEADERS)
    assert resp.status_code == 200
    after_samples = list(trust_index_score.collect())
    # Gauge has at least one sample now with our labels.
    found = False
    for metric in after_samples:
        for s in metric.samples:
            if (
                s.name.endswith("trust_index_score")
                and s.labels.get("entity_type") == "factory"
                and s.labels.get("entity_id") == "global"
            ):
                found = True
                break
    assert found, (before_samples, after_samples)
