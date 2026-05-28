"""Q.115.V — testes do job plan-vs-actual + endpoint + feature plan_error_prior.

8 cenários conforme DoD:
1. Job sem dados (FasesOf vazia) → PlanVsActualReport(sample_size=0)
2. Job com 50 ops → plan_accuracy_pct ∈ [0, 100], deltas calculados
3. delta_duration negativo quando actual < planned (operadores rápidos)
4. delta_duration positivo quando actual > planned (delays)
5. Plan accuracy 100% quando actual == planned
6. Endpoint GET /v1/learning/plan-vs-actual?days=7 → 200 + estrutura coerente
7. Endpoint sem dados → 200 + sample_size=0, listas vazias
8. DurationModel extract_features inclui plan_error_prior; fallback 0 quando vazio
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from src.scheduling.jobs.plan_vs_actual import (
    DeltaByModel,
    DeltaByPhase,
    PlanVsActualReport,
    _compute_report,
)

TEST_TENANT = UUID("22222222-2222-2222-2222-222222222222")


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _row(
    phase_id: str = "INJECAO",
    modelo_id: str = "VIPER",
    planned_min: float = 60.0,
    observed_min: float = 70.0,
    delta_quality: float | None = None,
) -> Dict[str, Any]:
    return {
        "phase_id": phase_id,
        "phase_name": phase_id,
        "modelo_id": modelo_id,
        "planned_duration_min": planned_min,
        "observed_duration_min": observed_min,
        "delta_quality": delta_quality,
    }


# ─── 1. Job sem dados → sample_size=0 ────────────────────────────────────────


def test_compute_report_sem_dados_devolve_vazio():
    """Sem rows, _compute_report devolve sample_size=0 e listas vazias."""
    report = _compute_report(TEST_TENANT, days=7, rows=[])
    assert isinstance(report, PlanVsActualReport)
    assert report.sample_size == 0
    assert report.plan_accuracy_pct == 0.0
    assert report.deltas_by_phase == []
    assert report.deltas_by_model == []
    assert report.tenant_id == TEST_TENANT
    assert report.days == 7


# ─── 2. Job com 50 ops → deltas calculados + accuracy ∈ [0, 100] ─────────────


def test_compute_report_50_ops():
    """50 linhas sintéticas → plan_accuracy_pct ∈ [0, 100], listas preenchidas."""
    rows = []
    for i in range(50):
        planned = 60.0
        observed = 60.0 + (i % 10) * 3.0  # variação 0..27 min
        rows.append(_row(
            phase_id=f"FASE_{i % 5}",
            modelo_id=f"MODELO_{i % 3}",
            planned_min=planned,
            observed_min=observed,
        ))

    report = _compute_report(TEST_TENANT, days=7, rows=rows)

    assert report.sample_size == 50
    assert 0.0 <= report.plan_accuracy_pct <= 100.0
    assert len(report.deltas_by_phase) == 5  # 5 fases distintas
    assert len(report.deltas_by_model) == 3  # 3 modelos distintos
    # Todas as fases têm sample_n > 0
    for d in report.deltas_by_phase:
        assert d.sample_n > 0
        assert isinstance(d.avg_delta_duration_min, float)


# ─── 3. delta negativo quando actual < planned ────────────────────────────────


def test_delta_negativo_operadores_rapidos():
    """Quando observed < planned, delta_duration deve ser negativo."""
    rows = [_row(planned_min=100.0, observed_min=80.0)]
    report = _compute_report(TEST_TENANT, days=7, rows=rows)
    assert report.sample_size == 1
    assert report.deltas_by_phase[0].avg_delta_duration_min < 0
    assert report.deltas_by_model[0].avg_delta_duration_min < 0
    # Valor exacto: 80 - 100 = -20
    assert abs(report.deltas_by_phase[0].avg_delta_duration_min - (-20.0)) < 1e-9


# ─── 4. delta positivo quando actual > planned ────────────────────────────────


def test_delta_positivo_delays():
    """Quando observed > planned, delta_duration deve ser positivo."""
    rows = [_row(planned_min=60.0, observed_min=90.0)]
    report = _compute_report(TEST_TENANT, days=7, rows=rows)
    assert report.sample_size == 1
    assert report.deltas_by_phase[0].avg_delta_duration_min > 0
    # 90 - 60 = 30
    assert abs(report.deltas_by_phase[0].avg_delta_duration_min - 30.0) < 1e-9


# ─── 5. Plan accuracy 100% quando actual == planned ───────────────────────────


def test_plan_accuracy_100_pct_quando_perfeito():
    """actual == planned → plan_accuracy_pct deve ser 100.0."""
    rows = [_row(planned_min=60.0, observed_min=60.0) for _ in range(10)]
    report = _compute_report(TEST_TENANT, days=7, rows=rows)
    assert report.sample_size == 10
    assert abs(report.plan_accuracy_pct - 100.0) < 1e-6
    for d in report.deltas_by_phase:
        assert abs(d.avg_delta_duration_min) < 1e-9


# ─── 6. Endpoint GET /v1/learning/plan-vs-actual → 200 + estrutura ───────────


def _build_test_app(obs_rows: List[Any]):
    """Cria app mínima com FakeSession para testar o endpoint plan-vs-actual."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.learning.api_plan_vs_actual import router as pva_router
    from src.shared.auth.headers import require_tenant_header
    from src.shared.database import get_session

    class _FakeResult:
        def __init__(self, rows):
            self._rows = rows

        def scalars(self):
            return self

        def all(self):
            return self._rows

    async def _fake_session():
        class _Sess:
            async def execute(self, stmt):
                return _FakeResult(obs_rows)

        yield _Sess()

    app = FastAPI()
    app.include_router(pva_router)
    app.dependency_overrides[get_session] = _fake_session
    app.dependency_overrides[require_tenant_header] = lambda: TEST_TENANT
    return TestClient(app, raise_server_exceptions=True)


