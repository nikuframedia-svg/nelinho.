"""Q.115.E — testes do endpoint GET /v1/quality/risk-preview.

8 testes conforme especificação:
1. Happy path com modelo activo — 200 com p_defect válido, historical_count > 0
2. Sem modelo activo — fallback histórico, confidence=low, p_defect empírico
3. Operator desconhecido — historical_count=0
4. boat_id ausente (Q.115.A.07 deferred) — boat_id=None no response
5. Cache hit — 2x mesma query → sem erro (Redis opcional)
6. Top-3 similar_pairs ordenados por sample_n DESC
7. Top-3 risk_factors com PT-PT
8. Confidence thresholds: 0/20/101 amostras → low/medium/high

Padrão FakeSession (Q.61.02) — sem PostgreSQL, sem SQLite.
Patches em _historical_stats + _phase_error_rates para isolar da DB.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.quality.services.defect_risk_service import (
    DefectRiskService,
    QualityRiskPreview,
    SimilarPair,
)
from tests.conftest import FakeSession

TENANT = uuid4()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_predictor(p: float = 0.35) -> Any:
    """Callable que simula predictor com feature_importances_."""
    clf = MagicMock()
    # 4 features numéricas (len(NUMERIC_COLS) == 4), total 10 features
    clf.feature_importances_ = [0.05] * 6 + [0.1, 0.3, 0.4, 0.15]
    predictor = MagicMock(return_value=[p])
    predictor.classifier = clf
    return predictor


def _make_fake_session() -> FakeSession:
    return FakeSession()


def _pairs(data: list[tuple]) -> list[SimilarPair]:
    return [
        SimilarPair(
            operator_id=str(row[0]),
            operator_name=str(row[0]),
            phase_id=str(row[1]),
            phase_name=str(row[1]),
            historical_defect_rate=round(float(row[3]) / max(float(row[2]), 1), 4),
            sample_n=int(row[2]),
        )
        for row in data
    ]


# ---------------------------------------------------------------------------
# Teste 1 — Happy path com modelo activo
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_happy_path_modelo_activo():
    """p_defect válido, historical_count > 0, confidence medium."""
    raw_pairs = [("op-1", "F01", 50, 5), ("op-2", "F02", 30, 3), ("op-1", "F03", 25, 2)]
    sp = _pairs(raw_pairs)
    session = _make_fake_session()
    predictor = _mock_predictor(0.35)

    with patch.object(
        DefectRiskService, "_historical_stats", new_callable=AsyncMock,
        return_value=(50, sp),
    ), patch.object(
        DefectRiskService, "_phase_error_rates", new_callable=AsyncMock,
        return_value={"F01": 0.1},
    ), patch(
        "src.quality.services.defect_risk_service.ensure_quality_risk_model",
        new_callable=AsyncMock,
    ), patch(
        "src.quality.services.defect_risk_service.load_active_quality_risk_predictor",
        new_callable=AsyncMock,
        return_value=predictor,
    ):
        svc = DefectRiskService(session, TENANT)
        result = await svc.preview_for_combination(operator_id="op-1", phase_id="F01")

    assert isinstance(result, QualityRiskPreview)
    assert 0.0 <= result.p_defect <= 1.0
    assert result.historical_count == 50
    assert result.confidence == "medium"
    assert result.operator_id == "op-1"
    assert result.phase_id == "F01"
    assert isinstance(result.computed_at, datetime)


# ---------------------------------------------------------------------------
# Teste 2 — Sem modelo activo → fallback empírico
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sem_modelo_activo_fallback():
    """Sem modelo activo: confidence=low, p_defect via phase_error_rate."""
    session = _make_fake_session()

    with patch.object(
        DefectRiskService, "_historical_stats", new_callable=AsyncMock,
        return_value=(5, []),
    ), patch.object(
        DefectRiskService, "_phase_error_rates", new_callable=AsyncMock,
        return_value={"F99": 0.12},
    ), patch(
        "src.quality.services.defect_risk_service.ensure_quality_risk_model",
        new_callable=AsyncMock,
    ), patch(
        "src.quality.services.defect_risk_service.load_active_quality_risk_predictor",
        new_callable=AsyncMock,
        return_value=None,
    ):
        svc = DefectRiskService(session, TENANT)
        result = await svc.preview_for_combination(operator_id="op-x", phase_id="F99")

    assert result.confidence == "low"
    assert 0.0 <= result.p_defect <= 1.0
    assert len(result.top_risk_factors) >= 1
    assert result.top_risk_factors[0].feature == "phase_error_rate"
    # PT-PT
    assert result.top_risk_factors[0].description_pt != ""
    assert result.p_defect == 0.12  # empírico = phase_error_rate da fase


# ---------------------------------------------------------------------------
# Teste 3 — Operator desconhecido → historical_count=0
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_operator_desconhecido():
    """Operator sem histórico → historical_count=0, confidence=low."""
    session = _make_fake_session()

    with patch.object(
        DefectRiskService, "_historical_stats", new_callable=AsyncMock,
        return_value=(0, []),
    ), patch.object(
        DefectRiskService, "_phase_error_rates", new_callable=AsyncMock,
        return_value={},
    ), patch(
        "src.quality.services.defect_risk_service.ensure_quality_risk_model",
        new_callable=AsyncMock,
    ), patch(
        "src.quality.services.defect_risk_service.load_active_quality_risk_predictor",
        new_callable=AsyncMock,
        return_value=None,
    ):
        svc = DefectRiskService(session, TENANT)
        result = await svc.preview_for_combination(operator_id="op-unknown", phase_id="F01")

    assert result.historical_count == 0
    assert result.confidence == "low"
    assert isinstance(result, QualityRiskPreview)


# ---------------------------------------------------------------------------
# Teste 4 — boat_id deferred (Q.115.A.07) → boat_id=None no response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_boat_id_deferred_none_no_response():
    """boat_id passado no request mas response tem boat_id=None (migration 018 deferred)."""
    session = _make_fake_session()

    with patch.object(
        DefectRiskService, "_historical_stats", new_callable=AsyncMock,
        return_value=(10, []),
    ), patch.object(
        DefectRiskService, "_phase_error_rates", new_callable=AsyncMock,
        return_value={},
    ), patch(
        "src.quality.services.defect_risk_service.ensure_quality_risk_model",
        new_callable=AsyncMock,
    ), patch(
        "src.quality.services.defect_risk_service.load_active_quality_risk_predictor",
        new_callable=AsyncMock,
        return_value=None,
    ):
        svc = DefectRiskService(session, TENANT)
        result = await svc.preview_for_combination(
            operator_id="op-1", phase_id="F01", boat_id="BOAT-007"
        )

    assert result.boat_id is None  # sempre None até migration 018


# ---------------------------------------------------------------------------
# Teste 5 — Cache hit (Redis opcional — sem erro se indisponível)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_hit_skip_redis():
    """2x a mesma query funcionam sem Redis (cache opcional)."""
    session = _make_fake_session()

    with patch.object(
        DefectRiskService, "_historical_stats", new_callable=AsyncMock,
        return_value=(30, []),
    ), patch.object(
        DefectRiskService, "_phase_error_rates", new_callable=AsyncMock,
        return_value={},
    ), patch(
        "src.quality.services.defect_risk_service.ensure_quality_risk_model",
        new_callable=AsyncMock,
    ), patch(
        "src.quality.services.defect_risk_service.load_active_quality_risk_predictor",
        new_callable=AsyncMock,
        return_value=None,
    ):
        svc = DefectRiskService(session, TENANT)
        r1 = await svc.preview_for_combination(operator_id="op-1", phase_id="F01")
        r2 = await svc.preview_for_combination(operator_id="op-1", phase_id="F01")

    assert r1.p_defect == r2.p_defect
    assert r1.historical_count == r2.historical_count


# ---------------------------------------------------------------------------
# Teste 6 — Top-3 similar_pairs ordenados por sample_n DESC
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_similar_pairs_ordenados_sample_n_desc():
    """similar_pairs já vêm ordenados por sample_n DESC (query ORDER BY total DESC)."""
    raw = [("op-A", "F01", 100, 10), ("op-B", "F02", 60, 6), ("op-C", "F03", 20, 2)]
    sp = _pairs(raw)
    session = _make_fake_session()

    with patch.object(
        DefectRiskService, "_historical_stats", new_callable=AsyncMock,
        return_value=(100, sp),
    ), patch.object(
        DefectRiskService, "_phase_error_rates", new_callable=AsyncMock,
        return_value={},
    ), patch(
        "src.quality.services.defect_risk_service.ensure_quality_risk_model",
        new_callable=AsyncMock,
    ), patch(
        "src.quality.services.defect_risk_service.load_active_quality_risk_predictor",
        new_callable=AsyncMock,
        return_value=None,
    ):
        svc = DefectRiskService(session, TENANT)
        result = await svc.preview_for_combination(operator_id="op-A", phase_id="F01")

    assert len(result.similar_pairs) == 3
    sample_ns = [p.sample_n for p in result.similar_pairs]
    assert sample_ns == sorted(sample_ns, reverse=True), "similar_pairs devem estar em DESC"
    assert result.similar_pairs[0].sample_n == 100


# ---------------------------------------------------------------------------
# Teste 7 — Top-3 risk_factors com PT-PT
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_risk_factors_pt_pt():
    """risk_factors têm description_pt em PT-PT e contribution é float."""
    session = _make_fake_session()
    predictor = _mock_predictor(0.4)

    with patch.object(
        DefectRiskService, "_historical_stats", new_callable=AsyncMock,
        return_value=(50, []),
    ), patch.object(
        DefectRiskService, "_phase_error_rates", new_callable=AsyncMock,
        return_value={"F01": 0.15},
    ), patch(
        "src.quality.services.defect_risk_service.ensure_quality_risk_model",
        new_callable=AsyncMock,
    ), patch(
        "src.quality.services.defect_risk_service.load_active_quality_risk_predictor",
        new_callable=AsyncMock,
        return_value=predictor,
    ):
        svc = DefectRiskService(session, TENANT)
        result = await svc.preview_for_combination(operator_id="op-1", phase_id="F01")

    for rf in result.top_risk_factors:
        assert rf.description_pt, "description_pt não deve ser vazio"
        assert isinstance(rf.contribution, float)
        assert rf.feature


# ---------------------------------------------------------------------------
# Teste 8 — Confidence thresholds: 0/19/20/100/101 amostras
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "count,expected_confidence",
    [
        (0, "low"),
        (19, "low"),
        (20, "medium"),
        (100, "medium"),
        (101, "high"),
    ],
)
async def test_confidence_thresholds(count: int, expected_confidence: str):
    """Confidence muda em 20 e 100 amostras (limites inclusive)."""
    session = _make_fake_session()

    with patch.object(
        DefectRiskService, "_historical_stats", new_callable=AsyncMock,
        return_value=(count, []),
    ), patch.object(
        DefectRiskService, "_phase_error_rates", new_callable=AsyncMock,
        return_value={},
    ), patch(
        "src.quality.services.defect_risk_service.ensure_quality_risk_model",
        new_callable=AsyncMock,
    ), patch(
        "src.quality.services.defect_risk_service.load_active_quality_risk_predictor",
        new_callable=AsyncMock,
        return_value=None,
    ):
        svc = DefectRiskService(session, TENANT)
        result = await svc.preview_for_combination(operator_id="op-1", phase_id="F01")

    assert result.confidence == expected_confidence, (
        f"count={count}: esperado {expected_confidence!r}, obtido {result.confidence!r}"
    )
