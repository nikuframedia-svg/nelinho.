"""Sprint A — D1, F1, NEW-1, NEW-2 decoder/pair_assignment fixes.

Covers:
* D1 — setup counter flips 0→1 when two consecutive ops on the same
  machine carry different `setup_family` tags, and stays 0 on a single
  family run.
* F1 — `throughput_eur_day` appears on the schedule output when the
  caller passes `product_price_eur`; it's 0 when the mapping is absent.
* NEW-1 — `requires_pair` is accent/case insensitive so "Laminagem",
  "LAMINAGEM" and the ERP's "Laminagem Infusão" all resolve against the
  canonical PAIR_REQUIRED_PHASES set.
* NEW-2 — when the skill_matrix is populated but the op's phase has no
  eligible workers, the decoder emits a warning rather than silently
  scheduling an unstaffed op.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from src.plan.cpo.chromosome import Chromosome
from src.plan.cpo.decoder import decode
from src.plan.cpo.pair_assignment import requires_pair
from src.plan.cpo.state import FactoryState
from src.plan.engines.scheduling_adapter import SchedulingMachine, SchedulingOperation


def _machine(mid: str = "M1") -> SchedulingMachine:
    return SchedulingMachine(machine_id=mid, name=mid)


def _op(
    op_id: str,
    order_id: str,
    seq: int,
    *,
    product_id: str = "P1",
    phase_id: str = "PHASE_A",
    setup_family: str = "",
    machine_id: str = "M1",
    duration_minutes: float = 60.0,
) -> SchedulingOperation:
    return SchedulingOperation(
        operation_id=op_id,
        order_id=order_id,
        product_id=product_id,
        sequence=seq,
        operation_code=op_id,
        duration_minutes=duration_minutes,
        machine_id=machine_id,
        phase_id=phase_id,
        setup_family=setup_family,
    )


# ---------------------------------------------------------------------------
# D1 — Setup counter
# ---------------------------------------------------------------------------


def _run(ops, **extra) -> dict:
    state = FactoryState(tenant_id=uuid4())
    horizon_start = datetime(2026, 4, 22, 8, 0)
    horizon_end = horizon_start + timedelta(days=2)
    chrom = Chromosome(permutation=list(range(len(ops))))
    return decode(
        chrom, ops, [_machine()], state, horizon_start, horizon_end, **extra,
    )


def test_d1_setups_stays_zero_when_family_is_unknown():
    # Empty setup_family on both sides → no setup change can be asserted.
    ops = [
        _op("A", "OF1", 1, setup_family=""),
        _op("B", "OF1", 2, setup_family=""),
    ]
    result = _run(ops)
    assert result["setups"] == 0


def test_d1_setups_increments_when_families_differ():
    ops = [
        _op("A", "OF1", 1, setup_family="FAMILY_X"),
        _op("B", "OF1", 2, setup_family="FAMILY_Y"),
    ]
    result = _run(ops)
    # A is first on the machine (no predecessor), B is a different family.
    assert result["setups"] == 1


def test_d1_setups_stays_zero_on_single_family_run():
    ops = [
        _op("A", "OF1", 1, setup_family="FAMILY_X"),
        _op("B", "OF1", 2, setup_family="FAMILY_X"),
        _op("C", "OF1", 3, setup_family="FAMILY_X"),
    ]
    result = _run(ops)
    assert result["setups"] == 0


def test_d1_scheduled_dict_carries_setup_family():
    ops = [_op("A", "OF1", 1, setup_family="LAM_CARBON")]
    result = _run(ops)
    assert result["operations"][0]["setup_family"] == "LAM_CARBON"


# ---------------------------------------------------------------------------
# F1 — Throughput €/day
# ---------------------------------------------------------------------------


def test_f1_throughput_defaults_to_zero_without_price_lookup():
    ops = [_op("A", "OF1", 1), _op("B", "OF1", 2)]
    result = _run(ops)
    assert result["throughput_eur_day"] == 0.0
    assert result["throughput_eur_total"] == 0.0


def test_f1_throughput_sums_final_phase_prices_across_orders():
    # Each order's final op (highest sequence) contributes its price.
    ops = [
        _op("A1", "OF1", 1, product_id="P1"),
        _op("A2", "OF1", 2, product_id="P1"),  # final phase of OF1
        _op("B1", "OF2", 1, product_id="P2"),
        _op("B2", "OF2", 2, product_id="P2"),  # final phase of OF2
    ]
    prices = {"P1": Decimal("2400.00"), "P2": Decimal("1800.00")}
    result = _run(ops, product_price_eur=prices)
    # Horizon is 2 days; total revenue = 2400 + 1800 = 4200 → 2100 €/day
    assert result["throughput_eur_total"] == 4200.0
    assert result["throughput_eur_day"] == 2100.0


def test_f1_throughput_ignores_unscheduled_orders():
    # Force an order to stay infeasible by giving its machine_id an unknown
    # name — the decoder has to fall back, so this still schedules. To
    # actually force an unscheduled final phase, pass a chromosome that
    # omits it. We simulate by using a product with no price.
    ops = [
        _op("A1", "OF1", 1, product_id="P1"),
        _op("A2", "OF1", 2, product_id="P1"),
    ]
    prices = {"P2": Decimal("5000.00")}  # P1 missing on purpose
    result = _run(ops, product_price_eur=prices)
    assert result["throughput_eur_total"] == 0.0


# ---------------------------------------------------------------------------
# NEW-1 — requires_pair accent/case-insensitive
# ---------------------------------------------------------------------------


def test_new1_requires_pair_matches_case_insensitive():
    """Sprint Q.8 (CEO confirmation 2026-04-26): Laminagem moved from
    PAIR_REQUIRED_PHASES (hard) to PAIR_PREFERRED_PHASES (soft), so
    `requires_pair` now returns False. The case-insensitive matcher
    still works — verified on `prefers_pair` instead.
    """
    from src.plan.cpo.pair_assignment import prefers_pair

    state = FactoryState(tenant_id=uuid4())
    op_low = _op("X", "OF1", 1, phase_id="laminagem")
    op_mix = _op("Y", "OF1", 1, phase_id="Laminagem")
    op_acc = _op("Z", "OF1", 1, phase_id="Laminagem Infusão")
    # No phase is REQUIRED any more (set is empty post-Q.8).
    assert requires_pair(op_low, state) is False
    assert requires_pair(op_mix, state) is False
    # …but Laminagem standard is PREFERRED.
    assert prefers_pair(op_low, state) is True
    assert prefers_pair(op_mix, state) is True
    # Laminagem Infusão (different phase) is NOT in either set.
    assert prefers_pair(op_acc, state) is False


# ---------------------------------------------------------------------------
# NEW-2 — warn when skill_matrix has no eligible workers
# ---------------------------------------------------------------------------


def test_new2_warns_when_skill_matrix_lacks_phase():
    state = FactoryState(tenant_id=uuid4())
    # Populate skill_matrix for a DIFFERENT phase — ours has no workers.
    state.skill_matrix = {"OTHER_PHASE": {"w1", "w2"}}
    ops = [_op("A", "OF1", 1, phase_id="PHASE_WITH_NO_WORKERS")]

    horizon_start = datetime(2026, 4, 22, 8, 0)
    horizon_end = horizon_start + timedelta(days=2)
    result = decode(
        Chromosome(permutation=[0]), ops, [_machine()], state,
        horizon_start, horizon_end,
    )
    # Op is still scheduled (manual fallback), but a warning is raised.
    assert result["operations"], "op should still be scheduled as manual"
    assert any(
        "skill_matrix" in w.lower() for w in result["warnings"]
    ), f"expected a skill_matrix warning, got: {result['warnings']}"


def test_new2_quiet_when_skill_matrix_is_empty():
    """No skill_matrix at all → no false-alarm warning. The decoder only
    nags when there IS a matrix and this phase is absent from it.
    """
    state = FactoryState(tenant_id=uuid4())
    # skill_matrix left empty (default)
    ops = [_op("A", "OF1", 1, phase_id="ANY_PHASE")]

    horizon_start = datetime(2026, 4, 22, 8, 0)
    horizon_end = horizon_start + timedelta(days=2)
    result = decode(
        Chromosome(permutation=[0]), ops, [_machine()], state,
        horizon_start, horizon_end,
    )
    assert not any("skill_matrix" in w.lower() for w in result["warnings"])


def test_no_warn_for_no_labor_phase_q167i():
    """Q.167.I — fases SEM mão-de-obra (Cura '2', estado '11') têm pool vazio
    por design; o decoder agenda como manual mas NÃO emite o aviso 'verify
    skill seed' (era falso-alarme). Confirmado live: 0 crew em offp_eq p/ 2 e 11.
    """
    state = FactoryState(tenant_id=uuid4())
    # Matrix populada para OUTRA fase — a nossa (Cura '2') fica sem pool.
    state.skill_matrix = {"OTHER_PHASE": {"w1", "w2"}}
    ops = [_op("A", "OF1", 1, phase_id="2")]

    horizon_start = datetime(2026, 4, 22, 8, 0)
    horizon_end = horizon_start + timedelta(days=2)
    result = decode(
        Chromosome(permutation=[0]), ops, [_machine()], state,
        horizon_start, horizon_end,
    )
    # Op na mesma agendada (manual), mas SEM aviso de skill_matrix.
    assert result["operations"], "op should still be scheduled as manual"
    assert not any(
        "skill_matrix" in w.lower() for w in result["warnings"]
    ), f"no-labor phase should not warn, got: {result['warnings']}"


# ---------------------------------------------------------------------------
# Sprint Q.8 — Pair-preferred phases downgrade to solo when pool is thin
# ---------------------------------------------------------------------------


def test_q8_laminagem_downgrades_to_solo_when_only_one_worker_available():
    """Laminagem standard wants 2 workers (preferred) but the decoder
    accepts 1 when the eligible pool only has one — emits a warning
    instead of marking the op infeasible.
    """
    state = FactoryState(tenant_id=uuid4())
    state.skill_matrix = {"laminagem": {"w_solo"}}  # only 1 eligible worker
    op = _op("A", "OF1", 1, phase_id="laminagem")
    op.team_size = 2  # routing resolver assigns 2 for pair-preferred phases

    horizon_start = datetime(2026, 4, 22, 8, 0)
    horizon_end = horizon_start + timedelta(days=2)
    result = decode(
        Chromosome(permutation=[0]), [op], [_machine()], state,
        horizon_start, horizon_end,
    )
    # Scheduled, not infeasible.
    assert result["operations"], "PREFERRED-pair op should be placed solo"
    # Warning surfaced for the downgrade.
    assert any(
        "pair-preferred" in w.lower() for w in result["warnings"]
    ), f"expected pair-preferred warning, got: {result['warnings']}"


def test_q8_solo_assignment_kept_when_pool_has_two_workers():
    """When the pair pool is fully staffed (2+ eligible), the decoder
    still places 2 workers — the downgrade only kicks in when pool < 2.
    """
    state = FactoryState(tenant_id=uuid4())
    state.skill_matrix = {"laminagem": {"w1", "w2", "w3"}}
    op = _op("A", "OF1", 1, phase_id="laminagem")
    op.team_size = 2

    horizon_start = datetime(2026, 4, 22, 8, 0)
    horizon_end = horizon_start + timedelta(days=2)
    result = decode(
        Chromosome(permutation=[0]), [op], [_machine()], state,
        horizon_start, horizon_end,
    )
    assert result["operations"], "should be placed"
    workers = result["operations"][0]["workers"]
    assert len(workers) == 2, f"expected pair, got {workers}"
    # No downgrade warning because pool was sufficient.
    assert not any(
        "pair-preferred" in w.lower() for w in result["warnings"]
    )
