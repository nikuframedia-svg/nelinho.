"""
ProdPlan ONE - Inventory Ledger
================================

Manages inventory ledger entries using event sourcing pattern.
Maintains complete historical record of all inventory movements.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from .models import InventoryLedgerEntry
from src.shared.time import utc_now

logger = logging.getLogger(__name__)


class InventoryLedger:
    """
    Inventory ledger manager.
    
    Records inventory movements (receipts, consumptions, adjustments)
    and maintains complete historical record.
    
    Usage:
        ledger = InventoryLedger(session)
        result = await ledger.record_movement(
            sku_id="SKU-123",
            qty_change=100.0,
            transaction_type="receive",
            reference_id=po_id,
        )
    """
    
    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id
    
    async def record_movement(
        self,
        sku_id: str,
        qty_change,  # accepts Decimal | float | str
        transaction_type: str,  # "consume"|"receive"|"adjust"
        reference_id: Optional[UUID] = None,
    ) -> dict:
        """
        Record inventory movement.

        Sprint Q.12 — race-safe: o último ``qty_closing`` é lido com
        ``SELECT ... FOR UPDATE``, num savepoint, garantindo que dois
        consumos paralelos não ficam ambos a ler o mesmo opening.
        Insuficiência de stock para ``consume`` levanta ``ValueError``
        em vez de truncar silenciosamente para zero.

        Args:
            sku_id: SKU identifier
            qty_change: Quantity change (positive=receipt, negative=consumption)
            transaction_type: Type of transaction ("consume", "receive", "adjust")
            reference_id: Optional reference ID (operation_id or po_id)

        Returns:
            {sku_id, on_hand_after, qty_opening, qty_closing, reference_id}

        Raises:
            ValueError: when consumption exceeds on-hand stock.
        """
        # Convert input to Decimal first — single source of truth from now on.
        qty_change_decimal = Decimal(str(qty_change))

        async with self.session.begin_nested():
            # Get current on-hand (last ledger entry for this SKU) with row-level lock.
            stmt = (
                select(InventoryLedgerEntry)
                .where(
                    InventoryLedgerEntry.tenant_id == self.tenant_id,
                    InventoryLedgerEntry.sku_id == sku_id,
                )
                .order_by(desc(InventoryLedgerEntry.date))
                .limit(1)
                .with_for_update()
            )

            result = await self.session.execute(stmt)
            last_record = result.scalar_one_or_none()

            on_hand_before = last_record.qty_closing if last_record else Decimal("0")

            # Determine qty_in / qty_out using Decimal exclusively.
            if qty_change_decimal > 0:
                qty_in = qty_change_decimal
                qty_out = Decimal("0")
            else:
                qty_in = Decimal("0")
                qty_out = abs(qty_change_decimal)

            on_hand_after = on_hand_before + qty_change_decimal

            # Reject (don't clamp) consumption that would go negative —
            # silent truncation was hiding stock discrepancies.
            if on_hand_after < 0:
                raise ValueError(
                    f"insufficient stock for SKU {sku_id}: "
                    f"on_hand={on_hand_before}, requested={qty_out}"
                )

            qty_closing = on_hand_after

            entry = InventoryLedgerEntry(
                tenant_id=self.tenant_id,
                sku_id=sku_id,
                date=utc_now(),
                qty_opening=on_hand_before,
                qty_in=qty_in,
                qty_out=qty_out,
                qty_closing=qty_closing,
                transaction_type=transaction_type,
                reference_id=reference_id,
            )

            self.session.add(entry)
            await self.session.flush()  # Flush to get ID inside the savepoint.

        logger.info(
            "Inventory movement recorded: SKU=%s, type=%s, change=%s, on_hand: %s → %s",
            sku_id, transaction_type, qty_change_decimal, on_hand_before, qty_closing,
        )

        return {
            "sku_id": sku_id,
            "on_hand_after": qty_closing,
            "qty_opening": on_hand_before,
            "qty_closing": qty_closing,
            "reference_id": reference_id,
        }
    
    async def get_current_on_hand(self, sku_id: str) -> Decimal:
        """
        Get current on-hand quantity for a SKU.
        
        Args:
            sku_id: SKU identifier
        
        Returns:
            Current on-hand quantity (Decimal)
        """
        stmt = (
            select(InventoryLedgerEntry.qty_closing)
            .where(
                InventoryLedgerEntry.tenant_id == self.tenant_id,
                InventoryLedgerEntry.sku_id == sku_id,
            )
            .order_by(desc(InventoryLedgerEntry.date))
            .limit(1)
        )
        
        result = await self.session.execute(stmt)
        qty_closing = result.scalar_one_or_none()
        
        return qty_closing if qty_closing is not None else Decimal("0")
    
    async def get_ledger_history(
        self,
        sku_id: str,
        limit: int = 100,
    ) -> list[InventoryLedgerEntry]:
        """
        Get ledger history for a SKU.
        
        Args:
            sku_id: SKU identifier
            limit: Maximum number of entries to return
        
        Returns:
            List of InventoryLedgerEntry records
        """
        stmt = (
            select(InventoryLedgerEntry)
            .where(
                InventoryLedgerEntry.tenant_id == self.tenant_id,
                InventoryLedgerEntry.sku_id == sku_id,
            )
            .order_by(desc(InventoryLedgerEntry.date))
            .limit(limit)
        )
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())










