"""
ProdPlan ONE - Reports API
===========================

`/v1/reports/schedule` — CRUD for recurring report definitions.

Every mutating operation writes a ``core.audit_log`` row in the same
transaction (invariant 7: audit trail intact). ``/generate``, ``/email``
and ``/retention`` are added in sub-sprints Q.22.E/F/G.
"""

import logging
from datetime import date, datetime
from typing import List, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.audit import AuditLog
from src.reports.cleanup import DEFAULT_RETENTION_DAYS, cleanup_expired_runs
from src.reports.email import EmailDeliveryError, send_report_email
from src.reports.generators import run_generator, serialize_report
from src.reports.models import ReportRun, ReportSchedule
from src.shared.auth.headers import require_tenant_header, require_user_uuid
from src.shared.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/reports", tags=["Reports"])

ReportType = Literal["payroll", "cogs", "inventario"]
ReportFormat = Literal["csv", "json"]


async def write_audit(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    actor_id: Optional[UUID],
    action: str,
    entity_type: str,
    entity_id: UUID,
    before: Optional[dict] = None,
    after: Optional[dict] = None,
) -> None:
    """Append an audit row in the caller's transaction.

    Same semantics as ``MasterDataService._audit``: the row commits with
    the business change or rolls back with it.
    """
    session.add(
        AuditLog(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            old_values=before,
            new_values=after,
            actor_id=actor_id,
        )
    )


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ScheduleCreate(BaseModel):
    report_type: ReportType
    cron: str = Field(..., min_length=1, max_length=120)
    recipients: List[str] = Field(default_factory=list)
    format: ReportFormat = "csv"
    enabled: bool = True
    retention_days: int = Field(default=90, ge=1, le=3650)


class ScheduleUpdate(BaseModel):
    cron: Optional[str] = Field(default=None, min_length=1, max_length=120)
    recipients: Optional[List[str]] = None
    format: Optional[ReportFormat] = None
    enabled: Optional[bool] = None
    retention_days: Optional[int] = Field(default=None, ge=1, le=3650)


class ScheduleResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    report_type: str
    cron: str
    recipients: List[str]
    format: str
    enabled: bool
    retention_days: int
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]


def _to_response(row: ReportSchedule) -> ScheduleResponse:
    return ScheduleResponse(
        id=row.id,
        tenant_id=row.tenant_id,
        report_type=row.report_type,
        cron=row.cron,
        recipients=list(row.recipients or []),
        format=row.format,
        enabled=row.enabled,
        retention_days=row.retention_days,
        last_run_at=row.last_run_at,
        next_run_at=row.next_run_at,
    )


