"""Sprint Q.54.F — tests for the shared CPO ML wiring chokepoint.

`src/plan/cpo/ml_wiring.py:apply_ml_to_cpo` is the single place that
loads the active DurationModel + QualityRiskModel from the registry and
attaches them to the CPO inputs. Both `/v1/plan/cpo/schedule` and the
copilot's POETIQ path go through it, so the two planners wire identically.

These tests pin two things:
  * honest fallback — no active model → predictors are None, the
    fitness config is untouched, nothing raises;
  * wiring — when the registry hands back predictors, they land on the
    fitness config and the report flags them.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from src.plan.cpo.fitness import FitnessConfig
from src.plan.cpo.ml_wiring import MLWiringReport, apply_ml_to_cpo


TENANT = UUID("00000000-0000-0000-0000-000000000001")


class _StubRegistry:
    """Stands in for ModelRegistry — get_active returns None for every
    model unless preconfigured."""

    def __init__(self, session, tenant_id, **_kw):
        self._active = _StubRegistry.active_map

    active_map: dict = {}

    async def get_active(self, model_name):
        return self._active.get(model_name)

    def load(self, storage_uri):
        return self._active_obj.get(storage_uri)


@pytest.mark.asyncio
async def test_no_active_models_is_honest_fallback(monkeypatch):
    """Fresh tenant — no model ever trained. apply_ml_to_cpo must return
    (None, report-with-both-False) and leave the fitness config alone."""
    import src.ml.registry_loader as rl

    monkeypatch.setattr(rl, "ModelRegistry", _StubRegistry)
    _StubRegistry.active_map = {}

    fc = FitnessConfig()
    assert fc.quality_risk_predictor is None

    duration_predictor, report = await apply_ml_to_cpo(
        session=object(), tenant_id=TENANT, fitness_config=fc,
    )

    assert duration_predictor is None
    assert isinstance(report, MLWiringReport)
    assert report.duration_model_used is False
    assert report.quality_risk_predictor_used is False
    # Fitness config untouched — silent fallback by design.
    assert fc.quality_risk_predictor is None


@pytest.mark.asyncio
async def test_report_as_meta_shape():
    """The report serialises to the exact cpo_meta key shape the API
    and E2E asserts expect."""
    report = MLWiringReport(
        duration_model_used=True, quality_risk_predictor_used=False,
    )
    meta = report.as_meta()
    assert meta == {
        "duration_model_used": True,
        "quality_risk_predictor_used": False,
    }


@pytest.mark.asyncio
async def test_quality_risk_predictor_wired_when_active(monkeypatch):
    """When the registry has an active QualityRiskModel, apply_ml_to_cpo
    must attach its predict_proba_batch to the fitness config and flag
    it on the report."""
    import src.ml.registry_loader as rl

    class _FakeQRModel:
        def predict_proba_batch(self, rows):
            return [0.1 for _ in rows]

    class _Artifact:
        version = 3
        storage_uri = "file:///tmp/qr"

    class _Registry:
        def __init__(self, session, tenant_id, **_kw):
            pass

        async def get_active(self, model_name):
            return _Artifact() if model_name == "quality_risk" else None

        def load(self, storage_uri):
            return _FakeQRModel()

    monkeypatch.setattr(rl, "ModelRegistry", _Registry)

    fc = FitnessConfig()
    duration_predictor, report = await apply_ml_to_cpo(
        session=object(), tenant_id=TENANT, fitness_config=fc,
    )

    assert duration_predictor is None  # no duration artifact
    assert report.quality_risk_predictor_used is True
    assert fc.quality_risk_predictor is not None
    # The wired predictor actually works.
    assert fc.quality_risk_predictor([{"x": 1}, {"x": 2}]) == [0.1, 0.1]


# ─── Property test — ML wiring preserves the Spelke axioms ──────────
#
# Axioms 1-6 are enforced by the decoder, which never receives the ML
# predictors — the DurationModel only feeds the RoutingResolver's phase
# durations and the QualityRiskModel only feeds the fitness scalar.
# Neither can move an op in time, double-book a worker or a mould, or
# skip a curing gap. The property we DO need to pin is on the fitness
# side: wiring a quality-risk predictor must only ADD a non-negative
# penalty (the 0.10-weighted mean P(error) term) — it can never make a
# schedule look *better* than it would with no predictor, and it must
# never raise. If it could lower fitness, the GA would chase phantom
# gains and axiom 7's safety net would compare against a corrupt
# baseline.

from hypothesis import HealthCheck, given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from src.plan.cpo.fitness import compute_fitness  # noqa: E402


@st.composite
def _schedule_with_ops(draw):
    """A minimal schedule dict with the KPI keys fitness reads plus a
    handful of ops carrying phase_id/model_id (the quality-risk feature
    projector needs them)."""
    n_ops = draw(st.integers(min_value=0, max_value=8))
    ops = []
    for i in range(n_ops):
        ops.append({
            "id": f"op-{i}",
            "phase_id": draw(st.sampled_from(["LAMINAGEM", "PINTURA", "CURA"])),
            "model_id": draw(st.sampled_from(["K1", "K2", "K4"])),
            "workers": [f"w-{i}"],
            "duration_minutes": draw(st.integers(min_value=15, max_value=480)),
        })
    return {
        "operations": ops,
        "makespan_hours": draw(st.floats(min_value=0.0, max_value=400.0,
                                         allow_nan=False)),
        "total_tardiness_hours": draw(st.floats(min_value=0.0, max_value=200.0,
                                                allow_nan=False)),
        "setups": draw(st.integers(min_value=0, max_value=40)),
        "quality_risk": 0.0,
    }


@settings(deadline=None, max_examples=200,
          suppress_health_check=[HealthCheck.too_slow])
@given(schedule=_schedule_with_ops(),
       risk=st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
def test_axiom7_quality_risk_predictor_only_adds_penalty(schedule, risk):
    """Wiring a quality-risk predictor must never LOWER fitness vs the
    same schedule with no predictor. The risk term is a non-negative
    penalty — if it could be negative the GA + safety net would be
    optimising against a corrupt baseline."""
    no_ml = FitnessConfig()
    with_ml = FitnessConfig(quality_risk_predictor=lambda rows: [risk] * len(rows))

    fit_without = compute_fitness(schedule, no_ml)
    fit_with = compute_fitness(schedule, with_ml)

    # Predictor only adds w_quality_risk * mean_risk (+ hard penalty).
    # Both terms are ≥ 0, so fitness can only stay equal or rise.
    assert fit_with >= fit_without - 1e-6


@settings(deadline=None, max_examples=150,
          suppress_health_check=[HealthCheck.too_slow])
@given(schedule=_schedule_with_ops())
def test_axiom7_broken_predictor_never_crashes_fitness(schedule):
    """A predictor that raises must NOT take the GA down — fitness falls
    back to the zero-risk path. (Defence in depth: a buggy ML artifact
    can't brick scheduling.)"""
    def _broken(rows):
        raise RuntimeError("ml artifact corrupt")

    cfg = FitnessConfig(quality_risk_predictor=_broken)
    # Must not raise — _predict_risks_safe swallows and logs.
    fit = compute_fitness(schedule, cfg)
    assert isinstance(fit, float)


@pytest.mark.asyncio
async def test_registry_outage_does_not_raise(monkeypatch):
    """A registry that throws on get_active must not crash scheduling —
    apply_ml_to_cpo swallows it and returns the honest no-ML fallback."""
    import src.ml.registry_loader as rl

    class _BrokenRegistry:
        def __init__(self, session, tenant_id, **_kw):
            pass

        async def get_active(self, model_name):
            raise RuntimeError("registry DB down")

    monkeypatch.setattr(rl, "ModelRegistry", _BrokenRegistry)

    fc = FitnessConfig()
    duration_predictor, report = await apply_ml_to_cpo(
        session=object(), tenant_id=TENANT, fitness_config=fc,
    )
    assert duration_predictor is None
    assert report.duration_model_used is False
    assert report.quality_risk_predictor_used is False
    assert fc.quality_risk_predictor is None
