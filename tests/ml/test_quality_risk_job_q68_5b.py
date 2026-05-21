"""Q.68.5.B — tests for the quality-risk batch scoring job.

Verifies the job wrapper around ``DefectRiskService``:

* No-active-model path returns ``scored=0``, ``model_version=None``,
  ``model_available=False`` and never raises.
* Active-model path surfaces the service payload (scored count,
  high_risk count, model_version, model_available=True).
* Edge case: tenant with zero in-progress orders → ``scored=0`` but
  ``model_available=True``.
* Service raising mid-flight is swallowed: returns degraded dict,
  scheduler tick survives.
* Idempotency: running the job twice in a row yields equivalent metrics
  shape (deterministic given the same fake state).
* `_quality_risk_scoring_job` (scheduler entry) logs the metrics dict
  and never re-raises, even when the inner helper blows up.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

import pytest


TENANT = UUID("11111111-1111-1111-1111-111111111111")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeSession:
    """Minimal async session — only commit/rollback are exercised."""

    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def _patch_session(monkeypatch, session: _FakeSession) -> None:
    """Replace ``get_session_context`` with one yielding ``session``.

    Two patch points: the job's local import + the shared module so
    inner callers (DefectRiskService factory) see the same fake.
    """

    @asynccontextmanager
    async def _ctx():
        yield session

    import src.ml.jobs.quality_risk as job_mod
    import src.shared.database as db

    monkeypatch.setattr(job_mod, "get_session_context", _ctx, raising=True)
    monkeypatch.setattr(db, "get_session_context", _ctx, raising=True)


def _patch_registry(monkeypatch, *, active_version: int | None) -> None:
    """Stub ``ModelRegistry.get_active`` so the probe step is deterministic."""

    class _FakeActive:
        def __init__(self, v: int) -> None:
            self.version = v

    async def _get_active(self, model_name: str):
        del model_name  # only "quality_risk" is exercised
        if active_version is None:
            return None
        return _FakeActive(active_version)

    import src.ml.jobs.quality_risk as job_mod

    monkeypatch.setattr(
        job_mod.ModelRegistry, "get_active", _get_active, raising=True,
    )


def _patch_defect_service(monkeypatch, payload: dict[str, Any] | Exception) -> None:
    """Replace ``DefectRiskService.defect_risk`` with a stub returning
    ``payload`` (or raising it when ``payload`` is an Exception).
    """

    async def _defect_risk(self, *, top_n: int = 50):
        del top_n  # the job always asks for the full set
        if isinstance(payload, Exception):
            raise payload
        return payload

    import src.ml.jobs.quality_risk as job_mod

    monkeypatch.setattr(
        job_mod.DefectRiskService, "defect_risk", _defect_risk, raising=True,
    )


# ---------------------------------------------------------------------------
# score_quality_risk_for_tenant
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_score_returns_empty_when_no_active_model(monkeypatch):
    from src.ml.jobs.quality_risk import score_quality_risk_for_tenant

    session = _FakeSession()
    _patch_session(monkeypatch, session)
    _patch_registry(monkeypatch, active_version=None)
    _patch_defect_service(
        monkeypatch,
        {
            "model_available": False,
            "reason": "Sem modelo de risco activo.",
            "orders": [],
        },
    )

    result = await score_quality_risk_for_tenant(TENANT)

    assert result["scored"] == 0
    assert result["high_risk"] == 0
    assert result["model_version"] is None
    assert result["model_available"] is False
    assert isinstance(result["elapsed_ms"], int)
    assert result["elapsed_ms"] >= 0
    assert session.commits == 1


@pytest.mark.asyncio
async def test_score_returns_metrics_with_active_model(monkeypatch):
    from src.ml.jobs.quality_risk import score_quality_risk_for_tenant

    session = _FakeSession()
    _patch_session(monkeypatch, session)
    _patch_registry(monkeypatch, active_version=7)
    _patch_defect_service(
        monkeypatch,
        {
            "model_available": True,
            "total_orders": 12,
            "high_risk_count": 3,
            "orders": [
                {"of_id": "1", "defect_probability": 0.55, "risk_band": "alto"},
                {"of_id": "2", "defect_probability": 0.30, "risk_band": "medio"},
            ],
        },
    )

    result = await score_quality_risk_for_tenant(TENANT)

    assert result["scored"] == 12
    assert result["high_risk"] == 3
    assert result["model_version"] == 7
    assert result["model_available"] is True
    assert result["elapsed_ms"] >= 0
    assert session.commits == 1


@pytest.mark.asyncio
async def test_score_handles_zero_orders_active_model(monkeypatch):
    """Edge case: model is active but no in-progress orders to score."""
    from src.ml.jobs.quality_risk import score_quality_risk_for_tenant

    session = _FakeSession()
    _patch_session(monkeypatch, session)
    _patch_registry(monkeypatch, active_version=4)
    _patch_defect_service(
        monkeypatch,
        {"model_available": True, "orders": []},
    )

    result = await score_quality_risk_for_tenant(TENANT)

    # Service omitted total_orders → falls back to len(orders) == 0.
    assert result["scored"] == 0
    assert result["high_risk"] == 0
    assert result["model_version"] == 4
    assert result["model_available"] is True


@pytest.mark.asyncio
async def test_score_swallows_service_failure(monkeypatch, caplog):
    """A DefectRiskService crash must not leak into the scheduler."""
    from src.ml.jobs.quality_risk import score_quality_risk_for_tenant

    session = _FakeSession()
    _patch_session(monkeypatch, session)
    _patch_registry(monkeypatch, active_version=2)
    _patch_defect_service(monkeypatch, RuntimeError("predictor exploded"))

    with caplog.at_level(logging.WARNING, logger="src.ml.jobs.quality_risk"):
        result = await score_quality_risk_for_tenant(TENANT)

    assert result["scored"] == 0
    assert result["model_available"] is False
    # The model_version probe still ran successfully before the crash.
    assert result["model_version"] == 2
    assert any(
        "quality_risk_scoring tenant=" in rec.message
        and "failed" in rec.message
        for rec in caplog.records
    )


@pytest.mark.asyncio
async def test_score_is_idempotent(monkeypatch):
    """Two consecutive calls with the same stub state produce equivalent shape.

    Idempotency here means: no shared mutable state between invocations,
    no double-commit on a single session reference, deterministic metric
    keys. We assert the structural invariants — elapsed_ms is allowed to
    differ.
    """
    from src.ml.jobs.quality_risk import score_quality_risk_for_tenant

    session = _FakeSession()
    _patch_session(monkeypatch, session)
    _patch_registry(monkeypatch, active_version=5)
    _patch_defect_service(
        monkeypatch,
        {
            "model_available": True,
            "total_orders": 4,
            "high_risk_count": 1,
            "orders": [],
        },
    )

    first = await score_quality_risk_for_tenant(TENANT)
    second = await score_quality_risk_for_tenant(TENANT)

    keys = {"scored", "high_risk", "model_version", "model_available"}
    assert {k: first[k] for k in keys} == {k: second[k] for k in keys}
    # Each invocation commits exactly once on its own session lifecycle.
    assert session.commits == 2


# ---------------------------------------------------------------------------
# Scheduler-side wrapper
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scheduler_job_logs_metrics(monkeypatch, caplog):
    """`_quality_risk_scoring_job` logs the result dict and never raises."""
    from src.scheduling.jobs import ml as ml_mod

    async def _fake_score(tenant_id: UUID):
        return {
            "scored": 9,
            "high_risk": 2,
            "model_version": 3,
            "model_available": True,
            "elapsed_ms": 7,
        }

    # Patch the import-site name. The job uses a local import so we
    # patch the module attribute on the source module instead.
    import src.ml.jobs.quality_risk as quality_risk_mod

    monkeypatch.setattr(
        quality_risk_mod,
        "score_quality_risk_for_tenant",
        _fake_score,
        raising=True,
    )

    with caplog.at_level(logging.INFO, logger="src.scheduling.jobs.ml"):
        await ml_mod._quality_risk_scoring_job(TENANT)

    msgs = [rec.message for rec in caplog.records]
    assert any(
        "quality_risk_scoring tenant=" in m
        and "scored=9" in m
        and "high_risk=2" in m
        and "model_version=3" in m
        for m in msgs
    )


@pytest.mark.asyncio
async def test_scheduler_job_swallows_helper_crash(monkeypatch, caplog):
    """If the helper raises, the scheduler tick must still complete."""
    from src.scheduling.jobs import ml as ml_mod

    async def _boom(tenant_id: UUID):
        raise RuntimeError("helper exploded")

    import src.ml.jobs.quality_risk as quality_risk_mod

    monkeypatch.setattr(
        quality_risk_mod,
        "score_quality_risk_for_tenant",
        _boom,
        raising=True,
    )

    with caplog.at_level(logging.WARNING, logger="src.scheduling.jobs.ml"):
        await ml_mod._quality_risk_scoring_job(TENANT)  # must not raise

    assert any(
        "quality_risk_scoring tenant=" in rec.message
        and "failed" in rec.message
        for rec in caplog.records
    )
