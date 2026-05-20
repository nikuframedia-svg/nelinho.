"""
ProdPlan ONE — Sentry error reporting (Sprint Q.13.F / F.4)
============================================================

Optional Sentry wiring. Importing this module ALWAYS succeeds; whether
errors are actually reported depends on:

    1. The ``sentry-sdk`` package is installed (listed as an extra in
       requirements.txt; the core install does not pull it).
    2. The ``SENTRY_DSN`` env var is set.
    3. ``setup_error_reporting()`` is called from `main.py:lifespan`.

When any of those is missing, the module is a no-op: no SDK init, no
network calls, no overhead. Pairs with the OTel tracing module (B1)
to give the SRE team:

    * **OTel** answers "where in the request did it slow down".
    * **Sentry** answers "what raised, who, how often, with which
      release".

Why both
--------
OTel's exception captures are span events — useful for correlation
but not for the deduplicated, release-tagged, alert-routed view
Sentry provides out of the box. Mirrored release tags (``PRODPLAN_VERSION``)
let SRE pivot from a Sentry alert to the right git SHA.

Privacy
-------
Sentry's default scrubber redacts ``password``, ``secret``, ``token``
fields. We don't ship request bodies (``send_default_pii=False``) so a
copilot conversation transcript never leaves the cluster.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Module-level flag so callers can introspect whether reporting actually
# came up (for the /health/ready endpoint to report correctly).
ERROR_REPORTING_ACTIVE: bool = False


def _is_enabled() -> bool:
    """Sentry's standard env vars decide whether to set up.

    Honours ``SENTRY_DSN`` (must be set + non-empty) and
    ``SENTRY_ENABLED`` (boolean override; default True). When the DSN
    is unset, the module stays inert so dev machines don't take a
    startup penalty.
    """
    if os.getenv("SENTRY_ENABLED", "true").lower() in ("0", "false", "no"):
        return False
    return bool((os.getenv("SENTRY_DSN") or "").strip())


def setup_error_reporting() -> bool:
    """Install the Sentry SDK with the project's defaults.

    Called once from `main.py:lifespan` startup. Returns ``True`` when
    Sentry came up cleanly, ``False`` otherwise (deps missing, DSN
    unset, or runtime error). The boolean lets the caller log a single
    ``error_reporting=on/off`` line.

    Idempotent — calling twice is a no-op (the SDK's init records the
    last call's options but doesn't double-instrument).
    """
    global ERROR_REPORTING_ACTIVE

    if not _is_enabled():
        logger.info(
            "Sentry error reporting disabled (SENTRY_DSN unset or "
            "SENTRY_ENABLED=false)",
        )
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.asyncio import AsyncioIntegration
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except ImportError as exc:
        logger.warning(
            "Sentry SDK not installed (%s) — error reporting stays off. "
            "Install with: pip install 'sentry-sdk[fastapi]'", exc,
        )
        return False

    try:
        sentry_sdk.init(
            dsn=os.environ["SENTRY_DSN"],
            release=os.getenv("PRODPLAN_VERSION", "0.0.0-dev"),
            environment=os.getenv("ENVIRONMENT", "development"),
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            send_default_pii=False,
            attach_stacktrace=True,
            integrations=[
                AsyncioIntegration(),
                FastApiIntegration(transaction_style="endpoint"),
                StarletteIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
            ],
            before_send=_scrub_event,
        )
    except Exception as exc:
        logger.warning("Sentry init failed: %s — staying off", exc)
        return False

    ERROR_REPORTING_ACTIVE = True
    logger.info(
        "Sentry error reporting active: release=%s environment=%s",
        os.getenv("PRODPLAN_VERSION", "0.0.0-dev"),
        os.getenv("ENVIRONMENT", "development"),
    )
    return True


def _scrub_event(event: dict, _hint: dict) -> Optional[dict]:
    """Best-effort scrubber. The SDK's default scrubber covers
    common secret keys; we additionally drop request bodies because
    Copilot conversation transcripts may include factory-internal
    references the user didn't consent to ship.
    """
    try:
        request = event.get("request") or {}
        # Drop body — keep URL, method, headers (the SDK already
        # redacts authorization headers by default).
        if "data" in request:
            request["data"] = "<redacted>"
        if "json" in request:
            request["json"] = "<redacted>"
    except Exception:
        # Never let the scrubber drop the event on its own bug —
        # let it through; the default Sentry scrubbers still apply.
        return event
    return event


def is_active() -> bool:
    """True iff `setup_error_reporting` came up cleanly. Read-only."""
    return ERROR_REPORTING_ACTIVE


def capture_exception(exc: BaseException, **kwargs: Any) -> None:
    """Manual exception capture (for paths that swallow exceptions but
    still want to surface them in Sentry). No-op when reporting isn't
    active.
    """
    if not ERROR_REPORTING_ACTIVE:
        return
    try:
        import sentry_sdk
        sentry_sdk.capture_exception(exc, **kwargs)
    except Exception:  # noqa: S110  Reporting failure must NEVER cascade — call site already swallowed
        pass


__all__ = [
    "ERROR_REPORTING_ACTIVE",
    "capture_exception",
    "is_active",
    "setup_error_reporting",
]
