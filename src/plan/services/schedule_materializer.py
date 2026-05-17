"""
ProdPlan ONE — CPO Schedule Materializer (Sprint Q.dev-stack)
==============================================================

The CPO `/schedule` endpoint persists a `ScheduleCommit` (a JSONB blob of
operations). That blob is enough for the copilot and the preview-delta,
but the daily drag-drop allocation (Q.31.D.2) and the operator
start/complete flow (Q.30.A) read relational `plan.production_schedules`
rows — whose `operation_id` is a NOT-NULL FK to `core.operations`.

This module turns the CPO result into those rows:

1. Derives `core.operations` from the routing phases the schedule used —
   one Operation per distinct phase (`operation_code` = phase id). The
   routing phases ARE the operations, so this is a derivation, not
   invented data.
2. Resolves each order's product UUID (`order_id` → `plan.production_orders`
   → `core.products`). Orders with no resolvable product are skipped — a
   `ProductionSchedule.product_id` cannot be NULL.
3. Writes one `ProductionSchedule` per scheduled operation.

A new CPO run supersedes the previous one: prior `cpo_v4` schedule rows
that no operator has started (`actual_start IS NULL`) are deleted before
the insert. Rows an operator already touched survive.
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import delete, select

from src.core.models.operation import Operation, OperationType
from src.core.models.product import Product
from src.plan.models.order import ProductionOrder
from src.plan.models.schedule import ProductionSchedule, ScheduleStatus

logger = logging.getLogger(__name__)


def _parse_dt(value: Any) -> Optional[datetime]:
    """Parse an ISO timestamp from a CPO operation dict."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


async def _resolve_product_uuid(
    session: Any,
    tenant_id: UUID,
    order_id_str: str,
) -> Optional[UUID]:
    """`order_id` (legacy int as string) → `core.products.id` UUID.

    Same chain the COGS endpoint uses: `production_orders.legacy_id`
    yields the legacy product id, which matches `products.product_code`.
    Returns None when any link is missing.
    """
    try:
        legacy = int(order_id_str)
    except (TypeError, ValueError):
        return None
    legacy_product = (await session.execute(
        select(ProductionOrder.product_id).where(
            ProductionOrder.tenant_id == tenant_id,
            ProductionOrder.legacy_id == legacy,
        )
    )).scalar_one_or_none()
    if legacy_product is None:
        return None
    return (await session.execute(
        select(Product.id).where(
            Product.tenant_id == tenant_id,
            Product.product_code == str(legacy_product),
        )
    )).scalar_one_or_none()


async def _ensure_operations(
    session: Any,
    tenant_id: UUID,
    ops: List[Dict[str, Any]],
    phase_codes: set[str],
) -> Tuple[Dict[str, UUID], int]:
    """Get-or-create one `core.operations` row per distinct phase.

    Returns `({phase_code: operation_uuid}, n_created)`. The phase name
    comes from the CPO op's `setup_family` (the human-readable phase
    name), falling back to the code itself.
    """
    existing: Dict[str, UUID] = {}
    if phase_codes:
        result = await session.execute(
            select(Operation.operation_code, Operation.id).where(
                Operation.tenant_id == tenant_id,
                Operation.operation_code.in_(phase_codes),
            )
        )
        for code, oid in result.all():
            existing[str(code)] = oid

    name_by_phase: Dict[str, str] = {}
    for op in ops:
        phase = str(op.get("phase_id") or "")
        if phase and phase not in name_by_phase:
            name_by_phase[phase] = str(op.get("setup_family") or phase)

    created: List[Tuple[str, Operation]] = []
    for code in phase_codes:
        if code in existing:
            continue
        new_op = Operation(
            tenant_id=tenant_id,
            operation_code=code,
            operation_name=name_by_phase.get(code, code),
            operation_type=OperationType.PRODUCTION,
        )
        session.add(new_op)
        created.append((code, new_op))

    if created:
        await session.flush()  # assign UUIDs
        for code, new_op in created:
            existing[code] = new_op.id

    return existing, len(created)


