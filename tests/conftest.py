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
import re
from typing import Any, AsyncGenerator, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio


# ---------------------------------------------------------------------------
# Q.68.3.2 — Module-level helpers (extracted utilities)
# ---------------------------------------------------------------------------

_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


def extract_uuid_params(query: Any) -> List[str]:
    """Q.68.3.2 — Extract UUID strings from a SQLAlchemy statement.

    Looks at both:
      * the rendered SQL text (``str(stmt)`` or compiled SQL), and
      * the bindparam values (``stmt.compile().params``).

    Returns a list preserving order: text matches first, then bindparam
    UUID-like values. Duplicates are kept (call-site can dedupe). Robust
    to non-compilable inputs (returns ``[]`` from text path and skips
    bindparams).

    Used by ``tests/plan/test_worker_operations_endpoint.py``,
    ``tests/shared/test_auth_login_q31g.py``, and other DOMAIN variants
    that need to assert which UUIDs were bound to a query.
    """
    found: List[str] = []

    # Text-mode extraction — works on plain strings or anything with __str__.
    try:
        text = str(query)
        found.extend(_UUID_RE.findall(text))
    except Exception:
        pass

    # Bindparam extraction — only for SQLA Compilable objects.
    compile_fn = getattr(query, "compile", None)
    if callable(compile_fn):
        try:
            compiled = compile_fn()
            params = getattr(compiled, "params", None)
            if isinstance(params, dict):
                for value in params.values():
                    sval = str(value)
                    if _UUID_RE.fullmatch(sval):
                        found.append(sval)
        except Exception:
            # Non-compilable statement (raw SQL string, Mock) — text path only.
            pass

    return found


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
        # ---- Q.68.3.2 — multi-batch queue, entity registry, behavioural flags
        self._batches: List[List[Any]] = []
        self._entities: Dict[tuple, Any] = {}
        self.add_should_raise: bool = False
        self.raise_on_execute: bool = False
        self.executed: int = 0
        self.executed_stmts: List[Any] = []

    def queue_scalar(self, value: Any) -> None:
        """Queue a value for the next `(await session.execute(...)).scalar_one_or_none()`."""
        self._scalar_queue.append(value)

    def queue_scalars(self, values: List[Any]) -> None:
        """Queue a list for the next `(await session.execute(...)).scalars().all()`."""
        self._scalars_queue.append(list(values))

    # ===== Q.68.3.2 — helpers novos =====

    def queue_batch(self, rows: List[Any]) -> None:
        """Q.68.3.2 — Append a batch of rows to the multi-batch queue.

        Each subsequent ``execute()`` call consumes one batch (FIFO). When
        the multi-batch queue is non-empty it takes precedence over the
        legacy ``_scalars_queue`` — once it drains, ``execute()`` falls
        back to the legacy queue.

        Use this when a service issues several distinct SELECTs and you
        want to script the answers in order. See
        ``tests/governance/test_learning_metrics.py`` and
        ``tests/plan/test_cpo_commit_orders_q54d.py`` for callsites.
        """
        self._batches.append(list(rows))

    def register_entity(self, model: Any, pk: Any, row: Any) -> None:
        """Q.68.3.2 — Pre-populate the session with a row identifiable by
        ``(Model, pk)`` for use by ``session.get(Model, pk)``.

        ``model`` is keyed by ``__name__`` so subclasses / re-imports
        share the same slot. ``pk`` is stringified so callers can pass
        UUIDs, ints, or strings interchangeably.
        """
        self._entities[(model.__name__, str(pk))] = row

    async def get(self, model: Any, pk: Any) -> Any:
        """Q.68.3.2 — ``AsyncSession.get`` equivalent (pk lookup).

        Returns the row registered via :meth:`register_entity`, or
        ``None`` if no such row exists. Used by
        ``tests/plan/test_co1_decision_recording.py`` and
        ``tests/copilot/test_copilot_api_characterization_q66_d.py``.
        """
        return self._entities.get((model.__name__, str(pk)))

    # Session surface ------------------------------------------------------

    def add(self, obj: Any) -> None:
        if self.add_should_raise:
            raise RuntimeError("FakeSession.add_should_raise=True")
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
        self.executed += 1
        self.executed_stmts.append(stmt)
        if self.raise_on_execute:
            raise RuntimeError("FakeSession.raise_on_execute=True")
        # Q.68.3.2 — multi-batch queue takes precedence when populated.
        if self._batches:
            batch = self._batches.pop(0)
            # If the batch is a single scalar wrapper (rare), it still
            # works because _FakeResult exposes scalar() over self._scalar.
            return _FakeResult(batch[0] if batch else None, batch)
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
# Typed-stash variant for tests that issue many distinct SELECTs
# ---------------------------------------------------------------------------
#
# Q.61.02 — unifica o `_FakeSession` que vivia em
# `tests/governance/test_yaml_rule_service_q17c.py:59-106`. A diferenca de
# desenho face ao queue-based FakeSession acima:
#
#   * Queue mode (FakeSession): cada `execute()` consome o proximo item da
#     fila. Bom para testes choreografados onde a ordem de queries e
#     conhecida.
#
#   * Stash mode (FakeRuleSession): adiciona-se rules/revisions a colecoes
#     tipadas; `execute()` inspecciona o SQL compilado para decidir que
#     colecao devolver. Bom quando o service emite varias queries distintas
#     e o teste so quer guarantir um estado inicial.
#
# Ambos os modos co-existem; servicos que precisam de fluxo simples usam
# FakeSession; YAML rule lifecycle (~15 transicoes diferentes a inspeccionar
# tabelas distintas) usa FakeRuleSession.


