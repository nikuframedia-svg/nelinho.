"""Q.64.B — material master mirror (ERP → supply.supply_material_master).

`ShortageDetector.scan()` requer linhas activas em `supply_material_master`
para correr — sem isto devolve 404 / lista vazia. A fonte canónica é
`dbo.PRODUTO`.

Mapping:
  * `product_id`     → `sku_id` (string)
  * `product_name`   → `name`
  * `active`         → `active`
  * `lead_time_days` → 7/'default' (placeholder; enriquecido abaixo)
  * `min_stock_qty`  → 0/'default' (placeholder; enriquecido abaixo)
  * `critical_flag`  → False
  * `reorder_qty`    → 0 (default)
  * `unit_of_measure` → 'UN' (ERP não expõe directamente)
  * `category`       → mapeia de `product_type_id`

Q.173.D — passo de enriquecimento após upsert base:
  * `min_stock_qty`   ← `factory_raw.produto."P_STOCKMIN"` (quando >0)
                        `min_stock_source` ← 'erp'
                        (só actualiza onde `min_stock_source` != 'manual')
  * `lead_time_days`  ← `factory_raw.entidade."E_PRAZOENTREGA"` do
                        fornecedor mais recente do produto (quando >0)
                        `lead_time_source` ← 'erp'
                        (só actualiza onde `lead_time_source` != 'manual')
  Materiais sem fonte ERP ficam com os defaults 0/7/'default'.

Idempotente: upsert por `(tenant_id, sku_id)`.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

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


# ---------------------------------------------------------------------------
# Q.173.D — SQL de enriquecimento (testável de forma isolada)
# ---------------------------------------------------------------------------

_ENRICH_MIN_STOCK_SQL = text("""
    UPDATE supply.supply_material_master m
    SET
        min_stock_qty    = p."P_STOCKMIN",
        min_stock_source = 'erp',
        updated_at       = NOW()
    FROM factory_raw.produto p
    WHERE m.tenant_id  = :tenant_id
      AND m.sku_id     = p."P_ID"::text
      AND p."P_STOCKMIN" > 0
      AND m.min_stock_source != 'manual'
""")

_ENRICH_LEAD_TIME_SQL = text("""
    UPDATE supply.supply_material_master m
    SET
        lead_time_days   = e."E_PRAZOENTREGA",
        lead_time_source = 'erp',
        updated_at       = NOW()
    FROM (
        -- Fornecedor mais recente do produto (último MOV_TPMOV_ID=9)
        SELECT DISTINCT ON (mov."MOV_P_ID")
               mov."MOV_P_ID"   AS p_id,
               ent."E_PRAZOENTREGA"
        FROM   factory_raw.movimento mov
        JOIN   factory_raw.entidade  ent
               ON ent."E_ID" = mov."MOV_E_ID"
        WHERE  mov."MOV_TPMOV_ID" = 9
          AND  ent."E_PRAZOENTREGA" > 0
        ORDER BY mov."MOV_P_ID", mov."MOV_ID" DESC
    ) e
    WHERE m.tenant_id        = :tenant_id
      AND m.sku_id            = e.p_id::text
      AND m.lead_time_source != 'manual'
""")


async def _enrich_from_erp(session: AsyncSession, tenant_id: UUID) -> tuple[int, int]:
    """Passo Q.173.D — actualiza min_stock e lead_time a partir do espelho local.

    Só altera linhas onde a fonte não é 'manual' (protege overrides do
    operador). Devolve (rows_min_stock, rows_lead_time) actualizados.
    Isolado numa função própria para ser testável de forma independente.
    """
    params = {"tenant_id": str(tenant_id)}

    result_ms = await session.execute(_ENRICH_MIN_STOCK_SQL, params)
    rows_ms: int = result_ms.rowcount  # type: ignore[assignment]

    result_lt = await session.execute(_ENRICH_LEAD_TIME_SQL, params)
    rows_lt: int = result_lt.rowcount  # type: ignore[assignment]

    logger.info(
        "material_master enrich — min_stock %d linha(s), lead_time %d linha(s)",
        rows_ms, rows_lt,
    )
    return rows_ms, rows_lt


async def mirror_material_master(
    *,
    session,
    tenant_id: UUID,
    since: Optional[date] = None,
) -> EtlRunResult:
    """Mirror `dbo.PRODUTO` → `supply.supply_material_master`.

    Q.64.B — desbloqueia `ShortageDetector.scan()`.
    Q.173.D — passo de enriquecimento com P_STOCKMIN + E_PRAZOENTREGA.
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
            # 'min_stock_source' e 'lead_time_source' NÃO estão em
            # update_fields — o upsert base nunca os toca (preserva 'manual').
        )

        # Passo de enriquecimento: sobrescreve com valores ERP reais
        # (respeita min_stock_source != 'manual' e lead_time_source != 'manual').
        await _enrich_from_erp(session, tenant_id)

        logger.info(
            "material_master mirror — %d product(s) processed (read %d)",
            len(mapped), len(rows),
        )

    return run.result


register_mirror("material_master", mirror_material_master)
