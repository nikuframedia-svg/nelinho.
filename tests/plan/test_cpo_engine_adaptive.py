"""
Tests for the CPO v4 engine with the Sprint F adaptive layers turned on.

Focus on behavioural integration, not GA performance — adaptive GA bench
numbers are tracked separately (roadmap item for Sprint I).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List
from uuid import UUID

from src.plan.cpo.engine import CPOConfig, CPOv4Engine
from src.plan.cpo.state import FactoryState
from src.plan.engines.scheduling_adapter import SchedulingMachine, SchedulingOperation


HORIZON_START = datetime(2026, 4, 20, 8, 0, 0)
HORIZON_END = HORIZON_START + timedelta(days=14)


def _state() -> FactoryState:
    return FactoryState(tenant_id=UUID("11111111-1111-1111-1111-111111111111"))


def _ops(n: int = 10) -> List[SchedulingOperation]:
    return [
        SchedulingOperation(
            operation_id=f"o{i}",
            order_id=f"O{i // 2}",
            product_id="P1",
            sequence=1 + (i % 2),
            operation_code="OP",
            duration_minutes=30,
            machine_id="M1",
        )
        for i in range(n)
    ]


def _machines() -> List[SchedulingMachine]:
    return [SchedulingMachine(machine_id="M1", name="Machine 1")]


class TestAdaptiveEngineIntegration:
    def test_default_flags_produce_meta_blocks(self):
        engine = CPOv4Engine(
            state=_state(),
            config=CPOConfig(
                population_size=10,
                generations=4,
                time_limit_sec=5,
                seed=7,
            ),
        )
        result = engine.schedule(_ops(10), _machines(), HORIZON_START, HORIZON_END)
        meta = result["cpo_meta"]
        assert meta["frrmab"] is not None
        assert set(meta["frrmab"].keys()) >= {
            "swap_adjacent", "swap_random", "insert_move",
            "flip_routing", "shift_group", "perturb_params",
        }
        assert meta["mapelites"] is not None
        assert meta["mapelites"]["cells_occupied"] >= 1

    def test_all_flags_off_matches_sprint_e_behaviour(self):
        """When every adaptive flag is off the meta is blank and we get
        the same end-to-end status as Sprint E's smoke test."""
        engine = CPOv4Engine(
            state=_state(),
            config=CPOConfig(
                population_size=5,
                generations=3,
                time_limit_sec=3,
                seed=7,
                use_frrmab=False,
                use_mapelites=False,
                use_surrogate=False,
                use_restart=False,
            ),
        )
        result = engine.schedule(_ops(6), _machines(), HORIZON_START, HORIZON_END)
        meta = result["cpo_meta"]
        assert meta["frrmab"] is None
        assert meta["mapelites"] is None
        assert meta["surrogate"]["enabled"] is False
        assert result["success"] is True

    def test_surrogate_off_by_default(self):
        engine = CPOv4Engine(
            state=_state(),
            config=CPOConfig(
                population_size=5,
                generations=2,
                time_limit_sec=3,
                seed=7,
            ),
        )
        result = engine.schedule(_ops(6), _machines(), HORIZON_START, HORIZON_END)
        assert result["cpo_meta"]["surrogate_skips"] == 0
        assert result["cpo_meta"]["surrogate"]["enabled"] is False

    def test_mapelites_captures_baseline_even_on_short_runs(self):
        """A 1-gen run still results in MAP-Elites containing >= baseline."""
        engine = CPOv4Engine(
            state=_state(),
            config=CPOConfig(
                population_size=4,
                generations=1,
                time_limit_sec=3,
                seed=7,
            ),
        )
        engine.schedule(_ops(6), _machines(), HORIZON_START, HORIZON_END)
        assert engine._mapelites is not None
        assert engine._mapelites.cells_occupied() >= 1

    def test_real_evals_counted(self):
        engine = CPOv4Engine(
            state=_state(),
            config=CPOConfig(
                population_size=6,
                generations=3,
                time_limit_sec=5,
                seed=7,
                use_surrogate=False,  # ensure no skips
            ),
        )
        result = engine.schedule(_ops(6), _machines(), HORIZON_START, HORIZON_END)
        meta = result["cpo_meta"]
        # With surrogate off, every population member is real-evaluated each gen.
        # 6 individuals * 3 gens = 18 (exact because time budget unused).
        assert meta["real_evaluations"] >= 6 * 3
