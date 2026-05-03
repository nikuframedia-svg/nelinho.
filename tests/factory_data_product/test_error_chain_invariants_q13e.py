"""Sprint Q.13.E E.6 — Error chain invariant tests.

Plan v4 §3.3: NELO's quality data is the *only* signal for capacity
correction. Lixagem água, Pintura Acab and Lixagem polim run at
49% / 42% / 41% retrabalho — but only if the rate-extraction pipeline
treats the data correctly.

These tests pin invariants that protect the rates from silently going
wrong:

  1. Rates are bounded in [0, 1] for any input — even pathological
     (more errors than order_phases for the same phase).
  2. A phase never appears in the rates dict if it had zero order
     phases (no division by zero, no infinity rates).
  3. The rate is exactly errors / phases for the well-formed case.
  4. Phases with `fase_id=""` are silently dropped (not '' rates).
  5. Empty input yields empty output (no spurious zeros for unknown
     phases).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.plan.cpo.state import _extract_error_rates


def _engine(*, errors=None, order_phases=None):
    """Tiny stand-in for the curated-data engine with the
    `_curated_data[active_id]` shape `_extract_error_rates` reads."""
    active_id = "ing-1"
    return SimpleNamespace(
        _active_ingestion_id=active_id,
        _curated_data={
            active_id: {
                "quality_events": list(errors or []),
                "order_phases": list(order_phases or []),
            },
        },
    )


def test_rates_bounded_in_unit_interval_even_for_more_errors_than_phases():
    """Pathological case: 50 errors but only 10 order phases. The
    capped rate is 1.0 (not 5.0). Without the cap, a single bad
    phase would dominate fitness and make the GA never schedule it."""
    errors = [SimpleNamespace(fase_id="LIX_AGUA") for _ in range(50)]
    phases = [SimpleNamespace(fase_id="LIX_AGUA") for _ in range(10)]
    rates = _extract_error_rates(_engine(errors=errors, order_phases=phases))
    assert rates == {"LIX_AGUA": 1.0}


def test_phase_with_zero_order_phases_does_not_appear_in_rates():
    """Errors logged against a phase that never ran an order MUST NOT
    create a divide-by-zero or a 'rate=infinity' row. They're silently
    dropped from the rates output (the caller can detect by absence)."""
    errors = [SimpleNamespace(fase_id="GHOST_PHASE")]
    phases = [SimpleNamespace(fase_id="LAMINAGEM")]
    rates = _extract_error_rates(_engine(errors=errors, order_phases=phases))
    assert "GHOST_PHASE" not in rates
    assert "LAMINAGEM" in rates  # 0 errors / 1 phase = 0.0
    assert rates["LAMINAGEM"] == 0.0


def test_well_formed_rate_is_exact_division():
    """Plan v4 §3.3 — Lixagem água historical = 49.2% rework.
    Inputs of (49 errors, 100 phases) → 0.49."""
    errors = [SimpleNamespace(fase_id="LIX_AGUA") for _ in range(49)]
    phases = [SimpleNamespace(fase_id="LIX_AGUA") for _ in range(100)]
    rates = _extract_error_rates(_engine(errors=errors, order_phases=phases))
    assert rates["LIX_AGUA"] == pytest.approx(0.49)


def test_blank_fase_id_silently_dropped():
    """A row with `fase_id=""` is dirty data. Dropping it is safer than
    creating a `rates[""]` entry that no consumer can act on."""
    errors = [
        SimpleNamespace(fase_id="LAMINAGEM"),
        SimpleNamespace(fase_id=""),  # dirty
    ]
    phases = [
        SimpleNamespace(fase_id="LAMINAGEM"),
        SimpleNamespace(fase_id=""),  # dirty
    ]
    rates = _extract_error_rates(_engine(errors=errors, order_phases=phases))
    assert "" not in rates
    assert "LAMINAGEM" in rates


def test_empty_input_yields_empty_output():
    """No data → empty dict. The CPO uses absence as 'no signal yet'
    and falls back to default capacity factor 1.0; an empty {} preserves
    that semantics. A mistakenly-emitted `{phase: 0.0}` for every phase
    in the catalogue would falsely tell the GA "no rework anywhere"."""
    rates = _extract_error_rates(_engine(errors=[], order_phases=[]))
    assert rates == {}


def test_extraction_robust_to_engine_without_curated_data():
    """Sometimes the engine arg has no `_curated_data` attribute (very
    early bootstrap, smoke tests). The extractor must NOT raise — it
    returns {} so callers continue cleanly."""
    bare_engine = SimpleNamespace()
    assert _extract_error_rates(bare_engine) == {}


def test_rates_aggregate_across_three_high_rework_phases_per_plan_v4():
    """Plan v4 §3.3 ground truth: three phases run at 40-50% rework
    (Lixagem água, Pintura Acab, Lixagem polim). The extractor
    surfaces each rate independently — the GA uses these to decide
    whether to apply the 1.5× capacity factor (E.1)."""
    errors = (
        [SimpleNamespace(fase_id="LIX_AGUA")] * 49
        + [SimpleNamespace(fase_id="PINTURA_ACAB")] * 42
        + [SimpleNamespace(fase_id="LIX_POLIM")] * 41
        + [SimpleNamespace(fase_id="LAMINAGEM")] * 5
    )
    phases = (
        [SimpleNamespace(fase_id="LIX_AGUA")] * 100
        + [SimpleNamespace(fase_id="PINTURA_ACAB")] * 100
        + [SimpleNamespace(fase_id="LIX_POLIM")] * 100
        + [SimpleNamespace(fase_id="LAMINAGEM")] * 100
    )
    rates = _extract_error_rates(_engine(errors=errors, order_phases=phases))
    assert rates["LIX_AGUA"] == pytest.approx(0.49)
    assert rates["PINTURA_ACAB"] == pytest.approx(0.42)
    assert rates["LIX_POLIM"] == pytest.approx(0.41)
    assert rates["LAMINAGEM"] == pytest.approx(0.05)
    # All three high-rework phases breach the E.1 threshold (0.40).
    assert all(rates[p] >= 0.40 for p in ("LIX_AGUA", "PINTURA_ACAB", "LIX_POLIM"))
    assert rates["LAMINAGEM"] < 0.40  # baseline phase below threshold
