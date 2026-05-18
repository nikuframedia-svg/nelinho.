"""Q.44.Z — API de configuração da Integração ERP.

Verifica o contrato da página de Integração ERP: o GET devolve a config
sem nunca expor o token em claro (write-only), e o PUT grava via
`TenantConfigService`. Usa `FakeSession` + um app mínimo, sem main.py.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.api.erp_integration import router as erp_router
from src.core.models.tenant_configuration import TenantConfiguration
from src.core.services.tenant_config_service import _reset_cache_for_tests
from src.shared.database import get_session
from tests.conftest import FakeSession, TEST_TENANT_ID


@pytest.fixture(autouse=True)
def _stub_publish(monkeypatch):
    async def fake_publish(_topic, _event):
        return True

    monkeypatch.setattr(
        "src.shared.kafka_client.publish_event", fake_publish, raising=True,
    )


@pytest.fixture(autouse=True)
def _clear_cache():
    _reset_cache_for_tests()


@pytest.fixture
def session_and_client():
    session = FakeSession()

    async def _override_session():
        yield session

    app = FastAPI()
    app.include_router(erp_router)
    app.dependency_overrides[get_session] = _override_session
    return session, TestClient(app)


_HEADERS = {
    "X-Tenant-Id": str(TEST_TENANT_ID),
    "X-User-Id": "00000000-0000-0000-0000-0000000000aa",
}


def _row(key: str, value: Any, data_type: str = "string") -> TenantConfiguration:
    return TenantConfiguration(
        id=uuid4(),
        tenant_id=TEST_TENANT_ID,
        category="system",
        key=key,
        value=TenantConfiguration.wrap(value),
        data_type=data_type,
        valid_from=datetime.utcnow(),
        valid_to=None,
        created_at=datetime.utcnow(),
        last_modified_at=datetime.utcnow(),
    )


def test_get_returns_defaults_when_unset(session_and_client):
    """Sem config gravada, o GET devolve os defaults seguros."""
    session, client = session_and_client
    session.queue_scalars([])
    resp = client.get("/v1/erp-integration", headers=_HEADERS)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["api_url"] is None
    assert body["token_set"] is False
    assert body["realtime_enabled"] is False
    assert body["write_enabled"] is False
    assert body["realtime_interval_minutes"] == 5


def test_get_never_returns_token_in_clear(session_and_client):
    """O token é write-only: o GET só diz que está definido + 4 dígitos."""
    session, client = session_and_client
    session.queue_scalars([
        _row("erp.api_url", "https://erp.nelo.eu/api"),
        _row("erp.api_token", "tok_SUPER_SECRET_wxyz9876"),
    ])
    resp = client.get("/v1/erp-integration", headers=_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_set"] is True
    assert body["token_hint"] == "…9876"
    # O token em claro NUNCA pode aparecer na resposta.
    assert "tok_SUPER_SECRET_wxyz9876" not in resp.text
    assert "SUPER_SECRET" not in resp.text


def test_get_requires_tenant_header(session_and_client):
    _, client = session_and_client
    resp = client.get("/v1/erp-integration")
    assert resp.status_code == 401


def test_put_writes_config_via_service(session_and_client):
    """O PUT grava as chaves `erp.*` e comita."""
    session, client = session_and_client
    # 1 campo → 1 set() → 1 _current_row (scalar). A leitura final
    # (get_category) consome o 2º slot de scalars.
    session.queue_scalar(None)            # _current_row: sem versão anterior
    session.queue_scalars([])             # consumido pelo execute do _current_row
    session.queue_scalars([              # leitura final reflecte o gravado
        _row("erp.realtime_interval_minutes", 10, data_type="int"),
    ])
    resp = client.put(
        "/v1/erp-integration",
        headers=_HEADERS,
        json={"realtime_interval_minutes": 10},
    )
    assert resp.status_code == 200, resp.text
    # Gravou uma linha de config nova e comitou.
    assert any(
        getattr(r, "key", None) == "erp.realtime_interval_minutes"
        for r in session.added
    )
    assert session.commit_calls >= 1


def test_put_omitting_token_does_not_write_it(session_and_client):
    """Um PUT sem `api_token` não escreve a chave do token."""
    session, client = session_and_client
    session.queue_scalar(None)
    session.queue_scalars([])
    session.queue_scalars([_row("erp.api_url", "https://x")])
    resp = client.put(
        "/v1/erp-integration",
        headers=_HEADERS,
        json={"api_url": "https://x"},
    )
    assert resp.status_code == 200, resp.text
    assert not any(
        getattr(r, "key", None) == "erp.api_token" for r in session.added
    )
