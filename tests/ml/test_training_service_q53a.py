"""
Q.53.A — ML training service sanity.

The training service builds a dataset from the DB and fits the model. Here
we exercise the fit step on rows shaped exactly like
`build_quality_risk_dataset` output and assert the trained predictor gives
a higher P(defeito) to a historically error-prone fase than to a clean one
— the core property the CPO relies on.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.ml.models_domain.duration import DurationModel
from src.ml.models_domain.quality_risk import QualityRiskModel

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _quality_rows() -> list[dict]:
    """Mimics build_quality_risk_dataset: a risky fase (Laminagem, 40% rate)
    and a clean fase (Armazem, ~0%)."""
    rows: list[dict] = []
    for i in range(200):
        rows.append({
            "modelo_id": "K1", "fase_id": "36",
            "team_size": 1, "mold_pocket_count": 1,
            "phase_error_rate": 0.40, "queue_depth": 200,
            "is_error": 1 if i < 80 else 0,  # 40% labelled error
            "timestamp": T0 + timedelta(hours=i),
        })
    for i in range(200):
        rows.append({
            "modelo_id": "K1", "fase_id": "9",
            "team_size": 1, "mold_pocket_count": 1,
            "phase_error_rate": 0.02, "queue_depth": 200,
            "is_error": 1 if i < 4 else 0,  # 2% labelled error
            "timestamp": T0 + timedelta(hours=200 + i),
        })
    return rows


def test_quality_risk_separates_risky_from_clean_fase():
    model = QualityRiskModel()
    metrics = model.train(_quality_rows())

    assert metrics["samples"] == 400
    assert 0.0 < metrics["positive_rate"] < 1.0

    risky = model.predict_proba({
        "modelo_id": "K1", "fase_id": "36",
        "team_size": 1, "mold_pocket_count": 1,
        "phase_error_rate": 0.40, "queue_depth": 200,
    })
    clean = model.predict_proba({
        "modelo_id": "K1", "fase_id": "9",
        "team_size": 1, "mold_pocket_count": 1,
        "phase_error_rate": 0.02, "queue_depth": 200,
    })
    assert 0.0 <= clean <= 1.0 and 0.0 <= risky <= 1.0
    # The historically error-prone fase must score strictly higher.
    assert risky > clean


def test_quality_risk_batch_matches_singletons():
    model = QualityRiskModel()
    model.train(_quality_rows())
    feats = [
        {"modelo_id": "K1", "fase_id": "36", "team_size": 1,
         "mold_pocket_count": 1, "phase_error_rate": 0.40, "queue_depth": 200},
        {"modelo_id": "K1", "fase_id": "9", "team_size": 1,
         "mold_pocket_count": 1, "phase_error_rate": 0.02, "queue_depth": 200},
    ]
    batch = model.predict_proba_batch(feats)
    assert len(batch) == 2
    for f, b in zip(feats, batch):
        assert b == model.predict_proba(f)


def test_duration_model_trains_on_db_shaped_rows():
    """build_duration_dataset rows must fit DurationModel without error."""
    rows = [
        {"modelo_id": "K1", "fase_id": "36", "team_size": 1,
         "mold_pocket_count": 1, "is_rework": 0, "queue_depth": 50,
         "horas_reais": 6.0 + (i % 5), "timestamp": T0 + timedelta(hours=i)}
        for i in range(60)
    ]
    model = DurationModel()
    metrics = model.train(rows)
    assert metrics["samples"] == 60
    pred = model.predict({
        "modelo_id": "K1", "fase_id": "36", "team_size": 1,
        "mold_pocket_count": 1, "is_rework": 0, "queue_depth": 50,
    })
    assert pred["p50_hours"] >= 0.0
    assert pred["p90_hours"] >= pred["p50_hours"]
