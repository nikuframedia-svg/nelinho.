"""
ProdPlan ONE - Suppliers API
==============================

REST endpoints for supplier management.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session
from src.core.models.partner import MaterialCategory
from src.core.services.master_data_service import MasterDataService
from .schemas import SupplierCreate, SupplierUpdate, SupplierResponse

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])

get_tenant_id = require_tenant_header


@router.post("", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    data: SupplierCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Create a new supplier."""
    service = MasterDataService(session, tenant_id)
    
    supplier = await service.create_supplier(
        supplier_code=data.supplier_code,
        supplier_name=data.supplier_name,
        material_category=data.material_category.value,
        lead_time_days=data.lead_time_days,
        payment_terms=data.payment_terms.value,
        contact_name=data.contact_name,
        contact_email=data.contact_email,
        contact_phone=data.contact_phone,
        address_line1=data.address_line1,
        address_line2=data.address_line2,
        city=data.city,
        postal_code=data.postal_code,
        country=data.country,
        quality_rating=data.quality_rating,
        is_active=data.is_active,
        is_preferred=data.is_preferred,
        notes=data.notes,
    )
    
    return supplier


@router.get("", response_model=List[SupplierResponse])
async def list_suppliers(
    material_category: MaterialCategory = None,
    is_active: bool = None,
    is_preferred: bool = None,
    limit: int = 100,
    offset: int = 0,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """List suppliers with optional filtering."""
    service = MasterDataService(session, tenant_id)
    suppliers = await service.list_suppliers(
        material_category=material_category.value if material_category else None,
        is_active=is_active,
        is_preferred=is_preferred,
        limit=limit,
        offset=offset,
    )
    return suppliers


@router.get("/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(
    supplier_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Get supplier by ID."""
    service = MasterDataService(session, tenant_id)
    supplier = await service.get_supplier(supplier_id)
    
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier {supplier_id} not found",
        )
    
    return supplier


@router.patch("/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: UUID,
    data: SupplierUpdate,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Update supplier."""
    service = MasterDataService(session, tenant_id)
    
    updates = {}
    if data.supplier_name is not None:
        updates["supplier_name"] = data.supplier_name
    if data.material_category is not None:
        updates["material_category"] = data.material_category.value
    if data.lead_time_days is not None:
        updates["lead_time_days"] = data.lead_time_days
    if data.payment_terms is not None:
        updates["payment_terms"] = data.payment_terms.value
    if data.contact_name is not None:
        updates["contact_name"] = data.contact_name
    if data.contact_email is not None:
        updates["contact_email"] = data.contact_email
    if data.contact_phone is not None:
        updates["contact_phone"] = data.contact_phone
    if data.address_line1 is not None:
        updates["address_line1"] = data.address_line1
    if data.address_line2 is not None:
        updates["address_line2"] = data.address_line2
    if data.city is not None:
        updates["city"] = data.city
    if data.postal_code is not None:
        updates["postal_code"] = data.postal_code
    if data.country is not None:
        updates["country"] = data.country
    if data.quality_rating is not None:
        updates["quality_rating"] = data.quality_rating
    if data.is_active is not None:
        updates["is_active"] = data.is_active
    if data.is_preferred is not None:
        updates["is_preferred"] = data.is_preferred
    if data.notes is not None:
        updates["notes"] = data.notes
    
    supplier = await service.update_supplier(supplier_id, **updates)
    
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier {supplier_id} not found",
        )
    
    return supplier


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supplier(
    supplier_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Soft delete supplier (set is_active=False)."""
    service = MasterDataService(session, tenant_id)
    deleted = await service.delete_supplier(supplier_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier {supplier_id} not found",
        )
    
    return None








