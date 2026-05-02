"""Sprint Q.9 (3.1) — OllamaClient.chat_with_fallback.

Convenience wrapper that never raises. API hot paths use it so a
circuit-breaker-open or Ollama-down condition returns a graceful
``{"ok": False, "code": "MODEL_OFFLINE", ...}`` instead of a 500.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from src.copilot.ollama_client import OllamaClient


@pytest.mark.asyncio
async def test_chat_with_fallback_returns_ok_on_success():
    client = OllamaClient()
    with patch.object(client, "chat", AsyncMock(return_value={"foo": "bar"})):
        out = await client.chat_with_fallback("hi", "model")
    assert out["ok"] is True
    assert out["foo"] == "bar"


@pytest.mark.asyncio
async def test_chat_with_fallback_swallows_exception():
    client = OllamaClient()
    with patch.object(client, "chat", AsyncMock(side_effect=Exception("boom"))):
        out = await client.chat_with_fallback("hi", "model")
    assert out["ok"] is False
    assert out["error"] == "boom"
    assert out["code"] == "MODEL_OFFLINE"


@pytest.mark.asyncio
async def test_chat_with_fallback_uses_custom_fallback():
    client = OllamaClient()
    custom = {"code": "DEGRADED", "message": "use cache"}
    with patch.object(client, "chat", AsyncMock(side_effect=Exception("kaboom"))):
        out = await client.chat_with_fallback(
            "hi", "model", fallback=custom,
        )
    assert out["ok"] is False
    assert out["code"] == "DEGRADED"
    assert out["message"] == "use cache"


@pytest.mark.asyncio
async def test_chat_with_fallback_handles_open_circuit_breaker():
    """Open circuit breaker → ``chat`` raises → wrapper returns
    MODEL_OFFLINE without re-raising."""
    client = OllamaClient()
    client._failure_count = 5
    client._circuit_open_until = datetime.utcnow() + timedelta(seconds=60)
    out = await client.chat_with_fallback("hi", "model")
    assert out["ok"] is False
    assert out["code"] == "MODEL_OFFLINE"
