"""Sprint Q.13.A — Spelke axiom 7 expand regression.

Pre-fix `safety_net.is_worse_than_baseline()` only compared 4 KPIs
(num_late_orders, total_tardiness_hours, otd_delivery, makespan 1.5×
cap). A candidate could:
  * drop throughput by 10% silently
  * raise quality_risk by 25% silently
  * double setup_time silently
  * starve operators (idle +50%) silently
…and the safety net would approve it as long as tardiness/OTD held.

These tests pin the new 4 guardrails in place so future refactors
can't unplug them without turning a test red.
"""

from __future__ import annotations

from src.plan.cpo.safety_net import (
    _gather_violations,
    apply_safety_net,
    is_worse_than_baseline,
)


# ─── Existing 4 guardrails — sanity checks ──────────────────────────


def _baseline_full():
    """A baseline schedule with all 7 KPIs populated."""
    return {
        "num_late_orders": 2,
        "total_tardiness_hours": 8.0,
        "otd_delivery": 0.92,
        "makespan_hours": 100.0,
        "throughput_eur_day": 32_000.0,
        "avg_quality_risk": 0.10,
        "setups": 12,
        "total_idle_hours": 5.0,
    }


def test_baseline_against_baseline_no_violations():
    base = _baseline_full()
    violations = _gather_violations(base, base)
    assert violations == []
    assert is_worse_than_baseline(base, base) is False


def test_late_order_increase_blocks():
    base = _baseline_full()
    cand = dict(base, num_late_orders=3)
    assert is_worse_than_baseline(cand, base) is True


def test_tardiness_increase_blocks():
    base = _baseline_full()
    cand = dict(base, total_tardiness_hours=10.0)
    assert is_worse_than_baseline(cand, base) is True


def test_otd_drop_blocks():
    base = _baseline_full()
    cand = dict(base, otd_delivery=0.85)
    assert is_worse_than_baseline(cand, base) is True


def test_makespan_within_1_5x_passes():
    base = _baseline_full()
    cand = dict(base, makespan_hours=140.0)  # 1.4×, ok
    assert is_worse_than_baseline(cand, base) is False


def test_makespan_above_1_5x_blocks():
    base = _baseline_full()
    cand = dict(base, makespan_hours=160.0)  # 1.6×
    assert is_worse_than_baseline(cand, base) is True


# ─── NEW Sprint Q.13.A guardrails ────────────────────────────────────


def test_throughput_drop_above_5pct_blocks():
    """The original gap. A candidate that drops throughput by 10% with
    everything else equal would have passed; now it doesn't."""
    base = _baseline_full()
    # 5% tolerance — 32k × 0.95 = 30.4k; 30.39k is just under.
    cand = dict(base, throughput_eur_day=30_300.0)
    assert is_worse_than_baseline(cand, base) is True
    violations = _gather_violations(cand, base)
    assert any(v[0] == "throughput_eur_day" for v in violations)


def test_throughput_drop_within_5pct_passes():
    base = _baseline_full()
    # 32k × 0.96 = 30.72k — within the 5% noise band.
    cand = dict(base, throughput_eur_day=30_720.0)
    assert is_worse_than_baseline(cand, base) is False


def test_quality_risk_rise_above_10pct_blocks():
    base = _baseline_full()
    # 0.10 × 1.15 = 0.115 — beyond 10% tolerance.
    cand = dict(base, avg_quality_risk=0.115)
    assert is_worse_than_baseline(cand, base) is True
    violations = _gather_violations(cand, base)
    assert any(v[0] == "avg_quality_risk" for v in violations)


def test_quality_risk_rise_within_10pct_passes():
    base = _baseline_full()
    cand = dict(base, avg_quality_risk=0.108)  # +8%, within tolerance
    assert is_worse_than_baseline(cand, base) is False


def test_setups_rise_above_15pct_blocks():
    """Nightly Karpathy fix 2026-05-07 — key renamed from
    `total_setup_time_h` (which decoder never emits) to `setups`
    (decoder.compute_kpis line ~700, integer count)."""
    base = _baseline_full()
    cand = dict(base, setups=14)  # 12 × 1.167 = 14, beyond 15% tolerance
    assert is_worse_than_baseline(cand, base) is True
    violations = _gather_violations(cand, base)
    assert any(v[0] == "setups" for v in violations)


def test_setups_rise_within_15pct_passes():
    base = _baseline_full()
    cand = dict(base, setups=13)  # 12 × 1.083, within tolerance
    assert is_worse_than_baseline(cand, base) is False


