"""Q.62.B.2 — ContextVar para o tenant_id da request actual.

Funciona em pareceria com:
  * `src/shared/database.py` event listener (`SET LOCAL app.tenant_id`).
  * `TenantContextMiddleware` (em `src/main.py`).
  * Migration `056_q62_b_rls_enable` (politicas Postgres RLS).

Quando o middleware FastAPI extrai `X-Tenant-Id` (ou JWT) e chama
`set_tenant_id(uuid)`, o event listener "begin" da engine sync injecta
`SET LOCAL app.tenant_id = '<uuid>'` em cada nova transacao. As
policies RLS criadas em 056 filtram queries automaticamente.

Background tasks (scheduler, ETL adapters) DEVEM chamar
`set_tenant_id` explicitamente antes de queries — senao o RLS rejeita
tudo (current_setting devolve string vazia, nao casa com UUID).

API:
  * `current_tenant_id_var` — ContextVar (use directly em legacy code).
  * `set_tenant_id(uuid)` — devolve Token (para reset).
  * `get_tenant_id()` — devolve UUID actual ou None.
  * `reset_tenant_id(token)` — restaura ao valor anterior ao set.
  * `tenant_scope(uuid)` — context manager idiomatico.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator, Optional
from uuid import UUID


# ContextVar — async-safe; cada Task tem o seu valor isolado.
current_tenant_id_var: ContextVar[Optional[UUID]] = ContextVar(
    "nelinho_tenant_id", default=None,
)


def set_tenant_id(value: Optional[UUID]) -> Token:
    """Define o tenant_id no contexto actual e devolve token (para reset)."""
    return current_tenant_id_var.set(value)


def get_tenant_id() -> Optional[UUID]:
    """Devolve o tenant_id da request actual, ou None."""
    return current_tenant_id_var.get()


def reset_tenant_id(token: Token) -> None:
    """Restaura ao valor anterior ao set."""
    current_tenant_id_var.reset(token)


@contextmanager
def tenant_scope(tenant_id: Optional[UUID]) -> Iterator[None]:
    """Context manager — set + reset automatico.

    Uso em background tasks::

        from src.shared.auth.tenant_context import tenant_scope

        async def my_job(tenant_id: UUID):
            with tenant_scope(tenant_id):
                async with get_session_context() as session:
                    ...  # RLS filtra para este tenant
    """
    token = set_tenant_id(tenant_id)
    try:
        yield
    finally:
        reset_tenant_id(token)
