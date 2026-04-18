# ProdPlan ONE - PROFIT API
"""
PROFIT Module API Routes
========================
"""

from fastapi import APIRouter

from .cogs import router as cogs_router
from .pricing import router as pricing_router
from .scenarios import router as scenarios_router
from .kpis import router as kpis_router
from .dashboard import router as dashboard_router  # Sprint Q.3-Q.5

router = APIRouter(prefix="/v1/profit", tags=["PROFIT"])

router.include_router(cogs_router)
router.include_router(pricing_router)
router.include_router(scenarios_router)
router.include_router(kpis_router)
router.include_router(dashboard_router)










