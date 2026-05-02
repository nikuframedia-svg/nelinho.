"""
Sprint R — quality + rework + mold tests.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from src.core.services.tenant_config_service import _reset_cache_for_tests
from src.plan.cpo.decoder import (
    REWORK_BUFFER_PHASE_KEYWORDS,
    classify_rework_phase,
)
from src.plan.models.mold import (
    Mold,
    MoldDefectLog,
    MoldHealth,
    MoldMaintenanceEvent,
    MoldUsageCounter,
)
from src.plan.services.mold_health_calculator import (
    DEFAULT_THRESHOLDS,
    DEFAULT_WEIGHTS,
    HealthComponents,
    MoldHealthCalculator,
    _risk_from_score,
)
from src.plan.services.mold_service import (
    CODE_MOLD_MAINT_DUE,
    MoldService,
)
from src.quality.models.rework import ErrorCatalog, ReworkEntry
from src.quality.services.dashboard_service import (
    VALID_GROUP_BY,
    QualityDashboardService,
)
from src.quality.services.impact_service import ImpactService
from src.quality.services.rework_service import (
    AUTO_ROUTE_CAUSER_PHASE_KEYWORDS,
    ErrorCatalogService,
    ReworkService,
)
from src.quality.services.root_cause_analyzer import (
    CANDIDATE_DIMENSIONS,
    RootCauseAnalyzer,
    _rank_counts,
    _signal,
)
from src.quality.services.supplier_quality_service import SupplierQualityService
from src.quality.services.worker_ranking_service import WorkerRankingService
from tests.conftest import TEST_TENANT_ID


@pytest.fixture(autouse=True)
def _stub_publish(monkeypatch):
    async def fake(_t, _e):
        return True

    monkeypatch.setattr(
        "src.shared.kafka_client.publish_event", fake, raising=True,
    )


@pytest.fixture(autouse=True)
def _clear_cache():
    _reset_cache_for_tests()


def _queue(session, *, scalar=None, scalars=None):
    session.queue_scalar(scalar)
    session.queue_scalars(scalars if scalars is not None else [])


# ---------------------------------------------------------------------------
# R.1 — ReworkService / ErrorCatalog
# ---------------------------------------------------------------------------

def test_auto_route_causer_keyword_matches_pintura():
    # QA02 — Pintura goes back to causer.
    assert ReworkService.should_route_to_causer("Pintura Acabamento") is True
    assert ReworkService.should_route_to_causer("pintura") is True
    assert ReworkService.should_route_to_causer("Laminagem") is False
    assert ReworkService.should_route_to_causer(None) is False


def test_auto_route_keywords_set_non_empty():
    assert len(AUTO_ROUTE_CAUSER_PHASE_KEYWORDS) > 0


@pytest.mark.asyncio
async def test_record_rework_persists_row(fake_session):
    svc = ReworkService(fake_session, TEST_TENANT_ID)
    row = await svc.record(
        of_id="OF-1",
        error_code="MOLDE_BACO",
        detected_at=datetime.now(timezone.utc),
        causer_employee_id=uuid4(),
        phase_id_rework="Pintura",
        cost_estimate_eur=Decimal("25"),
    )
    assert row in fake_session.added
    assert row.error_code == "MOLDE_BACO"


@pytest.mark.asyncio
async def test_error_catalog_upsert_new(fake_session):
    _queue(fake_session, scalar=None)
    svc = ErrorCatalogService(fake_session, TEST_TENANT_ID)
    row = await svc.upsert(
        error_code="MOLDE_BACO",
        name="Molde baço",
        mold_related=True,
    )
    assert row in fake_session.added
    assert row.mold_related is True


# ---------------------------------------------------------------------------
# R.3 — Worker ranking
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_worker_ranking_sorts_by_error_count(fake_session):
    eid_a, eid_b = uuid4(), uuid4()
    _queue(fake_session, scalars=[
        (eid_a, 7),
        (eid_b, 3),
    ])
    svc = WorkerRankingService(fake_session, TEST_TENANT_ID)
    items = await svc.ranking()
    assert [i["employee_id"] for i in items] == [str(eid_a), str(eid_b)]
    assert items[0]["share_pct"] == 70.0  # 7 / 10


@pytest.mark.asyncio
async def test_worker_ranking_skips_null_causer(fake_session):
    _queue(fake_session, scalars=[(None, 5)])
    svc = WorkerRankingService(fake_session, TEST_TENANT_ID)
    items = await svc.ranking()
    assert items == []


# ---------------------------------------------------------------------------
# R.4 — Dashboard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dashboard_rejects_unknown_group_by(fake_session):
    svc = QualityDashboardService(fake_session, TEST_TENANT_ID)
    with pytest.raises(ValueError):
        await svc.group_by(group_by="continent")


def test_dashboard_valid_group_by_covers_blueprint_dims():
    assert {"operator", "phase", "sku", "shift"} == VALID_GROUP_BY


@pytest.mark.asyncio
async def test_dashboard_group_by_phase(fake_session):
    _queue(fake_session, scalars=[
        (5, "Laminagem"),
        (2, "Pintura"),
    ])
    svc = QualityDashboardService(fake_session, TEST_TENANT_ID)
    out = await svc.group_by(group_by="phase")
    assert out["total_events"] == 7
    assert out["items"][0]["key"] == "Laminagem"


# ---------------------------------------------------------------------------
# R.5 — Root-cause analyser
# ---------------------------------------------------------------------------

def test_rank_counts_marks_dominant_as_strong_positive():
    from collections import Counter

    counter = Counter({"A": 90, "B": 5, "C": 5})
    ranked = _rank_counts(counter, total=100, top_n=3)
    assert ranked[0]["value"] == "A"
    assert ranked[0]["signal"] in {"strong_positive", "positive"}


def test_signal_thresholds():
    assert _signal(3.0) == "strong_positive"
    assert _signal(2.0) == "positive"
    assert _signal(0.0) == "neutral"
    assert _signal(-3.0) == "strong_negative"


def test_candidate_dimensions_cover_blueprint_signals():
    # Blueprint QA09 suggests erro × trabalhador × modelo × turno.
    expected = {"causer_employee_id", "model_id"}
    assert expected <= set(CANDIDATE_DIMENSIONS)


@pytest.mark.asyncio
async def test_root_cause_empty_window(fake_session):
    _queue(fake_session, scalars=[])
    svc = RootCauseAnalyzer(fake_session, TEST_TENANT_ID)
    out = await svc.analyse(error_code="MOLDE_BACO")
    assert out["total_events"] == 0
    assert out["dimensions"] == {}


# ---------------------------------------------------------------------------
# R.7 — Impact service
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_impact_by_error_aggregates(fake_session):
    # 1. the main aggregate query
    fake_session.queue_scalar(None)

    class _Row(tuple):
        def one(self):
            return self

    # The FakeSession.execute returns _FakeResult; we need `.one()` to return
    # a tuple of (count, cost_sum, hours_sum, distinct_of_ids).
    # Rather than extend the FakeSession, stub via queue_scalars handling:
    # we monkey-patch the first execute call below.
    captured: list = []

    async def _mock_execute(stmt):
        captured.append(stmt)
        if len(captured) == 1:
            # impact query
            class _Res:
                def one(self):
                    return (10, Decimal("500"), Decimal("20"), 4)

                def scalar_one_or_none(self):
                    return None
            return _Res()
        # total_all query
        class _Res2:
            def scalar_one_or_none(self):
                return 40
        return _Res2()

    fake_session.execute = _mock_execute  # type: ignore
    svc = ImpactService(fake_session, TEST_TENANT_ID)
    out = await svc.impact_by_error(error_code="X")
    assert out["events"] == 10
    assert out["share_pct_of_total_rework"] == 25.0  # 10 / 40


# ---------------------------------------------------------------------------
# R.8 — Supplier quality
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_supplier_quality_ranks_by_events(fake_session):
    supplier_a, supplier_b = uuid4(), uuid4()
    _queue(fake_session, scalars=[
        (supplier_a, 15, Decimal("300")),
        (supplier_b, 5, Decimal("50")),
    ])
    svc = SupplierQualityService(fake_session, TEST_TENANT_ID)
    items = await svc.by_supplier()
    assert items[0]["supplier_id"] == str(supplier_a)
    assert items[0]["events"] == 15


@pytest.mark.asyncio
async def test_supplier_quality_by_lot(fake_session):
    _queue(fake_session, scalars=[("LOT-A", 5), ("LOT-B", 2)])
    svc = SupplierQualityService(fake_session, TEST_TENANT_ID)
    items = await svc.by_lot()
    assert items[0]["material_lot_id"] == "LOT-A"


# ---------------------------------------------------------------------------
# R.6.2 — Mold health calculator
# ---------------------------------------------------------------------------

def test_risk_from_score_thresholds():
    th = {"red": 40, "yellow": 70}
    assert _risk_from_score(20, th) == "red"
    assert _risk_from_score(50, th) == "yellow"
    assert _risk_from_score(90, th) == "green"
    # Exactly at boundary: < red → red. At red → yellow (score==threshold = yellow).
    assert _risk_from_score(40, th) == "yellow"


def test_default_weights_sum_to_one():
    total = sum(DEFAULT_WEIGHTS.values())
    assert abs(total - 1.0) < 1e-6


def test_health_components_serialisation():
    c = HealthComponents(
        cycles_pct=0.8, defect_penalty=0.2,
        maint_age_pct=0.3, rework_rate=0.0,
    )
    d = c.as_dict()
    assert d["cycles_pct"] == 0.8


@pytest.mark.asyncio
async def test_mold_health_calculator_new_mold_returns_baseline(fake_session):
    mold = Mold(
        id=uuid4(),
        tenant_id=TEST_TENANT_ID,
        mold_code="M-1",
        model_id="MDL-X",
        pocket_count=1,
        expected_life_cycles=100,
        active=True,
    )
    # Config load — empty
    _queue(fake_session, scalars=[])
    # _cycles_pct: counter lookup → None (new mould)
    _queue(fake_session, scalar=None)
    # _defect_penalty: no defects
    _queue(fake_session, scalars=[])
    # _maint_age_pct: never maintained → 0.5 penalty
    _queue(fake_session, scalar=None)
    # _rework_rate: no rework entries
    _queue(fake_session, scalar=0)

    calc = MoldHealthCalculator(fake_session, TEST_TENANT_ID)
    result = await calc.compute(mold)
    # Only maint_age contributes 0.5 → penalty 0.5 * 0.2 = 0.1 → score 90.
    assert result.score_0_100 == 90
    assert result.risk_category == "green"


# ---------------------------------------------------------------------------
# R.6.3 — Mold service create / cycle tracking
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mold_service_create_seeds_counter(fake_session):
    _queue(fake_session, scalar=None)  # _find_by_code returns None
    svc = MoldService(fake_session, TEST_TENANT_ID)
    mold = await svc.create_mold(
        mold_code="M-NEW", model_id="MDL",
        pocket_count=2, expected_life_cycles=500,
    )
    assert mold in fake_session.added
    # Also a MoldUsageCounter for the same mold.
    counters = [a for a in fake_session.added if isinstance(a, MoldUsageCounter)]
    assert len(counters) == 1
    assert counters[0].mold_id == mold.id


@pytest.mark.asyncio
async def test_mold_service_increment_cycle_creates_counter_if_missing(fake_session):
    _queue(fake_session, scalar=None)
    svc = MoldService(fake_session, TEST_TENANT_ID)
    mold_id = uuid4()
    counter = await svc.increment_cycle(mold_id=mold_id, amount=5)
    assert counter.shot_count_total == 5
    assert counter.cycles_since_last_maint == 5
    assert counter in fake_session.added


# ---------------------------------------------------------------------------
# Sprint A Day 5 — MOLD_MAINT_DUE disabled when threshold ≤ 0 (H2 placeholder)
# ---------------------------------------------------------------------------

def test_default_maint_threshold_is_zero_after_q8_ceo_confirmation():
    """Sprint Q.8 (CEO confirmation 2026-04-26): NELO has no numeric
    maintenance policy — molds go to maintenance after visual inspection.
    The default `DEFAULT_MAINT_THRESHOLD_CYCLES` is therefore 0 so the
    auto-alert stays off out of the box; tenants opt in by setting a
    positive integer in `mold.maintenance_threshold_cycles`."""
    from src.plan.services.mold_service import DEFAULT_MAINT_THRESHOLD_CYCLES

    assert DEFAULT_MAINT_THRESHOLD_CYCLES == 0


@pytest.mark.asyncio
async def test_emit_maintenance_alerts_skipped_when_threshold_is_zero(
    fake_session, monkeypatch,
):
    """A threshold of 0 disables the MOLD_MAINT_DUE alert entirely —
    the NELO ERP lacks maintenance data, so until the CEO confirms H2
    the operator can silence the alert without affecting mold health.
    """
    # Intercept the config read to return 0 deterministically.
    from src.core.services import tenant_config_service

    async def _get(self, *a, **kw):
        return 0

    monkeypatch.setattr(tenant_config_service.TenantConfigService, "get", _get)

    svc = MoldService(fake_session, TEST_TENANT_ID)
    created = await svc.emit_maintenance_alerts()
    assert created == 0
    # When disabled, the service must short-circuit before querying molds.
    assert fake_session._scalars_queue == []
    # And must never add any alert to the session.
    from src.copilot.alerts.models import CopilotAlert

    assert not any(isinstance(a, CopilotAlert) for a in fake_session.added)


@pytest.mark.asyncio
async def test_emit_maintenance_alerts_skipped_when_threshold_is_negative(
    fake_session, monkeypatch,
):
    """Negative thresholds also disable — any "sentinel-off" value works."""
    from src.core.services import tenant_config_service

    async def _get(self, *a, **kw):
        return -1

    monkeypatch.setattr(tenant_config_service.TenantConfigService, "get", _get)

    svc = MoldService(fake_session, TEST_TENANT_ID)
    created = await svc.emit_maintenance_alerts()
    assert created == 0


# ---------------------------------------------------------------------------
# R.9 — Decoder rework-buffer classifier
# ---------------------------------------------------------------------------

def test_classify_rework_phase_detects_sanding_water():
    assert classify_rework_phase("Lixagem água", None) == "sanding_water"
    assert classify_rework_phase("Lixagem agua", None) == "sanding_water"


def test_classify_rework_phase_detects_sanding_polish():
    assert classify_rework_phase("Lixagem polimento", None) == "sanding_polish"


def test_classify_rework_phase_detects_painting_finishing():
    assert classify_rework_phase("Pintura Acabamento", None) == "painting_finishing"


def test_classify_rework_phase_unknown_returns_none():
    assert classify_rework_phase("Corte", None) is None


def test_rework_buffer_keywords_registered_for_three_buckets():
    assert set(REWORK_BUFFER_PHASE_KEYWORDS) == {
        "sanding_water", "sanding_polish", "painting_finishing",
    }


# ---------------------------------------------------------------------------
# Model round-trips — make sure the ORM classes construct correctly
# ---------------------------------------------------------------------------

def test_rework_entry_roundtrip():
    row = ReworkEntry(
        id=uuid4(),
        tenant_id=TEST_TENANT_ID,
        of_id="OF-1",
        error_code="X",
        detected_at=datetime.now(timezone.utc),
        context={},
    )
    assert row.error_code == "X"


def test_error_catalog_default_severity():
    row = ErrorCatalog(
        id=uuid4(),
        tenant_id=TEST_TENANT_ID,
        error_code="X",
        name="n",
    )
    assert row.severity_hint in {None, "medium"}
