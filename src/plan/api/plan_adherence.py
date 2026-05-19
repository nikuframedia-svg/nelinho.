"""
ProdPlan ONE — Endpoint de aderência ao plano (F13, Sprint Q.44.B)
===================================================================

Liga o `ScheduleCommit` (o plano digital, imutável) ao `OF_FP` real do ERP
MAR-KAYAKS, devolvendo a % de aderência, desvios por fase e deriva.

Endpoint
--------
    GET /v1/plan/adherence?commit_sha=<sha>&tolerance_hours=<h>

`commit_sha` omitido → usa o commit mais recente do tenant.

Honestidade de degradação
-------------------------
Em dev `sqlserver_enabled=False`, logo o reader `list_operations` lança
`RuntimeError`. Este endpoint apanha-o e devolve, com HTTP 200,
`status="sem_execucao_real"` — uma resposta explícita de que não há execução
real para comparar, NUNCA um número de aderência inventado. A janela de datas
para o reader é derivada das horas das operações planeadas no commit.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.nelo import services as nelo_services
from src.plan.cpo.commits import CommitsService
from src.plan.services.plan_adherence_service import (
    DEFAULT_TOLERANCE_HOURS,
    compare_adherence,
    realized_from_operation_rows,
)
from src.shared.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Plan"])


def get_tenant_id(x_tenant_id: UUID = Header(..., alias="X-Tenant-Id")) -> UUID:
    return x_tenant_id


def _planned_window(operations: list[dict[str, Any]]) -> Optional[tuple[date, date]]:
    """Janela [min start, max end] das operações planeadas, como datas.

    É a janela mais apertada que o reader `list_operations` (`OF_FP` tem
    2.6 M linhas) precisa de varrer para apanhar a execução real do plano.
    Devolve None se o commit não tiver operações com horas.
    """
    starts: list[datetime] = []
    ends: list[datetime] = []
    for op in operations:
        for key, bucket in (("start_time", starts), ("end_time", ends)):
            raw = op.get(key)
            if isinstance(raw, str):
                try:
                    bucket.append(datetime.fromisoformat(raw))
                except ValueError:
                    continue
    moments = starts + ends
    if not moments:
        return None
    return (min(moments).date(), max(moments).date())


@router.get("/adherence")
async def plan_adherence(
    commit_sha: Optional[str] = Query(None),
    tolerance_hours: float = Query(DEFAULT_TOLERANCE_HOURS, ge=0.0),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Aderência ao plano: compara um `ScheduleCommit` com o `OF_FP` real."""
    svc = CommitsService(session, tenant_id)
    if commit_sha:
        commit = await svc.get_by_sha(commit_sha) or await svc.get_by_sha_prefix(commit_sha)
    else:
        commit = await svc.get_latest()
    if commit is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="Sem commit de plano para comparar",
        )

    planned_ops = list(commit.operations or [])
    window = _planned_window(planned_ops)

    base = {
        "commit_sha256": commit.commit_sha256,
        "short_sha": commit.commit_sha256[:12],
        "planned_total": len(planned_ops),
    }

    if window is None:
        # Commit sem operações com horas — nada para janela nem comparação.
        return {
            **base,
            "status": "sem_plano_temporal",
            "detail": (
                "O commit não tem operações com horas de início/fim; "
                "não há plano temporal para confrontar com o realizado."
            ),
        }

    date_from, date_to = window

    # Caminho real: ler o OF_FP. Em dev (sqlserver_enabled=False) o reader
    # lança RuntimeError — degradação honesta, sem número inventado.
    try:
        rows = await nelo_services.list_operations(
            date_from=date_from,
            date_to=date_to,
        )
    except RuntimeError as exc:
        logger.info("Aderência ao plano: ERP indisponível — %s", exc)
        return {
            **base,
            "status": "sem_execucao_real",
            "detail": (
                "O ERP MAR-KAYAKS não está ligado (sqlserver_enabled=False); "
                "não há execução real (OF_FP) para comparar com o plano. "
                "Liga o sync do ERP para obter a aderência."
            ),
            "window": {"from": date_from.isoformat(), "to": date_to.isoformat()},
        }

    realized = realized_from_operation_rows(rows)
    result = compare_adherence(
        planned_ops,
        realized,
        tolerance_hours=tolerance_hours,
    )

    return {
        **base,
        **result.to_dict(),
        "window": {"from": date_from.isoformat(), "to": date_to.isoformat()},
    }
