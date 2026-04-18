"""
Tests for src.copilot.poetiq — K.4 simplified loop.

Only the helpers (`_kernel_score`, `_conversation_summary`) + schema
validation are covered here; the full endpoint integration requires a
live DB + curated data, which is the smoke-test scope.
"""

from __future__ import annotations

import pytest

from src.copilot.poetiq import (
    POETIQDelta,
    POETIQProposeRequest,
    _conversation_summary,
    _kernel_score,
)


class TestKernelScore:
    def test_best_case_no_tardy_full_util_safe(self):
        result = {
            "num_late_orders": 0,
            "avg_utilization": 100.0,
            "safety_net_triggered": False,
        }
        assert _kernel_score(result) == pytest.approx(1.0)

    def test_worst_case_tardy_low_util_safety_triggered(self):
        result = {
            "num_late_orders": 5,
            "avg_utilization": 0.0,
            "safety_net_triggered": True,
        }
        # (0.5 + 0 + 0.2) / 3 ≈ 0.2333
        assert _kernel_score(result) == pytest.approx(0.2333, abs=1e-3)

    def test_no_tardy_mid_util_safe(self):
        result = {
            "num_late_orders": 0,
            "avg_utilization": 60.0,
            "safety_net_triggered": False,
        }
        # (1 + 0.6 + 1) / 3 ≈ 0.8667
        assert _kernel_score(result) == pytest.approx(0.8667, abs=1e-3)

    def test_bounded_when_utilization_overflows(self):
        result = {
            "num_late_orders": 0,
            "avg_utilization": 200.0,  # should clamp to 1.0
            "safety_net_triggered": False,
        }
        assert _kernel_score(result) == pytest.approx(1.0)


class TestConversationSummary:
    def test_summary_covers_key_fields(self):
        result = {
            "makespan_hours": 12.4,
            "num_late_orders": 2,
            "avg_utilization": 55.3,
        }
        summary = _conversation_summary(
            result,
            commit_sha="abcdef1234567890",
            diff_payload={
                "summary": {"added_count": 3, "removed_count": 1, "changed_count": 4},
            },
        )
        assert "12.4h" in summary
        assert "tardy=2" in summary
        assert "abcdef123456" in summary
        assert "+3" in summary and "-1" in summary

    def test_summary_without_commit_or_diff(self):
        summary = _conversation_summary(
            {"makespan_hours": 5.0, "num_late_orders": 0, "avg_utilization": 40.0},
            commit_sha=None,
            diff_payload=None,
        )
        assert "Plano simulado" in summary
        assert "Commit" not in summary


class TestSchemas:
    def test_delta_requires_entity_type(self):
        with pytest.raises(ValueError):
            POETIQDelta(entity_type="", patch={})

    def test_request_defaults(self):
        req = POETIQProposeRequest(
            proposal="e se reduzir lote K1 em 20%?",
            delta=POETIQDelta(entity_type="standard_time", patch={"reduction_pct": 20}),
        )
        assert req.horizon_days == 14
        assert req.population_size == 50
        assert req.llm_qual == 1.0

    def test_llm_qual_bounded(self):
        with pytest.raises(ValueError):
            POETIQProposeRequest(
                proposal="x",
                delta=POETIQDelta(entity_type="x"),
                llm_qual=1.5,
            )
