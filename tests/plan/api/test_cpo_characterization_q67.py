"""Q.67.6.A2 — Characterization tests for src/plan/api/cpo.py.

Pin BEHAVIOUR ACTUAL of every CPO endpoint before the decomposition in
Q.67.6.B2. These tests are deliberately black-box: each calls the
endpoint via FastAPI TestClient and asserts (status, body shape) —
nothing about internals. If decomposition preserves behaviour, every
one of these stays green.

Endpoints covered (current state of `router`):

  * POST   /v1/plan/cpo/schedule
  * POST   /v1/plan/cpo/schedule/async
  * GET    /v1/plan/cpo/schedule/job/{job_id}
  * PUT    /v1/plan/cpo/schedule/job/{job_id}/approve
  * GET    /v1/plan/cpo/commits
  * GET    /v1/plan/cpo/commits/{sha}
  * GET    /v1/plan/cpo/commits/{sha}/orders
  * GET    /v1/plan/cpo/commits/{from_sha}/diff/{to_sha}
  * GET    /v1/plan/cpo/timeline
  * GET    /v1/plan/cpo/commits/{sha}/alternatives
  * POST   /v1/plan/cpo/commits/{sha}/decide
  * GET    /v1/plan/cpo/operations/{operation_id}/worker-pairs

Strategy:
  - Mount only the CPO router (no other side-effects).
  - Override `require_tenant_header` (dev tenant) and `get_session`
    (returns a tiny in-memory session) at the dependency level.
  - Patch the heavyweight collaborators (`run_cpo_schedule`,
    `CommitsService.*`, arq pools, `FactoryState.load`, etc.) so each
    test runs in milliseconds and is hermetic.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Shared scaffolding
# ---------------------------------------------------------------------------

DEV_TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _build_app() -> FastAPI:
    """Mount only the CPO router. Override tenant + session deps with stubs."""
    from src.plan.api.cpo import router as cpo_router
    from src.shared.auth.headers import require_tenant_header
    from src.shared.database import get_session

    app = FastAPI()
    app.include_router(cpo_router)
    app.dependency_overrides[require_tenant_header] = lambda: DEV_TENANT
    # Q.171.B — os endpoints async/decide passaram a exigir o contexto de
    # utilizador real (ator de auditoria); override no harness.
    from src.shared.auth.headers import get_current_user_or_dev_header as _gu
    from src.shared.auth.jwt_handler import UserContext as _UC
    from uuid import UUID as _UUID
    app.dependency_overrides[_gu] = lambda: _UC(
        user_id=_UUID("22222222-2222-2222-2222-222222222222"),
        tenant_id=DEV_TENANT, role="manager_operations",
    )

    async def _fake_session():
        # Endpoint tests never touch the real session — every collaborator
        # that uses it is patched. We still need a sentinel so FastAPI can
        # resolve the Depends(...) chain.
        yield MagicMock(name="fake_session")

    app.dependency_overrides[get_session] = _fake_session
    return app


def _make_commit(
    *,
    sha: str = "a" * 64,
    parent_id: Optional[UUID] = None,
    kpis: Optional[Dict[str, Any]] = None,
    operations: Optional[List[Dict[str, Any]]] = None,
    alternatives: Optional[List[Dict[str, Any]]] = None,
    rejected_alternatives: Optional[List[Dict[str, Any]]] = None,
    user_preference_signal: Optional[Dict[str, Any]] = None,
    status_value: str = "DRAFT",
):
    """Build a minimal ScheduleCommit-shaped object for endpoint responses."""
    from src.plan.cpo.commits import ScheduleCommit

    return ScheduleCommit(
        id=uuid4(),
        tenant_id=DEV_TENANT,
        parent_id=parent_id,
        commit_sha256=sha,
        author="system",
        message="characterization-test",
        kpis=kpis or {"makespan_hours": 100.0, "avg_utilization": 0.75},
        operations=operations or [],
        delta={},
        alternatives=alternatives or [],
        cpo_meta={},
        rejected_alternatives=rejected_alternatives or [],
        user_preference_signal=user_preference_signal or {},
        evidence_refs=[],
        scenarios_tested=0,
        trust_index=0.8,
        operations_count=len(operations or []),
        status=status_value,
    )


# ---------------------------------------------------------------------------
# Router registration — every endpoint pinned by path + method
# ---------------------------------------------------------------------------

EXPECTED_ROUTES = [
    ("POST", "/v1/plan/cpo/schedule"),
    ("POST", "/v1/plan/cpo/schedule/async"),
    ("GET", "/v1/plan/cpo/schedule/job/{job_id}"),
    ("PUT", "/v1/plan/cpo/schedule/job/{job_id}/approve"),
    ("GET", "/v1/plan/cpo/commits"),
    ("GET", "/v1/plan/cpo/commits/{sha}"),
    ("GET", "/v1/plan/cpo/commits/{sha}/orders"),
    ("GET", "/v1/plan/cpo/commits/{from_sha}/diff/{to_sha}"),
    ("GET", "/v1/plan/cpo/timeline"),
    ("GET", "/v1/plan/cpo/commits/{sha}/alternatives"),
    ("POST", "/v1/plan/cpo/commits/{sha}/decide"),
    ("GET", "/v1/plan/cpo/operations/{operation_id}/worker-pairs"),
]


def test_router_exposes_all_expected_endpoints():
    from src.plan.api.cpo import router

    pairs = set()
    for r in router.routes:
        for method in getattr(r, "methods", set()) or set():
            pairs.add((method, r.path))
    for method, path in EXPECTED_ROUTES:
        assert (method, path) in pairs, (
            f"endpoint {method} {path} missing — refactor likely dropped it"
        )


def test_router_prefix_and_tags_pinned():
    from src.plan.api.cpo import router

    assert router.prefix == "/v1/plan/cpo"
    assert "CPO v4 Scheduler" in router.tags


# ---------------------------------------------------------------------------
# POST /schedule — sync path
# ---------------------------------------------------------------------------


def _baseline_schedule_dict() -> Dict[str, Any]:
    """Minimal valid CPOScheduleResponse payload that run_cpo_schedule yields."""
    return {
        "tenant_id": str(DEV_TENANT),
        "engine_used": "cpo_v4",
        "status": "ok",
        "solve_time_sec": 1.23,
        "makespan_hours": 100.0,
        "total_tardiness_hours": 0.0,
        "num_late_orders": 0,
        "setups": 5,
        "avg_utilization": 0.85,
        "safety_net_triggered": False,
        "degraded": False,
        "fallback_reason": None,
        "cpo_meta": {"generations": 50},
        "operations": [],
        "warnings": [],
        "infeasible_op_ids": [],
        "commit_sha256": "b" * 64,
        "parent_sha256": None,
    }


def test_post_schedule_happy_path(monkeypatch):
    async def _fake_run(_session, _tenant, _request):
        return _baseline_schedule_dict()

    monkeypatch.setattr("src.plan.cpo.scheduler_run.run_cpo_schedule", _fake_run)

    client = TestClient(_build_app())
    resp = client.post(
        "/v1/plan/cpo/schedule",
        headers={"X-Tenant-Id": str(DEV_TENANT)},
        json={"horizon_days": 7, "time_limit_sec": 10.0},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Pin the response shape (keys + selected types).
    for key in [
        "tenant_id", "engine_used", "status", "solve_time_sec",
        "makespan_hours", "total_tardiness_hours", "num_late_orders",
        "setups", "avg_utilization", "safety_net_triggered", "degraded",
        "fallback_reason", "cpo_meta", "operations", "warnings",
        "infeasible_op_ids", "commit_sha256", "parent_sha256",
    ]:
        assert key in body, f"missing key {key!r} in /schedule response"
    assert body["engine_used"] == "cpo_v4"
    assert isinstance(body["operations"], list)
    assert isinstance(body["warnings"], list)


def test_post_schedule_rejects_horizon_out_of_range():
    """Pydantic validation: horizon_days has ge=1, le=180."""
    client = TestClient(_build_app())
    resp = client.post(
        "/v1/plan/cpo/schedule",
        headers={"X-Tenant-Id": str(DEV_TENANT)},
        json={"horizon_days": 999},
    )
    assert resp.status_code == 422


def test_post_schedule_rejects_negative_generations():
    """Pydantic validation: generations has ge=1."""
    client = TestClient(_build_app())
    resp = client.post(
        "/v1/plan/cpo/schedule",
        headers={"X-Tenant-Id": str(DEV_TENANT)},
        json={"generations": 0},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /schedule/async — Arq enqueue
# ---------------------------------------------------------------------------


def test_post_schedule_async_returns_202(monkeypatch):
    fake_job = MagicMock(job_id="job-test-123")
    fake_pool = AsyncMock()
    fake_pool.enqueue_job = AsyncMock(return_value=fake_job)
    fake_pool.close = AsyncMock(return_value=None)

    async def _fake_create_pool(*_a, **_kw):
        return fake_pool

    monkeypatch.setattr("arq.connections.create_pool", _fake_create_pool)

    client = TestClient(_build_app())
    resp = client.post(
        "/v1/plan/cpo/schedule/async",
        headers={"X-Tenant-Id": str(DEV_TENANT)},
        json={"horizon_days": 7},
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["job_id"] == "job-test-123"
    assert body["status_url"].endswith("/job/job-test-123")
    assert "enqueued_at" in body


def test_post_schedule_async_returns_409_when_dedup(monkeypatch):
    """Arq returns None when an identical job_id is already enqueued."""
    fake_pool = AsyncMock()
    fake_pool.enqueue_job = AsyncMock(return_value=None)
    fake_pool.close = AsyncMock(return_value=None)

    async def _fake_create_pool(*_a, **_kw):
        return fake_pool

    monkeypatch.setattr("arq.connections.create_pool", _fake_create_pool)

    client = TestClient(_build_app())
    resp = client.post(
        "/v1/plan/cpo/schedule/async",
        headers={"X-Tenant-Id": str(DEV_TENANT)},
        json={"horizon_days": 7},
    )
    assert resp.status_code == 409
    assert "already enqueued" in resp.json()["detail"].lower()


def test_post_schedule_async_returns_503_when_redis_down(monkeypatch):
    async def _fake_create_pool(*_a, **_kw):
        raise RuntimeError("Redis offline")

    monkeypatch.setattr("arq.connections.create_pool", _fake_create_pool)

    client = TestClient(_build_app())
    resp = client.post(
        "/v1/plan/cpo/schedule/async",
        headers={"X-Tenant-Id": str(DEV_TENANT)},
        json={"horizon_days": 7},
    )
    assert resp.status_code == 503
    assert "redis" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# GET /schedule/job/{job_id} — Arq polling
# ---------------------------------------------------------------------------


def test_get_job_status_not_found(monkeypatch):
    from arq.jobs import JobStatus

    fake_pool = AsyncMock()
    fake_pool.close = AsyncMock(return_value=None)

    async def _fake_create_pool(*_a, **_kw):
        return fake_pool

    fake_job = MagicMock()
    fake_job.status = AsyncMock(return_value=JobStatus.not_found)
    fake_job.info = AsyncMock(return_value=None)

    monkeypatch.setattr("arq.connections.create_pool", _fake_create_pool)
    monkeypatch.setattr("arq.jobs.Job", lambda *_a, **_kw: fake_job)

    client = TestClient(_build_app())
    resp = client.get(
        "/v1/plan/cpo/schedule/job/missing-id",
        headers={"X-Tenant-Id": str(DEV_TENANT)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["job_id"] == "missing-id"
    assert body["state"] == "not_found"
    assert body["result"] is None


# ---------------------------------------------------------------------------
# GET /commits
# ---------------------------------------------------------------------------


def test_list_commits_empty(monkeypatch):
    async def _fake_list(self, limit=50, *, healthy_only=False):
        return []

    monkeypatch.setattr(
        "src.plan.cpo.commits.CommitsService.list_commits",
        _fake_list,
    )

    client = TestClient(_build_app())
    resp = client.get(
        "/v1/plan/cpo/commits",
        headers={"X-Tenant-Id": str(DEV_TENANT)},
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_commits_returns_array_of_commit_shapes(monkeypatch):
    commit = _make_commit()

    async def _fake_list(self, limit=50, *, healthy_only=False):
        return [commit]

    monkeypatch.setattr(
        "src.plan.cpo.commits.CommitsService.list_commits",
        _fake_list,
    )

    client = TestClient(_build_app())
    resp = client.get(
        "/v1/plan/cpo/commits?limit=10",
        headers={"X-Tenant-Id": str(DEV_TENANT)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list) and len(body) == 1
    row = body[0]
    for key in [
        "id", "tenant_id", "commit_sha256", "short_sha",
        "author", "message", "kpis", "alternatives", "trust_index",
        "operations_count",
    ]:
        assert key in row, f"missing key {key!r} in commit row"
    assert row["short_sha"] == "a" * 12


def test_list_commits_limit_validation():
    """limit query param has ge=1, le=500."""
    client = TestClient(_build_app())
    resp = client.get(
        "/v1/plan/cpo/commits?limit=9999",
        headers={"X-Tenant-Id": str(DEV_TENANT)},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /commits/{sha}
# ---------------------------------------------------------------------------


def test_get_commit_by_sha_happy_path(monkeypatch):
    commit = _make_commit(sha="c" * 64)

    async def _fake_by_sha(self, sha):
        if sha == "c" * 64:
            return commit
        return None

    async def _fake_by_prefix(self, prefix):
        return None

    monkeypatch.setattr(
        "src.plan.cpo.commits.CommitsService.get_by_sha", _fake_by_sha
    )
    monkeypatch.setattr(
        "src.plan.cpo.commits.CommitsService.get_by_sha_prefix",
        _fake_by_prefix,
    )

    client = TestClient(_build_app())
    resp = client.get(
        f"/v1/plan/cpo/commits/{'c' * 64}",
        headers={"X-Tenant-Id": str(DEV_TENANT)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["commit_sha256"] == "c" * 64
    # By default include_operations=False
    assert body.get("operations") is None


def test_get_commit_returns_404_on_unknown_sha(monkeypatch):
    async def _none(self, *_a, **_kw):
        return None

    monkeypatch.setattr(
        "src.plan.cpo.commits.CommitsService.get_by_sha", _none
    )
    monkeypatch.setattr(
        "src.plan.cpo.commits.CommitsService.get_by_sha_prefix", _none
    )

    client = TestClient(_build_app())
    resp = client.get(
        "/v1/plan/cpo/commits/deadbeefdeadbeef",
        headers={"X-Tenant-Id": str(DEV_TENANT)},
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# GET /commits/{from_sha}/diff/{to_sha}
# ---------------------------------------------------------------------------


def test_diff_commits_happy_path(monkeypatch):
    diff_payload = {
        "from_sha": "a" * 64,
        "to_sha": "b" * 64,
        "added": [{"operation_id": "op1"}],
        "removed": [],
        "changed": [],
        "kpi_deltas": {"makespan_hours": -2.0},
        "summary": {"added": 1, "removed": 0, "changed": 0},
    }

    async def _fake_diff(self, from_sha, to_sha):
        return diff_payload

    monkeypatch.setattr(
        "src.plan.cpo.commits.CommitsService.diff", _fake_diff
    )

    client = TestClient(_build_app())
    resp = client.get(
        f"/v1/plan/cpo/commits/{'a' * 64}/diff/{'b' * 64}",
        headers={"X-Tenant-Id": str(DEV_TENANT)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["from_sha"] == "a" * 64
    assert body["to_sha"] == "b" * 64
    assert body["summary"]["added"] == 1
    for key in ["added", "removed", "changed", "kpi_deltas", "summary"]:
        assert key in body


def test_diff_returns_404_when_commit_unknown(monkeypatch):
    async def _raise(self, from_sha, to_sha):
        raise ValueError("commit_not_found: from=x a=False to=y b=False")

    monkeypatch.setattr(
        "src.plan.cpo.commits.CommitsService.diff", _raise
    )

    client = TestClient(_build_app())
    resp = client.get(
        f"/v1/plan/cpo/commits/{'x' * 64}/diff/{'y' * 64}",
        headers={"X-Tenant-Id": str(DEV_TENANT)},
    )
    assert resp.status_code == 404
    assert "commit_not_found" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# GET /timeline
# ---------------------------------------------------------------------------


def test_timeline_empty_when_no_commits(monkeypatch):
    async def _none(self):
        return None

    monkeypatch.setattr(
        "src.plan.cpo.commits.CommitsService.get_latest", _none
    )

    client = TestClient(_build_app())
    resp = client.get(
        "/v1/plan/cpo/timeline",
        headers={"X-Tenant-Id": str(DEV_TENANT)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["commit_sha256"] is None
    assert body["candidates"] == []


def test_timeline_returns_candidates_from_latest(monkeypatch):
    commit = _make_commit(
        alternatives=[
            {
                "rank": 0,
                "fitness": 0.95,
                "generation": 10,
                "behavioral": {"avg_utilization": 0.8},
                "chromosome": {"permutation": [0, 1, 2]},
            },
            {
                "rank": 1,
                "fitness": 0.90,
                "generation": 12,
                "behavioral": {"avg_utilization": 0.78},
                "chromosome": {"permutation": [1, 0, 2]},
            },
        ],
    )

    async def _fake_latest(self):
        return commit

    monkeypatch.setattr(
        "src.plan.cpo.commits.CommitsService.get_latest", _fake_latest
    )

    client = TestClient(_build_app())
    resp = client.get(
        "/v1/plan/cpo/timeline",
        headers={"X-Tenant-Id": str(DEV_TENANT)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["commit_sha256"] == commit.commit_sha256
    assert len(body["candidates"]) == 2
    c0 = body["candidates"][0]
    for key in ["rank", "fitness", "generation", "behavioral", "chromosome"]:
        assert key in c0


# ---------------------------------------------------------------------------
# GET /commits/{sha}/alternatives
# ---------------------------------------------------------------------------


def test_alternatives_happy_path(monkeypatch):
    commit = _make_commit(
        sha="d" * 64,
        kpis={
            "avg_utilization": 0.80,
            "total_tardiness_hours": 10.0,
            "num_late_orders": 2,
        },
        alternatives=[
            {
                "rank": 0,
                "fitness": 0.99,
                "generation": 5,
                "behavioral": {
                    "avg_utilization": 0.85,
                    "total_tardiness_hours": 5.0,
                    "num_late_orders": 1,
                },
            },
        ],
    )

    async def _fake_by_sha(self, sha):
        return commit if sha == "d" * 64 else None

    async def _none(self, *_a, **_kw):
        return None

    monkeypatch.setattr(
        "src.plan.cpo.commits.CommitsService.get_by_sha", _fake_by_sha
    )
    monkeypatch.setattr(
        "src.plan.cpo.commits.CommitsService.get_by_sha_prefix", _none
    )

    client = TestClient(_build_app())
    resp = client.get(
        f"/v1/plan/cpo/commits/{'d' * 64}/alternatives",
        headers={"X-Tenant-Id": str(DEV_TENANT)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["commit_sha256"] == "d" * 64
    assert "primary_kpis" in body
    assert len(body["alternatives"]) == 1
    alt = body["alternatives"][0]
    for key in [
        "rank", "fitness", "generation", "descriptor",
        "vs_primary", "trade_off_narrative",
    ]:
        assert key in alt
    # `vs_primary` has the same axes as `behavioral`, with percentage strings
    # or None.
    assert "avg_utilization" in alt["vs_primary"]
    # Narrative is non-empty PT-PT prose.
    assert isinstance(alt["trade_off_narrative"], str)
    assert len(alt["trade_off_narrative"]) > 0


def test_alternatives_n_validation():
    client = TestClient(_build_app())
    resp = client.get(
        f"/v1/plan/cpo/commits/{'e' * 64}/alternatives?n=999",
        headers={"X-Tenant-Id": str(DEV_TENANT)},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /commits/{sha}/decide
# ---------------------------------------------------------------------------


def test_decide_requires_category_when_rejections_present(monkeypatch):
    """Pin Q.5: rejection_category mandatory when rejected_alt_idxs non-empty."""
    commit = _make_commit(sha="f" * 64)

    async def _fake_by_sha(self, sha):
        return commit if sha == "f" * 64 else None

    async def _none(self, *_a, **_kw):
        return None

    monkeypatch.setattr(
        "src.plan.cpo.commits.CommitsService.get_by_sha", _fake_by_sha
    )
    monkeypatch.setattr(
        "src.plan.cpo.commits.CommitsService.get_by_sha_prefix", _none
    )

    client = TestClient(_build_app())
    resp = client.post(
        f"/v1/plan/cpo/commits/{'f' * 64}/decide",
        headers={"X-Tenant-Id": str(DEV_TENANT)},
        json={"chosen_alt_idx": 0, "rejected_alt_idxs": [1, 2]},
    )
    assert resp.status_code == 400
    assert "rejection_category" in resp.json()["detail"]


def test_decide_rejects_unknown_category():
    client = TestClient(_build_app())
    resp = client.post(
        f"/v1/plan/cpo/commits/{'f' * 64}/decide",
        headers={"X-Tenant-Id": str(DEV_TENANT)},
        json={
            "chosen_alt_idx": 0,
            "rejected_alt_idxs": [1],
            "rejection_category": "BANANA",
            "reason": "long enough reason here",
        },
    )
    assert resp.status_code == 400
    assert "unknown rejection_category" in resp.json()["detail"].lower()


def test_decide_requires_reason_when_rejections_present():
    """Pin Q.R.2: reason ≥ 10 chars when rejected_alt_idxs non-empty."""
    client = TestClient(_build_app())
    resp = client.post(
        f"/v1/plan/cpo/commits/{'f' * 64}/decide",
        headers={"X-Tenant-Id": str(DEV_TENANT)},
        json={
            "chosen_alt_idx": 0,
            "rejected_alt_idxs": [1],
            "rejection_category": "COST",
            "reason": "short",
        },
    )
    assert resp.status_code == 400
    assert "reason" in resp.json()["detail"].lower()


def test_decide_happy_path(monkeypatch):
    commit = _make_commit(sha="f" * 64)
    updated = _make_commit(
        sha="f" * 64,
        rejected_alternatives=[
            {"alt_idx": 1, "kpis": {"makespan_hours": 110.0}},
        ],
        user_preference_signal={
            "decided_by": "alice",
            "decided_at": "2026-05-21T10:00:00Z",
        },
    )

    async def _fake_by_sha(self, sha):
        return commit if sha == "f" * 64 else None

    async def _none(self, *_a, **_kw):
        return None

    async def _fake_record(self, *, commit_id, chosen_alt_idx, rejected_alt_idxs,
                           decided_by, reason=None, decided_at=None):
        return updated

    monkeypatch.setattr(
        "src.plan.cpo.commits.CommitsService.get_by_sha", _fake_by_sha
    )
    monkeypatch.setattr(
        "src.plan.cpo.commits.CommitsService.get_by_sha_prefix", _none
    )
    monkeypatch.setattr(
        "src.plan.cpo.commits.CommitsService.record_decision", _fake_record
    )

    client = TestClient(_build_app())
    resp = client.post(
        f"/v1/plan/cpo/commits/{'f' * 64}/decide",
        headers={"X-Tenant-Id": str(DEV_TENANT)},
        json={
            "chosen_alt_idx": 0,
            "rejected_alt_idxs": [1],
            "rejection_category": "COST",
            "reason": "primary tem menos setups",
            "decided_by": "alice",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["commit_sha256"] == "f" * 64
    assert isinstance(body["rejected_alternatives"], list)
    assert isinstance(body["user_preference_signal"], dict)


def test_decide_accepts_no_rejections_without_category(monkeypatch):
    """When rejected_alt_idxs is empty, no category or reason needed."""
    commit = _make_commit(sha="f" * 64)
    updated = _make_commit(sha="f" * 64)

    async def _fake_by_sha(self, sha):
        return commit if sha == "f" * 64 else None

    async def _none(self, *_a, **_kw):
        return None

    async def _fake_record(self, **_kwargs):
        return updated

    monkeypatch.setattr(
        "src.plan.cpo.commits.CommitsService.get_by_sha", _fake_by_sha
    )
    monkeypatch.setattr(
        "src.plan.cpo.commits.CommitsService.get_by_sha_prefix", _none
    )
    monkeypatch.setattr(
        "src.plan.cpo.commits.CommitsService.record_decision", _fake_record
    )

    client = TestClient(_build_app())
    resp = client.post(
        f"/v1/plan/cpo/commits/{'f' * 64}/decide",
        headers={"X-Tenant-Id": str(DEV_TENANT)},
        json={"chosen_alt_idx": 0, "rejected_alt_idxs": []},
    )
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# GET /operations/{operation_id}/worker-pairs
# ---------------------------------------------------------------------------


def test_worker_pairs_returns_404_when_no_commit(monkeypatch):
    async def _none(self):
        return None

    async def _fake_load(_db, _tid):
        return MagicMock(name="factory_state")

    monkeypatch.setattr(
        "src.plan.cpo.state.FactoryState.load", _fake_load
    )
    monkeypatch.setattr(
        "src.plan.cpo.commits.CommitsService.get_latest", _none
    )

    client = TestClient(_build_app())
    resp = client.get(
        "/v1/plan/cpo/operations/some-op/worker-pairs",
        headers={"X-Tenant-Id": str(DEV_TENANT)},
    )
    assert resp.status_code == 404
    assert "no schedule commit" in resp.json()["detail"].lower()


def test_worker_pairs_returns_404_when_op_not_in_commit(monkeypatch):
    commit = _make_commit(
        operations=[{"operation_id": "op-other", "phase_id": "LAMINAGEM"}],
    )

    async def _fake_latest(self):
        return commit

    async def _fake_load(_db, _tid):
        return MagicMock(name="factory_state")

    monkeypatch.setattr(
        "src.plan.cpo.state.FactoryState.load", _fake_load
    )
    monkeypatch.setattr(
        "src.plan.cpo.commits.CommitsService.get_latest", _fake_latest
    )

    client = TestClient(_build_app())
    resp = client.get(
        "/v1/plan/cpo/operations/op-missing/worker-pairs",
        headers={"X-Tenant-Id": str(DEV_TENANT)},
    )
    assert resp.status_code == 404
    assert "not found in latest commit" in resp.json()["detail"].lower()


def test_worker_pairs_returns_empty_when_phase_not_paired(monkeypatch):
    """needs_pair=False, pairs=[] when the op's phase is not pair-required."""
    commit = _make_commit(
        operations=[{
            "operation_id": "op-1",
            "order_id": "OF-1",
            "product_id": "K1",
            "sequence": 1,
            "operation_code": "CURA",
            "duration_minutes": 60.0,
            "phase_id": "CURA",
        }],
    )

    async def _fake_latest(self):
        return commit

    async def _fake_load(_db, _tid):
        return MagicMock(name="factory_state")

    monkeypatch.setattr(
        "src.plan.cpo.state.FactoryState.load", _fake_load
    )
    monkeypatch.setattr(
        "src.plan.cpo.commits.CommitsService.get_latest", _fake_latest
    )
    monkeypatch.setattr(
        "src.plan.cpo.pair_assignment.needs_pair_assignment",
        lambda _op, _state: False,
    )

    client = TestClient(_build_app())
    resp = client.get(
        "/v1/plan/cpo/operations/op-1/worker-pairs",
        headers={"X-Tenant-Id": str(DEV_TENANT)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["operation_id"] == "op-1"
    assert body["phase_id"] == "CURA"
    assert body["needs_pair"] is False
    assert body["pairs"] == []


def test_worker_pairs_returns_ranked_pairs(monkeypatch):
    commit = _make_commit(
        operations=[{
            "operation_id": "op-1",
            "order_id": "OF-1",
            "product_id": "K1",
            "sequence": 1,
            "operation_code": "LAMINAGEM",
            "duration_minutes": 240.0,
            "phase_id": "LAMINAGEM",
        }],
    )

    async def _fake_latest(self):
        return commit

    async def _fake_load(_db, _tid):
        return MagicMock(name="factory_state")

    monkeypatch.setattr(
        "src.plan.cpo.state.FactoryState.load", _fake_load
    )
    monkeypatch.setattr(
        "src.plan.cpo.commits.CommitsService.get_latest", _fake_latest
    )
    monkeypatch.setattr(
        "src.plan.cpo.pair_assignment.needs_pair_assignment",
        lambda _op, _state: True,
    )
    monkeypatch.setattr(
        "src.plan.cpo.pair_assignment.rank_pairs",
        lambda _op, _state, top_n=3: [
            {"chefe_id": "E001", "partner_id": "E002", "score": 8.2},
            {"chefe_id": "E003", "partner_id": "E004", "score": 6.1},
        ],
    )

    client = TestClient(_build_app())
    resp = client.get(
        "/v1/plan/cpo/operations/op-1/worker-pairs?top_n=2",
        headers={"X-Tenant-Id": str(DEV_TENANT)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["needs_pair"] is True
    assert len(body["pairs"]) == 2
    first = body["pairs"][0]
    for key in ["chefe_id", "partner_id", "score"]:
        assert key in first
    assert first["score"] == 8.2
