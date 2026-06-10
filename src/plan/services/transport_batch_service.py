"""
ProdPlan ONE - Transport Batch Service (Sprint P.2)
====================================================

CRUD for `TransportBatch` + `TransportBatchAssignment`. Feeds the decoder
with "which orders travel together" so the fitness function can score
spread-out batches (truck consolidation — Sprint P.3).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.governance.audit_service import audit_change
from src.plan.models.order import OrderStatus, ProductionOrder
from src.plan.models.transport import TransportBatch, TransportBatchAssignment
from src.shared.time import local_today


class TransportBatchNotFoundError(Exception):
    pass


class TransportBatchService:
    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def create_batch(
        self,
        *,
        code: str,
        transport_date: date,
        truck_capacity_units: int = 50,
        priority: int = 100,
        destination: Optional[str] = None,
    ) -> TransportBatch:
        row = TransportBatch(
            id=uuid4(),
            tenant_id=self.tenant_id,
            code=code,
            transport_date=transport_date,
            truck_capacity_units=truck_capacity_units,
            priority=priority,
            destination=destination,
            status="OPEN",
        )
        self.session.add(row)
        await audit_change(
            self.session,
            tenant_id=self.tenant_id,
            entity_type="transport_batch",
            entity_id=row.id,
            action="INSERT",
            old_values=None,
            new_values={
                "code": code,
                "transport_date": transport_date.isoformat(),
                "truck_capacity_units": truck_capacity_units,
                "priority": priority,
                "destination": destination,
                "status": "OPEN",
            },
            reason="Q.66.B.3 — batch de transporte criado",
        )
        await self.session.flush()
        return row

    async def assign_order(
        self,
        *,
        batch_id: UUID,
        order_id: UUID,
    ) -> TransportBatchAssignment:
        """Idempotent — re-assigning an already-linked order is a no-op."""
        stmt = select(TransportBatchAssignment).where(
            and_(
                TransportBatchAssignment.tenant_id == self.tenant_id,
                TransportBatchAssignment.order_id == order_id,
            )
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            if existing.batch_id != batch_id:
                existing.batch_id = batch_id
                await self.session.flush()
            return existing

        link = TransportBatchAssignment(
            id=uuid4(),
            tenant_id=self.tenant_id,
            batch_id=batch_id,
            order_id=order_id,
        )
        self.session.add(link)
        await audit_change(
            self.session,
            tenant_id=self.tenant_id,
            entity_type="transport_batch_assignment",
            entity_id=link.id,
            action="INSERT",
            old_values=None,
            new_values={
                "batch_id": str(batch_id),
                "order_id": str(order_id),
            },
            reason="Q.66.B.3 — ordem atribuida a batch de transporte",
        )
        await self.session.flush()
        return link

    async def list_batches(
        self,
        *,
        since: Optional[date] = None,
        until: Optional[date] = None,
        status: Optional[str] = None,
    ) -> list[TransportBatch]:
        stmt = select(TransportBatch).where(
            TransportBatch.tenant_id == self.tenant_id,
        )
        if since:
            stmt = stmt.where(TransportBatch.transport_date >= since)
        if until:
            stmt = stmt.where(TransportBatch.transport_date <= until)
        if status:
            stmt = stmt.where(TransportBatch.status == status)
        stmt = stmt.order_by(TransportBatch.transport_date, TransportBatch.priority)
        return list((await self.session.execute(stmt)).scalars().all())

    async def orders_by_batch(self) -> dict[UUID, list[UUID]]:
        """Return `{batch_id: [order_id, …]}` for every OPEN batch."""
        stmt = (
            select(TransportBatchAssignment)
            .where(TransportBatchAssignment.tenant_id == self.tenant_id)
        )
        rows = list((await self.session.execute(stmt)).scalars().all())
        out: dict[UUID, list[UUID]] = {}
        for row in rows:
            out.setdefault(row.batch_id, []).append(row.order_id)
        return out

    async def remove_order(
        self,
        *,
        batch_id: UUID,
        order_id: UUID,
    ) -> bool:
        """Detach an order from a batch. Returns True iff a link existed."""
        stmt = select(TransportBatchAssignment).where(
            and_(
                TransportBatchAssignment.tenant_id == self.tenant_id,
                TransportBatchAssignment.batch_id == batch_id,
                TransportBatchAssignment.order_id == order_id,
            )
        )
        link = (await self.session.execute(stmt)).scalar_one_or_none()
        if link is None:
            return False
        await self.session.delete(link)
        await self.session.flush()
        return True

    async def get_batch(self, batch_id: UUID) -> TransportBatch:
        """Public read-only fetch. Raises TransportBatchNotFoundError if absent."""
        return await self._get(batch_id)

    async def assigned_count(self, batch_id: UUID) -> int:
        """How many orders are currently linked to this batch."""
        stmt = select(TransportBatchAssignment).where(
            and_(
                TransportBatchAssignment.tenant_id == self.tenant_id,
                TransportBatchAssignment.batch_id == batch_id,
            )
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return len(list(rows))

    async def list_orders(self, batch_id: UUID) -> list[UUID]:
        """Return the order_ids currently assigned to one batch.

        Sprint Q.9 Onda 3.3 — backs `GET /batches/{id}/orders`. The
        DispatchPage frontend uses this to render the assigned ord
        cards as draggable items between batches.
        """
        stmt = (
            select(TransportBatchAssignment.order_id)
            .where(
                and_(
                    TransportBatchAssignment.tenant_id == self.tenant_id,
                    TransportBatchAssignment.batch_id == batch_id,
                )
            )
            .order_by(TransportBatchAssignment.created_at)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return list(rows)

    async def freeze(self, batch_id: UUID) -> TransportBatch:
        row = await self._get(batch_id)
        row.status = "FROZEN"
        await self.session.flush()
        return row

    async def dispatch(self, batch_id: UUID) -> TransportBatch:
        row = await self._get(batch_id)
        row.status = "DISPATCHED"
        await self.session.flush()
        return row

    async def refresh_from_orders(
        self,
        *,
        horizon_days: int = 45,
        default_capacity: int = 50,
        today: Optional[date] = None,
    ) -> dict[str, int]:
        """Q.143.A — deriva camiões reais a partir das `production_orders`.

        Para cada `transport_date` distinta na janela [hoje, hoje+horizon],
        garante um camião OPEN `SHP-{date}` e atribui-lhe as ordens dessa data
        que ainda NÃO têm camião — até à capacidade. Preserva o drag-drop
        manual (nunca reatribui uma ordem já colocada) e nunca toca em camiões
        FROZEN/DISPATCHED.

        Idempotente: uma 2ª corrida não cria camiões nem atribui nada novo.
        Devolve `{batches_created, batches_touched, orders_assigned, overflow}`.
        """
        ref_today = today or local_today()
        until = ref_today + timedelta(days=horizon_days)

        # 1. Ordens elegíveis (futuras, não canceladas) agrupadas por data.
        stmt = (
            select(ProductionOrder)
            .where(
                ProductionOrder.tenant_id == self.tenant_id,
                ProductionOrder.transport_date.is_not(None),
                ProductionOrder.transport_date >= ref_today,
                ProductionOrder.transport_date <= until,
                ProductionOrder.status != OrderStatus.CANCELLED,
            )
            .order_by(ProductionOrder.transport_date, ProductionOrder.legacy_id)
        )
        orders = list((await self.session.execute(stmt)).scalars().all())

        by_date: dict[date, list[ProductionOrder]] = {}
        for o in orders:
            if o.transport_date is not None:
                by_date.setdefault(o.transport_date, []).append(o)

        # 2. Ordens já atribuídas a QUALQUER camião — nunca reatribuir
        #    (preserva movimentos manuais e corridas anteriores).
        existing_by_batch = await self.orders_by_batch()
        already_assigned: set[UUID] = {
            oid for ids in existing_by_batch.values() for oid in ids
        }

        # Camiões existentes na janela, indexados por data (1 lookup).
        existing_batches = await self.list_batches(since=ref_today, until=until)
        batch_by_date: dict[date, TransportBatch] = {}
        for b in existing_batches:
            batch_by_date.setdefault(b.transport_date, b)

        summary = {
            "batches_created": 0,
            "batches_touched": 0,
            "orders_assigned": 0,
            "overflow": 0,
        }

        for tdate in sorted(by_date.keys()):
            day_orders = by_date[tdate]
            batch = batch_by_date.get(tdate)
            if batch is None:
                batch = await self.create_batch(
                    code=f"SHP-{tdate.isoformat()}",
                    transport_date=tdate,
                    truck_capacity_units=default_capacity,
                )
                batch_by_date[tdate] = batch
                summary["batches_created"] += 1
            elif batch.status != "OPEN":
                # Camião congelado/despachado — não mexer.
                continue

            used = len(existing_by_batch.get(batch.id, []))
            free = max(0, batch.truck_capacity_units - used)
            assigned_here = 0
            for o in day_orders:
                if o.id in already_assigned:
                    continue
                if assigned_here >= free:
                    summary["overflow"] += 1
                    continue
                await self.assign_order(batch_id=batch.id, order_id=o.id)
                already_assigned.add(o.id)
                assigned_here += 1
                summary["orders_assigned"] += 1
            if assigned_here > 0:
                summary["batches_touched"] += 1

        return summary

    async def _get(self, batch_id: UUID) -> TransportBatch:
        stmt = select(TransportBatch).where(
            and_(
                TransportBatch.tenant_id == self.tenant_id,
                TransportBatch.id == batch_id,
            )
        )
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise TransportBatchNotFoundError(str(batch_id))
        return row


def compute_truck_consolidation_penalty_h(
    ops_by_order: dict[str, list[Any]],
    orders_by_batch: dict[Any, list[str]],
    tolerance_h: float = 12.0,
) -> float:
    """Sum over all batches of `max(span(finish_times) − tolerance, 0)`.

    `ops_by_order[order_id]` = ScheduledOp dicts with `.end` datetimes.
    `orders_by_batch[batch_id]` = list of order_ids.

    We look at the LAST op of each order (the transport-ready event) and
    measure the span of those finish times within a batch. Anything above
    `tolerance_h` drives the penalty up; anything within the tolerance is
    considered "arrived together".

    Returns a scalar in hours. Zero when nothing to consolidate.
    """
    if not orders_by_batch:
        return 0.0

    penalty = 0.0
    for _batch_id, order_ids in orders_by_batch.items():
        finish_times = []
        for order_id in order_ids:
            ops = ops_by_order.get(str(order_id))
            if not ops:
                continue
            last_end = max(op.get("end") or op.get("finish") for op in ops if op)
            if last_end is None:
                continue
            finish_times.append(last_end)
        if len(finish_times) < 2:
            continue
        span_h = (max(finish_times) - min(finish_times)).total_seconds() / 3600.0
        penalty += max(0.0, span_h - tolerance_h)
    return penalty
