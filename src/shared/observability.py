"""Q.61.12 + Q.61.37 — trace_id end-to-end + structlog.

Q.61.12 instalou:
  * `trace_id_var` ContextVar (async-safe).
  * `get_trace_id()` / `set_trace_id()` helpers.
  * `TraceIdMiddleware` (ASGI BaseHTTPMiddleware) que extrai header
    `X-Request-Id` ou gera UUID novo, faz set+token, ecoa em
    response.headers["X-Request-Id"].
  * `TraceIdLogFilter` que anexa `trace_id` a cada LogRecord stdlib.

Q.61.37 adiciona structlog setup:
  * `configure_structlog()` instala o pipeline com:
      - timestamp ISO
      - log level
      - trace_id processor (le do ContextVar)
      - JSON renderer (machine-parsable; OTel-ready)
  * `get_logger(name)` devolve um structlog BoundLogger.
  * Logging stdlib continua a funcionar (compat) — call-sites com
    `logging.getLogger(__name__)` ganham trace_id via filter.

Migracao de call-sites e touched-file pays — nao mexer em massa
(Karpathy failure mode #3).
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


# ─── Q.61.37 — structlog setup ────────────────────────────────────────


def _add_trace_id_processor(_logger, _method_name, event_dict):
    """structlog processor — injecta trace_id (Q.61.12 ContextVar)
    em cada event dict.

    Tipos compativeis com structlog.types.Processor.
    """
    tid = _trace_id_var.get()
    if tid is not None:
        event_dict["trace_id"] = tid
    return event_dict


def configure_structlog(json_logs: bool = True) -> None:
    """Q.61.37 — instala o pipeline structlog.

    Idempotente — chamar varias vezes nao parte nada.

    Args:
        json_logs: True (default) renderiza para JSON (production).
            False usa ConsoleRenderer (dev local — mais legivel).
    """
    import structlog

    renderer = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _add_trace_id_processor,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None):
    """Q.61.37 — devolve structlog BoundLogger.

    Uso:
        from src.shared.observability import get_logger
        logger = get_logger(__name__)
        logger.info("event_name", key1="value1", entity_id=str(eid))

    Equivalente a logging.getLogger() em compat (BoundLogger emite via
    stdlib handlers no fim do pipeline).
    """
    import structlog
    return structlog.get_logger(name)


__all__ = [
    "HEADER",
    "TraceIdLogFilter",
    "TraceIdMiddleware",
    "configure_structlog",
    "get_logger",
    "get_trace_id",
    "reset_trace_id",
    "set_trace_id",
]
