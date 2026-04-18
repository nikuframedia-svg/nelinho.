"""
ProdPlan ONE - Priority Report API (Sprint Q.6 / CS06)
========================================================

Exposes how the scheduler's priority ordering relates to the revenue value
of each order. Callers plug this into the Timeline UI so planners can
inspect whether the GA is actually maximising €/dia — or whether a few
high-value orders are getting bumped by tardiness constraints.

Endpoint:
    GET /v1/plan/priority-report?commit_sha=<sha>

When `commit_sha` is omitted, the latest commit for the tenant is used.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.cpo.commits import CommitsService
from src.profit.models.pricing import OrderRevenue
from src.shared.database import get_session

router = APIRouter(tags=["Plan"])


def get_tenant_id(x_tenant_id: UUID = Header(..., alias="X-Tenant-Id")) -> UUID:
    return x_tenant_id


@router.get("/priority-report")
async def priority_report(
    commit_sha: Optional[str] = Query(None),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    svc = CommitsService(session, tenant_id)
    commit = None
    if commit_sha:
        commit = await svc.get_by_sha(commit_sha) or await svc.get_by_sha_prefix(commit_sha)
    else:
        commit = await svc.get_latest()
    if commit is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="No commit available for priority report",
        )

    ops = list(commit.operations or [])
    order_ids = sorted({str(op.get("order_id") or "") for op in ops if op.get("order_id")})

    revenue_by_order = await _revenue_by_order(session, tenant_id, order_ids)
    order_first_index = _order_first_index(ops)

    items: list[dict[str, Any]] = []
    for order_id, first_idx in sorted(order_first_index.items(), key=lambda kv: kv[1]):
        revenue = revenue_by_order.get(order_id, Decimal("0"))
        items.append({
            "order_id": order_id,
            "first_op_index": first_idx,
            "revenue_eur": float(revenue),
        })

    # Correlation indicator — Spearman-style: is higher revenue served earlier?
    ranks_by_revenue = _rank_by_revenue(items)
    inversions = _count_inversions(ranks_by_revenue)
    # Smaller inversion count = scheduler matches revenue order; max = n*(n-1)/2.
    max_inversions = max(1, len(items) * (len(items) - 1) / 2)
    alignment = max(0.0, 1.0 - inversions / max_inversions)

    return {
        "commit_sha256": commit.commit_sha256,
        "items": items,
        "alignment_pct": round(alignment * 100, 2),
        "inversions": inversions,
        "max_inversions": int(max_inversions),
    }


async def _revenue_by_order(
    session: AsyncSession, tenant_id: UUID, order_ids: list[str],
) -> dict[str, Decimal]:
    if not order_ids:
        return {}
    stmt = select(OrderRevenue).where(
        and_(
            OrderRevenue.tenant_id == tenant_id,
            OrderRevenue.order_id.in_(order_ids),
        )
    )
    rows = (await session.execute(stmt)).scalars().all()
    return {r.order_id: Decimal(str(r.total_revenue_eur)) for r in rows}


def _order_first_index(ops: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for idx, op in enumerate(ops):
        order_id = str(op.get("order_id") or "")
        if not order_id or order_id in out:
            continue
        out[order_id] = idx
    return out


def _rank_by_revenue(items: list[dict[str, Any]]) -> list[int]:
    """Return a list of ranks: position i holds the rank of items[i] when
    ordered by revenue DESC. Ties broken by first_op_index."""
    indexed = list(enumerate(items))
    indexed.sort(key=lambda kv: (-kv[1]["revenue_eur"], kv[1]["first_op_index"]))
    ranks = [0] * len(items)
    for rank, (orig_idx, _) in enumerate(indexed):
        ranks[orig_idx] = rank
    return ranks


def _count_inversions(arr: list[int]) -> int:
    """Count pair-wise inversions (i<j but arr[i] > arr[j])."""
    count = 0
    n = len(arr)
    for i in range(n):
        for j in range(i + 1, n):
            if arr[i] > arr[j]:
                count += 1
    return count
