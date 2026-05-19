"""
ProdPlan ONE - Margin Segmentation Service (Sprint Q.53.C)
===========================================================

Powers `GET /v1/profit/margin-by-segment`. Today the profit module only
exposes *aggregate* margin (`/orders/margin-summary`); the Direção page
needs margin broken down by a business dimension — country (from the
customer) or commercial agent.

The data comes from the live NELO ERP via the read-only adapter
(`src.adapters.nelo.services.list_open_orders`), which carries
`customer_country`, `sale_price` and `cost_price` per work order. When
the adapter is not configured/reachable (e.g. dev without SQL Server),
the service degrades honestly: `erp_available=False` with a reason — it
never invents numbers.

Margin per order = `sale_price - cost_price`. Both come straight from
`ORDEMFABRICO` (`OF_PRECOVENDA` / `OF_PRECOCUSTO`). CoeficienteX
(`OF_COEFICIENTE`) is deliberately NOT used here — it is DINHEIRO but a
different figure, and mixing it into a margin breakdown would be wrong.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Dimensions the segmentation supports. `country` reads the customer
# country; `agent` reads the commercial agent reference.
SUPPORTED_DIMENSIONS = ("country", "agent")


@dataclass(frozen=True)
class SegmentRow:
    """Aggregated margin for one segment value."""

    segment: str
    order_count: int
    revenue_eur: float
    cogs_eur: float
    margin_eur: float
    margin_pct: Optional[float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment": self.segment,
            "order_count": self.order_count,
            "revenue_eur": round(self.revenue_eur, 2),
            "cogs_eur": round(self.cogs_eur, 2),
            "margin_eur": round(self.margin_eur, 2),
            "margin_pct": (
                round(self.margin_pct, 4) if self.margin_pct is not None else None
            ),
        }


class MarginSegmentService:
    """Breaks the open-order book down into margin-by-dimension rows."""

    def __init__(self, *, order_limit: int = 5000) -> None:
        self.order_limit = order_limit

    async def margin_by_segment(self, dimension: str) -> dict[str, Any]:
        """Aggregate `sale_price - cost_price` grouped by `dimension`.

        Returns a 200-shaped dict always — when the ERP is offline or the
        dimension has no usable data, `erp_available`/segment list reflect
        that honestly.
        """
        dim = dimension.lower()
        if dim not in SUPPORTED_DIMENSIONS:
            raise ValueError(
                f"dimension inválida: {dimension!r} — "
                f"usa uma de {SUPPORTED_DIMENSIONS}"
            )

        from src.adapters.nelo import services as nelo

        try:
            orders = await nelo.list_open_orders(limit=self.order_limit)
        except (RuntimeError, OSError) as exc:
            # Same degradation contract as GET /v1/profit/oee — the
            # frontend honest-empty-state hook reads `erp_available`.
            logger.warning(
                "margin-by-segment indisponível — adaptador NELO offline: %s",
                exc,
            )
            return {
                "dimension": dim,
                "segments": [],
                "total": _empty_total(),
                "erp_available": False,
                "unavailable_reason": (
                    "Os dados de margem por segmento vêm do ERP NELO "
                    "(SQL Server / ORDEMFABRICO), que não está ligado "
                    "neste ambiente."
                ),
            }

        return self._aggregate(dim, orders)

    def _aggregate(self, dim: str, orders: list[Any]) -> dict[str, Any]:
        """Pure aggregation of `OrderRow`s into segment buckets."""
        buckets: dict[str, dict[str, float]] = {}
        skipped_no_dimension = 0

        for o in orders:
            key = self._segment_key(dim, o)
            if key is None:
                skipped_no_dimension += 1
                continue
            sale = float(getattr(o, "sale_price", 0.0) or 0.0)
            cost = float(getattr(o, "cost_price", 0.0) or 0.0)
            b = buckets.setdefault(
                key, {"count": 0.0, "revenue": 0.0, "cogs": 0.0}
            )
            b["count"] += 1
            b["revenue"] += sale
            b["cogs"] += cost

        rows: list[SegmentRow] = []
        for key, b in buckets.items():
            revenue = b["revenue"]
            cogs = b["cogs"]
            margin = revenue - cogs
            rows.append(
                SegmentRow(
                    segment=key,
                    order_count=int(b["count"]),
                    revenue_eur=revenue,
                    cogs_eur=cogs,
                    margin_eur=margin,
                    margin_pct=(margin / revenue) if revenue > 0 else None,
                )
            )
        rows.sort(key=lambda r: r.margin_eur, reverse=True)

        total_revenue = sum(r.revenue_eur for r in rows)
        total_cogs = sum(r.cogs_eur for r in rows)
        total_margin = total_revenue - total_cogs
        total = {
            "order_count": sum(r.order_count for r in rows),
            "revenue_eur": round(total_revenue, 2),
            "cogs_eur": round(total_cogs, 2),
            "margin_eur": round(total_margin, 2),
            "margin_pct": (
                round(total_margin / total_revenue, 4)
                if total_revenue > 0
                else None
            ),
        }

        # The dimension may be present in the ERP but unpopulated for
        # every row — be honest rather than returning an empty list with
        # no explanation.
        has_data = len(rows) > 0
        return {
            "dimension": dim,
            "segments": [r.to_dict() for r in rows],
            "total": total,
            "skipped_no_dimension": skipped_no_dimension,
            "erp_available": True,
            "unavailable_reason": (
                None
                if has_data
                else (
                    f"O ERP respondeu, mas nenhuma ordem tem a dimensão "
                    f"'{dim}' preenchida — sem dados para segmentar."
                )
            ),
        }

    @staticmethod
    def _segment_key(dim: str, order: Any) -> Optional[str]:
        """Resolve the segment label for one order, or None when absent."""
        if dim == "country":
            raw = getattr(order, "customer_country", None)
        else:  # agent
            # The ERP carries the commercial reference on `reference`;
            # there is no dedicated agent column today, so we use it as
            # the agent proxy. Empty → skipped (degrades honestly).
            raw = getattr(order, "reference", None)
        if raw is None:
            return None
        label = str(raw).strip()
        return label or None


def _empty_total() -> dict[str, Any]:
    return {
        "order_count": 0,
        "revenue_eur": 0.0,
        "cogs_eur": 0.0,
        "margin_eur": 0.0,
        "margin_pct": None,
    }
