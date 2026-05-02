"""Sprint R.4 — RetrainExplanation rendering.

Covers the deterministic PT-text builder that turns a pair of weight
snapshots + a category breakdown into one explanation line per KPI.

* Direction classification respects the 5% threshold.
* Same inputs always produce the same human_text (audit-friendly).
* Dominant category is reflected in the prose when available.
* First retrain (no previous_weights) reports zero delta.
"""

from __future__ import annotations

from src.governance.preference_learning.retrain_explanation import (
    RetrainExplanation,
    build_retrain_explanations,
)


CURRENT = {
    "w_makespan": 1.5,    # default 1.0  → +50%
    "w_tardiness": 9.0,   # default 10.0 → -10%
    "w_setups": 0.5,      # default 0.5  → 0%
    "w_quality_risk": 0.10,
}
PREVIOUS = {
    "w_makespan": 1.0,
    "w_tardiness": 10.0,
    "w_setups": 0.5,
    "w_quality_risk": 0.10,
}


def test_each_kpi_gets_one_explanation():
    rows = build_retrain_explanations(
        current_weights=CURRENT,
        previous_weights=PREVIOUS,
        pairs_used=84,
        by_category={"CUSTOMER": 50, "QUALITY": 30, "OTHER": 4},
    )
    assert len(rows) == 4
    by_kpi = {r.kpi: r for r in rows}
    assert set(by_kpi.keys()) == {
        "w_makespan", "w_tardiness", "w_setups", "w_quality_risk",
    }


def test_direction_classification_respects_5pct_threshold():
    rows = build_retrain_explanations(
        current_weights=CURRENT,
        previous_weights=PREVIOUS,
        pairs_used=84,
        by_category={"CUSTOMER": 50},
    )
    by_kpi = {r.kpi: r for r in rows}
    assert by_kpi["w_makespan"].direction == "up"      # +50%
    assert by_kpi["w_tardiness"].direction == "down"   # -10%
    assert by_kpi["w_setups"].direction == "stable"    # 0%
    assert by_kpi["w_quality_risk"].direction == "stable"


def test_human_text_is_deterministic_for_same_inputs():
    a = build_retrain_explanations(
        current_weights=CURRENT,
        previous_weights=PREVIOUS,
        pairs_used=84,
        by_category={"CUSTOMER": 50},
    )
    b = build_retrain_explanations(
        current_weights=CURRENT,
        previous_weights=PREVIOUS,
        pairs_used=84,
        by_category={"CUSTOMER": 50},
    )
    assert [r.to_dict() for r in a] == [r.to_dict() for r in b]


def test_dominant_category_appears_in_prose():
    rows = build_retrain_explanations(
        current_weights=CURRENT,
        previous_weights=PREVIOUS,
        pairs_used=84,
        by_category={"CUSTOMER": 60, "QUALITY": 24},
    )
    makespan = next(r for r in rows if r.kpi == "w_makespan")
    assert "CUSTOMER" in makespan.human_text
    assert "84 pares" in makespan.human_text


def test_first_retrain_with_no_previous_weights_reports_zero_delta():
    rows = build_retrain_explanations(
        current_weights=CURRENT,
        previous_weights=None,
        pairs_used=84,
        by_category={"CUSTOMER": 60},
    )
    # All deltas should be 0 — there's no prior baseline to compare to.
    assert all(r.delta_pct == 0 for r in rows)
    assert all(r.direction == "stable" for r in rows)


def test_no_pairs_used_short_circuits_text():
    rows = build_retrain_explanations(
        current_weights=CURRENT,
        previous_weights=PREVIOUS,
        pairs_used=0,
        by_category={},
    )
    assert all("sem pares novos" in r.human_text for r in rows)


def test_to_dict_is_jsonable():
    """The dataclass must round-trip through JSON for TenantConfig storage."""
    import json

    rows = build_retrain_explanations(
        current_weights=CURRENT,
        previous_weights=PREVIOUS,
        pairs_used=84,
        by_category={"CUSTOMER": 50},
    )
    payload = json.dumps([r.to_dict() for r in rows])
    parsed = json.loads(payload)
    assert isinstance(parsed, list)
    assert all(isinstance(p, dict) for p in parsed)
    assert parsed[0]["kpi"] in {"w_makespan", "w_tardiness", "w_setups", "w_quality_risk"}
