"""
F4.E — /pricing: 404 honesto + validação do PriceSimulationRequest.

Antes deste fix:

* POST /pricing/recommend e /pricing/simulate com ``order_id`` sem COGS
  deixavam o ``ValueError`` do serviço subir → 500 via
  global_exception_handler (devia ser 404, padrão de cogs.py);
* ``PriceSimulationRequest`` aceitava ``prices=[]`` (simulação vazia
  silenciosa) e ``quantity`` tinha tipagem ambígua ``int = None``.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.profit.api.pricing import router as pricing_router
from src.shared.database import get_session
from tests.conftest import TEST_TENANT_ID, FakeSession

_HEADERS = {"X-Tenant-Id": str(TEST_TENANT_ID)}


@pytest.fixture
def client_and_session():
    session = FakeSession()

    async def _override():
        yield session

    app = FastAPI()
    app.include_router(pricing_router)
    app.dependency_overrides[get_session] = _override
    return TestClient(app), session


def test_recommend_unknown_order_returns_404(client_and_session):
    client, session = client_and_session
    session.queue_scalar(None)  # latest COGS → não existe

    resp = client.post(
        "/pricing/recommend",
        json={"order_id": f"OF-{uuid4().hex[:8]}"},
        headers=_HEADERS,
    )
    assert resp.status_code == 404, resp.text
    assert "No COGS calculation" in resp.json()["detail"]


def test_simulate_unknown_order_returns_404(client_and_session):
    client, session = client_and_session
    session.queue_scalar(None)

    resp = client.post(
        "/pricing/simulate",
        json={"order_id": "OF-INEXISTENTE", "prices": ["100.00"]},
        headers=_HEADERS,
    )
    assert resp.status_code == 404, resp.text


def test_simulate_empty_prices_rejected_422(client_and_session):
    client, _ = client_and_session
    resp = client.post(
        "/pricing/simulate",
        json={"order_id": "OF-1", "prices": []},
        headers=_HEADERS,
    )
    assert resp.status_code == 422


def test_simulate_quantity_zero_rejected_422(client_and_session):
    client, _ = client_and_session
    resp = client.post(
        "/pricing/simulate",
        json={"order_id": "OF-1", "prices": ["100.00"], "quantity": 0},
        headers=_HEADERS,
    )
    assert resp.status_code == 422


def test_simulate_quantity_omitted_is_allowed(client_and_session):
    # quantity=None → fallback à quantidade do COGS na BD; aqui o COGS não
    # existe, por isso o caminho válido de payload termina em 404 (não 422).
    client, session = client_and_session
    session.queue_scalar(None)
    resp = client.post(
        "/pricing/simulate",
        json={"order_id": "OF-1", "prices": ["100.00"]},
        headers=_HEADERS,
    )
    assert resp.status_code == 404
