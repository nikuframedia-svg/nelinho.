"""
ProdPlan ONE — OpenTelemetry tracing (Sprint Q.13.B / B1)
==========================================================

Optional OTLP wiring. Importing this module ALWAYS succeeds; whether
tracing is actually emitted depends on:

    1. The ``opentelemetry-*`` packages are installed (they are listed
       as extras in `requirements.txt`; the core install does not pull
       them so a developer machine can run without).
    2. The ``OTEL_TRACES_EXPORTER`` env var is set (e.g. ``otlp`` or
       ``console``) — the standard OTel switch.
    3. ``setup_tracing(app)`` is called from `main.py:lifespan` at
       startup.

When any of those is missing, the module is a no-op: tracing calls
do nothing, no spans emitted, no overhead. This is the explicit
graceful-degradation contract — the production deploy can adopt
tracing incrementally without forcing a re-install on every dev
machine.

What gets instrumented (when active)
-------------------------------------

* **FastAPI** — every request becomes a parent span with the route
  template, status code, method, duration. Auto-correlated with
  `prodplan_http_requests_total` via shared trace_id.
* **SQLAlchemy / asyncpg** — every DB statement becomes a child span
  with the query text (sampled), duration, rows. Combined with the
  Postgres slow-query log (B2), gives the "this query was slow on
  this request" trace.
* **httpx** — outbound calls (Ollama, ERP adapter) are traced too.

What's NOT auto-instrumented yet
---------------------------------

* Kafka producer/consumer span propagation — the OTel instrumentor
  exists but Kafka context propagation through async outbox is
  fiddly enough to defer to a follow-up.
* APScheduler jobs — the scheduler runs jobs in its own threadpool;
  OTel context doesn't propagate without explicit hooks.

Both are tracked as Onda 2 / Onda 3 of Fase B in the plan.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Module-level flag so callers can introspect whether tracing actually
# came up (for the /health/ready endpoint to report correctly).
TRACING_ACTIVE: bool = False


def _is_enabled() -> bool:
    """OpenTelemetry's standard env vars decide whether to set up.

    We honour ``OTEL_SDK_DISABLED`` (boolean) and
    ``OTEL_TRACES_EXPORTER`` (must be set + non-"none"). When neither
    is set, the module stays inert so dev machines without OTel
    installed don't take a startup penalty.
    """
    if os.getenv("OTEL_SDK_DISABLED", "").lower() == "true":
        return False
    exporter = (os.getenv("OTEL_TRACES_EXPORTER", "") or "").strip().lower()
    return exporter not in ("", "none")


def setup_tracing(app: Any) -> bool:
    """Install OTel TracerProvider + auto-instrument.

    Called once from `main.py:lifespan` startup. Returns ``True`` when
    tracing came up cleanly, ``False`` otherwise (deps missing,
    exporter unconfigured, or runtime error). The boolean lets the
    caller log a single ``tracing=on/off`` line.

    Idempotent — calling twice is a no-op (the SDK's set_tracer_provider
    refuses to override an existing one).
    """
    global TRACING_ACTIVE

    if not _is_enabled():
        logger.info("OpenTelemetry tracing disabled (OTEL_TRACES_EXPORTER unset)")
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:
        logger.warning(
            "OpenTelemetry packages not installed (%s) — tracing stays off. "
            "Install with: pip install opentelemetry-distro "
            "opentelemetry-exporter-otlp opentelemetry-instrumentation-fastapi "
            "opentelemetry-instrumentation-sqlalchemy "
            "opentelemetry-instrumentation-asyncpg "
            "opentelemetry-instrumentation-httpx",
            exc,
        )
        return False

    # Service identity. Picked up by the collector / Jaeger / Tempo
    # so traces from this app are tagged consistently.
    resource = Resource.create({
        "service.name": os.getenv("OTEL_SERVICE_NAME", "prodplan-api"),
        "service.version": os.getenv("PRODPLAN_VERSION", "1.0.0"),
        "deployment.environment": os.getenv("ENVIRONMENT", "development"),
    })

    provider = TracerProvider(resource=resource)
    # OTLPSpanExporter reads OTEL_EXPORTER_OTLP_ENDPOINT (default
    # http://localhost:4317 grpc) so no endpoint needs to be passed
    # here — operators set it in env.
    exporter = OTLPSpanExporter()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Auto-instrument FastAPI: every request becomes a parent span.
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor().instrument_app(app)
    except Exception as exc:
        logger.warning("OTel FastAPI instrument failed: %s", exc)

    # Auto-instrument SQLAlchemy + asyncpg: every DB statement is a
    # child span correlated to the parent request.
    try:
        from opentelemetry.instrumentation.sqlalchemy import (
            SQLAlchemyInstrumentor,
        )
        SQLAlchemyInstrumentor().instrument()
    except Exception as exc:
        logger.warning("OTel SQLAlchemy instrument failed: %s", exc)

    # Auto-instrument httpx: outbound calls (Ollama, ERP) get their
    # own child spans.
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        HTTPXClientInstrumentor().instrument()
    except Exception as exc:
        logger.warning("OTel httpx instrument failed: %s", exc)

    TRACING_ACTIVE = True
    logger.info(
        "OpenTelemetry tracing active: service=%s endpoint=%s",
        resource.attributes.get("service.name"),
        os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "<default localhost:4317>"),
    )
    return True


def is_active() -> bool:
    """True iff `setup_tracing` came up cleanly. Read-only."""
    return TRACING_ACTIVE


def shutdown_tracing() -> None:
    """Flush pending spans before process exit. No-op when tracing
    isn't active. Called from `main.py:lifespan` shutdown.

    The OTel SDK's BatchSpanProcessor buffers spans in memory; without
    an explicit flush, spans for the last second of traffic are lost
    on hard shutdown. With B5's 30s graceful window, this fits.
    """
    if not TRACING_ACTIVE:
        return

    try:
        from opentelemetry import trace
        provider = trace.get_tracer_provider()
        # All built-in providers expose `force_flush`; user-supplied
        # ones may not — guard.
        flush = getattr(provider, "force_flush", None)
        if callable(flush):
            flush(timeout_millis=5000)
    except Exception as exc:
        logger.warning("OTel flush failed at shutdown: %s", exc)


__all__ = [
    "TRACING_ACTIVE",
    "is_active",
    "setup_tracing",
    "shutdown_tracing",
]
