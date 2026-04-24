"""Sprint A C1 — chromosome.routing_choices honoured by the decoder.

Before this fix the decoder silently ignored `chromosome.routing_choices`
so the GA could mutate the field forever without ever producing a
different schedule. Now variant "B" flips the machine-selection priority
to try `alternative_machines` first — same op, different machine path.

Covers:
* variant "B" with alternative_machines → picks the alt machine
* variant "A" (default) → picks the primary machine
* variant "B" with NO alternative_machines → falls back to primary
  (no infeasibility, no crash)
* empty routing_choices → behaves identically to pre-C1 decoder
* `routing_variants_applied` counter reflects how many ops flipped
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from src.plan.cpo.chromosome import Chromosome
from src.plan.cpo.decoder import decode
from src.plan.cpo.state import FactoryState
from src.plan.engines.scheduling_adapter import SchedulingMachine, SchedulingOperation


def _machine(mid: str) -> SchedulingMachine:
    return SchedulingMachine(machine_id=mid, name=mid)


def _op(
    op_id: str,
    *,
    machine_id: str = "M_PRIMARY",
    alternative_machines=None,
) -> SchedulingOperation:
    return SchedulingOperation(
        operation_id=op_id,
        order_id="OF1",
        product_id="P1",
        sequence=1,
        operation_code=op_id,
        duration_minutes=60,
        machine_id=machine_id,
        alternative_machines=list(alternative_machines or []),
        phase_id="PHASE_A",
    )


def _run(ops, machines, *, routing_choices=None):
    state = FactoryState(tenant_id=uuid4())
    horizon_start = datetime(2026, 4, 22, 8, 0)
    horizon_end = horizon_start + timedelta(days=2)
    chrom = Chromosome(
        permutation=list(range(len(ops))),
        routing_choices=dict(routing_choices or {}),
    )
    return decode(chrom, ops, machines, state, horizon_start, horizon_end)


# ---------------------------------------------------------------------------
# Basic variant selection
# ---------------------------------------------------------------------------


def test_variant_b_with_alt_picks_alt_machine():
    ops = [_op("O1", machine_id="M_PRIMARY", alternative_machines=["M_ALT"])]
    machines = [_machine("M_PRIMARY"), _machine("M_ALT")]
    result = _run(ops, machines, routing_choices={"O1": "B"})

    assert result["operations"][0]["machine_id"] == "M_ALT"
    assert result["routing_variants_applied"] == 1


def test_variant_a_keeps_primary_machine():
    ops = [_op("O1", machine_id="M_PRIMARY", alternative_machines=["M_ALT"])]
    machines = [_machine("M_PRIMARY"), _machine("M_ALT")]
    result = _run(ops, machines, routing_choices={"O1": "A"})

    assert result["operations"][0]["machine_id"] == "M_PRIMARY"
    assert result["routing_variants_applied"] == 0


def test_variant_b_without_alts_falls_back_to_primary():
    """A route-B request on an op that has no alt is not infeasible —
    we schedule on the primary and leave the counter at 0.
    """
    ops = [_op("O1", machine_id="M_PRIMARY", alternative_machines=[])]
    machines = [_machine("M_PRIMARY")]
    result = _run(ops, machines, routing_choices={"O1": "B"})

    assert result["operations"][0]["machine_id"] == "M_PRIMARY"
    assert result["routing_variants_applied"] == 0
    assert result["infeasible_op_ids"] == []


def test_empty_routing_choices_is_backward_compatible():
    """No routing_choices map → decoder behaves exactly like pre-C1."""
    ops = [_op("O1", machine_id="M_PRIMARY", alternative_machines=["M_ALT"])]
    machines = [_machine("M_PRIMARY"), _machine("M_ALT")]
    result = _run(ops, machines, routing_choices={})

    assert result["operations"][0]["machine_id"] == "M_PRIMARY"
    assert result["routing_variants_applied"] == 0


# ---------------------------------------------------------------------------
# Multi-op counter
# ---------------------------------------------------------------------------


def test_routing_variants_applied_counts_each_flip():
    ops = [
        _op("O1", machine_id="M_PRIMARY", alternative_machines=["M_ALT"]),
        _op("O2", machine_id="M_PRIMARY", alternative_machines=["M_ALT"]),
        _op("O3", machine_id="M_PRIMARY", alternative_machines=["M_ALT"]),
    ]
    # Each op in its own order so they don't force sequencing.
    for i, op in enumerate(ops):
        op.order_id = f"OF{i}"
        op.sequence = 1
    machines = [_machine("M_PRIMARY"), _machine("M_ALT")]
    result = _run(
        ops, machines,
        routing_choices={"O1": "B", "O3": "B"},  # O2 stays default "A"
    )

    # Extract machine per op
    by_id = {o["operation_id"]: o for o in result["operations"]}
    assert by_id["O1"]["machine_id"] == "M_ALT"
    assert by_id["O2"]["machine_id"] == "M_PRIMARY"
    assert by_id["O3"]["machine_id"] == "M_ALT"
    assert result["routing_variants_applied"] == 2


# ---------------------------------------------------------------------------
# Tie-break — when both machines have the same free_at, variant B must
# steer the decoder to the alt side (baseline keeps primary).
# ---------------------------------------------------------------------------


def test_tie_break_baseline_chooses_primary_variant_b_chooses_alt():
    """Single op, two idle machines with identical earliest availability.
    The decoder's tie-break follows `candidate_machines.index(m)` — which
    with variant A puts primary first, with variant B puts alt first.
    This is the crisp proof that routing_choices changes the output.
    """
    ops = [_op("O1", machine_id="M_PRIMARY", alternative_machines=["M_ALT"])]
    machines = [_machine("M_PRIMARY"), _machine("M_ALT")]

    baseline = _run(ops, machines, routing_choices={})
    with_variant = _run(ops, machines, routing_choices={"O1": "B"})

    assert baseline["operations"][0]["machine_id"] == "M_PRIMARY"
    assert with_variant["operations"][0]["machine_id"] == "M_ALT"
    assert baseline["routing_variants_applied"] == 0
    assert with_variant["routing_variants_applied"] == 1
