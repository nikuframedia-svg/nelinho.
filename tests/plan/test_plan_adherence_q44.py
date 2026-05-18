"""
Tests for src.plan.services.plan_adherence_service — F13 (Sprint Q.44).

Comparação plano vs realizado: aderência ao plano, desvios por fase,
operações em falta / não planeadas. Lógica pura, sem I/O — cada teste é
uma spec independente (DAMP).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from src.plan.services.plan_adherence_service import (
    DEFAULT_TOLERANCE_HOURS,
    RealizedOperation,
    compare_adherence,
    realized_from_operation_rows,
)


T0 = datetime(2026, 5, 18, 8, 0, 0)


def _planned(order_id, phase_id, start=None, end=None):
    op = {"order_id": order_id, "phase_id": phase_id, "operation_id": f"{order_id}-{phase_id}"}
    if start is not None:
        op["start_time"] = start.isoformat()
    if end is not None:
        op["end_time"] = end.isoformat()
    return op


# ---------------------------------------------------------------------------
# Aderência perfeita / nula
# ---------------------------------------------------------------------------

class TestAdherencePct:
    def test_all_executed_on_time_is_full_adherence(self):
        planned = [
            _planned("1001", "10", start=T0, end=T0 + timedelta(hours=4)),
            _planned("1001", "20", start=T0 + timedelta(hours=4), end=T0 + timedelta(hours=8)),
        ]
        realized = [
            RealizedOperation("1001", "10", start_at=T0, end_at=T0 + timedelta(hours=4)),
            RealizedOperation(
                "1001", "20",
                start_at=T0 + timedelta(hours=4),
                end_at=T0 + timedelta(hours=8),
            ),
        ]
        result = compare_adherence(planned, realized)
        assert result.planned_total == 2
        assert result.matched_total == 2
        assert result.within_tolerance_total == 2
        assert result.adherence_pct == 100.0
        assert result.match_pct == 100.0

    def test_missing_real_execution_is_not_adherent(self):
        planned = [
            _planned("1001", "10", start=T0),
            _planned("1001", "20", start=T0 + timedelta(hours=4)),
        ]
        realized = [RealizedOperation("1001", "10", start_at=T0)]
        result = compare_adherence(planned, realized)
        assert result.matched_total == 1
        assert result.adherence_pct == 50.0
        assert result.missing == [{"order_id": "1001", "phase_id": "20"}]

    def test_empty_plan_yields_zero_pct_not_crash(self):
        result = compare_adherence([], [])
        assert result.adherence_pct == 0.0
        assert result.match_pct == 0.0
        assert result.planned_total == 0


# ---------------------------------------------------------------------------
# Tolerância de horas
# ---------------------------------------------------------------------------

class TestTolerance:
    def test_drift_within_tolerance_counts_as_adherent(self):
        planned = [_planned("1001", "10", start=T0)]
        # 6 h de atraso, dentro da janela de 8 h por omissão
        realized = [RealizedOperation("1001", "10", start_at=T0 + timedelta(hours=6))]
        result = compare_adherence(planned, realized)
        assert result.within_tolerance_total == 1
        assert result.adherence_pct == 100.0

    def test_drift_beyond_tolerance_matched_but_not_adherent(self):
        planned = [_planned("1001", "10", start=T0)]
        # 30 h de atraso — executou, mas não cumpriu o plano
        realized = [RealizedOperation("1001", "10", start_at=T0 + timedelta(hours=30))]
        result = compare_adherence(planned, realized)
        assert result.matched_total == 1
        assert result.within_tolerance_total == 0
        assert result.adherence_pct == 0.0
        assert result.match_pct == 100.0

    def test_custom_tolerance_is_honoured(self):
        planned = [_planned("1001", "10", start=T0)]
        realized = [RealizedOperation("1001", "10", start_at=T0 + timedelta(hours=3))]
        strict = compare_adherence(planned, realized, tolerance_hours=2.0)
        assert strict.within_tolerance_total == 0
        loose = compare_adherence(planned, realized, tolerance_hours=4.0)
        assert loose.within_tolerance_total == 1

    def test_default_tolerance_is_one_shift(self):
        assert DEFAULT_TOLERANCE_HOURS == 8.0


# ---------------------------------------------------------------------------
# Desvios por fase
# ---------------------------------------------------------------------------

class TestPhaseDeviations:
    def test_avg_start_drift_reported_per_phase(self):
        planned = [
            _planned("1001", "10", start=T0),
            _planned("1002", "10", start=T0),
        ]
        realized = [
            RealizedOperation("1001", "10", start_at=T0 + timedelta(hours=2)),
            RealizedOperation("1002", "10", start_at=T0 + timedelta(hours=4)),
        ]
        result = compare_adherence(planned, realized)
        phase10 = next(p for p in result.phase_deviations if p.phase_id == "10")
        assert phase10.planned_count == 2
        assert phase10.matched_count == 2
        # média de (2 h, 4 h) = 3 h de deriva
        assert phase10.avg_start_drift_hours == 3.0

    def test_phase_with_no_real_data_has_none_drift(self):
        planned = [_planned("1001", "99", start=T0)]
        result = compare_adherence(planned, [])
        phase99 = next(p for p in result.phase_deviations if p.phase_id == "99")
        assert phase99.matched_count == 0
        assert phase99.avg_start_drift_hours is None


# ---------------------------------------------------------------------------
# Operações não planeadas + junção
# ---------------------------------------------------------------------------

class TestUnplannedAndJoin:
    def test_realized_op_not_in_plan_is_unplanned(self):
        planned = [_planned("1001", "10", start=T0)]
        realized = [
            RealizedOperation("1001", "10", start_at=T0),
            RealizedOperation("9999", "10", start_at=T0),  # OF que não estava no plano
        ]
        result = compare_adherence(planned, realized)
        assert result.unplanned == [{"order_id": "9999", "phase_id": "10"}]

    def test_repeated_real_op_keeps_earliest_start(self):
        planned = [_planned("1001", "10", start=T0)]
        realized = [
            RealizedOperation("1001", "10", start_at=T0 + timedelta(hours=20)),  # retrabalho
            RealizedOperation("1001", "10", start_at=T0 + timedelta(hours=1)),   # 1ª passagem
        ]
        result = compare_adherence(planned, realized)
        # a 1ª passagem (1 h de deriva) é a que conta, não o retrabalho
        assert result.within_tolerance_total == 1
        phase10 = result.phase_deviations[0]
        assert phase10.avg_start_drift_hours == 1.0

    def test_join_key_is_order_plus_phase_not_operation_id(self):
        # operation_id planeado é string CPO; o real seria OFFP_ID — não casam.
        # A junção tem de ser por (order_id, phase_id).
        planned = [_planned("1001", "10", start=T0)]
        realized = [RealizedOperation("1001", "10", start_at=T0)]
        result = compare_adherence(planned, realized)
        assert result.matched_total == 1


# ---------------------------------------------------------------------------
# Conversão a partir de OperationRow do reader ERP
# ---------------------------------------------------------------------------

class TestRealizedFromRows:
    def test_converts_operation_row_like_objects(self):
        class _Row:
            def __init__(self, woid, pid, start, end):
                self.work_order_id = woid
                self.phase_id = pid
                self.start_at = start
                self.end_at = end

        rows = [_Row(1001, 10, T0, T0 + timedelta(hours=4))]
        realized = realized_from_operation_rows(rows)
        assert len(realized) == 1
        assert realized[0].work_order_id == "1001"
        assert realized[0].phase_id == "10"
        assert realized[0].start_at == T0

    def test_round_trip_through_converter_matches(self):
        class _Row:
            work_order_id = 1001
            phase_id = 10
            start_at = T0
            end_at = T0 + timedelta(hours=4)

        planned = [_planned("1001", "10", start=T0)]
        realized = realized_from_operation_rows([_Row()])
        result = compare_adherence(planned, realized)
        assert result.adherence_pct == 100.0
