"""
Tests for PurchaseOrderService (Sprint Q.53.D).

Tracking of supplier purchase orders — the "Entregas" tab. DB reads are
mocked via `FakeSession`; each test reads as an independent spec.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from src.supply.models import (
    PO_STATUS_CANCELLED,
    PO_STATUS_OPEN,
    PO_STATUS_PARTIAL,
    PO_STATUS_RECEIVED,
    PurchaseOrder,
)
from src.supply.purchase_order_service import PurchaseOrderService
from tests.conftest import TEST_TENANT_ID


def _queue_list(fake_session, *, total: int, rows: list) -> None:
    """Queue the two executes `list_purchase_orders` issues, in order.

    `FakeSession.execute` pops one scalar slot AND one scalars slot per
    call. Call #1 is the COUNT (scalar=total); call #2 is the row SELECT
    (scalars=rows).
    """
    fake_session.queue_scalar(total)   # execute #1: COUNT
    fake_session.queue_scalars([])
    fake_session.queue_scalar(None)    # execute #2: row SELECT
    fake_session.queue_scalars(rows)


def _po(
    *,
    product_code: str = "MAT-001",
    supplier: str = "Fibras Lda",
    qty_ordered: Decimal = Decimal("100"),
    qty_received: Decimal = Decimal("0"),
    status: str = PO_STATUS_OPEN,
    eta: date | None = None,
    erp_movement_id: int | None = None,
    source: str = "prodplan",
) -> PurchaseOrder:
    return PurchaseOrder(
        id=uuid4(),
        tenant_id=TEST_TENANT_ID,
        erp_movement_id=erp_movement_id,
        po_number="PO-0001",
        supplier_name=supplier,
        supplier_erp_id=None,
        product_code=product_code,
        product_name=f"Material {product_code}",
        qty_ordered=qty_ordered,
        qty_received=qty_received,
        unit_of_measure="KG",
        ordered_at=date.today() - timedelta(days=10),
        eta=eta,
        received_at=None,
        status=status,
        source=source,
        notes=None,
        synced_at=datetime.now(timezone.utc),
    )


class TestEmptyMirror:
    @pytest.mark.asyncio
    async def test_degrades_honestly_when_never_synced(self, fake_session):
        # COUNT(*) → 0 means the mirror was never populated.
        _queue_list(fake_session, total=0, rows=[])

        svc = PurchaseOrderService(fake_session, TEST_TENANT_ID)
        result = await svc.list_purchase_orders()

        assert result["data_available"] is False
        assert result["source"] == "indisponivel"
        assert result["count"] == 0
        assert result["items"] == []
        assert result["unavailable_reason"] is not None
        assert "purchase_orders" in result["unavailable_reason"]

    @pytest.mark.asyncio
    async def test_empty_summary_is_all_zero(self, fake_session):
        _queue_list(fake_session, total=0, rows=[])
        svc = PurchaseOrderService(fake_session, TEST_TENANT_ID)
        result = await svc.list_purchase_orders()
        assert result["summary"] == {
            "open": 0,
            "overdue": 0,
            "received": 0,
            "cancelled": 0,
            "total_outstanding_qty": 0.0,
        }


class TestListPurchaseOrders:
    @pytest.mark.asyncio
    async def test_serialises_rows_with_outstanding_qty(self, fake_session):
        po = _po(qty_ordered=Decimal("100"), qty_received=Decimal("40"),
                 status=PO_STATUS_PARTIAL, eta=date.today() + timedelta(days=5))
        _queue_list(fake_session, total=1, rows=[po])

        svc = PurchaseOrderService(fake_session, TEST_TENANT_ID)
        result = await svc.list_purchase_orders()

        assert result["data_available"] is True
        assert result["count"] == 1
        item = result["items"][0]
        assert item["qty_ordered"] == 100.0
        assert item["qty_received"] == 40.0
        assert item["qty_outstanding"] == 60.0
        assert item["status"] == "PARTIAL"
        assert item["is_overdue"] is False
        assert item["days_to_eta"] == 5

    @pytest.mark.asyncio
    async def test_overdue_flag_when_eta_in_past_and_open(self, fake_session):
        po = _po(status=PO_STATUS_OPEN, eta=date.today() - timedelta(days=3))
        _queue_list(fake_session, total=1, rows=[po])
        svc = PurchaseOrderService(fake_session, TEST_TENANT_ID)
        result = await svc.list_purchase_orders()
        item = result["items"][0]
        assert item["is_overdue"] is True
        assert item["days_to_eta"] == -3

    @pytest.mark.asyncio
    async def test_received_po_is_never_overdue(self, fake_session):
        # A delivered PO with a past ETA must not be flagged overdue.
        po = _po(status=PO_STATUS_RECEIVED, eta=date.today() - timedelta(days=30),
                 qty_ordered=Decimal("50"), qty_received=Decimal("50"))
        _queue_list(fake_session, total=1, rows=[po])
        svc = PurchaseOrderService(fake_session, TEST_TENANT_ID)
        result = await svc.list_purchase_orders()
        item = result["items"][0]
        assert item["is_overdue"] is False
        assert item["days_to_eta"] is None  # not open ⇒ no countdown

    @pytest.mark.asyncio
    async def test_outstanding_never_negative_on_over_receipt(self, fake_session):
        # Received more than ordered (ERP rounding) ⇒ outstanding clamps to 0.
        po = _po(qty_ordered=Decimal("100"), qty_received=Decimal("105"),
                 status=PO_STATUS_RECEIVED)
        _queue_list(fake_session, total=1, rows=[po])
        svc = PurchaseOrderService(fake_session, TEST_TENANT_ID)
        result = await svc.list_purchase_orders()
        assert result["items"][0]["qty_outstanding"] == 0.0

    @pytest.mark.asyncio
    async def test_summary_counts_and_outstanding(self, fake_session):
        rows = [
            _po(status=PO_STATUS_OPEN, qty_ordered=Decimal("100"),
                qty_received=Decimal("0"), eta=date.today() + timedelta(days=2)),
            _po(status=PO_STATUS_PARTIAL, qty_ordered=Decimal("80"),
                qty_received=Decimal("30"),
                eta=date.today() - timedelta(days=1)),  # overdue
            _po(status=PO_STATUS_RECEIVED, qty_ordered=Decimal("50"),
                qty_received=Decimal("50")),
            _po(status=PO_STATUS_CANCELLED, qty_ordered=Decimal("20"),
                qty_received=Decimal("0")),
        ]
        _queue_list(fake_session, total=4, rows=rows)
        svc = PurchaseOrderService(fake_session, TEST_TENANT_ID)
        result = await svc.list_purchase_orders()
        s = result["summary"]
        assert s["open"] == 2          # OPEN + PARTIAL
        assert s["overdue"] == 1
        assert s["received"] == 1
        assert s["cancelled"] == 1
        # outstanding = 100 (open) + 50 (partial 80-30); received/cancelled excluded
        assert s["total_outstanding_qty"] == 150.0

    @pytest.mark.asyncio
    async def test_last_synced_at_is_iso_string(self, fake_session):
        po = _po()
        _queue_list(fake_session, total=1, rows=[po])
        svc = PurchaseOrderService(fake_session, TEST_TENANT_ID)
        result = await svc.list_purchase_orders()
        assert result["last_synced_at"] is not None
        # parseable ISO 8601
        datetime.fromisoformat(result["last_synced_at"])

    @pytest.mark.asyncio
    async def test_invalid_status_rejected(self, fake_session):
        # COUNT runs before status validation; only one execute is reached.
        fake_session.queue_scalar(1)
        fake_session.queue_scalars([])
        svc = PurchaseOrderService(fake_session, TEST_TENANT_ID)
        with pytest.raises(ValueError):
            await svc.list_purchase_orders(status="DELIVERED")

    @pytest.mark.asyncio
    async def test_limit_is_clamped(self, fake_session):
        # Out-of-range limit must not blow up — service clamps to [1, 1000].
        _queue_list(fake_session, total=0, rows=[])
        svc = PurchaseOrderService(fake_session, TEST_TENANT_ID)
        result = await svc.list_purchase_orders(limit=99999)
        assert result["count"] == 0
