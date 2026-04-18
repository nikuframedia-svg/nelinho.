"""
Tests for src.ml.jobs.base.RetrainJob.

Strategy: concrete `DummyRetrainJob` that returns scripted features/model/
metrics; fake governance service that records proposals.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from uuid import UUID, uuid4

import pytest

from src.ml.config import MLConfig
from src.ml.jobs.base import RetrainJob
from src.ml.models.registry import ModelRegistry
from src.ml.models.storage import ArtifactStorage


TENANT = UUID("11111111-1111-1111-1111-111111111111")


class DummyRetrainJob(RetrainJob):
    model_name = "dummy_test"
    schedule_cron = "0 3 * * *"

    def __init__(self, metrics: Dict[str, Any], should_raise: bool = False):
        self._metrics = metrics
        self._should_raise = should_raise
        self.calls = {"extract": 0, "train": 0, "validate": 0}

    def extract_features(self, tenant_id):
        self.calls["extract"] += 1
        return [1, 2, 3]

    def train(self, features) -> Tuple[Any, int]:
        self.calls["train"] += 1
        if self._should_raise:
            raise RuntimeError("simulated training failure")
        return ({"trained": True}, len(features))

    def validate(self, model, features) -> Dict[str, Any]:
        self.calls["validate"] += 1
        return dict(self._metrics)


class FakeGovernance:
    def __init__(self, auto_approve: bool = True):
        self.auto_approve = auto_approve
        self.proposals = []

    async def propose_decision(self, **kwargs):
        self.proposals.append(kwargs)
        return {
            "id": str(uuid4()),
            "status": "approved" if self.auto_approve else "pending_approval",
            **kwargs,
        }


@pytest.fixture
def ml_storage(tmp_path: Path, monkeypatch) -> ArtifactStorage:
    monkeypatch.setenv("PRODPLAN_ML_ARTIFACT_DIR", str(tmp_path))
    return ArtifactStorage(MLConfig(artifact_dir=tmp_path, auto_promote_max_wmape_delta=0.05))


class TestRetrainJobLifecycle:
    async def test_successful_run_persists_artifact(
        self, fake_session, ml_storage, monkeypatch,
    ):
        # Patch ModelRegistry to inject our tmp storage
        from src.ml.jobs import base as base_module
        orig_registry = base_module.ModelRegistry

        def _patched_registry(session, tenant_id):
            return orig_registry(session, tenant_id, storage=ml_storage)

        monkeypatch.setattr(base_module, "ModelRegistry", _patched_registry)

        job = DummyRetrainJob(metrics={"wmape": 0.07, "auc": 0.88})
        fake_session.queue_scalar(None)  # get_active → no baseline
        fake_session.queue_scalar(None)  # _next_version → first version

        governance = FakeGovernance(auto_approve=True)
        summary = await job.run(fake_session, TENANT, governance_service=governance, proposed_by="tester")

        assert summary["status"] == "success"
        assert summary["model_name"] == "dummy_test"
        assert summary["version"] == 1
        assert summary["metrics"] == {"wmape": 0.07, "auc": 0.88}
        assert summary["training_samples"] == 3
        assert job.calls == {"extract": 1, "train": 1, "validate": 1}
        # Proposal was sent
        assert len(governance.proposals) == 1
        assert governance.proposals[0]["decision_type"] == "model_promotion"

    async def test_training_failure_returns_failed_status(
        self, fake_session, ml_storage, monkeypatch,
    ):
        from src.ml.jobs import base as base_module
        orig_registry = base_module.ModelRegistry

        def _patched_registry(session, tenant_id):
            return orig_registry(session, tenant_id, storage=ml_storage)

        monkeypatch.setattr(base_module, "ModelRegistry", _patched_registry)

        job = DummyRetrainJob(metrics={}, should_raise=True)
        fake_session.queue_scalar(None)

        summary = await job.run(fake_session, TENANT, governance_service=None)

        assert summary["status"] == "failed"
        assert "simulated training failure" in summary["error"]
        # No artifact persisted
        from src.ml.models.orm import MLModelArtifact
        artifacts = [o for o in fake_session.added if isinstance(o, MLModelArtifact)]
        assert artifacts == []

    async def test_should_promote_default_policy(self):
        job = DummyRetrainJob(metrics={"wmape": 0.05})

        # No baseline: always promote
        assert job.should_promote({"wmape": 0.10}, None) is True
        # Baseline worse: promote
        assert job.should_promote({"wmape": 0.05}, {"wmape": 0.10}) is True
        # Baseline better: do NOT promote
        assert job.should_promote({"wmape": 0.10}, {"wmape": 0.05}) is False
        # Missing values: conservative no-promote
        assert job.should_promote({}, {"wmape": 0.10}) is False

    async def test_no_governance_service_skips_proposal(
        self, fake_session, ml_storage, monkeypatch,
    ):
        from src.ml.jobs import base as base_module
        orig_registry = base_module.ModelRegistry

        def _patched_registry(session, tenant_id):
            return orig_registry(session, tenant_id, storage=ml_storage)

        monkeypatch.setattr(base_module, "ModelRegistry", _patched_registry)

        job = DummyRetrainJob(metrics={"wmape": 0.07})
        fake_session.queue_scalar(None)
        fake_session.queue_scalar(None)

        summary = await job.run(fake_session, TENANT, governance_service=None)

        assert summary["status"] == "success"
        assert summary["decision_id"] is None
        assert summary["auto_promoted"] is False
