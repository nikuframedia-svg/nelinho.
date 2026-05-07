"""
ProdPlan ONE - Conversation Store
==================================

Redis-backed multi-turn conversation context for the Copilot.
Stores the last N turns per conversation_id with automatic TTL expiry.
"""

import json
import logging
from typing import Dict, List, Optional
from uuid import UUID

from src.shared.redis_client import get_redis

logger = logging.getLogger(__name__)

# Max turns kept in context (user + assistant = 1 turn)
MAX_TURNS = 3
# TTL for conversation context in Redis (30 minutes)
CONVERSATION_TTL = 1800


class ConversationStore:
    """
    Redis-backed store for multi-turn conversation context.

    Each conversation stores the last MAX_TURNS exchanges as Ollama-format messages.
    Automatically expires after CONVERSATION_TTL seconds of inactivity.
    """

    @staticmethod
    def _key(tenant_id: UUID, conversation_id: UUID) -> str:
        return f"copilot:conv:{tenant_id}:{conversation_id}"

    @classmethod
    async def get_history(
        cls,
        tenant_id: UUID,
        conversation_id: UUID,
    ) -> List[Dict[str, str]]:
        """
        Get conversation history as Ollama chat messages.

        Returns:
            List of {"role": "user"|"assistant", "content": "..."} dicts,
            ordered chronologically (oldest first).
        """
        try:
            redis = await get_redis()
            key = cls._key(tenant_id, conversation_id)
            raw = await redis.get(key)
            if raw is None:
                return []
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"Failed to read conversation history: {e}")
            return []

    # Sprint Q.12 Onda 3.2 — Lua script that performs GET → append →
    # trim → SET atomically inside Redis. The previous Python-side
    # read-modify-write let two concurrent ``append_turn`` calls
    # interleave: both read the same baseline history, both appended a
    # different turn, the second SET clobbered the first. The script
    # is keyed on the conversation key and parameterised on the new
    # messages + max_messages + ttl so a single round-trip does the
    # whole transaction.
    #
    # KEYS[1]   conversation key
    # ARGV[1]   user message JSON-encoded
    # ARGV[2]   assistant message JSON-encoded
    # ARGV[3]   max number of messages to retain (string-encoded int)
    # ARGV[4]   TTL seconds (string-encoded int)
    _APPEND_TURN_LUA = """
local raw = redis.call('GET', KEYS[1])
local history
if raw then
  history = cjson.decode(raw)
else
  history = {}
end
table.insert(history, cjson.decode(ARGV[1]))
table.insert(history, cjson.decode(ARGV[2]))
local max_msgs = tonumber(ARGV[3])
while #history > max_msgs do
  table.remove(history, 1)
end
redis.call('SET', KEYS[1], cjson.encode(history), 'EX', tonumber(ARGV[4]))
return #history
"""

    @classmethod
    async def append_turn(
        cls,
        tenant_id: UUID,
        conversation_id: UUID,
        user_message: str,
        assistant_message: str,
    ) -> None:
        """
        Append a user+assistant turn and trim to MAX_TURNS.
        Resets the TTL on every append.

        Sprint Q.12 Onda 3.2 — runs an atomic Lua script so the
        GET→append→trim→SET sequence happens inside a single Redis
        command. The previous read-modify-write let two concurrent
        callers clobber each other's turns silently. Falls back to a
        WATCH/MULTI/EXEC transaction when ``EVAL`` isn't supported
        (older fakeredis used in unit tests); the fallback is still
        atomic from the Redis side.
        """
        try:
            redis = await get_redis()
            key = cls._key(tenant_id, conversation_id)
            user_payload = json.dumps({"role": "user", "content": user_message})
            assistant_payload = json.dumps(
                {"role": "assistant", "content": assistant_message}
            )
            max_messages = MAX_TURNS * 2
            try:
                await redis.eval(
                    cls._APPEND_TURN_LUA,
                    1,
                    key,
                    user_payload,
                    assistant_payload,
                    str(max_messages),
                    str(CONVERSATION_TTL),
                )
                return
            except Exception as lua_exc:
                # Fallback for backends without Lua (older fakeredis
                # in unit tests). We use WATCH/MULTI/EXEC so the
                # read-modify-write is still atomic at the Redis layer
                # — only the round-trip count goes from 1 to 2.
                logger.debug(
                    "conversation_store: EVAL unavailable (%s); "
                    "falling back to WATCH/MULTI/EXEC.", lua_exc,
                )
            await cls._append_turn_via_watch(
                redis, key,
                json.loads(user_payload),
                json.loads(assistant_payload),
                max_messages,
            )
        except Exception as e:
            logger.warning(f"Failed to save conversation turn: {e}")

    @classmethod
    async def _append_turn_via_watch(
        cls,
        redis,
        key: str,
        user_msg: Dict[str, str],
        assistant_msg: Dict[str, str],
        max_messages: int,
    ) -> None:
        """WATCH/MULTI/EXEC fallback for environments without Lua.

        Retries up to ``_WATCH_MAX_RETRIES`` times if a concurrent
        writer invalidates the watched key. After that we drop the
        turn rather than spin forever — same trade-off the Lua path
        makes: better to lose one message than corrupt the chronology.
        """
        for _attempt in range(cls._WATCH_MAX_RETRIES):
            try:
                # py-redis exposes the transactional pipeline via
                # ``redis.pipeline(transaction=True)``. fakeredis
                # supports the same surface for unit tests.
                async with redis.pipeline(transaction=True) as pipe:
                    await pipe.watch(key)
                    raw = await pipe.get(key)
                    history = json.loads(raw) if raw else []
                    history.append(user_msg)
                    history.append(assistant_msg)
                    if len(history) > max_messages:
                        history = history[-max_messages:]
                    pipe.multi()
                    pipe.set(key, json.dumps(history), ex=CONVERSATION_TTL)
                    await pipe.execute()
                    return
            except Exception as exc:  # pragma: no cover — retry path
                # WatchError or backend hiccup — retry; final attempt
                # falls out of the loop and is logged by the caller.
                logger.debug(
                    "conversation_store: WATCH attempt %d failed: %s",
                    _attempt, exc,
                )
        # Best-effort failure mode — one lost turn is preferable to a
        # half-written history.
        raise RuntimeError(
            f"conversation_store: WATCH/MULTI/EXEC failed after "
            f"{cls._WATCH_MAX_RETRIES} attempts for key={key}"
        )

    _WATCH_MAX_RETRIES = 5

    @classmethod
    async def clear(cls, tenant_id: UUID, conversation_id: UUID) -> None:
        """Clear conversation history."""
        try:
            redis = await get_redis()
            await redis.delete(cls._key(tenant_id, conversation_id))
        except Exception as e:
            logger.warning(f"Failed to clear conversation: {e}")
