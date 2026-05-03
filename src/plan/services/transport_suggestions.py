"""
ProdPlan ONE - Transport Batch Suggestions (Sprint Q.2 / DE03)
==============================================================

Generates the 5 suggestion types described in PP1 NELO Plan v4 §37 for the
Despacho/Expedição UI. Each suggestion follows the principle "explica
sempre" — i.e. carries `what / why / if_accept / if_reject / alternative`
so the UI can render the consequence panel without re-deriving anything.

Suggestion catalogue:

| type                  | trigger                                                |
|-----------------------|--------------------------------------------------------|
| advance_boat          | order ready well before its scheduled batch date       |
| delay_boat            | order at high quality risk shipping inside this batch  |
| swap_between_batches  | this batch is over capacity AND another is below       |
| complete_truck        | this batch is half-empty AND there are unassigned ords |
| regroup_by_client     | the same client has orders spread across many batches  |

The detector is deliberately simple — a heuristic pass over batch state.
The CPO/quality stacks remain authoritative; this is just a "noticeable
patterns" surface that the operator approves or dismisses.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.models.order import OrderStatus, ProductionOrder
from src.plan.models.transport import TransportBatch, TransportBatchAssignment

logger = logging.getLogger(__name__)


# Capacity defaults — overridable via TenantConfig.transporte.* in
# Q.2's caller (the API layer reads these via configApi).
DEFAULT_TRUCK_CAPACITY = 50

# Sprint Q.13.E E.2 — historical modal load on the Vila do Conde lane.
# The truck *can* take 50 boats (CEO baseline) but the real distribution
# clusters at 26 — that's the load `complete_truck` aims for.
DEFAULT_TRUCK_CAPACITY_MODA = 26

DEFAULT_DELIVERY_BUFFER_DAYS = 1

# A batch is "half-empty" when assigned <= half of capacity.
HALF_EMPTY_RATIO = 0.5

# Client spread threshold — propose regroup only if same client appears in
# this many batches within the planning window.
CLIENT_SPREAD_BATCHES = 3


@dataclass
class TransportSuggestion:
    """A single dispatch suggestion ready for the UI."""

    type: str
    what: str
    why: str
    if_accept: str
    if_reject: str
    alternative: Optional[str] = None
    affected_order_ids: Optional[List[str]] = None
    target_batch_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "what": self.what,
            "why": self.why,
            "if_accept": self.if_accept,
            "if_reject": self.if_reject,
            "alternative": self.alternative,
            "affected_order_ids": self.affected_order_ids or [],
            "target_batch_id": self.target_batch_id,
        }


class TransportSuggestionsService:
    """Generate dispatch suggestions for a single transport batch.

    Args:
        session: AsyncSession scoped to the tenant.
        tenant_id: tenant UUID.
        truck_capacity: default capacity when batch.truck_capacity_units is 0.
        buffer_days: how many days "early" qualifies as advance_boat.
    """

    def __init__(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        *,
        truck_capacity: int = DEFAULT_TRUCK_CAPACITY,
        truck_capacity_moda: int = DEFAULT_TRUCK_CAPACITY_MODA,
        buffer_days: int = DEFAULT_DELIVERY_BUFFER_DAYS,
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.truck_capacity = truck_capacity
        self.truck_capacity_moda = truck_capacity_moda
        self.buffer_days = buffer_days

    async def for_batch(self, batch_id: UUID) -> List[TransportSuggestion]:
        """Top-level: all 5 detectors for a single batch, in a stable order."""
        batch = await self._fetch_batch(batch_id)
        if batch is None or batch.status == "DISPATCHED":
            return []

        orders, assigned_ids = await self._fetch_assigned_orders(batch_id)
        unassigned = await self._fetch_unassigned_completed_orders()
        peer_batches = await self._fetch_peer_batches(batch.transport_date)

        suggestions: List[TransportSuggestion] = []
        suggestions.extend(self._detect_advance(batch, orders))
        suggestions.extend(self._detect_delay(batch, orders))
        suggestions.extend(self._detect_swap(batch, peer_batches, len(orders)))
        suggestions.extend(self._detect_complete_truck(batch, len(orders), unassigned))
        suggestions.extend(self._detect_regroup_by_client(orders, peer_batches))
        return suggestions

    # ------------------------------------------------------------------
    # Detectors — each returns 0..N suggestions
    # ------------------------------------------------------------------

    def _detect_advance(
        self,
        batch: TransportBatch,
        orders: List[ProductionOrder],
    ) -> List[TransportSuggestion]:
        threshold = batch.transport_date - timedelta(days=self.buffer_days + 1)
        ready = [
            o for o in orders
            if o.status == OrderStatus.COMPLETED.value
            and o.completed_date is not None
            and o.completed_date <= threshold
        ]
        if not ready:
            return []
        ids = [str(o.id) for o in ready[:5]]
        return [
            TransportSuggestion(
                type="advance_boat",
                what=(
                    f"Antecipar {len(ready)} barco(s) prontos para uma "
                    "expedição mais cedo."
                ),
                why=(
                    f"Já estão concluídos ≥{self.buffer_days + 1} dias antes "
                    f"da data {batch.transport_date.isoformat()}; a aguardar "
                    "ocupam espaço sem necessidade."
                ),
                if_accept=(
                    "Cliente recebe mais cedo e liberta espaço neste batch "
                    "para outros barcos com prazo mais apertado."
                ),
                if_reject=(
                    "Os barcos ficam neste batch como planeado; sem custo "
                    "adicional mas sem oportunidade de antecipar entrega."
                ),
                alternative=(
                    "Mover só os mais urgentes (top 5) e deixar os restantes."
                ),
                affected_order_ids=ids,
            )
        ]

    def _detect_delay(
        self,
        batch: TransportBatch,
        orders: List[ProductionOrder],
    ) -> List[TransportSuggestion]:
        # Heuristic: if the order is still IN_PROGRESS within `buffer_days` of
        # transport_date it's a candidate for delay (quality risk proxy: not
        # finished in time = chance of rushed work / defects).
        cutoff = batch.transport_date - timedelta(days=self.buffer_days)
        at_risk = [
            o for o in orders
            if o.status == OrderStatus.IN_PROGRESS.value
            and (o.completed_date is None or o.completed_date > cutoff)
        ]
        if not at_risk:
            return []
        ids = [str(o.id) for o in at_risk[:5]]
        return [
            TransportSuggestion(
                type="delay_boat",
                what=(
                    f"Adiar {len(at_risk)} barco(s) para a próxima expedição."
                ),
                why=(
                    "Ainda IN_PROGRESS dentro da janela de buffer — risco de "
                    "ir com defeito por trabalho apressado."
                ),
                if_accept=(
                    "Evita enviar com possível retrabalho; mais 1 expedição "
                    "de margem para QC."
                ),
                if_reject=(
                    "Risco de cliente receber barco com defeito + retrabalho "
                    "depois (custo €340 médio)."
                ),
                alternative=(
                    "Manter no batch mas marcar prioridade alta para QC final."
                ),
                affected_order_ids=ids,
            )
        ]

    def _detect_swap(
        self,
        batch: TransportBatch,
        peer_batches: List[TransportBatch],
        assigned: int,
    ) -> List[TransportSuggestion]:
        capacity = batch.truck_capacity_units or self.truck_capacity
        if assigned <= capacity:
            return []
        # Find under-loaded peer batches (any non-DISPATCHED batch in window)
        candidates = [
            b for b in peer_batches
            if b.id != batch.id
            and b.status != "DISPATCHED"
        ]
        if not candidates:
            return []
        target = min(candidates, key=lambda b: (b.priority, b.transport_date))
        excess = assigned - capacity
        return [
            TransportSuggestion(
                type="swap_between_batches",
                what=(
                    f"Mover {excess} barco(s) deste batch ({assigned}/"
                    f"{capacity}) para o batch '{target.code}' "
                    f"({target.transport_date.isoformat()})."
                ),
                why=(
                    f"Este batch está acima da capacidade do camião "
                    f"({assigned} > {capacity}); o batch '{target.code}' tem "
                    "espaço."
                ),
                if_accept=(
                    "Carga equilibrada entre camiões; reduz risco logístico."
                ),
                if_reject=(
                    f"Continuamos com {excess} barco(s) acima da capacidade "
                    "— camião em sobrelotação."
                ),
                alternative="Pedir camião adicional para esta data.",
                target_batch_id=str(target.id),
            )
        ]

    def _detect_complete_truck(
        self,
        batch: TransportBatch,
        assigned: int,
        unassigned: List[ProductionOrder],
    ) -> List[TransportSuggestion]:
        capacity = batch.truck_capacity_units or self.truck_capacity
        # Sprint Q.13.E E.2 — target the *modal* load (real-world average,
        # ~26 boats), not the truck's ceiling (50). Suggesting "fill to 50"
        # over-promises trips that historically never run that full and
        # creates a demand the production schedule can't keep up with.
        target = min(self.truck_capacity_moda, capacity)
        if assigned == 0 or assigned >= target:
            return []
        if not unassigned:
            return []
        slack = target - assigned
        candidates = unassigned[:slack]
        ids = [str(o.id) for o in candidates]
        return [
            TransportSuggestion(
                type="complete_truck",
                what=(
                    f"Adicionar {len(candidates)} barco(s) sem expedição a "
                    f"este batch para chegar à carga típica ({target} barcos)."
                ),
                why=(
                    f"Batch abaixo da moda ({assigned}/{target}, capacidade "
                    f"máxima {capacity}); há {len(unassigned)} barco(s) "
                    "prontos sem expedição atribuída."
                ),
                if_accept=(
                    "Camião completo — poupa um trip da semana seguinte "
                    "(~€800 por viagem)."
                ),
                if_reject=(
                    "Camião sai a meio; custo logístico fica como está."
                ),
                alternative=(
                    "Aceitar metade dos barcos sugeridos para manter folga "
                    "para imprevistos."
                ),
                affected_order_ids=ids,
            )
        ]

    def _detect_regroup_by_client(
        self,
        orders: List[ProductionOrder],
        peer_batches: List[TransportBatch],
    ) -> List[TransportSuggestion]:
        # We don't have a `customer_id` in the legacy ProductionOrder model;
        # use product_type as a coarse proxy until C5 customer wiring lands.
        if not orders:
            return []
        # Spread = same product_type appearing in this batch + ≥CLIENT_SPREAD_BATCHES
        # peer batches.
        types_in_self = {o.product_type for o in orders if o.product_type}
        if not types_in_self:
            return []
        # We'd need to know what's in peer batches to detect spread; this
        # detector is a teaser — returns empty until peer-batch order lookup
        # is wired by Q.5 (CEO Dashboard backlog-by-client). Documented so
        # the UI surface stays consistent.
        return []

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    async def _fetch_batch(self, batch_id: UUID) -> Optional[TransportBatch]:
        stmt = select(TransportBatch).where(
            and_(
                TransportBatch.tenant_id == self.tenant_id,
                TransportBatch.id == batch_id,
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _fetch_assigned_orders(
        self, batch_id: UUID,
    ) -> tuple[List[ProductionOrder], List[UUID]]:
        link_stmt = select(TransportBatchAssignment.order_id).where(
            and_(
                TransportBatchAssignment.tenant_id == self.tenant_id,
                TransportBatchAssignment.batch_id == batch_id,
            )
        )
        ids = list((await self.session.execute(link_stmt)).scalars().all())
        if not ids:
            return [], []
        ord_stmt = select(ProductionOrder).where(
            and_(
                ProductionOrder.tenant_id == self.tenant_id,
                ProductionOrder.id.in_(ids),
            )
        )
        rows = list((await self.session.execute(ord_stmt)).scalars().all())
        return rows, ids

    async def _fetch_unassigned_completed_orders(self) -> List[ProductionOrder]:
        # Orders with status COMPLETED that have NO row in
        # TransportBatchAssignment for this tenant.
        assigned_stmt = select(TransportBatchAssignment.order_id).where(
            TransportBatchAssignment.tenant_id == self.tenant_id,
        )
        assigned_ids = set(
            (await self.session.execute(assigned_stmt)).scalars().all()
        )
        ord_stmt = select(ProductionOrder).where(
            and_(
                ProductionOrder.tenant_id == self.tenant_id,
                ProductionOrder.status == OrderStatus.COMPLETED.value,
            )
        )
        rows = list((await self.session.execute(ord_stmt)).scalars().all())
        return [r for r in rows if r.id not in assigned_ids]

    async def _fetch_peer_batches(
        self, anchor_date: date,
    ) -> List[TransportBatch]:
        # Window: anchor_date ± 7d. Wide enough to detect swaps within the
        # working week without dragging in unrelated future runs.
        window = timedelta(days=7)
        stmt = select(TransportBatch).where(
            and_(
                TransportBatch.tenant_id == self.tenant_id,
                TransportBatch.transport_date >= anchor_date - window,
                TransportBatch.transport_date <= anchor_date + window,
                TransportBatch.status != "DISPATCHED",
            )
        )
        return list((await self.session.execute(stmt)).scalars().all())
