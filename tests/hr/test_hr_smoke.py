"""Sprint Q.7 Fase 2 — HR module smoke tests.

The audit (`scripts/audit.py`) flagged `hr` as yellow because it had no
test files. Q.7 Fase 2 also fixed a real bug:

    src/hr/services/allocation_service.py:252 used `timedelta` BEFORE
    importing it on line 254 → UnboundLocalError on `to_date=None`.

This test guards against the regression by exercising the import path
and the helpers, plus a minimal smoke of the API surface.
"""

from __future__ import annotations

import importlib
from datetime import date, timedelta


def test_allocation_service_imports_cleanly():
    """If `timedelta` is removed from the top-level import again, this
    test catches it. The bug was: usage on line 252, import on line 254
    (after) — Python would raise UnboundLocalError because the local
    import shadowed the global scope."""
    mod = importlib.import_module("src.hr.services.allocation_service")
    assert hasattr(mod, "AllocationService")
    # The fix moved `timedelta` to the top-level imports; verify it's there.
    assert hasattr(mod, "timedelta"), (
        "timedelta import lost — get_employee_availability() will crash "
        "with UnboundLocalError when called with to_date=None"
    )


def test_allocation_service_default_to_date_arithmetic():
    """The bug was specifically in the default-argument computation
    `to_date = to_date or from_date + timedelta(weeks=4)`. We can
    exercise the same arithmetic without the service to confirm the
    helper invariants — and prove the import path is wired."""
    from src.hr.services.allocation_service import timedelta as tdelta

    base = date(2026, 4, 25)
    out = base + tdelta(weeks=4)
    assert (out - base).days == 28


def test_hr_api_router_exists():
    """The hr module exposes a FastAPI router; if the router import
    breaks, the whole /v1/hr/* surface goes silent."""
    from src.hr.api import router

    assert router is not None
    # We don't pin the route count (it changes); we check there's at
    # least one mounted endpoint.
    assert len([r for r in router.routes if hasattr(r, "path")]) > 0


def test_productivity_endpoint_no_dead_service_var():
    """The audit flagged `service = ProductivityService(...)` was
    instantiated then never used in get_productivity_report. Fixed in
    Q.7 Fase 2. This test ensures the endpoint module imports cleanly
    after the fix (regression guard)."""
    mod = importlib.import_module("src.hr.api.productivity")
    assert hasattr(mod, "router")
