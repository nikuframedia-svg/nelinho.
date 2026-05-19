"""
ProdPlan ONE - Test Fixtures
=============================

Shared fixtures for unit tests. Strategy:
- Governance service: mock AsyncSession (models use PostgreSQL schemas/JSONB,
  not portable to SQLite).
- Copilot service: mock Ollama client, mock RAG, mock session, mock context.
- ConversationStore: fakeredis (drop-in for redis.asyncio).
"""

from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio


# ---------------------------------------------------------------------------
# Deterministic IDs
# ---------------------------------------------------------------------------

TEST_TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
TEST_USER_A = "alice"
TEST_USER_B = "bob"
TEST_USER_C = "carol"


@pytest.fixture
def tenant_id() -> UUID:
    return TEST_TENANT_ID


@pytest.fixture
def user_a() -> str:
    return TEST_USER_A


@pytest.fixture
def user_b() -> str:
    return TEST_USER_B


# ---------------------------------------------------------------------------
# AsyncMock session for services that don't need real persistence
# ---------------------------------------------------------------------------

class FakeSession:
    """
    Lightweight async session mock that captures adds and exposes a query queue.

    Usage:
        session = FakeSession()
        session.queue_scalar(None)          # next execute().scalar_one_or_none()
        session.queue_scalars([obj1, obj2]) # next execute().scalars().all()
        service = GovernanceService(session, tenant_id)
        ...
        assert session.added  # list of objects passed to session.add()
    """

    def __init__(self) -> None:
        self.added: List[Any] = []
        self._scalar_queue: List[Any] = []
        self._scalars_queue: List[List[Any]] = []
        self.flush_calls: int = 0
        self.refresh_calls: List[Any] = []
        self.commit_calls: int = 0
        self.rollback_calls: int = 0
        self.deleted: List[Any] = []

    def queue_scalar(self, value: Any) -> None:
        """Queue a value for the next `(await session.execute(...)).scalar_one_or_none()`."""
        self._scalar_queue.append(value)

    def queue_scalars(self, values: List[Any]) -> None:
        """Queue a list for the next `(await session.execute(...)).scalars().all()`."""
        self._scalars_queue.append(list(values))

    # Session surface ------------------------------------------------------

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def delete(self, obj: Any) -> None:
        self.deleted.append(obj)

    async def flush(self) -> None:
        self.flush_calls += 1

    async def commit(self) -> None:
        self.commit_calls += 1

    async def rollback(self) -> None:
        self.rollback_calls += 1

    async def refresh(self, obj: Any) -> None:
        self.refresh_calls.append(obj)

    def begin_nested(self) -> "_FakeNestedTransaction":
        """No-op savepoint — `async with session.begin_nested():` works.

        Sprint Q.12 — added to support the inventory_ledger / allocation_service
        / payroll_service savepoint usage without spinning up a real DB.
        """
        self.begin_nested_calls = getattr(self, "begin_nested_calls", 0) + 1
        return _FakeNestedTransaction()

    async def execute(self, stmt: Any) -> "_FakeResult":
        scalar = self._scalar_queue.pop(0) if self._scalar_queue else None
        scalars = self._scalars_queue.pop(0) if self._scalars_queue else []
        return _FakeResult(scalar, scalars)


class _FakeNestedTransaction:
    """Async context manager that mimics SQLAlchemy savepoint."""

    async def __aenter__(self) -> "_FakeNestedTransaction":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeResult:
    def __init__(self, scalar: Any, scalars: List[Any]) -> None:
        self._scalar = scalar
        self._scalars = scalars

    def scalar_one_or_none(self) -> Any:
        return self._scalar

    def scalar(self) -> Any:
        # SQLAlchemy's Result.scalar() — alias for scalar_one_or_none() in
        # the fake; we don't simulate the "more than one row" error here.
        return self._scalar

    def scalars(self) -> "_FakeScalars":
        return _FakeScalars(self._scalars)

    def all(self) -> List[Any]:
        # Multi-column selects (e.g. `SELECT a, b`) return Row tuples via
        # `.all()`. Tests using queue_scalars([(a1, b1), (a2, b2)]) can rely
        # on this.
        return list(self._scalars)


