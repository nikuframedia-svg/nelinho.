"""
Tests for ShortageDetector (Sprint O.4).

Tiny scope: validate code selection (WARN vs CRITICAL) and dedup skip.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from src.copilot.alerts.models import (
    CODE_MATERIAL_SHORTAGE_PROJECTED,
    CODE_MATERIAL_STOCKOUT_IMMINENT,
    CopilotAlert,
    STATUS_ACTIVE,
)
from src.core.services.tenant_config_service import _reset_cache_for_tests
from src.supply.models import MaterialMaster
from src.supply.shortage_detector import ShortageDetector
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


def _material(
    *,
    sku_id: str = "SKU-A",
    min_stock: Decimal = Decimal("100"),
    critical: bool = False,
    lead_time_days: int = 7,
) -> MaterialMaster:
    return MaterialMaster(
        id=uuid4(),
        tenant_id=TEST_TENANT_ID,
        sku_id=sku_id,
        name="mat",
        unit_of_measure="UN",
        lead_time_days=lead_time_days,
        min_stock_qty=min_stock,
        reorder_qty=Decimal("100"),
        safety_stock_days=0,
        critical_flag=critical,
        active=True,
    )


# ---------------------------------------------------------------------------
# Scan runs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scan_emits_warn_when_projected_under_min(fake_session):
    # 1. critical_days config load
    _queue(fake_session, scalars=[])
    # 2. list active MaterialMaster rows
    mat = _material(sku_id="SKU-A", min_stock=Decimal("100"))
    _queue(fake_session, scalars=[mat])
    # 3. get_position sequence for SKU-A:
    #    _find_material
    _queue(fake_session, scalar=mat)
    #    get_current_on_hand
    _queue(fake_session, scalar=Decimal("20"))
    #    in_transit query
    _queue(fake_session, scalars=[])
    #    ROPConfig query → None (no avg daily demand → days_to_stockout=None)
    _queue(fake_session, scalar=None)
    #    safety_multiplier config load
    _queue(fake_session, scalars=[])
    # 4. _duplicate check → None (no prior alert)
    _queue(fake_session, scalar=None)

    detector = ShortageDetector(fake_session, TEST_TENANT_ID)
    summary = await detector.scan()
    assert summary["warn_created"] == 1
    assert summary["critical_created"] == 0
    # One CopilotAlert added
    alerts = [a for a in fake_session.added if isinstance(a, CopilotAlert)]
    assert len(alerts) == 1
    assert alerts[0].code == CODE_MATERIAL_SHORTAGE_PROJECTED
    assert alerts[0].severity == "WARN"
    assert alerts[0].entity_refs == ["material:SKU-A"]


@pytest.mark.asyncio
async def test_scan_emits_critical_when_material_is_flagged(fake_session):
    _queue(fake_session, scalars=[])
    mat = _material(sku_id="SKU-B", min_stock=Decimal("50"), critical=True)
    _queue(fake_session, scalars=[mat])
    _queue(fake_session, scalar=mat)
    _queue(fake_session, scalar=Decimal("10"))
    _queue(fake_session, scalars=[])
    _queue(fake_session, scalar=None)
    _queue(fake_session, scalars=[])
    _queue(fake_session, scalar=None)

    detector = ShortageDetector(fake_session, TEST_TENANT_ID)
    summary = await detector.scan()
    assert summary["critical_created"] == 1
    assert summary["warn_created"] == 0
    alerts = [a for a in fake_session.added if isinstance(a, CopilotAlert)]
    assert alerts[0].code == CODE_MATERIAL_STOCKOUT_IMMINENT
    assert alerts[0].severity == "CRITICAL"


@pytest.mark.asyncio
async def test_scan_skips_duplicate(fake_session):
    # Queue layout: load_thresholds + list_materials + (5× get_position) +
    # _duplicate. The safety_multiplier lookup inside get_position hits the
    # TenantConfig cache populated by load_thresholds so it does NOT execute
    # — that's why there are 7 queue entries, not 8.
    _queue(fake_session, scalars=[])            # load_thresholds cfg
    mat = _material(sku_id="SKU-C", min_stock=Decimal("100"))
    _queue(fake_session, scalars=[mat])          # list_materials
    _queue(fake_session, scalar=mat)             # get_position._find_material
    _queue(fake_session, scalar=Decimal("10"))   # on_hand
    _queue(fake_session, scalars=[])             # transit
    _queue(fake_session, scalar=None)            # rop
    _queue(fake_session, scalar=uuid4())         # _duplicate — existing alert

    detector = ShortageDetector(fake_session, TEST_TENANT_ID)
    summary = await detector.scan()
    assert summary["skipped_duplicate"] == 1
    assert summary["warn_created"] == 0


@pytest.mark.asyncio
async def test_scan_no_materials_returns_zero(fake_session):
    _queue(fake_session, scalars=[])  # critical_days cfg
    _queue(fake_session, scalars=[])  # no materials
    detector = ShortageDetector(fake_session, TEST_TENANT_ID)
    summary = await detector.scan()
    assert summary == {
        "materials_scanned": 0,
        "warn_created": 0,
        "critical_created": 0,
        "skipped_duplicate": 0,
    }


@pytest.mark.asyncio
async def test_scan_skips_material_above_min(fake_session):
    _queue(fake_session, scalars=[])
    mat = _material(sku_id="SKU-D", min_stock=Decimal("50"))
    _queue(fake_session, scalars=[mat])
    _queue(fake_session, scalar=mat)
    _queue(fake_session, scalar=Decimal("200"))  # well above min
    _queue(fake_session, scalars=[])
    _queue(fake_session, scalar=None)
    _queue(fake_session, scalars=[])

    detector = ShortageDetector(fake_session, TEST_TENANT_ID)
    summary = await detector.scan()
    assert summary["warn_created"] == 0
    assert summary["critical_created"] == 0
    assert not any(isinstance(a, CopilotAlert) for a in fake_session.added)
