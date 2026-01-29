# ProdPlan ONE - Shared API
"""
Shared API Routes
=================

Cross-cutting API endpoints shared across modules.
"""

from fastapi import APIRouter

from .decisions import router as decisions_router
from .capabilities import router as capabilities_router

router = APIRouter(prefix="/v1", tags=["Shared"])

router.include_router(decisions_router)
router.include_router(capabilities_router)






