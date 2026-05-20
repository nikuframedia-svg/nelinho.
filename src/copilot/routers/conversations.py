"""Q.66.D.4a — sub-router: conversations CRUD.

Container de chat multi-turno (CopilotConversation + CopilotMessage).
O `send_message` injecta `conversation_id` no request antes do
`process_ask` para que o `ConversationStore` (Redis, últimos 3 turnos)
tenha memória entre turns.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.copilot import api as _api  # late attribute access — vê monkey-patches
from src.copilot.models import CopilotConversation, CopilotMessage
from src.copilot.schemas import CopilotAskRequest
from src.shared.auth.jwt_handler import UserContext, get_current_user
from src.shared.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/conversations", status_code=status.HTTP_201_CREATED)
async def create_conversation(
    user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(_api.get_tenant_id),
    session: AsyncSession = Depends(get_session),
    title: Optional[str] = Body(None),
):
    """Criar nova conversa."""
    conversation = CopilotConversation(
        tenant_id=tenant_id,
        actor_id=user.user_id,
        title=title or "Nova conversa",
    )
    # Q.66.B.3: conversa do copiloto (chat container), nao state de
    # governance. Mensagens vivem em copilot.message com correlation_id.
    session.add(conversation)  # noqa: audit_coverage  # copilot chat container, not gov state
    # Commit explícito: `get_session` só auto-commita se `session.new/dirty/
    # deleted` tiverem conteúdo no fim do request — e `flush()` esvazia
    # `session.new`. Sem este commit a conversa era inserida e logo
    # rollbacked ao fechar a sessão (id devolvido, linha inexistente).
    await session.commit()
    await session.refresh(conversation)

    return {
        "id": str(conversation.id),
        "title": conversation.title,
        "created_at": conversation.created_at.isoformat(),
    }


@router.get("/conversations", status_code=status.HTTP_200_OK)
async def list_conversations(
    user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(_api.get_tenant_id),
    session: AsyncSession = Depends(get_session),
    limit: int = 20,
    offset: int = 0,
    archived: bool = False,
):
    """Listar conversas do utilizador."""
    query = select(CopilotConversation).where(
        and_(
            CopilotConversation.tenant_id == tenant_id,
            CopilotConversation.actor_id == user.user_id,
            CopilotConversation.is_archived == archived,
        )
    ).order_by(CopilotConversation.last_message_at.desc().nulls_last(), CopilotConversation.created_at.desc())

    result = await session.execute(query.offset(offset).limit(limit))
    conversations = result.scalars().all()

    return [
        {
            "id": str(c.id),
            "title": c.title,
            "created_at": c.created_at.isoformat(),
            "last_message_at": c.last_message_at.isoformat() if c.last_message_at else None,
            "is_archived": c.is_archived,
        }
        for c in conversations
    ]


@router.get("/conversations/{conversation_id}/messages", status_code=status.HTTP_200_OK)
async def get_conversation_messages(
    conversation_id: UUID,
    user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(_api.get_tenant_id),
    session: AsyncSession = Depends(get_session),
    limit: int = 100,
    offset: int = 0,
):
    """Obter mensagens de uma conversa."""
    # Verificar que a conversa pertence ao utilizador
    conversation = await session.get(CopilotConversation, conversation_id)
    if not conversation or conversation.tenant_id != tenant_id or conversation.actor_id != user.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada")

    query = select(CopilotMessage).where(
        and_(
            CopilotMessage.tenant_id == tenant_id,
            CopilotMessage.conversation_id == conversation_id,
        )
    ).order_by(CopilotMessage.created_at.asc())

    result = await session.execute(query.offset(offset).limit(limit))
    messages = result.scalars().all()

    return [
        {
            "id": str(m.id),
            "role": m.actor_role,
            "content_text": m.content_text,
            "content_structured": m.content_structured,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]


@router.post("/conversations/{conversation_id}/messages", status_code=status.HTTP_201_CREATED)
async def send_message(
    conversation_id: UUID,
    request: CopilotAskRequest,
    user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(_api.get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Enviar mensagem numa conversa e obter resposta do COPILOT."""
    # Verificar que a conversa pertence ao utilizador
    conversation = await session.get(CopilotConversation, conversation_id)
    if not conversation or conversation.tenant_id != tenant_id or conversation.actor_id != user.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada")

    # Guardar mensagem do utilizador
    user_message = CopilotMessage(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        actor_role="user",
        content_text=request.user_query,
        content_structured=None,
    )
    # Q.66.B.3: mensagem de chat LLM, nao state de governance.
    session.add(user_message)  # noqa: audit_coverage  # chat message, not gov state
    await session.flush()

    # Memória multi-turno: o `process_ask` lê/escreve o `ConversationStore`
    # (Redis, últimos 3 turnos) com base em `request.conversation_id`. O
    # endpoint recebe o id no path mas nunca o injectava no request — o
    # LLM ficava sem memória da conversa. Liga-os aqui.
    request.conversation_id = conversation_id

    # Processar pergunta com COPILOT
    service = _api.CopilotService(session, tenant_id, user.user_id, user.role)
    response, audit_data = await service.process_ask(request)

    # Guardar resposta do COPILOT
    copilot_message = CopilotMessage(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        actor_role="copilot",
        content_text=response.summary,
        content_structured=response.model_dump(),
        correlation_id=response.correlation_id,
        latency_ms=audit_data.get("latency_ms"),
        model=audit_data.get("model") or response.meta.get("model"),
        validation_passed=response.meta.get("validation_passed"),
    )
    # Q.66.B.3: resposta LLM (latencia/model/validation) — chat history,
    # nao state of governance.
    session.add(copilot_message)  # noqa: audit_coverage  # chat message, not gov state

    # Atualizar last_message_at da conversa
    conversation.last_message_at = datetime.now(timezone.utc)

    await session.commit()

    return response


@router.patch("/conversations/{conversation_id}/rename", status_code=status.HTTP_200_OK)
async def rename_conversation(
    conversation_id: UUID,
    title: str = Body(..., embed=True),
    user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(_api.get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Renomear conversa."""
    conversation = await session.get(CopilotConversation, conversation_id)
    if not conversation or conversation.tenant_id != tenant_id or conversation.actor_id != user.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada")

    conversation.title = title
    await session.commit()

    return {"id": str(conversation.id), "title": conversation.title}


@router.post("/conversations/{conversation_id}/archive", status_code=status.HTTP_200_OK)
async def archive_conversation(
    conversation_id: UUID,
    user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(_api.get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Arquivar/desarquivar conversa."""
    conversation = await session.get(CopilotConversation, conversation_id)
    if not conversation or conversation.tenant_id != tenant_id or conversation.actor_id != user.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada")

    conversation.is_archived = not conversation.is_archived
    await session.commit()

    return {"id": str(conversation.id), "is_archived": conversation.is_archived}
