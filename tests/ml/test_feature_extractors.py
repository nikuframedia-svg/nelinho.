"""
Tests for src.ml.feature_engineering.extractors + registry.

Strategy: pass a stub object exposing `.engine._active_ingestion_id` and
`._curated_data` so the extractors' `_curated()` helper finds rows without
a real IngestEngine.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest

from src.ml.feature_engineering.extractors import (
    FeatureExtractor,
    MoldFeatures,
    OrderFeatures,
    PhaseFeatures,
    WorkerFeatures,
)
from src.ml.feature_engineering.registry import (
    get_extractor_cls,
    list_extractors,
    register_extractor,
)


TENANT = UUID("11111111-1111-1111-1111-111111111111")


def _stub_semantic(**buckets) -> SimpleNamespace:
    """Build a fake semantic-queries object with the requested curated buckets."""
    engine = SimpleNamespace(
        _active_ingestion_id="active",
        _curated_data={"active": dict(buckets)},
    )
    return SimpleNamespace(engine=engine)


class TestOrderFeatures:
    def test_extracts_basic_fields(self):
        extractor = OrderFeatures(TENANT)
        order = {"of_id": "O-1", "modelo_id": "K1", "quantidade": 3, "data_entrega_prevista": "2026-05-01"}

        feats = extractor.extract(order)
        assert feats["of_id"] == "O-1"
        assert feats["modelo_id"] == "K1"
        assert feats["quantidade"] == 3.0
        assert feats["has_due_date"] is True

    def test_no_due_date(self):
        extractor = OrderFeatures(TENANT)
        feats = extractor.extract({"of_id": "O-2", "modelo_id": "K1", "quantidade": 1})
        assert feats["has_due_date"] is False


class TestPhaseFeatures:
    def test_error_rate_and_duration(self):
        phases = [
            SimpleNamespace(fase_id="FASE-LAM", modelo_id="K1", horas_reais=8.0),
            SimpleNamespace(fase_id="FASE-LAM", modelo_id="K1", horas_reais=7.0),
            SimpleNamespace(fase_id="FASE-LAM", modelo_id="K1", horas_reais=9.0),
            SimpleNamespace(fase_id="FASE-PNT", modelo_id="K1", horas_reais=12.0),
        ]
        errors = [
            SimpleNamespace(fase_id="FASE-LAM", of_id="O-1"),
            SimpleNamespace(fase_id="FASE-LAM", of_id="O-2"),
        ]

        stub = _stub_semantic(
            order_phases=phases,
            quality_events=errors,
        )
        extractor = PhaseFeatures(TENANT, stub)

        feats = extractor.extract({"of_id": "O-1", "fase_id": "FASE-LAM", "modelo_id": "K1"})
        # 2 errors / 3 phases = 0.6667
        assert feats["historical_error_rate"] == pytest.approx(0.6667, abs=1e-3)
        # Median of [7,8,9] = 8
        assert feats["median_duration_h"] == 8.0
        # is_rework: O-1 has an error on FASE-LAM
        assert feats["is_rework"] is True

    def test_no_data_yields_zero_error_rate(self):
        extractor = PhaseFeatures(TENANT, _stub_semantic())
        feats = extractor.extract({"of_id": "O-1", "fase_id": "FASE-XY", "modelo_id": "K1"})
        assert feats["historical_error_rate"] == 0.0
        assert feats["median_duration_h"] is None


class TestWorkerFeatures:
    def test_counts_aptas_phases(self):
        skills = [
            SimpleNamespace(funcionario_id="W1", fase_id="FASE-LAM", apto=True),
            SimpleNamespace(funcionario_id="W1", fase_id="FASE-PNT", apto=True),
            SimpleNamespace(funcionario_id="W1", fase_id="FASE-OLD", apto=False),
            SimpleNamespace(funcionario_id="W2", fase_id="FASE-LAM", apto=True),
        ]
        extractor = WorkerFeatures(TENANT, _stub_semantic(skill_matrix=skills))

        feats = extractor.extract("W1")
        assert feats["funcionario_id"] == "W1"
        assert feats["n_fases_aptos"] == 2  # False excluded


class TestMoldFeatures:
    def test_extracts_mold_metadata(self):
        molds = [
            SimpleNamespace(
                molde_id="MLD-1",
                modelo_id="K1",
                pocket_count=6,
                em_manutencao=False,
            ),
        ]
        uses = [
            SimpleNamespace(molde_id="MLD-1", of_id="O-1"),
            SimpleNamespace(molde_id="MLD-1", of_id="O-2"),
            SimpleNamespace(molde_id="MLD-2", of_id="O-3"),
        ]
        extractor = MoldFeatures(TENANT, _stub_semantic(molds=molds, mold_usage=uses))

        feats = extractor.extract("MLD-1")
        assert feats["modelo_id"] == "K1"
        assert feats["pocket_count"] == 6
        assert feats["em_manutencao"] is False
        assert feats["uses_total"] == 2

    def test_unknown_mold_defaults(self):
        extractor = MoldFeatures(TENANT, _stub_semantic(molds=[], mold_usage=[]))
        feats = extractor.extract("MLD-?")
        assert feats["pocket_count"] == 1
        assert feats["em_manutencao"] is False
        assert feats["uses_total"] == 0


class TestExtractorRegistry:
    def test_builtin_extractors_registered(self):
        extractors = list_extractors()
        assert "order" in extractors
        assert "phase" in extractors
        assert "worker" in extractors
        assert "mold" in extractors

    def test_get_extractor_cls(self):
        assert get_extractor_cls("order") is OrderFeatures

    def test_unknown_raises(self):
        with pytest.raises(KeyError):
            get_extractor_cls("nonexistent")

    def test_register_new_extractor(self):
        class CustomExtractor(FeatureExtractor):
            name = "custom_test"

            def extract(self, entity, context=None):
                return {"custom": True}

        register_extractor(CustomExtractor)
        assert get_extractor_cls("custom_test") is CustomExtractor
