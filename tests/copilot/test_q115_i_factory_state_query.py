"""
Q.115.I — testes dos 4 métodos novos do FactoryStateQuery

Cada teste usa stub mínimo (sem DB / sem Ollama).
DAMP: cada teste lê como spec independente.
"""

import pytest

from src.copilot.rlm.factory_state_query import FactoryStateQuery


# ─── boat_risk_profile ────────────────────────────────────────────────────────

def test_boat_risk_profile_empty_tenant_returns_correct_structure():
    """Com queries=None (sem semantic layer) → estrutura correcta + nota."""
    fsq = FactoryStateQuery(state=None, queries=None)
    result = fsq.boat_risk_profile("BOAT-001")

    assert result["boat_id"] == "BOAT-001"
    assert "top_phases_at_risk" in result
    assert isinstance(result["top_phases_at_risk"], list)
    assert "note" in result
    assert result["note"] is not None


def test_boat_risk_profile_optional_fields_none_when_unavailable():
    """avg_quality_score e completed_ops_30d são None quando sem dados."""
    fsq = FactoryStateQuery(state=None, queries=None)
    result = fsq.boat_risk_profile("BOAT-002")

    assert result.get("avg_quality_score") is None
    assert result.get("completed_ops_30d") is None


# ─── affinity_signals ────────────────────────────────────────────────────────

def test_affinity_signals_empty_returns_empty_list_with_note():
    """Tabela vazia (Q.115.G pendente) → [] + nota."""
    fsq = FactoryStateQuery(state=None, queries=None)
    result = fsq.affinity_signals()

    assert result["signals"] == []
    assert result["total"] == 0
    assert "note" in result
    assert "Q.115.G" in result["note"]


def test_affinity_signals_with_phase_id_filter():
    """Filtro phase_id não quebra quando sem dados."""
    fsq = FactoryStateQuery(state=None, queries=None)
    result = fsq.affinity_signals(phase_id="FASE-01")

    assert isinstance(result["signals"], list)


def test_affinity_signals_with_operator_id_filter():
    """Filtro operator_id não quebra quando sem dados."""
    fsq = FactoryStateQuery(state=None, queries=None)
    result = fsq.affinity_signals(operator_id="OP-42")

    assert isinstance(result["signals"], list)


# ─── runbook_lookup ──────────────────────────────────────────────────────────

def test_runbook_lookup_empty_returns_empty_list_with_note():
    """Tabela vazia (Q.115.H pendente) → [] + nota."""
    fsq = FactoryStateQuery(state=None, queries=None)
    result = fsq.runbook_lookup("ERR-001")

    assert result["error_code"] == "ERR-001"
    assert result["runbooks"] == []
    assert result["total_history_count"] == 0
    assert "note" in result
    assert "Q.115.H" in result["note"]


def test_runbook_lookup_structure_present():
    """Mesmo sem dados, todos os campos existem."""
    fsq = FactoryStateQuery(state=None, queries=None)
    result = fsq.runbook_lookup("ERR-BOLHA-LAMINADO")

    assert "error_code" in result
    assert "runbooks" in result
    assert "total_history_count" in result


# ─── cost_baseline ───────────────────────────────────────────────────────────

def test_cost_baseline_empty_returns_structure_with_note():
    """Tabelas vazias → campos None mas estrutura presente."""
    fsq = FactoryStateQuery(state=None, queries=None)
    result = fsq.cost_baseline()

    assert "daily_target_eur" in result
    assert "current_baseline_margin_eur" in result
    assert "top_revenue_clients_30d" in result
    assert isinstance(result["top_revenue_clients_30d"], list)
    assert "note" in result


def test_cost_baseline_with_commit_id():
    """Param commit_id opcional não quebra quando sem dados."""
    fsq = FactoryStateQuery(state=None, queries=None)
    result = fsq.cost_baseline(commit_id="COMMIT-XYZ")

    assert "daily_target_eur" in result


# ─── run() dispatcher inclui os 4 métodos novos ──────────────────────────────

def test_run_dispatcher_boat_risk_profile():
    fsq = FactoryStateQuery(state=None, queries=None)
    result = fsq.run("boat_risk_profile", boat_id="BOAT-X")
    assert "boat_id" in result
    assert "error" not in result


def test_run_dispatcher_affinity_signals():
    fsq = FactoryStateQuery(state=None, queries=None)
    result = fsq.run("affinity_signals")
    assert "signals" in result
    assert "error" not in result


def test_run_dispatcher_cost_baseline():
    fsq = FactoryStateQuery(state=None, queries=None)
    result = fsq.run("cost_baseline")
    assert "daily_target_eur" in result
    assert "error" not in result
