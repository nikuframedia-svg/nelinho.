"""
ProdPlan ONE - Legacy API Endpoints
====================================

Q.61.32 deixou este módulo vazio. Os 7 endpoints `/api/*` que aqui
viviam foram migrados em 3 sub-sprints (sob o tema de "src/legacy não
era para apagar, era para migrar"):

    Q.61.32a  /api/orders*      → /v1/plan/orders/*       (src/plan/api/orders.py)
    Q.61.32b  /api/allocations* → /v1/workforce/allocations/*
    Q.61.32c  /api/errors*      → /v1/quality/errors/*    (src/quality/api.py)

O `legacy_router` continua montado em `src/main.py` apenas para servir
de tag OpenAPI (e qualquer endpoint residual que apareça num PR). Q.61.32d
desmonta-o e apaga este pacote.
"""

from fastapi import APIRouter

router = APIRouter(tags=["Legacy"])
