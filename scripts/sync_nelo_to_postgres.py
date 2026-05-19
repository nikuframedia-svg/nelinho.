"""ETL: NELO MAR-KAYAKS → Postgres `production_orders`.

Reads open work orders from the live NELO ERP via the read-only adapter
(`src.adapters.nelo.services`) and upserts them into the local Postgres
`plan.production_orders` table by `legacy_id = OF_ID`. Idempotent: re-run
to refresh; existing rows are UPDATEd, new rows INSERTed.

Scope notes
-----------
- **production_orders**: full sync. Joins ORDEMFABRICO + PRODUTO +
  PRODUTO_TIPO + FASES_PRODUCAO to populate product_name, product_type
  and current_phase_name (fields required by `ProductionOrder`).
- **transport_batch**: NOT synced. `list_current_schedule()` reads
  PLANEAMENTO_DIARIO (NELO daily shift planning — 64 rows, last in
  2019-10-14, schema: day/start/end/headcount). The local `transport_
  batch` table models **truck shipments** (transport_date, truck_capacity_
  units=50, destination). These are semantically distinct — sync would
  produce garbage. Open question for follow-up: build transport_batch
  from distinct `OF_DATATRANSPORTE` values across open orders instead.

Usage
-----
    .\\.venv\\Scripts\\python.exe scripts\\sync_nelo_to_postgres.py [--limit N] [--tenant UUID]

By default: limit=500, tenant=00000000-...-001 (dev).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.nelo.services import close_engine, get_engine as get_nelo_engine
from src.plan.models.order import OrderStatus, ProductionOrder
from src.shared.database import get_session_context

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("sync_nelo")

DEFAULT_TENANT = UUID("00000000-0000-0000-0000-000000000001")


# ─── NELO source query ──────────────────────────────────────────────────
# Joins ORDEMFABRICO with PRODUTO + PRODUTO_TIPO + FASES_PRODUCAO so we
# get the names ProductionOrder needs without a second round-trip.
# Matches the vw_pp1_orders body extended with product_type + phase_name.

_NELO_OPEN_ORDERS_SQL = """
SELECT TOP :limit
    of_.OF_ID                AS work_order_id,
    of_.OF_DATA              AS ordered_at,
    of_.OF_DATAFIM           AS end_date,
    of_.OF_DATATRANSPORTE    AS transport_date,
    of_.OF_P_ID              AS product_id,
    p.P_NOME                 AS product_name,
    pt.TP_NOME               AS product_type,
    of_.OF_FP_ID             AS current_phase_id,
    fp.FP_NOME               AS current_phase_name
FROM        dbo.ORDEMFABRICO  of_  WITH (NOLOCK)
INNER JOIN  dbo.PRODUTO       p    WITH (NOLOCK) ON p.P_ID  = of_.OF_P_ID
LEFT JOIN   dbo.PRODUTO_TIPO  pt   WITH (NOLOCK) ON pt.TP_ID = p.P_TP_ID
INNER JOIN  dbo.FASES_PRODUCAO fp  WITH (NOLOCK) ON fp.FP_ID = of_.OF_FP_ID
WHERE of_.OF_DATAFIM IS NULL
  AND of_.OF_DATA > '1900-01-02'
