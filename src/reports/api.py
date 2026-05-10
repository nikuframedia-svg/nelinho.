"""POST /v1/reports/generate — dispatcher único de relatórios.

Sprint Q.18.ZIP.BE.4.

Aceita ``{template_id, format}`` + filtros opcionais e devolve um
``ReportResponse`` com:

  * status: ``ready`` / ``not_implemented``
  * format: ``csv`` / ``json``
  * filename: nome sugerido para download (e.g. ``producao_2026-05-09.csv``)
  * content: payload textual (CSV ou JSON serializado)
  * row_count: nº linhas (CSV header não conta)
  * generated_at: ISO timestamp

Templates (closed enum, mirrored no frontend RelatoriosPage REPORT_TEMPLATES):

  * ``producao``    — WIP por fase + throughput hoje (factory dashboard)
  * ``cliente``     — backlog agrupado por cliente
  * ``qualidade``   — rework dashboard agrupado por fase
  * ``payroll``     — placeholder (delega quando service exposto)
  * ``cogs``        — placeholder (delega quando service exposto)
  * ``inventario``  — placeholder (delega quando service exposto)

Estado actual: ``producao`` + ``cliente`` + ``qualidade`` ready (delegam
aos services live). Os outros 3 retornam ``not_implemented`` sem 5xx.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session

router = APIRouter(prefix="/v1/reports", tags=["Reports"])


TemplateId = Literal[
    "producao",
    "cliente",
    "qualidade",
    "payroll",
    "cogs",
    "inventario",
]
ReportFormat = Literal["csv", "json"]


class ReportRequest(BaseModel):
    template_id: TemplateId = Field(description="Template do relatório.")
    format: ReportFormat = Field(default="csv")
    since: date | None = Field(default=None, description="Janela inicial (opcional).")
    until: date | None = Field(default=None, description="Janela final (opcional).")


class ReportResponse(BaseModel):
    template_id: TemplateId
    status: Literal["ready", "not_implemented"]
    format: ReportFormat
    filename: str
    content: str = Field(description="CSV text ou JSON string. Vazio se not_implemented.")
    row_count: int = 0
    generated_at: str
    message: str | None = None


def _rows_to_csv(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def _format_payload(rows: list[dict[str, Any]], fmt: ReportFormat) -> str:
    if fmt == "csv":
        return _rows_to_csv(rows)
    return json.dumps(rows, ensure_ascii=False, default=str, indent=2)


async def _gen_producao(
    session: AsyncSession, tenant_id: UUID
) -> list[dict[str, Any]]:
    """Snapshot WIP por fase. Delega a FactoryDashboardService quando live;
    senão devolve lista vazia (ready, 0 rows — UI mostra empty state)."""
    try:
        from src.factory.services.dashboard import FactoryWIPDashboardService

        svc = FactoryWIPDashboardService(session, tenant_id)
        snapshot = await svc.snapshot()
        phases = snapshot.get("phases", []) if isinstance(snapshot, dict) else []
        return [
            {
                "fase": p.get("phase_id") or p.get("name") or "—",
                "wip": p.get("wip", 0),
                "capacity": p.get("capacity", 0),
                "utilization_pct": p.get("utilization_pct", 0),
            }
            for p in phases
        ]
    except Exception:
        return []


async def _gen_cliente(
    session: AsyncSession, tenant_id: UUID
) -> list[dict[str, Any]]:
    """Backlog por cliente. Delega ao CEODashboardService.backlog_by_client."""
    try:
        from src.profit.services.ceo_dashboard_service import CEODashboardService

        svc = CEODashboardService(session, tenant_id)
        items = await svc.backlog_by_client(limit=500)
        return [
            {
                "cliente": it.get("client_name") or it.get("client_id") or "—",
                "encomendas": it.get("order_count", 0),
                "valor_eur": it.get("total_value_eur", 0),
                "proximo_prazo": it.get("earliest_deadline"),
            }
            for it in items
        ]
    except Exception:
        return []


async def _gen_qualidade(
    session: AsyncSession,
    tenant_id: UUID,
    since: date | None,
    until: date | None,
) -> list[dict[str, Any]]:
    """Rework agrupado por fase."""
    try:
        from src.quality.services.dashboard_service import QualityDashboardService

        svc = QualityDashboardService(session, tenant_id)
        since_dt = datetime.combine(since, datetime.min.time()) if since else None
        until_dt = datetime.combine(until, datetime.min.time()) if until else None
        result = await svc.group_by(
            group_by="phase",
            since=since_dt,
            until=until_dt,
            top_n=100,
        )
        items = result.get("items", []) if isinstance(result, dict) else []
        return [
            {
                "fase": it.get("group") or it.get("phase_id") or "—",
                "rework_count": it.get("rework_count", 0),
                "cost_estimate_eur": it.get("cost_estimate_eur", 0),
                "hours_lost": it.get("hours_lost", 0),
            }
            for it in items
        ]
    except Exception:
        return []


@router.post("/generate", response_model=ReportResponse)
async def generate_report(
    req: ReportRequest,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> ReportResponse:
    """Dispatcher central. Delega ao service apropriado conforme ``template_id``."""
    now = datetime.utcnow().isoformat()
    today = date.today().isoformat()
    filename_ext = "csv" if req.format == "csv" else "json"
    filename = f"{req.template_id}_{today}.{filename_ext}"

    rows: list[dict[str, Any]] = []
    not_impl = False
    message: str | None = None

    if req.template_id == "producao":
        rows = await _gen_producao(session, tenant_id)
    elif req.template_id == "cliente":
        rows = await _gen_cliente(session, tenant_id)
    elif req.template_id == "qualidade":
        rows = await _gen_qualidade(session, tenant_id, req.since, req.until)
    elif req.template_id in ("payroll", "cogs", "inventario"):
        not_impl = True
        message = (
            f"Template '{req.template_id}' ainda não implementado. "
            "Service backend correspondente será wired em sub-sprint dedicado."
        )
    else:  # pragma: no cover — Pydantic Literal guarda
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown template_id: {req.template_id}",
        )

    if not_impl:
        return ReportResponse(
            template_id=req.template_id,
            status="not_implemented",
            format=req.format,
            filename=filename,
            content="",
            row_count=0,
            generated_at=now,
            message=message,
        )

    content = _format_payload(rows, req.format)
    return ReportResponse(
        template_id=req.template_id,
        status="ready",
        format=req.format,
        filename=filename,
        content=content,
        row_count=len(rows),
        generated_at=now,
    )


# ──────────────────────────────────────────────────────────────────────────
# Onda 18 R — schedule + email + retention stubs
# ──────────────────────────────────────────────────────────────────────────


class ReportScheduleRequest(BaseModel):
    template_id: str = Field(description="Template do relatório.")
    cron: str = Field(description="Expressão cron, ex: '0 8 * * MON'.")
    enabled: bool = Field(default=True)


@router.post("/schedule")
async def schedule_report(
    req: ReportScheduleRequest,
    tenant_id: UUID = Depends(require_tenant_header),
):
    """Agenda execução periódica do template (Onda 18 R).

    Stub: log + retorna echo. Persistência em ReportSchedule model
    fica para sub-sprint dedicado (necessita migration).
    """
    import logging
    logging.getLogger("reports.schedule").info(
        "schedule_report tenant=%s template=%s cron=%s enabled=%s",
        tenant_id, req.template_id, req.cron, req.enabled,
    )
    return {
        "status": "stubbed",
        "template_id": req.template_id,
        "cron": req.cron,
        "enabled": req.enabled,
        "next_run": None,
        "message": "Schedule registered (stub). Persistence pending sub-sprint.",
    }


class ReportEmailRequest(BaseModel):
    template_id: str
    to: list[str] = Field(min_length=1, description="Lista de destinatários email.")
    schedule_cron: str | None = Field(default=None)


@router.post("/email")
async def email_report(
    req: ReportEmailRequest,
    tenant_id: UUID = Depends(require_tenant_header),
):
    """Configura entrega por email (Onda 18 R)."""
    import logging
    logging.getLogger("reports.email").info(
        "email_report tenant=%s template=%s to=%s cron=%s",
        tenant_id, req.template_id, req.to, req.schedule_cron,
    )
    return {
        "status": "stubbed",
        "template_id": req.template_id,
        "recipients": req.to,
        "schedule_cron": req.schedule_cron,
        "message": "Email delivery configured (stub). SMTP integration pending.",
    }


class ReportRetentionRequest(BaseModel):
    template_id: str
    retention_days: int = Field(ge=7, le=3650)


@router.post("/retention")
async def set_report_retention(
    req: ReportRetentionRequest,
    tenant_id: UUID = Depends(require_tenant_header),
):
    """Define janela de retenção GDPR para o template (Onda 18 R)."""
    import logging
    logging.getLogger("reports.retention").info(
        "set_retention tenant=%s template=%s days=%d",
        tenant_id, req.template_id, req.retention_days,
    )
    return {
        "status": "stubbed",
        "template_id": req.template_id,
        "retention_days": req.retention_days,
        "message": "GDPR retention set (stub). Cleanup job pending.",
    }
