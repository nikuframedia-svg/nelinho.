"""
ProdPlan ONE - Report Generators
=================================

One generator per report type. Each takes a session + tenant + period
and returns a JSON-serialisable ``dict`` with a stable shape::

    {
      "report_type": str,
      "period": {"start": iso, "end": iso},
      "rows": [ {...}, ... ],
      "summary": {...},
      "generated_at": iso,
    }

The dict is stored verbatim in ``ReportRun.payload`` (JSONB) and can be
rendered to CSV / JSON for email delivery via :func:`serialize_report`.
"""

import csv
import io
import json
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.hr.models.allocation import HRAllocation
from src.profit.models.cost import CostCalculation
from src.supply.models import InventoryLedgerEntry

logger = logging.getLogger(__name__)


def _num(value: Any) -> float:
    """Coerce a DB numeric (Decimal / None) to a JSON-safe float."""
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _resolve_period(
    period_start: Optional[date], period_end: Optional[date]
) -> tuple[date, date]:
    """Default to the trailing 30 days when no period is supplied."""
    end = period_end or date.today()
    start = period_start or (end - timedelta(days=30))
    return start, end


async def generate_payroll_report(
    session: AsyncSession,
    tenant_id: UUID,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
) -> dict:
    """Per-employee hours + labour cost over the period.

    Sourced from ``hr.hr_allocations`` — actual values where recorded,
    falling back to the allocated/estimated figures.
    """
    start, end = _resolve_period(period_start, period_end)

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
    result = await session.execute(stmt)
    rows = [
        {
            "employee_id": str(employee_id),
            "hours": _num(total_hours),
            "labour_cost_eur": _num(total_cost),
        }
        for employee_id, total_hours, total_cost in result.all()
    ]

    return {
        "report_type": "payroll",
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "rows": rows,
        "summary": {
            "employee_count": len(rows),
            "total_hours": round(sum(r["hours"] for r in rows), 2),
            "total_labour_cost_eur": round(sum(r["labour_cost_eur"] for r in rows), 2),
        },
        "generated_at": datetime.utcnow().isoformat(),
    }


async def generate_cogs_report(
    session: AsyncSession,
    tenant_id: UUID,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
) -> dict:
    """Cost-of-goods breakdown per order over the period.

    Sourced from ``profit.cost_calculations``.
    """
    start, end = _resolve_period(period_start, period_end)
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
    result = await session.execute(stmt)
    rows = [
        {
            "order_id": str(order_id),
            "total_cogs_eur": _num(total),
            "material_cost_eur": _num(material),
            "labor_cost_eur": _num(labor),
            "machine_cost_eur": _num(machine),
            "overhead_cost_eur": _num(overhead),
        }
        for order_id, total, material, labor, machine, overhead in result.all()
    ]

    return {
        "report_type": "cogs",
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "rows": rows,
        "summary": {
            "order_count": len(rows),
            "total_cogs_eur": round(sum(r["total_cogs_eur"] for r in rows), 2),
        },
        "generated_at": datetime.utcnow().isoformat(),
    }


async def generate_inventario_report(
    session: AsyncSession,
    tenant_id: UUID,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
) -> dict:
    """Current on-hand stock per SKU.

    Sourced from ``supply.inventory_ledger_entries``: the most recent
    ledger entry per SKU carries the closing quantity. ``period_*`` is
    accepted for signature symmetry but a stock snapshot is point-in-time.
    """
    del period_start, period_end  # snapshot — not period-bounded

    stmt = (
        select(
            InventoryLedgerEntry.sku_id,
            InventoryLedgerEntry.qty_closing,
            InventoryLedgerEntry.date,
        )
        .where(InventoryLedgerEntry.tenant_id == tenant_id)
        .order_by(InventoryLedgerEntry.sku_id, InventoryLedgerEntry.date.desc())
    )
    result = await session.execute(stmt)

    # Keep the first (most recent) row per SKU.
    latest: dict[str, dict] = {}
    for sku_id, qty_closing, entry_date in result.all():
        if sku_id not in latest:
            latest[sku_id] = {
                "sku_id": sku_id,
                "on_hand": _num(qty_closing),
                "as_of": entry_date.isoformat() if entry_date else None,
            }
    rows = list(latest.values())

    return {
        "report_type": "inventario",
        "period": {"start": None, "end": date.today().isoformat()},
        "rows": rows,
        "summary": {
            "sku_count": len(rows),
            "total_on_hand": round(sum(r["on_hand"] for r in rows), 2),
        },
        "generated_at": datetime.utcnow().isoformat(),
    }


GENERATORS = {
    "payroll": generate_payroll_report,
    "cogs": generate_cogs_report,
    "inventario": generate_inventario_report,
}


async def run_generator(
    report_type: str,
    session: AsyncSession,
    tenant_id: UUID,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
) -> dict:
    """Dispatch to the generator for ``report_type``."""
    generator = GENERATORS.get(report_type)
    if generator is None:
        raise ValueError(f"Unknown report_type: {report_type}")
    return await generator(session, tenant_id, period_start, period_end)


def serialize_report(report: dict, fmt: str) -> str:
    """Render a report dict to ``json`` or ``csv`` text.

    CSV emits the ``rows`` table only; the period/summary metadata lives
    in the JSON form.
    """
    if fmt == "json":
        return json.dumps(report, indent=2, ensure_ascii=False)
    if fmt == "csv":
        rows = report.get("rows", [])
        buf = io.StringIO()
        if rows:
            writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return buf.getvalue()
    raise ValueError(f"Unknown format: {fmt}")
