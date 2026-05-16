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

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Legacy"])


# Sprint Q.18.A.4: was a local ``get_tenant_id`` that accepted any UUID
# header value (including the zero UUID). That defeated the Q.12 Onda 0.1
# fail-closed guarantee on /api/orders, /api/allocations, /api/errors.
# Reuse the project-wide dependency so 401 / zero-UUID rejection apply
# uniformly across legacy endpoints.
get_tenant_id = require_tenant_header


# ============================================================================
# ORDERS ENDPOINTS
# ============================================================================

@router.get("/api/orders")
async def list_orders(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    pageSize: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status: ALL, IN_PROGRESS, COMPLETED"),
    search: Optional[str] = Query(None, description="Search in product name, order ID, or phase"),
    productType: Optional[str] = Query(None, description="Filter by product type: K1, K2, K4, C1, C2, C4, Other"),
    sortBy: str = Query("createdDate", description="Sort field: createdDate, productName, status, id"),
    sortOrder: str = Query("desc", description="Sort order: asc, desc"),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Get paginated list of production orders."""
    try:
        # Build query
        query = select(ProductionOrder).where(ProductionOrder.tenant_id == tenant_id)
        
        # Filters
        if status and status.upper() != "ALL":
            try:
                order_status = OrderStatus(status.upper())
                # Compare as string value
                query = query.where(ProductionOrder.status == order_status.value)
            except ValueError:
                pass  # Invalid status, ignore
        
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    ProductionOrder.product_name.ilike(search_pattern),
                    ProductionOrder.current_phase_name.ilike(search_pattern),
                    ProductionOrder.legacy_id.cast(str).ilike(search_pattern),
                )
            )
        
        if productType and productType.upper() != "ALL":
            query = query.where(ProductionOrder.product_type == productType.upper())
        
        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await session.execute(count_query)
        total = total_result.scalar() or 0
        
        # Sorting
        sort_field_map = {
            "createdDate": ProductionOrder.created_date,
            "productName": ProductionOrder.product_name,
            "status": ProductionOrder.status,
            "id": ProductionOrder.legacy_id,
        }
        sort_field = sort_field_map.get(sortBy, ProductionOrder.created_date)
        
        if sortOrder.lower() == "asc":
            query = query.order_by(sort_field.asc())
        else:
            query = query.order_by(sort_field.desc())
        
        # Pagination
        offset = (page - 1) * pageSize
        query = query.limit(pageSize).offset(offset)
        
        # Execute
        result = await session.execute(query)
        orders = result.scalars().all()
        
        # Format response
        orders_data = []
        for order in orders:
            orders_data.append({
                "id": str(order.legacy_id),
                "productId": str(order.product_id) if order.product_id else None,
                "productName": order.product_name,
                "productType": order.product_type,
                "currentPhaseId": str(order.current_phase_id) if order.current_phase_id else None,
                "currentPhaseName": order.current_phase_name,
                "createdDate": order.created_date.isoformat() if order.created_date else None,
                "completedDate": order.completed_date.isoformat() if order.completed_date else None,
                "transportDate": order.transport_date.isoformat() if order.transport_date else None,
                "status": order.status.value if hasattr(order.status, 'value') else str(order.status),
            })
        
        total_pages = math.ceil(total / pageSize) if pageSize > 0 else 0
        
        return {
            "data": orders_data,
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
            logger.warning(f"DB unavailable in list_orders, returning fallback: {e}")
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


@router.get("/api/orders/stats")
async def orders_stats(
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Get aggregate statistics for all orders."""
    try:
        # Total
        total_query = select(func.count(ProductionOrder.id)).where(
            ProductionOrder.tenant_id == tenant_id
        )
        total_result = await session.execute(total_query)
        total = total_result.scalar() or 0
        
        # In progress
        in_progress_query = select(func.count(ProductionOrder.id)).where(
            and_(
                ProductionOrder.tenant_id == tenant_id,
                ProductionOrder.status == OrderStatus.IN_PROGRESS.value,
            )
        )
        in_progress_result = await session.execute(in_progress_query)
        in_progress = in_progress_result.scalar() or 0
        
        # Completed
        completed_query = select(func.count(ProductionOrder.id)).where(
            and_(
                ProductionOrder.tenant_id == tenant_id,
                ProductionOrder.status == OrderStatus.COMPLETED.value,
            )
        )
        completed_result = await session.execute(completed_query)
        completed = completed_result.scalar() or 0
        
        # With transport
        with_transport_query = select(func.count(ProductionOrder.id)).where(
            and_(
                ProductionOrder.tenant_id == tenant_id,
                ProductionOrder.transport_date.isnot(None),
            )
        )
        with_transport_result = await session.execute(with_transport_query)
        with_transport = with_transport_result.scalar() or 0
        
        # Phase distribution
        phase_query = (
            select(
                ProductionOrder.current_phase_name,
                func.count(ProductionOrder.id).label("count"),
            )
            .where(ProductionOrder.tenant_id == tenant_id)
            .group_by(ProductionOrder.current_phase_name)
            .order_by(func.count(ProductionOrder.id).desc())
            .limit(8)
        )
        phase_result = await session.execute(phase_query)
        phase_distribution = [
            {"phase": row[0], "count": row[1]} for row in phase_result.all()
        ]
        
        return {
            "total": total,
            "inProgress": in_progress,
            "completed": completed,
            "withTransport": with_transport,
            "phaseDistribution": phase_distribution,
        }
    except (ConnectionRefusedError, Exception) as e:
        # DB unavailable - return fallback data
        import logging
        logger = logging.getLogger(__name__)
        error_str = str(e).lower()
        if "connection refused" in error_str or "operationalerror" in error_str or "interfaceerror" in error_str:
            logger.warning(f"DB unavailable in orders_stats, returning fallback: {e}")
            return {
                "total": 0,
                "inProgress": 0,
                "completed": 0,
                "withTransport": 0,
                "phaseDistribution": [],
            }
        # Re-raise other exceptions (they'll be handled by global handler)
        raise


@router.get("/api/orders/{order_id}")
async def get_order(
    order_id: int,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Get a single order by ID."""
    
    query = select(ProductionOrder).where(
        and_(
            ProductionOrder.tenant_id == tenant_id,
            ProductionOrder.legacy_id == order_id,
        )
    )
    
    result = await session.execute(query)
    order = result.scalar_one_or_none()
    
    if not order:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )
    
    return {
        "id": str(order.legacy_id),
        "productId": str(order.product_id) if order.product_id else None,
        "productName": order.product_name,
        "productType": order.product_type,
        "currentPhaseId": str(order.current_phase_id) if order.current_phase_id else None,
        "currentPhaseName": order.current_phase_name,
        "createdDate": order.created_date.isoformat() if order.created_date else None,
        "completedDate": order.completed_date.isoformat() if order.completed_date else None,
        "transportDate": order.transport_date.isoformat() if order.transport_date else None,
        "status": order.status.value if hasattr(order.status, 'value') else str(order.status),
    }


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

@router.get("/api/errors/stats")
async def errors_stats(
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Get aggregate statistics for all errors."""
    
    # TODO: Implement when ProductionError model is available
    # For now, return empty structure compatible with ErrorsStats interface
    # This prevents 404 errors when DB is not available
    
    try:
        # If we have a ProductionError model in the future, query here
        # For now, return empty stats
        return {
            "total": 0,
            "bySeverity": {
                "minor": 0,
                "major": 0,
                "critical": 0,
            },
            "ordersWithErrors": 0,
            "topDescriptions": [],
            "topPhases": [],
        }
    except Exception as e:
        logger.warning(f"Error fetching errors stats: {e}")
        # Return empty structure even on error
        return {
            "total": 0,
            "bySeverity": {
                "minor": 0,
                "major": 0,
                "critical": 0,
            },
            "ordersWithErrors": 0,
            "topDescriptions": [],
            "topPhases": [],
        }


@router.get("/api/errors")
async def list_errors(
    page: int = 1,
    page_size: int = 20,
    order_id: Optional[str] = None,
    severity: Optional[str] = None,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """List production errors with pagination and filters."""
    
    # TODO: Implement when ProductionError model is available
    # For now, return empty paginated response compatible with frontend
    
    try:
        # If we have a ProductionError model in the future, query here
        # For now, return empty list
        return {
            "data": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 0,
        }
    except Exception as e:
        logger.warning(f"Error fetching errors list: {e}")
        return {
            "data": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 0,
        }
