"""
ProdPlan ONE - Customers API
==============================

REST endpoints for customer management.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import get_session
from src.core.models.partner import CustomerSegment, PriceTier
from src.core.services.master_data_service import MasterDataService
from .schemas import CustomerCreate, CustomerUpdate, CustomerResponse

router = APIRouter(prefix="/customers", tags=["Customers"])


def get_tenant_id(x_tenant_id: UUID = Header(...)) -> UUID:
    """Extract tenant ID from header."""
    return x_tenant_id


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    data: CustomerCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Create a new customer."""
    service = MasterDataService(session, tenant_id)
    
    customer = await service.create_customer(
        customer_code=data.customer_code,
        customer_name=data.customer_name,
        segment=data.segment.value,
        payment_terms=data.payment_terms.value,
        price_tier=data.price_tier.value,
        credit_limit=data.credit_limit,
        contact_name=data.contact_name,
        contact_email=data.contact_email,
        contact_phone=data.contact_phone,
        address_line1=data.address_line1,
        address_line2=data.address_line2,
        city=data.city,
        postal_code=data.postal_code,
        country=data.country,
        is_active=data.is_active,
        notes=data.notes,
    )
    
    return customer


@router.get("", response_model=List[CustomerResponse])
async def list_customers(
    segment: CustomerSegment = None,
    is_active: bool = None,
    price_tier: PriceTier = None,
    limit: int = 100,
    offset: int = 0,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """List customers with optional filtering."""
    from src.shared.pagination import validate_pagination
    validate_pagination(limit, offset)
    service = MasterDataService(session, tenant_id)
    customers = await service.list_customers(
        segment=segment.value if segment else None,
        is_active=is_active,
        price_tier=price_tier.value if price_tier else None,
        limit=limit,
        offset=offset,
    )
    return customers


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Get customer by ID."""
    service = MasterDataService(session, tenant_id)
    customer = await service.get_customer(customer_id)
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer {customer_id} not found",
        )
    
    return customer


@router.patch("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: UUID,
    data: CustomerUpdate,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Update customer."""
    service = MasterDataService(session, tenant_id)
    
    updates = {}
    if data.customer_name is not None:
        updates["customer_name"] = data.customer_name
    if data.segment is not None:
        updates["segment"] = data.segment.value
    if data.payment_terms is not None:
        updates["payment_terms"] = data.payment_terms.value
    if data.price_tier is not None:
        updates["price_tier"] = data.price_tier.value
    if data.credit_limit is not None:
        updates["credit_limit"] = data.credit_limit
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
    if data.is_active is not None:
        updates["is_active"] = data.is_active
    if data.notes is not None:
        updates["notes"] = data.notes
    
    customer = await service.update_customer(customer_id, **updates)
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer {customer_id} not found",
        )
    
    return customer


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(
    customer_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Soft delete customer (set is_active=False)."""
    service = MasterDataService(session, tenant_id)
    deleted = await service.delete_customer(customer_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer {customer_id} not found",
        )
    
    return None








