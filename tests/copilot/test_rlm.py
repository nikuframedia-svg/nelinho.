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


# ─── Sprint F+ — kernel tool-call (causal_query sub-query) ───────────────


def test_causal_query_returns_kernel_delta_for_intervention():
    """Ground-truth check: the wrapper returns a non-trivial delta
    when we intervene on shift_mode (doubled shift roughly doubles
    throughput per the NELO_DAG functional forms)."""
    q = FactoryStateQuery()
    result = q.causal_query("throughput_eur_day", do={"shift_mode": 2.0})
    assert "error" not in result
    assert result["target"] == "throughput_eur_day"
    assert result["direction"] == "increase"
    assert result["delta"] > 20_000  # comfortably above noise band
    assert result["magnitude"] == result["delta"]  # delta > 0 → equal


def test_causal_query_handles_unknown_target_cleanly():
    q = FactoryStateQuery()
    result = q.causal_query("does-not-exist")
    assert "error" in result
    assert "unknown DAG node" in result["error"]


def test_causal_query_handles_unknown_intervention_node():
    q = FactoryStateQuery()
    result = q.causal_query(
        "throughput_eur_day", do={"nonsense_knob": 1.0},
    )
    assert "error" in result


def test_causal_query_rejects_non_numeric_intervention():
    q = FactoryStateQuery()
    result = q.causal_query("throughput_eur_day", do={"shift_mode": "two"})
    assert "error" in result
    assert "must be numeric" in result["error"]


def test_causal_query_observation_propagates_through_dag():
    """observe={curing_time: 30} should push makespan upward."""
    q = FactoryStateQuery()
    baseline = q.causal_query("makespan_hours")
    elevated = q.causal_query("makespan_hours", observe={"curing_time": 30.0})
    assert "error" not in baseline
    assert "error" not in elevated
    assert elevated["target_value"] > baseline["target_value"]


def test_causal_query_appears_in_describe_catalogue():
    catalogue = FactoryStateQuery.describe()
    names = {row["name"] for row in catalogue}
    assert "causal_query" in names
    text = FactoryStateQuery.catalogue_text()
    assert "causal_query" in text
    assert "magnitudes" in text.lower()


def test_dispatcher_returns_explicit_error_for_causal_query_without_args():
    """The blanket ``except TypeError: return fn()`` fallback would
    have made `run('causal_query')` re-explode — we override it so
    the LLM gets a structured diagnostic instead of an exception in
    the trace."""
    q = FactoryStateQuery()
    result = q.run("causal_query")  # missing required `target`
    assert "error" in result
    assert "target" in result["error"]
    # Other sub-queries keep their permissive fallback.
    overview = q.run("overview", spurious_kwarg=True)
    assert "error" not in overview


def test_agent_chains_causal_query_then_answer_with_exact_delta():
    """End-to-end: LLM picks causal_query → tool result has delta →
    LLM emits an answer that quotes the delta verbatim."""
    q = FactoryStateQuery()
    # Compute the kernel delta once so we can put it in the canned answer.
    expected = q.causal_query("makespan_hours", do={"routing_variant": 1.0})
    expected_delta = expected["delta"]

    llm = _canned_llm([
        '{"action": "query", "name": "causal_query", '
        '"params": {"target": "makespan_hours", '
        '"do": {"routing_variant": 1.0}}}',
        '{"action": "answer", "text": '
        f'"Variante B reduz makespan em {expected_delta} h."'
        '}',
    ])
    trace = asyncio.run(run_rlm_agent(
        question="Se mudarmos para a variante B, o makespan baixa quanto?",
        state_query=q,
        llm=llm,
        max_steps=4,
    ))
    assert trace.terminated_reason == "complete"
    assert trace.steps_used == 2
    # The agent ran exactly one query and it was causal_query.
    assert len(trace.queries_run) == 1
    assert trace.queries_run[0]["name"] == "causal_query"
    delta_in_tool = trace.queries_run[0]["result"]["delta"]
    assert delta_in_tool == expected_delta
    # The answer cites the delta verbatim.
    assert str(expected_delta) in (trace.answer or "")


def test_agent_default_max_steps_is_six():
    """Bumped from 5 → 6 so a JSON cold-start retry plus a kernel
    query plus an answer all fit without `max_steps_reached`."""
    import inspect
    sig = inspect.signature(run_rlm_agent)
    assert sig.parameters["max_steps"].default == 6


# ─── Sprint F+++ — world_model_forecast sub-query ────────────────────────


def test_world_model_forecast_appears_in_catalogue():
    names = {row["name"] for row in FactoryStateQuery.describe()}
    assert "world_model_forecast" in names
    text = FactoryStateQuery.catalogue_text()
    assert "world_model_forecast" in text
    assert "trajectória" in text.lower() or "horizonte" in text.lower()


def test_world_model_forecast_returns_capped_trajectory():
    """The sub-query returns trajectory rows trimmed for token budget
    even when the underlying forecast ran for many steps."""
    q = FactoryStateQuery()
    result = q.world_model_forecast(
        "throughput_eur_day", horizon_steps=14, samples=80,
    )
    assert "error" not in result
    assert result["target"] == "throughput_eur_day"
    assert result["step_unit"] == "shift"
    assert result["horizon_steps"] == 14
    # Cap: at most 8 rows shipped to the LLM regardless of horizon.
    assert len(result["trajectory"]) <= 8
    # Each row carries the headline quantiles.
    row = result["trajectory"][0]
    assert {"step", "mean", "std", "p05", "p50", "p95"} <= set(row.keys())
    assert "summary" in result
    assert "ci90_at_horizon" in result["summary"]