async def materialize_cpo_schedule(
    session: Any,
    tenant_id: UUID,
    result: Dict[str, Any],
    planning_run_id: str,
) -> Dict[str, int]:
    """Turn a CPO `result` dict into `plan.production_schedules` rows.

    Returns counts `{"rows", "operations_created", "orders_skipped"}`.
    Commits the session — the caller's `get_session` dependency would
    otherwise drop the rows after the flush (`session.new` empties, so
    its auto-commit heuristic skips).
    """
    ops: List[Dict[str, Any]] = list(result.get("operations") or [])
    if not ops:
        return {"rows": 0, "operations_created": 0, "orders_skipped": 0}

    # 1. Resolve each order's product UUID, once per order.
    product_by_order: Dict[str, Optional[UUID]] = {}
    for op in ops:
        oid = str(op.get("order_id") or "")
        if oid and oid not in product_by_order:
            product_by_order[oid] = await _resolve_product_uuid(
                session, tenant_id, oid,
            )

    # 2. Ensure a core.operations row per distinct phase.
    phase_codes = {str(op.get("phase_id") or "") for op in ops}
    phase_codes.discard("")
    op_uuid_by_phase, created = await _ensure_operations(
        session, tenant_id, ops, phase_codes,
    )

    # 3. Supersede the previous CPO plan — keep operator-touched rows.
    await session.execute(
        delete(ProductionSchedule).where(
            ProductionSchedule.tenant_id == tenant_id,
            ProductionSchedule.engine_used == "cpo_v4",
            ProductionSchedule.actual_start.is_(None),
        )
    )

    # 4. One ProductionSchedule per op; operation_sequence per order by
    #    start time. Orders with no resolvable product are skipped.
    by_order: Dict[str, List[Dict[str, Any]]] = {}
    for op in ops:
        by_order.setdefault(str(op.get("order_id") or ""), []).append(op)

    run_id = planning_run_id[:50]
    rows = 0
    skipped: set[str] = set()
    for oid, order_ops in by_order.items():
        product_uuid = product_by_order.get(oid)
        if product_uuid is None:
            skipped.add(oid)
            continue
        order_ops.sort(key=lambda o: str(o.get("start_time") or ""))
        seen_ops: set[UUID] = set()
        seq = 0
        for op in order_ops:
            op_uuid = op_uuid_by_phase.get(str(op.get("phase_id") or ""))
            if op_uuid is None or op_uuid in seen_ops:
                # Skip a phase repeated within one order — the
                # (tenant, order, operation, run) unique key forbids it.
                continue
            start = _parse_dt(op.get("start_time"))
            end = _parse_dt(op.get("end_time"))
            if start is None or end is None:
                continue
            seen_ops.add(op_uuid)
            seq += 1
            dur_min = float(op.get("duration_minutes") or 0.0)
            session.add(ProductionSchedule(
                tenant_id=tenant_id,
                order_id=oid,
                product_id=product_uuid,
                quantity=Decimal("1"),
                operation_id=op_uuid,
                operation_sequence=seq,
                machine_id=None,  # CPO "MANUAL" pool — no core.machines row
                scheduled_start_date=start.date(),
                scheduled_start_time=start.time(),
                scheduled_end_date=end.date(),
                scheduled_end_time=end.time(),
                scheduled_duration_hours=Decimal(str(round(dur_min / 60.0, 2))),
                setup_time_minutes=0,
                status=ScheduleStatus.SCHEDULED,
                planning_run_id=run_id,
                engine_used="cpo_v4",
            ))
            rows += 1

    await session.commit()
    summary = {
        "rows": rows,
        "operations_created": created,
        "orders_skipped": len(skipped),
    }
    logger.info(
        "CPO schedule materialized: %d rows, %d operations derived, "
        "%d orders skipped (no product)",
        rows, created, len(skipped),
    )
    return summary
