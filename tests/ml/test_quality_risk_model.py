"""
Tests for src.ml.models_domain.quality_risk.QualityRiskModel.
"""

from __future__ import annotations

import random
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List
from uuid import UUID

import pytest

from src.ml.config import MLConfig
from src.ml.models.storage import ArtifactStorage
from src.ml.models_domain.quality_risk import (
    QualityRiskModel,
    QualityRiskRetrainJob,
    build_training_dataset,
)


TENANT = UUID("11111111-1111-1111-1111-111111111111")


def _synthetic_rows(n: int = 300, seed: int = 11) -> List[Dict[str, Any]]:
    """
    Synthetic training data with a learnable error signal:
    higher `phase_error_rate` and `is_rework` → higher P(error).
    """
    rng = random.Random(seed)
    modelos = ["K1", "K2"]
    fases = ["LAM", "PNT", "ACB"]
    base_rate = {"LAM": 0.35, "PNT": 0.20, "ACB": 0.05}
    rows = []
    for _ in range(n):
        fase = rng.choice(fases)
        error_rate = base_rate[fase] + rng.gauss(0, 0.05)
        error_rate = max(0.0, min(1.0, error_rate))
        is_error = int(rng.random() < error_rate)
        rows.append({
            "modelo_id": rng.choice(modelos),
            "fase_id": fase,
            "team_size": rng.choice([1, 2]),
            "mold_pocket_count": rng.choice([1, 2, 6]),
            "phase_error_rate": round(error_rate, 3),
            "queue_depth": rng.randint(5, 50),
            "is_error": is_error,
        })
    return rows


class TestQualityRiskModel:
    def test_train_and_predict(self):
        model = QualityRiskModel()
        metrics = model.train(_synthetic_rows(300), random_state=42)

        assert metrics["samples"] == 300
        assert 0.0 <= metrics["auc"] <= 1.0
        assert metrics["positive_rate"] > 0
        assert model.classifier is not None

        p = model.predict_proba({
            "modelo_id": "K1", "fase_id": "LAM",
            "team_size": 2, "mold_pocket_count": 6,
            "phase_error_rate": 0.4, "queue_depth": 20,
        })
        assert 0.0 <= p <= 1.0

    def test_predict_before_train_raises(self):
        with pytest.raises(RuntimeError):
            QualityRiskModel().predict_proba({"modelo_id": "K1"})

    def test_insufficient_data_raises(self):
        with pytest.raises(ValueError):
            QualityRiskModel().train(_synthetic_rows(10))

    def test_degenerate_labels_raises(self):
        """All-positive or all-negative should fail training."""
        rows = _synthetic_rows(100)
        for r in rows:
            r["is_error"] = 1  # all positive
        with pytest.raises(ValueError, match="positive and one negative"):
            QualityRiskModel().train(rows)

    def test_flag_threshold(self):
        model = QualityRiskModel()
        model.train(_synthetic_rows(300))
        row = {
            "modelo_id": "K1", "fase_id": "LAM",
            "team_size": 1, "mold_pocket_count": 1,
            "phase_error_rate": 0.8, "queue_depth": 30,
        }
        # Threshold 0.0 → always flagged
        assert model.flag_threshold(row, threshold=0.0) is True
        # Threshold 1.1 → never flagged
        assert model.flag_threshold(row, threshold=1.1) is False

    def test_round_trip_via_joblib(self, tmp_path: Path):
        storage = ArtifactStorage(MLConfig(artifact_dir=tmp_path, auto_promote_max_wmape_delta=0.05))
        model = QualityRiskModel()
        model.train(_synthetic_rows(200))

        uri = storage.save(model, "quality_risk", 1)
        restored: QualityRiskModel = storage.load(uri)

        assert restored.vocabulary == model.vocabulary
        row = {"modelo_id": "K1", "fase_id": "PNT",
               "team_size": 1, "mold_pocket_count": 2,
               "phase_error_rate": 0.2, "queue_depth": 15}
        assert restored.predict_proba(row) == pytest.approx(model.predict_proba(row))


class TestBuildTrainingDataset:
    def test_builds_binary_labels(self):
        phases = [
            SimpleNamespace(of_id="O1", fase_id="LAM", team_size=2, molde_id="M1"),
            SimpleNamespace(of_id="O1", fase_id="PNT", team_size=1, molde_id=None),
            SimpleNamespace(of_id="O2", fase_id="LAM", team_size=2, molde_id="M1"),
        ]
        orders = [
            SimpleNamespace(of_id="O1", modelo_id="K1"),
            SimpleNamespace(of_id="O2", modelo_id="K2"),
        ]
        quality = [SimpleNamespace(of_id="O1", fase_id="PNT")]
        molds = [SimpleNamespace(molde_id="M1", pocket_count=6)]

        engine = SimpleNamespace(
            _active_ingestion_id="active",
            _curated_data={"active": {
                "order_phases": phases,
                "orders": orders,
                "quality_events": quality,
                "molds": molds,
            }},
        )
        sq = SimpleNamespace(engine=engine)
        rows = build_training_dataset(sq)

        assert len(rows) == 3
        # O1/PNT has a quality event → is_error=1
        assert any(r["fase_id"] == "PNT" and r["is_error"] == 1 for r in rows)
        # O1/LAM has no event → is_error=0
        lam_rows = [r for r in rows if r["fase_id"] == "LAM" and r["modelo_id"] == "K1"]
        assert lam_rows[0]["is_error"] == 0

    def test_empty_when_no_semantic(self):
        assert build_training_dataset(None) == []


class TestQualityRiskRetrainJobIntegration:
    async def test_auc_promotion_policy(self):
        job = QualityRiskRetrainJob(semantic_queries=None)
        # Higher AUC wins
        assert job.should_promote({"auc": 0.90}, {"auc": 0.82}) is True
        assert job.should_promote({"auc": 0.70}, {"auc": 0.82}) is False
        assert job.should_promote({"auc": 0.85}, None) is True
