"""Sprint Q.10 Fase C.5 — ImproveService unit tests.

Cover CRUD + tenant isolation + LLM generator with both Ollama-up
and Ollama-down paths (the latter must fall back to seed data
without raising).
"""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from src.improve.models import (
    ImprovementSuggestion,
    SuggestionSource,
    SuggestionStatus,
)
from src.improve.service import (
    ImproveService,
    SEED_SUGGESTIONS,
    SuggestionNotFoundError,
    SuggestionStateError,
)


TENANT = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def _suggestion(*, tenant_id: UUID = TENANT, status: str = "pending") -> ImprovementSuggestion:
    s = ImprovementSuggestion(
        id=uuid4(),
        tenant_id=tenant_id,
        title="Test suggestion",
        description="d",
        domain="oee",
        action_type="reduce_standard_time",
        status=status,
        source="seed",
        estimated_impact={"oee": {"delta": 1.0}},
        confidence=0.7,
    )
    s.created_at = datetime.utcnow()
    s.updated_at = datetime.utcnow()
    return s


def _stub_session(seeded, *, count_initial: int = 1):
    """Mock that:
    * returns scalar(count) for the seeding count query (we say count>0
      so seed isn't triggered automatically; a separate test toggles it)
    * returns the seeded list for the listing query
    """
    session = AsyncMock()

    async def _execute(stmt):
        try:
            params = stmt.compile().params
        except Exception:
            params = {}
        wanted_tenant = None
        wanted_id = None
        wanted_status = None
        wanted_domain = None
        for v in params.values():
            if isinstance(v, UUID):
                if wanted_tenant is None:
                    wanted_tenant = v
                else:
                    wanted_id = v
            elif isinstance(v, str):
                if v in {"pending", "approved", "rejected", "implemented"}:
                    wanted_status = v
                else:
                    wanted_domain = v

        ids = {s.id for s in seeded}
        if wanted_tenant in ids:
            wanted_id, wanted_tenant = wanted_tenant, wanted_id

        hits = [
            s for s in seeded
            if (wanted_tenant is None or s.tenant_id == wanted_tenant)
            and (wanted_id is None or s.id == wanted_id)
            and (wanted_status is None or s.status == wanted_status)
            and (wanted_domain is None or s.domain == wanted_domain)
        ]

        is_count = "count" in str(stmt).lower()

        class _Result:
            def scalar_one_or_none(self_):
                return hits[0] if hits else None
            def scalar(self_):
                return count_initial if is_count else (len(hits))
            def scalars(self_):
                class _S:
                    def all(_self): return list(hits)
                return _S()
        return _Result()

    session.execute = _execute
    session.add = lambda obj: None
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_get_suggestion_isolates_by_tenant():
    other = _suggestion(tenant_id=OTHER_TENANT)
    session = _stub_session([other])
    svc = ImproveService(session, TENANT)
    out = await svc.get_suggestion(other.id)
    assert out is None


@pytest.mark.asyncio
async def test_approve_marks_approved_and_stamps_reviewer():
    sug = _suggestion()
    session = _stub_session([sug])
    svc = ImproveService(session, TENANT)
    reviewer = uuid4()
    out = await svc.approve(sug.id, reviewer)
    assert out.status == SuggestionStatus.APPROVED.value
    assert out.reviewed_by == reviewer
    assert out.reviewed_at is not None


@pytest.mark.asyncio
async def test_approve_rejects_already_reviewed():
    sug = _suggestion(status=SuggestionStatus.APPROVED.value)
    session = _stub_session([sug])
    svc = ImproveService(session, TENANT)
    with pytest.raises(SuggestionStateError):
        await svc.approve(sug.id, uuid4())


@pytest.mark.asyncio
async def test_reject_stores_reason():
    sug = _suggestion()
    session = _stub_session([sug])
    svc = ImproveService(session, TENANT)
    out = await svc.reject(sug.id, uuid4(), reason="too risky")
    assert out.status == SuggestionStatus.REJECTED.value
    assert out.rejection_reason == "too risky"


@pytest.mark.asyncio
async def test_reject_unknown_id_raises():
    session = _stub_session([])
    svc = ImproveService(session, TENANT)
    with pytest.raises(SuggestionNotFoundError):
        await svc.reject(uuid4(), uuid4())


@pytest.mark.asyncio
async def test_generate_via_llm_uses_ollama_payload():
    """When Ollama returns a valid suggestions array, the service stores
    each row with source=llm_generated and confidence as parsed."""
    session = _stub_session([])
    fake_payload = {
        "ok": True,
        "suggestions": [
            {
                "title": "LLM idea 1",
                "description": "d1",
                "domain": "quality",
                "action_type": "improve_quality",
                "estimated_impact": {"quality": {"delta": 4.2, "confidence": 0.9}},
                "confidence": 0.83,
            },
        ],
    }
    fake_client = AsyncMock()
    fake_client.chat_with_fallback = AsyncMock(return_value=fake_payload)
    with patch("src.copilot.ollama_client.get_ollama_client", return_value=fake_client):
        svc = ImproveService(session, TENANT)
        out = await svc.generate_via_llm(scope="quality", limit=3)

    assert len(out) == 1
    assert out[0].source == SuggestionSource.LLM_GENERATED.value
    assert out[0].confidence == 0.83
    assert out[0].title == "LLM idea 1"


@pytest.mark.asyncio
async def test_generate_via_llm_falls_back_to_seed_when_llm_down():
    """ok=False (Ollama down / circuit-open) → service produces seed rows
    instead, never raises."""
    session = _stub_session([])
    fake_client = AsyncMock()
    fake_client.chat_with_fallback = AsyncMock(return_value={
        "ok": False, "code": "MODEL_OFFLINE",
    })
    with patch("src.copilot.ollama_client.get_ollama_client", return_value=fake_client):
        svc = ImproveService(session, TENANT)
        out = await svc.generate_via_llm(scope="oee", limit=2)

    assert out, "expected seed fallback to produce at least one row"
    assert all(s.source == SuggestionSource.SEED.value for s in out)
    # All requested-domain rows
    assert all(s.domain == "oee" for s in out)


@pytest.mark.asyncio
async def test_generate_via_llm_falls_back_when_payload_malformed():
    """ok=True but no recognisable suggestions array → seed fallback."""
    session = _stub_session([])
    fake_client = AsyncMock()
    fake_client.chat_with_fallback = AsyncMock(return_value={
        "ok": True, "content": "not json at all",
    })
    with patch("src.copilot.ollama_client.get_ollama_client", return_value=fake_client):
        svc = ImproveService(session, TENANT)
        out = await svc.generate_via_llm(limit=3)
    assert out
    assert all(s.source == SuggestionSource.SEED.value for s in out)
