"""Q.169.B — validador estrutural universal de schedules.

A matriz de paridade (Q.169.A) mostrou que os axiomas 1-6 são garantidos
"by construction" no decoder mas NADA os verifica no schedule final que
vai para o ScheduleCommit. Estes testes travam o contrato do
`validate_schedule` dimensão a dimensão + a recusa no caminho de escrita
(`create_from_schedule` levanta ScheduleValidationError) + a property
hypothesis de que schedules válidos-por-construção passam SEMPRE.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.plan.cpo.schedule_validator import (
    ScheduleValidationError,
    validate_schedule,
)
from src.plan.cpo.state import FactoryState

_T0 = datetime(2026, 6, 15, 8, 0, 0)


def _op(oid, order, phase, start_h, end_h, workers=(), mold=None,
        batch=None, machine=None):
    return {
        "operation_id": oid,
        "order_id": order,
        "phase_id": phase,
        "machine_id": machine,
        "workers": list(workers),
        "mold_id": mold,
        "mold_batch_id": batch,
        "start_time": (_T0 + timedelta(hours=start_h)).isoformat(),
        "end_time": (_T0 + timedelta(hours=end_h)).isoformat(),
        "duration_minutes": (end_h - start_h) * 60.0,
        "setup_family": phase,
    }


def _state_with_curing_and_skills() -> FactoryState:
    state = FactoryState(tenant_id=uuid4())
    state.phase_transition_gaps = {("LAMINAGEM", "CURA"): 15.0}
    state.phase_catalog = [
        {"fase_id": "1", "fase_nome": "Laminagem", "sequence": 1},
        {"fase_id": "2", "fase_nome": "Cura", "sequence": 2},
        {"fase_id": "3", "fase_nome": "Acabamento", "sequence": 3},
    ]
    state.skill_matrix = {"1": {"W1", "W2"}, "3": {"W3"}}
    return state


# ───────────────────────── casos dirigidos por dimensão ─────────────────────


class TestOrderSequence:
    def test_boat_in_two_phases_at_once_is_error(self):
        rep = validate_schedule({"operations": [
            _op("a", "OF-1", "1", 0, 4),
            _op("b", "OF-1", "2", 2, 6),  # sobrepõe a fase anterior
        ]})
        assert not rep.ok
        assert any("sobrepostas" in e for e in rep.errors)

    def test_sequential_phases_pass(self):
        rep = validate_schedule({"operations": [
            _op("a", "OF-1", "1", 0, 4),
            _op("b", "OF-1", "2", 4, 8),  # toca, não sobrepõe
        ]})
        assert rep.ok

    def test_different_orders_may_overlap(self):
        rep = validate_schedule({"operations": [
            _op("a", "OF-1", "1", 0, 4, workers=("W1",)),
            _op("b", "OF-2", "1", 0, 4, workers=("W2",)),
        ]})
        assert rep.ok


class TestCuringChemistry:
    def test_curing_gap_violation_is_error(self):
        state = _state_with_curing_and_skills()
        rep = validate_schedule({"operations": [
            _op("a", "OF-1", "1", 0, 4, workers=("W1",)),   # Laminagem
            _op("b", "OF-1", "2", 5, 10),                   # Cura 1h depois — mín 15h
        ]}, state=state)
        assert not rep.ok
        assert any("cura química" in e for e in rep.errors)

    def test_curing_gap_respected_passes(self):
        state = _state_with_curing_and_skills()
        rep = validate_schedule({"operations": [
            _op("a", "OF-1", "1", 0, 4, workers=("W1",)),
            _op("b", "OF-1", "2", 4 + 15.5, 4 + 20),  # 15.5h de gap ≥ 15h
        ]}, state=state)
        assert rep.ok, rep.errors

    def test_stateless_skips_curing_check(self):
        """Sem state não há gaps — o check fica fora de checks_run (nunca
        finge que validou o que não pode validar)."""
        rep = validate_schedule({"operations": [
            _op("a", "OF-1", "1", 0, 4),
            _op("b", "OF-1", "2", 5, 10),
        ]})
        assert rep.ok
        assert "cura_quimica" not in rep.checks_run


class TestMoldExclusive:
    def test_same_mold_overlap_is_error(self):
        rep = validate_schedule({"operations": [
            _op("a", "OF-1", "1", 0, 4, mold="M9"),
            _op("b", "OF-2", "1", 2, 6, mold="M9"),
        ]})
        assert not rep.ok
        assert any("molde M9" in e for e in rep.errors)

    def test_same_batch_may_share_mold(self):
        """Ops do MESMO mold_batch_id são um batch — coexistem no molde."""
        rep = validate_schedule({"operations": [
            _op("a", "OF-1", "1", 0, 4, mold="M9", batch="B1"),
            _op("b", "OF-2", "1", 0, 4, mold="M9", batch="B1"),
        ]})
        assert rep.ok, rep.errors

    def test_distinct_batches_must_serialize(self):
        rep = validate_schedule({"operations": [
            _op("a", "OF-1", "1", 0, 4, mold="M9", batch="B1"),
            _op("b", "OF-2", "1", 3, 7, mold="M9", batch="B2"),
        ]})
        assert not rep.ok


class TestWorkerDoubleBooking:
    def test_worker_in_two_overlapping_ops_is_error(self):
        rep = validate_schedule({"operations": [
            _op("a", "OF-1", "1", 0, 4, workers=("W1",)),
            _op("b", "OF-2", "1", 2, 6, workers=("W1",)),
        ]})
        assert not rep.ok
        assert any("double-booking" in e for e in rep.errors)

    def test_back_to_back_is_fine(self):
        rep = validate_schedule({"operations": [
            _op("a", "OF-1", "1", 0, 4, workers=("W1",)),
            _op("b", "OF-2", "1", 4, 8, workers=("W1",)),
        ]})
        assert rep.ok


class TestSkillMatch:
    def test_foreign_worker_is_error(self):
        state = _state_with_curing_and_skills()
        rep = validate_schedule({"operations": [
            _op("a", "OF-1", "1", 0, 4, workers=("INTRUSO",)),
        ]}, state=state)
        assert not rep.ok
        assert any("axioma 5" in e for e in rep.errors)

    def test_pool_worker_passes(self):
        state = _state_with_curing_and_skills()
        rep = validate_schedule({"operations": [
            _op("a", "OF-1", "1", 0, 4, workers=("W1",)),
        ]}, state=state)
        assert rep.ok

    def test_phase_without_pool_is_not_checked(self):
        """Pool vazio = fase manual — qualquer operador é aceitável."""
        state = _state_with_curing_and_skills()
        rep = validate_schedule({"operations": [
            _op("a", "OF-1", "99", 0, 4, workers=("QUALQUER",)),
        ]}, state=state)
        assert rep.ok


class TestPairsAndMachines:
    def test_laminagem_solo_is_warning_not_error(self):
        """Downgrade soft (Sprint Q.8) é política aceite — visível, não bloqueante."""
        state = _state_with_curing_and_skills()
        rep = validate_schedule({"operations": [
            _op("a", "OF-1", "1", 0, 4, workers=("W1",)),  # fase 1 = Laminagem
        ]}, state=state)
        assert rep.ok
        assert any("par-preferida" in w for w in rep.warnings)

    def test_machine_overlap_is_warning_only(self):
        rep = validate_schedule({"operations": [
            _op("a", "OF-1", "1", 0, 4, machine="40::st1"),
            _op("b", "OF-2", "1", 2, 6, machine="40::st1"),
        ]})
        assert rep.ok
        assert any("estação" in w for w in rep.warnings)

    def test_manual_pool_never_flagged(self):
        rep = validate_schedule({"operations": [
            _op("a", "OF-1", "1", 0, 4, machine="MANUAL"),
            _op("b", "OF-2", "1", 0, 4, machine="MANUAL"),
        ]})
        assert rep.ok and not rep.warnings


# ───────────────────────── caminho de escrita recusa ────────────────────────


class TestCommitRefusesInvalid:
    async def test_create_from_schedule_raises_on_structural_violation(
        self, fake_session, tenant_id,
    ):
        from src.plan.cpo.commits import CommitsService

        fake_session.queue_scalar(None)
        service = CommitsService(fake_session, tenant_id)
        with pytest.raises(ScheduleValidationError):
            await service.create_from_schedule(schedule_result={
                "makespan_hours": 4.0,
                "operations": [
                    _op("a", "OF-1", "1", 0, 4, mold="M9"),
                    _op("b", "OF-2", "1", 2, 6, mold="M9"),
                ],
            })
        assert not fake_session.added, "schedule inválido NUNCA é persistido"

    async def test_valid_schedule_persists_with_validation_meta(
        self, fake_session, tenant_id,
    ):
        from src.plan.cpo.commits import CommitsService

        fake_session.queue_scalar(None)
        service = CommitsService(fake_session, tenant_id)
        commit = await service.create_from_schedule(schedule_result={
            "makespan_hours": 4.0,
            "operations": [_op("a", "OF-1", "1", 0, 4, workers=("W1",))],
        })
        meta = commit.cpo_meta["validation"]
        assert meta["ok"] is True
        assert "molde_exclusivo" in meta["checks_run"]
        assert "operador_sem_double_booking" in meta["checks_run"]


# ───────────────────────── property: válido-por-construção passa ────────────


@settings(max_examples=60, deadline=None)
@given(
    n_orders=st.integers(min_value=1, max_value=5),
    n_phases=st.integers(min_value=1, max_value=4),
    dur_h=st.floats(min_value=0.5, max_value=8.0),
    gap_h=st.floats(min_value=0.0, max_value=4.0),
)
def test_property_sequential_schedules_always_pass(n_orders, n_phases, dur_h, gap_h):
    """INVARIANTE: um schedule construído sequencialmente (fases encadeadas
    por ordem, molde e operador próprios por ordem) passa SEMPRE — o
    validador não tem falsos positivos sobre planos bem-formados."""
    ops = []
    for o in range(n_orders):
        for p in range(n_phases):
            start = p * (dur_h + gap_h)
            ops.append(_op(
                f"OF-{o}::{p}", f"OF-{o}", str(p),
                start, start + dur_h,
                workers=(f"W{o}",), mold=f"M{o}",
                batch=f"B{o}",  # fases da mesma ordem partilham o molde dela
            ))
    rep = validate_schedule({"operations": ops})
    assert rep.ok, rep.errors


@settings(max_examples=40, deadline=None)
@given(
    overlap_h=st.floats(min_value=0.25, max_value=3.0),
)
def test_property_injected_double_booking_always_caught(overlap_h):
    """INVARIANTE: qualquer sobreposição real (> tolerância de 60s) do mesmo
    operador é SEMPRE apanhada."""
    ops = [
        _op("a", "OF-1", "1", 0, 4, workers=("W1",)),
        _op("b", "OF-2", "1", 4 - overlap_h, 8, workers=("W1",)),
    ]
    rep = validate_schedule({"operations": ops})
    assert not rep.ok
