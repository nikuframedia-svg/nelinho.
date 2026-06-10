"""
ProdPlan ONE - Capacity Service
================================

Business logic for capacity planning and analysis.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.factory_data_product.models.curated import CuratedPhaseCapacity
from src.plan.models.schedule import ProductionSchedule, ScheduleStatus
from src.shared.kafka_client import publish_event, Topics
from src.shared.events import CapacityConstraintEvent
from src.shared.time import local_today


class CapacityAnalysis:
    """Result of capacity analysis for a machine."""
    
    def __init__(
        self,
        machine_id: UUID,
        machine_name: str,
        period: date,
        available_minutes: int,
        allocated_minutes: int,
    ):
        self.machine_id = machine_id
        self.machine_name = machine_name
        self.period = period
        self.available_minutes = available_minutes
        self.allocated_minutes = allocated_minutes
    
    @property
    def utilization_percent(self) -> float:
        if self.available_minutes > 0:
            return min(100, (self.allocated_minutes / self.available_minutes) * 100)
        return 0
    
    @property
    def free_minutes(self) -> int:
        return max(0, self.available_minutes - self.allocated_minutes)
    
    @property
    def is_over_capacity(self) -> bool:
        return self.allocated_minutes > self.available_minutes
    
    @property
    def severity(self) -> str:
        if self.utilization_percent >= 100:
            return "critical"
        elif self.utilization_percent >= 90:
            return "warning"
        return "normal"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "machine_id": str(self.machine_id),
            "machine_name": self.machine_name,
            "period": self.period.isoformat(),
            "available_minutes": self.available_minutes,
            "allocated_minutes": self.allocated_minutes,
            "utilization_percent": round(self.utilization_percent, 1),
            "free_minutes": self.free_minutes,
            "is_over_capacity": self.is_over_capacity,
            "severity": self.severity,
        }


class CapacityService:
    """
    Service for capacity planning.
    
    Analyzes machine utilization and detects capacity constraints.
    """
    
    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id
    
    async def analyze_capacity(
        self,
        machines: List[Dict[str, Any]],
        from_date: date = None,
        to_date: date = None,
        period_days: int = 7,
    ) -> Dict[str, Any]:
        """
        Analyze capacity utilization for machines.
        
        Args:
            machines: List of machines with available hours
            from_date: Start of analysis period
            to_date: End of analysis period
            period_days: Period granularity in days
        
        Returns:
            Capacity analysis results
        """
        from_date = from_date or local_today()
        to_date = to_date or from_date + timedelta(weeks=4)
        
        results: List[CapacityAnalysis] = []
        warnings: List[str] = []
        
        # Generate periods
        periods = []
        current = from_date
        while current < to_date:
            periods.append(current)
            current += timedelta(days=period_days)
        
        # Analyze each machine
        for machine in machines:
            machine_id = UUID(machine["machine_id"]) if isinstance(machine["machine_id"], str) else machine["machine_id"]
            machine_name = machine.get("machine_name", "Unknown")
            available_hours_per_day = float(machine.get("available_hours_per_day", 8))
            available_days_per_period = min(period_days, 5)  # Assume 5-day week
            
            available_minutes = int(available_hours_per_day * 60 * available_days_per_period)
            
            for period in periods:
                period_end = period + timedelta(days=period_days)
                
                # Query scheduled operations for this machine and period
                query = select(
                    func.sum(ProductionSchedule.scheduled_duration_hours)
                ).where(
                    and_(
                        ProductionSchedule.tenant_id == self.tenant_id,
                        ProductionSchedule.machine_id == machine_id,
                        ProductionSchedule.scheduled_start_date >= period,
                        ProductionSchedule.scheduled_start_date < period_end,
                        ProductionSchedule.status.in_([
                            ScheduleStatus.SCHEDULED,
                            ScheduleStatus.IN_PROGRESS,
                        ]),
                    )
                )
                
                result = await self.session.execute(query)
                total_hours = result.scalar() or Decimal("0")
                allocated_minutes = int(float(total_hours) * 60)
                
                analysis = CapacityAnalysis(
                    machine_id=machine_id,
                    machine_name=machine_name,
                    period=period,
                    available_minutes=available_minutes,
                    allocated_minutes=allocated_minutes,
                )
                
                results.append(analysis)
                
                # Check for constraints
                if analysis.is_over_capacity:
                    warning = f"{machine_name} over-capacity ({analysis.utilization_percent:.1f}%) for period {period}"
                    warnings.append(warning)
                    
                    # Publish event
                    await publish_event(
                        Topics.CAPACITY_CONSTRAINT_DETECTED,
                        CapacityConstraintEvent(
                            tenant_id=self.tenant_id,
                            payload={
                                "machine_id": str(machine_id),
                                "period": period.isoformat(),
                                "available_minutes": available_minutes,
                                "required_minutes": allocated_minutes,
                                "utilization_percent": analysis.utilization_percent,
                                "severity": analysis.severity,
                            },
                        ),
                    )
        
        # Aggregate results
        total_available = sum(r.available_minutes for r in results)
        total_allocated = sum(r.allocated_minutes for r in results)
        avg_utilization = (total_allocated / total_available * 100) if total_available > 0 else 0
        
        over_capacity_count = sum(1 for r in results if r.is_over_capacity)
        
        return {
            "status": "completed",
            "period_start": from_date.isoformat(),
            "period_end": to_date.isoformat(),
            "machines_analyzed": len(machines),
            "periods_analyzed": len(periods),
            "summary": {
                "total_available_minutes": total_available,
                "total_allocated_minutes": total_allocated,
                "avg_utilization_percent": round(avg_utilization, 1),
                "over_capacity_periods": over_capacity_count,
            },
            "machine_analysis": [r.to_dict() for r in results],
            "warnings": warnings,
        }
    
    async def get_machine_availability(
        self,
        machine_id: UUID,
        from_date: date = None,
        to_date: date = None,
        available_hours_per_day: float = 8.0,
    ) -> Dict[str, Any]:
        """Get availability for a single machine."""
        from_date = from_date or local_today()
        to_date = to_date or from_date + timedelta(weeks=4)
        
        # Query all scheduled operations
        query = select(ProductionSchedule).where(
            and_(
                ProductionSchedule.tenant_id == self.tenant_id,
                ProductionSchedule.machine_id == machine_id,
                ProductionSchedule.scheduled_start_date >= from_date,
                ProductionSchedule.scheduled_start_date <= to_date,
            )
        ).order_by(ProductionSchedule.scheduled_start_date)
        
        result = await self.session.execute(query)
        schedules = list(result.scalars().all())
        
        # Build daily availability
        daily_availability = []
        current = from_date
        
        while current <= to_date:
            available_minutes = int(available_hours_per_day * 60)
            
            day_schedules = [
                s for s in schedules
                if s.scheduled_start_date == current
            ]
            
            allocated_minutes = sum(
                int(float(s.scheduled_duration_hours) * 60)
                for s in day_schedules
            )
            
            daily_availability.append({
                "date": current.isoformat(),
                "available_minutes": available_minutes,
                "allocated_minutes": allocated_minutes,
                "free_minutes": max(0, available_minutes - allocated_minutes),
                "utilization_percent": min(100, allocated_minutes / available_minutes * 100) if available_minutes > 0 else 0,
                "orders_scheduled": [s.order_id for s in day_schedules],
            })
            
            current += timedelta(days=1)
        
        total_available = sum(d["available_minutes"] for d in daily_availability)
        total_allocated = sum(d["allocated_minutes"] for d in daily_availability)
        
        return {
            "machine_id": str(machine_id),
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "summary": {
                "total_available_minutes": total_available,
                "total_allocated_minutes": total_allocated,
                "avg_utilization_percent": round(total_allocated / total_available * 100, 1) if total_available > 0 else 0,
                "free_minutes": max(0, total_available - total_allocated),
            },
            "availability": daily_availability,
        }

    async def phase_capacity_summary(
        self,
        *,
        ingestion_id: Optional[UUID] = None,
    ) -> List[Dict[str, Any]]:
        """Per-phase available hours from `CuratedPhaseCapacity`.

        Sprint Q.8 Fase 5 — was unused (the curated table was populated
        but no consumer queried it). The CEO dashboard uses this to show
        "what is theoretically possible per phase per period" alongside
        the machine-centric metrics already exposed by `analyze_capacity`.

        Returns one row per phase: `{fase_id, fase_nome, periodo_tipo,
        capacidade_horas, funcionarios_count}`. Filters by
        `ingestion_id` when provided so the dashboard pins to a specific
        ERP snapshot rather than mixing scopes.
        """
        stmt = select(
            CuratedPhaseCapacity.fase_id,
            CuratedPhaseCapacity.fase_nome,
            CuratedPhaseCapacity.periodo_tipo,
            CuratedPhaseCapacity.capacidade_horas,
            CuratedPhaseCapacity.funcionarios_count,
        )
        if ingestion_id is not None:
            stmt = stmt.where(CuratedPhaseCapacity.ingestion_id == ingestion_id)
        stmt = stmt.order_by(CuratedPhaseCapacity.fase_id)

        rows = (await self.session.execute(stmt)).all()
        return [
            {
                "fase_id": r[0],
                "fase_nome": r[1],
                "periodo_tipo": r[2],
                "capacidade_horas": float(r[3]) if r[3] is not None else None,
                "funcionarios_count": r[4],
            }
            for r in rows
        ]






