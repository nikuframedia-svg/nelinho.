"""
ProdPlan ONE - Background Scheduler (APScheduler wrapper)
=========================================================

Single-process AsyncIO scheduler used by Sprint C jobs:
- alerts scan (every 15 min) → `AlertsEngine.scan()` per active tenant
- daily feedback generation (00:30) → `generate_daily_feedback()`

Multi-worker deployments need distributed locking (not implemented here) —
for the current single-uvicorn-worker dev setup, an in-process scheduler is
enough. See docstring of `start_scheduler` for the upgrade path.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    APSCHEDULER_AVAILABLE = True
except ImportError:  # pragma: no cover
    APSCHEDULER_AVAILABLE = False

logger = logging.getLogger(__name__)


# Module-level singleton so jobs can be inspected / tested
_scheduler: Optional["AsyncIOScheduler"] = None


def get_scheduler() -> Optional["AsyncIOScheduler"]:
    """Return the global scheduler instance (or None if not started)."""
    return _scheduler


def start_scheduler(
    tenants: Optional[List[UUID]] = None,
    alerts_interval_minutes: int = 15,
    daily_feedback_cron: str = "30 0 * * *",
) -> Optional["AsyncIOScheduler"]:
    """
    Start the global AsyncIOScheduler with the default Sprint C jobs.

    Args:
        tenants: Tenants to scan for alerts each tick. If omitted, the scheduler
            is started empty and callers can add tenants via `register_tenant`.
        alerts_interval_minutes: How often to run the alerts scan.
        daily_feedback_cron: Cron expression for the daily feedback job (UTC).

    Returns:
        The scheduler instance, or None if APScheduler is not installed.

    Scaling note: this runs in-process. For multi-worker deployments, replace
    with a distributed job runner (Celery/Temporal) or run a single dedicated
    scheduler worker.
    """
    global _scheduler

    if not APSCHEDULER_AVAILABLE:
        logger.warning("APScheduler not installed — background jobs disabled")
        return None

    if _scheduler is not None and _scheduler.running:
        logger.info("Scheduler already running — skipping start")
        return _scheduler

    _scheduler = AsyncIOScheduler(timezone="UTC")

    # Alerts scan — one job per tenant, identified by tenant id in job_id
    if tenants:
        for tid in tenants:
            _scheduler.add_job(
                _alerts_scan_job,
                trigger=IntervalTrigger(minutes=alerts_interval_minutes),
                args=[tid],
                id=f"alerts_scan:{tid}",
                name=f"alerts_scan[{tid}]",
                replace_existing=True,
                coalesce=True,
                max_instances=1,
            )

    # Daily feedback — single global job (tenants list iterated inside)
    _scheduler.add_job(
        _daily_feedback_job,
        trigger=CronTrigger.from_crontab(daily_feedback_cron, timezone="UTC"),
        args=[tenants or []],
        id="daily_feedback",
        name="daily_feedback",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )

    _scheduler.start()
    logger.info(
        f"Scheduler started: alerts every {alerts_interval_minutes}m for "
        f"{len(tenants or [])} tenant(s); daily_feedback='{daily_feedback_cron}' UTC"
    )
    return _scheduler


def register_tenant(
    tenant_id: UUID,
    interval_minutes: int = 15,
    shortage_interval_minutes: int = 60,
) -> None:
    """Register per-tenant background jobs.

    * **alerts_scan** — every `interval_minutes` (default 15 min) — runs the
      copilot AlertsEngine (4 detectors).
    * **shortage_scan** — every `shortage_interval_minutes` (default 60 min
      per Sprint O.4) — runs the supply.ShortageDetector.
    """
    if _scheduler is None:
        logger.warning("register_tenant called before start_scheduler")
        return
    _scheduler.add_job(
        _alerts_scan_job,
        trigger=IntervalTrigger(minutes=interval_minutes),
        args=[tenant_id],
        id=f"alerts_scan:{tenant_id}",
        name=f"alerts_scan[{tenant_id}]",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    _scheduler.add_job(
        _shortage_scan_job,
        trigger=IntervalTrigger(minutes=shortage_interval_minutes),
        args=[tenant_id],
        id=f"shortage_scan:{tenant_id}",
        name=f"shortage_scan[{tenant_id}]",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )


async def shutdown_scheduler() -> None:
    """Stop the scheduler on app shutdown."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler shut down")
    _scheduler = None


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

async def _shortage_scan_job(tenant_id: UUID) -> None:
    """Run ShortageDetector.scan() hourly for a single tenant (Sprint O.4)."""
    from src.shared.database import get_session_context
    from src.supply.shortage_detector import ShortageDetector

    started = datetime.utcnow()
    try:
        async with get_session_context() as session:
            detector = ShortageDetector(session=session, tenant_id=tenant_id)
            summary = await detector.scan()
            await session.commit()
        elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
        logger.info(
            "shortage_scan tenant=%s warn=%s critical=%s skipped=%s elapsed_ms=%s",
            tenant_id, summary.get("warn_created"),
            summary.get("critical_created"), summary.get("skipped_duplicate"),
            elapsed_ms,
        )
    except Exception as exc:
        logger.error("shortage_scan tenant=%s failed: %s", tenant_id, exc, exc_info=True)


async def _alerts_scan_job(tenant_id: UUID) -> None:
    """Run AlertsEngine.scan() for a single tenant, own session."""
    from src.copilot.alerts.engine import AlertsEngine
    from src.shared.database import get_session_context

    started = datetime.utcnow()
    try:
        async with get_session_context() as session:
            engine = AlertsEngine(session=session, tenant_id=tenant_id)
            summary = await engine.scan()
            await session.commit()
        elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
        logger.info(
            f"alerts_scan tenant={tenant_id} created={summary.get('created')} "
            f"skipped={summary.get('skipped_duplicate')} elapsed_ms={elapsed_ms}"
        )
    except Exception as e:
        logger.error(f"alerts_scan failed for tenant={tenant_id}: {e}", exc_info=True)


async def _daily_feedback_job(tenant_ids: List[UUID]) -> None:
    """Regenerate daily feedback for each tenant. No-op if job module missing."""
    try:
        from src.copilot.jobs.daily_feedback import generate_daily_feedback
    except ImportError:
        logger.debug("daily_feedback job module not available — skipping")
        return

    from src.shared.database import get_session_context

    for tid in tenant_ids:
        try:
            async with get_session_context() as session:
                await generate_daily_feedback(session, tid)
                await session.commit()
            logger.info(f"daily_feedback generated for tenant={tid}")
        except Exception as e:
            logger.error(f"daily_feedback failed for tenant={tid}: {e}", exc_info=True)
