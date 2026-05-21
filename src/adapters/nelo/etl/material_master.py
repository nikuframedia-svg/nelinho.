"""Q.64.B — material master mirror (ERP → supply.supply_material_master).

`ShortageDetector.scan()` requer linhas activas em `supply_material_master`
para correr — sem isto devolve 404 / lista vazia. A fonte canónica é
`dbo.PRODUTO`.

Mapping:
  * `product_id`     → `sku_id` (string)
  * `product_name`   → `name`
  * `cost_price`     → metadata (não persistido aqui; PRODUTO_STOCKS tem isso)
  * `active`         → `active`
  * `lead_time_days` → default 7 (não há fonte directa em PRODUTO; placeholder)
  * `min_stock_qty`  → default 0 (P_STOCKMIN está em ProductStockRow, mirror
                       futuro pode actualizar)
  * `critical_flag`  → False (decisão produto futura — Q.65?)
  * `reorder_qty`    → 0 (default)
  * `unit_of_measure` → "UN" (default — ERP não expõe directamente)
  * `category`       → mapeia de `product_type_id` se útil

Idempotente: upsert por `(tenant_id, sku_id)`.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID

from src.adapters.nelo import services
from src.adapters.nelo.schemas import ProductRow
from src.supply.models import MaterialMaster

from .runner import EtlRunner, EtlRunResult
from .sync import register_mirror

logger = logging.getLogger(__name__)


def _map_product(row: ProductRow) -> Optional[Dict[str, Any]]:
    """`ProductRow` → linha para `supply_material_master`."""
    if row.product_id is None:
        return None

    return {
        "sku_id": str(row.product_id),
        "name": (row.product_name or f"P_{row.product_id}")[:255],
        "description": None,
        "unit_of_measure": "UN",
        "category": (
            f"type_{row.product_type_id}" if row.product_type_id else None
        ),
        "default_supplier_id": None,
        "lead_time_days": 7,
        "min_stock_qty": Decimal("0"),
        "reorder_qty": Decimal("0"),
        "critical_flag": False,
        "active": bool(row.active) and not bool(row.discontinued),
    }


async def mirror_material_master(
    *,
    session,
    tenant_id: UUID,
    since: Optional[date] = None,
) -> EtlRunResult:
    """Mirror `dbo.PRODUTO` → `supply.supply_material_master`.

    Q.64.B — desbloqueia `ShortageDetector.scan()`.
    """
    async with EtlRunner(session, tenant_id, source="material_master") as run:
        rows = await services.list_products(limit=50_000)
        run.count_read(len(rows))

        mapped = [m for m in (_map_product(r) for r in rows) if m is not None]
        run.count_skipped(len(rows) - len(mapped))

        await run.upsert(
            MaterialMaster,
            mapped,
            key_fields=["sku_id"],
            update_fields=[
                "name", "description", "unit_of_measure", "category",
                "lead_time_days", "min_stock_qty", "reorder_qty",
                "critical_flag", "active",
            ],
        )
        logger.info(
            "material_master mirror — %d product(s) processed (read %d)",
            len(mapped), len(rows),
        )

    return run.result


register_mirror("material_master", mirror_material_master)
