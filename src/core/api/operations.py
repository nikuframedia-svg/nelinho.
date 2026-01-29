"""
ProdPlan ONE - Operations API
==============================

REST endpoints for operation management.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import get_session
from src.core.services.master_data_service import MasterDataService
from .schemas import OperationCreate, OperationUpdate, OperationResponse

router = APIRouter(prefix="/operations", tags=["Operations"])


def get_tenant_id(x_tenant_id: UUID = Header(...)) -> UUID:
    """Extract tenant ID from header."""
    return x_tenant_id


@router.post("", response_model=OperationResponse, status_code=status.HTTP_201_CREATED)
async def create_operation(
    data: OperationCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Create a new operation."""
    service = MasterDataService(session, tenant_id)
    
    operation = await service.create_operation(
        operation_code=data.operation_code,
        operation_name=data.operation_name,
        machine_id=data.machine_id,
        std_time_minutes=data.std_time_minutes,
        setup_time_minutes=data.setup_time_minutes,
        skills_required=data.skills_required,
    )
    
    return operation


@router.get("", response_model=List[OperationResponse])
async def list_operations(
    machine_id: UUID = None,
    limit: int = 100,
    offset: int = 0,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """List operations with optional filtering."""
    try:
        service = MasterDataService(session, tenant_id)
        operations = await service.list_operations(
            machine_id=machine_id,
            limit=limit,
            offset=offset,
        )
        return operations
    except (ConnectionRefusedError, Exception) as e:
        # DB unavailable - return fallback data
        import logging
        logger = logging.getLogger(__name__)
        error_str = str(e).lower()
        if "connection refused" in error_str or "operationalerror" in error_str or "interfaceerror" in error_str:
            logger.warning(f"DB unavailable in list_operations, returning fallback: {e}")
            return []
        # Re-raise other exceptions (they'll be handled by global handler)
        raise


@router.get("/{operation_id}", response_model=OperationResponse)
async def get_operation(
    operation_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Get operation by ID."""
    service = MasterDataService(session, tenant_id)
    operation = await service.get_operation(operation_id)
    
    if not operation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Operation {operation_id} not found",
        )
    
    return operation


@router.patch("/{operation_id}", response_model=OperationResponse)
async def update_operation(
    operation_id: UUID,
    data: OperationUpdate,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Update operation."""
    service = MasterDataService(session, tenant_id)
    
    updates = {}
    if data.operation_name is not None:
        updates["operation_name"] = data.operation_name
    if data.machine_id is not None:
        updates["machine_id"] = data.machine_id
    if data.std_time_minutes is not None:
        updates["std_time_minutes"] = data.std_time_minutes
    if data.setup_time_minutes is not None:
        updates["setup_time_minutes"] = data.setup_time_minutes
    if data.skills_required is not None:
        updates["skills_required"] = data.skills_required
    
    operation = await service.update_operation(operation_id, **updates)
    
    if not operation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Operation {operation_id} not found",
        )
    
    return operation


@router.delete("/{operation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_operation(
    operation_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Delete operation."""
    service = MasterDataService(session, tenant_id)
    deleted = await service.delete_operation(operation_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Operation {operation_id} not found",
        )
    
    return None