async def _get_or_404(
    session: AsyncSession, tenant_id: UUID, schedule_id: UUID
) -> ReportSchedule:
    result = await session.execute(
        select(ReportSchedule).where(
            ReportSchedule.id == schedule_id,
            ReportSchedule.tenant_id == tenant_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report schedule {schedule_id} not found",
        )
    return row


class GenerateRequest(BaseModel):
    report_type: ReportType
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    schedule_id: Optional[UUID] = None


class RunResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    schedule_id: Optional[UUID]
    report_type: str
    status: str
    generated_at: Optional[datetime]
    delivered_to: List[str]
    payload: dict
    error: Optional[str]


def _run_to_response(row: ReportRun) -> RunResponse:
    return RunResponse(
        id=row.id,
        tenant_id=row.tenant_id,
        schedule_id=row.schedule_id,
        report_type=row.report_type,
        status=row.status,
        generated_at=row.generated_at,
        delivered_to=list(row.delivered_to or []),
        payload=dict(row.payload or {}),
        error=row.error,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/schedule", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    body: ScheduleCreate,
    tenant_id: UUID = Depends(require_tenant_header),
    actor_id: UUID = Depends(require_user_uuid),
    session: AsyncSession = Depends(get_session),
) -> ScheduleResponse:
    """Create a recurring report definition."""
    row = ReportSchedule(
        tenant_id=tenant_id,
        report_type=body.report_type,
        cron=body.cron,
        recipients=body.recipients,
        format=body.format,
        enabled=body.enabled,
        retention_days=body.retention_days,
    )
    session.add(row)
    await session.flush()
    await write_audit(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action="INSERT",
        entity_type="report_schedule",
        entity_id=row.id,
        after=body.model_dump(),
    )
    await session.commit()
    return _to_response(row)


@router.get("/schedule", response_model=List[ScheduleResponse])
async def list_schedules(
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> List[ScheduleResponse]:
    """List all report schedules for the tenant."""
    result = await session.execute(
        select(ReportSchedule)
        .where(ReportSchedule.tenant_id == tenant_id)
        .order_by(ReportSchedule.created_at.desc())
    )
    return [_to_response(r) for r in result.scalars().all()]


@router.get("/schedule/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: UUID,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> ScheduleResponse:
    """Fetch one report schedule."""
    return _to_response(await _get_or_404(session, tenant_id, schedule_id))


@router.patch("/schedule/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: UUID,
    body: ScheduleUpdate,
    tenant_id: UUID = Depends(require_tenant_header),
    actor_id: UUID = Depends(require_user_uuid),
    session: AsyncSession = Depends(get_session),
) -> ScheduleResponse:
    """Patch a report schedule. Only the supplied fields change."""
    row = await _get_or_404(session, tenant_id, schedule_id)
    before = _to_response(row).model_dump(mode="json")

    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    for field, value in changes.items():
        setattr(row, field, value)
    await session.flush()
    await write_audit(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action="UPDATE",
        entity_type="report_schedule",
        entity_id=row.id,
        before=before,
        after=_to_response(row).model_dump(mode="json"),
    )
    await session.commit()
    return _to_response(row)


@router.delete("/schedule/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: UUID,
    tenant_id: UUID = Depends(require_tenant_header),
    actor_id: UUID = Depends(require_user_uuid),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a report schedule."""
    row = await _get_or_404(session, tenant_id, schedule_id)
    before = _to_response(row).model_dump(mode="json")
    await write_audit(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action="DELETE",
        entity_type="report_schedule",
        entity_id=row.id,
        before=before,
    )
    await session.delete(row)
    await session.commit()


@router.post("/generate", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def generate_report(
    body: GenerateRequest,
    tenant_id: UUID = Depends(require_tenant_header),
    actor_id: UUID = Depends(require_user_uuid),
    session: AsyncSession = Depends(get_session),
) -> RunResponse:
    """Run a report generator now and persist the result as a ReportRun.

    A generator failure is recorded (``status="failed"`` + ``error``)
    rather than discarded — the run row is the audit record.
    """
    try:
        payload = await run_generator(
            body.report_type, session, tenant_id, body.period_start, body.period_end
        )
        run_status, error = "generated", None
    except Exception as exc:  # generator / DB failure — record it
        logger.warning("report generation failed (%s): %s", body.report_type, exc)
        payload, run_status, error = {}, "failed", str(exc)

    run = ReportRun(
        tenant_id=tenant_id,
        schedule_id=body.schedule_id,
        report_type=body.report_type,
        status=run_status,
        generated_at=datetime.utcnow(),
        delivered_to=[],
        payload=payload,
        error=error,
    )
    session.add(run)
    await session.flush()
    await write_audit(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action="INSERT",
        entity_type="report_run",
        entity_id=run.id,
        after={"report_type": body.report_type, "status": run_status},
    )
    await session.commit()
    return _run_to_response(run)


class EmailRequest(BaseModel):
    report_type: ReportType
    recipients: List[str] = Field(..., min_length=1)
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    format: ReportFormat = "csv"
    schedule_id: Optional[UUID] = None


@router.post("/email", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def email_report(
    body: EmailRequest,
    tenant_id: UUID = Depends(require_tenant_header),
    actor_id: UUID = Depends(require_user_uuid),
    session: AsyncSession = Depends(get_session),
) -> RunResponse:
    """Generate a report and email it to ``recipients``.

    The ReportRun records the outcome: ``delivered`` (sent, or skipped
    because SMTP is disabled in dev) or ``failed`` (generation or SMTP
    error, with ``error`` populated).
    """
    payload: dict = {}
    delivered_to: List[str] = []
    run_status = "pending"
    error: Optional[str] = None

    try:
        payload = await run_generator(
            body.report_type, session, tenant_id, body.period_start, body.period_end
        )
        attachment = serialize_report(payload, body.format)
        delivery = await send_report_email(
            body.recipients,
            subject=f"ProdPlan ONE — relatório {body.report_type}",
            body=f"Relatório {body.report_type} em anexo ({body.format}).",
            attachment_name=f"{body.report_type}.{body.format}",
            attachment_text=attachment,
        )
        delivered_to = delivery["recipients"]
        run_status = "delivered"
    except EmailDeliveryError as exc:
        run_status, error = "failed", f"email delivery failed: {exc}"
    except Exception as exc:  # generation / serialisation failure
        logger.warning("email_report failed (%s): %s", body.report_type, exc)
        run_status, error = "failed", str(exc)

    run = ReportRun(
        tenant_id=tenant_id,
        schedule_id=body.schedule_id,
        report_type=body.report_type,
        status=run_status,
        generated_at=datetime.utcnow(),
        delivered_to=delivered_to,
        payload=payload,
        error=error,
    )
    session.add(run)
    await session.flush()
    await write_audit(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action="INSERT",
        entity_type="report_run",
        entity_id=run.id,
        after={"report_type": body.report_type, "status": run_status},
    )
    await session.commit()
    return _run_to_response(run)


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------


class RetentionPolicyResponse(BaseModel):
    default_retention_days: int
    total_runs: int
    schedules: List[dict]


class RetentionCleanupResponse(BaseModel):
    deleted: int


@router.get("/retention", response_model=RetentionPolicyResponse)
async def get_retention_policy(
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> RetentionPolicyResponse:
    """Show the retention policy: per-schedule ``retention_days`` and
    the current ``ReportRun`` count."""
    schedules = (
        await session.execute(
            select(ReportSchedule).where(ReportSchedule.tenant_id == tenant_id)
        )
    ).scalars().all()
    total_runs = (
        await session.execute(
            select(func.count())
            .select_from(ReportRun)
            .where(ReportRun.tenant_id == tenant_id)
        )
    ).scalar() or 0

    return RetentionPolicyResponse(
        default_retention_days=DEFAULT_RETENTION_DAYS,
        total_runs=int(total_runs),
        schedules=[
            {
                "id": str(s.id),
                "report_type": s.report_type,
                "retention_days": s.retention_days,
            }
            for s in schedules
        ],
    )


@router.post("/retention", response_model=RetentionCleanupResponse)
async def trigger_retention_cleanup(
    tenant_id: UUID = Depends(require_tenant_header),
    actor_id: UUID = Depends(require_user_uuid),
    session: AsyncSession = Depends(get_session),
) -> RetentionCleanupResponse:
    """Manually run the retention cleanup for this tenant.

    Deletes expired ``ReportRun`` rows; each deletion is audited inside
    :func:`cleanup_expired_runs`.
    """
    deleted = await cleanup_expired_runs(session, tenant_id)
    return RetentionCleanupResponse(deleted=deleted)
