# ProdPlan ONE - HR Module
"""
HR Module - Workforce Management
================================

Responsibilities:
- Employee allocation to operations
- Labor cost tracking
- Productivity metrics
- Shift scheduling
- Payroll summary
"""

# Sprint Q.12 — exports públicos. Antes era vazio, forçando imports
# de subpaths como `from src.hr.services.payroll_service import ...`.
from src.hr.services.allocation_service import AllocationService
from src.hr.services.payroll_service import PayrollService
from src.hr.services.productivity_service import ProductivityService

__all__ = [
    "AllocationService",
    "PayrollService",
    "ProductivityService",
]










