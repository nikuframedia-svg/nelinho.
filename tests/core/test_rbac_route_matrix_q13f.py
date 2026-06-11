"""Sprint Q.13.F F.2 — RBAC route-prefix matrix tests.

Plan v4 §11.2: every route must map to a permission and the matrix
must be enumerable + lockable. These tests pin:

  * Admin can hit everything (`ADMIN_PLATFORM` has all perms).
  * Operator can hit `/v1/operador/*` and `/v1/quality/rework/*`
    but is locked out of master-data writes + governance.
  * CEO is read-only on the dashboard surface; never writes; never
    sees tenant-config or governance.
  * Most-specific prefix wins (e.g. `/v1/plan/preview-delta` does NOT
    fall to `/v1/plan` rules).
  * Method scope: a `(GET,)`-only entry rejects POSTs with the same
    permission set.
  * Routes not in the matrix return `None` (deferred to per-route
    decorator) — the absence is a deliberate gradual-rollout feature.
"""

from __future__ import annotations

import pytest

from src.shared.auth.rbac import (
    ROUTE_PREFIX_REQUIREMENTS,
    Permission,
    Role,
    is_route_allowed_for_role,
    requirements_for_route,
)


# ───────────────────────────────────────────────────────────────────────────
# Matrix structure invariants
# ───────────────────────────────────────────────────────────────────────────


def test_matrix_is_non_empty_and_well_typed():
    assert ROUTE_PREFIX_REQUIREMENTS, "route matrix must not be empty"
    for prefix, (methods, perms) in ROUTE_PREFIX_REQUIREMENTS.items():
        assert prefix.startswith("/v1/"), f"prefix '{prefix}' must be under /v1/"
        assert isinstance(methods, tuple), f"methods for {prefix} must be a tuple"
        assert perms, f"prefix {prefix} must require at least one permission"
        for p in perms:
            assert isinstance(p, Permission), f"non-Permission in {prefix}"


# ───────────────────────────────────────────────────────────────────────────
# Most-specific prefix wins
# ───────────────────────────────────────────────────────────────────────────


def test_specific_prefix_wins_over_general():
    """`/v1/plan/preview-delta/some-id` must match the preview-delta
    entry, NOT fall through to `/v1/plan/cpo` or any other prefix."""
    perms = requirements_for_route("/v1/plan/preview-delta/op-123", "POST")
    assert perms == [Permission.SCHEDULE_WRITE]


def test_capacity_route_is_get_only():
    """`/v1/plan/capacity` is `(GET,)` — POST must NOT match it."""
    assert requirements_for_route("/v1/plan/capacity/m-1", "GET") == [
        Permission.CAPACITY_READ
    ]
    # POST falls through to /v1/plan/cpo or to None
    fallback = requirements_for_route("/v1/plan/capacity/m-1", "POST")
    # Either explicit other prefix matches OR no prefix does — but it
    # must NOT have matched the GET-only entry.
    if fallback is not None:
        assert fallback != [Permission.CAPACITY_READ]


def test_unmatched_route_returns_none():
    """Unmatched paths defer to the per-route decorator (gradual
    rollout). Must NOT default-deny silently."""
    assert requirements_for_route("/v1/some-new-experimental-area", "GET") is None


# ───────────────────────────────────────────────────────────────────────────
# Role-level access tests
# ───────────────────────────────────────────────────────────────────────────


def test_admin_platform_can_access_everything():
    """Admin has all perms (`set(Permission)`); every matrix entry
    must be reachable for them."""
    for prefix, (methods, _perms) in ROUTE_PREFIX_REQUIREMENTS.items():
        method = methods[0] if methods else "POST"
        assert is_route_allowed_for_role(
            prefix + "/anything", method, Role.ADMIN_PLATFORM.value,
        ), f"ADMIN should access {prefix} {method}"


