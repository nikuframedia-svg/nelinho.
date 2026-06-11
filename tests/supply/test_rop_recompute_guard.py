"""Q.172 (F4.E) — guarda anti-abuso do POST /v1/supply/rop-configs/recompute.

Achados de auditoria: o endpoint corria `recompute_rop_configs` (itera todos
os SKUs ativos, queries + upserts) sem rate limiting nem timeout — chamadas
repetidas/paralelas podiam exaurir CPU e o connection pool.

Agora:
* janela deslizante in-process por tenant (10/hora) → 429 com Retry-After;
* `timeout_seconds` (default 300, 10–600) com `asyncio.timeout` → 504,
  cancelado ANTES do commit (nada meio-escrito);
* log INFO com duration_seconds.
"""

from __future__ import annotations

from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session
from src.supply import api as supply_api
from src.supply.api import router as supply_router
from src.supply.routers.rop import (
    _RECOMPUTE_MAX_CALLS,
    _reset_rop_recompute_limiter_for_tests,
)

TENANT = UUID("00000000-0000-0000-0000-000000000001")
_OK = {"rows_processed": 3, "rows_upserted": 2, "rows_skipped": 1}


@pytest.fixture(autouse=True)
def _reset_limiter():
    """Estado do limiter é module-level — limpar antes E depois de cada teste
    para não envenenar os testes de caracterização que partilham o processo."""
    _reset_rop_recompute_limiter_for_tests()
    yield
    _reset_rop_recompute_limiter_for_tests()


async def _stub_session() -> AsyncIterator[Any]:
    sess = AsyncMock()
    yield sess


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(supply_router)
    app.dependency_overrides[get_session] = _stub_session
    app.dependency_overrides[require_tenant_header] = lambda: TENANT
    return TestClient(app, raise_server_exceptions=False)


def test_recompute_dentro_do_limite_responde_200():
    client = _client()
    with patch.object(
        supply_api, "recompute_rop_configs", new=AsyncMock(return_value=_OK),
    ):
        resp = client.post("/v1/supply/rop-configs/recompute")
    assert resp.status_code == 200, resp.text
    assert resp.json() == _OK


def test_recompute_excede_limite_devolve_429_com_retry_after():
    """Chamada N+1 dentro da janela → 429; as N primeiras passam."""
    client = _client()
    with patch.object(
        supply_api, "recompute_rop_configs", new=AsyncMock(return_value=_OK),
    ):
        for i in range(_RECOMPUTE_MAX_CALLS):
            resp = client.post("/v1/supply/rop-configs/recompute")
            assert resp.status_code == 200, f"chamada {i + 1}: {resp.text}"
        resp = client.post("/v1/supply/rop-configs/recompute")
    assert resp.status_code == 429, resp.text
    assert "Retry-After" in resp.headers
    assert int(resp.headers["Retry-After"]) >= 1
    assert "Limite" in resp.json()["detail"]


def test_recompute_429_nao_chama_o_servico():
    """Quando o limite está esgotado, o recompute caro nem sequer arranca."""
    client = _client()
    mock = AsyncMock(return_value=_OK)
    with patch.object(supply_api, "recompute_rop_configs", new=mock):
        for _ in range(_RECOMPUTE_MAX_CALLS):
            client.post("/v1/supply/rop-configs/recompute")
        assert mock.await_count == _RECOMPUTE_MAX_CALLS
        resp = client.post("/v1/supply/rop-configs/recompute")
        assert resp.status_code == 429
        assert mock.await_count == _RECOMPUTE_MAX_CALLS  # não cresceu


def test_recompute_timeout_devolve_504_honesto():
    """TimeoutError no recompute → 504 com mensagem PT-PT, sem commit."""
    client = _client()
    with patch.object(
        supply_api,
        "recompute_rop_configs",
        new=AsyncMock(side_effect=TimeoutError()),
    ):
        resp = client.post(
            "/v1/supply/rop-configs/recompute",
            params={"timeout_seconds": 10},
        )
    assert resp.status_code == 504, resp.text
    assert "timeout" in resp.json()["detail"].lower()
    assert "nenhuma alteração foi gravada" in resp.json()["detail"]


def test_recompute_timeout_seconds_validado():
    """timeout_seconds fora de [10, 600] → 422 (Query bounds)."""
    client = _client()
    resp = client.post(
        "/v1/supply/rop-configs/recompute", params={"timeout_seconds": 5},
    )
    assert resp.status_code == 422
    resp = client.post(
        "/v1/supply/rop-configs/recompute", params={"timeout_seconds": 9999},
    )
    assert resp.status_code == 422


def test_recompute_limite_e_por_tenant():
    """Tenant B não herda o esgotamento do tenant A."""
    tenant_b = UUID("00000000-0000-0000-0000-000000000002")

    def _client_for(tenant: UUID) -> TestClient:
        app = FastAPI()
        app.include_router(supply_router)
        app.dependency_overrides[get_session] = _stub_session
        app.dependency_overrides[require_tenant_header] = lambda: tenant
        return TestClient(app, raise_server_exceptions=False)

    with patch.object(
        supply_api, "recompute_rop_configs", new=AsyncMock(return_value=_OK),
    ):
        client_a = _client_for(TENANT)
        for _ in range(_RECOMPUTE_MAX_CALLS):
            client_a.post("/v1/supply/rop-configs/recompute")
        assert client_a.post("/v1/supply/rop-configs/recompute").status_code == 429

        client_b = _client_for(tenant_b)
        resp = client_b.post("/v1/supply/rop-configs/recompute")
    assert resp.status_code == 200, resp.text
