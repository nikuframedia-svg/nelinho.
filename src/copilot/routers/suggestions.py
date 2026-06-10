"""Q.66.D.4a — sub-router: suggestions GET + user feedback.

`/suggestions/{id}` é o registo imutável de uma sugestão (audit) e
`/feedback/user` recolhe 👍/👎 ad-hoc do utilizador (Onda 13 M /
Q.31.H). Ambos partilham o tema "feedback sobre uma sugestão" — daí
o agrupamento.
"""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.copilot import api as _api  # late attribute access — vê monkey-patches
from src.copilot.models import CopilotSuggestion, CopilotUserFeedback
from src.copilot.schemas import CopilotResponse
from src.shared.auth.jwt_handler import UserContext, get_current_user
from src.shared.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/suggestions/{suggestion_id}", response_model=CopilotResponse)
async def get_suggestion(
    suggestion_id: UUID,
    user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(_api.get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Obter registo imutável de sugestão (audit)."""
    suggestion = await session.get(CopilotSuggestion, suggestion_id)

    if not suggestion or suggestion.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggestion não encontrada",
        )

    return suggestion.response_json


# ──────────────────────────────────────────────────────────────────────────
# User feedback collector — Onda 13 M (UI ad-hoc 👍👎 + texto)
# ──────────────────────────────────────────────────────────────────────────


class UserFeedbackRequest(BaseModel):
    """Q.171.C — contrato tipado (era dict sem schema: campos quaisquer)."""

    thumb: str = Field(..., pattern="^(up|down)$")
    text: str = Field(default="", max_length=4000)
    context: Optional[dict] = None


@router.post("/feedback/user", status_code=status.HTTP_200_OK)
async def submit_user_feedback(
    payload: UserFeedbackRequest,
    tenant_id: UUID = Depends(_api.get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Recebe feedback ad-hoc do utilizador (👍/👎 + texto livre).

    Q.31.H — persiste em ``copilot_user_feedback``. Antes era um stub
    log-only e o sinal perdia-se.

    Payload aceita: ``{thumb: 'up'|'down', text: str, context?: dict}``.
    """
    thumb = payload.thumb.strip()
    text = payload.text.strip()
    if thumb not in ("up", "down"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="thumb must be 'up' or 'down'")

    context = payload.context
    row = CopilotUserFeedback(
        id=uuid4(),
        tenant_id=tenant_id,
        thumb=thumb,
        text=text or None,
        context=context if isinstance(context, dict) else None,
    )
    # Q.66.B.3: feedback do utilizador (thumbs up/down) e dado de
    # aprendizagem para tuning do copiloto, nao state de governance.
    session.add(row)  # noqa: audit_coverage  # user feedback for learning, not gov state
    await session.commit()

    return {
        "status": "received",
        "id": str(row.id),
        "thumb": thumb,
        "text_len": len(text),
        "tenant_id": str(tenant_id),
    }
