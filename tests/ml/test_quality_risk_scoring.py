"""
Tests for src.ml.scoring.quality_risk_scoring (Sprint Q.41.A).

Covers the activation of the previously-stubbed `_quality_risk_scoring_job`:
the scorer must (a) write `quality_risk_score` on pending schedule rows when
a model is trained, and (b) degrade honestly — never report a false success —
when there is no model or no rows.

Strategy: the shared `FakeSession` queues query results in call order. A real
QualityRiskModel is trained on synthetic rows and round-tripped through
ArtifactStorage so the registry loader can `load()` it from disk.
"""

from __future__ import annotations

import random
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List
from uuid import UUID, uuid4

import pytest

from src.ml.config import MLConfig
from src.ml.models.orm import MLModelArtifact
from src.ml.models.storage import ArtifactStorage
from src.ml.models_domain.quality_risk import QualityRiskModel
from src.ml.scoring.quality_risk_scoring import (
    QualityRiskScoringResult,
    score_quality_risk,
)


TENANT = UUID("11111111-1111-1111-1111-111111111111")


def _synthetic_rows(n: int = 300, seed: int = 7) -> List[Dict[str, Any]]:
    """Synthetic training data with a learnable error signal."""
    rng = random.Random(seed)
    base_rate = {"LAM": 0.35, "PNT": 0.20, "ACB": 0.05}
    rows = []
    for _ in range(n):
        fase = rng.choice(list(base_rate))
        error_rate = max(0.0, min(1.0, base_rate[fase] + rng.gauss(0, 0.05)))
        rows.append({
            "modelo_id": rng.choice(["K1", "K2"]),
            "fase_id": fase,
            "team_size": rng.choice([1, 2]),
            "mold_pocket_count": rng.choice([1, 2, 6]),
            "phase_error_rate": round(error_rate, 3),
            "queue_depth": rng.randint(5, 50),
            "is_error": int(rng.random() < error_rate),
        })
    return rows


def _trained_artifact(tmp_path: Path) -> tuple[MLModelArtifact, ArtifactStorage]:
    """Train a QualityRiskModel, persist it, return an active artifact row."""
    storage = ArtifactStorage(
        MLConfig(artifact_dir=tmp_path, auto_promote_max_wmape_delta=0.05)
    )
    model = QualityRiskModel()
    model.train(_synthetic_rows())
    uri = storage.save(model, "quality_risk", 1)
    artifact = MLModelArtifact(
        id=uuid4(),
        tenant_id=TENANT,
        model_name="quality_risk",
        version=3,
        storage_uri=uri,
        metrics={"auc": 0.81},
        active=True,
        trained_by="test",
    )
    return artifact, storage


def _schedule_row(*, product_id: UUID, operation_id: UUID) -> SimpleNamespace:
    """A minimal ProductionSchedule-shaped object the scorer can mutate."""
    return SimpleNamespace(
        id=uuid4(),
        tenant_id=TENANT,
        product_id=product_id,
        operation_id=operation_id,
        status="SCHEDULED",
        scheduled_start_date=date(2026, 5, 20),
        scheduled_duration_hours=Decimal("4.50"),
        assigned_employee_id=None,
        quality_risk_score=None,
        quality_risk_scored_at=None,
    )


class TestNoModel:
    async def test_no_active_model_is_honest_noop(self, fake_session, monkeypatch):
        """Without a trained model the scorer reports no_model — not success."""
        # registry.get_active("quality_risk") -> None inside the loader.
        fake_session.queue_scalar(None)

        result = await score_quality_risk(fake_session, TENANT)

        assert isinstance(result, QualityRiskScoringResult)
        assert result.status == "no_model"
        assert result.rows_scored == 0
        # Nothing was flushed — honest no-op, not a fake success.
        assert fake_session.flush_calls == 0


class TestNoRows:
    async def test_model_present_but_no_pending_schedules(
        self, fake_session, tmp_path
    ):
        """A trained model + zero pending rows -> no_rows, nothing persisted."""
        artifact, storage = _trained_artifact(tmp_path)
        monkey_storage(artifact, storage)

        # FakeSession.execute consumes one scalar AND one scalars list per
        # call. Calls in order: loader get_active, version get_active,
        # schedules select. Pad the scalars queue so the schedules call
        # (3rd) returns an empty list.
        fake_session.queue_scalar(artifact)
        fake_session.queue_scalar(artifact)
        fake_session.queue_scalars([])  # call 1 — unused scalars slot
        fake_session.queue_scalars([])  # call 2 — unused scalars slot
        fake_session.queue_scalars([])  # call 3 — schedules: none pending

        result = await score_quality_risk(fake_session, TENANT)

        assert result.status == "no_rows"
        assert result.model_version == 3
        assert result.rows_scored == 0
        assert fake_session.flush_calls == 0


class TestScoresRows:
    async def test_scores_pending_schedule_rows(self, fake_session, tmp_path):
        """The happy path: pending rows get a clamped score + scored_at."""
        artifact, storage = _trained_artifact(tmp_path)
        monkey_storage(artifact, storage)

        prod_a, prod_b = uuid4(), uuid4()
        op_lam, op_pnt = uuid4(), uuid4()
        rows = [
            _schedule_row(product_id=prod_a, operation_id=op_lam),
            _schedule_row(product_id=prod_b, operation_id=op_pnt),
        ]

        # FakeSession.execute pops one scalar AND one scalars list per
        # call. Call order: loader get_active, version get_active,
        # schedules select, product-code select, operation-code select.
        fake_session.queue_scalar(artifact)        # call 1 scalar
        fake_session.queue_scalar(artifact)        # call 2 scalar
        fake_session.queue_scalars([])             # call 1 — unused
        fake_session.queue_scalars([])             # call 2 — unused
        fake_session.queue_scalars(rows)           # call 3 — schedules
        fake_session.queue_scalars([(prod_a, "K1"), (prod_b, "K2")])   # call 4
        fake_session.queue_scalars([(op_lam, "LAM"), (op_pnt, "PNT")])  # call 5

        result = await score_quality_risk(fake_session, TENANT)

        assert result.status == "scored"
        assert result.rows_considered == 2
        assert result.rows_scored == 2
        assert fake_session.flush_calls == 1
        for row in rows:
            assert row.quality_risk_score is not None
            assert Decimal("0") <= row.quality_risk_score <= Decimal("1")
            assert row.quality_risk_scored_at is not None


# ---------------------------------------------------------------------------
# Helper — patch ModelRegistry to use the tmp_path-backed storage so the
# registry loader can `load()` the round-tripped artifact from disk.
# ---------------------------------------------------------------------------

_PATCHED: Dict[str, Any] = {}


def monkey_storage(artifact: MLModelArtifact, storage: ArtifactStorage) -> None:
    """Pin ArtifactStorage so ModelRegistry(...).load() resolves tmp_path."""
    _PATCHED["storage"] = storage


@pytest.fixture(autouse=True)
def _patch_registry_storage(monkeypatch):
    """Make every ModelRegistry constructed during a test use the test
    storage (tmp_path-rooted) instead of the global artifact_dir."""
    import src.ml.models.registry as registry_mod

    orig_init = registry_mod.ModelRegistry.__init__

    def patched_init(self, session, tenant_id, storage=None):
        orig_init(self, session, tenant_id, storage=_PATCHED.get("storage", storage))

    monkeypatch.setattr(registry_mod.ModelRegistry, "__init__", patched_init)
    yield
    _PATCHED.clear()
