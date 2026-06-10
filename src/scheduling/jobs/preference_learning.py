"""Q.66.A.4 — jobs de aprendizagem de preferências (Camadas 1-3).

Movidos de `src.shared.scheduler` sem alterações de comportamento.
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from src.scheduling.scheduler_lock import with_advisory_lock
from src.shared.time import utc_now_naive

logger = logging.getLogger(__name__)


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

    started = utc_now_naive()
    try:
        async with get_session_context() as session:
            detector = PreferenceRuleDetector(session, tenant_id)
            rules = await detector.scan(window_days=30)
            await session.commit()
        elapsed_ms = int((utc_now_naive() - started).total_seconds() * 1000)
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

    started = utc_now_naive()
    try:
        async with get_session_context() as session:
            retainer = AdaptiveFitnessWeights(session, tenant_id)
            result = await retainer.retrain(window_days=30)
            await session.commit()
        elapsed_ms = int((utc_now_naive() - started).total_seconds() * 1000)
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


@with_advisory_lock("dpo_finetune")
async def _dpo_finetune_job(tenant_id: UUID) -> None:
    """Sprint R.5.4 — weekly DPO fine-tune candidate (Camada 3).

    Q.61.35 — protegido por pg_try_advisory_lock("dpo_finetune"). Em
    multi-worker, so 1 processo corre o DPO por janela (GPU + 30min
    de compute caro). Outros skip com log "job_skipped lock_held".

    Runs Sunday 03:00 UTC. Reads ConfigStore key
    ``learning.fine_tune.enabled`` and bails if it's false (default).
    The job NEVER promotes — it just builds a dataset, runs
    ``run_finetune`` in smoke mode (or real, if the GPU stack is
    present), and writes the report next to a versioned adapter
    directory. The R.1 dashboard surfaces "candidate pending" and a
    human carries out the promote via the API.
    """
    # NOTE: original god-file importava `from datetime import timedelta`
    # aqui mas o body nunca o usa — import morto removido na decomposição.
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

            scripts_dir = _P(__file__).resolve().parents[3] / "scripts"
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

    started = utc_now_naive()
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
        elapsed_ms = int((utc_now_naive() - started).total_seconds() * 1000)
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