ORDER BY of_.OF_DATA DESC
"""


# ─── PT-PT product type → internal code (K1/K2/K4/...) ──────────────────
# NELO PRODUTO_TIPO names are human strings ("Canoe Sprint Ep.", "Ocean", …).
# The local ProductionOrder.product_type expects K1/K2/K4/C1/C2/C4/Other.
# Derive from PRODUTO.P_NOME prefix when possible — falls back to "Other".

def derive_product_type(product_name: str | None) -> str:
    if not product_name:
        return "Other"
    head = product_name.strip().split()[0].upper() if product_name.strip() else ""
    if head in {"K1", "K2", "K4", "C1", "C2", "C4"}:
        return head
    return "Other"


# ─── NELO read (SELECT TOP :limit doesn't accept bind in some drivers) ──


async def fetch_open_orders(limit: int) -> list[dict[str, Any]]:
    engine = get_nelo_engine()
    # Interpolate limit as int literal (TOP doesn't accept bind in some
    # ODBC drivers); safe via int() cast.
    sql = _NELO_OPEN_ORDERS_SQL.replace(":limit", str(int(limit)))
    async with engine.connect() as conn:
        result = await conn.execute(text(sql))
        return [dict(r) for r in result.mappings().all()]


# ─── Postgres upsert ────────────────────────────────────────────────────


async def upsert_orders(
    session: AsyncSession,
    tenant_id: UUID,
    nelo_rows: list[dict[str, Any]],
) -> tuple[int, int]:
    """Insert/update each row by (tenant_id, legacy_id). Returns (inserted, updated).

    Uses Postgres `INSERT ... ON CONFLICT (legacy_id) DO UPDATE` since
    `ProductionOrder.legacy_id` has a unique index. xmax/xmin tricks don't
    work cross-version; we approximate inserted vs updated via a pre-count.
    """
    if not nelo_rows:
        return 0, 0

    legacy_ids = [int(r["work_order_id"]) for r in nelo_rows]
    pre = await session.execute(
        text(
            "SELECT legacy_id FROM plan.production_orders "
            "WHERE tenant_id = :tid AND legacy_id = ANY(:ids)"
        ),
        {"tid": str(tenant_id), "ids": legacy_ids},
    )
    existing_ids: set[int] = {row[0] for row in pre}

    table = ProductionOrder.__table__
    rows_to_upsert = []
    for r in nelo_rows:
        wo = int(r["work_order_id"])
        ordered_at = r["ordered_at"]
        transport_date = r["transport_date"]
        end_date = r["end_date"]

        rows_to_upsert.append(
            {
                "tenant_id": tenant_id,
                "legacy_id": wo,
                "product_id": int(r["product_id"]) if r["product_id"] is not None else None,
                "product_name": (r["product_name"] or "").strip()[:255] or "Unknown",
                "product_type": derive_product_type(r["product_name"]),
                "current_phase_id": int(r["current_phase_id"]) if r["current_phase_id"] is not None else None,
                "current_phase_name": (r["current_phase_name"] or "").strip()[:255] or "Unknown",
                "created_date": ordered_at.date() if isinstance(ordered_at, datetime) else ordered_at,
                "transport_date": (
                    transport_date.date()
                    if isinstance(transport_date, datetime)
                    else transport_date
                ),
                "completed_date": end_date.date() if isinstance(end_date, datetime) else end_date,
                "status": OrderStatus.IN_PROGRESS.value,
            }
        )

    # Postgres on-conflict upsert by (tenant_id, legacy_id). The unique
    # index on legacy_id alone (per the ProductionOrder model) makes
    # legacy_id sufficient as the conflict target.
    stmt = pg_insert(table).values(rows_to_upsert)
    update_cols = {
        "product_id": stmt.excluded.product_id,
        "product_name": stmt.excluded.product_name,
        "product_type": stmt.excluded.product_type,
        "current_phase_id": stmt.excluded.current_phase_id,
        "current_phase_name": stmt.excluded.current_phase_name,
        "created_date": stmt.excluded.created_date,
        "transport_date": stmt.excluded.transport_date,
        "completed_date": stmt.excluded.completed_date,
        "status": stmt.excluded.status,
    }
    stmt = stmt.on_conflict_do_update(index_elements=["legacy_id"], set_=update_cols)
    await session.execute(stmt)

    inserted = sum(1 for r in rows_to_upsert if r["legacy_id"] not in existing_ids)
    updated = len(rows_to_upsert) - inserted
    return inserted, updated


# ─── Main ───────────────────────────────────────────────────────────────


async def main(limit: int, tenant_id: UUID) -> int:
    log.info("Starting NELO → Postgres sync (limit=%d, tenant=%s)", limit, tenant_id)
    t0 = time.perf_counter()

    log.info("Reading open work orders from NELO …")
    try:
        rows = await fetch_open_orders(limit)
    except Exception as exc:  # noqa: BLE001
        log.error("NELO read FAILED: %s", exc)
        await close_engine()
        return 1
    log.info("  fetched %d rows from MAR-KAYAKS in %.2fs", len(rows), time.perf_counter() - t0)

    if not rows:
        log.warning("No open orders returned. Nothing to sync.")
        await close_engine()
        return 0

    log.info("Upserting into plan.production_orders …")
    t1 = time.perf_counter()
    try:
        async with get_session_context() as session:
            inserted, updated = await upsert_orders(session, tenant_id, rows)
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        log.exception("Postgres upsert FAILED: %s", exc)
        await close_engine()
        return 1
    log.info("  upsert done in %.2fs", time.perf_counter() - t1)

    # Final counts in Postgres
    async with get_session_context() as session:
        total = (await session.execute(
            text("SELECT COUNT(*) FROM plan.production_orders WHERE tenant_id = :tid"),
            {"tid": str(tenant_id)},
        )).scalar()
        in_progress = (await session.execute(
            text(
                "SELECT COUNT(*) FROM plan.production_orders "
                "WHERE tenant_id = :tid AND status = :st"
            ),
            {"tid": str(tenant_id), "st": OrderStatus.IN_PROGRESS.value},
        )).scalar()

    log.info("Sync summary:")
    log.info("  Fetched from NELO:           %d", len(rows))
    log.info("  Inserted (new legacy_id):    %d", inserted)
    log.info("  Updated  (existing):         %d", updated)
    log.info("  Postgres total rows (tenant): %d", total or 0)
    log.info("  Postgres IN_PROGRESS:        %d", in_progress or 0)
    log.info("Total elapsed: %.2fs", time.perf_counter() - t0)

    # Schedule sync intentionally skipped — see module docstring.
    log.info(
        "Note: transport_batch sync skipped (PLANEAMENTO_DIARIO ≠ truck batches). "
        "See script docstring for follow-up plan."
    )

    await close_engine()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit", type=int, default=500,
        help="Max open orders to pull from NELO (default 500)",
    )
    parser.add_argument(
        "--tenant", type=str, default=str(DEFAULT_TENANT),
        help=f"Target tenant_id (default {DEFAULT_TENANT})",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.limit, UUID(args.tenant))))
