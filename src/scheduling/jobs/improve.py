"""Q.66.A.4 — jobs do loop de melhoria (adoption signal + ABL feedback).

Movidos de `src.shared.scheduler` sem alterações de comportamento.
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

logger = logging.getLogger(__name__)


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
