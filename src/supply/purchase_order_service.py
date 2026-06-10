"""
ProdPlan ONE - Purchase Order Service (Sprint Q.53.D)
======================================================

Read-side service for supplier purchase-order tracking — the "Entregas"
tab of the Materiais page.

`supply.purchase_orders` is a *local mirror* of supplier orders. Rows
come from two places:

* the NELO ERP `MOVIMENTO` table (movement type 9, "Pedidos a
  fornecedor"), mirrored by the supply `purchase_orders` ETL;
* ProdPlan itself, when a future MRP suggestion flow promotes a planned
  order to a real PO (`source="prodplan"`, `erp_movement_id` NULL).

This service only *reads* — it never writes the ERP. If the table is
empty it degrades honestly: callers get an empty list plus a flag and a
human-readable reason so the UI can show an explicit empty state instead
of a silent blank table.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.time import local_today

from .models import (
    PO_STATUS_CANCELLED,
    PO_STATUS_OPEN,
    PO_STATUS_PARTIAL,
    PO_STATUS_RECEIVED,
    PO_STATUSES,
    PurchaseOrder,
)

logger = logging.getLogger(__name__)


# Open == still expecting goods. PARTIAL is open because lines are short.
_OPEN_STATUSES = (PO_STATUS_OPEN, PO_STATUS_PARTIAL)


class PurchaseOrderService:
    """Read-only tracking of supplier purchase orders."""

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def list_purchase_orders(
        self,
        *,
        status: Optional[str] = None,
        product_code: Optional[str] = None,
        supplier: Optional[str] = None,
        open_only: bool = False,
        limit: int = 200,
    ) -> dict[str, Any]:
        """List tracked POs, newest ETA first, with an honest availability flag.

        Returns a document:
            {
              items: [...],          # serialised PO rows
              count: int,
              data_available: bool,  # False when the mirror was never synced
              source: str,           # 'supply_purchase_orders' | 'indisponivel'
              last_synced_at: str|None,
              unavailable_reason: str|None,
              summary: {open, overdue, received, cancelled, total_outstanding_qty},
            }

        `open_only` keeps only OPEN/PARTIAL rows; `status` filters to one
        exact reception state. Both may be combined.
        """
        limit = max(1, min(limit, 1000))

        # Is the mirror populated at all? One cheap COUNT decides whether we
        # report honest emptiness vs an empty filter result.
        total_rows = (
            await self.session.execute(
                select(func.count())
                .select_from(PurchaseOrder)
                .where(PurchaseOrder.tenant_id == self.tenant_id)
            )
        ).scalar_one_or_none() or 0

        stmt = (
            select(PurchaseOrder)
            .where(PurchaseOrder.tenant_id == self.tenant_id)
            .order_by(
                PurchaseOrder.eta.is_(None),  # rows without ETA last
                PurchaseOrder.eta.asc(),
                PurchaseOrder.ordered_at.desc(),
            )
            .limit(limit)
        )
        if status:
            if status not in PO_STATUSES:
                raise ValueError(
                    f"status inválido: {status!r} — usar um de {PO_STATUSES}"
                )
            stmt = stmt.where(PurchaseOrder.status == status)
        if open_only:
            stmt = stmt.where(PurchaseOrder.status.in_(_OPEN_STATUSES))
        if product_code:
            stmt = stmt.where(PurchaseOrder.product_code == product_code.strip())
        if supplier:
            stmt = stmt.where(
                PurchaseOrder.supplier_name.ilike(f"%{supplier.strip()}%")
            )

        rows = list((await self.session.execute(stmt)).scalars().all())

        today = local_today()
        items = [_po_to_dict(r, today) for r in rows]

        last_synced_at = max(
            (r.synced_at for r in rows if r.synced_at is not None),
            default=None,
        )

        summary = _summarise(rows, today)

        data_available = total_rows > 0
        unavailable_reason: Optional[str] = None
        if not data_available:
            unavailable_reason = (
                "Ainda não há encomendas a fornecedor sincronizadas. Corre o "
                "ETL `scripts/sync_nelo_erp.py --only purchase_orders` para "
                "espelhar os movimentos tipo 9 (\"Pedidos a fornecedor\") do "
                "ERP NELO."
            )

        return {
            "items": items,
            "count": len(items),
            "data_available": data_available,
            "source": (
                "supply_purchase_orders" if data_available else "indisponivel"
            ),
            "last_synced_at": (
                last_synced_at.isoformat() if last_synced_at else None
            ),
            "unavailable_reason": unavailable_reason,
            "summary": summary,
        }


def _po_to_dict(po: PurchaseOrder, today: date) -> dict[str, Any]:
    qty_ordered = Decimal(str(po.qty_ordered or 0))
    qty_received = Decimal(str(po.qty_received or 0))
    outstanding = qty_ordered - qty_received
    if outstanding < 0:
        outstanding = Decimal("0")

    is_open = po.status in _OPEN_STATUSES
    is_overdue = bool(is_open and po.eta is not None and po.eta < today)
    days_to_eta: Optional[int] = None
    if is_open and po.eta is not None:
        days_to_eta = (po.eta - today).days

    return {
        "id": str(po.id),
        "po_number": po.po_number,
        "erp_movement_id": po.erp_movement_id,
        "supplier_name": po.supplier_name,
        "supplier_erp_id": po.supplier_erp_id,
        "product_code": po.product_code,
        "product_name": po.product_name,
        "qty_ordered": float(qty_ordered),
        "qty_received": float(qty_received),
        "qty_outstanding": float(outstanding),
        "unit_of_measure": po.unit_of_measure,
        "ordered_at": po.ordered_at.isoformat() if po.ordered_at else None,
        "eta": po.eta.isoformat() if po.eta else None,
        "received_at": po.received_at.isoformat() if po.received_at else None,
        "status": po.status,
        "is_overdue": is_overdue,
        "days_to_eta": days_to_eta,
        "source": po.source,
        "notes": po.notes,
    }


def _summarise(rows: list[PurchaseOrder], today: date) -> dict[str, Any]:
    open_n = overdue_n = received_n = cancelled_n = 0
    outstanding = Decimal("0")
    for r in rows:
        if r.status in _OPEN_STATUSES:
            open_n += 1
            qo = Decimal(str(r.qty_ordered or 0))
            qr = Decimal(str(r.qty_received or 0))
            delta = qo - qr
            if delta > 0:
                outstanding += delta
            if r.eta is not None and r.eta < today:
                overdue_n += 1
        elif r.status == PO_STATUS_RECEIVED:
            received_n += 1
        elif r.status == PO_STATUS_CANCELLED:
            cancelled_n += 1
    return {
        "open": open_n,
        "overdue": overdue_n,
        "received": received_n,
        "cancelled": cancelled_n,
        "total_outstanding_qty": float(outstanding),
    }
