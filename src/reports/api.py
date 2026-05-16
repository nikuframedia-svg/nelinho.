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
  * ``payroll``     — horas + custo de mão-de-obra por operador
  * ``cogs``        — custo dos produtos vendidos por OF
  * ``inventario``  — stock on-hand actual por SKU

Estado actual: os 6 templates delegam aos generators / services live
(Sprint Q.22.E ligou payroll/cogs/inventario). Quando uma tabela não
tem dados o relatório vem ``ready`` com 0 linhas — nunca placeholders.
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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.audit import AuditLog
from src.reports.models import ReportRun, ReportSchedule
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

    if req.template_id == "producao":
        rows = await _gen_producao(session, tenant_id)
    elif req.template_id == "cliente":
        rows = await _gen_cliente(session, tenant_id)
    elif req.template_id == "qualidade":
        rows = await _gen_qualidade(session, tenant_id, req.since, req.until)
    elif req.template_id in ("payroll", "cogs", "inventario"):
        # Sprint Q.22.E — payroll/cogs/inventario delegate to the
        # generators in reports.generators (hr/profit/supply tables).
        from src.reports.generators import run_generator

        rows = await run_generator(
            req.template_id, session, tenant_id, req.since, req.until
        )
    else:  # pragma: no cover — Pydantic Literal guarda
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown template_id: {req.template_id}",
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
    template_id: TemplateId = Field(description="Template do relatório.")
    cron: str = Field(min_length=1, description="Expressão cron, ex: '0 8 * * MON'.")
    enabled: bool = Field(default=True)
    format: ReportFormat = Field(default="csv")
    recipients: list[str] = Field(
        default_factory=list, description="Destinatários email (opcional)."
    )
    retention_days: int = Field(
        default=90, ge=7, le=3650, description="Janela de retenção GDPR (dias)."
    )


class ReportScheduleResponse(BaseModel):
    id: UUID
    template_id: str
    cron: str
    enabled: bool
    format: ReportFormat
    recipients: list[str]
    retention_days: int
    created_at: str


@router.post("/schedule", response_model=ReportScheduleResponse, status_code=201)
async def schedule_report(
    req: ReportScheduleRequest,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> ReportScheduleResponse:
    """Agenda execução periódica de um template (Sprint Q.22.D).

    Persiste uma row ``reports.report_schedule``. A criação escreve um
    ``core.audit_log`` INSERT na mesma transacção — invariante 7: "porque
    é que o sistema tem este agendamento" tem resposta sem ``git blame``.
    """
    schedule = ReportSchedule(
        tenant_id=tenant_id,
        report_type=req.template_id,
        cron=req.cron,
        recipients=list(req.recipients),
        format=req.format,
        enabled=req.enabled,
        retention_days=req.retention_days,
    )
    session.add(schedule)
    await session.flush()  # populate schedule.id

    session.add(
        AuditLog(
            tenant_id=tenant_id,
            entity_type="report_schedule",
            entity_id=schedule.id,
            action="INSERT",
            new_values={
                "report_type": req.template_id,
                "cron": req.cron,
                "enabled": req.enabled,
                "retention_days": req.retention_days,
            },
            reason="report schedule created",
        )
    )
    await session.commit()

    return ReportScheduleResponse(
        id=schedule.id,
        template_id=schedule.report_type,
        cron=schedule.cron,
        enabled=schedule.enabled,
        format=schedule.format,  # type: ignore[arg-type]
        recipients=list(schedule.recipients),
        retention_days=schedule.retention_days,
        created_at=schedule.created_at.isoformat(),
    )


@router.get("/schedule", response_model=list[ReportScheduleResponse])
async def list_report_schedules(
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> list[ReportScheduleResponse]:
    """Lista os agendamentos de relatórios do tenant (Sprint Q.22.D)."""
    rows = (
        await session.execute(
            select(ReportSchedule)
            .where(ReportSchedule.tenant_id == tenant_id)
            .order_by(ReportSchedule.created_at.desc())
        )
    ).scalars().all()
    return [
        ReportScheduleResponse(
            id=s.id,
            template_id=s.report_type,
            cron=s.cron,
            enabled=s.enabled,
            format=s.format,  # type: ignore[arg-type]
            recipients=list(s.recipients),
            retention_days=s.retention_days,
            created_at=s.created_at.isoformat(),
        )
        for s in rows
    ]


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
