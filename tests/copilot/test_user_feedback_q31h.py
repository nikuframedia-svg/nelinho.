"""Q.31.H — `POST /api/copilot/feedback/user` persiste o feedback.

Antes o endpoint era um stub log-only: o 👍/👎 + texto livre da UI
(`DailyFeedbackForm`) era escrito para o log e descartado. Agora cada
submissão vira uma linha em `copilot_user_feedback`.

Testes:
  * thumb válido → 200 + linha CopilotUserFeedback staged + commit;
  * thumb inválido / em falta → 400, nada staged;
  * context não-dict é ignorado (guarda), texto vazio → None.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from fastapi import HTTPException

from src.copilot.api import submit_user_feedback
from src.copilot.routers.suggestions import UserFeedbackRequest
from src.copilot.models import CopilotUserFeedback
from src.shared.auth.jwt_handler import UserContext

_TENANT = UUID("11111111-1111-1111-1111-111111111111")
_USER = UserContext(
    user_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
    tenant_id=_TENANT,
    role="OPERATOR",
)


class _FakeSession:
    """AsyncSession mínima: captura add() + commit."""

    def __init__(self) -> None:
        self.staged: list = []
        self.committed = False

    def add(self, instance: Any) -> None:
        self.staged.append(instance)

    async def commit(self) -> None:
        self.committed = True


@pytest.mark.asyncio
async def test_feedback_up_is_persisted():
    session = _FakeSession()
    result = await submit_user_feedback(
        payload=UserFeedbackRequest(thumb="up", text="Resposta clara", context={"source": "x"}),
        user=_USER,
        tenant_id=_TENANT,
        session=session,  # type: ignore[arg-type]
    )
    assert result["status"] == "received"
    assert UUID(result["id"])
    assert len(session.staged) == 1
    row = session.staged[0]
    assert isinstance(row, CopilotUserFeedback)
    assert row.thumb == "up"
    assert row.text == "Resposta clara"
    assert row.context == {"source": "x"}
    assert row.user_id == _USER.user_id  # Q.F4.E — user_id gravado
    assert session.committed is True


@pytest.mark.asyncio
async def test_feedback_down_with_empty_text_stores_none():
    session = _FakeSession()
    await submit_user_feedback(
        payload=UserFeedbackRequest(thumb="down", text="   "),
        user=_USER,
        tenant_id=_TENANT,
        session=session,  # type: ignore[arg-type]
    )
    row = session.staged[0]
    assert row.thumb == "down"
    assert row.text is None
    assert row.context is None


@pytest.mark.asyncio
async def test_feedback_invalid_thumb_is_400_and_nothing_staged():
    """Q.171.C — o contrato passou a Pydantic: thumb inválido é rejeitado
    na FRONTEIRA (422 na API) antes de chegar à função."""
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        UserFeedbackRequest(thumb="maybe")


@pytest.mark.asyncio
async def test_feedback_non_dict_context_is_ignored():
    """Q.171.C — context não-dict é rejeitado pelo Pydantic na fronteira."""
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        UserFeedbackRequest(thumb="up", context="not-a-dict")