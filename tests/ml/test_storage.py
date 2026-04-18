"""
Tests for src.ml.models.storage.ArtifactStorage.

Strategy: point the artifact_dir at a per-test tmp_path and round-trip
a simple Python object (dict works — joblib serialises anything picklable).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.ml.config import MLConfig
from src.ml.models.storage import ArtifactStorage, FILE_SCHEME


@pytest.fixture
def storage(tmp_path: Path) -> ArtifactStorage:
    cfg = MLConfig(artifact_dir=tmp_path, auto_promote_max_wmape_delta=0.05)
    return ArtifactStorage(cfg)


class TestArtifactStorage:
    def test_save_and_load_round_trip(self, storage, tmp_path):
        obj = {"w": [0.1, 0.2, 0.3], "bias": 4.2, "label": "model-v1"}
        uri = storage.save(obj, "test_model", version=1)

        assert uri.startswith(FILE_SCHEME)
        # Path is inside our tmp_path
        assert str(tmp_path.as_posix()) in uri
        # Loads back equal
        assert storage.load(uri) == obj

    def test_save_many_versions(self, storage):
        v1 = storage.save({"ver": 1}, "clf", 1)
        v2 = storage.save({"ver": 2}, "clf", 2)
        assert v1 != v2
        assert storage.load(v1)["ver"] == 1
        assert storage.load(v2)["ver"] == 2

    def test_load_missing_raises(self, storage):
        with pytest.raises(FileNotFoundError):
            storage.load("file:///nonexistent/path/model.joblib")

    def test_delete_removes_file(self, storage):
        uri = storage.save({"x": 1}, "clf", 1)
        assert storage.delete(uri) is True
        assert storage.delete(uri) is False  # already gone — idempotent

    def test_name_with_slash_is_sanitized(self, storage, tmp_path):
        uri = storage.save({"x": 1}, "nested/name/../escape", 1)
        # Use the storage's own URI → Path resolver so this test works on
        # both POSIX (file:///abs/path) and Windows (file://C:/abs/path).
        saved_path = storage._resolve(uri)
        try:
            saved_path.resolve().relative_to(tmp_path.resolve())
        except ValueError:
            pytest.fail(f"Saved path {saved_path} escaped outside {tmp_path}")
        # And the roundtrip still works (not corrupted by the sanitization)
        assert storage.load(uri) == {"x": 1}

    def test_handles_bare_path_uri(self, storage):
        """Backward compat: if someone passes a bare path (no file://), load still works."""
        uri = storage.save({"x": 42}, "clf", 1)
        bare = uri.replace(FILE_SCHEME, "")
        assert storage.load(bare)["x"] == 42
