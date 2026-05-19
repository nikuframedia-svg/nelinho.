"""
Tests for src.ml.models_domain.otd_risk.OTDRiskModel (Sprint Q.54.F).

Strategy: synthetic training data (no Excel). A learnable signal —
negative `slack_days` and high `phase_error_rate_mean` push P(late) up.
Round-trip via ArtifactStorage confirms the model pickles cleanly.
"""

from __future__ import annotations

import random
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timedelta
from typing import Any, Dict, List
from uuid import UUID

import pytest

from src.ml.config import MLConfig
from src.ml.models.storage import ArtifactStorage
from src.ml.models_domain.otd_risk import (
    OTDRiskModel,
    OTDRiskRetrainJob,
    build_training_dataset,
)


TENANT = UUID("11111111-1111-1111-1111-111111111111")


def _synthetic_rows(n: int = 300, seed: int = 7) -> List[Dict[str, Any]]:
    """Synthetic order rows with a learnable late signal: an order is
    more likely to be late when slack is negative and its phases are
    error-prone."""
    rng = random.Random(seed)
    modelos = ["K1", "K2", "K4"]
    rows = []
    for _ in range(n):
        slack = rng.uniform(-10.0, 15.0)
        err = rng.uniform(0.0, 0.5)
        n_phases = rng.randint(5, 41)
        # late probability rises as slack falls and error rate rises
        p_late = max(0.0, min(1.0, 0.5 - 0.06 * slack + 0.8 * err))
        is_late = int(rng.random() < p_late)
        rows.append({
            "modelo_id": rng.choice(modelos),
            "n_phases": n_phases,
            "total_planned_hours": round(n_phases * rng.uniform(2, 8), 1),
            "slack_days": round(slack, 2),
            "open_phases": rng.randint(0, n_phases),
            "phase_error_rate_mean": round(err, 3),
            "is_late": is_late,
        })
    return rows


class TestOTDRiskModel:
    def test_train_and_predict(self):
        model = OTDRiskModel()
        metrics = model.train(_synthetic_rows(300), random_state=42)

        assert metrics["samples"] == 300
        assert 0.0 <= metrics["auc"] <= 1.0
        assert 0.0 <= metrics["positive_rate"] <= 1.0
        assert model.classifier is not None

        p = model.predict_proba({
            "modelo_id": "K1", "n_phases": 20, "total_planned_hours": 90.0,
            "slack_days": -5.0, "open_phases": 12, "phase_error_rate_mean": 0.4,
        })
        assert 0.0 <= p <= 1.0

    def test_predict_before_train_raises(self):
        with pytest.raises(RuntimeError):
            OTDRiskModel().predict_proba({"modelo_id": "K1"})

    def test_insufficient_data_raises(self):
        with pytest.raises(ValueError):
            OTDRiskModel().train(_synthetic_rows(10))

    def test_degenerate_labels_raise(self):
        rows = _synthetic_rows(50)
        for r in rows:
            r["is_late"] = 0  # all on-time — no signal
        with pytest.raises(ValueError):
            OTDRiskModel().train(rows)

    def test_batch_predict(self):
        model = OTDRiskModel()
        model.train(_synthetic_rows(300))
        probs = model.predict_proba_batch(_synthetic_rows(20, seed=99))
        assert len(probs) == 20
        assert all(0.0 <= p <= 1.0 for p in probs)

    def test_negative_slack_raises_risk(self):
        """The model must learn the domain signal: a tight (negative
        slack) order with error-prone phases scores higher than a
        comfortable one."""
        model = OTDRiskModel()
        model.train(_synthetic_rows(500))
        tight = model.predict_proba({
            "modelo_id": "K1", "n_phases": 30, "total_planned_hours": 150.0,
            "slack_days": -8.0, "open_phases": 25, "phase_error_rate_mean": 0.45,
        })
        comfortable = model.predict_proba({
            "modelo_id": "K1", "n_phases": 30, "total_planned_hours": 150.0,
            "slack_days": 12.0, "open_phases": 5, "phase_error_rate_mean": 0.05,
        })
        assert tight > comfortable

    def test_round_trip_via_joblib(self, tmp_path: Path):
        storage = ArtifactStorage(
            MLConfig(artifact_dir=tmp_path, auto_promote_max_wmape_delta=0.05)
        )
        model = OTDRiskModel()
        model.train(_synthetic_rows(300))

        uri = storage.save(model, "otd_risk", 1)
        restored: OTDRiskModel = storage.load(uri)

        assert restored.vocabulary == model.vocabulary
        assert restored.classifier is not None
        row = {
            "modelo_id": "K2", "n_phases": 15, "total_planned_hours": 70.0,
            "slack_days": 2.0, "open_phases": 8, "phase_error_rate_mean": 0.2,
        }
        assert restored.predict_proba(row) == model.predict_proba(row)


