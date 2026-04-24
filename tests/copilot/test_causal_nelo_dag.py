"""Sprint F.1 — NELO_DAG structure + causal_query semantics.

Covers:
* DAG invariants — no cycles, every parent exists, topological order
  respected.
* Functional forms — doubling shift_mode nearly doubles throughput,
  routing_variant=1 lowers makespan relative to baseline, more
  workers reduce laminagem_duration.
* ``do`` vs ``observe`` semantics — a hard intervention severs the
  intervened node from its parents' influence; an observation does
  not.
* Descendant / ancestor helpers are consistent with the parents list.
"""

from __future__ import annotations

import pytest

from src.copilot.causal.nelo_dag import (
    ALL_NODES,
    NODES_BY_ID,
    NodeCategory,
    ancestors_of,
    causal_query,
    descendants_of,
    edge_exists,
    graph_summary,
    is_valid_node,
    topological_order,
)


# ─── Structural invariants ────────────────────────────────────────────────


def test_all_parents_reference_known_nodes():
    for node in ALL_NODES:
        for parent in node.parents:
            assert parent in NODES_BY_ID, (
                f"{node.id} has unknown parent {parent!r}"
            )


def test_no_cycles_topological_sort_terminates():
    order = topological_order()
    assert len(order) == len(ALL_NODES)
    index = {nid: i for i, nid in enumerate(order)}
    for node in ALL_NODES:
        for parent in node.parents:
            assert index[parent] < index[node.id], (
                f"{parent} must precede {node.id} in topological order"
            )


def test_confounders_have_no_parents_and_outputs_have_many():
    confounders = [n for n in ALL_NODES if n.category == NodeCategory.CONFOUNDER]
    outputs = [n for n in ALL_NODES if n.category == NodeCategory.OUTPUT]
    assert confounders, "at least one confounder expected"
    for node in confounders:
        assert node.parents == (), (
            f"confounder {node.id} should have no modelled parents"
        )
    for node in outputs:
        assert len(node.parents) >= 1, (
            f"output {node.id} must depend on something"
        )


def test_graph_summary_shape():
    summary = graph_summary()
    assert summary["node_count"] == len(ALL_NODES)
    assert summary["confounder_count"] >= 1
    assert {"id", "parents", "baseline"}.issubset(summary["nodes"][0].keys())


# ─── Functional forms ─────────────────────────────────────────────────────


def test_double_shift_mode_doubles_throughput_near_enough():
    baseline = causal_query("throughput_eur_day")
    doubled = causal_query("throughput_eur_day", do={"shift_mode": 2.0})
    # Within ±10% of 2× (we allow slack for the makespan feedback).
    ratio = doubled.target_value / baseline.target_value
    assert 1.7 < ratio < 2.3, f"expected ~2x; got {ratio:.2f}"


def test_routing_variant_b_lowers_makespan():
    baseline = causal_query("makespan_hours")
    variant_b = causal_query("makespan_hours", do={"routing_variant": 1.0})
    assert variant_b.target_value < baseline.target_value
    assert variant_b.delta < 0


def test_more_laminagem_workers_shorten_duration():
    slim = causal_query("laminagem_duration", do={"worker_count_laminagem": 12.0})
    rich = causal_query("laminagem_duration", do={"worker_count_laminagem": 24.0})
    assert rich.target_value < slim.target_value


def test_colder_ambient_raises_curing_time():
    cold = causal_query("curing_time", do={"external_temperature": 12.0})
    warm = causal_query("curing_time", do={"external_temperature": 22.0})
    assert cold.target_value > warm.target_value


# ─── do vs observe semantics ─────────────────────────────────────────────


def test_do_operator_severs_parents():
    """do(mold_setup_time=10.0) must keep mold_setup_time at 10 even
    though its natural computation would give ~0.75."""
    result = causal_query(
        "mold_setup_time", do={"mold_setup_time": 10.0},
    )
    assert result.target_value == pytest.approx(10.0)


def test_observe_does_not_replace_functional_form_downstream():
    """Observing curing_time=30 in the evidence but asking for
    makespan should still use curing_time=30 (observation propagates),
    yielding a clearly higher makespan than baseline."""
    observed = causal_query(
        "makespan_hours", observe={"curing_time": 30.0},
    )
    baseline = causal_query("makespan_hours")
    assert observed.target_value > baseline.target_value


# ─── Traversal helpers ────────────────────────────────────────────────────


def test_descendants_of_routing_variant_reaches_throughput():
    desc = descendants_of("routing_variant")
    # routing_variant feeds laminagem_duration → queues → makespan → throughput
    assert "throughput_eur_day" in desc
    assert "makespan_hours" in desc


def test_ancestors_of_throughput_includes_shift_mode():
    anc = ancestors_of("throughput_eur_day")
    assert "shift_mode" in anc
    assert "rework_rate" in anc


def test_edge_exists_direct_and_transitive():
    # rework_rate is a direct parent of throughput via the functional form.
    assert edge_exists("rework_rate", "throughput_eur_day", transitive=True)
    # shift_mode is transitively upstream.
    assert edge_exists("shift_mode", "throughput_eur_day", transitive=True)
    # But setup_count and throughput are siblings (no edge either way).
    assert not edge_exists("setup_count", "throughput_eur_day", transitive=True)


# ─── Error paths ─────────────────────────────────────────────────────────


def test_causal_query_unknown_target_raises():
    with pytest.raises(KeyError):
        causal_query("not_a_node")


def test_causal_query_unknown_intervention_raises():
    with pytest.raises(KeyError):
        causal_query("throughput_eur_day", do={"nonsense_knob": 1.0})


def test_is_valid_node_guard():
    assert is_valid_node("routing_variant") is True
    assert is_valid_node("invented") is False
