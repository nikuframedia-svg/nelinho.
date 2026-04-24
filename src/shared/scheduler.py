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
    mold_health_interval_minutes: int = 60 * 24,
    quality_scoring_interval_minutes: int = 30,
) -> None:
    """Register per-tenant background jobs.

    * **alerts_scan** — every `interval_minutes` (default 15 min)
    * **shortage_scan** — every `shortage_interval_minutes` (Sprint O.4)
    * **mold_health_scan** — daily (Sprint R.6.2); also emits AL08 alerts
    * **quality_risk_scoring** — every 30 min (Sprint R.2)
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
    _scheduler.add_job(
        _mold_health_scan_job,
        trigger=IntervalTrigger(minutes=mold_health_interval_minutes),
        args=[tenant_id],
        id=f"mold_health_scan:{tenant_id}",
        name=f"mold_health_scan[{tenant_id}]",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    _scheduler.add_job(
        _quality_risk_scoring_job,
        trigger=IntervalTrigger(minutes=quality_scoring_interval_minutes),
        args=[tenant_id],
        id=f"quality_risk_scoring:{tenant_id}",
        name=f"quality_risk_scoring[{tenant_id}]",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    # Sprint C 2.3 — PreferenceRuleDetector (Camada 1 aprendizagem).
    # Runs once a day, at 03:00 UTC, when the ERP is quiet and the
    # previous day's commits are fully flushed. 30-day window scans
    # ~1-2k commits in seconds for a single tenant.
    _scheduler.add_job(
        _preference_rule_detector_job,
        trigger=CronTrigger(hour=3, minute=0, timezone="UTC"),
        args=[tenant_id],
        id=f"preference_rule_detector:{tenant_id}",
        name=f"preference_rule_detector[{tenant_id}]",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    # Sprint D.4 — AdaptiveFitnessWeights (Camada 2). Weekly retrain on
    # Sunday 02:00 UTC so the weights the GA reads on Monday morning are
    # fresh. Weekly cadence (not daily) matches the sample budget: <50
    # new pairs per day for most tenants, so a longer accumulation window
    # avoids training on noise.
    _scheduler.add_job(
        _preference_weights_retrain_job,
        trigger=CronTrigger(day_of_week=6, hour=2, minute=0, timezone="UTC"),
        args=[tenant_id],
        id=f"preference_weights_retrain:{tenant_id}",
        name=f"preference_weights_retrain[{tenant_id}]",
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

async def _mold_health_scan_job(tenant_id: UUID) -> None:
    """Recompute mold health daily + emit AL08 alerts (Sprint R.6.2/R.6.3)."""
    from src.plan.services.mold_service import MoldService
    from src.shared.database import get_session_context

    started = datetime.utcnow()
    try:
        async with get_session_context() as session:
            svc = MoldService(session, tenant_id)
            molds = await svc.list_molds()
            scored = 0
            for mold in molds:
                await svc.recompute_health(mold)
                scored += 1
            alerts = await svc.emit_maintenance_alerts()
            await session.commit()
        elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
        logger.info(
            "mold_health_scan tenant=%s scored=%s alerts=%s elapsed_ms=%s",
            tenant_id, scored, alerts, elapsed_ms,
        )
    except Exception as exc:
        logger.error("mold_health_scan tenant=%s failed: %s", tenant_id, exc, exc_info=True)


async def _quality_risk_scoring_job(tenant_id: UUID) -> None:
    """Stub for Sprint R.2 — real scoring wired when ProductionSchedule flow
    has enough data. The job logs today so observability is consistent."""
    logger.info(
        "quality_risk_scoring tenant=%s (stub — wire scoring model when ready)",
        tenant_id,
    )


async def _preference_rule_detector_job(tenant_id: UUID) -> None:
    """Sprint C 2.3 — run Camada 1 learning detector nightly.

    Mines `ScheduleCommit.rejected_alternatives` from the last 30 days
    and persists new `PreferenceRule` rows in `governance.preference_rule`
    for operator review (`status=detected`). Operator then confirms or
    rejects via `/admin/learned-rules` (frontend — not wired yet).

    Best-effort: a failure here never blocks other jobs. If the detector
    import fails (e.g. partial deploy) the log captures it and the job
    returns cleanly.
    """
    try:
        from src.governance.preference_learning import PreferenceRuleDetector
    except ImportError:
        logger.debug(
            "preference_rule_detector module missing — skipping tenant=%s",
            tenant_id,
        )
        return

    from src.shared.database import get_session_context

    started = datetime.utcnow()
    try:
        async with get_session_context() as session:
            detector = PreferenceRuleDetector(session, tenant_id)
            rules = await detector.scan(window_days=30)
            await session.commit()
        elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
        logger.info(
            "preference_rule_detector tenant=%s rules_detected=%s elapsed_ms=%s",
            tenant_id, len(rules), elapsed_ms,
        )
    except Exception as exc:
        logger.error(
            "preference_rule_detector tenant=%s failed: %s",
            tenant_id, exc, exc_info=True,
        )


async def _preference_weights_retrain_job(tenant_id: UUID) -> None:
    """Sprint D.4 — weekly retrain of AdaptiveFitnessWeights (Camada 2).

    Pulls recent commits with rejected alternatives, fits a pairwise
    logistic regression on the KPI deltas, and persists the blended
    weights under ``tenant_config(governance, adaptive_fitness_weights)``.

    Below the minimum sample threshold the retainer returns
    ``status="skipped"`` and the previously persisted weights (or
    domain defaults) remain in effect. Any exception is swallowed —
    a broken training run must never break the scheduler thread.
    """
    try:
        from src.governance.preference_learning import AdaptiveFitnessWeights
    except ImportError:
        logger.debug(
            "adaptive_fitness_weights module missing — skipping tenant=%s",
            tenant_id,
        )
        return

    from src.shared.database import get_session_context

    started = datetime.utcnow()
    try:
        async with get_session_context() as session:
            retainer = AdaptiveFitnessWeights(session, tenant_id)
            result = await retainer.retrain(window_days=30)
            await session.commit()
        elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
        logger.info(
            "preference_weights_retrain tenant=%s status=%s pairs=%s commits=%s elapsed_ms=%s",
            tenant_id, result.status, result.pairs_used,
            result.commits_scanned, elapsed_ms,
        )
    except Exception as exc:
        logger.error(
            "preference_weights_retrain tenant=%s failed: %s",
            tenant_id, exc, exc_info=True,
        )


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
