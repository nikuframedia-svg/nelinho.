"""
ProdPlan ONE — Correlation helpers for Mill's diff (Sprint Q.15.D.4)
=====================================================================

Cohen's d effect-size + a thin map to a 0-1 ``correlation`` score the
operator can read at a glance.

Why Cohen's d (and not Pearson)
-------------------------------

Mill's method asks "what changed between the good period and the bad
period". The natural framing is:

  * **good period:** samples of the metric (e.g. error_rate per day)
  * **bad period:** samples of the same metric

The shift is captured by the **standardised mean difference**:

    d = (mean_bad - mean_good) / pooled_std

Pearson would require pairing observations and runs the risk of
spurious correlation when the two periods aren't time-aligned. Cohen's
d is the right tool for "did the *level* shift" — which is what the
operator wants to know.

Mapping ``d → correlation``
---------------------------

Cohen's conventional bins:

    |d| <= 0.2  → trivial
    |d| <= 0.5  → small
    |d| <= 0.8  → medium
    |d| <= 1.5  → large
    |d| >  1.5  → very large

We map ``correlation = min(1.0, abs(d) / 1.5)`` so a "very large" d
saturates at 1.0 and "medium" sits at ~0.5. The Mill's diff endpoint
declares ``likely_cause=True`` when correlation >= 0.7 (≈ d >= 1.05),
which corresponds to a "large" effect — strong enough to act on but
not so strict that real causes get filtered.
"""

from __future__ import annotations

import math
from typing import List, Optional, Sequence


def cohens_d(
    group_a: Sequence[float],
    group_b: Sequence[float],
) -> Optional[float]:
    """Standardised mean difference between two samples.

    Returns ``None`` when either sample is empty OR when the pooled
    standard deviation is zero (no variance — undefined effect size).

    Sign convention: positive ``d`` means group_b's mean is higher
    than group_a's. For Mill's diff callers pass
    ``cohens_d(good, bad)`` so positive ``d`` means "the bad period
    has higher values" (typical for error_rate / lead_time metrics).
    """
    a = [float(x) for x in group_a]
    b = [float(x) for x in group_b]
    n_a, n_b = len(a), len(b)
    if n_a == 0 or n_b == 0:
        return None

    mean_a = sum(a) / n_a
    mean_b = sum(b) / n_b

    # Sample variance (n-1) for both groups; fall back to 0 when n=1.
    var_a = sum((x - mean_a) ** 2 for x in a) / (n_a - 1) if n_a > 1 else 0.0
    var_b = sum((x - mean_b) ** 2 for x in b) / (n_b - 1) if n_b > 1 else 0.0

    # Pooled std (Cohen's classic formulation).
    if n_a + n_b - 2 <= 0:
        return None
    pooled_var = (
        (n_a - 1) * var_a + (n_b - 1) * var_b
    ) / (n_a + n_b - 2)
    if pooled_var <= 0:
        return None
    pooled_std = math.sqrt(pooled_var)
    return (mean_b - mean_a) / pooled_std


def correlation_from_d(d: Optional[float]) -> float:
    """Map Cohen's |d| to a 0-1 ``correlation`` score.

    ``d`` of None (undefined effect size) returns 0.0 — Mill's diff
    treats that as "no signal" rather than crashing the dashboard.

    The 1.5 ceiling is deliberate: Cohen's "very large" effect (|d| >
    1.2) saturates here. Without it, an extreme outlier sample could
    push correlation to absurd values (5.0+) that the dashboard
    couldn't render meaningfully.
    """
    if d is None:
        return 0.0
    return min(1.0, abs(d) / 1.5)


def is_likely_cause(
    correlation: float, *, threshold: float = 0.7,
) -> bool:
    """``True`` when the correlation passes the "large effect" gate.

    0.7 corresponds to |d| ≈ 1.05 (Cohen's "large"). The Mill's diff
    UI renders ``likely_cause=True`` rows with the red badge so the
    operator can spot them without reading every entry.
    """
    return correlation >= threshold


__all__ = [
    "cohens_d",
    "correlation_from_d",
    "is_likely_cause",
]
