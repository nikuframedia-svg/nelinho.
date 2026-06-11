"""Q.172 (F4.E) — GET /v1/quality/first-pass-yield com estado-vazio honesto.

Achado de auditoria: sem ordens concluídas na janela o endpoint devolvia
`{..., first_pass_yield_pct: 0.0}` — indistinguível de um FPY real de 0%.
Invariante #8 (dados honestos): o estado-vazio leva `reason="NO_SOURCE_DATA"`,
mesmo padrão de src/profit/api/kpis.py. Com dados, `reason` NÃO aparece.

Mock no contrato do serviço (DashboardMetricsService.first_pass_yield) —
o fix vive na camada API de src/quality, não no serviço de profit.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.profit.services.dashboard_metrics_service import FPYResult
from src.quality.api import router as quality_router
from src.shared.database import get_session
from tests.conftest import TEST_TENANT_ID, FakeSession

_HEADERS = {"X-Tenant-Id": str(TEST_TENANT_ID)}


def _client(session: FakeSession) -> TestClient:
    async def _override():
        yield session

    app = FastAPI()
    app.include_router(quality_router)
    app.dependency_overrides[get_session] = _override
    return TestClient(app)


def test_fpy_sem_dados_marca_reason_no_source_data():
    """orders_total=0 → 200 com reason=NO_SOURCE_DATA (não 404, não 0% mudo)."""
    empty = FPYResult(
        window_days=30,
        orders_total=0,
        orders_with_rework=0,
        first_pass_yield_pct=0.0,
    )
    with patch(
        "src.profit.services.dashboard_metrics_service."
        "DashboardMetricsService.first_pass_yield",
        new=AsyncMock(return_value=empty),
    ):
        resp = _client(FakeSession()).get(
            "/v1/quality/first-pass-yield", headers=_HEADERS,
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["reason"] == "NO_SOURCE_DATA"
    assert body["orders_total"] == 0
    assert body["first_pass_yield_pct"] == 0.0


def test_fpy_com_dados_nao_tem_reason():
    """Com ordens na janela, o payload mantém o contrato sem `reason`."""
    real = FPYResult(
        window_days=30,
        orders_total=10,
        orders_with_rework=2,
        first_pass_yield_pct=80.0,
    )
    with patch(
        "src.profit.services.dashboard_metrics_service."
        "DashboardMetricsService.first_pass_yield",
        new=AsyncMock(return_value=real),
    ):
        resp = _client(FakeSession()).get(
            "/v1/quality/first-pass-yield", headers=_HEADERS,
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "reason" not in body
    assert body["first_pass_yield_pct"] == 80.0


def test_fpy_zero_pct_real_distingue_se_de_sem_dados():
    """FPY=0% REAL (todas as ordens com retrabalho) NÃO leva reason —
    é um zero medido, não um vazio."""
    all_rework = FPYResult(
        window_days=30,
        orders_total=5,
        orders_with_rework=5,
        first_pass_yield_pct=0.0,
    )
    with patch(
        "src.profit.services.dashboard_metrics_service."
        "DashboardMetricsService.first_pass_yield",
        new=AsyncMock(return_value=all_rework),
    ):
        resp = _client(FakeSession()).get(
            "/v1/quality/first-pass-yield", headers=_HEADERS,
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "reason" not in body
    assert body["first_pass_yield_pct"] == 0.0
