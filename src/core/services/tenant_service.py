"""
ProdPlan ONE - Tenant Service
==============================

Business logic for tenant management.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.tenant import Tenant, TenantStatus, SubscriptionLevel
from src.shared.kafka_client import publish_event, Topics
from src.shared.events import TenantConfiguredEvent


class TenantService:
    """
    Service for tenant management.
    
    Handles CRUD operations and tenant lifecycle.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_tenant(
        self,
        tenant_name: str,
        tenant_code: str,
        subscription_level: SubscriptionLevel = SubscriptionLevel.STARTER,
        contact_email: Optional[str] = None,
        currency_code: str = "EUR",
        timezone: str = "UTC",
    ) -> Tenant:
        """Create a new tenant."""
        tenant = Tenant(
            tenant_name=tenant_name,
            tenant_code=tenant_code.upper(),
            status=TenantStatus.PENDING,
            subscription_level=subscription_level,
            contact_email=contact_email,
            currency_code=currency_code,
            timezone=timezone,
        )
        
        self.session.add(tenant)
        await self.session.flush()
        
        # Publish event
        await publish_event(
            Topics.TENANT_CONFIGURED,
            TenantConfiguredEvent(
                tenant_id=tenant.id,
                payload={
                    "tenant_name": tenant_name,
                    "subscription_level": subscription_level.value,
                    "modules_enabled": ["CORE", "PLAN", "PROFIT", "HR"],
                },
            ),
        )
        
        return tenant
    
    async def get_tenant(self, tenant_id: UUID) -> Optional[Tenant]:
        """Get tenant by ID."""
        result = await self.session.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        return result.scalar_one_or_none()
    
    async def get_tenant_by_code(self, tenant_code: str) -> Optional[Tenant]:
        """Get tenant by code."""
        result = await self.session.execute(
            select(Tenant).where(Tenant.tenant_code == tenant_code.upper())
        )
        return result.scalar_one_or_none()
    
    async def list_tenants(
        self,
        status: Optional[TenantStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Tenant]:
        """List tenants with optional filtering."""
        query = select(Tenant)
        
        if status:
            query = query.where(Tenant.status == status)
        
        query = query.order_by(Tenant.tenant_name).limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def activate_tenant(self, tenant_id: UUID) -> Optional[Tenant]:
        """Activate a tenant."""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return None
        
        tenant.status = TenantStatus.ACTIVE
        tenant.activated_at = datetime.utcnow()
        
        await self.session.flush()
        return tenant
    
    async def suspend_tenant(self, tenant_id: UUID, reason: str = None) -> Optional[Tenant]:
        """Suspend a tenant."""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return None
        
        tenant.status = TenantStatus.SUSPENDED
        tenant.suspended_at = datetime.utcnow()
        if reason:
            tenant.notes = f"Suspended: {reason}"
        
        await self.session.flush()
        return tenant
    
    async def update_subscription(
        self,
        tenant_id: UUID,
        subscription_level: SubscriptionLevel,
    ) -> Optional[Tenant]:
        """Update tenant subscription level."""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return None
        
        tenant.subscription_level = subscription_level
        await self.session.flush()
        
        return tenant
    
    async def update_tenant(
        self,
        tenant_id: UUID,
        **updates,
    ) -> Optional[Tenant]:
        """Update tenant fields."""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return None
        
        for key, value in updates.items():
            if value is not None and hasattr(tenant, key):
                setattr(tenant, key, value)
        
        await self.session.flush()
        return tenant
    
    async def delete_tenant(self, tenant_id: UUID) -> bool:
        """
        Soft delete a tenant (mark as cancelled).
        
        Note: Hard delete would require cascading to all tenant data.
        """
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return False
        
        tenant.status = TenantStatus.CANCELLED
        await self.session.flush()
        
        return True



