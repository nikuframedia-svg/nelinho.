"""
ProdPlan ONE - Payroll Service
===============================

Business logic for payroll calculations.
"""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.hr.models.allocation import HRAllocation, AllocationStatus
from src.hr.models.productivity import MonthlyPayrollSummary
from src.shared.kafka_client import publish_event, Topics
from src.shared.events import MonthlyPayrollCalculatedEvent


class PayrollService:
    """
    Service for payroll calculations.
    """
    
    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id
    
    async def calculate_monthly_payroll(
        self,
        year_month: date,
        burden_rate: Decimal = Decimal("0.32"),
        overtime_multiplier: Decimal = Decimal("1.5"),
        regular_hours_threshold: int = 160,
    ) -> Dict[str, Any]:
        """
        Calculate monthly payroll summary.

        Sprint Q.12 — corre dentro de transação com row-level lock sobre
        as alocações COMPLETED do mês (``with_for_update``). Sem isto,
        cancelamentos concorrentes durante o cálculo davam totais
        inconsistentes (cancelamento posterior continuava somado).

        Args:
            year_month: First day of month
            burden_rate: Social charges rate
            overtime_multiplier: Overtime rate multiplier
            regular_hours_threshold: Monthly regular hours limit

        Returns:
            Payroll summary
        """
        year_month = year_month.replace(day=1)

        # Get month range
        if year_month.month == 12:
            month_end = year_month.replace(year=year_month.year + 1, month=1)
        else:
            month_end = year_month.replace(month=year_month.month + 1)

        async with self.session.begin_nested():
            # Lock allocations for the month so concurrent status changes
            # don't slip in mid-calculation.
            query = (
                select(HRAllocation)
                .where(
                    and_(
                        HRAllocation.tenant_id == self.tenant_id,
                        HRAllocation.allocation_date >= year_month,
                        HRAllocation.allocation_date < month_end,
                        HRAllocation.status == AllocationStatus.COMPLETED,
                    )
                )
                .with_for_update()
            )

            result = await self.session.execute(query)
            allocations = list(result.scalars().all())

            # Group by employee
            employee_summaries: Dict[UUID, Dict[str, Any]] = {}

            for alloc in allocations:
                if alloc.employee_id not in employee_summaries:
                    employee_summaries[alloc.employee_id] = {
                        "employee_id": alloc.employee_id,
                        "total_hours": Decimal("0"),
                        "total_regular_hours": Decimal("0"),
                        "total_overtime_hours": Decimal("0"),
                        "total_cost": Decimal("0"),
                        "hourly_rate": alloc.hourly_rate,
                    }

                hours = alloc.actual_hours or alloc.allocated_hours
                employee_summaries[alloc.employee_id]["total_hours"] += hours
                employee_summaries[alloc.employee_id]["total_cost"] += alloc.actual_cost or alloc.estimated_cost

            # Calculate regular vs overtime
            total_regular_cost = Decimal("0")
            total_overtime_cost = Decimal("0")
            total_burden = Decimal("0")

            for emp_id, summary in employee_summaries.items():
                total = summary["total_hours"]
                rate = summary["hourly_rate"]

                if total > regular_hours_threshold:
                    regular = Decimal(str(regular_hours_threshold))
                    overtime = total - regular
                else:
                    regular = total
                    overtime = Decimal("0")

                summary["total_regular_hours"] = regular
                summary["total_overtime_hours"] = overtime

                regular_cost = regular * rate
                overtime_cost = overtime * rate * overtime_multiplier

                summary["regular_cost"] = regular_cost
                summary["overtime_cost"] = overtime_cost
                summary["burden_cost"] = (regular_cost + overtime_cost) * burden_rate
                summary["total_loaded_cost"] = regular_cost + overtime_cost + summary["burden_cost"]

                total_regular_cost += regular_cost
                total_overtime_cost += overtime_cost
                total_burden += summary["burden_cost"]

            total_cost = total_regular_cost + total_overtime_cost + total_burden

            # Save summary inside the same locked savepoint.
            payroll_summary = MonthlyPayrollSummary(
                tenant_id=self.tenant_id,
                year_month=year_month,
                regular_hours=sum(s["total_regular_hours"] for s in employee_summaries.values()),
                overtime_hours=sum(s["total_overtime_hours"] for s in employee_summaries.values()),
                total_hours=sum(s["total_hours"] for s in employee_summaries.values()),
                regular_cost=total_regular_cost,
                overtime_cost=total_overtime_cost,
                burden_cost=total_burden,
                total_cost=total_cost,
                employee_count=len(employee_summaries),
            )

            self.session.add(payroll_summary)
            await self.session.flush()
        
        # Publish event
        await publish_event(
            Topics.MONTHLY_PAYROLL_CALCULATED,
            MonthlyPayrollCalculatedEvent(
                tenant_id=self.tenant_id,
                payload={
                    "year_month": year_month.isoformat(),
                    "employee_count": len(employee_summaries),
                    "total_payroll_cost": float(total_cost),
                    "total_bonus": 0,  # Would come from productivity
                    "currency": "EUR",
                },
            ),
        )
        
        return {
            "year_month": year_month.isoformat(),
            "employee_count": len(employee_summaries),
            "total_hours": float(sum(s["total_hours"] for s in employee_summaries.values())),
            "regular_hours": float(sum(s["total_regular_hours"] for s in employee_summaries.values())),
            "overtime_hours": float(sum(s["total_overtime_hours"] for s in employee_summaries.values())),
            "regular_cost": float(total_regular_cost),
            "overtime_cost": float(total_overtime_cost),
            "burden_cost": float(total_burden),
            "total_cost": float(total_cost),
            "employee_summaries": [
                {
                    "employee_id": str(emp_id),
                    "total_hours": float(s["total_hours"]),
                    "regular_hours": float(s["total_regular_hours"]),
                    "overtime_hours": float(s["total_overtime_hours"]),
                    "total_cost": float(s.get("total_loaded_cost", 0)),
                }
                for emp_id, s in employee_summaries.items()
            ],
        }
    
    async def get_labor_cost(
        self,
        from_date: date = None,
        to_date: date = None,
        order_id: str = None,
        employee_id: UUID = None,
    ) -> Dict[str, Any]:
        """Get aggregated labor cost."""
        query = select(
            func.sum(HRAllocation.actual_cost).label("actual_cost"),
            func.sum(HRAllocation.estimated_cost).label("estimated_cost"),
            func.sum(HRAllocation.allocated_hours).label("allocated_hours"),
            func.sum(HRAllocation.actual_hours).label("actual_hours"),
            func.count(HRAllocation.id).label("allocation_count"),
        ).where(
            HRAllocation.tenant_id == self.tenant_id
        )
        
        if from_date:
            query = query.where(HRAllocation.allocation_date >= from_date)
        if to_date:
            query = query.where(HRAllocation.allocation_date <= to_date)
        if order_id:
            query = query.where(HRAllocation.order_id == order_id)
        if employee_id:
            query = query.where(HRAllocation.employee_id == employee_id)
        
        result = await self.session.execute(query)
        row = result.one()
        
        return {
            "from_date": from_date.isoformat() if from_date else None,
            "to_date": to_date.isoformat() if to_date else None,
            "order_id": order_id,
            "employee_id": str(employee_id) if employee_id else None,
            "allocated_hours": float(row.allocated_hours or 0),
            "actual_hours": float(row.actual_hours or 0),
            "estimated_cost": float(row.estimated_cost or 0),
            "actual_cost": float(row.actual_cost or 0),
            "allocation_count": row.allocation_count or 0,
        }










