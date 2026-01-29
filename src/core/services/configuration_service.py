"""
ProdPlan ONE - Configuration Service
======================================

Business logic for rate configuration management.
"""

from datetime import date
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.rates import LaborRate, MachineRate, OverheadRate
from src.shared.redis_client import get_redis
from src.shared.kafka_client import publish_event, Topics
from src.shared.events import ConfigUpdatedEvent


class ConfigurationService:
    """
    Service for configuration management.
    
    Handles cost rates (labor, machine, overhead) with caching.
    """
    
    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # LABOR RATES
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def set_labor_rate(
        self,
        employee_id: UUID,
        base_hourly_rate: Decimal,
        burden_rate: Decimal = Decimal("0.32"),
        effective_date: date = None,
        valid_until: date = None,
        currency_code: str = "EUR",
    ) -> LaborRate:
        """Set labor rate for an employee."""
        effective_date = effective_date or date.today()
        loaded_rate = LaborRate.calculate_loaded_rate(base_hourly_rate, burden_rate)
        
        labor_rate = LaborRate(
            tenant_id=self.tenant_id,
            employee_id=employee_id,
            effective_date=effective_date,
            valid_until=valid_until,
            base_hourly_rate=base_hourly_rate,
            burden_rate=burden_rate,
            loaded_rate=loaded_rate,
            currency_code=currency_code,
        )
        
        self.session.add(labor_rate)
        await self.session.flush()
        
        # Update cache
        redis = await get_redis()
        await redis.set_labor_rate(self.tenant_id, employee_id, float(loaded_rate))
        
        # Publish event
        await publish_event(
            Topics.CONFIG_UPDATED,
            ConfigUpdatedEvent(
                tenant_id=self.tenant_id,
                payload={
                    "config_type": "labor_rates",
                    "affected_entities": [str(employee_id)],
                    "effective_from": effective_date.isoformat(),
                },
            ),
        )
        
        return labor_rate
    
    async def get_labor_rate(
        self,
        employee_id: UUID,
        as_of_date: date = None,
    ) -> Optional[LaborRate]:
        """Get effective labor rate for an employee."""
        as_of_date = as_of_date or date.today()
        
        result = await self.session.execute(
            select(LaborRate).where(
                and_(
                    LaborRate.employee_id == employee_id,
                    LaborRate.tenant_id == self.tenant_id,
                    LaborRate.effective_date <= as_of_date,
                )
            ).order_by(LaborRate.effective_date.desc()).limit(1)
        )
        
        rate = result.scalar_one_or_none()
        
        # Check valid_until
        if rate and rate.valid_until and rate.valid_until < as_of_date:
            return None
        
        return rate
    
    async def get_labor_rate_value(
        self,
        employee_id: UUID,
        as_of_date: date = None,
    ) -> Decimal:
        """Get loaded labor rate value, with cache."""
        # Check cache first
        redis = await get_redis()
        cached = await redis.get_labor_rate(self.tenant_id, employee_id)
        if cached is not None:
            return Decimal(str(cached))
        
        # Get from DB
        rate = await self.get_labor_rate(employee_id, as_of_date)
        if rate:
            # Update cache
            await redis.set_labor_rate(self.tenant_id, employee_id, float(rate.loaded_rate))
            return rate.loaded_rate
        
        return Decimal("0")
    
    async def list_labor_rates(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> List[LaborRate]:
        """List all labor rates for the tenant."""
        result = await self.session.execute(
            select(LaborRate).where(
                LaborRate.tenant_id == self.tenant_id,
            ).order_by(LaborRate.effective_date.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # MACHINE RATES
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def set_machine_rate(
        self,
        machine_id: UUID,
        depreciation_rate: Decimal = Decimal("0"),
        energy_cost_per_hour: Decimal = Decimal("0"),
        maintenance_cost_per_hour: Decimal = Decimal("0"),
        effective_date: date = None,
        valid_until: date = None,
        currency_code: str = "EUR",
    ) -> MachineRate:
        """Set machine rate."""
        effective_date = effective_date or date.today()
        total_rate = MachineRate.calculate_total_rate(
            depreciation_rate,
            energy_cost_per_hour,
            maintenance_cost_per_hour,
        )
        
        machine_rate = MachineRate(
            tenant_id=self.tenant_id,
            machine_id=machine_id,
            effective_date=effective_date,
            valid_until=valid_until,
            depreciation_rate=depreciation_rate,
            energy_cost_per_hour=energy_cost_per_hour,
            maintenance_cost_per_hour=maintenance_cost_per_hour,
            total_rate=total_rate,
            currency_code=currency_code,
        )
        
        self.session.add(machine_rate)
        await self.session.flush()
        
        # Update cache
        redis = await get_redis()
        await redis.set_machine_rate(self.tenant_id, machine_id, float(total_rate))
        
        # Publish event
        await publish_event(
            Topics.CONFIG_UPDATED,
            ConfigUpdatedEvent(
                tenant_id=self.tenant_id,
                payload={
                    "config_type": "machine_rates",
                    "affected_entities": [str(machine_id)],
                    "effective_from": effective_date.isoformat(),
                },
            ),
        )
        
        return machine_rate
    
    async def get_machine_rate(
        self,
        machine_id: UUID,
        as_of_date: date = None,
    ) -> Optional[MachineRate]:
        """Get effective machine rate."""
        as_of_date = as_of_date or date.today()
        
        result = await self.session.execute(
            select(MachineRate).where(
                and_(
                    MachineRate.machine_id == machine_id,
                    MachineRate.tenant_id == self.tenant_id,
                    MachineRate.effective_date <= as_of_date,
                )
            ).order_by(MachineRate.effective_date.desc()).limit(1)
        )
        
        rate = result.scalar_one_or_none()
        
        if rate and rate.valid_until and rate.valid_until < as_of_date:
            return None
        
        return rate
    
    async def get_machine_rate_value(
        self,
        machine_id: UUID,
        as_of_date: date = None,
    ) -> Decimal:
        """Get total machine rate value, with cache."""
        redis = await get_redis()
        cached = await redis.get_machine_rate(self.tenant_id, machine_id)
        if cached is not None:
            return Decimal(str(cached))
        
        rate = await self.get_machine_rate(machine_id, as_of_date)
        if rate:
            await redis.set_machine_rate(self.tenant_id, machine_id, float(rate.total_rate))
            return rate.total_rate
        
        return Decimal("0")
    
    async def list_machine_rates(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> List[MachineRate]:
        """List all machine rates for the tenant."""
        result = await self.session.execute(
            select(MachineRate).where(
                MachineRate.tenant_id == self.tenant_id,
            ).order_by(MachineRate.effective_date.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # OVERHEAD RATES
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def set_overhead_rate(
        self,
        year_month: date,
        rent_amount: Decimal = Decimal("0"),
        utilities_amount: Decimal = Decimal("0"),
        management_amount: Decimal = Decimal("0"),
        other_overhead_amount: Decimal = Decimal("0"),
        total_available_hours: int = 10000,
        currency_code: str = "EUR",
    ) -> OverheadRate:
        """Set overhead rate for a month."""
        total_monthly_overhead = (
            rent_amount + utilities_amount + management_amount + other_overhead_amount
        )
        calculated_rate = OverheadRate.calculate_rate(
            total_monthly_overhead,
            total_available_hours,
        )
        
        overhead_rate = OverheadRate(
            tenant_id=self.tenant_id,
            year_month=year_month.replace(day=1),  # Normalize to first of month
            rent_amount=rent_amount,
            utilities_amount=utilities_amount,
            management_amount=management_amount,
            other_overhead_amount=other_overhead_amount,
            total_monthly_overhead=total_monthly_overhead,
            total_available_hours=total_available_hours,
            calculated_rate=calculated_rate,
            currency_code=currency_code,
        )
        
        self.session.add(overhead_rate)
        await self.session.flush()
        
        # Publish event
        await publish_event(
            Topics.CONFIG_UPDATED,
            ConfigUpdatedEvent(
                tenant_id=self.tenant_id,
                payload={
                    "config_type": "overhead_rates",
                    "affected_entities": [],
                    "effective_from": year_month.isoformat(),
                },
            ),
        )
        
        return overhead_rate
    
    async def get_overhead_rate(
        self,
        year_month: date = None,
    ) -> Optional[OverheadRate]:
        """Get overhead rate for a month."""
        year_month = year_month or date.today()
        year_month = year_month.replace(day=1)  # Normalize
        
        result = await self.session.execute(
            select(OverheadRate).where(
                and_(
                    OverheadRate.year_month == year_month,
                    OverheadRate.tenant_id == self.tenant_id,
                )
            )
        )
        
        return result.scalar_one_or_none()
    
    async def get_overhead_rate_value(
        self,
        year_month: date = None,
    ) -> Decimal:
        """Get overhead rate value per hour."""
        rate = await self.get_overhead_rate(year_month)
        if rate:
            return rate.calculated_rate
        return Decimal("0")
    
    async def list_overhead_rates(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> List[OverheadRate]:
        """List all overhead rates for the tenant."""
        result = await self.session.execute(
            select(OverheadRate).where(
                OverheadRate.tenant_id == self.tenant_id,
            ).order_by(OverheadRate.year_month.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # CACHE MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def invalidate_rate_cache(self) -> int:
        """Invalidate all rate caches for this tenant."""
        redis = await get_redis()
        return await redis.invalidate_tenant_cache(self.tenant_id)



