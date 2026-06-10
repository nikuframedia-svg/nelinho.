"""ProdPlan ONE — Report generators (Sprint Q.22.E).

One generator per report type. Each takes a session + tenant + period
and returns ``list[dict]`` — the report rows — ready for the
``/v1/reports/generate`` dispatcher to render to CSV / JSON.

These delegate to the live domain tables (no aggregation logic is
reinvented): ``hr.hr_allocations``, ``profit.cost_calculations``,
``supply.inventory_ledger_entries``. When a table has no rows for the
tenant the generator returns ``[]`` — the dispatcher reports
``status="ready"`` with ``row_count=0`` and the UI shows an empty
state. ZERO MOCKS: never a placeholder row.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.time import local_today

logger = logging.getLogger("reports.generators")


def _num(value: Any) -> float:
    """Coerce a DB numeric (Decimal / None) to a JSON-safe float."""
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _resolve_period(
    since: date | None, until: date | None
) -> tuple[date, date]:
    """Default to the trailing 30 days when no period is supplied."""
    end = until or local_today()
    start = since or (end - timedelta(days=30))
    return start, end


async def generate_payroll(
    session: AsyncSession,
    tenant_id: UUID,
    since: date | None = None,
    until: date | None = None,
) -> list[dict[str, Any]]:
    """Per-employee hours + labour cost over the period.

    Sourced from ``hr.hr_allocations`` — actual values where recorded,
    falling back to the allocated / estimated figures.
    """
    from src.hr.models.allocation import HRAllocation

    start, end = _resolve_period(since, until)
    hours = func.coalesce(HRAllocation.actual_hours, HRAllocation.allocated_hours)
    cost = func.coalesce(HRAllocation.actual_cost, HRAllocation.estimated_cost)

    stmt = (
        select(
            HRAllocation.employee_id,
            func.sum(hours),
            func.sum(cost),
        )
        .where(
            HRAllocation.tenant_id == tenant_id,
            HRAllocation.allocation_date >= start,
            HRAllocation.allocation_date <= end,
        )
        .group_by(HRAllocation.employee_id)
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "employee_id": str(employee_id),
            "hours": round(_num(total_hours), 2),
            "labour_cost_eur": round(_num(total_cost), 2),
        }
        for employee_id, total_hours, total_cost in rows
    ]


async def generate_cogs(
    session: AsyncSession,
    tenant_id: UUID,
    since: date | None = None,
    until: date | None = None,
) -> list[dict[str, Any]]:
    """Cost-of-goods breakdown per order over the period.

    Sourced from ``profit.cost_calculations``.
    """
    from src.profit.models.cost import CostCalculation

    start, end = _resolve_period(since, until)
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end, datetime.max.time())

    stmt = (
        select(
            CostCalculation.order_id,
            func.sum(CostCalculation.total_cogs),
            func.sum(CostCalculation.material_cost),
            func.sum(CostCalculation.labor_cost),
            func.sum(CostCalculation.machine_cost),
            func.sum(CostCalculation.overhead_cost),
        )
        .where(
            CostCalculation.tenant_id == tenant_id,
            CostCalculation.calculated_at >= start_dt,
            CostCalculation.calculated_at <= end_dt,
        )
        .group_by(CostCalculation.order_id)
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "order_id": str(order_id),
            "total_cogs_eur": round(_num(total), 2),
            "material_cost_eur": round(_num(material), 2),
            "labor_cost_eur": round(_num(labor), 2),
            "machine_cost_eur": round(_num(machine), 2),
            "overhead_cost_eur": round(_num(overhead), 2),
        }
        for order_id, total, material, labor, machine, overhead in rows
    ]


async def generate_inventario(
    session: AsyncSession,
    tenant_id: UUID,
    since: date | None = None,
    until: date | None = None,
) -> list[dict[str, Any]]:
    """Current on-hand stock per SKU.

    Sourced from ``supply.inventory_ledger_entries``: the most recent
    ledger entry per SKU carries the closing quantity. ``since`` /
    ``until`` are accepted for signature symmetry but stock is a
    point-in-time snapshot.
    """
    del since, until  # snapshot — not period-bounded
    from src.supply.models import InventoryLedgerEntry

    stmt = (
        select(
            InventoryLedgerEntry.sku_id,
            InventoryLedgerEntry.qty_closing,
            InventoryLedgerEntry.date,
        )
        .where(InventoryLedgerEntry.tenant_id == tenant_id)
        .order_by(InventoryLedgerEntry.sku_id, InventoryLedgerEntry.date.desc())
    )
    rows = (await session.execute(stmt)).all()

    # Keep the first (most recent) row per SKU.
    latest: dict[str, dict] = {}
    for sku_id, qty_closing, entry_date in rows:
        if sku_id not in latest:
            latest[sku_id] = {
                "sku_id": sku_id,
                "on_hand": round(_num(qty_closing), 2),
                "as_of": entry_date.isoformat() if entry_date else None,
            }
    return list(latest.values())


# Dispatch table — keyed by the report template id.
GENERATORS = {
    "payroll": generate_payroll,
    "cogs": generate_cogs,
    "inventario": generate_inventario,
}


async def run_generator(
    template_id: str,
    session: AsyncSession,
    tenant_id: UUID,
    since: date | None = None,
    until: date | None = None,
) -> list[dict[str, Any]]:
    """Dispatch to the generator for ``template_id``.

    Raises ``KeyError`` if the template has no generator — the caller
    (``/v1/reports/generate``) guards this with the Pydantic Literal.
    """
    generator = GENERATORS[template_id]
    return await generator(session, tenant_id, since, until)
