"""Q.66.A.4 — job global de purge de retenção do audit log.

Movido de `src.shared.scheduler` sem alterações de comportamento.
"""

from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


async def _audit_retention_purge_job() -> None:
    """Sprint Q.13.B (B3) — daily audit-log retention purge.

    Three classes of audit rows grow unbounded in production:

      * ``copilot.copilot_action_logs.executed_at``: every Copilot
        action ever taken — once `status='rolled_back'` or it's well
        past the rollback window, the audit value drops to ~zero.
      * ``governance.approval.created_at``: every approval/rejection
        on a closed decision. Kept for compliance for the retention
        window; older rows can be archived/dropped.
      * ``plan.schedule_commit.cpo_meta``: the bulky JSONB carrying
        GA elites + MAP-Elites grid + safety-net debug. We DON'T drop
        the commit row itself (that's the chain) — just NULL the
        cpo_meta blob on commits older than the retention window.
        The KPIs + delta + alternatives stay intact.

    Retention window comes from ConfigStore key
    ``system.audit.retention_days`` (default 90). Setting this to 0
    or negative disables the job for that tenant — operators in
    regulated environments can extend to 365+ days.

    The job is GLOBAL (not per-tenant) because the audit tables are
    cross-tenant scoped already. Runs at 04:30 UTC, after ABL
    feedback (04:00) and well before the next preference rule
    detector window (03:00 the following day).

    Best-effort: each table purge is in its own try/except so a lock
    contention or schema mismatch on one table doesn't block the
    others.
    """
    from datetime import timedelta

    from src.shared.database import get_session_context

    started = datetime.utcnow()
    retention_days = 90  # safe default if config lookup fails
    try:
        from src.core.services.tenant_config_service import TenantConfigService
        # Read from a sentinel "system tenant" — same convention used by
        # other system-level configs. When the tenant config schema
        # isn't multi-tenant for `system.*` we fall through to default.
        async with get_session_context() as cfg_session:
            # Use the first active tenant as a proxy — `system.*` keys
            # are tenant-replicated for now (Sprint Q.13 doesn't fix the
            # multi-tenant config split; that's a separate piece).
            from sqlalchemy import select
            from src.core.models.tenant import Tenant
            row = (await cfg_session.execute(
                select(Tenant.id).limit(1)
            )).scalar_one_or_none()
            if row is not None:
                cfg_svc = TenantConfigService(cfg_session, row)
                value = await cfg_svc.get(
                    "system", "audit.retention_days", default=90,
                )
                if value is not None:
                    try:
                        retention_days = int(value)
                    except (ValueError, TypeError):
                        pass
    except Exception as exc:
        logger.warning(
            "audit_retention_purge: config lookup failed (%s) — using default %d days",
            exc, retention_days,
        )

    if retention_days <= 0:
        logger.info(
            "audit_retention_purge: disabled (retention_days=%d)", retention_days,
        )
        return

    cutoff = started - timedelta(days=retention_days)
    logger.info(
        "audit_retention_purge: cutoff=%s retention_days=%d",
        cutoff.isoformat(), retention_days,
    )

    purged_action_logs = 0
    purged_approvals = 0
    cleared_cpo_meta = 0

    # ── copilot_action_logs purge ────────────────────────────────────
    try:
        from sqlalchemy import delete
        from src.copilot.models import CopilotActionLog
        async with get_session_context() as session:
            stmt = delete(CopilotActionLog).where(
                CopilotActionLog.executed_at < cutoff
            )
            result = await session.execute(stmt)
            purged_action_logs = result.rowcount or 0
            await session.commit()
    except Exception as exc:
        logger.warning(
            "audit_retention_purge: copilot_action_logs purge failed: %s", exc,
        )

    # ── governance.approval purge ────────────────────────────────────
    try:
        from sqlalchemy import delete
        from src.governance.models import ApprovalRequest
        async with get_session_context() as session:
            stmt = delete(ApprovalRequest).where(
                ApprovalRequest.created_at < cutoff
            )
            result = await session.execute(stmt)
            purged_approvals = result.rowcount or 0
            await session.commit()
    except Exception as exc:
        logger.warning(
            "audit_retention_purge: approval purge failed: %s", exc,
        )

    # ── schedule_commit.cpo_meta clear ───────────────────────────────
    # Keep the commit row (chain integrity); just NULL the bulky meta.
    try:
        from sqlalchemy import update
        from src.plan.cpo.commits import ScheduleCommit
        async with get_session_context() as session:
            stmt = (
                update(ScheduleCommit)
                .where(ScheduleCommit.created_at < cutoff)
                .where(ScheduleCommit.cpo_meta != {})
                .values(cpo_meta={})
            )
            result = await session.execute(stmt)
            cleared_cpo_meta = result.rowcount or 0
            await session.commit()
    except Exception as exc:
        logger.warning(
            "audit_retention_purge: cpo_meta clear failed: %s", exc,
        )

    elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
    logger.info(
        "audit_retention_purge: action_logs=%d approvals=%d "
        "cpo_meta_cleared=%d elapsed_ms=%d",
        purged_action_logs, purged_approvals, cleared_cpo_meta, elapsed_ms,
    )
