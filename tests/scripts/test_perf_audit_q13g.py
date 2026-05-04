"""Sprint Q.13.G — `scripts/perf_audit.py` parser unit tests.

The script ships in Q.13.F as the deploy-time runner that confirms
each hot query hits its expected composite index (added in alembic
042). The runner couples three responsibilities:

  * Run the EXPLAIN ANALYZE statement (DB-bound, hard to test).
  * **Walk the JSON plan tree** for a named index (pure-functional).
  * **Summarise** `(plan_time, exec_time, node_type, used_index)`
    for human-readable output (pure-functional).

These tests exercise the two pure functions (`_walk_for_index`,
`_summary`) with canned EXPLAIN JSON so a regression in the parser
is caught without a Postgres instance.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest


# `scripts/perf_audit.py` lives outside `src/`; path-hack so the
# test can import it without a package install.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from perf_audit import _summary, _walk_for_index  # noqa: E402


# ───────────────────────────────────────────────────────────────────────────
# `_walk_for_index` — recursive search through the Plan tree
# ───────────────────────────────────────────────────────────────────────────


def test_walk_for_index_finds_top_level_match():
    plan: Dict[str, Any] = {
        "Node Type": "Index Scan",
        "Index Name": "ix_prod_sched_tenant_start_date",
    }
    assert _walk_for_index(plan, "ix_prod_sched_tenant_start_date") is True


def test_walk_for_index_finds_nested_match():
    """Postgres nests `Plans` under aggregates / joins. The walker
    must recurse all the way down."""
    plan: Dict[str, Any] = {
        "Node Type": "Aggregate",
        "Plans": [
            {
                "Node Type": "Sort",
                "Plans": [
                    {
                        "Node Type": "Index Scan",
                        "Index Name": "ix_decision_run_tenant_status_executed_at",
                    },
                ],
            },
        ],
    }
    assert _walk_for_index(plan, "ix_decision_run_tenant_status_executed_at") is True


def test_walk_for_index_returns_false_on_seq_scan():
    """Seq Scan plans don't have an `Index Name` field. The walker
    should report False so the summary can flag the missing index."""
    plan: Dict[str, Any] = {
        "Node Type": "Seq Scan",
        "Relation Name": "production_schedules",
    }
    assert _walk_for_index(plan, "ix_prod_sched_tenant_start_date") is False


def test_walk_for_index_distinguishes_different_indexes():
    """A query that hits a *different* index than the expected one
    should still report False — the audit's whole purpose is to
    confirm the right index, not just any index."""
    plan: Dict[str, Any] = {
        "Node Type": "Index Scan",
        "Index Name": "ix_prod_sched_tenant_machine_date",
    }
    assert _walk_for_index(plan, "ix_prod_sched_tenant_start_date") is False


def test_walk_for_index_empty_plan_returns_false():
    """A plan node with no `Plans` and no `Index Name` returns False
    cleanly (no AttributeError, no crash)."""
    assert _walk_for_index({}, "ix_anything") is False


def test_walk_for_index_handles_null_plans_field():
    plan = {"Node Type": "Limit", "Plans": None}
    assert _walk_for_index(plan, "ix_anything") is False


# ───────────────────────────────────────────────────────────────────────────
# `_summary` — assembles the human-readable status line
# ───────────────────────────────────────────────────────────────────────────


def _explain_envelope(plan: Dict[str, Any], plan_time: float = 1.2,
                      exec_time: float = 18.4) -> List[Dict[str, Any]]:
    """Mimic the `EXPLAIN (FORMAT JSON)` envelope — a list with one
    dict containing `Plan` + timing metadata."""
    return [{
        "Plan": plan,
        "Planning Time": plan_time,
        "Execution Time": exec_time,
    }]


def test_summary_status_ok_when_index_matches():
    plan = {
        "Node Type": "Index Scan",
        "Index Name": "ix_prod_sched_tenant_start_date",
    }
    out = _summary(_explain_envelope(plan), "ix_prod_sched_tenant_start_date")
    assert out["status"] == "ok"
    assert out["uses_expected_index"] is True
    assert out["node_type"] == "Index Scan"
    assert out["plan_time_ms"] == pytest.approx(1.2)
    assert out["exec_time_ms"] == pytest.approx(18.4)


def test_summary_status_warn_when_index_missing():
    plan = {"Node Type": "Seq Scan", "Relation Name": "production_schedules"}
    out = _summary(_explain_envelope(plan), "ix_prod_sched_tenant_start_date")
    assert out["status"] == "warn"
    assert out["uses_expected_index"] is False


def test_summary_handles_empty_plan_envelope():
    """Sometimes EXPLAIN returns no rows (e.g. permission error wrapped
    in a try). Summary must report empty rather than crash."""
    out = _summary([], "ix_anything")
    assert out["status"] == "empty"


def test_summary_carries_plan_metadata():
    plan = {
        "Node Type": "Aggregate",
        "Plans": [{
            "Node Type": "Index Scan",
            "Index Name": "ix_decision_run_tenant_status_executed_at",
        }],
    }
    out = _summary(
        _explain_envelope(plan, plan_time=2.5, exec_time=42.0),
        "ix_decision_run_tenant_status_executed_at",
    )
    assert out["status"] == "ok"
    assert out["uses_expected_index"] is True
    assert out["node_type"] == "Aggregate"
    assert out["plan_time_ms"] == pytest.approx(2.5)
    assert out["exec_time_ms"] == pytest.approx(42.0)
