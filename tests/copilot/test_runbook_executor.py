"""Sprint Q.9 (2.8) — Copilot RUN_RUNBOOK executor.

Loads a YAML definition from runbook_definitions/, validates required
keys, resolves date_range placeholders. Advisory only — does NOT run
SQL against a live DB until Sprint G.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from src.copilot.runbook_executor import (
    RUNBOOK_DIR,
    RunbookInvalid,
    RunbookNotFound,
    execute_runbook,
    list_runbooks,
    load_runbook,
)


def test_list_runbooks_includes_existing_yamls():
    """At least the two seed YAMLs (oee_diagnosis, bottleneck_analysis)."""
    available = list_runbooks()
    assert "oee_diagnosis" in available
    assert "bottleneck_analysis" in available


def test_load_runbook_returns_parsed_yaml():
    rb = load_runbook("oee_diagnosis")
    assert rb["id"] == "oee_diagnosis"
    assert isinstance(rb["queries"], list)
    assert all("sql" in q and "name" in q for q in rb["queries"])


def test_load_runbook_unknown_id_raises():
    with pytest.raises(RunbookNotFound):
        load_runbook("not_a_runbook")


def test_execute_runbook_returns_planned_trace():
    """Smoke: trace has steps + advisory flag + ISO timestamp."""
    trace = execute_runbook("oee_diagnosis")
    assert trace["status"] == "planned"
    assert trace["advisory_mode"] is True
    assert trace["runbook_id"] == "oee_diagnosis"
    assert len(trace["steps"]) >= 1
    for step in trace["steps"]:
        assert step["status"] == "planned"
        assert "sql" in step
        # Parameters present when the SQL references a placeholder.
        if ":start_date" in step["sql"]:
            assert "start_date" in step["parameters"]


def test_execute_runbook_resolves_24h_default_range():
    trace = execute_runbook("oee_diagnosis")
    start = datetime.fromisoformat(trace["inputs"]["start_date"])
    end = datetime.fromisoformat(trace["inputs"]["end_date"])
    delta = end - start
    # Default is 24h ± a few seconds.
    assert abs(delta - timedelta(hours=24)) < timedelta(seconds=5)


def test_execute_runbook_honours_payload_date_range():
    trace = execute_runbook("oee_diagnosis", payload={"date_range": "7d"})
    start = datetime.fromisoformat(trace["inputs"]["start_date"])
    end = datetime.fromisoformat(trace["inputs"]["end_date"])
    delta = end - start
    assert abs(delta - timedelta(days=7)) < timedelta(seconds=5)


def test_load_runbook_rejects_yaml_missing_required_keys(tmp_path, monkeypatch):
    """An incomplete YAML is rejected — protects against silent stubs."""
    bad = tmp_path / "broken.yaml"
    bad.write_text("name: 'no id no queries'\n", encoding="utf-8")
    monkeypatch.setattr(
        "src.copilot.runbook_executor.RUNBOOK_DIR", tmp_path,
    )
    with pytest.raises(RunbookInvalid):
        load_runbook("broken")
