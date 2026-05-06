"""
ProdPlan ONE - BOM API
========================

REST endpoints for Bill of Materials management.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session
from src.core.services.master_data_service import MasterDataService
from .schemas import BOMItemCreate, BOMItemUpdate, BOMItemResponse

router = APIRouter(prefix="/bom", tags=["BOM"])

get_tenant_id = require_tenant_header


@router.get("/products/{product_id}", response_model=List[BOMItemResponse])
async def get_bom_by_product(
    product_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Get BOM for a product."""
    service = MasterDataService(session, tenant_id)
    
    # Verify product exists
    product = await service.get_product(product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found",
        )
    
    bom_items = await service.get_bom(product_id)
    return bom_items


@router.post("", response_model=BOMItemResponse, status_code=status.HTTP_201_CREATED)
async def create_bom_item(
    data: BOMItemCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Add a BOM item."""
    service = MasterDataService(session, tenant_id)
    
    # Verify parent product exists
    parent_product = await service.get_product(data.parent_product_id)
    if not parent_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parent product {data.parent_product_id} not found",
        )
    
    # Verify component product exists
    component_product = await service.get_product(data.component_product_id)
    if not component_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Component product {data.component_product_id} not found",
        )
    
    bom_item = await service.add_bom_item(
        parent_product_id=data.parent_product_id,
        component_product_id=data.component_product_id,
        quantity_per=data.quantity_per,
        sequence=data.sequence,
        scrap_factor=data.scrap_factor,
    )
    
    # Update additional fields if provided
    if data.unit_of_measure:
        bom_item.unit_of_measure = data.unit_of_measure
    if data.operation_id:
        bom_item.operation_id = data.operation_id
    if data.effective_from:
        bom_item.effective_from = data.effective_from
    if data.effective_to:
        bom_item.effective_to = data.effective_to
    if data.bom_version:
        bom_item.bom_version = data.bom_version
    if data.position_ref:
        bom_item.position_ref = data.position_ref
    if data.notes:
        bom_item.notes = data.notes
    
    await session.flush()
    return bom_item


@router.get("/{bom_id}", response_model=BOMItemResponse)
async def get_bom_item(
    bom_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Get BOM item by ID."""
    service = MasterDataService(session, tenant_id)
    bom_item = await service.get_bom_item(bom_id)
    
    if not bom_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BOM item {bom_id} not found",
        )
    
    return bom_item


@router.put("/{bom_id}", response_model=BOMItemResponse)
async def update_bom_item(
    bom_id: UUID,
    data: BOMItemUpdate,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Update a BOM item."""
    service = MasterDataService(session, tenant_id)
    bom_item = await service.get_bom_item(bom_id)
    
    if not bom_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BOM item {bom_id} not found",
        )
    
    # Update fields if provided
    if data.quantity_per is not None:
        bom_item.quantity_per = data.quantity_per
    if data.unit_of_measure is not None:
        bom_item.unit_of_measure = data.unit_of_measure
    if data.sequence is not None:
        bom_item.sequence = data.sequence
    if data.operation_id is not None:
        bom_item.operation_id = data.operation_id
    if data.scrap_factor is not None:
        bom_item.scrap_factor = data.scrap_factor
    if data.effective_from is not None:
        bom_item.effective_from = data.effective_from
    if data.effective_to is not None:
        bom_item.effective_to = data.effective_to
    if data.bom_version is not None:
        bom_item.bom_version = data.bom_version
    if data.position_ref is not None:
        bom_item.position_ref = data.position_ref
    if data.notes is not None:
        bom_item.notes = data.notes
    
    await session.flush()
    return bom_item


@router.delete("/{bom_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bom_item(
    bom_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Delete a BOM item."""
    service = MasterDataService(session, tenant_id)
    bom_item = await service.get_bom_item(bom_id)
    
    if not bom_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BOM item {bom_id} not found",
        )
    
    await service.delete_bom_item(bom_id)
    await session.flush()
    return None








