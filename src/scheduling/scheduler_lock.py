"""Q.61.35 — distributed scheduler lock via Postgres advisory locks.

Antes do Q.61.35, jobs como `_dpo_finetune_job` (~30 min, opcionalmente
GPU) e `_causal_discovery_job` (PCMCI+, ~45 min) corriam in-process num
unico uvicorn. Em multi-node OU em multi-worker dentro do mesmo node,
NADA impedia o mesmo job de correr 2× em paralelo:

  * Compute duplicado (caro, especialmente no DPO com GPU).
  * Race conditions nos writes (ML promotion, audit rows).

Q.61.35 instala um decorador leve:

    @with_advisory_lock("dpo_finetune")
    async def _dpo_finetune_job(tenant_id):
        ...

O decorador faz:
  1. Hash estavel do `lock_name` -> bigint (chave do advisory lock).
  2. `pg_try_advisory_lock(key)` — non-blocking; se outro processo
     ja tem o lock, devolve False.
  3. Se False: log "skipped — lock held" + return None (graceful).
  4. Se True: executa a fn; em `finally` liberta com
     `pg_advisory_unlock`.

Caracteristicas:
  * **Session-level lock** (nao xact) — sobrevive o tempo todo da
    funcao mesmo que esta nao esteja numa transaccao. Libertacao
    explicita ou ao fechar a connection.
  * **Tenant-aware**: por convencao chamada com lock_name incluindo
    tenant_id quando o job e per-tenant; lock GLOBAL para jobs como
    `nelo_erp_incremental_sync`.
  * **Postgres-only** — fora de Postgres (testes com SQLite/fakes)
    cai no fallback "sem lock" (loga warning, executa). Decisao
    consciente: o caso de teste nao precisa de lock real.
"""

from __future__ import annotations

import hashlib
import logging
from functools import wraps
from typing import Any, Awaitable, Callable, TypeVar

from sqlalchemy import text

from src.shared.database import engine

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _lock_key(name: str) -> int:
    """Hash estavel do `name` para um bigint compativel com
    `pg_try_advisory_lock(bigint)`. Postgres aceita int8 (-2^63..2^63-1);
    sha256 -> 8 primeiros bytes -> signed int64.
    """
    digest = hashlib.sha256(name.encode("utf-8")).digest()
    # Big-endian, signed; clamp ao range int64 para o driver aceitar.
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


async def _try_acquire(conn, key: int) -> bool:
    """Tenta acquire — devolve True/False. Postgres-only; falsy
    fallback noutros dialects."""
    try:
        result = await conn.scalar(
            text("SELECT pg_try_advisory_lock(:k)"), {"k": key},
        )
        return bool(result)
    except Exception as exc:
        # Q.61.35 defensivo: fora-de-Postgres (SQLite em testes) cai aqui.
        # `except Exception` deliberado — qualquer falha do driver e
        # equivalente a "lock nao disponivel" -> fallback executa sem lock.
        logger.warning(
            "advisory lock unavailable (likely non-Postgres engine: %s) "
            "- executing job WITHOUT lock", exc,
        )
        return True  # graceful fallback - testes nao tem PG


async def _release(conn, key: int) -> None:
    try:
        await conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": key})
    except Exception as exc:
        # Q.61.35 defensivo: unlock no fallback path nao tem efeito real.
        logger.debug("advisory unlock failed (ok in fallback path): %s", exc)


def with_advisory_lock(
    lock_name: str,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T | None]]]:
    """Decorator factory — cria um wrapper que adquire `pg_try_advisory_lock`
    antes de chamar a funcao. Se outro processo ja tem o lock, devolve None.

    Usage:

        @with_advisory_lock("dpo_finetune")
        async def _dpo_finetune_job(tenant_id):
            ...
    """
    key = _lock_key(lock_name)

    def decorator(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T | None]]:
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> T | None:
            # Connection separada para o lock — nao usa session pool
            # da request (lock e session-level, queremos vida = job).
            async with engine.connect() as conn:
                acquired = await _try_acquire(conn, key)
                if not acquired:
                    logger.info(
                        "job_skipped lock_held name=%s key=%d",
                        lock_name, key,
                    )
                    return None
                try:
                    return await fn(*args, **kwargs)
                finally:
                    await _release(conn, key)

        return wrapper

    return decorator


__all__ = ["with_advisory_lock"]
