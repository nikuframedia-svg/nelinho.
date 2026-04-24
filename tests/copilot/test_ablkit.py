"""Sprint I.2 — ABLkit divergence detection + DPO export.

Covers:
* ``detect_divergences`` returns nothing for a passing chain.
* Sign-mismatch claims produce a `kernel` layer divergence tagged
  ``severity=major``.
* Unknown-node claims produce a ``dag_consistent`` divergence tagged
  ``severity=contradiction``.
* Per-divergence DPO triplet has the expected prompt / chosen /
  rejected shape with ABLkit meta.
* :class:`DivergenceStore` appends → loads → exports JSONL round-trip.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from src.copilot.causal import (
    CausalChain,
    CausalClaim,
    Divergence,
    DivergenceStore,
    causal_query,
    detect_divergences,
    render_dpo_triplet,
    verify_chain,
)


# ─── Helpers ──────────────────────────────────────────────────────────────


def _good_chain_b() -> CausalChain:
    """Well-formed chain: routing B → makespan goes down."""
    kernel = causal_query("makespan_hours", do={"routing_variant": 1.0})
    return CausalChain(
        question="O que acontece ao makespan se mudarmos para a variante B?",
        target="makespan_hours",
        root_cause="routing_variant",
        mechanism=[
            CausalClaim(node="laminagem_duration", direction="decrease"),
            CausalClaim(
                node="makespan_hours",
                direction="decrease",
                magnitude=abs(kernel.delta),
            ),
        ],
        confidence=0.8,
    )


# ─── detect_divergences ───────────────────────────────────────────────────


def test_no_divergence_for_passing_chain():
    chain = _good_chain_b()
    kernel = causal_query("makespan_hours", do={"routing_variant": 1.0})
    result = verify_chain(chain, kernel_result=kernel)
    assert result.passed
    assert detect_divergences(chain, result, kernel_delta=kernel.delta) == []


def test_sign_mismatch_yields_major_kernel_divergence():
    kernel = causal_query("makespan_hours", do={"routing_variant": 1.0})
    # Kernel says makespan decreases; chain claims it increases.
    bad = CausalChain(
        question="E se mudarmos para a variante B?",
        target="makespan_hours",
        root_cause="routing_variant",
        mechanism=[
            CausalClaim(node="laminagem_duration", direction="decrease"),
            CausalClaim(
                node="makespan_hours",
                direction="increase",
                magnitude=abs(kernel.delta),
            ),
        ],
        confidence=0.7,
    )
    result = verify_chain(bad, kernel_result=kernel)
    assert not result.passed

    divs = detect_divergences(bad, result, kernel_delta=kernel.delta)
    assert any(d.layer == "kernel" for d in divs)
    assert all(d.severity in {"major", "contradiction"} for d in divs)
    kernel_div = next(d for d in divs if d.layer == "kernel")
    assert kernel_div.claimed["direction"] == "increase"
    assert kernel_div.kernel["delta"] == pytest.approx(kernel.delta)


def test_unknown_node_yields_contradiction_severity():
    bad = CausalChain(
        question="Pergunta inventada",
        target="makespan_hours",
        root_cause="UNKNOWN_NODE",
        mechanism=[CausalClaim(node="makespan_hours", direction="decrease")],
        confidence=0.5,
    )
    result = verify_chain(bad)
    divs = detect_divergences(bad, result)
    assert any(d.layer == "dag_consistent" for d in divs)
    assert all(d.severity == "contradiction" for d in divs)


# ─── DPO triplet rendering ────────────────────────────────────────────────


def test_render_dpo_triplet_carries_kernel_truth_in_chosen():
    div = Divergence(
        question="Porquê o makespan aumentou?",
        target="makespan_hours",
        claimed={"direction": "increase", "magnitude": 40.0, "rationale": None},
        kernel={"delta": -12.0},
        layer="kernel",
        severity="major",
        description="sign mismatch",
        coherence=0.3,
        tenant_id="tenant-1",
    )
    triplet = render_dpo_triplet(div)
    assert "makespan_hours" in triplet["prompt"]
    # Kernel says DECREASE → chosen must reflect that
    assert "desce" in triplet["chosen"].lower() or "estável" in triplet["chosen"].lower()
    # Rejected carries the LLM's bad claim
    assert "sobe" in triplet["rejected"].lower() or "increase" in triplet["rejected"].lower()
    assert triplet["meta"]["source"] == "ablkit"
    assert triplet["meta"]["layer"] == "kernel"
    assert triplet["meta"]["tenant_id"] == "tenant-1"


def test_render_dpo_triplet_without_magnitude_still_structured():
    div = Divergence(
        question="?",
        target="throughput_eur_day",
        claimed={"direction": "decrease", "magnitude": None, "rationale": None},
        kernel={},
        layer="nli",
        severity="minor",
        description="direction only",
        coherence=0.6,
    )
    triplet = render_dpo_triplet(div)
    assert set(triplet.keys()) == {"prompt", "chosen", "rejected", "meta"}
    assert "throughput_eur_day" in triplet["prompt"]


# ─── DivergenceStore ─────────────────────────────────────────────────────


def test_store_append_load_roundtrip(tmp_path: Path):
    store = DivergenceStore(tmp_path / "divergences.jsonl")
    divs = [
        Divergence(
            question="q1", target="makespan_hours",
            claimed={"direction": "increase", "magnitude": 10.0},
            kernel={"delta": -12.0},
            layer="kernel", severity="major",
            description="sign mismatch", coherence=0.3,
        ),
        Divergence(
            question="q2", target="throughput_eur_day",
            claimed={"direction": "decrease"},
            kernel={},
            layer="direction", severity="major",
            description="not reachable", coherence=0.4,
        ),
    ]
    assert store.append(divs) == 2
    loaded = store.load_all()
    assert len(loaded) == 2
    assert loaded[0].target == "makespan_hours"
    assert loaded[1].layer == "direction"


def test_store_export_dpo_writes_valid_jsonl(tmp_path: Path):
    store = DivergenceStore(tmp_path / "divs.jsonl")
    store.append([
        Divergence(
            question="?", target="makespan_hours",
            claimed={"direction": "increase", "magnitude": 40.0},
            kernel={"delta": -12.0},
            layer="kernel", severity="major",
            description="sign mismatch", coherence=0.3,
        ),
    ])
    output = tmp_path / "dpo_ablkit.jsonl"
    count = store.export_dpo(output)
    assert count == 1
    lines = output.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert set(payload.keys()) == {"prompt", "chosen", "rejected", "meta"}
    assert payload["meta"]["source"] == "ablkit"


def test_store_load_handles_missing_file(tmp_path: Path):
    store = DivergenceStore(tmp_path / "never-created.jsonl")
    assert store.load_all() == []
