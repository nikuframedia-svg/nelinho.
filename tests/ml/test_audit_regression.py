"""FASE 5 — regression tests for ML-side fixes from auditoria PLANO (Decide).

Covers:
- CRIT-03: LLMAdapterPromoter.register signature
- CRIT-04: RetrainJob.run raises EmptyDatasetError on empty features
- CRIT-05: build_training_dataset returns [] (not silent crash)
- CRIT-18: ArtifactStorage path traversal (already in test_storage.py;
           extra coverage here for regression isolation)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple
from uuid import uuid4

import pytest

# ---------------------------------------------------------------------------
# CRIT-04 — RetrainJob.run raises EmptyDatasetError on empty features
# ---------------------------------------------------------------------------


class _StubRetrainJob:
    """Minimal RetrainJob that lets us push features through the lifecycle
    without spinning sklearn / governance."""

    model_name = "stub"
    schedule_cron = ""

    def __init__(self, features: List[Dict[str, Any]]):
        self._features = features

    def extract_features(self, tenant_id):  # noqa: D401 — abstract impl
        return self._features

    def train(self, features) -> Tuple[Any, int]:
        return ({"trained": True}, len(features))

    def validate(self, model, features) -> Dict[str, Any]:
        return {"wmape": 0.1}


class TestRetrainJobEmptyDataset:
    @pytest.mark.asyncio
    async def test_empty_features_marks_run_as_failed(self, fake_session):
        from src.ml.jobs.base import RetrainJob

        # Subclass at runtime to inherit the abstract lifecycle from
        # RetrainJob while keeping our stub features.
        Job = type(  # noqa: N806 — class factory pattern
            "Job",
            (_StubRetrainJob, RetrainJob),
            {"model_name": "stub_empty"},
        )
        job = Job(features=[])

        # registry.get_active() runs first inside RetrainJob.run() — pre-queue
        # a None scalar so that lookup completes (no baseline) before we hit
        # the EmptyDataset guard.
        fake_session.queue_scalar(None)

        summary = await job.run(session=fake_session, tenant_id=uuid4())

        assert summary["status"] == "failed"
        assert summary["error_type"] == "EmptyDatasetError"
        assert "stub_empty" in summary["error"]


# ---------------------------------------------------------------------------
# CRIT-05 — build_training_dataset returns [] when semantic layer is down
# ---------------------------------------------------------------------------


class TestBuildTrainingDatasetEmptyPath:
    def test_duration_returns_empty_when_sq_none(self, caplog):
        import logging
        from src.ml.models_domain.duration import build_training_dataset

        with caplog.at_level(
            logging.WARNING, logger="src.ml.models_domain.duration",
        ):
            rows = build_training_dataset(semantic_queries=None)

        assert rows == []
        assert any("returning empty" in r.message for r in caplog.records)

    def test_quality_risk_returns_empty_when_sq_none(self, caplog):
        import logging
        from src.ml.models_domain.quality_risk import build_training_dataset

        with caplog.at_level(
            logging.WARNING, logger="src.ml.models_domain.quality_risk",
        ):
            rows = build_training_dataset(semantic_queries=None)

        assert rows == []
        assert any("returning empty" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# CRIT-03 — LLMAdapterPromoter.register uses the real registry signature
# ---------------------------------------------------------------------------


class _FakeArtifact:
    def __init__(self, version=1):
        self.version = version


class _FakeRegistry:
    """Records the call arguments so the test can assert the call shape."""

    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    async def save(self, **kwargs):
        # Reject the legacy bug-compatible kwargs explicitly so a
        # regression that brings them back is caught here.
        for forbidden in ("model_obj", "extra"):
            assert forbidden not in kwargs, (
                f"LLMAdapterPromoter still passes {forbidden!r} — "
                "registry.save signature changed in Sprint G."
            )
        # The real registry.save expects (model_name, model, metrics,
        # trained_by, ...). All four must be present.
        for required in ("model_name", "model", "metrics", "trained_by"):
            assert required in kwargs, (
                f"LLMAdapterPromoter forgot {required!r} kwarg"
            )
        self.calls.append(kwargs)
        return _FakeArtifact(version=1)


class TestLLMPromoterRegisterSignature:
    @pytest.mark.asyncio
    async def test_register_calls_registry_save_with_correct_signature(
        self, monkeypatch,
    ):
        from src.ml.llm.promoter import LLMAdapterPromoter

        fake_registry = _FakeRegistry()
        # ModelRegistry is imported lazily inside register(); patch
        # the symbol at the registry module so the local lookup hits
        # our fake.
        monkeypatch.setattr(
            "src.ml.models.registry.ModelRegistry",
            lambda *args, **kwargs: fake_registry,
        )

        promoter = LLMAdapterPromoter(session=object(), tenant_id=uuid4())
        outcome = await promoter.register(
            model_name="copilot_pt",
            adapter_path=Path("/tmp/adapter"),
            metrics={"loss": 0.42},
        )

        assert outcome.registered is True
        assert outcome.error is None
        assert len(fake_registry.calls) == 1
        call = fake_registry.calls[0]
        # Adapter path is shipped inside the model payload (joblib-safe)
        assert call["model"]["kind"] == "lora_adapter"
        assert call["model"]["adapter_path"] == "/tmp/adapter".replace("\\", "/") or call["model"]["adapter_path"].endswith("adapter")
        # Metrics carry the lora metadata for downstream consumers
        assert call["metrics"]["meta"]["kind"] == "lora_adapter"
        assert call["trained_by"] == "qlora_trainer"


# ---------------------------------------------------------------------------
# CRIT-18 — ArtifactStorage path traversal hardening (cross-check)
# ---------------------------------------------------------------------------


class TestArtifactStorageSandboxRegression:
    def test_load_outside_root_raises(self, tmp_path):
        from src.ml.config import MLConfig
        from src.ml.models.storage import ArtifactStorage, ArtifactStorageError

        cfg = MLConfig(
            artifact_dir=tmp_path,
            auto_promote_max_wmape_delta=0.05,
        )
        storage = ArtifactStorage(cfg)

        # Round-trip OK
        uri = storage.save({"weights": [1, 2, 3]}, "regression_model", 1)
        assert storage.load(uri) == {"weights": [1, 2, 3]}

        # Escape attempts
        with pytest.raises(ArtifactStorageError):
            storage.load("/etc/passwd")
        with pytest.raises(ArtifactStorageError):
            storage.load(f"file://{tmp_path}/../../../escape.joblib")
