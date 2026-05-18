"""Q.32.B.1 — histórico de conversa durável.

O Redis (`ConversationStore`) é cache efémero (3 turnos, TTL 30 min).
Quando expira, o `process_ask` ficava sem histórico. Agora há fallback
ao Postgres `copilot_message`, a fonte durável.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.copilot.conversation_store import ConversationStore
from src.copilot.service import CopilotService
from tests.conftest import FakeSession


def _service(session: FakeSession) -> CopilotService:
    return CopilotService(session, uuid4(), uuid4(), "admin_platform")


@pytest.mark.asyncio
async def test_history_uses_redis_when_available(monkeypatch):
    redis_history = [
        {"role": "user", "content": "olá"},
        {"role": "assistant", "content": "viva"},
    ]

    async def _redis_hit(*_a, **_k):
        return redis_history

    monkeypatch.setattr(ConversationStore, "get_history", _redis_hit)
    svc = _service(FakeSession())
    hist = await svc._load_conversation_history(uuid4())
    assert hist == redis_history


@pytest.mark.asyncio
async def test_history_falls_back_to_postgres_when_redis_empty(monkeypatch):
    async def _redis_empty(*_a, **_k):
        return []

    monkeypatch.setattr(ConversationStore, "get_history", _redis_empty)

    session = FakeSession()
    # A query ordena por created_at DESC — devolvemos newest-first; o
    # helper faz .reverse() para repor a ordem cronológica.
    session.queue_scalars([
        SimpleNamespace(actor_role="copilot", content_text="resposta 2"),
        SimpleNamespace(actor_role="user", content_text="pergunta 2"),
        SimpleNamespace(actor_role="copilot", content_text="resposta 1"),
        SimpleNamespace(actor_role="user", content_text="pergunta 1"),
    ])
    svc = _service(session)
    hist = await svc._load_conversation_history(uuid4())

    assert [h["role"] for h in hist] == ["user", "assistant", "user", "assistant"]
    assert [h["content"] for h in hist] == [
        "pergunta 1", "resposta 1", "pergunta 2", "resposta 2",
    ]


@pytest.mark.asyncio
async def test_history_empty_when_redis_down_and_no_rows(monkeypatch):
    async def _redis_boom(*_a, **_k):
        raise ConnectionError("redis down")

    monkeypatch.setattr(ConversationStore, "get_history", _redis_boom)
    svc = _service(FakeSession())  # sem scalars na fila → 0 mensagens
    hist = await svc._load_conversation_history(uuid4())
    assert hist == []
