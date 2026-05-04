"""Sprint Q.13.G — Sentry error_reporting graceful-fallback tests.

Mirrors `test_tracing_q13b.py` for the Sentry side. The error
reporting module MUST be a no-op in three distinct conditions:

  1. ``SENTRY_DSN`` env var unset (the default for dev).
  2. ``SENTRY_ENABLED=false`` (operator opt-out).
  3. ``sentry-sdk`` not installed (dev box without optional dep).

A regression in any of those would either crash startup OR send
copilot-conversation transcripts to Sentry without operator consent.
"""

from __future__ import annotations

import importlib
import sys


def _reload_module() -> object:
    """Reload `src.shared.error_reporting` so module globals reset
    between tests (`setup_error_reporting` is idempotent + sets
    ERROR_REPORTING_ACTIVE)."""
    if "src.shared.error_reporting" in sys.modules:
        return importlib.reload(sys.modules["src.shared.error_reporting"])
    import src.shared.error_reporting as e
    return e


def test_setup_no_op_when_dsn_unset(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    monkeypatch.delenv("SENTRY_ENABLED", raising=False)
    err = _reload_module()
    assert err.setup_error_reporting() is False
    assert err.is_active() is False


def test_setup_no_op_when_dsn_blank(monkeypatch):
    """Empty-string DSN is treated identically to unset — operators
    using a CI/CD config that emits ``SENTRY_DSN=`` shouldn't get a
    crash, just a clean disable."""
    monkeypatch.setenv("SENTRY_DSN", "")
    err = _reload_module()
    assert err.setup_error_reporting() is False
    assert err.is_active() is False


def test_setup_no_op_when_explicitly_disabled(monkeypatch):
    """``SENTRY_ENABLED=false`` overrides a set DSN. Useful for SREs
    who want to keep the DSN in CI/CD config but pause reporting on a
    specific environment without unsetting the DSN everywhere."""
    monkeypatch.setenv("SENTRY_DSN", "https://fake@sentry.io/1")
    monkeypatch.setenv("SENTRY_ENABLED", "false")
    err = _reload_module()
    assert err.setup_error_reporting() is False
    assert err.is_active() is False


def test_setup_handles_missing_deps_gracefully(monkeypatch):
    """When SENTRY_DSN is set but sentry-sdk isn't installed,
    setup_error_reporting returns False + logs a hint instead of
    crashing the lifespan startup."""
    monkeypatch.setenv("SENTRY_DSN", "https://fake@sentry.io/1")
    monkeypatch.delenv("SENTRY_ENABLED", raising=False)
    err = _reload_module()

    # Block the sentry_sdk import so the try/except path fires.
    blocked_modules = [m for m in list(sys.modules) if m.startswith("sentry_sdk")]
    for m in blocked_modules:
        sys.modules[m] = None  # type: ignore[assignment]

    real_import = (
        __builtins__["__import__"]
        if isinstance(__builtins__, dict)
        else __builtins__.__import__
    )

    def _block_sentry(name, *a, **kw):
        if name.startswith("sentry_sdk"):
            raise ImportError(f"simulated missing module: {name}")
        return real_import(name, *a, **kw)

    if isinstance(__builtins__, dict):
        __builtins__["__import__"] = _block_sentry
    else:
        monkeypatch.setattr(__builtins__, "__import__", _block_sentry)

    try:
        result = err.setup_error_reporting()
        assert result is False
        assert err.is_active() is False
    finally:
        if isinstance(__builtins__, dict):
            __builtins__["__import__"] = real_import


def test_capture_exception_no_op_when_inactive(monkeypatch):
    """`capture_exception` is the manual-capture surface for paths
    that swallow errors. When reporting is OFF it must NOT raise — a
    swallow-and-still-blow-up would be the worst-case bug."""
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    err = _reload_module()
    # No exception, no SDK call, no return value mismatch.
    err.capture_exception(RuntimeError("test"))
    assert err.is_active() is False


def test_scrub_event_redacts_request_bodies():
    """Direct unit test for the body scrubber. The default Sentry
    scrubbers handle auth headers; we additionally drop request bodies
    because Copilot transcripts may carry factory-internal references
    the user didn't consent to ship."""
    from src.shared.error_reporting import _scrub_event

    event = {
        "message": "exception",
        "request": {
            "url": "/v1/copilot/ask",
            "method": "POST",
            "data": {"question": "secret prompt"},
            "json": {"question": "another secret"},
        },
    }
    cleaned = _scrub_event(event, {})
    assert cleaned is not None
    assert cleaned["request"]["data"] == "<redacted>"
    assert cleaned["request"]["json"] == "<redacted>"
    # URL + method preserved (they're legitimate triage info).
    assert cleaned["request"]["url"] == "/v1/copilot/ask"
    assert cleaned["request"]["method"] == "POST"


def test_scrub_event_handles_missing_request_field():
    """Events without a `request` key (e.g. background-job exceptions)
    must pass through cleanly — the scrubber must not assume request
    shape."""
    from src.shared.error_reporting import _scrub_event

    event = {"message": "background job failed", "level": "error"}
    cleaned = _scrub_event(event, {})
    assert cleaned == event  # untouched