class TestBuildTrainingDataset:
    def test_empty_when_no_semantic(self):
        assert build_training_dataset(None) == []

    def test_joins_orders_phases_and_labels_late(self):
        due = datetime(2026, 5, 1, 12, 0, 0)
        phases = [
            # O1 finishes late (after due)
            SimpleNamespace(of_id="O1", fase_id="LAM",
                            data_fim_real=datetime(2026, 5, 3, 9, 0, 0),
                            horas_reais=8.0),
            SimpleNamespace(of_id="O1", fase_id="PNT",
                            data_fim_real=datetime(2026, 5, 2, 9, 0, 0),
                            horas_reais=3.0),
            # O2 finishes on time (before due)
            SimpleNamespace(of_id="O2", fase_id="LAM",
                            data_fim_real=datetime(2026, 4, 28, 9, 0, 0),
                            horas_reais=7.5),
        ]
        orders = [
            SimpleNamespace(of_id="O1", modelo_id="K1", data_entrega_prevista=due),
            SimpleNamespace(of_id="O2", modelo_id="K2", data_entrega_prevista=due),
        ]
        quality = [SimpleNamespace(of_id="O1", fase_id="PNT")]

        engine = SimpleNamespace(
            _active_ingestion_id="active",
            _curated_data={
                "active": {
                    "order_phases": phases,
                    "orders": orders,
                    "quality_events": quality,
                }
            },
        )
        sq = SimpleNamespace(engine=engine)
        rows = build_training_dataset(sq)

        assert len(rows) == 2
        o1 = next(r for r in rows if r["modelo_id"] == "K1")
        o2 = next(r for r in rows if r["modelo_id"] == "K2")
        assert o1["is_late"] == 1
        assert o2["is_late"] == 0
        assert o1["n_phases"] == 2
        assert o1["slack_days"] < 0  # finished after due

    def test_order_without_due_date_skipped(self):
        phases = [
            SimpleNamespace(of_id="O1", fase_id="LAM",
                            data_fim_real=datetime(2026, 5, 3), horas_reais=8.0),
        ]
        orders = [SimpleNamespace(of_id="O1", modelo_id="K1",
                                  data_entrega_prevista=None)]
        engine = SimpleNamespace(
            _active_ingestion_id="active",
            _curated_data={"active": {"order_phases": phases, "orders": orders}},
        )
        rows = build_training_dataset(SimpleNamespace(engine=engine))
        assert rows == []

    def test_unfinished_order_skipped(self):
        """An order whose phases have no real finish time can't be
        labelled — it must not enter the training set."""
        phases = [
            SimpleNamespace(of_id="O1", fase_id="LAM",
                            data_fim_real=None, horas_reais=8.0),
        ]
        orders = [SimpleNamespace(of_id="O1", modelo_id="K1",
                                  data_entrega_prevista=datetime(2026, 5, 1))]
        engine = SimpleNamespace(
            _active_ingestion_id="active",
            _curated_data={"active": {"order_phases": phases, "orders": orders}},
        )
        rows = build_training_dataset(SimpleNamespace(engine=engine))
        assert rows == []


class TestOTDRiskRetrainJobIntegration:
    async def test_lifecycle_with_synthetic_data(self, fake_session, tmp_path):
        """Full RetrainJob lifecycle: extract → train → validate → save."""
        from src.ml.jobs import base as base_module
        import pytest as _pytest

        storage = ArtifactStorage(
            MLConfig(artifact_dir=tmp_path, auto_promote_max_wmape_delta=0.05)
        )
        orig_registry = base_module.ModelRegistry

        class _Job(OTDRiskRetrainJob):
            def extract_features(self, tenant_id):
                return _synthetic_rows(300)

        # Patch ModelRegistry to use the tmp storage.
        base_module.ModelRegistry = lambda s, t: orig_registry(s, t, storage=storage)
        try:
            job = _Job(semantic_queries=None)
            fake_session.queue_scalar(None)  # get_active baseline
            fake_session.queue_scalar(None)  # _next_version
            summary = await job.run(fake_session, TENANT, governance_service=None)
        finally:
            base_module.ModelRegistry = orig_registry

        assert summary["status"] == "success"
        assert summary["model_name"] == "otd_risk"
        assert summary["training_samples"] == 300
