"""Q.66.A.4 — núcleo do scheduler (singleton + arranque/registo/shutdown).

Movido de `src.shared.scheduler` sem alterações de comportamento. O
singleton `_scheduler` vive aqui (única instância do processo). O shim
`src/shared/scheduler.py` proxy-a leituras/escritas de `_scheduler` para
este módulo, por isso os tests Q.25.D / Q.54.A que fazem
``scheduler._scheduler = None`` continuam a actuar sobre o estado real.
"""

from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    APSCHEDULER_AVAILABLE = True
except ImportError:  # pragma: no cover
    APSCHEDULER_AVAILABLE = False

# Q.144.B — jitter (s) para escalonar os 6 jobs de sync ERP de 5 min, que de
# outro modo disparavam todos no mesmo instante (rajada que pressiona o
# event-loop/pool e podia estagnar pedidos do frontend). Cada corrida espalha-se
# por 0..jitter s, partindo o "thundering herd" sem perder a cadência de 5 min.
_ERP_SYNC_JITTER_S = 25

from src.scheduling.jobs.alerts import _alerts_scan_job
from src.scheduling.jobs.audit import _audit_retention_purge_job
from src.scheduling.jobs.causal import _causal_discovery_job
from src.scheduling.jobs.copilot import _copilot_schema_reindex_job
from src.scheduling.jobs.feedback import _daily_feedback_job
from src.scheduling.jobs.kpi_snapshot import _kpi_snapshot_job
from src.scheduling.jobs.improve import (
    _abl_feedback_job,
    _improve_adoption_signal_job,
)
from src.scheduling.jobs.ml import (
    _mold_health_scan_job,
    _multivariate_drift_job,
    _quality_risk_scoring_job,
)
from src.scheduling.jobs.nelo_erp import (
    _nelo_erp_comercial_job,
    _nelo_erp_customers_job,
    _nelo_erp_incremental_sync_job,
    _nelo_erp_logistica_job,
    _nelo_erp_phase_history_incremental_job,
    _nelo_erp_production_orders_job,
    _nelo_erp_raw_full_nightly_job,
    _nelo_erp_raw_incremental_job,
    _nelo_erp_sync_job,
    _nelo_erp_time_mining_job,
)
from src.scheduling.jobs.order_reconciliation import _order_status_reconcile_job
from src.scheduling.jobs.preference_learning import (
    _dpo_finetune_job,
    _preference_rule_detector_job,
    _preference_weights_retrain_job,
)
from src.scheduling.jobs.boat_phase_score_job import _boat_phase_score_job
from src.scheduling.jobs.boat_potential_job import _boat_potential_job
from src.scheduling.jobs.boat_complexity_job import _boat_complexity_job
from src.scheduling.jobs.phase_operator_affinity import _phase_operator_affinity_job
from src.scheduling.jobs.auto_cpo_replan_job import _auto_cpo_replan_global_job
from src.scheduling.jobs.auto_propose_signals_job import _auto_propose_signals_job
from src.scheduling.jobs.capture_plan_execution import (
    _capture_plan_execution_global_job,
)
from src.scheduling.jobs.phase_calibration_job import _phase_calibration_global_job
from src.scheduling.jobs.plan_vs_actual import _plan_vs_actual_global_job
from src.scheduling.jobs.runbook_learning import _runbook_learning_job
from src.scheduling.jobs.supply import _shortage_scan_job

logger = logging.getLogger(__name__)