class _TypedFakeResult:
    """_FakeResult sem fila — devolve a coleccao tipada que lhe foi dada."""

    def __init__(self, items: List[Any]) -> None:
        self._items = items

    def scalars(self) -> "_TypedFakeResult":
        return self

    def all(self) -> List[Any]:
        return list(self._items)

    def scalar_one_or_none(self) -> Any:
        return self._items[0] if self._items else None


class FakeRuleSession(FakeSession):
    """FakeSession para tests YAML rule lifecycle (governance.yaml_policy).

    Em vez de queue, mantem coleccoes tipadas por classe de modelo. O
    `execute(stmt)` inspecciona o SQL compilado para devolver o conjunto
    certo (rules vs revisions). Coexiste com o queue-based (chamadas a
    `execute()` que nao batem em nenhum FROM caem para o queue do pai).
    """

    def __init__(self) -> None:
        super().__init__()
        # Coleccoes tipadas — populadas via `add()`. Tipos importados
        # lazy para evitar acoplamento de bootstrap a governance.yaml_policy.
        self.rules: List[Any] = []
        self.revisions: List[Any] = []
        self.flush_count = 0  # alias historico para compat com testes

    def add(self, obj: Any) -> None:
        super().add(obj)  # mantem flat list `self.added`
        cls_name = obj.__class__.__name__
        if cls_name == "TenantRule":
            if getattr(obj, "id", None) is None:
                obj.id = uuid4()
            self.rules.append(obj)
        elif cls_name == "TenantRuleRevision":
            if getattr(obj, "id", None) is None:
                obj.id = uuid4()
            self.revisions.append(obj)

    async def flush(self) -> None:
        await super().flush()
        for r in self.rules:
            if getattr(r, "id", None) is None:
                r.id = uuid4()
        self.flush_count = self.flush_calls

    async def execute(self, stmt: Any) -> Any:
        # Compila para inspeccionar. Se nao for um Select inspeccionavel,
        # caimos no super().execute() (queue-based).
        try:
            compiled = str(stmt.compile(compile_kwargs={"literal_binds": False}))
        except Exception:
            return await super().execute(stmt)

        if "FROM governance.yaml_policy_rule_revision" in compiled:
            return _TypedFakeResult(self.revisions)
        if "FROM governance.yaml_policy_rule" in compiled:
            return _TypedFakeResult(self.rules)
        return await super().execute(stmt)


@pytest.fixture
def fake_rule_session() -> FakeRuleSession:
    return FakeRuleSession()


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
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        self.chat_calls.append({
            "prompt": prompt,
            "model": model,
            "format": format,
            "history": history,
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
