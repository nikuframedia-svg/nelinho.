"""Q.61.12 — trace_id end-to-end.

Frontend `lib/api/client.ts` injecta `X-Request-Id`. Esta camada extrai
no middleware HTTP, mete em `contextvars`, e os call-sites (logs,
audit, outbox event) leem daqui. Resultado: 1 HTTP request →
trace_id consistente em todos os logs/eventos.

Q.61.12 cobre o esqueleto:
  * `trace_id_var` ContextVar (async-safe).
  * `get_trace_id()` / `set_trace_id()` helpers.
  * `TraceIdMiddleware` (ASGI BaseHTTPMiddleware) que extrai header
    `X-Request-Id` ou gera UUID novo, faz set+token, ecoa em
    response.headers["X-Request-Id"].
  * `TraceIdLogFilter` que anexa `trace_id` a cada LogRecord.

Q.61.37 (Vaga 8) substitui logging stdlib por structlog + OTel; ai
o `add_trace_id` vira processor structlog e este filter sai. Ate la,
este modulo basta para correlacionar HTTP request -> logs.
"""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# ContextVar — async-safe; cada Task tem o seu valor isolado.
_trace_id_var: ContextVar[Optional[str]] = ContextVar(
    "nelinho_trace_id", default=None,
)


def get_trace_id() -> Optional[str]:
    """Devolve o trace_id da request actual, ou None se nao houver."""
    return _trace_id_var.get()


def set_trace_id(value: Optional[str]):
    """Define o trace_id no contexto actual e devolve o token (para reset)."""
    return _trace_id_var.set(value)


def reset_trace_id(token) -> None:
    """Restaura o trace_id ao valor anterior ao set."""
    _trace_id_var.reset(token)


HEADER = "X-Request-Id"


class TraceIdMiddleware(BaseHTTPMiddleware):
    """Extrai X-Request-Id do header (ou gera UUID), set ContextVar,
    ecoa no response header.

    Comportamento:
      * Se o cliente enviou `X-Request-Id` valido (str nao vazia), usa
        esse valor.
      * Senao, gera `uuid.uuid4().hex` (32 chars, sem hifens).
      * Apos a request, `reset` para nao vazar entre requests.
    """

    async def dispatch(self, request: Request, call_next):
        incoming = request.headers.get(HEADER) or request.headers.get(HEADER.lower())
        trace_id = incoming if incoming else uuid.uuid4().hex
        token = set_trace_id(trace_id)
        try:
            response: Response = await call_next(request)
        finally:
            reset_trace_id(token)
        # Echo no response — cliente pode correlacionar com network logs.
        response.headers[HEADER] = trace_id
        return response


class TraceIdLogFilter(logging.Filter):
    """Anexa `trace_id` a cada LogRecord (vazio se nao houver).

    Activar via:
        handler.addFilter(TraceIdLogFilter())
        formatter = logging.Formatter("%(asctime)s [%(trace_id)s] %(message)s")
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = _trace_id_var.get() or "-"
        return True


__all__ = [
    "HEADER",
    "TraceIdLogFilter",
    "TraceIdMiddleware",
    "get_trace_id",
    "reset_trace_id",
    "set_trace_id",
]
