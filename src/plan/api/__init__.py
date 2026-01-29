# ProdPlan ONE - PLAN API
"""
PLAN Module API Routes
======================
"""

from fastapi import APIRouter

from .schedule import router as schedule_router
from .mrp import router as mrp_router
from .capacity import router as capacity_router

router = APIRouter(prefix="/v1/plan", tags=["PLAN"])

router.include_router(schedule_router)
router.include_router(mrp_router)
router.include_router(capacity_router)










