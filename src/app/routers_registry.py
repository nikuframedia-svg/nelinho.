"""src/app/routers_registry.py — central include_router registration (Q.67.6.C2).

Single source of truth for which routers are mounted on the FastAPI app.
Order is preserved EXACTLY from the legacy `src/main.py` so that any
implicit dependencies on registration order (e.g. catch-all routes,
middleware that introspects `app.routes`) keep behaving identically.

Adding a new router? Append the import + `app.include_router(...)` at
the bottom unless ordering matters.
"""
from __future__ import annotations

from fastapi import FastAPI

# Original top-of-file router imports (preserved as a block so they
# survive grep audits looking for the legacy import lines).
from src.copilot.alerts.api import router as copilot_alerts_router
from src.copilot.api import router as copilot_router
from src.copilot.api_endpoints.runbooks_api import router as runbooks_router
from src.copilot.api_endpoints.tools_api import router as tools_router
from src.copilot.poetiq import router as copilot_poetiq_router
from src.core.api import router as core_router
from src.core.api import tenant_config_router
from src.explain.api import router as explain_router
from src.factory_data_product import factory_router
from src.governance.api import router as governance_router
from src.governance.api_learning_metrics import router as learning_metrics_router  # Sprint R.1
from src.governance.api_preference_rules import router as preference_rules_router
from src.hr.api import router as hr_router
from src.improve.api import router as improve_router
from src.ml.api import router as ml_router
from src.plan.api import router as plan_router
from src.plan.api.cpo import router as plan_cpo_router
from src.profit.api import router as profit_router
from src.sandbox.api import router as sandbox_router
from src.shared.api import router as shared_router
from src.shared.realtime.activity_api import router as activity_router
from src.supply.api import router as supply_router
from src.twin.api import router as twin_router
from src.workforce.api import router as workforce_router
from src.workforce.employee_extras_api import router as workforce_employees_router  # Sprint Q.3


def register_routers(app: FastAPI) -> None:
    """Mount every API router. Order matches the legacy src/main.py."""
    # Include routers
    app.include_router(core_router)
    app.include_router(tenant_config_router)  # Sprint L.3 — /v1/config/*

    # Sprint AA.4 — Trust Index v2.0 endpoint
    from src.dqa.api import router as dqa_router

    app.include_router(dqa_router)

    # Sprint Q.7 Fase 1 — Diagnostics dashboard (per-module health + infra pings)
    from src.diagnostics import router as diagnostics_router

    app.include_router(diagnostics_router)

    # Sprint N — Factory Map
    from src.factory_data_product.api.factory_map import router as factory_map_router

    app.include_router(factory_map_router)

    # Sprint R — Quality
    from src.quality.api import router as quality_router

    app.include_router(quality_router)
    app.include_router(plan_router)
    app.include_router(profit_router)
    app.include_router(hr_router)
    app.include_router(copilot_router)
    app.include_router(supply_router)  # Supply Chain Planning module
    app.include_router(shared_router)  # Shared/Governance APIs (Decision Ledger)
    # Q.61.32d — legacy_router desmontado; src/legacy/ apagado em Q.61.32d.

    # New module routers
    app.include_router(explain_router)  # Explainability API
    app.include_router(twin_router)  # Digital Twin API
    app.include_router(sandbox_router)  # Sandbox API
    app.include_router(improve_router)  # Improvement Suggestions API
    app.include_router(factory_router)  # Factory Data Product API (C10)
    app.include_router(runbooks_router)  # Runbooks API (P2 Enterprise)
    app.include_router(tools_router)  # Tool Registry API (P2 Enterprise)
    app.include_router(governance_router)  # Governance API (Approvals, SoD)
    app.include_router(preference_rules_router)  # Sprint E.3 — learned rules review
    app.include_router(
        learning_metrics_router
    )  # Sprint R.1 — learning visibility (pairs/rules/weights)
    app.include_router(workforce_router)  # Workforce Operations API (NEW)
    app.include_router(
        workforce_employees_router
    )  # Sprint Q.3 — Employees extras (quality-score, skills, history)
    app.include_router(copilot_alerts_router)  # Proactive alerts (Sprint C — Fase 5)
    app.include_router(plan_cpo_router)  # CPO v4 scheduler (Sprint E — DRCFFS-R)

    # Sprint Q.18.UI.A.1 — minimal /v1/auth/me for the Sidebar user chip.
    from src.shared.api.auth_me import router as auth_me_router

    app.include_router(auth_me_router)

    # Q.31.G — login real por password (POST /v1/auth/login + /refresh).
    from src.shared.api.auth_login import router as auth_login_router

    app.include_router(auth_login_router)

    # Q.31.F — pesquisa global (GET /v1/search).
    from src.search.api import router as search_router

    app.include_router(search_router)

    # Sprint Q.18.ZIP.BE.4 — POST /v1/reports/generate dispatcher.
    from src.reports.api import router as reports_router

    app.include_router(reports_router)

    # Sprint D.1 — Real-time SSE fan-out of Kafka events to the browser.
    from src.shared.realtime import router as realtime_router

    app.include_router(realtime_router)
    app.include_router(activity_router)  # /v1/activity/recent — outbox poll for LiveActivityFeed
    app.include_router(ml_router)  # ML learning infrastructure (Sprint G)
    app.include_router(copilot_poetiq_router)  # POETIQ copilot↔CPO loop (Sprint K.4)

    # Q.61.34 — outbox observability (GET /v1/outbox/status)
    from src.shared.api.outbox_status import router as outbox_status_router

    app.include_router(outbox_status_router)

    # Q.66.E.3 — agent actions observability (GET /v1/observability/agent-actions)
    from src.observability import router as observability_router

    app.include_router(observability_router)

    # Q.115.B — config revenue-target, client-priority, user-input
    from src.app.routers.q115_config import router as q115_config_router

    app.include_router(q115_config_router)

    # Q.115.C — drag-drop manual reorder com safety_net + Kafka
    from src.plan.api.reorder import router as reorder_router

    app.include_router(reorder_router)

    # Q.115.G — afinidades operador/fase (GET /v1/learning/affinities)
    from src.learning.api_affinities import router as affinities_router

    app.include_router(affinities_router)

    # Q.115.V — plan-vs-actual (GET /v1/learning/plan-vs-actual)
    from src.learning.api_plan_vs_actual import router as plan_vs_actual_router

    app.include_router(plan_vs_actual_router)

    # Q.115.X5 — cancel/retire/deactivate para obras/encomendas/barcos/pessoas
    from src.master_data.api.cancel import router as cancel_router

    app.include_router(cancel_router)

    # Q.115.X6 — boat-phase-scores + boat-potential
    from src.learning.api_boat_scores import router as boat_scores_router

    app.include_router(boat_scores_router)

    # Q.116.A — entity summaries (4 sheets contextuais)
    from src.plan.api.entity_summary import router as entity_summary_router

    app.include_router(entity_summary_router)
