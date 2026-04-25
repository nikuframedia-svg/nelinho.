# ProdPlan ONE - PLAN API
"""
PLAN Module API Routes
======================
"""

from fastapi import APIRouter

from .schedule import router as schedule_router
from .mrp import router as mrp_router
from .capacity import router as capacity_router
from .priority_report import router as priority_report_router  # Sprint Q.6
from .transport import router as transport_router  # Sprint Q.2
from .schedule_preview import router as schedule_preview_router  # Sprint Q.4

router = APIRouter(prefix="/v1/plan", tags=["PLAN"])

router.include_router(schedule_router)
router.include_router(mrp_router)
router.include_router(capacity_router)
router.include_router(priority_report_router)
router.include_router(transport_router)
router.include_router(schedule_preview_router)










