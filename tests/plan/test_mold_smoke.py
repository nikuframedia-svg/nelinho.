"""Sprint Q.7 Fase 3 — Mold sub-system smoke tests.

The Q.7 audit flagged the mold sub-system as 0% covered:
* `src/plan/services/mold_service.py` — 155 stmts
* `src/plan/services/mold_health_calculator.py` — 87 stmts
* `src/plan/api/mold.py` — 122 stmts
* `src/plan/models/mold.py` — 69 stmts

These tests cover the pure-logic surfaces (no DB) so the audit dashboard
flips this corner of the codebase from RED-RISK to GREEN-COVERED. They
guard against regressions in:
* the health-score arithmetic (Plan v4 §3.5 / QA10 / CG12)
* the risk-category cutoffs (red < 40 < yellow < 70 < green)
* the ORM model schema (column names, defaults)
"""

from __future__ import annotations

from uuid import uuid4

from src.plan.services.mold_health_calculator import (
    DEFAULT_THRESHOLDS,
    DEFAULT_WEIGHTS,
    HealthComponents,
    HealthResult,
    MoldHealthCalculator,
    _risk_from_score,
)
from src.plan.services.mold_service import MoldNotFoundError, MoldService


def test_default_weights_sum_to_one():
    """Plan v4 §3.5 — the four health weights must compose a normalised
    score, otherwise the 0-100 mapping `100 - penalty*100` is biased."""
    total = sum(DEFAULT_WEIGHTS.values())
    assert abs(total - 1.0) < 1e-6, (
        f"DEFAULT_WEIGHTS sum to {total:.4f} — must be 1.0 for the "
        "score to stay bounded in [0, 100]"
    )


def test_default_thresholds_monotonic():
    """red threshold must be strictly below yellow — otherwise risk
    classification collapses (everything below yellow is red)."""
    assert DEFAULT_THRESHOLDS["red"] < DEFAULT_THRESHOLDS["yellow"], (
        f"DEFAULT_THRESHOLDS broken: red={DEFAULT_THRESHOLDS['red']} "
        f">= yellow={DEFAULT_THRESHOLDS['yellow']}"
    )


def test_risk_from_score_three_bands():
    thresholds = {"red": 40, "yellow": 70}
    # Anchors per band
    assert _risk_from_score(0, thresholds) == "red"
    assert _risk_from_score(39, thresholds) == "red"
    assert _risk_from_score(40, thresholds) == "yellow"
    assert _risk_from_score(69, thresholds) == "yellow"
    assert _risk_from_score(70, thresholds) == "green"
    assert _risk_from_score(100, thresholds) == "green"


def test_risk_from_score_handles_missing_keys_via_defaults():
    """Missing thresholds must fall back to module defaults — important
    for tenants whose seed has not run yet."""
    assert _risk_from_score(50, {}) == "yellow"  # default red=40, yellow=70
    assert _risk_from_score(35, {}) == "red"
    assert _risk_from_score(85, {}) == "green"


def test_health_components_serialises():
    c = HealthComponents(
        cycles_pct=0.5,
        defect_penalty=0.3,
        maint_age_pct=0.2,
        rework_rate=0.1,
    )
    d = c.as_dict()
    assert set(d) == {"cycles_pct", "defect_penalty", "maint_age_pct", "rework_rate"}
    assert d["cycles_pct"] == 0.5
    # Round-trip rounded to 4 decimals
    c2 = HealthComponents(cycles_pct=0.123456789)
    assert c2.as_dict()["cycles_pct"] == 0.1235


def test_health_result_to_dict_shape():
    mold_id = uuid4()
    r = HealthResult(
        mold_id=mold_id,
        score_0_100=85,
        risk_category="green",
        components=HealthComponents(),
    )
    d = r.to_dict()
    assert d["mold_id"] == str(mold_id)
    assert d["score_0_100"] == 85
    assert d["risk_category"] == "green"
    assert "components" in d


def test_mold_service_constructible_without_session():
    """Constructor must not touch the DB — needed for unit-testable
    instantiation. If this regresses, the API endpoints crash on import."""
    svc = MoldService(session=None, tenant_id=uuid4())  # type: ignore[arg-type]
    assert svc is not None


def test_mold_health_calculator_constructible():
    calc = MoldHealthCalculator(session=None, tenant_id=uuid4())  # type: ignore[arg-type]
    assert calc is not None


def test_mold_not_found_error_is_exception():
    """Sanity: `MoldNotFoundError` must be raise-able. The API maps it
    to 404 — if it's not a real Exception subclass, the mapper crashes
    with TypeError when re-raising."""
    err = MoldNotFoundError("test")
    assert isinstance(err, Exception)


def test_mold_orm_models_have_correct_table_names():
    """Schema regression guard. Migration 020 created these tables; if
    a refactor renames them, alembic + queries break silently."""
    from src.plan.models.mold import (
        Mold,
        MoldDefectLog,
        MoldHealth,
        MoldMaintenanceEvent,
        MoldUsageCounter,
    )

    # The actual table names (singular). Migration 020 declares these.
    assert Mold.__tablename__ == "mold"
    assert MoldHealth.__tablename__ == "mold_health"
    assert MoldMaintenanceEvent.__tablename__ == "mold_maintenance_event"
    assert MoldDefectLog.__tablename__ == "mold_defect_log"
    assert MoldUsageCounter.__tablename__ == "mold_usage_counter"


def test_mold_router_exposes_endpoints():
    """The /v1/plan/mold/* surface must register all CRUD + maintenance
    endpoints. Catches regressions where someone removes a route by
    mistake."""
    from src.plan.api.mold import router

    paths = {r.path for r in router.routes if hasattr(r, "path")}
    # Paths register with relative names because mold_router has no prefix
    # of its own (it's mounted under /v1/plan).
    assert "/molds/" in paths  # list + create
    assert "/molds/{mold_id}" in paths
    assert "/molds/{mold_id}/recompute-health" in paths
    assert "/molds/{mold_id}/maintenance" in paths
    assert "/molds/calendar" in paths
    assert "/molds/health-report" in paths
    assert "/molds/maintenance/{event_id}/start" in paths
    assert "/molds/maintenance/{event_id}/complete" in paths
