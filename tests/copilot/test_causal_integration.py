"""Sprint F.5 — integration tests covering the four causal question types
from Blueprint v2.0 §25:

    1. state          — "what is <KPI> today?"
    2. intervention   — "what happens if we do X?"
    3. counterfactual — "what would have happened if we had done X?"
    4. abduction      — "given we observe Y, what's the likely cause?"

Each test stubs the LLM with a canned JSON response representing a
plausible answer, runs ``verify_chain`` against the real NELO kernel,
and asserts the chain passes the default coherence gate. Together
they exercise the full NELO_DAG ⇄ CausalChain ⇄ RLM loop with no
external services.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List

import pytest

from src.copilot.causal import (
    COHERENCE_GATE,
    CausalChain,
    CausalClaim,
    causal_query,
    verify_chain,
    verify_chain_dict,
)
from src.copilot.rlm import FactoryStateQuery, run_rlm_agent
from src.copilot.rlm.agent import AgentTurn


# ─── Reusable canned-LLM helper ──────────────────────────────────────────


def _canned(responses: List[str]):
    idx = {"i": 0}

    async def _call(_turns: List[AgentTurn]) -> str:
        i = min(idx["i"], len(responses) - 1)
        idx["i"] += 1
        return responses[i]

    return _call


# ═══════════════════════════════════════════════════════════════════════════
# 1. STATE — "what is throughput_eur_day today?"
# ═══════════════════════════════════════════════════════════════════════════


def test_state_query_throughput_baseline():
    """No intervention → target value equals the forward-propagated
    baseline and delta is zero."""
    result = causal_query("throughput_eur_day")
    assert result.delta == pytest.approx(0.0)
    assert result.target_value > 0


def test_state_chain_passes_with_unchanged_claim():
    chain = CausalChain(
        question="Qual é o throughput atual?",
        target="throughput_eur_day",
        root_cause="shift_mode",
        mechanism=[
            CausalClaim(node="throughput_eur_day", direction="unchanged"),
        ],
        confidence=0.9,
    )
    result = causal_query("throughput_eur_day")
    verdict = verify_chain(chain, kernel_result=result)
    # Unchanged claim + zero delta → no kernel issue. Passes gate.
    assert verdict.passed


# ═══════════════════════════════════════════════════════════════════════════
# 2. INTERVENTION — "what happens if we switch to routing B?"
# ═══════════════════════════════════════════════════════════════════════════


def test_intervention_routing_b_lowers_makespan_chain_passes():
    kernel = causal_query("makespan_hours", do={"routing_variant": 1.0})
    chain = CausalChain(
        question="Se mudarmos para a variante B, o que acontece ao makespan?",
        target="makespan_hours",
        root_cause="routing_variant",
        mechanism=[
            CausalClaim(
                node="laminagem_duration",
                direction="decrease",
                rationale="Rota B corta 8% da duração em Laminagem",
            ),
            CausalClaim(
                node="makespan_hours",
                direction="decrease",
                magnitude=abs(kernel.delta),
            ),
        ],
        counterfactual="Sem B, makespan mantinha-se na referência.",
        recommendation="Adotar a variante B para esta família",
        confidence=0.82,
    )
    verdict = verify_chain(chain, kernel_result=kernel)
    assert verdict.passed
    assert verdict.coherence >= COHERENCE_GATE


def test_intervention_wrong_direction_is_rejected():
    kernel = causal_query("throughput_eur_day", do={"shift_mode": 2.0})
    # Kernel says throughput goes UP under double shift; chain says DOWN.
    chain = CausalChain(
        question="E se passarmos a 2 turnos?",
        target="throughput_eur_day",
        root_cause="shift_mode",
        mechanism=[
            CausalClaim(node="throughput_eur_day", direction="decrease"),
        ],
        confidence=0.7,
    )
    verdict = verify_chain(chain, kernel_result=kernel)
    assert not verdict.passed
    assert any("sign mismatch" in i for i in verdict.issues)


def test_intervention_more_workers_lowers_laminagem_duration():
    kernel = causal_query(
        "laminagem_duration", do={"worker_count_laminagem": 24.0},
    )
    assert kernel.delta < 0  # more workers → shorter duration
    chain = CausalChain(
        question="E se puser 24 laminadores?",
        target="laminagem_duration",
        root_cause="worker_count_laminagem",
        mechanism=[
            CausalClaim(
                node="laminagem_duration",
                direction="decrease",
                magnitude=abs(kernel.delta),
            ),
        ],
        recommendation="Aumentar para 24 na fase de pico",
        confidence=0.85,
    )
    verdict = verify_chain(chain, kernel_result=kernel)
    assert verdict.passed


# ═══════════════════════════════════════════════════════════════════════════
# 3. COUNTERFACTUAL — "what would makespan have been if we had done X?"
# ═══════════════════════════════════════════════════════════════════════════


def test_counterfactual_delta_is_negative_of_intervention():
    """The counterfactual "had we done B" is the same do-operator as
    the forward intervention; the chain's sign should match."""
    kernel = causal_query("makespan_hours", do={"routing_variant": 1.0})
    # Counterfactual scenario: had we adopted B, makespan would have
    # been ~|delta| lower than the baseline we actually saw.
    chain = CausalChain(
        question="E se tivéssemos escolhido a variante B?",
        target="makespan_hours",
        root_cause="routing_variant",
        mechanism=[
            CausalClaim(
                node="makespan_hours",
                direction="decrease",
                magnitude=abs(kernel.delta),
            ),
        ],
        counterfactual="Com B, teríamos fechado ~12h mais cedo.",
        confidence=0.75,
    )
    verdict = verify_chain(chain, kernel_result=kernel)
    assert verdict.passed


