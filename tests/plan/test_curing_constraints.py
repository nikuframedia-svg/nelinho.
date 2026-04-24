"""Sprint A D2+ST1 — curing/drying gap constraints.

Covers:
* `normalize_phase_code` strips accents and folds case
* `FactoryState.min_gap_hours` reads seeded + loaded gaps
* `_load_phase_transition_gaps` falls back to NELO_CURING_GAPS_SEED when
  DB is empty or unavailable
* Decoder honours the curing gap in `_earliest_start`
* CP-SAT `_add_precedence_constraints` applies the same gap
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from uuid import uuid4

from src.plan.cpo.chromosome import Chromosome
from src.plan.cpo.decoder import decode
from src.plan.cpo.state import (
    NELO_CURING_GAPS_SEED,
    FactoryState,
    _load_phase_transition_gaps,
    normalize_phase_code,
)
from src.plan.engines.scheduling_adapter import SchedulingMachine, SchedulingOperation


# ---------------------------------------------------------------------------
# normalize_phase_code
# ---------------------------------------------------------------------------


def test_normalize_strips_accents_and_folds_case():
    assert normalize_phase_code("Laminagem Infusão") == "LAMINAGEM_INFUSAO"
    assert normalize_phase_code("Colagem Peças") == "COLAGEM_PECAS"
    assert normalize_phase_code("pintura acabamento") == "PINTURA_ACABAMENTO"
    assert normalize_phase_code("LAMINAGEM") == "LAMINAGEM"


def test_normalize_handles_empty_and_none():
    assert normalize_phase_code(None) == ""
    assert normalize_phase_code("") == ""
    assert normalize_phase_code("   ") == ""


def test_normalize_collapses_repeated_separators():
    assert normalize_phase_code("Lixagem  Água") == "LIXAGEM_AGUA"
    assert normalize_phase_code("Lixagem-Polimento") == "LIXAGEM_POLIMENTO"


# ---------------------------------------------------------------------------
# FactoryState.min_gap_hours
# ---------------------------------------------------------------------------


def _state_with_seed() -> FactoryState:
    """FactoryState populated by loading with no session (→ seed fallback)."""
    gaps = asyncio.run(_load_phase_transition_gaps(None, uuid4()))
    state = FactoryState(tenant_id=uuid4())
    state.phase_transition_gaps = gaps
    return state


def test_state_min_gap_returns_zero_for_unknown_transition():
    s = _state_with_seed()
    assert s.min_gap_hours("LAMINAGEM", "DESMOLDE") == 0.0


def test_state_min_gap_returns_seeded_value():
    s = _state_with_seed()
    # From NELO_CURING_GAPS_SEED: Laminagem → Cura is 15h.
    assert s.min_gap_hours("Laminagem", "Cura") == 15.0
    # Accent variants hit the same key.
    assert s.min_gap_hours("Laminagem Infusão", "Cura") == 24.0
    # Colagem Peças → Pintura Acabamento is 19.5h
    assert s.min_gap_hours("Colagem Peças", "Pintura Acabamento") == 19.5


def test_state_min_gap_zero_when_either_input_empty():
    s = _state_with_seed()
    assert s.min_gap_hours(None, "Cura") == 0.0
    assert s.min_gap_hours("Laminagem", None) == 0.0


# ---------------------------------------------------------------------------
# _load_phase_transition_gaps fallback
# ---------------------------------------------------------------------------


def test_load_without_session_returns_full_seed():
    gaps = asyncio.run(_load_phase_transition_gaps(None, uuid4()))
    # All 16 rows loaded.
    assert len(gaps) == len(NELO_CURING_GAPS_SEED)
    # A known entry is present.
    assert gaps[("LAMINAGEM", "CURA")] == 15.0


def test_load_with_failing_session_falls_back_to_seed():
    class _BoomSession:
        async def execute(self, *_a, **_kw):  # pragma: no cover — exercised
            raise RuntimeError("table does not exist")

    gaps = asyncio.run(_load_phase_transition_gaps(_BoomSession(), uuid4()))
    # The seed is preserved even when the DB path explodes.
    assert gaps[("LAMINAGEM", "CURA")] == 15.0
    assert len(gaps) == len(NELO_CURING_GAPS_SEED)


# ---------------------------------------------------------------------------
# Decoder — curing gap honoured in earliest_start
# ---------------------------------------------------------------------------


def _make_machine(machine_id: str = "M1") -> SchedulingMachine:
    return SchedulingMachine(
        machine_id=machine_id,
        name=machine_id,
    )


def _make_op(
    op_id: str,
    order_id: str,
    sequence: int,
    phase_code: str,
    *,
    duration_minutes: float = 60.0,
    machine_id: str = "M1",
) -> SchedulingOperation:
    # `phase_id` is the canonical phase code used for curing gap lookups.
    return SchedulingOperation(
        operation_id=op_id,
        order_id=order_id,
        product_id="P1",
        sequence=sequence,
        operation_code=op_id,
        duration_minutes=duration_minutes,
        machine_id=machine_id,
        phase_id=phase_code,
    )


def test_decoder_respects_curing_gap_between_laminagem_and_cura():
    state = _state_with_seed()
    horizon_start = datetime(2026, 4, 22, 8, 0)
    horizon_end = horizon_start + timedelta(days=5)

    lam = _make_op("L1", "OF1", 1, "LAMINAGEM", duration_minutes=60)
    cura = _make_op("C1", "OF1", 2, "CURA", duration_minutes=60)

    chrom = Chromosome(permutation=[0, 1])
    result = decode(
        chrom, [lam, cura], [_make_machine()], state,
        horizon_start, horizon_end,
    )

    by_id = {o["operation_id"]: o for o in result["operations"]}
    lam_end = datetime.fromisoformat(by_id["L1"]["end_time"])
    cura_start = datetime.fromisoformat(by_id["C1"]["start_time"])
    gap = cura_start - lam_end
    # Seed says Laminagem→Cura is 15h, decoder must enforce ≥ that.
    assert gap >= timedelta(hours=15), (
        f"expected gap ≥ 15h, got {gap}"
    )


def test_decoder_no_curing_gap_for_transitions_without_seed():
    """Transitions NOT in the seed must not introduce spurious delays."""
    state = _state_with_seed()
    horizon_start = datetime(2026, 4, 22, 8, 0)
    horizon_end = horizon_start + timedelta(days=2)

    a = _make_op("A", "OF1", 1, "DESMOLDE", duration_minutes=30)
    b = _make_op("B", "OF1", 2, "CORTE", duration_minutes=30)

    chrom = Chromosome(permutation=[0, 1])
    result = decode(
        chrom, [a, b], [_make_machine()], state,
        horizon_start, horizon_end,
    )
    by_id = {o["operation_id"]: o for o in result["operations"]}
    a_end = datetime.fromisoformat(by_id["A"]["end_time"])
    b_start = datetime.fromisoformat(by_id["B"]["start_time"])
    # With no queue_gap passed and no curing gap for this transition,
    # successor may start at predecessor's end.
    assert b_start >= a_end
    assert (b_start - a_end) < timedelta(hours=12)


# ---------------------------------------------------------------------------
# CP-SAT precedence constraints (no ortools required — API smoke only)
# ---------------------------------------------------------------------------


def test_cpsat_lrho_accepts_phase_gaps_kwarg():
    """refine() must accept phase_gaps without requiring ortools."""
    from src.plan.engines.cpsat_lrho import CPSATLRHO, LRHOConfig

    lrho = CPSATLRHO(LRHOConfig())
    seed_gaps = {
        (normalize_phase_code(a), normalize_phase_code(b)): h
        for (a, b, h, _r, _n) in NELO_CURING_GAPS_SEED
    }
    horizon_start = datetime(2026, 4, 22)
    horizon_end = horizon_start + timedelta(days=2)
    result = lrho.refine(
        {"operations": []},
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        phase_gaps=seed_gaps,
    )
    # Either ortools is absent (used=False) or the schedule is unchanged
    # (no ops in baseline). We only assert the call itself doesn't blow up.
    assert result is not None
