"""Q.61.37 — structlog setup + trace_id processor.

Pina:
  * configure_structlog() corre sem crashar.
  * get_logger() devolve BoundLogger callable.
  * trace_id (Q.61.12 ContextVar) entra no event dict do log.
"""

from __future__ import annotations

import json
from io import StringIO
import logging
import structlog

from src.shared.observability import (
    configure_structlog,
    get_logger,
    reset_trace_id,
    set_trace_id,
)


def test_configure_structlog_is_idempotent():
    """Chamar varias vezes nao parte nada."""
    configure_structlog(json_logs=True)
    configure_structlog(json_logs=False)
    configure_structlog(json_logs=True)


def test_get_logger_returns_bound_logger():
    configure_structlog(json_logs=True)
    log = get_logger("test_q61_37")
    # BoundLogger expoe info/warning/error etc.
    assert callable(getattr(log, "info"))
    assert callable(getattr(log, "warning"))
    assert callable(getattr(log, "error"))


def test_trace_id_processor_includes_id_when_set():
    """Quando set_trace_id() esta active, o processor injecta-o."""
    from src.shared.observability import _add_trace_id_processor

    token = set_trace_id("trace-q61-37-abc")
    try:
        event = _add_trace_id_processor(None, "info", {"event": "hello"})
        assert event["trace_id"] == "trace-q61-37-abc"
        assert event["event"] == "hello"
    finally:
        reset_trace_id(token)


def test_trace_id_processor_omits_id_when_unset():
    """Sem trace_id no contexto, processor nao adiciona a key."""
    from src.shared.observability import _add_trace_id_processor

    # Sem `set_trace_id` activo.
    event = _add_trace_id_processor(None, "info", {"event": "hello"})
    assert "trace_id" not in event


def test_structlog_pipeline_emits_with_trace_id(caplog):
    """End-to-end: log via get_logger() inclui trace_id no output."""
    configure_structlog(json_logs=True)
    log = get_logger("e2e_q61_37")

    token = set_trace_id("e2e-trace-id-xyz")
    try:
        with caplog.at_level(logging.INFO, logger="e2e_q61_37"):
            log.info("test_event", key1="value1")
    finally:
        reset_trace_id(token)

    # caplog.text contem a representacao do registo final.
    # Como o pipeline acaba em JSONRenderer, a mensagem do LogRecord
    # e a string JSON.
    assert "trace_id" in caplog.text
    assert "e2e-trace-id-xyz" in caplog.text
    assert "test_event" in caplog.text
