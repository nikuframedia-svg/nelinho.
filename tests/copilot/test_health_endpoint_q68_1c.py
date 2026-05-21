"""Q.68.1.C — `/api/copilot/health` security hardening.

Auditoria C3 destapou que `GET /api/copilot/health` expunha:
    * `ollama_base_url` (URL interno do Ollama)
    * `ollama_model` (modelo em produção)
    * `rate_limit.per_hour/per_day` (config sensível)

…sem qualquer autenticação. Atacante anónimo conseguia mapear infra
interna por uma única chamada HTTP. Q.68.1.C fecha o buraco:

    1. Endpoint exige `Depends(get_current_user)` — 401/403 sem JWT.
    2. Response sanitizada — só `status / subsystems / circuit_breaker /
       timestamp`. Nunca URLs nem nome de modelo nem rate-limit.

Estes tests servem de regressão. Se algum falhar no futuro, está-se a
re-introduzir leak ou a quebrar a contratualização da resposta.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.copilot import api as copilot_api
from src.copilot.api import copilot_health
from src.copilot.routers.health import router as health_router
from src.shared.auth.jwt_handler import UserContext, create_access_token


_TENANT = UUID("00000000-0000-0000-0000-00000000aaaa")
_USER = UUID("00000000-0000-0000-0000-00000000bbbb")


def _make_app() -> FastAPI:
    """Standalone FastAPI app só com o sub-router de health."""
    app = FastAPI()
    app.include_router(health_router, prefix="/api/copilot")
    return app


def _fake_ollama_client(online: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        _circuit_open_until=None,
        _failure_count=0,
        base_url="http://internal-ollama-host:11434",  # secret-ish URL
        reset_circuit_breaker=lambda: None,
        health_check=AsyncMock(return_value=online),
    )


# ──────────────────────────────────────────────────────────────────────────
# 1. Auth obrigatória — sem JWT → 401/403
# ──────────────────────────────────────────────────────────────────────────


def test_health_without_auth_returns_401():
    """GET /api/copilot/health SEM Authorization header → 401 ou 403.

    NÃO deve devolver 200, NÃO deve devolver shape do payload, NÃO
    deve mencionar `ollama_base_url`, `ollama_model`, nem rate limit.
    """
    app = _make_app()
    client = TestClient(app)

    # Mesmo se o cliente Ollama existir, o auth dependency deve bloquear
    # ANTES de qualquer chamada ao subsistema.
    with patch.object(copilot_api, "get_ollama_client",
                      return_value=_fake_ollama_client(online=True)):
        response = client.get("/api/copilot/health")

    assert response.status_code in (401, 403), (
        f"esperado 401/403 (auth required) mas veio {response.status_code} "
        f"body={response.text!r} — security leak"
    )
    # Defesa em profundidade: corpo não deve conter URLs internos
    body_lower = response.text.lower()
    assert "internal-ollama-host" not in body_lower
    assert "11434" not in body_lower
    assert "gemma" not in body_lower
    assert "rate_limit" not in body_lower


# ──────────────────────────────────────────────────────────────────────────
# 2. Auth válida → 200 + shape sanitizada
# ──────────────────────────────────────────────────────────────────────────


def test_health_with_auth_returns_sanitized_shape():
    """GET /api/copilot/health com JWT válido → 200 + shape mínima."""
    app = _make_app()
    client = TestClient(app)
    token = create_access_token(_USER, _TENANT, "manager_operations")

    with patch.object(copilot_api, "get_ollama_client",
                      return_value=_fake_ollama_client(online=True)):
        response = client.get(
            "/api/copilot/health",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200, response.text
    body = response.json()

    # Shape esperada (Q.68.1.C)
    assert set(body.keys()) == {
        "status", "subsystems", "circuit_breaker", "timestamp",
    }, f"shape inesperada — keys={sorted(body.keys())}"

    assert body["status"] in ("ok", "degraded", "down")
    assert body["circuit_breaker"] in ("closed", "open", "half_open", "unknown")
    assert isinstance(body["subsystems"], dict)
    assert body["subsystems"].get("ollama") in ("up", "down")
    assert isinstance(body["timestamp"], str) and body["timestamp"]


# ──────────────────────────────────────────────────────────────────────────
# 3. Response NÃO contém URLs internos nem nome de modelo nem rate limits
# ──────────────────────────────────────────────────────────────────────────


def test_health_response_does_not_leak_infra_secrets():
    """Garante que NENHUM campo sensível volta para o cliente, mesmo
    autenticado. Q.68.1.C: o role do user não importa — health é
    diagnostic mas não pode mapear infra.
    """
    app = _make_app()
    client = TestClient(app)
    token = create_access_token(_USER, _TENANT, "manager_operations")

    fake_client = _fake_ollama_client(online=True)
    with patch.object(copilot_api, "get_ollama_client", return_value=fake_client):
        response = client.get(
            "/api/copilot/health",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    raw = json.dumps(body).lower()

    # Forbidden leaks
    assert "ollama_base_url" not in body
    assert "ollama_model" not in body
    assert "rate_limit" not in body
    assert "embeddings_model" not in body
    assert "base_url" not in body
    assert "model" not in body

    # Defesa-em-profundidade: substrings sensíveis
    assert "internal-ollama-host" not in raw, "URL Ollama vazou no payload"
    assert "11434" not in raw, "porta Ollama vazou no payload"
    assert "gemma" not in raw, "nome do modelo vazou no payload"
    assert "per_hour" not in raw
    assert "per_day" not in raw


# ──────────────────────────────────────────────────────────────────────────
# 4. Direct-call (sem TestClient) — degradação não vaza secrets
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health_degraded_when_ollama_offline_still_sanitized():
    """Mesmo no path `degraded` (Ollama offline), shape continua mínima."""
    fake_user = UserContext(
        user_id=_USER,
        tenant_id=_TENANT,
        role="manager_operations",
    )
    fake_client = _fake_ollama_client(online=False)

    with patch.object(copilot_api, "get_ollama_client", return_value=fake_client):
        result = await copilot_health(_user=fake_user)

    assert result["status"] == "degraded"
    assert result["subsystems"]["ollama"] == "down"
    # ainda assim NÃO expõe nada interno
    assert "ollama_base_url" not in result
    assert "ollama_model" not in result
    assert "rate_limit" not in result


@pytest.mark.asyncio
async def test_health_exception_path_returns_sanitized_down():
    """Se `get_ollama_client` rebenta, devolve shape `down` mas sem
    propagar a exception string para o cliente — `error` field foi
    REMOVIDO no Q.68.1.C (era um vector de leak de stack trace)."""
    fake_user = UserContext(
        user_id=_USER,
        tenant_id=_TENANT,
        role="manager_operations",
    )

    def boom():
        raise RuntimeError("internal-ollama-host:11434 connection refused")

    with patch.object(copilot_api, "get_ollama_client", side_effect=boom):
        result = await copilot_health(_user=fake_user)

    assert result["status"] == "down"
    assert result["subsystems"]["ollama"] == "down"
    assert "error" not in result, "stack trace / mensagem de excepção vazou"
    assert "internal-ollama-host" not in json.dumps(result).lower()
