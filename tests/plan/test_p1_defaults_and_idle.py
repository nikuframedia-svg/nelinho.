"""Sprint A P1 — F4 default weight, E1 default generations, F2 idle stats.

Quick tests for three independent fixes:
* F4 — FitnessConfig.w_quality_risk now defaults to 0.10 (Blueprint v2.0
  §5.5) instead of 0.0. Without a predictor the quality_risk_score stays
  at 0, so this is a forward-compatible bump — it starts contributing
  as soon as a Sprint H QualityRiskModel gets wired.
* E1 — CPOConfig.generations defaults to 200 (was 50). Required for the
  FRRMAB window=200 to see a stable reward signal.
* F2 — decoder output carries `total_idle_hours` + `idle_ratio`. A
  half-utilised worker on a 2-day horizon produces ~24h idle.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from src.plan.cpo.chromosome import Chromosome
from src.plan.cpo.decoder import decode
from src.plan.cpo.engine import CPOConfig
from src.plan.cpo.fitness import FitnessConfig
from src.plan.cpo.state import FactoryState
from src.plan.engines.scheduling_adapter import SchedulingMachine, SchedulingOperation


# ---------------------------------------------------------------------------
# F4 — default w_quality_risk raised to 0.10
# ---------------------------------------------------------------------------


def test_f4_default_w_quality_risk_is_010():
    cfg = FitnessConfig()
    assert cfg.w_quality_risk == 0.10, (
        f"expected F4 default 0.10, got {cfg.w_quality_risk}"
    )


def test_f4_backwards_compat_explicit_zero_still_works():
    """Existing callers can pin w_quality_risk=0.0 and the fitness ignores
    the quality term — the raised default should never break those tests.
    """
    cfg = FitnessConfig(w_quality_risk=0.0)
    assert cfg.w_quality_risk == 0.0


# ---------------------------------------------------------------------------
# E1 — default generations now 200
# ---------------------------------------------------------------------------


def test_e1_default_generations_is_200():
    cfg = CPOConfig()
    assert cfg.generations == 200, (
        f"expected E1 default 200, got {cfg.generations}"
    )


def test_e1_callers_can_still_pin_fifty():
    """Legacy Sprint E/F tests pass generations=50 explicitly — still honoured."""
    cfg = CPOConfig(generations=50)
    assert cfg.generations == 50


# ---------------------------------------------------------------------------
# F2 — idle operators on the schedule output
# ---------------------------------------------------------------------------


def _machine(mid: str) -> SchedulingMachine:
    return SchedulingMachine(machine_id=mid, name=mid)


def _op(
    op_id: str,
    duration_min: float,
    *,
    phase_id: str = "PHASE_A",
) -> SchedulingOperation:
    return SchedulingOperation(
        operation_id=op_id,
        order_id="OF1",
        product_id="P1",
        sequence=int(op_id.replace("O", "")),
        operation_code=op_id,
        duration_minutes=duration_min,
        machine_id="M1",
        phase_id=phase_id,
    )


def _run(ops, horizon_days: int = 2, *, skill_matrix=None):
    state = FactoryState(tenant_id=uuid4())
    if skill_matrix:
        state.skill_matrix = skill_matrix
    horizon_start = datetime(2026, 4, 22, 8, 0)
    horizon_end = horizon_start + timedelta(days=horizon_days)
    chrom = Chromosome(permutation=list(range(len(ops))))
    return decode(chrom, ops, [_machine("M1")], state, horizon_start, horizon_end)


def test_f2_empty_schedule_has_zero_idle():
    result = _run([])
    assert result["total_idle_hours"] == 0.0
    assert result["idle_ratio"] == 0.0


def test_f2_single_worker_half_utilised_reports_idle_ratio():
    """One worker busy for 24h on a 48h horizon → idle_ratio ≈ 0.5."""
    # Phase PHASE_A has one capable worker. Op consumes 24h (= 1440 min).
    ops = [_op("O1", duration_min=1440)]
    result = _run(
        ops, horizon_days=2,
        skill_matrix={"PHASE_A": {"w1"}},
    )
    # Horizon = 48h, busy = 24h → idle = 24h; single active worker → ratio = 0.5
    assert result["operations"], "op must be scheduled"
    assert abs(result["idle_ratio"] - 0.5) < 0.02, result["idle_ratio"]
    assert abs(result["total_idle_hours"] - 24.0) < 0.5, result["total_idle_hours"]


def test_f2_idle_aggregates_across_multiple_workers():
    """Two independent workers each busy for 12h on a 24h horizon.
    Total capacity = 48 worker-hours, total busy = 24, idle = 24.
    """
    # Two ops on same phase; skill matrix has 2 workers so each op can go
    # to its own worker in parallel.
    ops = [_op("O1", duration_min=720), _op("O2", duration_min=720)]
    ops[1].order_id = "OF2"
    ops[1].sequence = 1  # remove precedence link
    result = _run(
        ops, horizon_days=1,
        skill_matrix={"PHASE_A": {"w1", "w2"}},
    )
    assert len(result["operations"]) == 2
    # 24h horizon × 2 workers = 48h capacity; busy = 12 + 12 = 24 → idle=24
    assert abs(result["total_idle_hours"] - 24.0) < 0.5, result["total_idle_hours"]
    assert abs(result["idle_ratio"] - 0.5) < 0.05, result["idle_ratio"]


def test_f2_idle_ratio_clamped_to_unit_interval():
    """Even under weird inputs the ratio must stay in [0, 1] — fitness
    uses it normalised against `_NORM_IDLE_H` and negatives would flip
    the sign of the contribution (NEW-3 class bug).
    """
    ops = [_op("O1", duration_min=1)]
    result = _run(ops, horizon_days=1, skill_matrix={"PHASE_A": {"w1"}})
    assert 0.0 <= result["idle_ratio"] <= 1.0
    assert result["total_idle_hours"] >= 0.0
