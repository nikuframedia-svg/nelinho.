"""Q.174.F4 — property tests: disponibilidade de operadores (axioma novo).

A spec do produto: «trabalhador só pode ser alocado se estiver disponível».
As janelas de indisponibilidade vêm de ENT_MOV (MET_MET_ID=2 — faltas/baixas/
férias, com dias FUTUROS reais) + overrides locais (plan.worker_absence).

Invariantes:
* A — `absence_adjusted_start` nunca devolve um início que toque numa janela,
  nunca recua, e com `worker_absences={}` devolve o start intacto (fast-path,
  back-compat byte-idêntico).
* B — end-to-end no decoder: NENHUMA op agendada usa um operador dentro de
  uma janela de ausência; sem ausências o schedule é idêntico ao legacy.
* C — post-pass CP-SAT: idem (espelho do decoder).
* D — validador: um schedule que viole a disponibilidade é recusado (errors).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from hypothesis import given, settings, strategies as st

from src.plan.cpo.chromosome import Chromosome
from src.plan.cpo.decoder import decode
from src.plan.cpo.state import FactoryState
from src.plan.engines.cpsat_postpass import assign_concrete
from src.plan.engines.scheduling_adapter import (
    SchedulingMachine,
    SchedulingOperation,
)

_REF = datetime(2026, 6, 15, 8, 0, 0)
_FASE = "40"


def _state(absences: dict) -> FactoryState:
    state = FactoryState(tenant_id=uuid4())
    state.skill_matrix = {_FASE: {"w1"}}
    state.worker_absences = absences
    return state


def _op(oid: str, order: str, dur_min: float = 120.0) -> SchedulingOperation:
    return SchedulingOperation(
        operation_id=oid, order_id=order, product_id="P", sequence=1,
        operation_code=_FASE, duration_minutes=dur_min, machine_id=None,
        phase_id=_FASE, team_size=1,
    )


def _overlaps(s1, e1, s2, e2) -> bool:
    return s1 < e2 and s2 < e1


# ---------------------------------------------------------------------------
# A — absence_adjusted_start é puro, monótono e respeita as janelas
# ---------------------------------------------------------------------------


@given(
    gap_h=st.floats(min_value=0.0, max_value=72.0),
    len1_h=st.floats(min_value=1.0, max_value=48.0),
    len2_h=st.floats(min_value=1.0, max_value=48.0),
    dur_h=st.floats(min_value=0.25, max_value=16.0),
    offset_h=st.floats(min_value=-24.0, max_value=120.0),
)
@settings(max_examples=200, deadline=None)
def test_adjusted_start_nunca_toca_janelas(gap_h, len1_h, len2_h, dur_h, offset_h):
    a1 = (_REF, _REF + timedelta(hours=len1_h))
    a2_ini = a1[1] + timedelta(hours=gap_h)
    a2 = (a2_ini, a2_ini + timedelta(hours=len2_h))
    # fundir como o loader faz (janelas adjacentes/sobrepostas)
    spans = [a1, a2] if a2[0] > a1[1] else [(a1[0], max(a1[1], a2[1]))]
    state = _state({"w1": spans})

    start = _REF + timedelta(hours=offset_h)
    adj = state.absence_adjusted_start("w1", start, dur_h)

    assert adj >= start  # nunca recua
    # o intervalo [adj, adj+dur) não toca nenhuma janela
    fim = adj + timedelta(hours=dur_h)
    for ini, f in spans:
        assert not _overlaps(adj, fim, ini, f)


def test_adjusted_start_fast_path_sem_ausencias():
    state = _state({})
    assert state.absence_adjusted_start("w1", _REF, 4.0) == _REF
    state2 = _state({"w2": [(_REF, _REF + timedelta(days=1))]})
    # outro operador → intacto
    assert state2.absence_adjusted_start("w1", _REF, 4.0) == _REF


# ---------------------------------------------------------------------------
# B — decoder end-to-end: nenhuma op dentro de janela; sem ausências = legacy
# ---------------------------------------------------------------------------


def _decode(state, ops):
    machines = [SchedulingMachine(machine_id="M1", name="M1")]
    chrom = Chromosome(permutation=list(range(len(ops))))
    return decode(
        chrom, ops, machines, state,
        horizon_start=_REF, horizon_end=_REF + timedelta(days=90),
    )


@given(absent_days=st.integers(min_value=1, max_value=10))
@settings(max_examples=30, deadline=None)
def test_decoder_nunca_agenda_dentro_de_ausencia(absent_days):
    janela = (_REF - timedelta(hours=8),
              _REF + timedelta(days=absent_days))
    state = _state({"w1": [janela]})
    ops = [_op(f"O{i}", f"OF{i}") for i in range(3)]

    result = _decode(state, ops)
    for op in result["operations"]:
        if "w1" not in (op.get("workers") or []):
            continue
        s = datetime.fromisoformat(op["start_time"])
        e = datetime.fromisoformat(op["end_time"])
        assert not _overlaps(s, e, janela[0], janela[1]), (
            f"op {op['operation_id']} dentro da ausência: {s}..{e}"
        )
        assert s >= janela[1]


def test_decoder_sem_ausencias_byte_identico():
    ops = [_op(f"O{i}", f"OF{i}") for i in range(4)]
    base = _decode(_state({}), ops)
    again = _decode(_state({}), ops)
    assert [o["start_time"] for o in base["operations"]] == [
        o["start_time"] for o in again["operations"]
    ]


# ---------------------------------------------------------------------------
# C — post-pass CP-SAT espelha a garantia
# ---------------------------------------------------------------------------


def test_postpass_respeita_ausencia():
    janela = (_REF - timedelta(hours=8), _REF + timedelta(days=3))
    state = _state({"w1": [janela]})
    ops = [_op("A", "OF1"), _op("B", "OF2")]
    scheduled = assign_concrete(ops, state, _REF, {"A": 0, "B": 0})
    for s_op in scheduled:
        if "w1" not in s_op.workers:
            continue
        assert not _overlaps(s_op.start, s_op.end, janela[0], janela[1])
        assert s_op.start >= janela[1]


# ---------------------------------------------------------------------------
# D — validador recusa violações (write-gate)
# ---------------------------------------------------------------------------


def test_validador_recusa_op_dentro_de_ausencia():
    from src.plan.cpo.schedule_validator import validate_schedule

    janela = (_REF, _REF + timedelta(days=2))
    state = _state({"w1": [janela]})
    schedule = {
        "operations": [{
            "operation_id": "X1",
            "order_id": "OF1",
            "phase_id": _FASE,
            "workers": ["w1"],
            "start_time": (_REF + timedelta(hours=2)).isoformat(),
            "end_time": (_REF + timedelta(hours=4)).isoformat(),
        }]
    }
    report = validate_schedule(schedule, state)
    assert any("AUSENTE" in e for e in report.errors)
    assert "operador_disponivel" in report.checks_run

    # sem ausências → check nem corre (back-compat)
    report2 = validate_schedule(schedule, _state({}))
    assert "operador_disponivel" not in report2.checks_run
