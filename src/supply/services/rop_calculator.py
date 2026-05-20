"""Q.64.C — ROP (Reorder Point) recompute from inventory ledger history.

Distinto do `src/supply/rop_calculator.ROPCalculator` (math stateless,
recebe inputs ja calculados): este modulo *recalcula* as linhas em
`supply.supply_rop_configs` a partir de `inventory_ledger_entries`
+ `material_master`. Le os ultimos N dias de qty_out por SKU activo,
deriva `avg_daily_demand`, lead time vem do master, e aplica a formula
classica de inventory management:

    avg_daily_demand = sum(qty_out ultimos N dias) / N
    base_rop         = avg_daily_demand x lead_time_days
    safety_stock     = z_score x sqrt(lead_time_days) x avg_daily_demand x variability
    rop              = base_rop + safety_stock

Z-score sem dependencia de scipy — tabela hardcoded para 0.90/0.95/0.97/
0.99 (suficiente para os service levels que usamos). `service_level`
fora destes valores cai no mais proximo (`min(abs(k - sl))`).

Idempotente: upsert por (tenant_id, sku_id) — segunda chamada substitui
em vez de duplicar.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.supply.models import (
    InventoryLedgerEntry,
    MaterialMaster,
    ROPConfig,
)

logger = logging.getLogger(__name__)


# Z-scores para niveis de servico comuns (norm.ppf). Sem scipy.
_Z_SCORE_BY_SERVICE_LEVEL: dict[float, float] = {
    0.90: 1.282,
    0.95: 1.645,
    0.97: 1.881,
    0.99: 2.326,
}


def _z_score_for(service_level: float) -> float:
    """Aproximacao z-score sem scipy.

    Devolve o z-score do nivel de servico mais proximo na tabela. Para
    0.95 (default) devolve 1.645. service_level fora de [0.5, 1.0] e
    aceite pelo `min` — o caller (api endpoint) ja valida o range.
    """
    closest = min(
        _Z_SCORE_BY_SERVICE_LEVEL.keys(),
        key=lambda k: abs(k - service_level),
    )
    return _Z_SCORE_BY_SERVICE_LEVEL[closest]


async def recompute_rop_configs(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    lookback_days: int = 90,
    service_level: float = 0.95,
    variability_factor: float = 0.3,
) -> dict[str, int]:
    """Recalcula `ROPConfig` para cada SKU activo do tenant.

    Le `MaterialMaster` (active=True), soma `InventoryLedgerEntry.qty_out`
    nos ultimos `lookback_days`, e faz upsert em `ROPConfig` por
    (tenant_id, sku_id). SKUs sem consumo (avg_daily_demand <= 0) sao
    saltados — ROP zero seria mentir.

    Args:
        session: async session ligada ao tenant.
        tenant_id: tenant alvo.
        lookback_days: janela historica para avg_daily_demand. Default 90d.
        service_level: 0.95 (default) = stockout em 5% das semanas.
        variability_factor: proxy para coeficiente de variacao (CV) da
            demanda. 0.3 = 30% de variabilidade — adequado para materiais
            de fabrica com consumo regular.

    Returns:
        dict com `rows_processed`, `rows_upserted`, `rows_skipped`.

    Note:
        Chama `session.flush()` no fim — o caller e que faz `commit()`.
    """
    since = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    z_score = _z_score_for(service_level)

    # 1. Listar SKUs activos.
    masters_stmt = select(MaterialMaster).where(
        and_(
            MaterialMaster.tenant_id == tenant_id,
            MaterialMaster.active.is_(True),
        )
    )
    masters = (await session.execute(masters_stmt)).scalars().all()

    rows_processed = 0
    rows_upserted = 0
    rows_skipped = 0

    for master in masters:
        rows_processed += 1

        # 2. Sum qty_out na janela.
        out_stmt = select(
            func.coalesce(func.sum(InventoryLedgerEntry.qty_out), 0)
        ).where(
            and_(
                InventoryLedgerEntry.tenant_id == tenant_id,
                InventoryLedgerEntry.sku_id == master.sku_id,
                InventoryLedgerEntry.date >= since,
            )
        )
        total_demand_raw = (await session.execute(out_stmt)).scalar()
        total_demand = Decimal(str(total_demand_raw or 0))
        avg_daily_demand = total_demand / Decimal(str(lookback_days))

        if avg_daily_demand <= 0:
            rows_skipped += 1
            continue

        # 3. Aplicar formula.
        lead_time_days = max(int(master.lead_time_days or 7), 1)
        sqrt_lead = math.sqrt(lead_time_days)
        lead_time_std_dev = sqrt_lead * variability_factor

        base_rop = avg_daily_demand * Decimal(str(lead_time_days))
        safety_stock = (
            Decimal(str(z_score))
            * Decimal(str(sqrt_lead))
            * avg_daily_demand
            * Decimal(str(variability_factor))
        )
        rop = base_rop + safety_stock

        # 4. Upsert ROPConfig.
        existing_stmt = select(ROPConfig).where(
            and_(
                ROPConfig.tenant_id == tenant_id,
                ROPConfig.sku_id == master.sku_id,
            )
        )
        existing = (
            await session.execute(existing_stmt)
        ).scalar_one_or_none()

        if existing is None:
            row = ROPConfig(
                tenant_id=tenant_id,
                sku_id=master.sku_id,
                avg_daily_demand=avg_daily_demand,
                lead_time_days=lead_time_days,
                lead_time_std_dev=lead_time_std_dev,
                service_level=service_level,
                rop=rop,
                base_rop=base_rop,
                safety_stock=safety_stock,
                z_score=z_score,
            )
            # Q.66.B.3: ROPConfig e resultado calculado de reorder point
            # (avg_daily_demand x lead_time x z-score), nao state autoritativo
            # — re-correr o calculator regenera. Audit so em adopcao manual.
            session.add(row)  # noqa: audit_coverage  # ROP calc result, not gov state
        else:
            existing.avg_daily_demand = avg_daily_demand
            existing.lead_time_days = lead_time_days
            existing.lead_time_std_dev = lead_time_std_dev
            existing.service_level = service_level
            existing.rop = rop
            existing.base_rop = base_rop
            existing.safety_stock = safety_stock
            existing.z_score = z_score

        rows_upserted += 1

    await session.flush()
    logger.info(
        "ROP recompute: %d processed, %d upserted, %d skipped (no demand)",
        rows_processed,
        rows_upserted,
        rows_skipped,
    )
    return {
        "rows_processed": rows_processed,
        "rows_upserted": rows_upserted,
        "rows_skipped": rows_skipped,
    }


__all__ = ["recompute_rop_configs", "_z_score_for"]
