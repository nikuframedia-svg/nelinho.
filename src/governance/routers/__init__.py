"""Governance API sub-routers.

Q.67.6.B5 — ``src/governance/api.py`` used to carry ~948L of FastAPI routes
in a single file. Each concern now lives in its own sub-router and is mounted
by the aggregator in :mod:`src.governance.api`:

* :mod:`.policies`  — GET /policies, /policies/{decision_type}.
* :mod:`.decisions` — propose / approve / get / list / pending/me / audit-pack
  / execute / rollback / bulk / payload patch / kill-switch / delta.
* :mod:`.timeline`  — /decisions/timeline + /audit/timeline.
* :mod:`.rbac`      — /rbac/matrix.
* :mod:`.rule_firings` — /rule-firings + /rule-firings/{id}/outcome + adoption.
* :mod:`.event_outbox` — /event-outbox.
"""

from .decisions import router as decisions_router
from .event_outbox import router as event_outbox_router
from .policies import router as policies_router
from .rbac import router as rbac_router
from .rule_firings import router as rule_firings_router
from .timeline import router as timeline_router

__all__ = [
    "decisions_router",
    "event_outbox_router",
    "policies_router",
    "rbac_router",
    "rule_firings_router",
    "timeline_router",
]
