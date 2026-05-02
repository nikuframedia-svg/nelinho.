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

    # Sprint Q.13.B (B3) — daily audit log retention purge.
    # Runs once globally at 04:30 UTC (after ABL 04:00, well before
    # next preference detector at 03:00). Cross-tenant scope means the
    # job purges the audit tables once per day rather than per tenant.
    _scheduler.add_job(
        _audit_retention_purge_job,
        trigger=CronTrigger(hour=4, minute=30, timezone="UTC"),
        id="audit_retention_purge",
        name="audit_retention_purge",
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
    # Sprint R.3 — ABL feedback (Camada 4). Runs daily 04:00 UTC, after
    # the preference rule detector (03:00) so the two never contend on
    # DB locks. Reads yesterday's CausalChain + verification rows from
    # CopilotMessage.content_structured and emits ABL JSONL triplets
    # for the upcoming Camada 3 fine-tune.
    _scheduler.add_job(
        _abl_feedback_job,
        trigger=CronTrigger(hour=4, minute=0, timezone="UTC"),
        args=[tenant_id],
        id=f"abl_feedback:{tenant_id}",
        name=f"abl_feedback[{tenant_id}]",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    # Sprint R.5.4 — DPO fine-tune candidate (Camada 3, OPT-IN).
    # Runs Sunday 03:00 UTC, but only when ConfigStore key
    # learning.fine_tune.enabled is True. The job builds the candidate
    # adapter; promote is always a separate human action via
    # POST /v1/governance/learning/adapter/promote/{version}.
    _scheduler.add_job(
        _dpo_finetune_job,
        trigger=CronTrigger(day_of_week=6, hour=3, minute=0, timezone="UTC"),
        args=[tenant_id],
        id=f"dpo_finetune:{tenant_id}",
        name=f"dpo_finetune[{tenant_id}]",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    # Sprint Q.13.D D.2 — PCMCI+ causal discovery (Camada 4 → DAG).
    # Runs weekly on Sundays 05:00 UTC (after the Camada-2 retrain at
    # 02:00 and the DPO fine-tune at 03:00). Gated by ConfigStore key
    # ``learning.discovery.enabled`` (default False); when off the job
    # logs and returns immediately. Discovery edges are stored in
    # ``governance.causal_discovery_report`` for operator review — the
    # SCM (NELO_DAG) is NEVER mutated automatically.
    _scheduler.add_job(
        _causal_discovery_job,
        trigger=CronTrigger(day_of_week=6, hour=5, minute=0, timezone="UTC"),
        args=[tenant_id],
        id=f"causal_discovery:{tenant_id}",
        name=f"causal_discovery[{tenant_id}]",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    # Sprint Q.13.D D.3 — improve adoption signal feedback loop.
    # Runs daily 04:15 UTC, between abl_feedback (04:00) and audit
    # retention purge (04:30). Reads yesterday's terminal DecisionRun
    # rows (executed / executed_partial / rejected) and feeds each
    # decision_type back into ImproveService.record_adoption_signal so
    # the matching pending suggestions' confidence rises with adoption
    # and falls with rejection (Bayesian Beta-Bernoulli, capped at N=50).
    _scheduler.add_job(
        _improve_adoption_signal_job,
        trigger=CronTrigger(hour=4, minute=15, timezone="UTC"),
        args=[tenant_id],
        id=f"improve_adoption_signal:{tenant_id}",
        name=f"improve_adoption_signal[{tenant_id}]",
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


async def _dpo_finetune_job(tenant_id: UUID) -> None:
    """Sprint R.5.4 — weekly DPO fine-tune candidate (Camada 3).

    Runs Sunday 03:00 UTC. Reads ConfigStore key
    ``learning.fine_tune.enabled`` and bails if it's false (default).
    The job NEVER promotes — it just builds a dataset, runs
    ``run_finetune`` in smoke mode (or real, if the GPU stack is
    present), and writes the report next to a versioned adapter
    directory. The R.1 dashboard surfaces "candidate pending" and a
    human carries out the promote via the API.
    """
    from datetime import timedelta

    try:
        from src.governance.preference_learning import DPODatasetBuilder
        from src.governance.preference_learning.dataset_mixer import (
            discover_abl_files,
            mix_datasets,
        )
    except ImportError:
        logger.debug(
            "dpo_finetune module missing — skipping tenant=%s", tenant_id,
        )
        return

    try:
        from scripts.dpo_finetune import run_finetune  # type: ignore
    except ImportError:
        try:
            import sys
            from pathlib import Path as _P

            scripts_dir = _P(__file__).resolve().parents[2] / "scripts"
            if str(scripts_dir) not in sys.path:
                sys.path.insert(0, str(scripts_dir))
            from dpo_finetune import run_finetune  # type: ignore
        except ImportError as exc:
            logger.warning(
                "dpo_finetune script unavailable — skipping tenant=%s (%s)",
                tenant_id, exc,
            )
            return

    from pathlib import Path
    from src.core.services.tenant_config_service import TenantConfigService
    from src.shared.database import get_session_context

    started = datetime.utcnow()
    today = started.date()
    try:
        async with get_session_context() as session:
            cfg_svc = TenantConfigService(session, tenant_id)
            enabled = await cfg_svc.get(
                "learning", "fine_tune.enabled", default=False,
            )
            if not enabled:
                logger.info(
                    "dpo_finetune tenant=%s SKIPPED (learning.fine_tune.enabled=false)",
                    tenant_id,
                )
                return

            # Build DPO source from commits.
            dpo_dir = Path("data/learning/datasets")
            dpo_jsonl = dpo_dir / f"dpo_{tenant_id}_{today.isoformat()}.jsonl"
            builder = DPODatasetBuilder(session, tenant_id)
            await builder.build(window_days=90, output_path=dpo_jsonl)

        # Mix DPO + ABL outside the DB session.
        abl_files = discover_abl_files(Path("data/learning/abl_triplets"))
        mixed_path = dpo_dir / f"dataset_{tenant_id}_{today.isoformat()}.jsonl"
        manifest = mix_datasets(
            dpo_paths=[dpo_jsonl] if dpo_jsonl.exists() else [],
            abl_paths=abl_files,
            output_path=mixed_path,
            seed=42,
        )

        adapter_dir = Path("models/adapters") / f"gemma4-8b-nelo-{today.isoformat()}"
        report = run_finetune(
            dataset_path=mixed_path,
            output_path=adapter_dir,
            base_model="google/gemma-2-9b-it",
            config={},
            smoke=True,  # never auto-train on prod box without explicit opt-in
        )
        elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
        logger.info(
            "dpo_finetune tenant=%s status=%s pairs=%d adapter=%s elapsed_ms=%s",
            tenant_id, report.status, manifest.triplets_total,
            adapter_dir, elapsed_ms,
        )
    except Exception as exc:
        logger.error(
            "dpo_finetune tenant=%s failed: %s",
            tenant_id, exc, exc_info=True,
        )


async def _causal_discovery_job(tenant_id: UUID) -> None:
    """Sprint Q.13.D D.2 — weekly PCMCI+ causal-discovery run.

    Gated by ``learning.discovery.enabled`` (ConfigStore, default False).
    When the flag is on, the job runs :func:`discover_edges` and
    persists a `CausalDiscoveryReport` row in ``governance``. The SCM
    (`NELO_DAG`) is NEVER mutated by the job — discovered edges go to
    the operator review surface (frontend not wired yet).

    Telemetry source: best-effort. Until the ERP shadow-mode (Sprint G)
    feeds real time-series, the production path passes ``series=None
    allow_synthetic=False``, and `discover_edges` correctly returns
    ``status="unavailable"``. The row still gets persisted so operators
    can see "the job ran, no telemetry, no candidates" in the audit
    trail. In ``settings.environment != "production"``, the job uses
    ``allow_synthetic=True`` so the wiring is exercised end-to-end.

    Best-effort: any exception is swallowed and logged. The discovery
    pipeline is a side-effect — never blocks the scheduler.
    """
    try:
        from src.copilot.causal.discovery import (
            discover_edges,
            persist_discovery_report,
        )
    except ImportError:
        logger.debug(
            "causal_discovery: module missing — skipping tenant=%s", tenant_id,
        )
        return

    from src.core.services.tenant_config_service import TenantConfigService
    from src.shared.config import settings as _settings
    from src.shared.database import get_session_context

    started = datetime.utcnow()
    try:
        async with get_session_context() as session:
            cfg_svc = TenantConfigService(session, tenant_id)
            enabled = await cfg_svc.get(
                "learning", "discovery.enabled", default=False,
            )
            if not enabled:
                logger.info(
                    "causal_discovery tenant=%s SKIPPED "
                    "(learning.discovery.enabled=false)",
                    tenant_id,
                )
                return

            allow_synthetic = (
                getattr(_settings, "environment", "production") != "production"
            )
            # `discover_edges` is sync (CPU-bound numerical); call directly.
            report = discover_edges(
                series=None,
                allow_synthetic=allow_synthetic,
            )
            await persist_discovery_report(
                session=session, tenant_id=tenant_id, report=report,
            )
            await session.commit()
        elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
        logger.info(
            "causal_discovery tenant=%s status=%s sample_size=%d "
            "candidates=%d elapsed_ms=%d",
            tenant_id, report.status, report.sample_size,
            len(report.candidate_edges), elapsed_ms,
        )
    except Exception as exc:
        logger.error(
            "causal_discovery tenant=%s failed: %s",
            tenant_id, exc, exc_info=True,
        )


async def _improve_adoption_signal_job(tenant_id: UUID) -> None:
    """Sprint Q.13.D D.3 — feed yesterday's DecisionRun outcomes into
    `ImproveService.record_adoption_signal`.

    Closes Camada 1's confidence-calibrator loop: when an operator
    executes a decision the system had been suggesting, every pending
    suggestion with the matching ``action_type`` gets its confidence
    nudged up; when an operator rejects a decision, the matching
    suggestions' confidence drops. The Beta-Bernoulli math + cap at
    N=50 lives inside `record_adoption_signal`; this job is just the
    polling glue.

    Why polling instead of a Kafka-style subscriber? The decision
    pipeline already commits to Postgres before any side effects fire;
    once-a-day polling avoids needing in-process events to be reliable
    AND keeps a clean audit trail (the job log line records the
    yesterday-window summary).

    Best-effort: per-decision exceptions are swallowed so one bad row
    can't block the rest. The job log captures the totals.
    """
    from datetime import timedelta

    try:
        from sqlalchemy import select
        from src.governance.models import DecisionRun, DecisionStatus
        from src.improve.service import ImproveService
    except ImportError:
        logger.debug(
            "improve_adoption_signal: import missing — skipping tenant=%s",
            tenant_id,
        )
        return

    from src.shared.database import get_session_context

    started = datetime.utcnow()
    cutoff = started - timedelta(days=1)
    accepted_statuses = {
        DecisionStatus.EXECUTED.value,
        DecisionStatus.EXECUTED_PARTIAL.value,
    }
    rejected_statuses = {DecisionStatus.REJECTED.value}

    accepted_signals = 0
    rejected_signals = 0
    suggestions_updated = 0
    failed = 0
    try:
        async with get_session_context() as session:
            stmt = (
                select(
                    DecisionRun.decision_type,
                    DecisionRun.status,
                )
                .where(DecisionRun.tenant_id == tenant_id)
                .where(
                    DecisionRun.status.in_(
                        list(accepted_statuses | rejected_statuses)
                    )
                )
                # Use executed_at when set; fall back to proposed_at for
                # rejected rows that never got an execute timestamp.
                .where(
                    (DecisionRun.executed_at >= cutoff)
                    | (
                        (DecisionRun.executed_at.is_(None))
                        & (DecisionRun.proposed_at >= cutoff)
                    )
                )
            )
            rows = (await session.execute(stmt)).all()

            svc = ImproveService(session, tenant_id)
            for decision_type, status in rows:
                if not decision_type:
                    continue
                accepted = status in accepted_statuses
                try:
                    n = await svc.record_adoption_signal(
                        action_type=decision_type,
                        accepted=accepted,
                    )
                except Exception as exc:
                    failed += 1
                    logger.debug(
                        "improve_adoption_signal: per-decision failure "
                        "(%s) tenant=%s decision_type=%s",
                        exc, tenant_id, decision_type,
                    )
                    continue
                suggestions_updated += n
                if accepted:
                    accepted_signals += 1
                else:
                    rejected_signals += 1
            await session.commit()
        elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
        logger.info(
            "improve_adoption_signal tenant=%s accepted=%d rejected=%d "
            "suggestions_updated=%d failed=%d elapsed_ms=%d",
            tenant_id, accepted_signals, rejected_signals,
            suggestions_updated, failed, elapsed_ms,
        )
    except Exception as exc:
        logger.error(
            "improve_adoption_signal tenant=%s failed: %s",
            tenant_id, exc, exc_info=True,
        )


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


async def _abl_feedback_job(tenant_id: UUID) -> None:
    """Sprint R.3 — capture ABL divergences daily (Camada 4 → Camada 3).

    Pulls yesterday's chain + verification pairs (from
    ``CopilotMessage.content_structured`` once that wiring lands), runs
    the divergence detector, and appends DPO-shaped triplets to
    ``data/learning/abl_triplets/{date}.jsonl``. Until the chain
    capture is wired, the job logs a clean skip — no triplets, no
    crash, the daily window is just not productive yet.
    """
    from datetime import timedelta

    try:
        from src.copilot.jobs.abl_feedback import (
            _load_chain_pairs_from_db,
            run_abl_feedback,
        )
    except ImportError:
        logger.debug(
            "abl_feedback module missing — skipping tenant=%s", tenant_id,
        )
        return

    target = (datetime.utcnow() - timedelta(days=1)).date()
    started = datetime.utcnow()
    try:
        pairs = await _load_chain_pairs_from_db(tenant_id, target)
        report = run_abl_feedback(
            pairs, tenant_id=tenant_id, today=target,
        )
        elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
        logger.info(
            "abl_feedback tenant=%s date=%s chains=%d divergences=%d "
            "written=%d elapsed_ms=%s",
            tenant_id, report.target_date,
            report.chains_processed, report.divergences_detected,
            report.triplets_written, elapsed_ms,
        )
    except Exception as exc:
        logger.error(
            "abl_feedback tenant=%s failed: %s",
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
