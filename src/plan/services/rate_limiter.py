"""Q.115.D — Rate limiter para auto-propose.

In-memory dict[str, datetime] com TTL 5 min por chave.
Redis-backed opcional (futura extensão): basta trocar a implementação.

Invariante: max 1 Decision por chave por 5 min.
Drop silencioso (log INFO) quando o limite é atingido.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict

logger = logging.getLogger(__name__)

_RATE_WINDOW = timedelta(minutes=5)


class RateLimiter:
    """Rate limiter in-memory, thread-safe via asyncio (single-threaded event loop)."""

    def __init__(self, window: timedelta = _RATE_WINDOW) -> None:
        self._window = window
        self._last_seen: Dict[str, datetime] = {}

    def is_allowed(self, key: str) -> bool:
        """Retorna True se a chave pode avançar; False se está dentro da janela."""
        now = datetime.now(timezone.utc)
        last = self._last_seen.get(key)
        if last is not None and (now - last) < self._window:
            logger.info(
                "auto_propose: rate-limit atingido para chave=%s "
                "(última decisão há %s)",
                key,
                now - last,
            )
            return False
        return True

    def record(self, key: str) -> None:
        """Regista que esta chave gerou uma Decision agora."""
        self._last_seen[key] = datetime.now(timezone.utc)

    def clear(self, key: str) -> None:
        """Remove entrada (para testes)."""
        self._last_seen.pop(key, None)
