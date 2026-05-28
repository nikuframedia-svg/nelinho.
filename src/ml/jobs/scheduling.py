"""
ProdPlan ONE — ML Retrain Job Scheduling
=========================================

Registers the cron-driven retrain jobs (Duration, QualityRisk) with the
global APScheduler. Called from `main.py` lifespan after `start_scheduler`.

The Surrogate model is event-driven (Sprint F GA triggers it after N
real evaluations), not cron, so it is deliberately not registered here.
"""

from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


def register_ml_retrain_jobs(
    scheduler,
    tenants: Optional[List[UUID]] = None,
) -> int:
    """
    Add Duration + QualityRisk + OTDRisk retrain jobs to the scheduler.

    Returns the number of jobs registered. No-op if the scheduler is None
    (APScheduler unavailable) or the tenant list is empty.
    """
    if scheduler is None:
        return 0
    tenant_list = tenants or []
    if not tenant_list:
        logger.info(
            "register_ml_retrain_jobs: no active tenants — skip. Tenants can "
            "be registered later via src.shared.scheduler.register_tenant()."
        )
        return 0

    try:
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning("APScheduler not installed — ML retrain jobs disabled")
        return 0

    from src.ml.models_domain.duration import DurationRetrainJob
    from src.ml.models_domain.otd_risk import OTDRiskRetrainJob
    from src.ml.models_domain.quality_risk import QualityRiskRetrainJob
    from src.ml.models_domain.sequence_mining import SequenceMiningRetrainJob
    from src.ml.models_domain.throughput_forecast import ThroughputForecastRetrainJob
    from src.ml.observability.drift import DriftDetectionJob

    job_specs = [
        ("duration", DurationRetrainJob, DurationRetrainJob.schedule_cron),
        ("quality_risk", QualityRiskRetrainJob, QualityRiskRetrainJob.schedule_cron),
        ("otd_risk", OTDRiskRetrainJob, OTDRiskRetrainJob.schedule_cron),
        ("sequence_mining", SequenceMiningRetrainJob, SequenceMiningRetrainJob.schedule_cron),
        ("throughput_forecast", ThroughputForecastRetrainJob, ThroughputForecastRetrainJob.schedule_cron),
        ("drift_detection", DriftDetectionJob, DriftDetectionJob.schedule_cron),
    ]

    count = 0
    for tid in tenant_list:
        for name, _job_cls, cron in job_specs:
            if not cron:
                continue  # surrogate etc.
            scheduler.add_job(
                _run_retrain_job,
                trigger=CronTrigger.from_crontab(cron, timezone="UTC"),
                args=[name, str(tid)],
                id=f"ml_retrain:{name}:{tid}",
                name=f"ml_retrain_{name}[{tid}]",
                replace_existing=True,
                coalesce=True,
                max_instances=1,
            )
            count += 1

    logger.info(
        f"Registered {count} ML retrain jobs across {len(tenant_list)} tenant(s)"
    )
    return count


async def _run_retrain_job(job_name: str, tenant_id_str: str) -> None:
    """
    Dispatcher: lookup the job class by name, construct it with a semantic
    queries handle, and run it inside its own DB session.
    """
    from uuid import UUID
    tenant_id = UUID(tenant_id_str)

    try:
        from src.factory_data_product.services.semantic_queries_inmemory import (
            SemanticQueriesInMemory,
        )
        semantic = SemanticQueriesInMemory()
    except Exception as e:
        logger.warning(f"Semantic layer unavailable for retrain: {e}")
        semantic = None

    try:
        from src.governance.service import GovernanceService
        from src.ml.models_domain.duration import DurationRetrainJob
        from src.ml.models_domain.otd_risk import OTDRiskRetrainJob
        from src.ml.models_domain.quality_risk import QualityRiskRetrainJob
        from src.shared.database import get_session_context

        from src.ml.models_domain.sequence_mining import SequenceMiningRetrainJob
        from src.ml.models_domain.throughput_forecast import ThroughputForecastRetrainJob
        from src.ml.observability.drift import DriftDetectionJob

        job_cls_map = {
            "duration": DurationRetrainJob,
            "quality_risk": QualityRiskRetrainJob,
            "otd_risk": OTDRiskRetrainJob,
            "sequence_mining": SequenceMiningRetrainJob,
            "throughput_forecast": ThroughputForecastRetrainJob,
            "drift_detection": DriftDetectionJob,
        }
        job_cls = job_cls_map.get(job_name)
        if job_cls is None:
            logger.error(f"Unknown retrain job: {job_name}")
            return

        _no_semantic = {"sequence_mining", "throughput_forecast", "drift_detection"}

        async with get_session_context() as session:
            governance = GovernanceService(db=session, tenant_id=tenant_id)
            if job_name in _no_semantic:
                job = job_cls()
            else:
                job = job_cls(semantic_queries=semantic)
            summary = await job.run(
                session,
                tenant_id,
                governance_service=governance,
                proposed_by="scheduler",
            )
            await session.commit()
            logger.info(
                f"ML retrain {job_name} tenant={tenant_id}: "
                f"status={summary.get('status')} "
                f"samples={summary.get('training_samples')} "
                f"metrics={summary.get('metrics')}"
            )
    except Exception as e:
        logger.error(f"ML retrain {job_name} failed: {e}", exc_info=True)
