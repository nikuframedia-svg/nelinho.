"""
ProdPlan ONE - Products API
============================

REST endpoints for product management.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session
from src.core.models.product import ProductType, ProductStatus
from src.core.services.master_data_service import MasterDataService
from .schemas import ProductCreate, ProductUpdate, ProductResponse

router = APIRouter(prefix="/products", tags=["Products"])

# Backwards-compatible alias: existing endpoints use ``Depends(get_tenant_id)``;
# the resolver itself is now the JWT-first ``require_tenant_header``.
get_tenant_id = require_tenant_header


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    data: ProductCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Create a new product."""
    service = MasterDataService(session, tenant_id)
    
    # Check if code already exists
    existing = await service.get_product_by_code(data.product_code)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Product code '{data.product_code}' already exists",
        )
    
    product = await service.create_product(
        product_code=data.product_code,
        product_name=data.product_name,
        product_type=data.product_type,
        category=data.category,
        lead_time_days=data.lead_time_days,
        standard_cost=data.standard_cost,
    )
    
    return product


@router.get("", response_model=List[ProductResponse])
async def list_products(
    product_type: ProductType = None,
    status: ProductStatus = None,
    category: str = None,
    limit: int = 100,
    offset: int = 0,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """List products with optional filtering."""
    from src.shared.pagination import validate_pagination
    validate_pagination(limit, offset)
    try:
        service = MasterDataService(session, tenant_id)
        products = await service.list_products(
            product_type=product_type,
            status=status,
            category=category,
            limit=limit,
            offset=offset,
        )
        return products
    except (ConnectionRefusedError, Exception) as e:
        # Sprint S8 / Π7: DB unavailability now surfaces as 503 instead of
        # silently returning `[]`. Returning an empty list let clients believe
        # there were no products when the DB was actually down — masking a
        # real outage.
        import logging
        logger = logging.getLogger(__name__)
        error_str = str(e).lower()
        if "connection refused" in error_str or "operationalerror" in error_str or "interfaceerror" in error_str:
            logger.error(f"DB unavailable in list_products: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database unavailable; please retry shortly.",
            )
        # Re-raise other exceptions (they'll be handled by global handler)
        raise


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Get product by ID."""
    service = MasterDataService(session, tenant_id)
    product = await service.get_product(product_id)
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found",
        )
    
    return product


@router.get("/code/{product_code}", response_model=ProductResponse)
async def get_product_by_code(
    product_code: str,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Get product by code."""
    service = MasterDataService(session, tenant_id)
    product = await service.get_product_by_code(product_code)
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product '{product_code}' not found",
        )
    
    return product


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: UUID,
    data: ProductUpdate,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Update product."""
    service = MasterDataService(session, tenant_id)
    
    updates = {}
    if data.product_name is not None:
        updates["product_name"] = data.product_name
    if data.category is not None:
        updates["category"] = data.category
    if data.lead_time_days is not None:
        updates["lead_time_days"] = data.lead_time_days
    if data.standard_cost is not None:
        updates["standard_cost"] = data.standard_cost
    if data.status is not None:
        updates["status"] = data.status
    
    product = await service.update_product(product_id, **updates)
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found",
        )
    
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Delete product."""
    service = MasterDataService(session, tenant_id)
    deleted = await service.delete_product(product_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found",
        )
    
    return None


