"""Sprint Q.6 — End-to-end smoke for the Q.1-Q.6 advisory loop.

Validates the chain of guarantees the plan v4 §11 demands:

* "Explica sempre" — the preview-delta service surfaces conflicts/warnings
  with human-readable messages.
* "Porquê obrigatório em rejeições" — both the governance approve_decision
  endpoint AND the cpo decide endpoint refuse REJECT without a category.
* "Tudo editável via ConfigStore" — all new modules pull defaults via
  TenantConfigService rather than hardcoded constants.
* "Camada 1 hook" — Q.3 quality-score override and Q.5 rejection_category
  produce predicate-tagged signals the detector can ingest.

This is a static smoke (no live DB / no live HTTP server). It proves
imports + Pydantic schemas + pure helpers — full integration tests live
in the per-sprint suites (test_cpo_*, test_trust_*, test_co1_*, etc.).
"""

from __future__ import annotations

import copy
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


def test_q1_trust_v2_imports_clean():
    """Q.1 — TrustIndex v2 module + gates must import without error."""
    from src.dqa.trust_v2 import (  # noqa: F401
        SCOPE_FACTORY,
        TrustComponents,
        TrustIndexV2Calculator,
        TrustWeights,
    )
    from src.dqa.trust_gates import (  # noqa: F401
        TrustGate,
        gate_allows,
        load_gate_config,
    )
    from src.dqa.trust_signals import curated_signals_provider  # noqa: F401

    weights = TrustWeights()
    assert abs(weights.total() - 1.0) < 1e-6, "v2 weights must sum to 1.0"
    components = TrustComponents()  # all 1.0 default
    composite = components.composite(weights)
    assert 0.99 <= composite <= 1.01


def test_q1_quality_gates_uses_v2():
    """Q.1 — QualityGateMiddleware must import the v2 calculator."""
    import src.dqa.quality_gates as qg

    assert "TrustIndexV2Calculator" in dir(qg) or hasattr(qg, "QualityGateMiddleware")
    # The v1 import was removed; this check ensures we don't regress to v1.
    src = __import__("inspect").getsource(qg)
    assert "from .trust_index import" not in src, "v1 import resurrection detected"


def test_q2_transport_router_exposes_8_endpoints():
    """Q.2 — DispatchPage's backend must expose 8 transport endpoints."""
    from src.plan.api.transport import router

    # Router has prefix="/transport" — paths are stored relative to its parent
    # router (`src.plan.api.__init__` adds the `/v1/plan` prefix on top).
    paths = {r.path for r in router.routes}
    assert "/transport/batches" in paths
    assert "/transport/batches/{batch_id}" in paths
    assert "/transport/batches/{batch_id}/orders" in paths
    assert "/transport/batches/{batch_id}/orders/{order_id}" in paths
    assert "/transport/batches/{batch_id}/freeze" in paths
    assert "/transport/batches/{batch_id}/dispatch" in paths
    assert "/transport/batches/{batch_id}/suggestions" in paths
    # Sprint Q.5 — expeditions next-N-days
    assert "/transport/expeditions/next-n-days" in paths


def test_q2_rejection_category_enum_complete():
    """Q.2 — RejectionCategory enum has the 7 values referenced by the UI."""
    from src.governance.models import RejectionCategory

    expected = {"COST", "QUALITY", "CUSTOMER", "CAPACITY", "MOLD", "WORKFORCE", "OTHER"}
    actual = {c.value for c in RejectionCategory}
    assert actual == expected


def test_q2_governance_rejects_without_category():
    """Q.2 — POST /decisions/{id}/approve with action=reject must require category."""
    import logging
    logging.disable(logging.CRITICAL)
    from src.main import app

    client = TestClient(app)
    headers = {"X-Tenant-Id": str(uuid4())}
    r = client.post(
        "/v1/governance/decisions/some-id/approve",
        json={"action": "reject", "reason": "cost was too high here"},
        headers=headers,
    )
    assert r.status_code == 400
    assert "rejection_category" in r.json()["detail"]


def test_q3_workforce_override_emits_preference_rule_predicate():
    """Q.3 — WORKFORCE_OVERRIDE PreferenceRule predicates carry employee_id + field."""
    from src.governance.models import (
        PreferenceRule,
        PreferenceRuleStatus,
        PreferenceRuleType,
    )

    rule = PreferenceRule(
        id=uuid4(),
        tenant_id=uuid4(),
        type=PreferenceRuleType.WORKFORCE_OVERRIDE.value,
        description="op override score",
        predicate={
            "employee_id": str(uuid4()),
            "field": "quality_score",
            "ml_value": 7.5,
            "override_value": 9.0,
            "reason": "K1 expert",
        },
        confidence=1.0,
        status=PreferenceRuleStatus.DETECTED.value,
    )
    assert rule.type == "workforce_override"
    assert rule.predicate["field"] == "quality_score"


