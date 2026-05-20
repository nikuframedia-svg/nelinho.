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
# ALLOCATIONS ENDPOINTS
# ============================================================================

@router.get("/api/allocations")
async def list_allocations(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    pageSize: int = Query(20, ge=1, le=100, description="Items per page"),
    employeeId: Optional[int] = Query(None, description="Filter by employee ID"),
    phase: Optional[str] = Query(None, description="Filter by phase name"),
    isLeader: Optional[bool] = Query(None, description="Filter by leader status"),
    search: Optional[str] = Query(None, description="Search in employee name, phase, or order ID"),
    sortBy: str = Query("startDate", description="Sort field: startDate, employeeName, phaseName, id"),
    sortOrder: str = Query("desc", description="Sort order: asc, desc"),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Get paginated list of employee allocations."""
    try:
        # Build query
        query = select(LegacyAllocation).where(LegacyAllocation.tenant_id == tenant_id)
        
        # Filters
        if employeeId:
            query = query.where(LegacyAllocation.employee_id == employeeId)
        
        if phase:
            query = query.where(LegacyAllocation.phase_name.ilike(f"%{phase}%"))
        
        if isLeader is not None:
            query = query.where(LegacyAllocation.is_leader == isLeader)
        
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    LegacyAllocation.employee_name.ilike(search_pattern),
                    LegacyAllocation.phase_name.ilike(search_pattern),
                    LegacyAllocation.order_id.cast(str).ilike(search_pattern),
                )
            )
        
        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await session.execute(count_query)
        total = total_result.scalar() or 0
        
        # Sorting
        sort_field_map = {
            "startDate": LegacyAllocation.start_date,
            "employeeName": LegacyAllocation.employee_name,
            "phaseName": LegacyAllocation.phase_name,
            "id": LegacyAllocation.id,
        }
        sort_field = sort_field_map.get(sortBy, LegacyAllocation.start_date)
        
        if sortOrder.lower() == "asc":
            query = query.order_by(sort_field.asc())
        else:
            query = query.order_by(sort_field.desc())
        
        # Pagination
        offset = (page - 1) * pageSize
        query = query.limit(pageSize).offset(offset)
        
        # Execute
        result = await session.execute(query)
        allocations = result.scalars().all()
        
        # Format response
        allocations_data = []
        for allocation in allocations:
            allocations_data.append({
                "id": str(allocation.id),
                "orderId": str(allocation.order_id) if allocation.order_id else None,
                "phaseId": str(allocation.phase_id) if allocation.phase_id else None,
                "phaseName": allocation.phase_name,
                "employeeId": str(allocation.employee_id),
                "employeeName": allocation.employee_name,
                "isLeader": allocation.is_leader,
                "startDate": allocation.start_date.isoformat() if allocation.start_date else None,
                "endDate": allocation.end_date.isoformat() if allocation.end_date else None,
            })
        
        total_pages = math.ceil(total / pageSize) if pageSize > 0 else 0
        
        return {
            "data": allocations_data,
            "total": total,
            "page": page,
            "pageSize": pageSize,
            "totalPages": total_pages,
            "hasNextPage": page < total_pages,
            "hasPreviousPage": page > 1,
        }
    except (ConnectionRefusedError, Exception) as e:
        # DB unavailable - return fallback data
        import logging
        logger = logging.getLogger(__name__)
        error_str = str(e).lower()
        if "connection refused" in error_str or "operationalerror" in error_str or "interfaceerror" in error_str:
            logger.warning(f"DB unavailable in list_allocations, returning fallback: {e}")
            return {
                "data": [],
                "total": 0,
                "page": page,
                "pageSize": pageSize,
                "totalPages": 0,
                "hasNextPage": False,
                "hasPreviousPage": False,
            }
        # Re-raise other exceptions (they'll be handled by global handler)
        raise


@router.get("/api/allocations/stats")
async def allocations_stats(
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Get aggregate statistics for all allocations."""
    try:
        # Total
        total_query = select(func.count(LegacyAllocation.id)).where(
            LegacyAllocation.tenant_id == tenant_id
        )
        total_result = await session.execute(total_query)
        total = total_result.scalar() or 0
        
        # Unique employees
        unique_employees_query = select(func.count(func.distinct(LegacyAllocation.employee_id))).where(
            LegacyAllocation.tenant_id == tenant_id
        )
        unique_employees_result = await session.execute(unique_employees_query)
        unique_employees = unique_employees_result.scalar() or 0
        
        # Unique orders
        unique_orders_query = select(func.count(func.distinct(LegacyAllocation.order_id))).where(
            and_(
                LegacyAllocation.tenant_id == tenant_id,
                LegacyAllocation.order_id.isnot(None),
            )
        )
        unique_orders_result = await session.execute(unique_orders_query)
        unique_orders = unique_orders_result.scalar() or 0
        
        # As leader
        as_leader_query = select(func.count(LegacyAllocation.id)).where(
            and_(
                LegacyAllocation.tenant_id == tenant_id,
                LegacyAllocation.is_leader == True,
            )
        )
        as_leader_result = await session.execute(as_leader_query)
        as_leader = as_leader_result.scalar() or 0
        
        # Average per employee
        avg_per_employee = (total / unique_employees) if unique_employees > 0 else 0
        
        # Top phases
        top_phases_query = (
            select(
                LegacyAllocation.phase_name,
                func.count(LegacyAllocation.id).label("count"),
            )
            .where(LegacyAllocation.tenant_id == tenant_id)
            .group_by(LegacyAllocation.phase_name)
            .order_by(func.count(LegacyAllocation.id).desc())
            .limit(10)
        )
        top_phases_result = await session.execute(top_phases_query)
        top_phases = [
            {"phase": row[0], "count": row[1]} for row in top_phases_result.all()
        ]
        
        # Top employees
        top_employees_query = (
            select(
                LegacyAllocation.employee_name,
                func.count(LegacyAllocation.id).label("count"),
            )
            .where(LegacyAllocation.tenant_id == tenant_id)
            .group_by(LegacyAllocation.employee_name)
            .order_by(func.count(LegacyAllocation.id).desc())
            .limit(10)
        )
        top_employees_result = await session.execute(top_employees_query)
        top_employees = [
            {"employee": row[0], "count": row[1]} for row in top_employees_result.all()
        ]
        
        return {
            "total": total,
            "uniqueEmployees": unique_employees,
            "uniqueOrders": unique_orders,
            "asLeader": as_leader,
            "avgPerEmployee": round(avg_per_employee, 2),
            "topPhases": top_phases,
            "topEmployees": top_employees,
        }
    except (ConnectionRefusedError, Exception) as e:
        # DB unavailable - return fallback data
        import logging
        logger = logging.getLogger(__name__)
        error_str = str(e).lower()
        if "connection refused" in error_str or "operationalerror" in error_str or "interfaceerror" in error_str:
            logger.warning(f"DB unavailable in allocations_stats, returning fallback: {e}")
            return {
                "total": 0,
                "uniqueEmployees": 0,
                "uniqueOrders": 0,
                "asLeader": 0,
                "avgPerEmployee": 0.0,
                "topPhases": [],
                "topEmployees": []
            }
        # Re-raise other exceptions (they'll be handled by global handler)
        raise


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