class _FakeScalars:
    def __init__(self, items: List[Any]) -> None:
        self._items = items

    def all(self) -> List[Any]:
        return list(self._items)

    def first(self) -> Any:
        return self._items[0] if self._items else None


@pytest.fixture
def fake_session() -> FakeSession:
    return FakeSession()


# ---------------------------------------------------------------------------
# fakeredis for ConversationStore
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def fake_redis(monkeypatch):
    """
    Patch `src.shared.redis_client.get_redis` to return a fakeredis async client.
    Yields the client so tests can inspect keys directly.
    """
    import fakeredis.aioredis
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def _get_redis_fake():
        return fake

    # Patch both import sites (conversation_store imports from shared.redis_client)
    monkeypatch.setattr("src.shared.redis_client.get_redis", _get_redis_fake)
    monkeypatch.setattr("src.copilot.conversation_store.get_redis", _get_redis_fake)

    yield fake

    await fake.aclose()


# ---------------------------------------------------------------------------
# Ollama mock
# ---------------------------------------------------------------------------

class MockOllamaClient:
    """Stand-in for OllamaClient with scripted responses."""

    def __init__(self) -> None:
        self.chat_responses: List[Any] = []  # each item: dict OR Exception
        self.chat_calls: List[Dict[str, Any]] = []
        self.embeddings_responses: List[Any] = []

    def queue_chat(self, response: Any) -> None:
        """Queue a dict response or an Exception instance to raise."""
        self.chat_responses.append(response)

    def queue_embedding(self, vec: List[float]) -> None:
        self.embeddings_responses.append(vec)

    async def chat(
        self,
        prompt: str,
        model: str,
        format: Optional[str] = "json",
        history: Optional[List[Dict[str, str]]] = None,
        num_ctx: Optional[int] = None,
        num_predict: Optional[int] = None,
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        self.chat_calls.append({
            "prompt": prompt,
            "model": model,
            "format": format,
            "history": history,
            "num_ctx": num_ctx,
            "num_predict": num_predict,
            "system_prompt": system_prompt,
        })
        if not self.chat_responses:
            raise AssertionError("MockOllamaClient.chat called without a queued response")
        resp = self.chat_responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp

    async def embeddings(self, text: str, model: str) -> List[float]:
        if not self.embeddings_responses:
            raise AssertionError("MockOllamaClient.embeddings called without a queued response")
        return self.embeddings_responses.pop(0)

    async def health_check(self) -> bool:
        return True

    def reset_circuit_breaker(self) -> None:
        pass


@pytest.fixture
def mock_ollama(monkeypatch) -> MockOllamaClient:
    """Replace the global Ollama client singleton with a MockOllamaClient."""
    import src.copilot.ollama_client as ollama_mod
    client = MockOllamaClient()
    monkeypatch.setattr(ollama_mod, "_ollama_client", client)
    # also patch get_ollama_client in case modules import it at call time
    monkeypatch.setattr(ollama_mod, "get_ollama_client", lambda: client)
    # copilot.service imports get_ollama_client at module level
    monkeypatch.setattr("src.copilot.service.get_ollama_client", lambda: client)
    return client


# ---------------------------------------------------------------------------
# Valid CopilotResponse dict builder (short-form)
# ---------------------------------------------------------------------------

def make_valid_llm_response(
    summary: str = "Test response",
    intent: str = "generic",
    type_: str = "ANSWER",
    with_citations: bool = True,
) -> Dict[str, Any]:
    """Return the minimum-valid JSON dict an LLM would produce for process_ask."""
    fact = {"text": "A test fact.", "citations": []}
    if with_citations:
        fact["citations"] = [{
            "source_type": "db",
            "ref": "table:test;id:1",
            "label": "Test Source",
            "confidence": 0.9,
            "trust_index": 0.85,
        }]
    return {
        "type": type_,
        "intent": intent,
        "summary": summary,
        "facts": [fact],
        "actions": [],
        "warnings": [],
        "meta": {"model": "mock", "tokens": 10, "latency_ms": 5, "validation_passed": True},
    }


@pytest.fixture
def valid_llm_response_factory():
    return make_valid_llm_response
