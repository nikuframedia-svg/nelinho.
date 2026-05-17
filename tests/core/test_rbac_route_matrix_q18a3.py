"""Sprint Q.18.A.3 — close the fall-through gap on the route matrix.

After Q.18.A.2 the middleware enforces ROUTE_PREFIX_REQUIREMENTS, but
~9 routers had no entry and silently fell through. This test locks
the new entries so a future refactor can't quietly drop them.

The list mirrors the prefixes added in this sprint. If you legitimately
need to change a permission for one of these prefixes, update both the
matrix and this test in the same commit — the test failing without an
intentional matrix change means somebody dropped enforcement.
"""
from __future__ import annotations

import pytest

from src.shared.auth.rbac import (
    Permission,
    ROUTE_PREFIX_REQUIREMENTS,
    requirements_for_route,
)


# (prefix, sample_path, method, expected_permission)
EXPECTED = [
    ("/v1/twin",         "/v1/twin/scenarios",                  "POST",  Permission.SCENARIO_WRITE),
    ("/v1/sandbox",      "/v1/sandbox/scenarios/abc/publish",   "POST",  Permission.SCENARIO_WRITE),
    ("/v1/improve",      "/v1/improve/suggestions/x/approve",   "POST",  Permission.SCHEDULE_WRITE),
    ("/v1/supply",       "/v1/supply/forecast",                 "POST",  Permission.MRP_WRITE),
    ("/v1/explain",      "/v1/explain/decision/abc",            "GET",   Permission.SCHEDULE_READ),
    ("/v1/factory-map",  "/v1/factory-map/layout",              "GET",   Permission.MASTER_DATA_READ),
    ("/v1/factory",      "/v1/factory/datasets",                "GET",   Permission.MASTER_DATA_READ),
    ("/v1/runbooks",     "/v1/runbooks/list",                   "GET",   Permission.SCHEDULE_READ),
    ("/v1/tools",        "/v1/tools/registry",                  "GET",   Permission.SCHEDULE_READ),
    ("/v1/ml",           "/v1/ml/models",                       "GET",   Permission.SCHEDULE_READ),
    ("/v1/activity",     "/v1/activity/recent",                 "GET",   Permission.SCHEDULE_READ),
]


@pytest.mark.parametrize("prefix,path,method,expected", EXPECTED, ids=lambda v: str(v))
def test_prefix_resolves_to_expected_permission(prefix, path, method, expected):
    """Each Q.18.A.3 prefix resolves a sample path to the locked-in permission."""
    perms = requirements_for_route(path, method)
    assert perms is not None, f"matrix returned None for {method} {path}"
    assert expected in perms, (
        f"{method} {path} should require {expected.value}, got "
        f"{[p.value for p in perms]}"
    )


def test_no_q18a3_prefix_dropped():
    """All Q.18.A.3 prefixes must still be in the matrix."""
    matrix_prefixes = set(ROUTE_PREFIX_REQUIREMENTS.keys())
    for prefix, *_ in EXPECTED:
        assert prefix in matrix_prefixes, f"matrix dropped {prefix}"


# ---------------------------------------------------------------------------
# Method scoping — read-only entries reject write methods (must NOT match
# the read entry, otherwise an operator with read perms could POST).
# ---------------------------------------------------------------------------

def test_factory_map_post_does_not_match_read_entry():
    """``/v1/factory-map`` is GET-only. POST falls through (returns None)."""
    perms = requirements_for_route("/v1/factory-map/layout", "POST")
    assert perms is None, (
        "POST /v1/factory-map should fall through (no matrix entry), "
        f"but matrix returned {perms!r}"
    )


def test_explain_post_does_not_match_read_entry():
    """``/v1/explain`` is GET-only — POST must not silently use SCHEDULE_READ."""
    assert requirements_for_route("/v1/explain/whatever", "POST") is None


# ---------------------------------------------------------------------------
# Sanity: longest-prefix-wins still holds. /v1/governance/learning must
# resolve via the /v1/governance entry, not skip out to default.
# ---------------------------------------------------------------------------

def test_governance_subroute_inherits_governance_perm():
    perms = requirements_for_route("/v1/governance/learning/runs", "GET")
    assert perms is not None
    assert Permission.SCHEDULE_WRITE in perms
