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
from .phase_gaps import router as phase_gaps_router  # Sprint X.3 (cura/secagem editável)
from .mold import router as mold_router  # Sprint R.6 (Q.18.ZIP.BE.3 wire)
from .orders import router as orders_router  # Sprint Q.18.ZIP.BE.1
from .dates import router as dates_router  # Q.53.B (calendário + datas de entrega)
from .timeline import router as timeline_router  # Q.141 (linha temporal: actuals)
from .order_materials import router as order_materials_router  # Q.173.U (materiais por OF)

router = APIRouter(prefix="/v1/plan", tags=["PLAN"])

router.include_router(schedule_router)
router.include_router(mrp_router)
router.include_router(capacity_router)
router.include_router(priority_report_router)
router.include_router(transport_router)
router.include_router(schedule_preview_router)
router.include_router(phase_gaps_router)
router.include_router(mold_router)
router.include_router(orders_router)
router.include_router(dates_router)
router.include_router(timeline_router)
router.include_router(order_materials_router)  # Q.173.U










