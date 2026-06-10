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
from src.shared.time import local_today, utc_now, utc_now_naive

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


async def _collect_rows(
    template_id: str,
    session: AsyncSession,
    tenant_id: UUID,
    since: date | None,
    until: date | None,
) -> list[dict[str, Any]]:
    """Dispatch ``template_id`` to its generator and return the rows.

    Shared by ``/generate`` and ``/email`` so a report is produced the
    exact same way whether it is downloaded or mailed.
    """
    if template_id == "producao":
        return await _gen_producao(session, tenant_id)
    if template_id == "cliente":
        return await _gen_cliente(session, tenant_id)
    if template_id == "qualidade":
        return await _gen_qualidade(session, tenant_id, since, until)
    if template_id in ("payroll", "cogs", "inventario"):
        # Sprint Q.22.E — payroll/cogs/inventario delegate to the
        # generators in reports.generators (hr/profit/supply tables).
        from src.reports.generators import run_generator

        return await run_generator(template_id, session, tenant_id, since, until)
    # pragma: no cover — Pydantic Literal guarda os callers
    raise HTTPException(
        status.HTTP_400_BAD_REQUEST,
        detail=f"Unknown template_id: {template_id}",
    )


@router.post("/generate", response_model=ReportResponse)
async def generate_report(
    req: ReportRequest,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> ReportResponse:
    """Dispatcher central. Delega ao service apropriado conforme ``template_id``."""
    now = utc_now().isoformat()
    today = local_today().isoformat()
    filename_ext = "csv" if req.format == "csv" else "json"
    filename = f"{req.template_id}_{today}.{filename_ext}"

    rows = await _collect_rows(
        req.template_id, session, tenant_id, req.since, req.until
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
# Sprint Q.22.D-G — schedule (persistência) + email (SMTP) + retention
# (cleanup). Já não são stubs: persistem em reports.* e auditam.
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
    template_id: TemplateId
    to: list[str] = Field(min_length=1, description="Lista de destinatários email.")
    format: ReportFormat = Field(default="csv")
    since: date | None = Field(default=None)
    until: date | None = Field(default=None)


class ReportEmailResponse(BaseModel):
    run_id: UUID
    template_id: str
    status: Literal["delivered", "generated", "failed"]
    recipients: list[str]
    row_count: int
    sent: bool
    skipped: bool
    generated_at: str
    message: str | None = None


@router.post("/email", response_model=ReportEmailResponse)
async def email_report(
    req: ReportEmailRequest,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> ReportEmailResponse:
    """Gera um relatório e entrega-o por email (Sprint Q.22.F).

    Gera as linhas, persiste uma ``reports.report_run`` (ad-hoc, sem
    schedule), tenta o envio SMTP via :mod:`src.reports.email` e regista
    o resultado. Em dev (``smtp_enabled=False``) o envio é ``skipped`` —
    o relatório fica na mesma persistido com ``status="generated"``.
    Cada run escreve um ``core.audit_log`` na mesma transacção.
    """
    from src.reports.email import EmailDeliveryError, send_report_email

    now = utc_now_naive()
    rows = await _collect_rows(
        req.template_id, session, tenant_id, req.since, req.until
    )
    content = _format_payload(rows, req.format)
    ext = "csv" if req.format == "csv" else "json"

    run = ReportRun(
        tenant_id=tenant_id,
        schedule_id=None,
        report_type=req.template_id,
        status="pending",
        generated_at=now,
        delivered_to=[],
        payload={"rows": rows, "row_count": len(rows), "format": req.format},
    )
    session.add(run)
    await session.flush()  # populate run.id

    try:
        delivery = await send_report_email(
            recipients=req.to,
            subject=f"Relatório {req.template_id} — {now.date().isoformat()}",
            body=(
                f"Relatório '{req.template_id}' gerado em "
                f"{now.isoformat()} com {len(rows)} linha(s)."
            ),
            attachment_name=f"{req.template_id}_{now.date().isoformat()}.{ext}",
            attachment_text=content,
        )
    except EmailDeliveryError as exc:
        run.status = "failed"
        run.error = str(exc)
        session.add(
            AuditLog(
                tenant_id=tenant_id,
                entity_type="report_run",
                entity_id=run.id,
                action="INSERT",
                new_values={"report_type": req.template_id, "status": "failed"},
                reason="report email delivery failed",
            )
        )
        await session.commit()
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=f"Falha na entrega do relatório por email: {exc}",
        ) from exc

    # sent → delivered; skipped (SMTP off / dev) → generated.
    run.status = "delivered" if delivery["sent"] else "generated"
    run.delivered_to = delivery["recipients"] if delivery["sent"] else []
    session.add(
        AuditLog(
            tenant_id=tenant_id,
            entity_type="report_run",
            entity_id=run.id,
            action="INSERT",
            new_values={
                "report_type": req.template_id,
                "status": run.status,
                "recipients": req.to,
            },
            reason="report emailed",
        )
    )
    await session.commit()

    return ReportEmailResponse(
        run_id=run.id,
        template_id=req.template_id,
        status=run.status,  # type: ignore[arg-type]
        recipients=req.to,
        row_count=len(rows),
        sent=delivery["sent"],
        skipped=delivery["skipped"],
        generated_at=now.isoformat(),
        message=(
            None
            if delivery["sent"]
            else "SMTP desligado — relatório gerado e persistido, não enviado."
        ),
    )


class ReportRetentionRequest(BaseModel):
    template_id: TemplateId
    retention_days: int = Field(
        ge=7, le=3650, description="Janela de retenção GDPR (dias)."
    )
    run_cleanup: bool = Field(
        default=True,
        description="Correr a limpeza dos runs expirados de imediato.",
    )


class ReportRetentionResponse(BaseModel):
    template_id: str
    retention_days: int
    schedules_updated: int = Field(description="Schedules do template actualizados.")
    runs_deleted: int = Field(description="Runs expirados apagados pela limpeza.")
    message: str | None = None


@router.post("/retention", response_model=ReportRetentionResponse)
async def set_report_retention(
    req: ReportRetentionRequest,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> ReportRetentionResponse:
    """Define a janela de retenção GDPR de um template (Sprint Q.22.G).

    Actualiza o ``retention_days`` de todos os ``report_schedule`` do
    template e, se ``run_cleanup`` (default), corre logo
    :func:`cleanup_expired_runs` para apagar os runs já expirados. Cada
    UPDATE de schedule e cada DELETE de run escreve ``core.audit_log``.
    """
    from src.reports.cleanup import cleanup_expired_runs

    schedules = (
        await session.execute(
            select(ReportSchedule).where(
                ReportSchedule.tenant_id == tenant_id,
                ReportSchedule.report_type == req.template_id,
            )
        )
    ).scalars().all()

    for schedule in schedules:
        old = schedule.retention_days
        schedule.retention_days = req.retention_days
        session.add(
            AuditLog(
                tenant_id=tenant_id,
                entity_type="report_schedule",
                entity_id=schedule.id,
                action="UPDATE",
                old_values={"retention_days": old},
                new_values={"retention_days": req.retention_days},
                reason="janela de retenção GDPR actualizada",
            )
        )
    if schedules:
        await session.commit()

    runs_deleted = 0
    if req.run_cleanup:
        runs_deleted = await cleanup_expired_runs(
            session, tenant_id, default_retention_days=req.retention_days
        )

    return ReportRetentionResponse(
        template_id=req.template_id,
        retention_days=req.retention_days,
        schedules_updated=len(schedules),
        runs_deleted=runs_deleted,
        message=(
            f"{len(schedules)} agendamento(s) actualizado(s); "
            f"{runs_deleted} run(s) expirado(s) apagado(s)."
        ),
    )
