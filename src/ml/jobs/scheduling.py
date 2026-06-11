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

    # Q.173.AQ — drift_detection REMOVIDO do agendamento: o DriftDetectionJob
    # era um scaffold 100% inoperante (nenhum feature snapshot persistido,
    # eventos sempre 0) e rebentava com TypeError (run() não aceitava os
    # kwargs do dispatcher). O DriftDetector 1D continua disponível em
    # src/ml/observability/drift.py para quando os snapshots existirem.
    job_specs = [
        ("duration", DurationRetrainJob, DurationRetrainJob.schedule_cron),
        ("quality_risk", QualityRiskRetrainJob, QualityRiskRetrainJob.schedule_cron),
        ("otd_risk", OTDRiskRetrainJob, OTDRiskRetrainJob.schedule_cron),
        ("sequence_mining", SequenceMiningRetrainJob, SequenceMiningRetrainJob.schedule_cron),
        ("throughput_forecast", ThroughputForecastRetrainJob, ThroughputForecastRetrainJob.schedule_cron),
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
    Dispatcher: run the retrain for one model inside its own DB session.

    Q.173.AQ — duration/quality_risk/otd_risk passaram a usar o caminho
    DB-backed do `training_service` (factory_raw/plan reais). O caminho
    antigo construía `SemanticQueriesInMemory()` (TypeError: exige engine),
    caía em `semantic=None`, e cada job lia a camada curated VAZIA →
    `EmptyDatasetError` em todas as corridas desde sempre (auditoria
    2026-06-11: otd_risk com 0 artefactos).

    Promoção: bootstrap-only — o re-treino agendado regista o artefacto
    novo (auditável no registry) mas só o promove quando ainda não há
    nenhum ativo. Substituir um modelo ativo continua a ser um gesto
    deliberado, não um efeito colateral do cron.
    """
    from uuid import UUID
    tenant_id = UUID(tenant_id_str)

    try:
        from src.shared.database import get_session_context

        async with get_session_context() as session:
            summary = await _dispatch_retrain(session, tenant_id, job_name)
            await session.commit()
            logger.info(
                f"ML retrain {job_name} tenant={tenant_id}: "
                f"status={summary.get('status')} "
                f"samples={summary.get('training_samples') or summary.get('metrics', {}).get('samples')} "
                f"metrics={summary.get('metrics')}"
            )
    except Exception as e:
        logger.error(f"ML retrain {job_name} failed: {e}", exc_info=True)


async def _dispatch_retrain(session, tenant_id: UUID, job_name: str) -> dict:
    """Route one job name to the right (DB-backed) training path."""
    _db_backed = {"duration", "quality_risk", "otd_risk"}

    if job_name in _db_backed:
        from src.ml.models.registry import ModelRegistry
        from src.ml.training_service import (
            TrainingError,
            train_duration,
            train_otd_risk,
            train_quality_risk,
        )

        registry = ModelRegistry(session, tenant_id)
        has_active = await registry.get_active(job_name) is not None
        train_fn = {
            "duration": train_duration,
            "quality_risk": train_quality_risk,
            "otd_risk": train_otd_risk,
        }[job_name]
        try:
            return await train_fn(
                session, tenant_id,
                trained_by="scheduler",
                promote=not has_active,  # bootstrap-only
            )
        except TrainingError as exc:
            return {"status": "skipped", "reason": str(exc)}

    if job_name == "sequence_mining":
        from src.ml.models_domain.sequence_mining import SequenceMiningRetrainJob
        return await SequenceMiningRetrainJob().run(session, tenant_id)
    if job_name == "throughput_forecast":
        from src.ml.models_domain.throughput_forecast import ThroughputForecastRetrainJob
        return await ThroughputForecastRetrainJob().run(session, tenant_id)

    logger.error(f"Unknown retrain job: {job_name}")
    return {"status": "error", "reason": f"unknown job {job_name}"}
