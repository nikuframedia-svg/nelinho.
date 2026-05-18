"""Q.32.C.3 — bullet de feedback do copiloto no daily-feedback."""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.copilot.jobs.daily_feedback import _copilot_feedback_bullet
from tests.conftest import FakeSession


@pytest.mark.asyncio
async def test_bullet_is_none_when_no_feedback():
    assert await _copilot_feedback_bullet(FakeSession(), uuid4()) is None


@pytest.mark.asyncio
async def test_bullet_info_when_feedback_is_good():
    session = FakeSession()
    session.queue_scalars([
        ("up", {"intent": "diagnostic"}),
        ("up", {"intent": "diagnostic"}),
        ("down", {"intent": "diagnostic"}),
    ])
    bullet = await _copilot_feedback_bullet(session, uuid4())
    assert bullet is not None
    assert bullet.severity == "INFO"          # 66.7% ≥ 60
    assert "3 avaliações" in bullet.text


@pytest.mark.asyncio
async def test_bullet_warn_when_feedback_is_poor():
    session = FakeSession()
    session.queue_scalars([
        ("down", {"intent": "diagnostic"}),
        ("down", {"intent": "diagnostic"}),
        ("down", {"intent": "diagnostic"}),
        ("down", {"intent": "diagnostic"}),
        ("up", {"intent": "diagnostic"}),
    ])
    bullet = await _copilot_feedback_bullet(session, uuid4())
    assert bullet is not None
    assert bullet.severity == "WARN"          # 20% < 60
    assert "20.0%" in bullet.text
    assert "diagnostic" in bullet.text        # tema mais fraco