def _obs_row(
    phase_id: str = "INJECAO",
    modelo: str = "VIPER",
    planned: float = 60.0,
    observed: float = 70.0,
) -> SimpleNamespace:
    return SimpleNamespace(
        phase_id=phase_id,
        modelo=modelo,
        planned_duration_min=planned,
        observed_duration_min=observed,
        captured_at=datetime.now(timezone.utc),
        tenant_id=TEST_TENANT,
    )


def test_endpoint_plan_vs_actual_200():
    """GET /v1/learning/plan-vs-actual?days=7 → 200 + estrutura coerente."""
    obs = [_obs_row() for _ in range(5)]
    client = _build_test_app(obs)
    resp = client.get(
        "/v1/learning/plan-vs-actual?days=7",
        headers={"X-Tenant-Id": str(TEST_TENANT)},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["sample_size"] == 5
    assert 0.0 <= data["plan_accuracy_pct"] <= 100.0
    assert isinstance(data["deltas_by_phase"], list)
    assert isinstance(data["deltas_by_model"], list)
    assert data["days"] == 7


# ─── 7. Endpoint sem dados → 200 + sample_size=0 ─────────────────────────────


def test_endpoint_sem_dados_200_vazio():
    """GET /v1/learning/plan-vs-actual sem dados → 200, sample_size=0."""
    client = _build_test_app(obs_rows=[])
    resp = client.get(
        "/v1/learning/plan-vs-actual?days=7",
        headers={"X-Tenant-Id": str(TEST_TENANT)},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["sample_size"] == 0
    assert data["deltas_by_phase"] == []
    assert data["deltas_by_model"] == []


# ─── 8. DurationModel extract_features inclui plan_error_prior ───────────────


def test_duration_model_plan_error_prior_incluido():
    """build_training_dataset inclui plan_error_prior com valor do prior."""
    from src.ml.models_domain.duration import build_training_dataset

    # Fase + ordem sintética
    phase = SimpleNamespace(
        of_id="OF001",
        fase_id="INJECAO",
        horas_reais=1.5,
        team_size=2,
        molde_id="M001",
        data_fim_real=None,
        data_inicio_real=None,
        created_at=None,
    )
    order = SimpleNamespace(of_id="OF001", modelo_id="VIPER")

    class _FakeSQ:
        engine = SimpleNamespace(
            _active_ingestion_id="run1",
            _curated_data={
                "run1": {
                    "order_phases": [phase],
                    "orders": [order],
                    "quality_events": [],
                    "molds": [],
                }
            },
        )

    priors = {"VIPER::INJECAO": 5.0}  # 5 min de erro histórico
    rows = build_training_dataset(_FakeSQ(), plan_error_priors=priors)

    assert len(rows) == 1
    assert rows[0]["plan_error_prior"] == 5.0


def test_duration_model_plan_error_prior_fallback_zero():
    """build_training_dataset usa 0.0 quando priors=None."""
    from src.ml.models_domain.duration import build_training_dataset

    phase = SimpleNamespace(
        of_id="OF002",
        fase_id="DESMOLDAGEM",
        horas_reais=2.0,
        team_size=1,
        molde_id="M002",
        data_fim_real=None,
        data_inicio_real=None,
        created_at=None,
    )
    order = SimpleNamespace(of_id="OF002", modelo_id="VIPER")

    class _FakeSQ:
        engine = SimpleNamespace(
            _active_ingestion_id="run1",
            _curated_data={
                "run1": {
                    "order_phases": [phase],
                    "orders": [order],
                    "quality_events": [],
                    "molds": [],
                }
            },
        )

    rows = build_training_dataset(_FakeSQ(), plan_error_priors=None)
    assert len(rows) == 1
    assert rows[0]["plan_error_prior"] == 0.0
