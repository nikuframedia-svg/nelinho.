"""Sprint F.2 — CausalChain + verify_chain (5-layer validator).

Covers every verification layer:
* syntactic (empty mechanism / tautology catch)
* dag_consistent (unknown node names)
* direction (root_cause → target reachability, mechanism on-path)
* nli (recommendation vs mechanism contradictions)
* kernel (magnitude + sign vs causal_query result)

Plus the composite ``verify_chain`` + ``verify_chain_dict`` entry
points and the COHERENCE_GATE default.
"""

from __future__ import annotations

import pytest

from src.copilot.causal.chain import (
    COHERENCE_GATE,
    CausalChain,
    CausalClaim,
    CausalVerificationResult,
    LayerVerdict,
    verify_chain,
    verify_chain_dict,
)
from src.copilot.causal.nelo_dag import causal_query


# ─── Helpers ──────────────────────────────────────────────────────────────


def _good_chain(**overrides):
    """Build a well-formed chain. Tests perturb one field at a time."""
    base = dict(
        question="Porquê que o makespan baixa se trocarmos para variante B?",
        target="makespan_hours",
        root_cause="routing_variant",
        mechanism=[
            CausalClaim(
                node="laminagem_duration",
                direction="decrease",
                rationale="Rota B salta a colagem intermédia",
            ),
            CausalClaim(
                node="makespan_hours",
                direction="decrease",
                magnitude=20.0,
            ),
        ],
        counterfactual="Sem variante B ficaríamos a 260 h.",
        recommendation="Adotar a variante B nesta família",
        confidence=0.8,
    )
    base.update(overrides)
    return CausalChain(**base)


def _kernel_for_routing_b():
    return causal_query("makespan_hours", do={"routing_variant": 1.0})


# ─── Syntactic layer ──────────────────────────────────────────────────────


def test_syntactic_flags_empty_mechanism():
    chain = _good_chain(mechanism=[])
    result = verify_chain(chain)
    assert result.layer("syntactic").passed is False
    assert "mechanism is empty" in " ".join(result.issues)


def test_syntactic_flags_tautology():
    chain = _good_chain(root_cause="makespan_hours")
    result = verify_chain(chain)
    assert result.layer("syntactic").passed is False


def test_syntactic_pydantic_rejects_bad_direction():
    with pytest.raises(Exception):
        CausalClaim(node="makespan_hours", direction="wiggle")


# ─── DAG-consistent layer ─────────────────────────────────────────────────


def test_dag_layer_catches_unknown_node():
    chain = _good_chain(root_cause="UNKNOWN_NODE")
    result = verify_chain(chain)
    assert result.layer("dag_consistent").passed is False
    assert not result.passed


def test_dag_layer_passes_on_valid_names():
    result = verify_chain(_good_chain())
    assert result.layer("dag_consistent").passed is True


# ─── Direction layer ──────────────────────────────────────────────────────


def test_direction_flags_mechanism_step_off_path():
    # external_temperature is not a descendant of routing_variant →
    # it can't legitimately sit on the mechanism path from routing_variant.
    chain = _good_chain(
        mechanism=[
            CausalClaim(node="external_temperature", direction="unchanged"),
            CausalClaim(node="makespan_hours", direction="decrease"),
        ],
    )
    result = verify_chain(chain)
    assert result.layer("direction").passed is False


def test_direction_flags_disconnected_root_cause():
    # setup_count doesn't feed into throughput_eur_day transitively.
    chain = _good_chain(
        target="throughput_eur_day",
        root_cause="setup_count",
        mechanism=[
            CausalClaim(node="throughput_eur_day", direction="decrease"),
        ],
    )
    result = verify_chain(chain)
    assert result.layer("direction").passed is False


# ─── NLI layer ────────────────────────────────────────────────────────────


