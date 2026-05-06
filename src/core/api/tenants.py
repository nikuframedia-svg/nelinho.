"""
ProdPlan ONE - Tenants API
===========================

REST endpoints for tenant management.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.auth.headers import require_admin
from src.shared.database import get_session
from src.core.models.tenant import TenantStatus, SubscriptionLevel
from src.core.services.tenant_service import TenantService
from .schemas import TenantCreate, TenantUpdate, TenantResponse

# Tenant management is platform-admin scope: every endpoint here mutates or
# enumerates other tenants, so it must require ADMIN_PLATFORM via the
# `require_admin` dependency.
router = APIRouter(
    prefix="/tenants",
    tags=["Tenants"],
    dependencies=[Depends(require_admin)],
)


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    data: TenantCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new tenant."""
    service = TenantService(session)
    
    # Check if code already exists
    existing = await service.get_tenant_by_code(data.tenant_code)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tenant code '{data.tenant_code}' already exists",
        )
    
    # Sprint S8 / Π10: subscription_level is set server-side (defaults to
    # STARTER from tenant_service). Tier upgrades require the admin-only
    # PATCH /tenants/{id}/subscription endpoint.
    tenant = await service.create_tenant(
        tenant_name=data.tenant_name,
        tenant_code=data.tenant_code,
        contact_email=data.contact_email,
        currency_code=data.currency_code,
        timezone=data.timezone,
    )
    
    return tenant


@router.get("", response_model=List[TenantResponse])
async def list_tenants(
    status: TenantStatus = None,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    """List all tenants."""
    service = TenantService(session)
    tenants = await service.list_tenants(status=status, limit=limit, offset=offset)
    return tenants


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get tenant by ID."""
    service = TenantService(session)
    tenant = await service.get_tenant(tenant_id)
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {tenant_id} not found",
        )
    
    return tenant


@router.patch("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: UUID,
    data: TenantUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update tenant."""
    service = TenantService(session)
    
    updates = {}
    if data.tenant_name is not None:
        updates["tenant_name"] = data.tenant_name
    if data.contact_email is not None:
        updates["contact_email"] = data.contact_email
    if data.currency_code is not None:
        updates["currency_code"] = data.currency_code
    if data.timezone is not None:
        updates["timezone"] = data.timezone
    
    tenant = await service.update_tenant(tenant_id, **updates)
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {tenant_id} not found",
        )
    
    return tenant


@router.post("/{tenant_id}/activate", response_model=TenantResponse)
async def activate_tenant(
    tenant_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """Activate a tenant."""
    service = TenantService(session)
    tenant = await service.activate_tenant(tenant_id)
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {tenant_id} not found",
        )
    
    return tenant


@router.post("/{tenant_id}/suspend", response_model=TenantResponse)
async def suspend_tenant(
    tenant_id: UUID,
    reason: str = None,
    session: AsyncSession = Depends(get_session),
):
    """Suspend a tenant."""
    service = TenantService(session)
    tenant = await service.suspend_tenant(tenant_id, reason)
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {tenant_id} not found",
        )
    
    return tenant


@router.patch("/{tenant_id}/subscription", response_model=TenantResponse)
async def update_subscription(
    tenant_id: UUID,
    subscription_level: SubscriptionLevel,
    session: AsyncSession = Depends(get_session),
):
    """Update tenant subscription level."""
    service = TenantService(session)
    tenant = await service.update_subscription(tenant_id, subscription_level)
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {tenant_id} not found",
        )
    
    return tenant



