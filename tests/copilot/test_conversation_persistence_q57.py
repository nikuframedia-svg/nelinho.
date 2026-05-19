"""Q.57 — persistência e memória das conversas do COPILOT.

Dois bugs de ligação no `src/copilot/api.py`:

1. `send_message` recebia o `conversation_id` no path mas nunca o
   injectava no `CopilotAskRequest` — o `process_ask` lia
   `request.conversation_id` para activar o `ConversationStore` (memória
   multi-turno em Redis), por isso o LLM ficava sempre sem memória.
2. `create_conversation` fazia `flush()` mas não `commit()`. O
   `get_session` só auto-commita se `session.new/dirty/deleted` tiverem
   conteúdo no fim do request, e `flush()` esvazia `session.new` — a
   conversa era inserida e logo rollbacked.

Estes testes chamam os handlers directamente com uma sessão falsa.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

from src.copilot.api import create_conversation, send_message
from src.copilot.models import CopilotConversation, CopilotMessage
from src.copilot.schemas import CopilotAskRequest, CopilotResponse

_TENANT = UUID("11111111-1111-1111-1111-111111111111")
_ACTOR = UUID("22222222-2222-2222-2222-222222222222")
_CONVERSATION = UUID("33333333-3333-3333-3333-333333333333")


class _User:
    """Stand-in mínimo do `UserContext` (só `user_id` + `role`)."""

    user_id = _ACTOR
    role = "ADMIN"


class _Conv:
    """Stand-in da `CopilotConversation` devolvida por `session.get`."""

    def __init__(self, tenant_id: UUID, actor_id: UUID) -> None:
        self.tenant_id = tenant_id
        self.actor_id = actor_id
        self.last_message_at = None


def _response() -> CopilotResponse:
    """Resposta válida mínima — mesmos campos do caminho de erro da API."""
    return CopilotResponse(
        suggestion_id=uuid4(),
        correlation_id=uuid4(),
        type="ERROR",
        intent="generic",
        summary="ok",
        facts=[],
        actions=[],
        warnings=[],
        meta={"validation_passed": True},
    )


# ───────────────────────────────────────────────────────────────────────────
# create_conversation — tem de fazer commit
# ───────────────────────────────────────────────────────────────────────────


class _CreateSession:
    """Sessão falsa: capta `add` e regista se `commit` foi chamado."""

    def __init__(self) -> None:
        self.staged: list[Any] = []
        self.committed = False

    def add(self, instance: Any) -> None:
        self.staged.append(instance)

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, instance: Any) -> None:
        # Simula o que a BD preenche: id + created_at.
        if getattr(instance, "id", None) is None:
            instance.id = uuid4()
        if getattr(instance, "created_at", None) is None:
            instance.created_at = datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_create_conversation_commits_the_row():
    session = _CreateSession()
    result = await create_conversation(
        user=_User(),  # type: ignore[arg-type]
        tenant_id=_TENANT,
        session=session,  # type: ignore[arg-type]
        title="K1 — afinação de cura",
    )
    # Sem o commit explícito, a conversa nunca chegava à BD.
    assert session.committed is True
    assert len(session.staged) == 1
    assert isinstance(session.staged[0], CopilotConversation)
    assert result["title"] == "K1 — afinação de cura"
    UUID(result["id"])  # id parseável


# ───────────────────────────────────────────────────────────────────────────
# send_message — tem de injectar o conversation_id no request
# ───────────────────────────────────────────────────────────────────────────


class _SendSession:
    """Sessão falsa para `send_message`: get/add/flush/commit."""

    def __init__(self, conversation: Any) -> None:
        self._conversation = conversation
        self.staged: list[Any] = []
        self.flushed = False
        self.committed = False

    async def get(self, _model: Any, _pk: Any) -> Any:
        return self._conversation

    def add(self, instance: Any) -> None:
        self.staged.append(instance)

    async def flush(self) -> None:
        self.flushed = True

    async def commit(self) -> None:
        self.committed = True


@pytest.mark.asyncio
async def test_send_message_injects_conversation_id_into_process_ask():
    """O `process_ask` só usa a memória multi-turno se o request tiver
    `conversation_id`. O handler tem de o copiar do path."""
    session = _SendSession(_Conv(_TENANT, _ACTOR))
    request = CopilotAskRequest(user_query="e o molde 70907?", conversation_id=None)

    captured: dict[str, Any] = {}

    class _FakeService:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        async def process_ask(self, req: CopilotAskRequest):
            captured["request"] = req
            return _response(), {"latency_ms": 5, "model": "gemma"}

    with patch("src.copilot.api.CopilotService", _FakeService):
        resp = await send_message(
            conversation_id=_CONVERSATION,
            request=request,
            user=_User(),  # type: ignore[arg-type]
            tenant_id=_TENANT,
            session=session,  # type: ignore[arg-type]
        )

    # O request que chegou ao serviço carrega o id da conversa do path.
    assert captured["request"].conversation_id == _CONVERSATION
    assert isinstance(resp, CopilotResponse)
    # Mensagem do utilizador + resposta do copiloto persistidas.
    assert sum(isinstance(s, CopilotMessage) for s in session.staged) == 2
    assert session.committed is True
    # last_message_at actualizado.
    assert session._conversation.last_message_at is not None


@pytest.mark.asyncio
async def test_send_message_404_when_conversation_missing():
    from fastapi import HTTPException

    session = _SendSession(None)  # session.get → None
    request = CopilotAskRequest(user_query="olá", conversation_id=None)

    with pytest.raises(HTTPException) as exc_info:
        await send_message(
            conversation_id=_CONVERSATION,
            request=request,
            user=_User(),  # type: ignore[arg-type]
            tenant_id=_TENANT,
            session=session,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_send_message_404_when_conversation_belongs_to_other_tenant():
    from fastapi import HTTPException

    other_tenant = UUID("99999999-9999-9999-9999-999999999999")
    session = _SendSession(_Conv(other_tenant, _ACTOR))
    request = CopilotAskRequest(user_query="olá", conversation_id=None)

    with pytest.raises(HTTPException) as exc_info:
        await send_message(
            conversation_id=_CONVERSATION,
            request=request,
            user=_User(),  # type: ignore[arg-type]
            tenant_id=_TENANT,
            session=session,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 404