def test_nli_flags_recommendation_contradicting_mechanism():
    # Mechanism: "increase worker_count" → "decrease laminagem_duration"
    # Recommendation: "reduce workforce" → contradiction.
    chain = _good_chain(
        target="laminagem_duration",
        root_cause="worker_count_laminagem",
        mechanism=[
            CausalClaim(node="worker_count_laminagem", direction="increase"),
            CausalClaim(node="laminagem_duration", direction="decrease"),
        ],
        recommendation="reduce crew to cut cost",
    )
    result = verify_chain(chain)
    nli = result.layer("nli")
    assert nli.passed is False
    assert any("reducing" in i.lower() for i in nli.issues)


def test_nli_aligns_with_kernel_direction():
    """When kernel_result confirms the target direction, nli passes."""
    chain = _good_chain()
    kernel = _kernel_for_routing_b()
    result = verify_chain(chain, kernel_result=kernel)
    assert result.layer("nli").passed is True


# ─── Kernel layer ─────────────────────────────────────────────────────────


def test_kernel_layer_rewards_close_magnitude():
    """Claim magnitude near the kernel delta → full credit."""
    kernel = _kernel_for_routing_b()
    chain = _good_chain(
        mechanism=[
            CausalClaim(
                node="laminagem_duration", direction="decrease",
            ),
            CausalClaim(
                node="makespan_hours",
                direction="decrease",
                magnitude=abs(kernel.delta),
            ),
        ],
    )
    result = verify_chain(chain, kernel_result=kernel)
    assert result.layer("kernel").passed is True
    assert result.layer("kernel").score > 0.9


def test_kernel_layer_penalises_sign_mismatch():
    kernel = _kernel_for_routing_b()  # delta < 0 (B lowers makespan)
    chain = _good_chain(
        mechanism=[
            CausalClaim(node="laminagem_duration", direction="decrease"),
            CausalClaim(
                node="makespan_hours",
                direction="increase",
                magnitude=abs(kernel.delta),
            ),
        ],
    )
    result = verify_chain(chain, kernel_result=kernel)
    assert result.layer("kernel").passed is False
    assert any("sign mismatch" in i for i in result.layer("kernel").issues)


def test_kernel_layer_without_reference_gives_partial_credit():
    chain = _good_chain()
    result = verify_chain(chain)  # no kernel_result, no do
    k = result.layer("kernel")
    assert k.passed is False
    assert k.score == pytest.approx(0.5)


def test_kernel_layer_direction_only_gets_partial_credit_when_no_magnitude():
    """A claim without magnitude but right direction → 0.8 score."""
    kernel = _kernel_for_routing_b()
    chain = _good_chain(
        mechanism=[
            CausalClaim(node="laminagem_duration", direction="decrease"),
            CausalClaim(node="makespan_hours", direction="decrease"),
        ],
    )
    result = verify_chain(chain, kernel_result=kernel)
    k = result.layer("kernel")
    assert k.score == pytest.approx(0.8)
    assert k.passed is True


# ─── Composite entry + gate ──────────────────────────────────────────────


def test_verify_chain_auto_runs_kernel_when_do_given():
    chain = _good_chain()
    result = verify_chain(chain, do={"routing_variant": 1.0})
    # kernel layer should be non-default
    k = result.layer("kernel")
    assert k.score != 0.5


def test_verify_chain_dict_catches_invalid_payload():
    bad = {"question": "", "target": "makespan_hours"}  # missing required fields
    result = verify_chain_dict(bad)
    assert result.coherence == 0.0
    assert result.passed is False
    assert any("not a valid CausalChain" in i for i in result.issues)


def test_full_well_formed_chain_clears_default_gate():
    kernel = _kernel_for_routing_b()
    chain = _good_chain(
        mechanism=[
            CausalClaim(node="laminagem_duration", direction="decrease"),
            CausalClaim(
                node="makespan_hours",
                direction="decrease",
                magnitude=abs(kernel.delta),
            ),
        ],
    )
    result = verify_chain(chain, kernel_result=kernel)
    assert result.passed
    assert result.coherence >= COHERENCE_GATE


def test_malformed_chain_does_not_pass_gate():
    chain = _good_chain(root_cause="UNKNOWN_NODE")
    result = verify_chain(chain)
    assert not result.passed
    assert result.coherence < COHERENCE_GATE