def test_world_model_forecast_handles_unknown_target_with_did_you_mean():
    q = FactoryStateQuery()
    result = q.world_model_forecast(
        "thru_per_day", horizon_steps=4, samples=80,
    )
    assert "error" in result
    assert "did_you_mean" in result
    assert isinstance(result["did_you_mean"], list)


def test_dispatcher_returns_explicit_error_for_world_model_forecast_without_args():
    q = FactoryStateQuery()
    result = q.run("world_model_forecast")  # missing required `target`
    assert "error" in result
    assert "target" in result["error"]


# ─── Sprint F++++ — multi-turn continuation ──────────────────────────────


def test_continue_preserves_prior_turns_and_appends_new_question():
    """A second-turn question runs on top of the first turn's trace.
    The new trace must contain the prior system + user + assistant
    + tool turns, plus the new user turn."""
    from src.copilot.rlm.agent import run_rlm_agent_continue

    q = FactoryStateQuery(state=_StubState(), queries=_StubSemantic())
    llm1 = _canned_llm([
        '{"action": "query", "name": "bottlenecks"}',
        '{"action": "answer", "text": "Laminagem é o gargalo."}',
    ])
    first = asyncio.run(run_rlm_agent(
        question="Qual é o gargalo?", state_query=q, llm=llm1, max_steps=4,
    ))
    assert first.answer == "Laminagem é o gargalo."

    llm2 = _canned_llm([
        '{"action": "answer", "text": "Como já vi, o gargalo é Laminagem."}',
    ])
    second = asyncio.run(run_rlm_agent_continue(
        prior_trace=first,
        question="E porquê?",
        state_query=q, llm=llm2, max_steps=4,
    ))
    # The second trace inherits the first's turns plus the new user.
    roles = [t.role for t in second.turns]
    assert roles[0] == "system"
    assert "user" in roles[1:]   # original user question still there
    assert second.turns[-2].role == "user"  # the new follow-up
    assert second.turns[-2].content == "E porquê?"
    assert "Laminagem" in (second.answer or "")


def test_continue_truncates_old_turns_when_history_exceeds_budget():
    """With a tight ``max_history_chars``, the oldest non-system turns
    are dropped to fit the budget — keeping system prompt + recent
    exchange."""
    from src.copilot.rlm.agent import AgentTrace, run_rlm_agent_continue

    # Build a synthetic prior trace with bloated content.
    big_filler = "X" * 2000
    prior = AgentTrace(question="initial")
    prior.turns = [
        AgentTurn(role="system", content="SYS"),
        AgentTurn(role="user", content="initial " + big_filler),
        AgentTurn(role="assistant", content='{"action": "answer", "text": "ok"}'),
        AgentTurn(role="tool", content=big_filler),
        AgentTurn(role="user", content="middle"),
        AgentTurn(role="assistant", content='{"action": "answer", "text": "ok2"}'),
    ]
    q = FactoryStateQuery()
    llm = _canned_llm(['{"action": "answer", "text": "third"}'])
    new_trace = asyncio.run(run_rlm_agent_continue(
        prior_trace=prior,
        question="latest",
        state_query=q, llm=llm,
        max_history_chars=300,  # very tight — must drop most old turns
    ))
    # System turn always preserved.
    assert any(t.role == "system" and t.content == "SYS" for t in new_trace.turns)
    # The big filler must have been dropped from old user/tool turns.
    assert all("X" * 1000 not in t.content for t in new_trace.turns)
    # The new question is in.
    assert any(t.content == "latest" for t in new_trace.turns)


def test_continue_starts_fresh_queries_run_per_turn():
    """``queries_run`` belongs to THIS turn only — the caller knows
    which sub-queries were issued in response to the new question."""
    from src.copilot.rlm.agent import run_rlm_agent_continue

    q = FactoryStateQuery()
    llm1 = _canned_llm([
        '{"action": "query", "name": "wip"}',
        '{"action": "answer", "text": "a"}',
    ])
    first = asyncio.run(run_rlm_agent(
        question="state?", state_query=q, llm=llm1, max_steps=4,
    ))
    assert len(first.queries_run) == 1

    llm2 = _canned_llm([
        '{"action": "query", "name": "bottlenecks"}',
        '{"action": "answer", "text": "b"}',
    ])
    second = asyncio.run(run_rlm_agent_continue(
        prior_trace=first, question="follow-up?",
        state_query=q, llm=llm2, max_steps=4,
    ))
    # Fresh log — the prior wip call is NOT in the second turn's log.
    assert len(second.queries_run) == 1
    assert second.queries_run[0]["name"] == "bottlenecks"


def test_agent_chains_world_model_forecast_then_answer_with_p50():
    """End-to-end: LLM picks world_model_forecast → tool result has
    a trajectory with quantiles → answer cites the p50/p95 from the
    last step verbatim."""
    q = FactoryStateQuery()
    forecast_result = q.world_model_forecast(
        "throughput_eur_day", horizon_steps=4, samples=80,
    )
    horizon_p50 = forecast_result["trajectory"][-1]["p50"]
    horizon_p95 = forecast_result["trajectory"][-1]["p95"]

    llm = _canned_llm([
        '{"action": "query", "name": "world_model_forecast", '
        '"params": {"target": "throughput_eur_day", "horizon_steps": 4}}',
        '{"action": "answer", "text": '
        f'"Trajectória de throughput: p50={horizon_p50}, p95={horizon_p95} "}}',
    ])
    trace = asyncio.run(run_rlm_agent(
        question="Como vai evoluir o throughput nos próximos 4 turnos?",
        state_query=q, llm=llm, max_steps=4,
    ))
    assert trace.terminated_reason == "complete"
    assert trace.steps_used == 2
    assert len(trace.queries_run) == 1
    assert trace.queries_run[0]["name"] == "world_model_forecast"
    assert str(horizon_p50) in (trace.answer or "")