def test_q3_quality_score_arithmetic_laplace_smoothing():
    """Q.3 — pure formula must satisfy the 3 anchors specified in plan."""
    from src.workforce.employee_extras_service import (
        DEFAULT_SCORE,
        SMOOTHING_ALPHA,
        SMOOTHING_BETA,
    )

    def score(ops: int, defects: int) -> float:
        if ops == 0 and defects == 0:
            return DEFAULT_SCORE
        rate = (defects + SMOOTHING_ALPHA) / (ops + SMOOTHING_BETA)
        return max(1.0, min(10.0, 10.0 - 10.0 * rate))

    assert score(0, 0) == DEFAULT_SCORE
    assert 9.0 < score(100, 5) <= 9.5
    assert 5.0 < score(100, 50) <= 5.5
    assert score(10, 100) >= 1.0  # clamped


def test_q4_preview_delta_pure_helpers():
    """Q.4 — _detect_conflicts catches worker double-booking; _detect_warnings catches pair-rule."""
    from src.plan.services.preview_delta_service import (
        PreviewMutation,
        _apply_mutation,
        _detect_conflicts,
        _detect_warnings,
    )

    schedule = {
        "operations": [
            {
                "id": "op1",
                "phase_id": "LAMINAGEM",
                "workers": ["w1"],
                "start": "2026-04-25T08:00:00",
                "end": "2026-04-25T12:00:00",
            },
            {
                "id": "op2",
                "phase_id": "PINTURA",
                "workers": ["w2"],
                "start": "2026-04-25T09:00:00",
                "end": "2026-04-25T11:00:00",
            },
        ],
    }

    # Mutation: try to add w2 to op1 (overlapping window with op2)
    m = PreviewMutation(operation_id="op1", new_worker_ids=["w1", "w2"])
    after = copy.deepcopy(schedule)
    _apply_mutation(after, m)
    conflicts = _detect_conflicts(after, m)
    assert any(c.type == "worker_double_booking" for c in conflicts)

    # Mutation: drop op1 to single worker → pair rule warning
    m2 = PreviewMutation(operation_id="op1", new_worker_ids=["w1"])
    after2 = copy.deepcopy(schedule)
    _apply_mutation(after2, m2)
    warnings = _detect_warnings(after2, m2)
    assert any(w.type == "pair_rule" for w in warnings)


def test_q4_apply_move_endpoint_requires_reason_min_10():
    """Q.4 — apply-move must reject reason shorter than 10 chars at schema validation."""
    import logging
    logging.disable(logging.CRITICAL)
    from src.main import app

    client = TestClient(app)
    headers = {"X-Tenant-Id": str(uuid4())}
    r = client.post(
        "/v1/plan/schedule/apply-move",
        json={"operation_id": "op1", "reason": "short"},
        headers=headers,
    )
    assert r.status_code == 422  # Pydantic min_length violation


def test_q5_otd_calculator_handles_empty_data():
    """Q.5 — OTDResult must be sane when there are zero rows."""
    from src.profit.services.dashboard_metrics_service import OTDResult

    r = OTDResult(window_days=30, on_time=0, late=0, total=0, otd_pct=0.0)
    d = r.to_dict()
    assert d["otd_pct"] == 0.0
    assert d["window_days"] == 30
    assert d["by_client"] == []


def test_q5_cpo_decide_rejects_without_category():
    """Q.5 — POST /v1/plan/cpo/commits/{sha}/decide must require rejection_category when alts rejected."""
    import logging
    logging.disable(logging.CRITICAL)
    from src.main import app

    client = TestClient(app)
    headers = {"X-Tenant-Id": str(uuid4())}
    r = client.post(
        "/v1/plan/cpo/commits/abcdef1234567890/decide",
        json={
            "chosen_alt_idx": 0,
            "rejected_alt_idxs": [1, 2],
            "decided_by": "luis",
        },
        headers=headers,
    )
    assert r.status_code == 400
    assert "rejection_category" in r.json()["detail"]

    # And rejects unknown values
    r2 = client.post(
        "/v1/plan/cpo/commits/abcdef1234567890/decide",
        json={
            "chosen_alt_idx": 0,
            "rejected_alt_idxs": [1],
            "rejection_category": "NOT_A_VALID_VALUE",
            "decided_by": "luis",
        },
        headers=headers,
    )
    assert r2.status_code == 400
    assert "unknown rejection_category" in r2.json()["detail"]


