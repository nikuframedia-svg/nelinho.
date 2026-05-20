"""
ProdPlan ONE - Legacy API Endpoints
====================================

Compatibility endpoints for /api/orders and /api/allocations.
These endpoints provide paginated access to migrated data.
"""

import logging
import math
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session
from src.plan.models.order import ProductionOrder, OrderStatus
from src.hr.models.legacy_allocation import LegacyAllocation
from src.legacy.models import ProductionError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Legacy"])


# Sprint Q.18.A.4: was a local ``get_tenant_id`` that accepted any UUID
# header value (including the zero UUID). That defeated the Q.12 Onda 0.1
# fail-closed guarantee on /api/orders, /api/allocations, /api/errors.
# Reuse the project-wide dependency so 401 / zero-UUID rejection apply
# uniformly across legacy endpoints.
get_tenant_id = require_tenant_header


# ============================================================================
# ORDERS ENDPOINTS — Q.61.32a migrados para /v1/plan/orders/* (src/plan/api/orders.py).
# ============================================================================


# ============================================================================
# ALLOCATIONS ENDPOINTS — Q.61.32b migrados para /v1/workforce/allocations/*
# (src/workforce/api.py).
# ============================================================================


# ============================================================================
# ERRORS ENDPOINTS
# ============================================================================

_EMPTY_ERRORS_STATS = {
    "total": 0,
    "bySeverity": {"minor": 0, "major": 0, "critical": 0},
    "ordersWithErrors": 0,
    "topDescriptions": [],
    "topPhases": [],
}

# ERP 1-3 severity scale → frontend severityLabel (H3 in HANDOFF).
_SEVERITY_LABELS = {1: "Minor", 2: "Major", 3: "Critical"}


@router.get("/api/errors/stats")
async def errors_stats(
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Aggregate statistics over every production error (Sprint Q.22.C).

    Not paginated — counts across the whole ``plan.production_errors``
    table for the tenant. Shape matches the frontend ``ErrorsStats``
    interface. When the DB is unavailable returns an explicit empty
    structure (no 404) so the Qualidade page renders an empty state.
    """
    try:
        total = (
            await session.execute(
                select(func.count())
                .select_from(ProductionError)
                .where(ProductionError.tenant_id == tenant_id)
            )
        ).scalar() or 0

        # Counts per severity bucket.
        severity_rows = (
            await session.execute(
                select(ProductionError.severity, func.count())
                .where(ProductionError.tenant_id == tenant_id)
                .group_by(ProductionError.severity)
            )
        ).all()
        by_severity = {"minor": 0, "major": 0, "critical": 0}
        bucket = {1: "minor", 2: "major", 3: "critical"}
        for severity, count in severity_rows:
            key = bucket.get(severity)
            if key:
                by_severity[key] += count

        # Distinct orders that carry at least one error.
        orders_with_errors = (
            await session.execute(
                select(func.count(func.distinct(ProductionError.order_id)))
                .where(
                    and_(
                        ProductionError.tenant_id == tenant_id,
                        ProductionError.order_id.isnot(None),
                    )
                )
            )
        ).scalar() or 0

        # Top defect descriptions and phases.
        top_desc_rows = (
            await session.execute(
                select(ProductionError.description, func.count().label("c"))
                .where(ProductionError.tenant_id == tenant_id)
                .group_by(ProductionError.description)
                .order_by(func.count().desc())
                .limit(10)
            )
        ).all()
        top_phase_rows = (
            await session.execute(
                select(ProductionError.phase_name, func.count().label("c"))
                .where(ProductionError.tenant_id == tenant_id)
                .group_by(ProductionError.phase_name)
                .order_by(func.count().desc())
                .limit(10)
            )
        ).all()

        return {
            "total": total,
            "bySeverity": by_severity,
            "ordersWithErrors": orders_with_errors,
            "topDescriptions": [
                {"description": desc, "count": count}
                for desc, count in top_desc_rows
            ],
            "topPhases": [
                {"phase": phase, "count": count}
                for phase, count in top_phase_rows
            ],
        }
    except (ConnectionRefusedError, Exception) as e:
        error_str = str(e).lower()
        if any(
            m in error_str
            for m in ("connection refused", "operationalerror", "interfaceerror", "undefinedtable")
        ):
            logger.warning(f"DB unavailable in errors_stats, returning empty: {e}")
            return dict(_EMPTY_ERRORS_STATS)
        raise


@router.get("/api/errors")
async def list_errors(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    pageSize: int = Query(20, ge=1, le=100, description="Items per page"),
    severity: Optional[int] = Query(None, ge=1, le=3, description="Filter by severity 1-3"),
    phase: Optional[str] = Query(None, description="Filter by phase name"),
    search: Optional[str] = Query(None, description="Search in description or phase name"),
    sortBy: str = Query("severity", description="Sort field: id, severity, description, orderId"),
    sortOrder: str = Query("desc", description="Sort order: asc, desc"),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Paginated list of production errors (Sprint Q.22.C).

    Shape matches the frontend ``ErrorsResponse`` (camelCase keys +
    ``hasNextPage`` / ``hasPreviousPage``). When the DB is unavailable
    returns an explicit empty page (no 404).
    """
    try:
        query = select(ProductionError).where(
            ProductionError.tenant_id == tenant_id
        )

        if severity is not None:
            query = query.where(ProductionError.severity == severity)
        if phase:
            query = query.where(ProductionError.phase_name == phase)
        if search:
            pattern = f"%{search}%"
            query = query.where(
                or_(
                    ProductionError.description.ilike(pattern),
                    ProductionError.phase_name.ilike(pattern),
                )
            )

        # Total before pagination.
        total = (
            await session.execute(
                select(func.count()).select_from(query.subquery())
            )
        ).scalar() or 0

        sort_field_map = {
            "id": ProductionError.id,
            "severity": ProductionError.severity,
            "description": ProductionError.description,
            "orderId": ProductionError.order_id,
        }
        sort_field = sort_field_map.get(sortBy, ProductionError.severity)
        query = query.order_by(
            sort_field.asc() if sortOrder.lower() == "asc" else sort_field.desc()
        )

        offset = (page - 1) * pageSize
        query = query.limit(pageSize).offset(offset)

        errors = (await session.execute(query)).scalars().all()
        data = [
            {
                "id": str(err.id),
                "orderId": str(err.order_id) if err.order_id else None,
                "phaseName": err.phase_name,
                "evalPhaseName": err.eval_phase_name,
                "description": err.description,
                "severity": err.severity,
                "severityLabel": _SEVERITY_LABELS.get(err.severity, "Minor"),
            }
            for err in errors
        ]

        total_pages = math.ceil(total / pageSize) if pageSize > 0 else 0
        return {
            "data": data,
            "total": total,
            "page": page,
            "pageSize": pageSize,
            "totalPages": total_pages,
            "hasNextPage": page < total_pages,
            "hasPreviousPage": page > 1,
        }
    except (ConnectionRefusedError, Exception) as e:
        error_str = str(e).lower()
        if any(
            m in error_str
            for m in ("connection refused", "operationalerror", "interfaceerror", "undefinedtable")
        ):
            logger.warning(f"DB unavailable in list_errors, returning empty: {e}")
            return {
                "data": [],
                "total": 0,
                "page": page,
                "pageSize": pageSize,
                "totalPages": 0,
                "hasNextPage": False,
                "hasPreviousPage": False,
            }
        raise
