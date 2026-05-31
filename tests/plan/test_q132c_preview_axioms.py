"""Q.132.C — drag-and-drop respeita precedência (axioma 2) + cura (axioma 6).

Antes, o preview do arrastar só validava molde+operador; mover uma fase para
fora de ordem, ou colá-la violando a janela de cura, passava em silêncio.
`_detect_sequence_issues` surfaça ambos: precedência como conflito, cura como
aviso (com base em NELO_CURING_GAPS_SEED).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from src.plan.services.preview_delta_service import (
    _CURING_GAPS,
    PreviewMutation,
    _detect_sequence_issues,
)

_RANK = {"LAMINAGEM": 1, "CURA": 2, "PINTURA": 3}
_BASE = datetime(2026, 6, 1, 8, 0, 0)


def _op(opid: str, order: str, phase: str, start: datetime, dur_h: float = 2.0):
    return {
        "id": opid, "operation_id": opid, "order_id": order, "phase_id": phase,
        "start": start.isoformat(),
        "end": (start + timedelta(hours=dur_h)).isoformat(),
    }


def _issues(ops, op_id):
    sched = {"operations": ops}
    mut = PreviewMutation(operation_id=op_id)
    return _detect_sequence_issues(sched, mut, _RANK, _CURING_GAPS)


def test_precedence_violation_is_a_conflict():
    # CURA (rank 2) agendada ÀS 08:00, mas a sua predecessora LAMINAGEM (rank 1)
    # só começa às 13:00 → sequência invertida.
    cura = _op("op-cura", "OF1", "Cura", _BASE)
    lam = _op("op-lam", "OF1", "Laminagem", _BASE + timedelta(hours=5))
    issues = _issues([cura, lam], "op-cura")
    assert any(
        i.type == "precedence_violation" and i.severity == "conflict"
        for i in issues
    )


def test_no_precedence_issue_when_ordered():
    lam = _op("op-lam", "OF1", "Laminagem", _BASE)
    cura = _op("op-cura", "OF1", "Cura", _BASE + timedelta(hours=20))
    issues = _issues([lam, cura], "op-cura")
    assert not any(i.type == "precedence_violation" for i in issues)


def test_curing_gap_violation_is_a_warning():
    # LAMINAGEM→CURA exige 15.0h; aqui só há 2h de gap.
    lam = _op("op-lam", "OF1", "Laminagem", _BASE, dur_h=2.0)   # acaba 10:00
    cura = _op("op-cura", "OF1", "Cura", _BASE + timedelta(hours=4))  # 12:00
    issues = _issues([lam, cura], "op-cura")
    assert any(
        i.type == "curing_gap_violation" and i.severity == "warning"
        for i in issues
    )


def test_curing_gap_ok_when_respected():
    lam = _op("op-lam", "OF1", "Laminagem", _BASE, dur_h=2.0)   # acaba 10:00
    cura = _op("op-cura", "OF1", "Cura", _BASE + timedelta(hours=20))  # gap 18h
    issues = _issues([lam, cura], "op-cura")
    assert not any(i.type == "curing_gap_violation" for i in issues)


def test_empty_rank_map_skips_validation():
    # routing não semeado → sem precedência a validar (não inventa conflitos).
    sched = {"operations": [_op("a", "OF1", "Cura", _BASE)]}
    assert _detect_sequence_issues(sched, PreviewMutation(operation_id="a"), {}, _CURING_GAPS) == []


def test_other_orders_do_not_cross_contaminate():
    # uma fase de OUTRA ordem não conta para a precedência desta.
    cura = _op("op-cura", "OF1", "Cura", _BASE)
    lam_other = _op("op-lam2", "OF2", "Laminagem", _BASE + timedelta(hours=5))
    issues = _issues([cura, lam_other], "op-cura")
    assert not any(i.type == "precedence_violation" for i in issues)