def test_total_idle_hours_rise_above_20pct_blocks():
    """Nightly Karpathy fix 2026-05-07 — key renamed from
    `idle_operators_h` (which decoder never emits) to `total_idle_hours`
    (decoder.compute_kpis line ~703)."""
    base = _baseline_full()
    cand = dict(base, total_idle_hours=6.5)  # 5 × 1.3, beyond 20%
    assert is_worse_than_baseline(cand, base) is True
    violations = _gather_violations(cand, base)
    assert any(v[0] == "total_idle_hours" for v in violations)


def test_total_idle_hours_rise_within_20pct_passes():
    base = _baseline_full()
    cand = dict(base, total_idle_hours=5.9)  # +18%, within
    assert is_worse_than_baseline(cand, base) is False


# ─── Behaviour when KPI absent ──────────────────────────────────────


def test_missing_throughput_does_not_block():
    """A candidate may be from an older path that doesn't compute
    throughput. We don't block — only enforce when both sides have it."""
    base = _baseline_full()
    cand = dict(base)
    cand.pop("throughput_eur_day")
    base.pop("throughput_eur_day")
    assert is_worse_than_baseline(cand, base) is False


def test_missing_quality_risk_does_not_block():
    base = _baseline_full()
    cand = dict(base)
    cand.pop("avg_quality_risk")
    base.pop("avg_quality_risk")
    assert is_worse_than_baseline(cand, base) is False


# ─── apply_safety_net contract ──────────────────────────────────────


def test_apply_safety_net_attaches_violations_list():
    """The new contract returns the violations list on the resulting
    schedule so observability + the timeline UI can show WHY the
    safety net flipped to baseline."""
    base = _baseline_full()
    cand = dict(base, throughput_eur_day=29_000.0, avg_quality_risk=0.20)

    result = apply_safety_net(cand, base)
    assert result["safety_net_triggered"] is True
    assert "safety_net_violations" in result
    metrics = {v["metric"] for v in result["safety_net_violations"]}
    assert "throughput_eur_day" in metrics
    assert "avg_quality_risk" in metrics
    assert "guardrail" in result["safety_net_reason"]


def test_apply_safety_net_clean_candidate_passes_through():
    base = _baseline_full()
    cand = dict(base, makespan_hours=95.0)  # better!
    result = apply_safety_net(cand, base)
    assert result["safety_net_triggered"] is False
    assert result["safety_net_violations"] == []
    # Original keys preserved — safety_net is a guard, not a transformer.
    assert result["makespan_hours"] == 95.0


# ─── Integration guard: decoder.compute_kpis ↔ safety_net ───────────
# Onda nightly 2026-05-07 (Karpathy loop) — pin the contract that the
# decoder's KPI dict matches the keys safety_net reads. Before this
# test, `idle_operators_h` and `total_setup_time_h` lived in safety_net
# but decoder emitted `total_idle_hours` and `setups`, so 2 of the 4
# Sprint Q.13.A guardrails were silent no-ops (.get() → None →
# comparison skipped). avg_quality_risk stays absent on purpose
# (decoder doesn't compute it; fitness fills it from a predictor when
# one is wired).


def test_decoder_kpi_keys_cover_safety_net_soft_guardrails():
    """Static guard: every soft-guardrail key safety_net reads (except
    the dormant avg_quality_risk) must appear in decoder.compute_kpis'
    output dict. If a future refactor renames a key in either side,
    this test turns red — exactly the regression that this nightly
    fix recovers from."""
    import re
    from pathlib import Path

    decoder_src = Path("src/plan/cpo/decoder.py").read_text(encoding="utf-8")
    # Find the KPI dict literal that compute_kpis returns. The block we
    # care about contains `"makespan_hours":`, `"setups":`,
    # `"total_idle_hours":`, etc. — read keys directly to avoid grepping
    # comments.
    decoder_keys = set(
        re.findall(r'"([a-z_]+)":\s*(?:round|int|float|0|max|min|len)',
                   decoder_src)
    )
    # The keys safety_net reads on candidate / baseline (via .get()):
    safety_keys_active = {
        "num_late_orders", "total_tardiness_hours", "otd_delivery",
        "makespan_hours", "throughput_eur_day", "setups",
        "total_idle_hours",
    }
    missing = safety_keys_active - decoder_keys
    assert not missing, (
        f"safety_net reads keys the decoder doesn't emit: {missing}. "
        "If you renamed a KPI in the decoder, update safety_net.py to "
        "match (and vice versa). The dormant avg_quality_risk is "
        "intentionally NOT in this list — it comes from the fitness "
        "predictor, not the decoder."
    )
