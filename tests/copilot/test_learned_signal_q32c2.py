"""Q.32.C.2 — bloco "sinal aprendido" injectado no prompt do copiloto."""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.copilot.service import CopilotService
from tests.conftest import FakeSession


def _service(session: FakeSession) -> CopilotService:
    return CopilotService(session, uuid4(), uuid4(), "admin_platform")


@pytest.mark.asyncio
async def test_learned_signal_empty_when_no_feedback():
    assert await _service(FakeSession())._build_learned_signal() == ""


@pytest.mark.asyncio
async def test_learned_signal_empty_below_min_samples():
    session = FakeSession()
    session.queue_scalars([("up", {"intent": "diagnostic"})])  # só 1 < MIN (3)
    assert await _service(session)._build_learned_signal() == ""


@pytest.mark.asyncio
async def test_learned_signal_block_when_significant():
    session = FakeSession()
    session.queue_scalars([
        ("up", {"intent": "diagnostic"}),
        ("down", {"intent": "diagnostic"}),
        ("down", {"intent": "diagnostic"}),   # diagnostic: 1/3 = 33.3%
        ("up", {"intent": "generic"}),
        ("up", {"intent": "generic"}),
        ("up", {"intent": "generic"}),        # generic: 3/3 = 100%
    ])
    block = await _service(session)._build_learned_signal()

    assert "SINAL APRENDIDO" in block
    assert "Globalmente" in block
    assert "66.7%" in block          # 4 up / 6 total
    assert "diagnostic" in block
    assert "generic" in block
    # diagnostic está abaixo de 60% → recebe a nota de rigor.
    assert "sê mais rigoroso" in block
