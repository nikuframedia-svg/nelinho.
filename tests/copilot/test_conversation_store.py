"""
Tests for src.copilot.conversation_store.ConversationStore.

Coverage:
- get_history: empty key, valid JSON, corrupted JSON
- append_turn: first turn, multi-turn append, trim at MAX_TURNS*2, TTL reset
- clear: deletes key (idempotent)
- _key: format stability
"""

from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest

from src.copilot.conversation_store import (
    ConversationStore,
    CONVERSATION_TTL,
    MAX_TURNS,
)


# ---------------------------------------------------------------------------
# _key
# ---------------------------------------------------------------------------

class TestKey:
    def test_key_format(self, tenant_id):
        conv_id = UUID("22222222-2222-2222-2222-222222222222")
        key = ConversationStore._key(tenant_id, conv_id)
        assert key == f"copilot:conv:{tenant_id}:{conv_id}"

    def test_key_is_deterministic(self, tenant_id):
        conv_id = uuid4()
        assert ConversationStore._key(tenant_id, conv_id) == \
               ConversationStore._key(tenant_id, conv_id)


# ---------------------------------------------------------------------------
# get_history
# ---------------------------------------------------------------------------

class TestGetHistory:
    async def test_returns_empty_when_key_absent(self, fake_redis, tenant_id):
        history = await ConversationStore.get_history(tenant_id, uuid4())
        assert history == []

    async def test_returns_parsed_list_when_present(self, fake_redis, tenant_id):
        conv_id = uuid4()
        key = ConversationStore._key(tenant_id, conv_id)
        payload = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]
        await fake_redis.set(key, json.dumps(payload))

        history = await ConversationStore.get_history(tenant_id, conv_id)
        assert history == payload

    async def test_returns_empty_on_corrupted_json(self, fake_redis, tenant_id):
        conv_id = uuid4()
        key = ConversationStore._key(tenant_id, conv_id)
        await fake_redis.set(key, "not valid json {{{")

        history = await ConversationStore.get_history(tenant_id, conv_id)
        assert history == []  # catch-all exception handler returns []


# ---------------------------------------------------------------------------
# append_turn
# ---------------------------------------------------------------------------

class TestAppendTurn:
    async def test_first_turn_creates_two_messages(self, fake_redis, tenant_id):
        conv_id = uuid4()
        await ConversationStore.append_turn(
            tenant_id, conv_id, user_message="Q1", assistant_message="A1"
        )

        history = await ConversationStore.get_history(tenant_id, conv_id)
        assert history == [
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "A1"},
        ]

    async def test_multi_turn_appends_in_order(self, fake_redis, tenant_id):
        conv_id = uuid4()
        await ConversationStore.append_turn(tenant_id, conv_id, "Q1", "A1")
        await ConversationStore.append_turn(tenant_id, conv_id, "Q2", "A2")

        history = await ConversationStore.get_history(tenant_id, conv_id)
        assert [m["content"] for m in history] == ["Q1", "A1", "Q2", "A2"]

    async def test_trims_to_max_turns_window(self, fake_redis, tenant_id):
        conv_id = uuid4()
        # MAX_TURNS=3 => at most 6 messages. Append 5 turns (10 messages) => expect last 6.
        for i in range(5):
            await ConversationStore.append_turn(
                tenant_id, conv_id, f"Q{i}", f"A{i}"
            )

        history = await ConversationStore.get_history(tenant_id, conv_id)
        assert len(history) == MAX_TURNS * 2
        # Oldest kept should be from turn 5-MAX_TURNS = 2
        assert history[0]["content"] == "Q2"
        assert history[-1]["content"] == "A4"

    async def test_ttl_is_set_on_write(self, fake_redis, tenant_id):
        conv_id = uuid4()
        await ConversationStore.append_turn(tenant_id, conv_id, "Q", "A")

        key = ConversationStore._key(tenant_id, conv_id)
        ttl = await fake_redis.ttl(key)
        # Should be positive and ≤ CONVERSATION_TTL (30 min)
        assert 0 < ttl <= CONVERSATION_TTL

    async def test_handles_unicode_content(self, fake_redis, tenant_id):
        conv_id = uuid4()
        await ConversationStore.append_turn(
            tenant_id, conv_id,
            user_message="Qué é o OEE? 日本語 ✓",
            assistant_message="São três componentes: disponibilidade, performance, qualidade.",
        )

        history = await ConversationStore.get_history(tenant_id, conv_id)
        assert history[0]["content"] == "Qué é o OEE? 日本語 ✓"
        assert "disponibilidade" in history[1]["content"]

    async def test_swallows_redis_errors(self, monkeypatch, tenant_id):
        """append_turn logs warning on redis error and continues (no raise)."""
        class BrokenRedis:
            async def get(self, *a, **k):
                raise RuntimeError("redis down")
            async def set(self, *a, **k):
                raise RuntimeError("redis down")

        async def _bad_redis():
            return BrokenRedis()

        monkeypatch.setattr(
            "src.copilot.conversation_store.get_redis", _bad_redis
        )
        # Should not raise
        await ConversationStore.append_turn(tenant_id, uuid4(), "Q", "A")


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------

class TestClear:
    async def test_clear_removes_existing_key(self, fake_redis, tenant_id):
        conv_id = uuid4()
        await ConversationStore.append_turn(tenant_id, conv_id, "Q", "A")
        assert await ConversationStore.get_history(tenant_id, conv_id)  # non-empty

        await ConversationStore.clear(tenant_id, conv_id)
        assert await ConversationStore.get_history(tenant_id, conv_id) == []

    async def test_clear_is_idempotent_on_missing_key(self, fake_redis, tenant_id):
        # Should not raise even if key never existed
        await ConversationStore.clear(tenant_id, uuid4())
