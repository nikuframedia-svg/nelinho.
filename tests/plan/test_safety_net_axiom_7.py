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
    """A baseline schedule with all KPIs populated.

    Keys match decoder.compute_kpis output exactly — `setups` (an int
    count) and `total_idle_hours`, not the `total_setup_time_h` /
    `idle_operators_h` names earlier drafts of this test used.

    Sprint Q.54.G — added `lam_utilization` (% in Laminagem) and
    `idle_ratio` (horizon-normalised idle fraction).
    """
    return {
        "num_late_orders": 2,
        "total_tardiness_hours": 8.0,
        "otd_delivery": 0.92,
        "makespan_hours": 100.0,
        "throughput_eur_day": 32_000.0,
        "avg_quality_risk": 0.10,
        "setups": 10,
        "total_idle_hours": 5.0,
        "lam_utilization": 42.0,
        "idle_ratio": 0.18,
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


def test_setup_time_rise_above_15pct_blocks():
    base = _baseline_full()
    cand = dict(base, setups=12)  # 10 × 1.2, beyond the 15% tolerance
    assert is_worse_than_baseline(cand, base) is True
    violations = _gather_violations(cand, base)
    assert any(v[0] == "setups" for v in violations)


def test_setup_time_rise_within_15pct_passes():
    base = _baseline_full()
    cand = dict(base, setups=11)  # 10 × 1.1, within the 15% tolerance
    assert is_worse_than_baseline(cand, base) is False


def test_idle_operators_rise_above_20pct_blocks():
    base = _baseline_full()
    cand = dict(base, total_idle_hours=6.5)  # 5 × 1.3, beyond 20%
    assert is_worse_than_baseline(cand, base) is True
    violations = _gather_violations(cand, base)
    assert any(v[0] == "total_idle_hours" for v in violations)


def test_idle_operators_rise_within_20pct_passes():
    base = _baseline_full()
    cand = dict(base, total_idle_hours=5.9)  # +18%, within 20% tolerance
    assert is_worse_than_baseline(cand, base) is False


# ─── NEW Sprint Q.54.G guardrails — lam_utilization + idle_ratio ────


def test_lam_utilization_drop_above_5pp_blocks():
    """A candidate that drains Laminagem (the bottleneck) more than 5
    percentage points below baseline must flip to baseline — even when
    every other KPI holds."""
    base = _baseline_full()
    cand = dict(base, lam_utilization=36.0)  # 42 → 36 = 6pp drop
    assert is_worse_than_baseline(cand, base) is True
    violations = _gather_violations(cand, base)
    assert any(v[0] == "lam_utilization" for v in violations)


def test_lam_utilization_drop_within_5pp_passes():
    base = _baseline_full()
    cand = dict(base, lam_utilization=38.0)  # 4pp drop, within tolerance
    assert is_worse_than_baseline(cand, base) is False


def test_lam_utilization_rise_passes():
    """Higher Laminagem utilisation is good — never blocks."""
    base = _baseline_full()
    cand = dict(base, lam_utilization=55.0)
    assert is_worse_than_baseline(cand, base) is False


def test_idle_ratio_rise_above_5pp_blocks():
    base = _baseline_full()
    cand = dict(base, idle_ratio=0.25)  # 0.18 → 0.25 = 7pp rise
    assert is_worse_than_baseline(cand, base) is True
    violations = _gather_violations(cand, base)
    assert any(v[0] == "idle_ratio" for v in violations)


def test_idle_ratio_rise_within_5pp_passes():
    base = _baseline_full()
    cand = dict(base, idle_ratio=0.21)  # +3pp, within tolerance
    assert is_worse_than_baseline(cand, base) is False


def test_idle_ratio_drop_passes():
    """Lower idle ratio is good — never blocks."""
    base = _baseline_full()
    cand = dict(base, idle_ratio=0.05)
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


def test_missing_lam_utilization_does_not_block():
    """Older decoder paths may not emit lam_utilization — only enforce
    when both sides carry it."""
    base = _baseline_full()
    cand = dict(base)
    cand.pop("lam_utilization")
    base.pop("lam_utilization")
    assert is_worse_than_baseline(cand, base) is False


def test_missing_idle_ratio_does_not_block():
    base = _baseline_full()
    cand = dict(base)
    cand.pop("idle_ratio")
    base.pop("idle_ratio")
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


# ─── Property test — Spelke axiom 7 (Sprint Q.54.G) ─────────────────
#
# The safety net is a monotone guard: a candidate that is better-or-
# equal on EVERY guardrail dimension must NEVER be blocked, and a
# candidate that degrades ANY single dimension past its tolerance must
# ALWAYS be blocked. These two properties together pin axiom 7 closed
# across the full 9-dimension space — including the two Q.54.G
# additions (lam_utilization, idle_ratio).

from hypothesis import HealthCheck, given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402


@st.composite
def _kpi_schedule(draw):
    """A schedule dict with all nine guardrail KPIs at random but
    realistic NELO-scale values."""
    return {
        "num_late_orders": draw(st.integers(min_value=0, max_value=20)),
        "total_tardiness_hours": draw(
            st.floats(min_value=0.0, max_value=200.0, allow_nan=False)
        ),
        "otd_delivery": draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
        "makespan_hours": draw(
            st.floats(min_value=10.0, max_value=600.0, allow_nan=False)
        ),
        "throughput_eur_day": draw(
            st.floats(min_value=1_000.0, max_value=40_000.0, allow_nan=False)
        ),
        "avg_quality_risk": draw(
            st.floats(min_value=0.01, max_value=0.9, allow_nan=False)
        ),
        "setups": draw(st.integers(min_value=1, max_value=80)),
        "total_idle_hours": draw(
            st.floats(min_value=1.0, max_value=300.0, allow_nan=False)
        ),
        "lam_utilization": draw(
            st.floats(min_value=5.0, max_value=95.0, allow_nan=False)
        ),
        "idle_ratio": draw(st.floats(min_value=0.0, max_value=0.95, allow_nan=False)),
    }


@settings(deadline=None, max_examples=300, suppress_health_check=[HealthCheck.too_slow])
@given(base=_kpi_schedule())
def test_axiom7_equal_candidate_never_blocked(base):
    """Identity property: a candidate identical to the baseline is
    never worse than the baseline. If this fails, a guardrail has a
    sign error or an off-by-one tolerance."""
    cand = dict(base)
    assert is_worse_than_baseline(cand, base) is False


@settings(deadline=None, max_examples=300, suppress_health_check=[HealthCheck.too_slow])
@given(base=_kpi_schedule())
def test_axiom7_strictly_better_candidate_never_blocked(base):
    """A candidate that improves EVERY dimension (lower tardiness/idle/
    setups/makespan/risk, higher otd/throughput/lam_util, lower
    late-orders) must always pass — the safety net can't reject a pure
    win."""
    cand = {
        "num_late_orders": max(0, base["num_late_orders"] - 1),
        "total_tardiness_hours": base["total_tardiness_hours"] * 0.5,
        "otd_delivery": min(1.0, base["otd_delivery"] + 0.05),
        "makespan_hours": base["makespan_hours"] * 0.9,
        "throughput_eur_day": base["throughput_eur_day"] * 1.1,
        "avg_quality_risk": base["avg_quality_risk"] * 0.5,
        "setups": max(1, base["setups"] - 1),
        "total_idle_hours": base["total_idle_hours"] * 0.5,
        "lam_utilization": min(100.0, base["lam_utilization"] + 1.0),
        "idle_ratio": base["idle_ratio"] * 0.5,
    }
    assert is_worse_than_baseline(cand, base) is False


@settings(deadline=None, max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(
    base=_kpi_schedule(),
    which=st.sampled_from(["lam_utilization", "idle_ratio"]),
)
def test_axiom7_q54g_dimension_degradation_always_blocked(base, which):
    """Single-dimension degradation property for the two Q.54.G
    additions: pushing lam_utilization well below baseline OR idle_ratio
    well above baseline — with everything else held equal — must always
    flip the safety net. This is the primary defence for axiom 7's last
    two holes; if it fails, the guardrail is unplugged."""
    cand = dict(base)
    if which == "lam_utilization":
        # Drop 20pp below baseline — far past the 5pp tolerance.
        cand["lam_utilization"] = max(0.0, base["lam_utilization"] - 20.0)
        # Skip the (rare) case where the baseline is already near the
        # floor (clamped at 0) so the realised drop can't clear the 5pp
        # tolerance with comfortable margin. Require >6pp so float noise
        # at the tolerance boundary can't flip the assertion.
        if base["lam_utilization"] - cand["lam_utilization"] <= 6.0:
            return
    else:  # idle_ratio
        cand["idle_ratio"] = min(1.0, base["idle_ratio"] + 0.20)
        # Same boundary guard — require a realised rise >6pp so a
        # baseline near the 1.0 ceiling can't land exactly on tolerance.
        if cand["idle_ratio"] - base["idle_ratio"] <= 0.06:
            return
    assert is_worse_than_baseline(cand, base) is True
    violations = _gather_violations(cand, base)
    assert any(v[0] == which for v in violations)
