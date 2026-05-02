"""Sprint Q.13.B (B1) — OpenTelemetry tracing graceful-fallback tests.

The tracing module MUST be a no-op in 3 distinct conditions:
  1. ``OTEL_TRACES_EXPORTER`` env var unset (the default for dev)
  2. ``OTEL_SDK_DISABLED=true`` (operator opt-out)
  3. ``opentelemetry-*`` packages not installed (dev machine without extras)

Any of those failing turns a quiet add-tracing-later op into a startup
crash, which is the exact opposite of the design intent.
"""

from __future__ import annotations

import importlib
import sys


class _FakeApp:
    """Stand-in FastAPI app for setup_tracing — only checked for type
    by the auto-instrumentor, which doesn't run when tracing is off."""


def _reload_tracing() -> object:
    """Reload the module so the TRACING_ACTIVE module global resets
    between tests. setup_tracing's idempotency check makes that
    necessary."""
    if "src.shared.tracing" in sys.modules:
        return importlib.reload(sys.modules["src.shared.tracing"])
    import src.shared.tracing as t
    return t


def test_setup_tracing_no_op_when_env_var_unset(monkeypatch):
    monkeypatch.delenv("OTEL_TRACES_EXPORTER", raising=False)
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    tracing = _reload_tracing()
    assert tracing.setup_tracing(_FakeApp()) is False
    assert tracing.is_active() is False


def test_setup_tracing_no_op_when_sdk_disabled(monkeypatch):
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "otlp")
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    tracing = _reload_tracing()
    assert tracing.setup_tracing(_FakeApp()) is False
    assert tracing.is_active() is False


def test_setup_tracing_no_op_on_explicit_none(monkeypatch):
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "none")
    tracing = _reload_tracing()
    assert tracing.setup_tracing(_FakeApp()) is False


def test_shutdown_tracing_no_op_when_inactive(monkeypatch):
    monkeypatch.delenv("OTEL_TRACES_EXPORTER", raising=False)
    tracing = _reload_tracing()
    # Should not raise even though setup was never called.
    tracing.shutdown_tracing()


def test_setup_tracing_handles_missing_deps_gracefully(monkeypatch):
    """When OTEL_TRACES_EXPORTER is set but opentelemetry isn't
    installed, setup_tracing returns False + logs a hint instead of
    crashing the lifespan startup."""
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "otlp")
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    tracing = _reload_tracing()

    # Block the opentelemetry import so the try/except path fires.
    blocked_modules = [
        m for m in list(sys.modules) if m.startswith("opentelemetry")
    ]
    for m in blocked_modules:
        sys.modules[m] = None  # type: ignore[assignment]

    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def _block_otel(name, *a, **kw):
        if name.startswith("opentelemetry"):
            raise ImportError(f"simulated missing module: {name}")
        return real_import(name, *a, **kw)

    if isinstance(__builtins__, dict):
        __builtins__["__import__"] = _block_otel
    else:
        monkeypatch.setattr(__builtins__, "__import__", _block_otel)

    try:
        result = tracing.setup_tracing(_FakeApp())
        assert result is False
        assert tracing.is_active() is False
    finally:
        if isinstance(__builtins__, dict):
            __builtins__["__import__"] = real_import
