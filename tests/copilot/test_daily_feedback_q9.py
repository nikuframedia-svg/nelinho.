"""Sprint Q.9 (2.7) — daily feedback emits rejection patterns + anomalies.

The job replaces the previous static bullets with two real-data
streams. Tests cover:
* rejection patterns aggregator groups by reason and orders by count
* top_anomalies surfaces at-risk OFs when they exist
* generate_daily_feedback wires both into the response
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from src.copilot.jobs.daily_feedback import (
    _rejection_patterns,
    _top_anomalies,
    generate_daily_feedback,
)


TENANT = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def _row(reasons):
    """Build a fake `(rejected_alternatives,)` row for the SQL select."""
    return (reasons,)


@pytest.mark.asyncio
async def test_rejection_patterns_groups_by_reason():
    session = AsyncMock()

    async def _execute(_stmt):
        class _Result:
            def all(self_):
                return [
                    _row([
                        {"reason": "setup too high"},
                        {"reason": "setup too high"},
                        {"reason": "tardiness penalty"},
                    ]),
                    _row([
                        {"reason": "setup too high"},
                        {"reason": "preference rule violation"},
                    ]),
                ]
        return _Result()

    session.execute = _execute

    patterns = await _rejection_patterns(
        session, TENANT, datetime.utcnow() - timedelta(days=1),
    )
    assert patterns[0] == ("setup too high", 3)
    assert ("tardiness penalty", 1) in patterns
    assert ("preference rule violation", 1) in patterns


@pytest.mark.asyncio
async def test_rejection_patterns_handles_unspecified_reason():
    """Alternatives without a reason fall under the 'unspecified' bucket."""
    session = AsyncMock()

    async def _execute(_stmt):
        class _Result:
            def all(self_):
                return [_row([{}, {"reason": ""}, {"reason": "    "}])]
        return _Result()

    session.execute = _execute

    patterns = await _rejection_patterns(session, TENANT, datetime.utcnow())
    assert patterns == [("unspecified", 3)]


@pytest.mark.asyncio
async def test_top_anomalies_flags_at_risk_orders():
    """When the count query returns >0 at-risk OFs, an anomaly surfaces."""
    session = AsyncMock()

    async def _execute(_stmt):
        class _Result:
            def scalar(self_): return 7
            def one(self_): return SimpleNamespace(total=0, active=0, zombie=0)
        return _Result()

    session.execute = _execute

    anomalies = await _top_anomalies(session, TENANT, date(2026, 4, 26))
    kinds = [a["kind"] for a in anomalies]
    assert "at_risk_orders" in kinds
    at_risk = next(a for a in anomalies if a["kind"] == "at_risk_orders")
    assert at_risk["severity"] == "WARN"  # 7 >= 5
    assert "7 OFs" in at_risk["summary"]


@pytest.mark.asyncio
async def test_generate_daily_feedback_wires_both_streams(monkeypatch):
    """Smoke: the function returns a DailyFeedbackResponse with at least
    a rejection-patterns bullet and an anomaly bullet."""
    session = AsyncMock()

    # Stub the two helpers so we don't need a full DB schema.
    async def _patterns(*_a, **_kw):
        return [("setup too high", 4)]

    async def _anomalies(*_a, **_kw):
        return [{"kind": "at_risk_orders", "severity": "WARN", "summary": "7 OFs at risk"}]

    monkeypatch.setattr(
        "src.copilot.jobs.daily_feedback._rejection_patterns", _patterns,
    )
    monkeypatch.setattr(
        "src.copilot.jobs.daily_feedback._top_anomalies", _anomalies,
    )

    resp = await generate_daily_feedback(session, TENANT, "2026-04-26")
    titles = [b.title for b in resp.bullets]
    assert any("Rejection patterns" in t for t in titles)
    assert any("Anomaly" in t for t in titles)
    assert resp.date == "2026-04-26"
