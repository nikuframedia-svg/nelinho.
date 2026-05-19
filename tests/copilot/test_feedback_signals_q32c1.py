"""Q.32.C.1 — agregação do feedback do copiloto por intent."""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.copilot.feedback_signals import FeedbackSignalsService, IntentFeedback
from tests.conftest import FakeSession


def test_intent_feedback_up_pct_and_significance():
    fb = IntentFeedback(intent="diagnostic", up=2, down=1)
    assert fb.total == 3
    assert fb.up_pct == 66.7
    assert fb.is_significant
    assert not IntentFeedback(intent="x", up=1, down=1).is_significant
    # Sem avaliações: up_pct é 0.0, não rebenta com divisão por zero.
    assert IntentFeedback(intent="x").up_pct == 0.0


@pytest.mark.asyncio
async def test_by_intent_aggregates_thumbs_per_intent():
    session = FakeSession()
    # A query devolve linhas (thumb, response_json).
    session.queue_scalars([
        ("up", {"intent": "diagnostic"}),
        ("up", {"intent": "diagnostic"}),
        ("down", {"intent": "diagnostic"}),
        ("up", {"intent": "kpi_current"}),
    ])
    svc = FeedbackSignalsService(session, uuid4())
    out = await svc.by_intent(window_days=90)

    assert out["diagnostic"].up == 2
    assert out["diagnostic"].down == 1
    assert out["diagnostic"].up_pct == 66.7
    assert out["kpi_current"].up == 1
    assert out["kpi_current"].down == 0


@pytest.mark.asyncio
async def test_by_intent_defaults_missing_intent_to_generic():
    session = FakeSession()
    session.queue_scalars([
        ("up", {}),            # response_json sem 'intent'
        ("down", None),        # response_json nulo
    ])
    svc = FeedbackSignalsService(session, uuid4())
    out = await svc.by_intent()
    assert out["generic"].up == 1
    assert out["generic"].down == 1


@pytest.mark.asyncio
async def test_by_intent_empty_when_no_feedback():
    svc = FeedbackSignalsService(FakeSession(), uuid4())
    assert await svc.by_intent() == {}


@pytest.mark.asyncio
async def test_overall_sums_every_intent():
    session = FakeSession()
    session.queue_scalars([
        ("up", {"intent": "diagnostic"}),
        ("up", {"intent": "kpi_current"}),
        ("down", {"intent": "routing"}),
    ])
    svc = FeedbackSignalsService(session, uuid4())
    total = await svc.overall(window_days=7)
    assert total.up == 2
    assert total.down == 1
    assert total.up_pct == 66.7
