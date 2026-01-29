# ProdPlan ONE - CORE API
"""
CORE Module API Routes
======================

REST endpoints for master data management.
"""

from fastapi import APIRouter

from .tenants import router as tenants_router
from .products import router as products_router
from .machines import router as machines_router
from .employees import router as employees_router
from .operations import router as operations_router
from .rates import router as rates_router
from .bom import router as bom_router
from .customers import router as customers_router
from .suppliers import router as suppliers_router

router = APIRouter(prefix="/v1/core", tags=["CORE"])

router.include_router(tenants_router)
router.include_router(products_router)
router.include_router(machines_router)
router.include_router(employees_router)
router.include_router(operations_router)
router.include_router(rates_router)
router.include_router(bom_router)
router.include_router(customers_router)
router.include_router(suppliers_router)



