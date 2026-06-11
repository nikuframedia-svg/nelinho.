"""Q.115.F — GET /v1/profit/preview?schedule_commit_id=...

Devolve margem prevista para um ScheduleCommit existente.
404 se commit não existe; 200 com confidence=low se sample<100.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.ml.registry_loader import load_active_duration_predictor
from src.profit.services.margin_preview import compute_margin_preview
from src.shared.auth.headers import require_tenant_header
from src.shared.auth.rbac import Permission, PermissionDependency
from src.shared.database import get_session

router = APIRouter(tags=["Profit"])

_require_schedule_read = PermissionDependency([Permission.SCHEDULE_READ])


class MarginPreviewOut(BaseModel):
    schedule_commit_id: str
    predicted_margin_eur: Optional[Decimal]
    baseline_margin_eur: Optional[Decimal]
    delta_eur: Optional[Decimal]
    confidence: Literal["high", "medium", "low"]
    sample_size: int
    computed_at: datetime
    # Q.173.H — proveniência do custo/h: 'labor_rates' (média real) ou
    # 'none' (sem taxas na BD → margem null, nunca € inventado).
    cost_rate_eur_h: Optional[Decimal] = None
    cost_rate_source: Literal["labor_rates", "none"] = "none"
    ops_sem_duracao: int = 0

    model_config = {"from_attributes": True}


@router.get(
    "/preview",
    response_model=MarginPreviewOut,
    summary="Margem prevista para um schedule commit",
)
async def get_margin_preview(
    schedule_commit_id: str = Query(..., description="UUID ou sha prefix do commit"),
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
    _perm: None = Depends(_require_schedule_read),
) -> MarginPreviewOut:
    """Calcula a margem prevista (€) para o commit indicado.

    - 404 se o commit não existe ou não pertence a este tenant.
    - confidence=low quando sample<100 ou DurationModel indisponível.
    - delta_eur=null quando daily_revenue_target não está configurado.
    """
    duration_model = await load_active_duration_predictor(session, tenant_id)

    try:
        preview = await compute_margin_preview(
            session,
            tenant_id,
            schedule_commit_id,
            duration_model=duration_model,
        )
    except ValueError as exc:
        if "commit_not_found" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Commit não encontrado: {schedule_commit_id}",
            )
        raise

    return MarginPreviewOut(
        schedule_commit_id=preview.schedule_commit_id,
        predicted_margin_eur=preview.predicted_margin_eur,
        baseline_margin_eur=preview.baseline_margin_eur,
        delta_eur=preview.delta_eur,
        confidence=preview.confidence,
        sample_size=preview.sample_size,
        computed_at=preview.computed_at,
        cost_rate_eur_h=preview.cost_rate_eur_h,
        cost_rate_source=preview.cost_rate_source,
        ops_sem_duracao=preview.ops_sem_duracao,
    )
