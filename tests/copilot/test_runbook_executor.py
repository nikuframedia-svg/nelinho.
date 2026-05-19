"""Sprint Q.9 (2.8) / Q.35.5.2 — Copilot RUN_RUNBOOK executor.

Loads a YAML definition from runbook_definitions/, validates required
keys, resolves date_range placeholders.

Q.35.5.2 — `execute_runbook` is now async: without a session it builds
an advisory plan (`status="planned"`); with an `AsyncSession` it runs
the SELECTs and each step carries `rows` / `row_count`.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

import pytest

from src.copilot.runbook_executor import (
    RUNBOOK_DIR,
    RunbookInvalid,
    RunbookNotFound,
    execute_runbook,
    list_runbooks,
    load_runbook,
    loadable_runbooks,
)

_TENANT = UUID("00000000-0000-0000-0000-000000000001")


# --- fakes para o caminho "com session" --------------------------------

class _Row:
    """Mimica uma Row do SQLAlchemy — o executor lê `._mapping`."""

    def __init__(self, mapping):
        self._mapping = mapping


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _RunbookFakeSession:
    """Devolve conjuntos de linhas em fila, pela ordem dos `execute`."""

    def __init__(self, row_sets):
        self._row_sets = list(row_sets)
        self.executed: list = []

    async def execute(self, stmt, params=None):
        self.executed.append((str(stmt), params))
        rows = self._row_sets.pop(0) if self._row_sets else []
        return _Result([_Row(m) for m in rows])


# --- catálogo -----------------------------------------------------------

def test_list_runbooks_includes_existing_yamls():
    """At least the two seed YAMLs (oee_diagnosis, bottleneck_analysis)."""
    available = list_runbooks()
    assert "oee_diagnosis" in available
    assert "bottleneck_analysis" in available


def test_loadable_runbooks_excludes_incompatible_format():
    """Q.35.5.1 — `bottleneck_analysis` é do outro engine (step-based),
    não carrega aqui; só `oee_diagnosis` é executável."""
    loadable = loadable_runbooks()
    assert "oee_diagnosis" in loadable
    assert "bottleneck_analysis" not in loadable


def test_load_runbook_returns_parsed_yaml():
    rb = load_runbook("oee_diagnosis")
    assert rb["id"] == "oee_diagnosis"
    assert isinstance(rb["queries"], list)
    assert all("sql" in q and "name" in q for q in rb["queries"])


def test_load_runbook_unknown_id_raises():
    with pytest.raises(RunbookNotFound):
        load_runbook("not_a_runbook")


def test_load_runbook_rejects_yaml_missing_required_keys(tmp_path, monkeypatch):
    """An incomplete YAML is rejected — protects against silent stubs."""
    bad = tmp_path / "broken.yaml"
    bad.write_text("name: 'no id no queries'\n", encoding="utf-8")
    monkeypatch.setattr(
        "src.copilot.runbook_executor.RUNBOOK_DIR", tmp_path,
    )
    with pytest.raises(RunbookInvalid):
        load_runbook("broken")


# --- modo advisory (sem session) ----------------------------------------

async def test_execute_runbook_advisory_when_no_session():
    """Sem session → plano advisory, nenhuma query corre."""
    trace = await execute_runbook("oee_diagnosis")
    assert trace["status"] == "planned"
    assert trace["advisory_mode"] is True
    assert trace["runbook_id"] == "oee_diagnosis"
    assert len(trace["steps"]) >= 1
    for step in trace["steps"]:
        assert step["status"] == "planned"
        assert "sql" in step
        if ":start_date" in step["sql"]:
            assert "start_date" in step["parameters"]


async def test_execute_runbook_honours_runbook_default_range():
    """oee_diagnosis declara `default: 90d` — sem payload, a janela é 90d."""
    trace = await execute_runbook("oee_diagnosis")
    start = datetime.fromisoformat(trace["inputs"]["start_date"])
    end = datetime.fromisoformat(trace["inputs"]["end_date"])
    assert abs((end - start) - timedelta(days=90)) < timedelta(seconds=5)


async def test_execute_runbook_honours_payload_date_range():
    """O payload sobrepõe-se ao default do runbook."""
    trace = await execute_runbook("oee_diagnosis", payload={"date_range": "7d"})
    start = datetime.fromisoformat(trace["inputs"]["start_date"])
    end = datetime.fromisoformat(trace["inputs"]["end_date"])
    assert abs((end - start) - timedelta(days=7)) < timedelta(seconds=5)


# --- modo real (com session) --------------------------------------------

async def test_execute_runbook_runs_queries_with_session():
    """Com session → cada SELECT corre, o step traz `rows` e `row_count`."""
    session = _RunbookFakeSession([
        [{"rework_count": 3659}],
        [{"phase": "Lixagem - água", "error_count": 1061}],
        [{"error_code": "E-DEF-01", "error_count": 600}],
    ])
    trace = await execute_runbook(
        "oee_diagnosis", session=session, tenant_id=_TENANT,
    )
    assert trace["status"] == "executed"
    assert trace["advisory_mode"] is False
    assert all(s["status"] == "executed" for s in trace["steps"])
    first = trace["steps"][0]
    assert first["rows"] == [{"rework_count": 3659}]
    assert first["row_count"] == 1
    # As 3 queries da oee_diagnosis correram.
    assert len(session.executed) == 3


async def test_execute_runbook_failed_query_does_not_kill_runbook():
    """Uma query que rebenta vira step `failed`; as outras continuam."""
    class _Boom(_RunbookFakeSession):
        async def execute(self, stmt, params=None):
            self.executed.append((str(stmt), params))
            raise RuntimeError("coluna inexistente")

    session = _Boom([])
    trace = await execute_runbook(
        "oee_diagnosis", session=session, tenant_id=_TENANT,
    )
    assert trace["status"] == "failed"
    for step in trace["steps"]:
        assert step["status"] == "failed"
        assert "coluna inexistente" in step["error"]
