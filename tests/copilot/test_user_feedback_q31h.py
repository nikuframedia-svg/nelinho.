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

from uuid import UUID

import pytest
from fastapi import HTTPException

from src.copilot.api import submit_user_feedback
from src.copilot.models import CopilotUserFeedback
from tests.conftest import FakeSession

_TENANT = UUID("11111111-1111-1111-1111-111111111111")


@pytest.mark.asyncio
async def test_feedback_up_is_persisted():
    session = FakeSession()
    result = await submit_user_feedback(
        payload={"thumb": "up", "text": "Resposta clara", "context": {"source": "x"}},
        tenant_id=_TENANT,
        session=session,  # type: ignore[arg-type]
    )
    assert result["status"] == "received"
    assert UUID(result["id"])
    assert len(session.added) == 1
    row = session.added[0]
    assert isinstance(row, CopilotUserFeedback)
    assert row.thumb == "up"
    assert row.text == "Resposta clara"
    assert row.context == {"source": "x"}
    assert session.commit_calls >= 1


@pytest.mark.asyncio
async def test_feedback_down_with_empty_text_stores_none():
    session = FakeSession()
    await submit_user_feedback(
        payload={"thumb": "down", "text": "   "},
        tenant_id=_TENANT,
        session=session,  # type: ignore[arg-type]
    )
    row = session.added[0]
    assert row.thumb == "down"
    assert row.text is None
    assert row.context is None


@pytest.mark.asyncio
async def test_feedback_invalid_thumb_is_400_and_nothing_staged():
    session = FakeSession()
    with pytest.raises(HTTPException) as exc:
        await submit_user_feedback(
            payload={"thumb": "maybe"},
            tenant_id=_TENANT,
            session=session,  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 400
    assert session.added == []
    assert session.commit_calls == 0


@pytest.mark.asyncio
async def test_feedback_non_dict_context_is_ignored():
    session = FakeSession()
    await submit_user_feedback(
        payload={"thumb": "up", "context": "not-a-dict"},
        tenant_id=_TENANT,
        session=session,  # type: ignore[arg-type]
    )
    assert session.added[0].context is None
