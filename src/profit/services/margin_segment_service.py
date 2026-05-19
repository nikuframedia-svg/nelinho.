"""Margin segmentation service (Sprint Q.43 / F7).

Answers the CEO question "quem dá lucro vs quem dá só volume" by
aggregating per-order margin across three commercial dimensions:

    * ``customer``  — o cliente real (ENTIDADE.E_NOME do ERP)
    * ``country``   — o país do cliente (ENTIDADE.E_PAIS do ERP)
    * ``agent``     — o agente comercial

Source: ``src.adapters.nelo.services.list_open_orders`` returns one
``OrderRow`` per open work order, each carrying ``sale_price``
(OF_PRECOVENDA), ``cost_price`` (OF_PRECOCUSTO), the real customer name
and the customer country (joined from ``dbo.ENTIDADE``).

Per-order margin here is ``sale_price - cost_price`` straight from the
ERP. This is deliberately a different number from
``GET /v1/profit/orders/margins`` (which uses the COGS engine's
``CostCalculation``): the ERP pair is the only path that today carries a
*real* customer FK, so segmentation by customer/country must use it.

Honesty about missing dimensions
--------------------------------
* ``customer`` and ``country`` have data today — the ERP join is live.
* ``agent`` (agente comercial) has **no adapter reader**: it lives in the
  ERP tables ``AgenteEncomenda`` / ``ENTIDADE_PHC_FACT`` which depend on
  the F1 ERP sync. Until that lands, the ``agent`` dimension returns an
  explicit empty result with ``dimension_available=False`` and a reason
  string. ZERO MOCKS — no invented agent names, no fallback.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal

from src.adapters.nelo.schemas import OrderRow
from src.adapters.nelo.services import list_open_orders

log = logging.getLogger(__name__)

Dimension = Literal["customer", "country", "agent"]
DIMENSIONS: tuple[Dimension, ...] = ("customer", "country", "agent")

# The ``agent`` dimension cannot be served from local Postgres or the
# current read-only ERP adapter — it depends on the F1 ERP sync exposing
# AgenteEncomenda / ENTIDADE_PHC_FACT.
AGENT_PENDING_REASON = (
    "Agente comercial vive nas tabelas ERP AgenteEncomenda / "
    "ENTIDADE_PHC_FACT — sem reader no adapter. Fica vazio até ao sync ERP (F1)."
)

DEFAULT_MAX_ORDERS = 100_000
UNKNOWN_LABEL = "—"

OrderFetcher = Callable[[int], Awaitable[list[OrderRow]]]


# ─── Result shapes ──────────────────────────────────────────────────────


@dataclass
class SegmentRow:
    """Margin aggregate for one segment value (one customer / country)."""

    segment_value: str
    order_count: int
    revenue_eur: float
    cost_eur: float
    margin_eur: float = field(init=False)
    margin_pct: float | None = field(init=False, default=None)
    avg_margin_eur: float = field(init=False)

    def __post_init__(self) -> None:
        self.margin_eur = round(self.revenue_eur - self.cost_eur, 2)
        self.revenue_eur = round(self.revenue_eur, 2)
        self.cost_eur = round(self.cost_eur, 2)
        if self.revenue_eur > 0:
            self.margin_pct = round(self.margin_eur / self.revenue_eur, 4)
        self.avg_margin_eur = (
            round(self.margin_eur / self.order_count, 2)
            if self.order_count > 0
            else 0.0
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_value": self.segment_value,
            "order_count": self.order_count,
            "revenue_eur": self.revenue_eur,
            "cost_eur": self.cost_eur,
            "margin_eur": self.margin_eur,
            "margin_pct": self.margin_pct,
            "avg_margin_eur": self.avg_margin_eur,
        }


@dataclass
class SegmentMarginResult:
    dimension: Dimension
    dimension_available: bool
    rows: list[SegmentRow]
    order_count: int
    total_margin_eur: float
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "dimension_available": self.dimension_available,
            "reason": self.reason,
            "order_count": self.order_count,
            "total_margin_eur": round(self.total_margin_eur, 2),
            "segment_count": len(self.rows),
            "items": [r.to_dict() for r in self.rows],
        }


# ─── Service ────────────────────────────────────────────────────────────


class MarginSegmentService:
    """Stateless service. Pass in a fetcher (defaults to NELO adapter)."""

    def __init__(
        self,
        fetcher: OrderFetcher | None = None,
        max_orders: int = DEFAULT_MAX_ORDERS,
    ) -> None:
        self._fetcher = fetcher or list_open_orders
        self._max_orders = max_orders

    async def by_segment(self, dimension: Dimension) -> SegmentMarginResult:
        if dimension not in DIMENSIONS:
            raise ValueError(f"Unknown dimension: {dimension}")

        # ``agent`` is structurally supported but has no data source
        # today. Return an explicit empty result — never invent agents.
        if dimension == "agent":
            return SegmentMarginResult(
                dimension=dimension,
                dimension_available=False,
                rows=[],
                order_count=0,
                total_margin_eur=0.0,
                reason=AGENT_PENDING_REASON,
            )

        orders = await self._fetcher(self._max_orders)
        return self._aggregate(dimension, orders)

    def _aggregate(
        self, dimension: Dimension, orders: list[OrderRow]
    ) -> SegmentMarginResult:
        """Group ERP orders by the chosen dimension and sum margin.

        Per-order margin is ``sale_price - cost_price`` — both prices are
        non-nullable on ``OrderRow`` (OF_PRECOVENDA / OF_PRECOCUSTO)."""
        buckets: dict[str, dict[str, float]] = {}
        for o in orders:
            key = self._segment_key(dimension, o)
            bucket = buckets.setdefault(
                key, {"order_count": 0, "revenue_eur": 0.0, "cost_eur": 0.0}
            )
            bucket["order_count"] += 1
            bucket["revenue_eur"] += float(o.sale_price)
            bucket["cost_eur"] += float(o.cost_price)

        rows = [
            SegmentRow(
                segment_value=key,
                order_count=int(b["order_count"]),
                revenue_eur=b["revenue_eur"],
                cost_eur=b["cost_eur"],
            )
            for key, b in buckets.items()
        ]
        # Lowest margin first — the CEO wants to see who loses money.
        rows.sort(key=lambda r: r.margin_eur)
        total_margin = round(sum(r.margin_eur for r in rows), 2)

        return SegmentMarginResult(
            dimension=dimension,
            dimension_available=True,
            rows=rows,
            order_count=sum(r.order_count for r in rows),
            total_margin_eur=total_margin,
        )

    @staticmethod
    def _segment_key(dimension: Dimension, order: OrderRow) -> str:
        """Resolve the segment label for an order.

        ``customer`` prefers the real ENTIDADE name (``customer_full_name``)
        and only falls back to the free-text ``customer_name`` on the work
        order when the entity FK is absent. ``country`` reads
        ``customer_country`` (ENTIDADE.E_PAIS)."""
        if dimension == "customer":
            name = order.customer_full_name or order.customer_name
            return (name or UNKNOWN_LABEL).strip() or UNKNOWN_LABEL
        if dimension == "country":
            return (order.customer_country or UNKNOWN_LABEL).strip() or UNKNOWN_LABEL
        raise ValueError(f"Dimension {dimension} has no order-level key")