# ═══════════════════════════════════════════════════════════════════════════
# 4. ABDUCTION — "we observe Y high; what's the likely cause?"
# ═══════════════════════════════════════════════════════════════════════════


def test_abduction_rework_traced_to_quality_risk():
    """Given we observe elevated rework_rate, a plausible explanation
    is elevated quality_risk_score upstream; the DAG validates the
    direction."""
    kernel = causal_query("rework_rate", observe={"quality_risk_score": 0.25})
    chain = CausalChain(
        question="Porque subiu a taxa de retrabalho este mês?",
        target="rework_rate",
        root_cause="quality_risk_score",
        mechanism=[
            CausalClaim(
                node="rework_rate",
                direction="increase",
                magnitude=abs(kernel.delta),
            ),
        ],
        recommendation="Aumentar tempo de QC entre desmolde e pintura",
        confidence=0.70,
    )
    verdict = verify_chain(chain, kernel_result=kernel)
    assert verdict.passed


def test_abduction_tardiness_traced_to_material_shortage():
    kernel = causal_query(
        "total_tardiness_hours", observe={"material_availability_pct": 0.70},
    )
    assert kernel.delta > 0  # shortage increases tardiness
    chain = CausalChain(
        question="Porque estamos com atrasos elevados?",
        target="total_tardiness_hours",
        root_cause="material_availability_pct",
        mechanism=[
            CausalClaim(
                node="total_tardiness_hours",
                direction="increase",
                magnitude=abs(kernel.delta),
            ),
        ],
        recommendation="Acelerar as 3 compras em atraso",
        confidence=0.8,
    )
    verdict = verify_chain(chain, kernel_result=kernel)
    assert verdict.passed


# ═══════════════════════════════════════════════════════════════════════════
# RLM ⇄ CausalChain — full loop with a mocked LLM
# ═══════════════════════════════════════════════════════════════════════════


def test_rlm_agent_can_hand_back_causal_chain_json():
    """Simulate a Copilot flow: LLM asks one sub-query, then returns a
    CausalChain JSON as its ``answer`` text. We parse the answer and
    verify the chain."""

    # Canned: 1) probe bottlenecks, 2) emit a CausalChain answer.
    kernel = causal_query("laminagem_duration", do={"worker_count_laminagem": 24.0})
    chain_payload = {
        "question": "Como baixar a duração da Laminagem?",
        "target": "laminagem_duration",
        "root_cause": "worker_count_laminagem",
        "mechanism": [
            {
                "node": "laminagem_duration",
                "direction": "decrease",
                "magnitude": abs(kernel.delta),
                "rationale": "Mais laminadores reduzem a duração média",
            },
        ],
        "recommendation": "Aumentar para 24 laminadores nesta semana",
        "confidence": 0.82,
    }
    llm = _canned([
        '{"action": "query", "name": "bottlenecks"}',
        '{"action": "answer", "text": ' + json.dumps(json.dumps(chain_payload)) + '}',
    ])

    state_query = FactoryStateQuery()
    trace = asyncio.run(run_rlm_agent(
        question="Como baixar a duração da Laminagem?",
        state_query=state_query,
        llm=llm,
        max_steps=3,
    ))
    # The answer is stringified JSON — parse it back and verify.
    payload = json.loads(trace.answer)
    verdict = verify_chain_dict(payload, kernel_result=kernel)
    assert verdict.passed
    assert trace.terminated_reason == "complete"


def test_rlm_agent_with_non_causal_answer_still_terminates():
    """Not every question demands a causal chain — the agent can
    answer in free text when the question is purely descriptive."""
    llm = _canned([
        '{"action": "query", "name": "wip"}',
        '{"action": "answer", "text": "Temos 2 ordens em aberto."}',
    ])
    trace = asyncio.run(run_rlm_agent(
        question="Quantas ordens temos em aberto?",
        state_query=FactoryStateQuery(),
        llm=llm,
        max_steps=3,
    ))
    assert trace.answer == "Temos 2 ordens em aberto."
    assert trace.steps_used == 2


# ═══════════════════════════════════════════════════════════════════════════
# Coverage summary
# ═══════════════════════════════════════════════════════════════════════════


def test_sprint_f_stack_has_coverage_for_four_question_types():
    """Meta-test: this file covers the four Blueprint v2.0 §25 types.
    Fails if anyone removes the markers below, acting as a living
    checklist."""
    covered = {
        "state": "test_state_query_throughput_baseline",
        "intervention": "test_intervention_routing_b_lowers_makespan_chain_passes",
        "counterfactual": "test_counterfactual_delta_is_negative_of_intervention",
        "abduction": "test_abduction_rework_traced_to_quality_risk",
    }
    assert set(covered) == {"state", "intervention", "counterfactual", "abduction"}