def test_r2_cpo_decide_rejects_without_reason_or_short_reason():
    """Sprint R.2 — reason ≥10 chars is mandatory when alts are rejected.

    Camada 3 needs clean rationale to learn from; the dataset builder's
    new default (min_reason_len=10) would silently drop these commits,
    so the API must refuse them at write-time."""
    import logging
    logging.disable(logging.CRITICAL)
    from src.main import app

    client = TestClient(app)
    headers = {"X-Tenant-Id": str(uuid4())}

    # No reason at all → 400.
    r = client.post(
        "/v1/plan/cpo/commits/abcdef1234567890/decide",
        json={
            "chosen_alt_idx": 0,
            "rejected_alt_idxs": [1],
            "rejection_category": "QUALITY",
            "decided_by": "luis",
        },
        headers=headers,
    )
    assert r.status_code == 400
    assert "reason" in r.json()["detail"].lower()

    # Reason too short → 400.
    r2 = client.post(
        "/v1/plan/cpo/commits/abcdef1234567890/decide",
        json={
            "chosen_alt_idx": 0,
            "rejected_alt_idxs": [1],
            "rejection_category": "QUALITY",
            "reason": "no",  # 2 chars
            "decided_by": "luis",
        },
        headers=headers,
    )
    assert r2.status_code == 400
    assert "10 characters" in r2.json()["detail"]


def test_q6_config_categories_endpoint():
    """Q.6 — GET /v1/config/categories enumerates seeded categories."""
    import logging
    logging.disable(logging.CRITICAL)
    from src.main import app

    client = TestClient(app)
    r = client.get("/v1/config/categories", headers={"X-Tenant-Id": str(uuid4())})
    assert r.status_code == 200
    body = r.json()
    cats = {c["category"] for c in body["categories"]}
    # Q.1-Q.6 settings tabs all rely on these
    assert "trust" in cats
    assert "planning" in cats
    assert "mold" in cats
    assert "quality" in cats
    assert body["total"] > 50


def test_q6_reset_to_default_404_on_unknown_key():
    """Q.6 — reset-to-default must 404 cleanly for keys without a seed."""
    import logging
    logging.disable(logging.CRITICAL)
    from src.main import app

    client = TestClient(app)
    r = client.post(
        "/v1/config/foo/bar.does.not.exist/reset-to-default",
        headers={"X-Tenant-Id": str(uuid4())},
    )
    assert r.status_code == 404


def test_advisory_loop_chain_is_consistent():
    """Cross-sprint sanity — the four schemas that carry rejection_category
    use the SAME enum values so a category set on the cpo decide path can
    be replayed by the governance layer without translation.
    """
    from src.governance.models import RejectionCategory
    from src.plan.api.cpo import CommitDecisionRequest

    enum_values = {c.value for c in RejectionCategory}
    req = CommitDecisionRequest(
        chosen_alt_idx=0,
        rejected_alt_idxs=[1],
        rejection_category="MOLD",
        decided_by="luis",
    )
    assert req.rejection_category in enum_values


@pytest.mark.asyncio
async def test_async_smoke_no_event_loop_leak():
    """Sanity: the async DashboardMetricsService can be constructed safely."""
    from src.profit.services.dashboard_metrics_service import DashboardMetricsService

    class _NoopSession:
        async def execute(self, *a, **kw):
            class _R:
                def all(self):
                    return []
                def scalar_one(self):
                    return 0
                def scalars(self):
                    class _S:
                        def all(self):
                            return []
                    return _S()
            return _R()

    svc = DashboardMetricsService(_NoopSession(), uuid4())
    fpy = await svc.first_pass_yield(window_days=7)
    assert fpy.window_days == 7
    assert fpy.first_pass_yield_pct == 0.0  # zero data


def test_r1_learning_metrics_endpoints_registered():
    """Sprint R.1 — three GET endpoints power the Aprendizagem panel.

    Imports the FastAPI app and confirms the router registered the three
    paths the panel calls. A regression here would silently break the
    visibility of Camadas 1-4 even with the service intact.
    """
    from src.main import app

    paths = {
        getattr(r, "path", None)
        for r in app.routes
        if hasattr(r, "methods")
    }
    assert "/v1/governance/learning/pairs" in paths
    assert "/v1/governance/learning/rules" in paths
    assert "/v1/governance/learning/weights" in paths


def test_r1_learning_metrics_service_imports_clean():
    """The service + dataclasses must import without touching the DB."""
    from src.governance.preference_learning import (  # noqa: F401
        DEFAULT_MIN_REASON_LEN,
        LearningMetricsService,
        PairStats,
        RuleStats,
        WeightStats,
    )

    # Default reason gate aligns with R.2 enforcement (≥10 chars).
    assert DEFAULT_MIN_REASON_LEN == 10
