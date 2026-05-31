"""Q.115.D — Debouncer assíncrono para auto-propose.

30s timeout por chave. Se um segundo evento chegar com a mesma chave
antes do timer disparar, o timer é cancelado e reiniciado. Só depois
dos 30s de silêncio é que o callback é invocado.

Evita criar múltiplas Decisions CPO para rafagas de eventos da mesma OF/barco.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any, Awaitable, Callable, Dict, Optional

logger = logging.getLogger(__name__)

_DEBOUNCE_SECONDS = 30


class Debouncer:
    """Agrupa eventos por chave com debounce asyncio.

    Args:
        delay_seconds: segundos de silêncio antes de invocar callback.
    """

    def __init__(self, delay_seconds: float = _DEBOUNCE_SECONDS) -> None:
        self._delay = delay_seconds
        self._tasks: Dict[str, asyncio.Task] = {}
        self._pending_payloads: Dict[str, Any] = {}

    async def debounce(
        self,
        key: str,
        payload: Any,
        callback: Callable[[str, Any], Awaitable[None]],
    ) -> None:
        """Agenda callback para daqui a `_delay` segundos.

        Se já existe task para esta chave, cancela-a e agenda nova.
        O payload mais recente é o que fica (último evento ganha).
        """
        existing = self._tasks.get(key)
        if existing and not existing.done():
            existing.cancel()
            logger.debug("debouncer: timer reset para chave=%s", key)

        self._pending_payloads[key] = payload

        async def _run() -> None:
            try:
                await asyncio.sleep(self._delay)
                saved_payload = self._pending_payloads.pop(key, None)
                self._tasks.pop(key, None)
                if saved_payload is not None:
                    await callback(key, saved_payload)
            except asyncio.CancelledError:
                pass

        task = asyncio.create_task(_run())
        self._tasks[key] = task

    def pending_keys(self) -> list[str]:
        """Devolve chaves com timers activos (para debug/testes)."""
        return [k for k, t in self._tasks.items() if not t.done()]

    async def flush(self, key: Optional[str] = None) -> None:
        """Para testes: cancela timers e invoca callbacks imediatamente.

        Se `key` é None, faz flush de todos.
        """
        keys = [key] if key else list(self._tasks.keys())
        for k in keys:
            t = self._tasks.pop(k, None)
            if t and not t.done():
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    pass
