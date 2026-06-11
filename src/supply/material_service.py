"""
ProdPlan ONE - Material Service (Sprint O.2 / O.5 / O.6 / O.7)
===============================================================

CRUD + business logic for `MaterialMaster`, inventory adjustments that
respect the never-negative rule, and stock reconciliation flow.

The class is deliberately session-scoped; callers wrap it the same way they
do `GovernanceService` or `TenantConfigService`.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .inventory_ledger import InventoryLedger
from src.shared.time import local_today
from .models import (
    InventoryLedgerEntry,
    MaterialInTransit,
    MaterialMaster,
    ROPConfig,
    StockReconciliation,
)

logger = logging.getLogger(__name__)


# Transaction types. String values must match existing `InventoryLedger.record_movement`
# because we route adjustments through it to keep the ledger single-sourced.
TX_ADJUST = "adjust"
TX_RECEIVE = "receive"
TX_CONSUME = "consume"


class NegativeStockBlockedError(Exception):
    """Raised when a manual adjustment would drive on-hand below zero."""

    def __init__(self, sku_id: str, current: Decimal, delta: Decimal):
        self.sku_id = sku_id
        self.current = current
        self.delta = delta
        super().__init__(
            f"Stock adjustment for {sku_id} blocked: "
            f"current={current} + delta={delta} < 0"
        )


class MaterialNotFoundError(Exception):
    """The requested SKU has no `MaterialMaster` row for this tenant."""


class MaterialService:
    """Business logic around MaterialMaster and the ledger."""

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.ledger = InventoryLedger(session, tenant_id)

    # ─── Material master CRUD ─────────────────────────────────────────────

    async def create_material(
        self,
        *,
        sku_id: str,
        name: str,
        min_stock_qty: Decimal = Decimal("0"),
        reorder_qty: Decimal = Decimal("0"),
        lead_time_days: int = 7,
        default_supplier_id: Optional[UUID] = None,
        unit_of_measure: str = "UN",
        category: Optional[str] = None,
        critical_flag: bool = False,
    ) -> MaterialMaster:
        """Insert a new MaterialMaster. Raises ValueError on duplicate SKU."""
        existing = await self._find_material(sku_id)
        if existing is not None:
            raise ValueError(f"Material {sku_id} already exists for this tenant")

        row = MaterialMaster(
            id=uuid4(),
            tenant_id=self.tenant_id,
            sku_id=sku_id,
            name=name,
            min_stock_qty=min_stock_qty,
            reorder_qty=reorder_qty,
            lead_time_days=lead_time_days,
            default_supplier_id=default_supplier_id,
            unit_of_measure=unit_of_measure,
            category=category,
            critical_flag=critical_flag,
            active=True,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_materials(
        self,
        *,
        active_only: bool = True,
        category: Optional[str] = None,
    ) -> list[MaterialMaster]:
        stmt = select(MaterialMaster).where(MaterialMaster.tenant_id == self.tenant_id)
        if active_only:
            stmt = stmt.where(MaterialMaster.active.is_(True))
        if category:
            stmt = stmt.where(MaterialMaster.category == category)
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_material(self, sku_id: str) -> MaterialMaster:
        row = await self._find_material(sku_id)
        if row is None:
            raise MaterialNotFoundError(sku_id)
        return row

    async def update_min_stock(
        self,
        *,
        sku_id: str,
        min_stock_qty: Decimal,
    ) -> MaterialMaster:
        """MR05/O.3 — override manual do min_stock_qty.

        Marca `min_stock_source='manual'` para que re-runs do ETL
        (Q.173.D) não clobberem o valor definido pelo operador.
        """
        if min_stock_qty < 0:
            raise ValueError("min_stock_qty must be >= 0")
        row = await self.get_material(sku_id)
        row.min_stock_qty = min_stock_qty
        row.min_stock_source = "manual"
        await self.session.flush()
        return row

    async def _find_material(self, sku_id: str) -> Optional[MaterialMaster]:
        stmt = select(MaterialMaster).where(
            and_(
                MaterialMaster.tenant_id == self.tenant_id,
                MaterialMaster.sku_id == sku_id,
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    # ─── Prospeção (O.2) ──────────────────────────────────────────────────

    async def get_position(
        self,
        *,
        sku_id: str,
        horizon_days: int = 14,
    ) -> dict[str, Any]:
        """Aggregate on-hand + in-transit + projected vs min_stock.

        Caller may pass a SKU that has no MaterialMaster row — we still
        return a position document so UIs can show a stub, but
        `below_min`/`critical` fall back to False.
        """
        material = await self._find_material(sku_id)

        on_hand = await self.ledger.get_current_on_hand(sku_id)

        today = local_today()
        until = today + timedelta(days=horizon_days)

        in_transit_stmt = select(MaterialInTransit).where(
            and_(
                MaterialInTransit.tenant_id == self.tenant_id,
                MaterialInTransit.sku_id == sku_id,
                MaterialInTransit.status == "OPEN",
                MaterialInTransit.eta <= until,
            )
        )
        transit_rows = list(
            (await self.session.execute(in_transit_stmt)).scalars().all()
        )
        in_transit_total = sum(
            (Decimal(str(r.qty)) for r in transit_rows),
            start=Decimal("0"),
        )
        in_transit_detail = [
            {
                "purchase_order_id": str(r.purchase_order_id) if r.purchase_order_id else None,
                "qty": float(r.qty),
                "eta": r.eta.isoformat(),
                "supplier_id": str(r.supplier_id) if r.supplier_id else None,
            }
            for r in transit_rows
        ]

        # ROP info comes from ROPConfig if present; else null.
        rop_stmt = select(ROPConfig).where(
            and_(
                ROPConfig.tenant_id == self.tenant_id,
                ROPConfig.sku_id == sku_id,
            )
        )
        rop = (await self.session.execute(rop_stmt)).scalar_one_or_none()

        projected_stock = on_hand + in_transit_total
        min_stock = (
            Decimal(str(material.min_stock_qty))
            if material is not None and material.min_stock_qty is not None
            else Decimal("0")
        )
        # Safety-multiplier applies at read-time (MR05).
        try:
            from src.core.services.tenant_config_service import TenantConfigService

            cfg = TenantConfigService(self.session, self.tenant_id)
            multiplier = Decimal(str(await cfg.get(
                "supply", "safety_multiplier", default=1.0,
            )))
            effective_min = min_stock * multiplier
        except Exception:  # pragma: no cover — defensive
            effective_min = min_stock

        below_min = projected_stock < effective_min
        is_critical = bool(material and material.critical_flag and below_min)

        # Days to stockout based on ROP's average daily demand (if known)
        days_to_stockout: Optional[float] = None
        if rop is not None and rop.avg_daily_demand and rop.avg_daily_demand > 0:
            days_to_stockout = float(on_hand) / float(rop.avg_daily_demand)

        return {
            "sku_id": sku_id,
            "material": {
                "name": material.name if material else None,
                "category": material.category if material else None,
                "active": material.active if material else None,
                "unit_of_measure": material.unit_of_measure if material else None,
            },
            "on_hand": float(on_hand),
            "in_transit": {
                "qty": float(in_transit_total),
                "entries": in_transit_detail,
            },
            "projected_stock_horizon": float(projected_stock),
            "min_stock": float(effective_min),
            "below_min": below_min,
            "critical": is_critical,
            "days_to_stockout": days_to_stockout,
            "rop": float(rop.rop) if rop is not None else None,
            "lead_time_days": (
                material.lead_time_days if material else
                (rop.lead_time_days if rop else None)
            ),
        }

    # ─── Adjust (O.5) ─────────────────────────────────────────────────────

    async def adjust_stock(
        self,
        *,
        sku_id: str,
        qty_delta: Decimal,
        reason: str,
        actor: Optional[str] = None,
        reference_id: Optional[UUID] = None,
    ) -> dict[str, Any]:
        """Manual stock correction.

        Blueprint MR06/ST01 — NEVER permits on-hand to go negative. Unlike
        the legacy `InventoryLedger.record_movement()` which silently clamps
        to zero, this path **raises `NegativeStockBlockedError`** so the
        caller can return HTTP 422 with a structured payload.

        A `STOCK_ADJUSTED` event is emitted via the Kafka producer (best
        effort — a Kafka outage does not block the write, matching the
        pattern established in TenantConfigService).
        """
        if len(reason or "") < 5:
            raise ValueError("Adjustment reason required (min 5 characters)")

        current = await self.ledger.get_current_on_hand(sku_id)
        delta = Decimal(str(qty_delta))
        if current + delta < 0:
            raise NegativeStockBlockedError(sku_id, current, delta)

        result = await self.ledger.record_movement(
            sku_id=sku_id,
            qty_change=float(delta),
            transaction_type=TX_ADJUST,
            reference_id=reference_id,
        )
        await self._emit_stock_adjusted(
            sku_id=sku_id,
            qty_delta=delta,
            on_hand_before=current,
            on_hand_after=result["qty_closing"],
            reason=reason,
            actor=actor,
        )
        # Surface the inputs so callers (e.g. REST layer) can echo them back
        # without a second round-trip.
        return {
            **result,
            "sku_id": sku_id,
            "qty_delta": float(delta),
            "reason": reason,
            "actor": actor,
        }

    # ─── Movement history (O.6) ───────────────────────────────────────────

    async def get_movements(
        self,
        *,
        sku_id: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        transaction_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(InventoryLedgerEntry)
            .where(
                and_(
                    InventoryLedgerEntry.tenant_id == self.tenant_id,
                    InventoryLedgerEntry.sku_id == sku_id,
                )
            )
            .order_by(InventoryLedgerEntry.date.desc())
            .limit(max(1, min(limit, 500)))
        )
        if since:
            stmt = stmt.where(InventoryLedgerEntry.date >= since)
        if until:
            stmt = stmt.where(InventoryLedgerEntry.date <= until)
        if transaction_type:
            stmt = stmt.where(InventoryLedgerEntry.transaction_type == transaction_type)

        rows = list((await self.session.execute(stmt)).scalars().all())
        return [
            {
                "id": str(r.id),
                "date": r.date.isoformat() if r.date else None,
                "transaction_type": r.transaction_type,
                "qty_opening": float(r.qty_opening),
                "qty_in": float(r.qty_in),
                "qty_out": float(r.qty_out),
                "qty_closing": float(r.qty_closing),
                "reference_id": str(r.reference_id) if r.reference_id else None,
            }
            for r in rows
        ]

    # ─── Reconciliation (O.7) ─────────────────────────────────────────────

    async def create_reconciliation(
        self,
        *,
        sku_id: str,
        physical_qty: Decimal,
        counted_by: Optional[str] = None,
        comments: Optional[str] = None,
    ) -> StockReconciliation:
        theoretical = await self.ledger.get_current_on_hand(sku_id)
        variance = Decimal(str(physical_qty)) - theoretical
        variance_pct: Optional[float]
        if theoretical == 0:
            variance_pct = None
        else:
            variance_pct = float(variance / theoretical)

        row = StockReconciliation(
            id=uuid4(),
            tenant_id=self.tenant_id,
            sku_id=sku_id,
            theoretical_qty=theoretical,
            physical_qty=Decimal(str(physical_qty)),
            variance_qty=variance,
            variance_pct=variance_pct,
            counted_by=counted_by,
            comments=comments,
            resolved=False,
            counted_at=datetime.now(timezone.utc),
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_reconciliations(
        self,
        *,
        since: Optional[datetime] = None,
        unresolved_only: bool = False,
        limit: int = 100,
    ) -> list[StockReconciliation]:
        stmt = (
            select(StockReconciliation)
            .where(StockReconciliation.tenant_id == self.tenant_id)
            .order_by(StockReconciliation.counted_at.desc())
            .limit(max(1, min(limit, 500)))
        )
        if since:
            stmt = stmt.where(StockReconciliation.counted_at >= since)
        if unresolved_only:
            stmt = stmt.where(StockReconciliation.resolved.is_(False))
        return list((await self.session.execute(stmt)).scalars().all())

    async def resolve_reconciliation(
        self,
        *,
        reconciliation_id: UUID,
        resolved_by: Optional[str] = None,
    ) -> StockReconciliation:
        stmt = select(StockReconciliation).where(
            and_(
                StockReconciliation.tenant_id == self.tenant_id,
                StockReconciliation.id == reconciliation_id,
            )
        )
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise ValueError(f"Reconciliation {reconciliation_id} not found")
        if row.resolved:
            return row

        # Apply the variance as an adjust movement so the ledger matches reality.
        ledger_entry_id: Optional[UUID] = None
        if row.variance_qty != 0:
            applied = await self.adjust_stock(
                sku_id=row.sku_id,
                qty_delta=row.variance_qty,
                reason=f"Reconciliation {row.id} variance",
                actor=resolved_by,
            )
            ledger_entry_id = applied.get("reference_id")  # may be None

        row.resolved = True
        row.resolved_at = datetime.now(timezone.utc)
        row.resolved_by = resolved_by
        row.resolved_ledger_entry_id = ledger_entry_id
        await self.session.flush()

        try:
            from src.shared.kafka_client import EventBase, Topics, publish_event

            await publish_event(
                Topics.STOCK_RECONCILED,
                EventBase(
                    event_type="STOCK_RECONCILED",
                    tenant_id=self.tenant_id,
                    source_module="supply",
                    payload={
                        "reconciliation_id": str(row.id),
                        "sku_id": row.sku_id,
                        "theoretical_qty": float(row.theoretical_qty) if row.theoretical_qty is not None else None,
                        "physical_qty": float(row.physical_qty) if row.physical_qty is not None else None,
                        "variance_qty": float(row.variance_qty) if row.variance_qty is not None else None,
                        "resolved_by": resolved_by,
                        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
                        "ledger_entry_id": str(ledger_entry_id) if ledger_entry_id else None,
                    },
                ),
            )
        except Exception as exc:  # pragma: no cover — best-effort
            logger.warning("STOCK_RECONCILED publish failed for %s: %s", row.id, exc)

        return row

    # ─── event emission ───────────────────────────────────────────────────

    async def _emit_stock_adjusted(
        self,
        *,
        sku_id: str,
        qty_delta: Decimal,
        on_hand_before: Decimal,
        on_hand_after: Decimal,
        reason: str,
        actor: Optional[str],
    ) -> None:
        try:
            from src.shared.events import ConfigUpdatedEvent  # EventBase alias via package
            from src.shared.kafka_client import EventBase, Topics, publish_event

            class StockAdjustedEvent(EventBase):
                event_type: str = "STOCK_ADJUSTED"
                source_module: str = "SUPPLY"

            event = StockAdjustedEvent(
                tenant_id=self.tenant_id,
                payload={
                    "sku_id": sku_id,
                    "qty_delta": float(qty_delta),
                    "on_hand_before": float(on_hand_before),
                    "on_hand_after": float(on_hand_after),
                    "reason": reason,
                    "actor": actor,
                },
            )
            await publish_event(Topics.STOCK_ADJUSTED, event)
        except Exception as exc:  # pragma: no cover — best-effort
            logger.warning("STOCK_ADJUSTED publish failed: %s", exc)
