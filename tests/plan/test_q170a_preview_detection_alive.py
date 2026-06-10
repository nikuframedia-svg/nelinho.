"""Q.170.A — os detetores do preview estavam MORTOS em runtime.

Achado CRITICAL da auditoria 2026-06-10 (verificado à mão): as ops do
commit usam `start_time`/`end_time` (decoder `_scheduled_to_dict`) mas o
preview lia `op.get("start")`/`("end")` → None → NENHUM detetor disparava
(double-booking, molde, precedência, cura). E a 2ª camada (padrão
Q.169.F): os checks de pares/precedência/cura comparam códigos por NOME
normalizado, mas as ops trazem `phase_id` NUMÉRICO do ERP → tudo vazio.

Estes testes usam o shape REAL das ops do commit (start_time + phase_id
numérico) — antes do fix, todos os detetores devolviam [].
"""
from __future__ import annotations

from datetime import datetime, timedelta

from src.plan.services.preview_delta_service import (
    PreviewMutation,
    _CURING_GAPS,
    _detect_conflicts,
    _detect_sequence_issues,
    _detect_warnings,
)

_T0 = datetime(2026, 6, 15, 8, 0, 0)

_NAMES = {"1": "Laminagem", "2": "Cura", "67": "Laminagem Infusão"}


def _op(oid, order, phase, start_h, end_h, workers=(), mold=None):
    """Shape REAL de uma op de commit (start_time/end_time, id numérico)."""
    return {
        "operation_id": oid,
        "order_id": order,
        "phase_id": phase,
        "workers": list(workers),
        "mold_id": mold,
        "mold_batch_id": None,
        "start_time": (_T0 + timedelta(hours=start_h)).isoformat(),
        "end_time": (_T0 + timedelta(hours=end_h)).isoformat(),
    }


class TestConflictsFireOnRealShape:
    def test_worker_double_booking_detected(self):
        """O conflito que NUNCA disparava com `start`/`end` errados."""
        schedule = {"operations": [
            _op("a", "OF-1", "1", 0, 4, workers=("W1",)),
            _op("b", "OF-2", "1", 2, 6, workers=("W2",)),
        ]}
        out = _detect_conflicts(
            schedule, PreviewMutation(operation_id="a", new_worker_ids=["W2"]),
        )
        assert any(i.type == "worker_double_booking" for i in out), (
            "mover W2 para a op 'a' sobrepõe a op 'b' — tem de disparar"
        )

    def test_mold_conflict_detected(self):
        schedule = {"operations": [
            _op("a", "OF-1", "1", 0, 4, mold="M9"),
            _op("b", "OF-2", "1", 2, 6, mold="M9"),
        ]}
        out = _detect_conflicts(
            schedule, PreviewMutation(operation_id="a", new_worker_ids=None),
        )
        assert any(i.type == "mold_double_booking" for i in out)

    def test_no_overlap_no_conflict(self):
        schedule = {"operations": [
            _op("a", "OF-1", "1", 0, 4, workers=("W1",)),
            _op("b", "OF-2", "1", 4, 8, workers=("W2",)),
        ]}
        out = _detect_conflicts(
            schedule, PreviewMutation(operation_id="a", new_worker_ids=["W2"]),
        )
        assert not [i for i in out if i.type == "worker_double_booking"]


class TestWarningsWithNumericPhaseIds:
    def test_laminagem_solo_warns(self):
        """phase_id "1" + mapa id→nome → LAMINAGEM par-preferida deteta solo."""
        schedule = {"operations": [_op("a", "OF-1", "1", 0, 4, workers=("W1",))]}
        out = _detect_warnings(
            schedule, PreviewMutation(operation_id="a"), _NAMES,
        )
        assert any(i.type == "pair_rule" for i in out)

    def test_infusao_solo_does_not_warn(self):
        """Match EXATO: Infusão (67) é solo por política (98.8% real)."""
        schedule = {"operations": [_op("a", "OF-1", "67", 0, 4, workers=("W1",))]}
        out = _detect_warnings(
            schedule, PreviewMutation(operation_id="a"), _NAMES,
        )
        assert not [i for i in out if i.type == "pair_rule"]


class TestSequenceAndCuringWithNumericIds:
    _RANK = {"LAMINAGEM": 1, "CURA": 2}

    def test_curing_gap_violation_warns(self):
        """Cura 1h depois da Laminagem (mín 15h) com ids numéricos."""
        schedule = {"operations": [
            _op("a", "OF-1", "1", 0, 4),
            _op("b", "OF-1", "2", 5, 9),
        ]}
        out = _detect_sequence_issues(
            schedule, PreviewMutation(operation_id="b"),
            self._RANK, _CURING_GAPS, _NAMES,
        )
        assert any(i.type == "curing_gap_violation" for i in out)

    def test_curing_gap_respected_is_clean(self):
        schedule = {"operations": [
            _op("a", "OF-1", "1", 0, 4),
            _op("b", "OF-1", "2", 4 + 15.5, 4 + 20),
        ]}
        out = _detect_sequence_issues(
            schedule, PreviewMutation(operation_id="b"),
            self._RANK, _CURING_GAPS, _NAMES,
        )
        assert not [i for i in out if i.type == "curing_gap_violation"]

    def test_precedence_inversion_conflicts(self):
        """Cura agendada ANTES da Laminagem da mesma OF → conflito."""
        schedule = {"operations": [
            _op("a", "OF-1", "1", 10, 14),   # Laminagem depois...
            _op("b", "OF-1", "2", 0, 4),     # ...da Cura — invertido
        ]}
        out = _detect_sequence_issues(
            schedule, PreviewMutation(operation_id="b"),
            self._RANK, _CURING_GAPS, _NAMES,
        )
        assert any(i.type == "precedence_violation" for i in out)


class TestLegacyShapeStillWorks:
    def test_legacy_start_end_fields_accepted(self):
        """Payloads antigos com `start`/`end` continuam a funcionar."""
        schedule = {"operations": [
            {"operation_id": "a", "order_id": "OF-1", "phase_id": "1",
             "workers": ["W1"], "mold_id": None,
             "start": _T0.isoformat(),
             "end": (_T0 + timedelta(hours=4)).isoformat()},
            {"operation_id": "b", "order_id": "OF-2", "phase_id": "1",
             "workers": ["W2"], "mold_id": None,
             "start": (_T0 + timedelta(hours=2)).isoformat(),
             "end": (_T0 + timedelta(hours=6)).isoformat()},
        ]}
        out = _detect_conflicts(
            schedule, PreviewMutation(operation_id="a", new_worker_ids=["W2"]),
        )
        assert any(i.type == "worker_double_booking" for i in out)
