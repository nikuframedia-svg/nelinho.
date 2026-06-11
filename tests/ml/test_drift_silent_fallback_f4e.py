"""
F4.E — GET /v1/ml/drift deixa de mascarar falhas de BD em silêncio.

O contrato mantém-se (lista vazia → o painel mostra "sem drift" em vez de
rebentar), mas a falha passa a ser observável: o except agora incrementa
``prodplan_silent_fallback_total{module="ml_drift", reason="query_failed"}``
(padrão Q.170.G). Antes deste fix o contador não mexia — falha invisível.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.ml.api import router as ml_router
from src.shared.database import get_session
from src.shared.metrics import silent_fallback_total
from tests.conftest import TEST_TENANT_ID, FakeSession

_HEADERS = {"X-Tenant-Id": str(TEST_TENANT_ID)}


class _FailingSession(FakeSession):
    async def execute(self, stmt: Any, *args: Any, **kwargs: Any):
        raise RuntimeError("BD em baixo (simulado)")


def _fallback_count() -> float:
    for metric in silent_fallback_total.collect():
        for sample in metric.samples:
            if (
                sample.name.endswith("_total")
                and sample.labels.get("module") == "ml_drift"
                and sample.labels.get("reason") == "query_failed"
            ):
                return sample.value
    return 0.0


@pytest.fixture
def client():
    session = _FailingSession()

    async def _override():
        yield session

    app = FastAPI()
    app.include_router(ml_router)
    app.dependency_overrides[get_session] = _override
    return TestClient(app)


def test_drift_db_failure_returns_empty_and_bumps_metric(client):
    before = _fallback_count()

    resp = client.get(
        "/v1/ml/drift",
        params={"model_name": "duration", "since": "7d"},
        headers=_HEADERS,
    )

    # Contrato preservado: 200 + lista vazia (estado-vazio explícito).
    assert resp.status_code == 200, resp.text
    assert resp.json() == []

    # Mas a falha já não é silenciosa — métrica incrementada.
    assert _fallback_count() == before + 1