# Module-level singleton so jobs can be inspected / tested.
# IMPORTANT: This is the ONE source of truth. The shim
# `src/shared/scheduler.py` proxies attribute access to here.
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

    # Q.25.D — sync ERP->Postgres. Mirrors leves (master/molds/skills/
    # quality) todas as noites as 02:00 UTC, antes dos jobs que consomem
    # os dados. O `time_mining` pesado (3 anos de OF_FP) semanal, Domingo
    # 01:00 UTC. Registados sempre; fazem no-op quando sqlserver_enabled
    # =False, por isso ligar o flag nao exige reiniciar o scheduler.
    _scheduler.add_job(
        _nelo_erp_sync_job,
        trigger=CronTrigger(hour=2, minute=0, timezone="UTC"),
        id="nelo_erp_sync",
        name="nelo_erp_sync",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    _scheduler.add_job(
        _nelo_erp_time_mining_job,
        trigger=CronTrigger(day_of_week=6, hour=1, minute=0, timezone="UTC"),
        id="nelo_erp_time_mining",
        name="nelo_erp_time_mining",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    # Q.54.A — sync incremental operacional de 5/5 min (stock/calendar/
    # quality). Watermark por mirror lido de core.etl_run. coalesce=True
    # + max_instances=1 garantem que um sync lento não acumula corridas.
    # No-op quando sqlserver_enabled=False.
    _scheduler.add_job(
        _nelo_erp_incremental_sync_job,
        trigger=IntervalTrigger(minutes=5, jitter=_ERP_SYNC_JITTER_S),
        id="nelo_erp_incremental_sync",
        name="nelo_erp_incremental_sync",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    # Q.115.T — sync incremental phase_history + worker_assignment (15 min).
    # Alta cardinalidade — job separado para nao bloquear stock/calendar.
    # No-op quando sqlserver_enabled=False.
    _scheduler.add_job(
        _nelo_erp_phase_history_incremental_job,
        trigger=IntervalTrigger(minutes=15),
        id="nelo_erp_phase_history_incremental",
        name="nelo_erp_phase_history_incremental",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    # Q.125 — sync de 5/5 min dos dados PESADOS do ERP que alimentam o
    # dashboard/copiloto (factory_raw + faturação PHC + logística). O sync
    # incremental Q.54.A só cobria os mirrors ORM operacionais; estes três
    # estavam em scripts manuais e ficavam stale. Tudo DROP-free (upsert/
    # TRUNCATE) → seguro com as marts (VIEWs live sobre factory_raw).
    # coalesce + max_instances=1 evitam acumular. No-op se sqlserver_enabled=False.
    _scheduler.add_job(
        _nelo_erp_raw_incremental_job,
        trigger=IntervalTrigger(minutes=5, jitter=_ERP_SYNC_JITTER_S),
        id="nelo_erp_raw_incremental",
        name="nelo_erp_raw_incremental",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    # Q.157.0 — full-copy nocturno das tabelas factory_raw de baixa velocidade
    # (produto/fases_producao/moldes/entidade/produto_fase/produto_componente/
    # offp_eq/apontamento_trabalho). O incremental de 5 min salta-as; sem este
    # job ficavam dias stale (audit 2026-06-02: offp_eq/produto a 3 dias). 02:30
    # UTC = depois do mirror curado (02:00), antes da calibração (06:40).
    _scheduler.add_job(
        _nelo_erp_raw_full_nightly_job,
        trigger=CronTrigger(hour=2, minute=30, timezone="UTC"),
        id="nelo_erp_raw_full_nightly",
        name="nelo_erp_raw_full_nightly",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    _scheduler.add_job(
        _nelo_erp_comercial_job,
        trigger=IntervalTrigger(minutes=5, jitter=_ERP_SYNC_JITTER_S),
        id="nelo_erp_comercial",
        name="nelo_erp_comercial",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    _scheduler.add_job(
        _nelo_erp_logistica_job,
        trigger=IntervalTrigger(minutes=5, jitter=_ERP_SYNC_JITTER_S),
        id="nelo_erp_logistica",
        name="nelo_erp_logistica",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    # Q.125 — core.customers a partir de factory_raw.entidade (tipo Cliente).
    # O mirror `master` nunca espelhava clientes. 5/5 min, DROP-free (upsert).
    _scheduler.add_job(
        _nelo_erp_customers_job,
        trigger=IntervalTrigger(minutes=5, jitter=_ERP_SYNC_JITTER_S),
        id="nelo_erp_customers",
        name="nelo_erp_customers",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    # Q.131.C — plan.production_orders a partir de factory_raw.ordemfabrico
    # (WIP real, keyed por OF_P_ID). A lista de ordens deixa de ser 12 demo.
    # Postgres-interno (lê o factory_raw já espelhado), corre sempre; no-op
    # se o WIP estiver vazio. 5/5 min, upsert idempotente.
    _scheduler.add_job(
        _nelo_erp_production_orders_job,
        trigger=IntervalTrigger(minutes=5, jitter=_ERP_SYNC_JITTER_S),
        id="nelo_erp_production_orders",
        name="nelo_erp_production_orders",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    # Q.115.V — plan-vs-actual diário: compara planos CPO com execução real.
    # 06:30 UTC (depois do drift detection 06:00). Itera todos os tenants
    # registados. Best-effort: falha de um tenant não bloqueia os restantes.
    _scheduler.add_job(
        _plan_vs_actual_global_job,
        trigger=CronTrigger(hour=6, minute=30, timezone="UTC"),
        args=[tenants or []],
        id="plan_vs_actual",
        name="plan_vs_actual",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    # Q.134.A3a — captura PLANEADO vs REALIZADO por (of, fase) dos commits LIVE
    # → plan.plan_execution_observed (deviation_pct). 06:35 UTC: depois do
    # plan_vs_actual (06:30), ANTES da calibração (06:40) — para que a
    # calibração (Q.134.A3b) leia o desvio fresco.
    _scheduler.add_job(
        _capture_plan_execution_global_job,
        trigger=CronTrigger(hour=6, minute=35, timezone="UTC"),
        args=[tenants or []],
        id="capture_plan_execution",
        name="capture_plan_execution",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    # Q.133.A1 — calibração de durações p50/p95 por (modelo, fase) de of_fp →
    # plan.phase_duration_calibration. 06:40 UTC (depois do plan_vs_actual).
    # O FactoryState (Q.133.A2) lê esta tabela e prefere o p50 calibrado.
    _scheduler.add_job(
        _phase_calibration_global_job,
        trigger=CronTrigger(hour=6, minute=40, timezone="UTC"),
        args=[tenants or []],
        id="phase_calibration",
        name="phase_calibration",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    # Q.54.B — reconciliação do estado das ordens com a fase actual.
    # Postgres-interna, corre sempre (independente de sqlserver_enabled).
    _scheduler.add_job(
        _order_status_reconcile_job,
        trigger=IntervalTrigger(minutes=15),
        id="order_status_reconcile",
        name="order_status_reconcile",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    # Q.137 — replan CPO automático: a cada 15 min, se o WIP de barcos mudou
    # (reativo ao sync ERP de 5 min), enfileira o cpo_schedule_job no Arq → o
    # worker corre o CPO e persiste um DRAFT → o grid /overall mostra-o sozinho.
    # Rate-limit (60 min) + deteção de mudança evitam planos repetidos. DRAFT-only
    # (Q.17). Best-effort: Redis/worker em baixo → log + skip.
    _scheduler.add_job(
        _auto_cpo_replan_global_job,
        trigger=IntervalTrigger(minutes=15),
        args=[tenants or []],
        id="auto_cpo_replan",
        name="auto_cpo_replan",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    # Q.157.A/F/G — auto-propose REAL: gera decisões PROPOSED de sinais do plano
    # vivo (planeamento CPO ADOPT_PLAN + expedição + OTD) → enchem a landing
    # /decisoes. In-process, sem Kafka/dev-gate. Q.17: nascem PROPOSED (nunca
    # auto-LIVE). Supersede mantém ≤1 ADOPT_PLAN aberto; bloqueia re-propor
    # rejeitados. Q.157.G.3: 5 min (job leve) alinha com o sync ERP → menos
    # latência mudança→ADOPT_PLAN.
    _scheduler.add_job(
        _auto_propose_signals_job,
        trigger=IntervalTrigger(minutes=5, jitter=_ERP_SYNC_JITTER_S),
        args=[tenants or []],
        id="auto_propose_signals",
        name="auto_propose_signals",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    # Q.117.D — snapshot diário de KPIs para o gráfico de tendência da
    # página LLM › KPIs. 00:45 UTC (depois do daily_feedback 00:30). Itera
    # tenants; em dev a lista vem vazia e o job descobre-os na BD.
    _scheduler.add_job(
        _kpi_snapshot_job,
        trigger=CronTrigger(hour=0, minute=45, timezone="UTC"),
        args=[tenants or []],
        id="kpi_snapshot",
        name="kpi_snapshot",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )

    # Q.67.4.E — reindex nocturno dos schema docs no RAG do copilot.
    # 04:00 UTC (low traffic). No-op se copilot_enabled=False.
    _scheduler.add_job(
        _copilot_schema_reindex_job,
        trigger=CronTrigger(hour=4, minute=0, timezone="UTC"),
        id="copilot_schema_reindex",
        name="copilot_schema_reindex",
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
    # Sprint Q.15.D.3 — multivariate phase drift monitor (every 30 min).
    # When >= 2 phases drift simultaneously, fires the Reichenbach
    # common-cause detector and writes a row to governance.rule_firing
    # via the @record_rule_firing decorator on `find_common_cause`.
    # Gated by ConfigStore key `copilot.diagnostics.reichenbach.enabled`
    # — the job runs the check unconditionally but only invokes the
    # detector when the flag is True. Cheap enough to leave on always.
    _scheduler.add_job(
        _multivariate_drift_job,
        trigger=IntervalTrigger(minutes=30),
        args=[tenant_id],
        id=f"multivariate_drift:{tenant_id}",
        name=f"multivariate_drift[{tenant_id}]",
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
    # Q.115.G — phase_operator_affinity: afinidade operador/fase.
    # 03:30 UTC, após o preference_rule_detector (03:00). Recomputa
    # scores a partir dos últimos 90d de fases_of_history. Idempotente.
    _scheduler.add_job(
        _phase_operator_affinity_job,
        trigger=CronTrigger(hour=3, minute=30, timezone="UTC"),
        args=[tenant_id],
        id=f"phase_operator_affinity:{tenant_id}",
        name=f"phase_operator_affinity[{tenant_id}]",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    # Q.115.X6.A — boat_phase_score: afinidade barco/fase.
    # 03:45 UTC, após o phase_operator_affinity (03:30). Idempotente.
    _scheduler.add_job(
        _boat_phase_score_job,
        trigger=CronTrigger(hour=3, minute=45, timezone="UTC"),
        args=[tenant_id],
        id=f"boat_phase_score:{tenant_id}",
        name=f"boat_phase_score[{tenant_id}]",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    # Q.115.X6.B — boat_potential: potencialidade por barco.
    # 04:20 UTC (improve_adoption_signal às 04:15, audit_purge às 04:30).
    _scheduler.add_job(
        _boat_potential_job,
        trigger=CronTrigger(hour=4, minute=20, timezone="UTC"),
        args=[tenant_id],
        id=f"boat_potential:{tenant_id}",
        name=f"boat_potential[{tenant_id}]",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    # Q.155.A — boat_complexity (ICB): peças + tinta + fases por barco.
    # 04:25 UTC, logo após o boat_potential. Idempotente. Alimenta o matching
    # "barco difícil ↔ melhores operadores" no CPO.
    _scheduler.add_job(
        _boat_complexity_job,
        trigger=CronTrigger(hour=4, minute=25, timezone="UTC"),
        args=[tenant_id],
        id=f"boat_complexity:{tenant_id}",
        name=f"boat_complexity[{tenant_id}]",
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
    # Q.115.H — aprendizagem diária de runbooks (04:00 UTC).
    # Lê top-20 error_codes mais frequentes nos últimos 30d e tenta
    # construir runbooks a partir de padrões observados. Runbooks ficam
    # em approved_by=NULL até aprovação humana — nunca actuam sozinhos.
    _scheduler.add_job(
        _runbook_learning_job,
        trigger=CronTrigger(hour=4, minute=0, timezone="UTC"),
        args=[tenant_id],
        id=f"runbook_learning:{tenant_id}",
        name=f"runbook_learning[{tenant_id}]",
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
