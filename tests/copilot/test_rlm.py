"""Sprint F.4 — FactoryStateQuery + run_rlm_agent.

Covers:

* Each typed sub-query returns a bounded dict with the documented
  shape, including the FactoryState-only fallback path when no
  semantic layer is wired.
* Dispatcher ``run()`` routes known names, rejects unknown names
  without raising, and ignores unexpected params.
* Agent protocol parser tolerates code-fenced JSON and rejects
  unknown actions.
* Agent loop halts on ``answer``, hits ``max_steps`` cap, feeds
  query results back into the transcript, and records a trace.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Callable, Dict, List
from uuid import UUID

import asyncio
import pytest

from src.copilot.rlm import FactoryStateQuery
from src.copilot.rlm.agent import (
    AgentTurn,
    AnswerAction,
    QueryAction,
    build_system_prompt,
    parse_action,
    run_rlm_agent,
)


# ─── Stubs ────────────────────────────────────────────────────────────────


@dataclass
class _StubState:
    """Minimal stand-in for FactoryState — only the bits RLM reads."""
    tenant_id: UUID = UUID("88888888-8888-8888-8888-888888888888")
    open_orders: List[Dict[str, Any]] = field(default_factory=lambda: [
        {"order_id": "OF-100", "modelo_id": "K1", "quantidade": 3, "due_date": "2026-05-10"},
        {"order_id": "OF-101", "modelo_id": "K2", "quantidade": 5, "due_date": "2026-05-15"},
    ])
    preference_rules: List[Dict[str, Any]] = field(default_factory=lambda: [
        {"type": "temporal_block", "description": "Não Laminagem às sextas", "confidence": 0.88},
        {"type": "temporal_block", "description": "Não Pintura às segundas", "confidence": 0.71},
        {"type": "operator_affinity", "description": "Paulo na K4", "confidence": 0.92},
    ])


class _StubSemantic:
    """Stand-in for SemanticQueriesInMemory."""

    def get_wip(self) -> Dict[str, Any]:
        return {
            "trust_index": 0.82,
            "data": {
                "total": 42,
                "open_orders_list": [
                    {"order_id": "OF-1", "modelo_id": "K1", "quantidade": 2, "due_date": "2026-05-10"},
                    {"order_id": "OF-2", "modelo_id": "K2", "quantidade": 3, "due_date": "2026-05-20"},
                ],
            },
        }

    def get_bottlenecks(self, top_n: int = 10) -> Dict[str, Any]:
        return {
            "trust_index": 0.75,
            "data": {
                "bottlenecks": [
                    {"fase_nome": "Laminagem", "bottleneck_score": 88.5, "backlog_hours": 42, "is_critical": True},
                    {"fase_nome": "Pintura", "bottleneck_score": 62.0, "backlog_hours": 21, "is_critical": False},
                ],
            },
        }

    def get_skills_risk(self, min_capable: int = 3) -> Dict[str, Any]:
        return {
            "trust_index": 0.70,
            "data": {
                "phases_at_risk": 2,
                "critical_phases": 1,
                "high_risk_phases": 1,
                "risk_rows": [
                    {"fase_nome": "COLAGEM", "capable_worker_count": 1, "severity": "critical"},
                ],
            },
        }

    def get_quality(self, top_errors: int = 10, **_kw) -> Dict[str, Any]:
        return {
            "trust_index": 0.60,
            "data": {
                "total_errors": 37,
                "by_type": [
                    {"error_type": "resina_bolha", "count": 8},
                    {"error_type": "pintura_risco", "count": 6},
                ],
            },
        }


# ─── FactoryStateQuery ────────────────────────────────────────────────────


def test_describe_contains_all_query_names():
    names = {row["name"] for row in FactoryStateQuery.describe()}
    assert "wip" in names
    assert "bottlenecks" in names
    assert "preference_rules" in names
    assert "overview" in names


def test_catalogue_text_is_one_line_per_query():
    text = FactoryStateQuery.catalogue_text()
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) == len(FactoryStateQuery.describe())
    for row in FactoryStateQuery.describe():
        assert row["name"] in text


def test_wip_uses_semantic_layer_when_available():
    q = FactoryStateQuery(state=_StubState(), queries=_StubSemantic())
    result = q.wip()
    assert result["open_orders_count"] == 42
    assert len(result["top"]) == 2
    assert result["top"][0]["order_id"] == "OF-1"


def test_wip_falls_back_to_factory_state_when_semantic_unavailable():
    q = FactoryStateQuery(state=_StubState(), queries=None)
    result = q.wip()
    assert result["open_orders_count"] == 2
    assert result["source"] == "factory_state_fallback"


def test_bottlenecks_flags_critical_phase():
    q = FactoryStateQuery(state=_StubState(), queries=_StubSemantic())
    result = q.bottlenecks()
    assert result["count"] == 2
    assert result["top"][0]["phase"] == "Laminagem"
    assert result["top"][0]["is_critical"] is True


def test_skills_risk_propagates_severity():
    q = FactoryStateQuery(state=_StubState(), queries=_StubSemantic())
    result = q.skills_risk()
    assert result["phases_at_risk"] == 2
    assert result["top"][0]["severity"] == "critical"


def test_preference_rules_tallies_by_type():
    q = FactoryStateQuery(state=_StubState())
    result = q.preference_rules()
    assert result["count"] == 3
    assert result["by_type"]["temporal_block"] == 2
    assert result["by_type"]["operator_affinity"] == 1


def test_overview_combines_other_queries():
    q = FactoryStateQuery(state=_StubState(), queries=_StubSemantic())
    result = q.overview()
    assert result["wip"] == 42
    assert result["bottleneck_count"] == 2
    assert result["confirmed_rules"] == 3


def test_run_unknown_name_returns_structured_error():
    q = FactoryStateQuery(state=_StubState(), queries=_StubSemantic())
    result = q.run("nonexistent_query")
    assert "error" in result
    assert "hint" in result


def test_run_routes_known_name():
    q = FactoryStateQuery(state=_StubState(), queries=_StubSemantic())
    result = q.run("wip")
    assert result["open_orders_count"] == 42


def test_run_ignores_unexpected_params():
    q = FactoryStateQuery(state=_StubState(), queries=_StubSemantic())
    # `wip()` takes no params — passing one must not raise.
    result = q.run("wip", unused_flag=True)
    assert "open_orders_count" in result


# ─── parse_action ─────────────────────────────────────────────────────────


def test_parse_action_handles_bare_query_json():
    step = parse_action('{"action": "query", "name": "wip"}')
    assert isinstance(step, QueryAction)
    assert step.name == "wip"


def test_parse_action_strips_code_fence():
    raw = """```json
{"action": "answer", "text": "pronto"}
```"""
    step = parse_action(raw)
    assert isinstance(step, AnswerAction)
    assert step.text == "pronto"


def test_parse_action_tolerates_surrounding_prose():
    raw = "Aqui está a minha resposta:\n{\"action\": \"answer\", \"text\": \"ok\"}\nFim."
    step = parse_action(raw)
    assert isinstance(step, AnswerAction)


def test_parse_action_rejects_unknown_action():
    with pytest.raises(Exception):
        parse_action('{"action": "hack", "name": "wip"}')


def test_parse_action_rejects_no_json():
    with pytest.raises(ValueError):
        parse_action("no json here at all")


def test_build_system_prompt_includes_catalogue_and_max_steps():
    prompt = build_system_prompt(max_steps=4)
    assert "wip" in prompt
    assert "bottlenecks" in prompt
    assert "4 sub-queries" in prompt


# ─── run_rlm_agent ────────────────────────────────────────────────────────


def _canned_llm(responses: List[str]) -> Callable[[List[AgentTurn]], Any]:
    """Turn a list of raw LLM strings into the async callable the loop
    expects. Each call pops the next response; if exhausted the stub
    returns the last response again (keeps tests robust to over-runs)."""
    idx = {"i": 0}

    async def _call(_turns: List[AgentTurn]) -> str:
        i = min(idx["i"], len(responses) - 1)
        idx["i"] += 1
        return responses[i]

    return _call


def test_agent_halts_on_answer_action():
    q = FactoryStateQuery(state=_StubState(), queries=_StubSemantic())
    llm = _canned_llm([
        '{"action": "answer", "text": "Laminagem é o gargalo."}',
    ])
    trace = asyncio.run(run_rlm_agent(
        question="Qual é o gargalo?",
        state_query=q,
        llm=llm,
        max_steps=5,
    ))
    assert trace.answer == "Laminagem é o gargalo."
    assert trace.steps_used == 1
    assert trace.terminated_reason == "complete"


def test_agent_runs_query_then_answer():
    q = FactoryStateQuery(state=_StubState(), queries=_StubSemantic())
    llm = _canned_llm([
        '{"action": "query", "name": "bottlenecks"}',
        '{"action": "answer", "text": "Laminagem a 88.5."}',
    ])
    trace = asyncio.run(run_rlm_agent(
        question="Qual é o gargalo?",
        state_query=q,
        llm=llm,
        max_steps=5,
    ))
    assert trace.answer == "Laminagem a 88.5."
    assert trace.steps_used == 2
    assert len(trace.queries_run) == 1
    assert trace.queries_run[0]["name"] == "bottlenecks"
    # Tool observation is injected back into the transcript.
    assert any(t.role == "tool" and "bottlenecks" in t.content for t in trace.turns)


def test_agent_forces_answer_when_max_steps_reached():
    q = FactoryStateQuery(state=_StubState(), queries=_StubSemantic())
    # Two queries + one "forced answer" prompt → need 3 canned responses.
    llm = _canned_llm([
        '{"action": "query", "name": "wip"}',
        '{"action": "query", "name": "bottlenecks"}',
        '{"action": "answer", "text": "Forçado."}',
    ])
    trace = asyncio.run(run_rlm_agent(
        question="...",
        state_query=q,
        llm=llm,
        max_steps=2,
    ))
    assert trace.terminated_reason == "max_steps_reached"
    assert trace.answer == "Forçado."
    assert trace.steps_used == 2


def test_agent_recovers_from_invalid_json():
    q = FactoryStateQuery(state=_StubState(), queries=_StubSemantic())
    llm = _canned_llm([
        "not a json blob",
        '{"action": "answer", "text": "recovered"}',
    ])
    trace = asyncio.run(run_rlm_agent(
        question="?",
        state_query=q,
        llm=llm,
        max_steps=4,
    ))
    assert trace.answer == "recovered"
    # Both the bad attempt and the successful one consume steps.
    assert trace.steps_used == 2
