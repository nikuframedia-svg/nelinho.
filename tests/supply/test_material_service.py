"""
Tests for MaterialService (Sprint O.1-O.7).

All DB reads mocked via `FakeSession`. The legacy `InventoryLedger`
(already tested indirectly elsewhere) is exercised through the service;
we just queue the scalars it reads.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.supply.material_service import (
    MaterialNotFoundError,
    MaterialService,
    NegativeStockBlockedError,
)
from src.supply.models import (
    InventoryLedgerEntry,
    MaterialInTransit,
    MaterialMaster,
    ROPConfig,
    StockReconciliation,
)
from src.core.services.tenant_config_service import _reset_cache_for_tests
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
    min_stock: Decimal = Decimal("10"),
    critical: bool = False,
    lead_time_days: int = 7,
) -> MaterialMaster:
    return MaterialMaster(
        id=uuid4(),
        tenant_id=TEST_TENANT_ID,
        sku_id=sku_id,
        name=f"Mat {sku_id}",
        unit_of_measure="UN",
        category=None,
        default_supplier_id=None,
        lead_time_days=lead_time_days,
        min_stock_qty=min_stock,
        reorder_qty=Decimal("100"),
        safety_stock_days=0,
        critical_flag=critical,
        active=True,
    )


def _ledger_entry(*, sku_id: str, qty_closing: Decimal) -> InventoryLedgerEntry:
    return InventoryLedgerEntry(
        id=uuid4(),
        tenant_id=TEST_TENANT_ID,
        sku_id=sku_id,
        date=datetime.now(timezone.utc),
        qty_opening=Decimal("0"),
        qty_in=Decimal("0"),
        qty_out=Decimal("0"),
        qty_closing=qty_closing,
        transaction_type="adjust",
        reference_id=None,
    )


# ---------------------------------------------------------------------------
# create_material / update_min_stock
# ---------------------------------------------------------------------------

class TestMaterialMaster:
    @pytest.mark.asyncio
    async def test_create_material_happy_path(self, fake_session):
        # _find_material returns None on duplicate check
        _queue(fake_session, scalar=None)
        svc = MaterialService(fake_session, TEST_TENANT_ID)
        row = await svc.create_material(
            sku_id="SKU-NEW", name="Carbon Fibre",
            min_stock_qty=Decimal("50"),
        )
        assert row.sku_id == "SKU-NEW"
        assert row.min_stock_qty == Decimal("50")
        assert row in fake_session.added

    @pytest.mark.asyncio
    async def test_create_material_rejects_duplicate(self, fake_session):
        _queue(fake_session, scalar=_material(sku_id="SKU-A"))
        svc = MaterialService(fake_session, TEST_TENANT_ID)
        with pytest.raises(ValueError):
            await svc.create_material(sku_id="SKU-A", name="dup")

    @pytest.mark.asyncio
    async def test_update_min_stock_rejects_negative(self, fake_session):
        svc = MaterialService(fake_session, TEST_TENANT_ID)
        with pytest.raises(ValueError):
            await svc.update_min_stock(sku_id="SKU-A", min_stock_qty=Decimal("-1"))

    @pytest.mark.asyncio
    async def test_update_min_stock_material_not_found(self, fake_session):
        _queue(fake_session, scalar=None)
        svc = MaterialService(fake_session, TEST_TENANT_ID)
        with pytest.raises(MaterialNotFoundError):
            await svc.update_min_stock(sku_id="SKU-X", min_stock_qty=Decimal("10"))

    @pytest.mark.asyncio
    async def test_update_min_stock_happy_path(self, fake_session):
        existing = _material(sku_id="SKU-A", min_stock=Decimal("10"))
        _queue(fake_session, scalar=existing)
        svc = MaterialService(fake_session, TEST_TENANT_ID)
        row = await svc.update_min_stock(sku_id="SKU-A", min_stock_qty=Decimal("25"))
        assert row.min_stock_qty == Decimal("25")


# ---------------------------------------------------------------------------
# get_position
# ---------------------------------------------------------------------------

class TestGetPosition:
    @pytest.mark.asyncio
    async def test_below_min_when_projected_under_threshold(self, fake_session):
        # MaterialService._find_material (execute #1)
        _queue(fake_session, scalar=_material(sku_id="SKU-A", min_stock=Decimal("100")))
        # InventoryLedger.get_current_on_hand (execute #2)
        _queue(fake_session, scalar=Decimal("20"))
        # in_transit rows (execute #3) — one PO arriving tomorrow
        transit = MaterialInTransit(
            id=uuid4(), tenant_id=TEST_TENANT_ID,
            sku_id="SKU-A", purchase_order_id=uuid4(),
            qty=Decimal("30"), eta=date.today() + timedelta(days=1),
            supplier_id=None, status="OPEN",
        )
        _queue(fake_session, scalars=[transit])
        # ROPConfig (execute #4) — none
        _queue(fake_session, scalar=None)
        # safety_multiplier config (execute #5) — empty → default 1.0
        _queue(fake_session, scalars=[])

        svc = MaterialService(fake_session, TEST_TENANT_ID)
        result = await svc.get_position(sku_id="SKU-A")
        assert result["on_hand"] == 20.0
        assert result["in_transit"]["qty"] == 30.0
        assert result["projected_stock_horizon"] == 50.0
        assert result["min_stock"] == 100.0
        assert result["below_min"] is True

    @pytest.mark.asyncio
    async def test_not_critical_unless_flag_and_below_min(self, fake_session):
        _queue(fake_session, scalar=_material(sku_id="SKU-A", critical=True,
                                              min_stock=Decimal("100")))
        _queue(fake_session, scalar=Decimal("200"))  # on_hand well above
        _queue(fake_session, scalars=[])             # no transit
        _queue(fake_session, scalar=None)            # no ROP
        _queue(fake_session, scalars=[])             # cfg empty

        svc = MaterialService(fake_session, TEST_TENANT_ID)
        result = await svc.get_position(sku_id="SKU-A")
        assert result["below_min"] is False
        assert result["critical"] is False

    @pytest.mark.asyncio
    async def test_missing_material_returns_stub(self, fake_session):
        _queue(fake_session, scalar=None)            # _find_material
        _queue(fake_session, scalar=Decimal("0"))    # on_hand
        _queue(fake_session, scalars=[])             # transit
        _queue(fake_session, scalar=None)            # ROP
        _queue(fake_session, scalars=[])             # cfg
        svc = MaterialService(fake_session, TEST_TENANT_ID)
        result = await svc.get_position(sku_id="SKU-ZZ")
        assert result["material"] == {
            "name": None, "category": None, "active": None, "unit_of_measure": None,
        }
        assert result["below_min"] is False


# ---------------------------------------------------------------------------
# adjust_stock — NEVER-NEGATIVE enforcement
# ---------------------------------------------------------------------------

class TestAdjustStock:
    @pytest.mark.asyncio
    async def test_blocks_when_delta_would_go_negative(self, fake_session):
        # InventoryLedger.get_current_on_hand
        _queue(fake_session, scalar=Decimal("5"))
        svc = MaterialService(fake_session, TEST_TENANT_ID)
        with pytest.raises(NegativeStockBlockedError) as exc_info:
            await svc.adjust_stock(
                sku_id="SKU-A",
                qty_delta=Decimal("-10"),
                reason="manual correction",
            )
        err = exc_info.value
        assert err.sku_id == "SKU-A"
        assert err.current == Decimal("5")
        assert err.delta == Decimal("-10")

    @pytest.mark.asyncio
    async def test_reason_required(self, fake_session):
        svc = MaterialService(fake_session, TEST_TENANT_ID)
        with pytest.raises(ValueError):
            await svc.adjust_stock(
                sku_id="SKU-A", qty_delta=Decimal("1"), reason="x",  # too short
            )

    @pytest.mark.asyncio
    async def test_happy_path_writes_ledger_entry(self, fake_session):
        # adjust_stock flow:
        # 1. get_current_on_hand
        _queue(fake_session, scalar=Decimal("10"))
        # 2. record_movement internally does another get_current_on_hand
        _queue(fake_session, scalar=_ledger_entry(sku_id="SKU-A", qty_closing=Decimal("10")))
        svc = MaterialService(fake_session, TEST_TENANT_ID)
        result = await svc.adjust_stock(
            sku_id="SKU-A",
            qty_delta=Decimal("5"),
            reason="quarterly count correction",
            actor="alice",
        )
        assert result["qty_delta"] == 5.0
        assert result["reason"].startswith("quarterly")
        # One InventoryLedgerEntry was added
        added_entries = [a for a in fake_session.added if isinstance(a, InventoryLedgerEntry)]
        assert len(added_entries) == 1
        assert added_entries[0].qty_closing == Decimal("15")


# ---------------------------------------------------------------------------
# get_movements
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_movements_returns_serialised_rows(fake_session):
    e1 = _ledger_entry(sku_id="SKU-A", qty_closing=Decimal("10"))
    e2 = _ledger_entry(sku_id="SKU-A", qty_closing=Decimal("15"))
    _queue(fake_session, scalars=[e1, e2])
    svc = MaterialService(fake_session, TEST_TENANT_ID)
    movements = await svc.get_movements(sku_id="SKU-A")
    assert len(movements) == 2
    assert movements[0]["qty_closing"] == 10.0
    assert movements[0]["sku_id" if False else "transaction_type"] == "adjust"


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------

class TestReconciliation:
    @pytest.mark.asyncio
    async def test_create_computes_variance(self, fake_session):
        _queue(fake_session, scalar=Decimal("100"))  # theoretical on-hand
        svc = MaterialService(fake_session, TEST_TENANT_ID)
        row = await svc.create_reconciliation(
            sku_id="SKU-A",
            physical_qty=Decimal("95"),
            counted_by="warehouse-team",
        )
        assert row.theoretical_qty == Decimal("100")
        assert row.physical_qty == Decimal("95")
        assert row.variance_qty == Decimal("-5")
        assert abs(row.variance_pct + 0.05) < 1e-9
        assert row.resolved is False

    @pytest.mark.asyncio
    async def test_create_handles_zero_theoretical(self, fake_session):
        _queue(fake_session, scalar=Decimal("0"))
        svc = MaterialService(fake_session, TEST_TENANT_ID)
        row = await svc.create_reconciliation(
            sku_id="SKU-NEW", physical_qty=Decimal("5"),
        )
        assert row.variance_qty == Decimal("5")
        assert row.variance_pct is None  # cannot compute % over zero baseline

    @pytest.mark.asyncio
    async def test_resolve_applies_adjust(self, fake_session):
        # Setup: a reconciliation with variance = -3 that needs to be applied
        rec_id = uuid4()
        rec = StockReconciliation(
            id=rec_id, tenant_id=TEST_TENANT_ID, sku_id="SKU-A",
            theoretical_qty=Decimal("10"),
            physical_qty=Decimal("7"),
            variance_qty=Decimal("-3"),
            variance_pct=-0.3,
            resolved=False,
        )
        # resolve_reconciliation does:
        #   1. execute → fetch the reconciliation row
        #   2. adjust_stock:
        #      2a. get_current_on_hand
        #      2b. record_movement → another get_current_on_hand
        _queue(fake_session, scalar=rec)
        _queue(fake_session, scalar=Decimal("10"))  # current on_hand before adjust
        _queue(fake_session, scalar=_ledger_entry(sku_id="SKU-A", qty_closing=Decimal("10")))

        svc = MaterialService(fake_session, TEST_TENANT_ID)
        resolved = await svc.resolve_reconciliation(
            reconciliation_id=rec_id, resolved_by="alice",
        )
        assert resolved.resolved is True
        assert resolved.resolved_by == "alice"

    @pytest.mark.asyncio
    async def test_resolve_missing_id(self, fake_session):
        _queue(fake_session, scalar=None)
        svc = MaterialService(fake_session, TEST_TENANT_ID)
        with pytest.raises(ValueError):
            await svc.resolve_reconciliation(reconciliation_id=uuid4())
