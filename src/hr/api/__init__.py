# ProdPlan ONE - HR API
"""
HR Module API Routes
====================
"""

from fastapi import APIRouter

from .allocations import router as allocations_router
from .payroll import router as payroll_router
from .productivity import router as productivity_router

router = APIRouter(prefix="/v1/hr", tags=["HR"])

router.include_router(allocations_router)
router.include_router(payroll_router)
router.include_router(productivity_router)










