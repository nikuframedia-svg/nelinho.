"""
Tests for Sprint I.4 — mould multi-pocket batching in the decoder.

`compute_mold_batches` computes the grouping pre-pass; `decode` uses it
so ops of the same model sharing a multi-pocket mould run in parallel.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List
from uuid import UUID

import pytest

from src.plan.cpo.chromosome import Chromosome
from src.plan.cpo.decoder import compute_mold_batches, decode
from src.plan.cpo.state import FactoryState, MoldInfo
from src.plan.engines.scheduling_adapter import SchedulingMachine, SchedulingOperation


HORIZON_START = datetime(2026, 4, 20, 8, 0, 0)
HORIZON_END = HORIZON_START + timedelta(days=7)


def _state_with_mold(pocket_count: int, modelo_id: str = "K1") -> FactoryState:
    state = FactoryState(tenant_id=UUID("11111111-1111-1111-1111-111111111111"))
    mold = MoldInfo(
        molde_id="MLD-K1-6POCKET",
        modelo_id=modelo_id,
        pocket_count=pocket_count,
    )
    state.molds = {mold.molde_id: mold}
    state.molds_by_model = {modelo_id: [mold]}
    return state


def _op(op_id: str, order_id: str, *, mold_id: str = None, model_id: str = "K1",
        sequence: int = 1, duration: float = 60) -> SchedulingOperation:
    return SchedulingOperation(
        operation_id=op_id,
        order_id=order_id,
        product_id="P",
        sequence=sequence,
        operation_code="LAM",
        duration_minutes=duration,
        machine_id="M1",
        mold_required=True,
        mold_id=mold_id,
        model_id=model_id,
    )


class TestComputeMoldBatches:
    def test_no_candidates_returns_empty(self):
        state = _state_with_mold(pocket_count=6)
        ops = [_op("o1", "O1")]
        ops[0] = SchedulingOperation(
            operation_id="o1", order_id="O1", product_id="P", sequence=1,
            operation_code="OP", duration_minutes=30, machine_id="M1",
            mold_required=False,
        )
        assert compute_mold_batches(ops, state) == {}

    def test_single_op_not_batched(self):
        state = _state_with_mold(pocket_count=6)
        assert compute_mold_batches([_op("o1", "O1")], state) == {}

    def test_two_ops_same_model_share_batch(self):
        state = _state_with_mold(pocket_count=6)
        ops = [_op("o1", "O1"), _op("o2", "O2")]
        batches = compute_mold_batches(ops, state)
        assert len(batches) == 2
        # Same batch_id for both
        batch_ids = set(batches.values())
        assert len(batch_ids) == 1

    def test_ops_different_models_not_batched(self):
        state = _state_with_mold(pocket_count=6, modelo_id="K1")
        # Second mold for a different model
        mold_k2 = MoldInfo(molde_id="MLD-K2", modelo_id="K2", pocket_count=6)
        state.molds["MLD-K2"] = mold_k2
        state.molds_by_model["K2"] = [mold_k2]

        ops = [
            _op("o1", "O1", model_id="K1"),
            _op("o2", "O2", model_id="K2"),
        ]
        batches = compute_mold_batches(ops, state)
        # Each is alone in its (model, mold) group → no batching
        assert batches == {}

    def test_pocket_count_1_does_not_batch(self):
        state = _state_with_mold(pocket_count=1)
        ops = [_op("o1", "O1"), _op("o2", "O2")]
        assert compute_mold_batches(ops, state) == {}

    def test_batch_capped_at_pocket_count(self):
        state = _state_with_mold(pocket_count=2)
        ops = [_op(f"o{i}", f"O{i}") for i in range(5)]
        batches = compute_mold_batches(ops, state)
        # 5 ops, pocket_count=2 → 2 full batches of 2, 1 singleton (ignored)
        unique_batches = set(batches.values())
        assert len(unique_batches) == 2
        counts = {b: sum(1 for v in batches.values() if v == b) for b in unique_batches}
        assert sorted(counts.values()) == [2, 2]

    def test_ops_with_precedence_conflict_not_batched(self):
        state = _state_with_mold(pocket_count=6)
        # o2 depends on o1 — can't run in parallel
        o1 = _op("o1", "O1")
        o2 = SchedulingOperation(
            operation_id="o2", order_id="O2", product_id="P", sequence=1,
            operation_code="LAM", duration_minutes=60, machine_id="M1",
            mold_required=True, model_id="K1",
            predecessor_ops=["o1"],
        )
        batches = compute_mold_batches([o1, o2], state)
        # o2 is dropped from candidates; o1 alone → no batching
        assert batches == {}


class TestDecodeWithMoldBatching:
    def test_batched_ops_start_together(self):
        state = _state_with_mold(pocket_count=6)
        ops = [_op("a", "A", duration=60), _op("b", "B", duration=60)]
        machines = [SchedulingMachine(machine_id="M1", name="M1")]
        chromo = Chromosome(permutation=[0, 1])

        result = decode(chromo, ops, machines, state, HORIZON_START, HORIZON_END)

        scheduled = {o["operation_id"]: o for o in result["operations"]}
        # Both ops run in parallel on the same mould
        assert scheduled["a"]["start_time"] == scheduled["b"]["start_time"]
        assert scheduled["a"]["mold_id"] == scheduled["b"]["mold_id"]
        # Each op carries the same batch id
        assert scheduled["a"]["mold_batch_id"] is not None
        assert scheduled["a"]["mold_batch_id"] == scheduled["b"]["mold_batch_id"]

    def test_heterogeneous_durations_mould_busy_until_max(self):
        state = _state_with_mold(pocket_count=6)
        # o_fast finishes earlier, o_slow finishes later; the mould stays
        # occupied until max → o_next_batch can only start after o_slow.
        ops = [
            _op("a", "A", duration=30),
            _op("b", "B", duration=120),
        ]
        machines = [SchedulingMachine(machine_id="M1", name="M1")]
        chromo = Chromosome(permutation=[0, 1])

        result = decode(chromo, ops, machines, state, HORIZON_START, HORIZON_END)
        scheduled = {o["operation_id"]: o for o in result["operations"]}

        start_a = datetime.fromisoformat(scheduled["a"]["start_time"])
        end_a = datetime.fromisoformat(scheduled["a"]["end_time"])
        end_b = datetime.fromisoformat(scheduled["b"]["end_time"])
        assert (end_a - start_a).total_seconds() / 60 == 30  # own duration respected
        assert end_b > end_a  # slower op finishes later
