"""
ProdPlan ONE - Transport Batch Service (Sprint P.2)
====================================================

CRUD for `TransportBatch` + `TransportBatchAssignment`. Feeds the decoder
with "which orders travel together" so the fitness function can score
spread-out batches (truck consolidation — Sprint P.3).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.models.transport import TransportBatch, TransportBatchAssignment


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
    for batch_id, order_ids in orders_by_batch.items():
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
