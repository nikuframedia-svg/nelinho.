"""
Tests for src.ml.models_domain.duration.DurationModel + DurationRetrainJob.

Strategy: synthetic training data (no Excel). Round-trip via ArtifactStorage
ensures the model pickles + restores correctly.
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
from src.ml.models_domain.duration import (
    DurationModel,
    DurationRetrainJob,
    build_training_dataset,
)


TENANT = UUID("11111111-1111-1111-1111-111111111111")


def _synthetic_rows(n: int = 200, seed: int = 123) -> List[Dict[str, Any]]:
    """
    Generate synthetic (fase, modelo, team_size, ..., horas_reais) rows with
    a learnable relationship: horas_reais = base(modelo) + phase_offset(fase)
    + team_discount + noise.
    """
    rng = random.Random(seed)
    modelos = ["K1", "K2", "VX"]
    fases = ["LAM", "PNT", "ACB", "MNT"]
    base = {"K1": 8.0, "K2": 6.0, "VX": 12.0}
    phase_offset = {"LAM": 0.0, "PNT": 2.0, "ACB": -1.0, "MNT": 1.5}
    rows = []
    for _ in range(n):
        modelo = rng.choice(modelos)
        fase = rng.choice(fases)
        team = rng.choice([1, 2])
        horas = (
            base[modelo]
            + phase_offset[fase]
            - 0.7 * (team - 1)
            + rng.gauss(0, 0.6)
        )
        rows.append({
            "modelo_id": modelo,
            "fase_id": fase,
            "team_size": team,
            "mold_pocket_count": rng.choice([1, 2, 6]),
            "is_rework": rng.choice([0, 0, 0, 1]),
            "queue_depth": rng.randint(5, 50),
            "horas_reais": max(0.1, horas),
        })
    return rows


class TestDurationModel:
    def test_train_and_predict(self):
        model = DurationModel()
        metrics = model.train(_synthetic_rows(200), random_state=42)

        assert metrics["samples"] == 200
        assert 0.0 <= metrics["wmape"] <= 0.5  # sane bound
        assert metrics["mae_hours"] >= 0
        assert model.regressor is not None

        pred = model.predict(
            {"modelo_id": "K1", "fase_id": "LAM", "team_size": 2,
             "mold_pocket_count": 6, "is_rework": 0, "queue_depth": 20}
        )
        assert pred["p50_hours"] > 0
        assert pred["p90_hours"] >= pred["p50_hours"]

    def test_predict_before_train_raises(self):
        with pytest.raises(RuntimeError):
            DurationModel().predict({"modelo_id": "K1", "fase_id": "LAM"})

    def test_insufficient_data_raises(self):
        model = DurationModel()
        with pytest.raises(ValueError):
            model.train(_synthetic_rows(5))

    def test_rows_with_zero_horas_filtered(self):
        rows = _synthetic_rows(100)
        for r in rows[:50]:
            r["horas_reais"] = 0  # invalid targets
        model = DurationModel()
        metrics = model.train(rows)
        assert metrics["samples"] == 50

    def test_unknown_category_at_inference_is_zero_onehot(self):
        model = DurationModel()
        model.train(_synthetic_rows(100))
        pred = model.predict({
            "modelo_id": "UNKNOWN_MODEL",
            "fase_id": "UNKNOWN_PHASE",
            "team_size": 1,
            "mold_pocket_count": 1,
            "is_rework": 0,
            "queue_depth": 10,
        })
        # Still produces a number (maybe not accurate, but doesn't crash)
        assert isinstance(pred["p50_hours"], float)

    def test_round_trip_via_joblib(self, tmp_path: Path):
        storage = ArtifactStorage(MLConfig(artifact_dir=tmp_path, auto_promote_max_wmape_delta=0.05))
        model = DurationModel()
        model.train(_synthetic_rows(100))

        uri = storage.save(model, "duration", 1)
        restored: DurationModel = storage.load(uri)

        # Vocab + regressor carried across
        assert restored.vocabulary == model.vocabulary
        assert restored.regressor is not None

        # Prediction equal (determinism after pickle)
        row = {"modelo_id": "K1", "fase_id": "LAM", "team_size": 2,
               "mold_pocket_count": 6, "is_rework": 0, "queue_depth": 20}
        assert restored.predict(row) == model.predict(row)


class TestBuildTrainingDataset:
    def test_empty_when_no_semantic(self):
        assert build_training_dataset(None) == []

    def test_joins_phases_orders_quality(self):
        phases = [
            SimpleNamespace(of_id="O1", fase_id="LAM", horas_reais=8.0, team_size=2, molde_id="M1"),
            SimpleNamespace(of_id="O1", fase_id="PNT", horas_reais=3.0, team_size=1, molde_id=None),
            SimpleNamespace(of_id="O2", fase_id="LAM", horas_reais=7.5, team_size=2, molde_id="M1"),
        ]
        orders = [
            SimpleNamespace(of_id="O1", modelo_id="K1"),
            SimpleNamespace(of_id="O2", modelo_id="K2"),
        ]
        quality = [SimpleNamespace(of_id="O1", fase_id="PNT")]
        molds = [SimpleNamespace(molde_id="M1", pocket_count=6)]

        engine = SimpleNamespace(
            _active_ingestion_id="active",
            _curated_data={
                "active": {
                    "order_phases": phases,
                    "orders": orders,
                    "quality_events": quality,
                    "molds": molds,
                }
            },
        )
        sq = SimpleNamespace(engine=engine)
        rows = build_training_dataset(sq)

        assert len(rows) == 3
        # Phase O1/PNT was flagged as rework
        o1_pnt = next(r for r in rows if r["fase_id"] == "PNT")
        assert o1_pnt["is_rework"] == 1
        # Molde pocket count carried through
        o1_lam = next(r for r in rows if r["fase_id"] == "LAM" and r["modelo_id"] == "K1")
        assert o1_lam["mold_pocket_count"] == 6
        # queue_depth = count of LAM phases = 2
        assert o1_lam["queue_depth"] == 2


class TestDurationRetrainJobIntegration:
    async def test_lifecycle_with_synthetic_data(self, fake_session, tmp_path, monkeypatch):
        """Full RetrainJob lifecycle: extract → train → validate → save."""
        from src.ml.jobs import base as base_module

        storage = ArtifactStorage(MLConfig(artifact_dir=tmp_path, auto_promote_max_wmape_delta=0.05))

        orig_registry = base_module.ModelRegistry
        monkeypatch.setattr(
            base_module, "ModelRegistry",
            lambda s, t: orig_registry(s, t, storage=storage),
        )

        # Provide synthetic rows via the job's extract_features override
        class _Job(DurationRetrainJob):
            def extract_features(self, tenant_id):
                return _synthetic_rows(150)

        job = _Job(semantic_queries=None)
        fake_session.queue_scalar(None)  # get_active baseline
        fake_session.queue_scalar(None)  # _next_version

        summary = await job.run(fake_session, TENANT, governance_service=None)
        assert summary["status"] == "success"
        assert summary["model_name"] == "duration"
        assert summary["training_samples"] == 150
        assert summary["metrics"]["wmape"] >= 0
