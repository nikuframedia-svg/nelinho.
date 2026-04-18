"""
Tests for src.ml.models.registry.ModelRegistry.

Strategy: use the shared FakeSession fixture to queue query results.
ArtifactStorage uses a real tmp_path (joblib round-trip is cheap).
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest

from src.ml.config import MLConfig
from src.ml.models.orm import MLModelArtifact
from src.ml.models.registry import ModelNotFoundError, ModelRegistry
from src.ml.models.storage import ArtifactStorage


TENANT = UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def storage(tmp_path: Path) -> ArtifactStorage:
    return ArtifactStorage(MLConfig(artifact_dir=tmp_path, auto_promote_max_wmape_delta=0.05))


def _artifact(**kw) -> MLModelArtifact:
    """Construct an in-memory MLModelArtifact for tests (not persisted)."""
    a = MLModelArtifact(
        id=kw.pop("id", uuid4()),
        tenant_id=kw.pop("tenant_id", TENANT),
        model_name=kw.pop("model_name", "quality_risk"),
        version=kw.pop("version", 1),
        storage_uri=kw.pop("storage_uri", "file:///tmp/fake"),
        metrics=kw.pop("metrics", {}),
        active=kw.pop("active", False),
        trained_by=kw.pop("trained_by", "test"),
        training_duration_sec=kw.pop("training_duration_sec", None),
        training_samples=kw.pop("training_samples", None),
    )
    for k, v in kw.items():
        setattr(a, k, v)
    return a


class TestSave:
    async def test_save_persists_row_and_returns_artifact(self, fake_session, storage):
        registry = ModelRegistry(fake_session, TENANT, storage=storage)
        fake_session.queue_scalar(None)  # _next_version: no prior versions

        artifact = await registry.save(
            model_name="quality_risk",
            model={"weights": [1, 2, 3]},
            metrics={"wmape": 0.09, "auc": 0.85, "samples": 1000},
            trained_by="unit_test",
            training_duration_sec=12.3,
            training_samples=1000,
        )

        assert artifact.version == 1
        assert artifact.active is False
        assert artifact.metrics["wmape"] == 0.09
        assert artifact.storage_uri.startswith("file://")
        # Persisted in fake session
        assert artifact in fake_session.added
        assert fake_session.flush_calls >= 1

    async def test_save_monotonic_versioning(self, fake_session, storage):
        registry = ModelRegistry(fake_session, TENANT, storage=storage)
        fake_session.queue_scalar(3)  # previous version is 3

        artifact = await registry.save(
            model_name="duration",
            model={"w": 1},
            metrics={},
        )
        assert artifact.version == 4


class TestPromote:
    async def test_promote_not_found_raises(self, fake_session, storage):
        registry = ModelRegistry(fake_session, TENANT, storage=storage)
        fake_session.queue_scalar(None)

        with pytest.raises(ModelNotFoundError):
            await registry.promote(uuid4(), decision_id=None, promoted_by="alice")

    async def test_promote_marks_active_and_records_metadata(self, fake_session, storage):
        registry = ModelRegistry(fake_session, TENANT, storage=storage)
        target = _artifact(model_name="quality_risk", version=2)
        fake_session.queue_scalar(target)

        decision_id = uuid4()
        promoted = await registry.promote(
            artifact_id=target.id,
            decision_id=decision_id,
            promoted_by="bob",
        )

        assert promoted is target
        assert promoted.active is True
        assert promoted.promoted_by == "bob"
        assert promoted.promoted_by_decision_id == decision_id
        assert promoted.promoted_at is not None


class TestToDict:
    def test_to_dict_shape(self):
        art = _artifact(model_name="m", version=5, metrics={"wmape": 0.1})
        d = ModelRegistry.to_dict(art)
        assert d["model_name"] == "m"
        assert d["version"] == 5
        assert d["metrics"] == {"wmape": 0.1}
        assert d["active"] is False
        assert d["promoted_at"] is None


class TestGet:
    async def test_get_returns_artifact(self, fake_session, storage):
        registry = ModelRegistry(fake_session, TENANT, storage=storage)
        target = _artifact()
        fake_session.queue_scalar(target)

        fetched = await registry.get(target.id)
        assert fetched is target

    async def test_get_active_returns_none_when_absent(self, fake_session, storage):
        registry = ModelRegistry(fake_session, TENANT, storage=storage)
        fake_session.queue_scalar(None)

        assert await registry.get_active("unknown_model") is None
