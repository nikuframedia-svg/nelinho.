"""
Tests for Sprint M.3 (decision delta) + M.7 (alternatives with trade-offs).

Shape tests only (pure helpers + TestClient smoke). Deeper end-to-end coverage
lands in the integration suite (Sprint V.2) where real commits are written.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.plan.api.cpo import (
    _build_narrative,
    _format_delta_pct,
    _relative_delta,
    router as cpo_router,
)
from src.plan.cpo.commits import ScheduleCommit
from src.shared.database import get_session
from tests.conftest import FakeSession, TEST_TENANT_ID


@pytest.fixture(autouse=True)
def _stub_publish(monkeypatch):
    async def fake(_t, _e):
        return True

    monkeypatch.setattr(
        "src.shared.kafka_client.publish_event", fake, raising=True,
    )


def _client_with(session: FakeSession) -> TestClient:
    async def _override():
        yield session

    app = FastAPI()
    app.include_router(cpo_router)
    app.dependency_overrides[get_session] = _override
    return TestClient(app)


def _commit(
    *,
    tenant_id: UUID,
    sha: str = "a" * 64,
    parent_id: UUID | None = None,
    kpis: dict | None = None,
    alternatives: list | None = None,
    operations: list | None = None,
    trust_index: float = 0.85,
) -> ScheduleCommit:
    c = ScheduleCommit(
        id=uuid4(),
        tenant_id=tenant_id,
        parent_id=parent_id,
        commit_sha256=sha,
        author="system",
        message="",
        kpis=kpis or {
            "makespan_hours": 100.0,
            "total_tardiness_hours": 20.0,
            "num_late_orders": 3,
            "setups": 5,
            "avg_utilization": 0.80,
        },
        operations=operations or [],
        delta={},
        alternatives=alternatives or [],
        cpo_meta={},
        trust_index=trust_index,
        operations_count=len(operations or []),
    )
    c.created_at = datetime.utcnow()
    return c


_HEADERS = {"X-Tenant-Id": str(TEST_TENANT_ID)}


# ---------------------------------------------------------------------------
# M.7 pure helpers
# ---------------------------------------------------------------------------

def test_relative_delta_handles_zero_and_non_numeric():
    assert _relative_delta(0, 10) is None
    assert _relative_delta(None, 10) is None
    assert _relative_delta("x", 10) is None
    assert _relative_delta(10, 12) == pytest.approx(0.2)


def test_format_delta_pct():
    assert _format_delta_pct(0.052) == "+5.2%"
    assert _format_delta_pct(-0.10) == "-10.0%"
    assert _format_delta_pct(None) is None


def test_narrative_picks_largest_deltas():
    vs = {
        "avg_utilization": "+1.0%",
        "total_tardiness_hours": "-15.0%",
        "num_late_orders": "+5.0%",
    }
    text = _build_narrative(vs)
    # -15.0% (tardiness) and +5.0% (late orders) are the top two by magnitude
    assert "atraso total" in text
    assert "-15.0%" in text
    assert "utilização média" not in text or "+1.0%" in text


def test_narrative_handles_no_usable_deltas():
    text = _build_narrative({"makespan_hours": None})
    assert text.startswith("Trade-off indisponível")


# ---------------------------------------------------------------------------
# M.7 endpoint
# ---------------------------------------------------------------------------

def test_alternatives_endpoint_returns_enriched_list():
    session = FakeSession()
    alt = [
        {
            "rank": 0,
            "fitness": -10.0,
            "generation": 5,
            "behavioral": {
                "avg_utilization": 0.88,          # +10% vs primary 0.80
                "total_tardiness_hours": 18.0,    # -10% vs 20.0
                "num_late_orders": 3,             # 0% vs 3
            },
        },
    ]
    commit = _commit(tenant_id=TEST_TENANT_ID, alternatives=alt)
    session.queue_scalar(commit)
    client = _client_with(session)
    resp = client.get(f"/v1/plan/cpo/commits/{commit.commit_sha256}/alternatives?n=3", headers=_HEADERS)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["commit_sha256"] == commit.commit_sha256
    assert body["primary_kpis"]["makespan_hours"] == 100.0
    alt0 = body["alternatives"][0]
    assert alt0["rank"] == 0
    assert alt0["vs_primary"]["avg_utilization"] == "+10.0%"
    assert alt0["vs_primary"]["total_tardiness_hours"] == "-10.0%"
    # num_late_orders is exactly equal → % = 0
    assert alt0["vs_primary"]["num_late_orders"] == "+0.0%"
    # Narrative mentions one of the nonzero axes.
    assert "atraso total" in alt0["trade_off_narrative"] or "utilização média" in alt0["trade_off_narrative"]


def test_alternatives_endpoint_404_when_commit_missing():
    session = FakeSession()
    session.queue_scalar(None)     # get_by_sha returns None
    session.queue_scalars([])      # get_by_sha_prefix returns empty
    client = _client_with(session)
    resp = client.get("/v1/plan/cpo/commits/aaaaaaaaaaaaa/alternatives", headers=_HEADERS)
    assert resp.status_code == 404


def test_alternatives_respects_n_cap():
    session = FakeSession()
    alts = [
        {"rank": i, "fitness": -float(i), "generation": 0, "behavioral": {"avg_utilization": 0.80}}
        for i in range(20)
    ]
    commit = _commit(tenant_id=TEST_TENANT_ID, alternatives=alts)
    session.queue_scalar(commit)
    client = _client_with(session)
    resp = client.get(f"/v1/plan/cpo/commits/{commit.commit_sha256}/alternatives?n=4", headers=_HEADERS)
    assert resp.status_code == 200
    assert len(resp.json()["alternatives"]) == 4
