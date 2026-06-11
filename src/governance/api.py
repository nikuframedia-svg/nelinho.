"""
Governance API — aggregator
============================

Q.67.6.B5 — this file used to be a 948L router carrying ~20 endpoints. It is
now a thin aggregator that mounts six sub-routers (each ≤500L) plus the two
pre-existing siblings (yaml_policy + audit_log).

Sub-routers live in :mod:`src.governance.routers`:

* :mod:`.routers.policies`     — GET /policies + /policies/{type}.
* :mod:`.routers.decisions`    — propose / approve / get / list / pending/me
  / audit-pack / execute / rollback / payload-patch / kill-switch
  / delta.
* :mod:`.routers.timeline`     — /decisions/timeline + /audit/timeline.
* :mod:`.routers.rbac`         — /rbac/matrix.
* :mod:`.routers.rule_firings` — /rule-firings + adoption + outcome PATCH.
* :mod:`.routers.event_outbox` — /event-outbox.

External callers import :attr:`router`, :func:`get_governance_service` and
:func:`get_tenant_id` from this module — they are re-exported here for
back-compat so the 45-test characterization safety net + every existing
``from src.governance.api import ...`` keeps working.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

# Re-export dependencies + service-level symbols (tests + external code
# import these from this module).
from .routers._dependencies import (
    get_current_user,
    get_governance_service,
    get_tenant_id,
)

# Mount sub-routers
from .audit_log_api import router as _audit_log_router
from .routers.decisions import router as _decisions_router
from .routers.event_outbox import router as _event_outbox_router
from .routers.policies import router as _policies_router
from .routers.rbac import router as _rbac_router
from .routers.rule_firings import (
    RuleFiringOutcomeUpdate,
    RuleFiringResponse,
    list_rule_firings,
    router as _rule_firings_router,
    update_rule_firing_outcome,
)
from .routers.timeline import router as _timeline_router
from .yaml_policy.api import router as _yaml_policy_router

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/governance", tags=["Governance"])

# Decision lifecycle endpoints (propose/approve/execute/rollback/...).
router.include_router(_decisions_router)
# Policy lookup.
router.include_router(_policies_router)
# Pending/audit timeline read-side.
router.include_router(_timeline_router)
# RBAC matrix viewer.
router.include_router(_rbac_router)
# Rule firing audit log (Q.14.A + Q.14.C adoption).
router.include_router(_rule_firings_router)
# Generic event-outbox viewer (Onda 14 N).
router.include_router(_event_outbox_router)
# Q.17.C — yaml_policy sub-router (NL→YAML rule authoring + lifecycle).
router.include_router(_yaml_policy_router)
# Q.61.19 — audit_log sub-router (GET /v1/governance/audit-logs).
router.include_router(_audit_log_router)


__all__ = [
    "router",
    "get_current_user",
    "get_governance_service",
    "get_tenant_id",
    # Re-exports for tests / external callers that pin to the legacy api.py
    # symbol surface (Q.14.A endpoint handlers + their request body model).
    "RuleFiringOutcomeUpdate",
    "RuleFiringResponse",
    "list_rule_firings",
    "update_rule_firing_outcome",
]