def test_operator_limited_to_operador_and_quality_rework():
    op = Role.OPERATOR.value
    # Allowed surfaces
    assert is_route_allowed_for_role("/v1/operador/queue", "GET", op)
    assert is_route_allowed_for_role("/v1/quality/rework/123", "POST", op)
    # Forbidden — operator cannot write master data
    assert not is_route_allowed_for_role("/v1/core/customers", "POST", op)
    # Forbidden — operator cannot run CPO
    assert not is_route_allowed_for_role("/v1/plan/cpo/schedule", "POST", op)
    # Forbidden — operator cannot touch governance
    assert not is_route_allowed_for_role(
        "/v1/governance/decisions", "POST", op,
    )


def test_ceo_is_read_only_on_dashboard():
    ceo = Role.CEO.value
    # CEO can GET the dashboard surface
    assert is_route_allowed_for_role(
        "/v1/profit/dashboard", "GET", ceo,
    )
    assert is_route_allowed_for_role(
        "/v1/profit/throughput", "GET", ceo,
    )
    # CEO can read scenarios
    assert is_route_allowed_for_role("/v1/profit/scenarios/sc-1", "GET", ceo)
    # CEO must NOT write master data
    assert not is_route_allowed_for_role("/v1/core/customers", "POST", ceo)
    # CEO must NOT run CPO
    assert not is_route_allowed_for_role(
        "/v1/plan/cpo/schedule", "POST", ceo,
    )
    # CEO must NOT touch tenant config (Q.173.K — prefixo real /v1/config)
    assert not is_route_allowed_for_role(
        "/v1/config/planning/scope", "POST", ceo,
    )


def test_unknown_role_is_denied_for_matrix_routes():
    """An unknown / future role must NOT default to allow on a
    matrix-covered route — has_any_permission returns False for
    unrecognised roles."""
    assert not is_route_allowed_for_role(
        "/v1/core/customers", "POST", "future_role_does_not_exist",
    )


def test_unknown_role_passes_unmatched_routes():
    """Unmatched paths return None from `requirements_for_route`, and
    `is_route_allowed_for_role` treats that as 'allow' so the
    decorator layer can still gate."""
    assert is_route_allowed_for_role(
        "/v1/some-new-experimental-area", "GET",
        "future_role_does_not_exist",
    )


def test_planner_supply_can_run_cpo_but_not_change_master_data():
    planner = Role.PLANNER_SUPPLY.value
    assert is_route_allowed_for_role(
        "/v1/plan/cpo/schedule", "POST", planner,
    )
    # Planner can read master data but the matrix gates writes
    assert not is_route_allowed_for_role(
        "/v1/core/customers", "POST", planner,
    )


def test_q173k_config_mutations_exigem_config_write():
    """Q.173.K — o prefixo real /v1/config está na matriz para mutações.

    A auditoria 2026-06-11 encontrou a matriz a proteger /v1/core/config,
    prefixo que NENHUM router usa — PUT/POST de configuração passavam pelo
    fall-through sem CONFIG_WRITE.
    """
    from src.shared.auth.rbac import Permission, requirements_for_route

    for method in ("POST", "PUT", "PATCH", "DELETE"):
        req = requirements_for_route("/v1/config/planning/scope", method)
        assert req == [Permission.CONFIG_WRITE], (method, req)
    # GET fica fora da matriz de propósito (UI de todas as roles lê config;
    # tenant-header gate continua).
    assert requirements_for_route("/v1/config/transporte/truck", "GET") is None
    # As entradas mortas saíram — nenhum router usa estes prefixos.
    from src.shared.auth.rbac import ROUTE_PREFIX_REQUIREMENTS

    assert "/v1/core/config" not in ROUTE_PREFIX_REQUIREMENTS
    assert "/v1/core/tenant-config" not in ROUTE_PREFIX_REQUIREMENTS


def test_q173k_revenue_target_post_coberto():
    """POST /v1/config/revenue-target (q115) também fica sob a matriz."""
    from src.shared.auth.rbac import Permission, requirements_for_route

    assert requirements_for_route(
        "/v1/config/revenue-target", "POST",
    ) == [Permission.CONFIG_WRITE]
