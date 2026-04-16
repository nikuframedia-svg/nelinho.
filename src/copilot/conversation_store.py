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
        """
        try:
            redis = await get_redis()
            key = cls._key(tenant_id, conversation_id)

            # Get existing history
            raw = await redis.get(key)
            history = json.loads(raw) if raw else []

            # Append new turn
            history.append({"role": "user", "content": user_message})
            history.append({"role": "assistant", "content": assistant_message})

            # Trim to last MAX_TURNS * 2 messages (each turn = 2 messages)
            max_messages = MAX_TURNS * 2
            if len(history) > max_messages:
                history = history[-max_messages:]

            # Save with TTL reset
            await redis.set(key, json.dumps(history), ex=CONVERSATION_TTL)
        except Exception as e:
            logger.warning(f"Failed to save conversation turn: {e}")

    @classmethod
    async def clear(cls, tenant_id: UUID, conversation_id: UUID) -> None:
        """Clear conversation history."""
        try:
            redis = await get_redis()
            await redis.delete(cls._key(tenant_id, conversation_id))
        except Exception as e:
            logger.warning(f"Failed to clear conversation: {e}")
