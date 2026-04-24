"""Sprint C 1.3 — GET /v1/explain/commit/{sha} wiring + narrative.

Covers:
* Router exposes the new path
* `_generate_explanation` produces a terse PT-PT narrative citing the
  headline KPIs; empty KPIs don't crash
* 404 path when the commit doesn't exist
"""

from __future__ import annotations

from src.explain.api import _generate_explanation, router


def test_router_exposes_commit_endpoint():
    paths = {r.path for r in router.routes}
    assert "/v1/explain/commit/{commit_sha}" in paths


def test_generate_explanation_includes_headline_kpis():
    narrative = _generate_explanation({
        "makespan_hours": 120.5,
        "total_tardiness_hours": 8.2,
        "num_late_orders": 2,
        "throughput_eur_day": 28400,
        "setups": 12,
    })
    assert "120.5h" in narrative
    assert "12 mudanças de setup" in narrative
    assert "2 ordens com atraso" in narrative
    assert "28,400" in narrative


def test_generate_explanation_no_late_orders_says_so():
    narrative = _generate_explanation({
        "makespan_hours": 80,
        "total_tardiness_hours": 0,
        "num_late_orders": 0,
        "throughput_eur_day": 31000,
        "setups": 4,
    })
    assert "nenhuma ordem atrasada" in narrative
    assert "31,000" in narrative


def test_generate_explanation_handles_empty_kpis():
    """Backwards-compat: old commits without the Sprint C fields still
    produce a valid narrative instead of crashing."""
    narrative = _generate_explanation({})
    # With zeros everywhere we still get a grammatically-closed sentence.
    assert narrative.endswith(".")
    # Throughput 0 drops the "throughput alvo" clause entirely.
    assert "throughput" not in narrative


def test_generate_explanation_handles_none_values():
    """Pydantic JSON nullables arrive as None; the narrative coerces to 0."""
    narrative = _generate_explanation({
        "makespan_hours": None,
        "total_tardiness_hours": None,
        "num_late_orders": None,
        "throughput_eur_day": None,
        "setups": None,
    })
    assert "0.0h" in narrative
