"""Q.52.K — per-warehouse stock mirror (ERP → supply.warehouse_stock).

The factory tracks stock split across ~20 warehouses (Laminagem, Pintura,
Montagem, Camião Nelo…). The ERP exposes that split through its own view
``dbo.produto_stocks_por_armazem`` (≈8 k rows). This mirror snapshots it
into ``supply.warehouse_stock``:

* ``list_stock_by_warehouse()`` → ``supply.warehouse_stock``

``product_code`` carries the ERP ``P_ID`` (== ``core.products.product_code``),
so the supply API can join the snapshot to the BOM-derived material list.

Idempotent: upsert by ``(product_code, warehouse_id)``. ``synced_at`` is
bumped for every row of the tenant after the upsert so it always reflects
the last sync — without inflating the ``rows_updated`` tally when the
actual stock figure did not change.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import update

from src.adapters.nelo import services
from src.adapters.nelo.schemas import WarehouseStockRow
from src.supply.models import WarehouseStock

from .runner import EtlRunner, EtlRunResult
from .sync import register_mirror

logger = logging.getLogger(__name__)

# The DB column is Numeric(18, 6); the ERP figure is a float. Quantize to
# the same 6 places the column stores so a re-sync of unchanged stock
# compares equal — without this the float→Decimal round-trip differs from
# the stored value and every row counts as "updated" forever.
_Q6 = Decimal("0.000001")


def _map_stock(row: WarehouseStockRow) -> Optional[Dict[str, Any]]:
    """ERP ``produto_stocks_por_armazem`` row → ``supply.warehouse_stock``."""
    if row.product_id is None or row.warehouse_id is None:
        return None
    return {
        "product_code": str(row.product_id),
        "warehouse_id": int(row.warehouse_id),
        "warehouse_name": str(row.warehouse_name or f"Armazém {row.warehouse_id}")[:120],
        "stock": Decimal(str(row.stock or 0)).quantize(_Q6),
    }


async def mirror_stock(
    *,
    session,
    tenant_id: UUID,
    since: Optional[date] = None,
) -> EtlRunResult:
    """Mirror the ERP per-warehouse stock view into ``supply.warehouse_stock``."""
    async with EtlRunner(session, tenant_id, source="stock") as run:
        rows = await services.list_stock_by_warehouse()
        run.count_read(len(rows))
        mapped = [m for m in (_map_stock(r) for r in rows) if m is not None]
        run.count_skipped(len(rows) - len(mapped))
        await run.upsert(
            WarehouseStock,
            mapped,
            key_fields=["product_code", "warehouse_id"],
            update_fields=["warehouse_name", "stock"],
        )
        # `synced_at` reflects the snapshot time for every row — bumped in
        # one statement so an unchanged stock figure is not counted as an
        # "update" in the audit tally.
        await session.execute(
            update(WarehouseStock)
            .where(WarehouseStock.tenant_id == tenant_id)
            .values(synced_at=datetime.now(timezone.utc))
        )
        logger.info(
            "stock mirror — %d warehouse-stock row(s) processed", len(mapped),
        )
    return run.result


register_mirror("stock", mirror_stock)
