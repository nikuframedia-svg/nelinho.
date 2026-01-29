"""
ProdPlan ONE - Allocation Adapter
==================================

Adapter for employee allocation from base- workforce_analytics.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set
from uuid import UUID


@dataclass
class EmployeeSkill:
    """Employee skill definition."""
    employee_id: str
    skill_code: str
    proficiency_level: int = 1  # 1-5
    certified: bool = False
    certification_expiry: Optional[date] = None


@dataclass
class EmployeeAvailability:
    """Employee availability for a period."""
    employee_id: str
    date: date
    available_from: datetime
    available_until: datetime
    shift_type: str = "day"
    already_allocated_hours: Decimal = Decimal("0")
    
    @property
    def available_hours(self) -> Decimal:
        duration = (self.available_until - self.available_from).total_seconds() / 3600
        return Decimal(str(duration)) - self.already_allocated_hours


@dataclass
class OperationRequirement:
    """Operation labor requirement."""
    operation_id: str
    order_id: str
    required_hours: Decimal
    required_skill_codes: List[str]
    min_proficiency: int = 1
    scheduled_date: date = None
    machine_id: Optional[str] = None
    priority: int = 1


@dataclass
class AllocationResult:
    """Result of allocation."""
    operation_id: str
    order_id: str
    employee_id: str
    employee_name: str
    allocated_hours: Decimal
    hourly_rate: Decimal
    estimated_cost: Decimal
    skill_match: bool = True


class AllocationAdapter:
    """
    Adapter for employee allocation.
    
    Matches employees to operations based on skills and availability.
    """
    
    def __init__(self):
        self._employees: Dict[str, Dict[str, Any]] = {}
        self._skills: Dict[str, List[EmployeeSkill]] = {}
        self._availability: Dict[str, List[EmployeeAvailability]] = {}
        self._hourly_rates: Dict[str, Decimal] = {}
    
    def add_employee(
        self,
        employee_id: str,
        employee_name: str,
        skills: List[EmployeeSkill] = None,
        hourly_rate: Decimal = Decimal("10.0"),
    ) -> None:
        """Add employee to the pool."""
        self._employees[employee_id] = {
            "id": employee_id,
            "name": employee_name,
        }
        self._skills[employee_id] = skills or []
        self._hourly_rates[employee_id] = hourly_rate
    
    def add_availability(
        self,
        employee_id: str,
        availability: EmployeeAvailability,
    ) -> None:
        """Add availability for an employee."""
        if employee_id not in self._availability:
            self._availability[employee_id] = []
        self._availability[employee_id].append(availability)
    
    def allocate(
        self,
        requirements: List[OperationRequirement],
        strategy: str = "skill_first",
    ) -> List[AllocationResult]:
        """
        Allocate employees to operations.
        
        Strategies:
        - skill_first: Prioritize skill match over availability
        - availability_first: Prioritize availability
        - cost_optimized: Minimize total labor cost
        """
        allocations: List[AllocationResult] = []
        
        # Sort requirements by priority
        sorted_reqs = sorted(requirements, key=lambda r: -r.priority)
        
        # Track remaining availability
        remaining_hours: Dict[str, Dict[date, Decimal]] = {}
        for emp_id, avails in self._availability.items():
            remaining_hours[emp_id] = {}
            for avail in avails:
                if avail.date not in remaining_hours[emp_id]:
                    remaining_hours[emp_id][avail.date] = Decimal("0")
                remaining_hours[emp_id][avail.date] += avail.available_hours
        
        for req in sorted_reqs:
            # Find matching employees
            candidates = self._find_candidates(
                req,
                remaining_hours,
                strategy,
            )
            
            if not candidates:
                continue
            
            # Allocate from candidates
            remaining_req = req.required_hours
            
            for candidate in candidates:
                if remaining_req <= 0:
                    break
                
                emp_id = candidate["employee_id"]
                available = candidate["available_hours"]
                
                to_allocate = min(remaining_req, available)
                if to_allocate <= 0:
                    continue
                
                rate = self._hourly_rates.get(emp_id, Decimal("10.0"))
                cost = to_allocate * rate
                
                allocations.append(AllocationResult(
                    operation_id=req.operation_id,
                    order_id=req.order_id,
                    employee_id=emp_id,
                    employee_name=self._employees.get(emp_id, {}).get("name", ""),
                    allocated_hours=to_allocate,
                    hourly_rate=rate,
                    estimated_cost=cost,
                    skill_match=candidate["skill_match"],
                ))
                
                # Update remaining
                remaining_req -= to_allocate
                if req.scheduled_date and emp_id in remaining_hours:
                    if req.scheduled_date in remaining_hours[emp_id]:
                        remaining_hours[emp_id][req.scheduled_date] -= to_allocate
        
        return allocations
    
    def _find_candidates(
        self,
        req: OperationRequirement,
        remaining_hours: Dict[str, Dict[date, Decimal]],
        strategy: str,
    ) -> List[Dict[str, Any]]:
        """Find candidate employees for an operation."""
        candidates = []
        
        for emp_id, emp_data in self._employees.items():
            # Check availability
            available = Decimal("0")
            if emp_id in remaining_hours:
                if req.scheduled_date:
                    available = remaining_hours[emp_id].get(req.scheduled_date, Decimal("0"))
                else:
                    available = sum(remaining_hours[emp_id].values())
            
            if available <= 0:
                continue
            
            # Check skills
            skill_match = self._check_skill_match(emp_id, req)
            
            candidates.append({
                "employee_id": emp_id,
                "employee_name": emp_data.get("name", ""),
                "available_hours": available,
                "skill_match": skill_match,
                "rate": self._hourly_rates.get(emp_id, Decimal("10.0")),
            })
        
        # Sort by strategy
        if strategy == "skill_first":
            candidates.sort(key=lambda c: (-int(c["skill_match"]), c["rate"]))
        elif strategy == "cost_optimized":
            candidates.sort(key=lambda c: (c["rate"], -int(c["skill_match"])))
        else:  # availability_first
            candidates.sort(key=lambda c: (-c["available_hours"], -int(c["skill_match"])))
        
        return candidates
    
    def _check_skill_match(
        self,
        employee_id: str,
        req: OperationRequirement,
    ) -> bool:
        """Check if employee has required skills."""
        if not req.required_skill_codes:
            return True
        
        emp_skills = self._skills.get(employee_id, [])
        emp_skill_codes = {
            s.skill_code for s in emp_skills
            if s.proficiency_level >= req.min_proficiency
        }
        
        required_set = set(req.required_skill_codes)
        return required_set.issubset(emp_skill_codes)
    
    def get_employee_workload(
        self,
        employee_id: str,
        allocations: List[AllocationResult],
    ) -> Dict[str, Any]:
        """Get workload summary for an employee."""
        emp_allocations = [a for a in allocations if a.employee_id == employee_id]
        
        total_hours = sum(a.allocated_hours for a in emp_allocations)
        total_cost = sum(a.estimated_cost for a in emp_allocations)
        
        return {
            "employee_id": employee_id,
            "total_allocated_hours": float(total_hours),
            "total_labor_cost": float(total_cost),
            "operations_count": len(emp_allocations),
            "allocations": [
                {
                    "operation_id": a.operation_id,
                    "order_id": a.order_id,
                    "hours": float(a.allocated_hours),
                    "cost": float(a.estimated_cost),
                }
                for a in emp_allocations
            ],
        }










