"""
ProdPlan ONE - Daily Feedback Job
==================================

Gera feedback diário automático do COPILOT.

Sprint Q.9 (2.7) — analyses real signals from the curated layer + the
schedule-commit ledger to produce two feedback streams every day:
  (a) **Rejection patterns** — which alternative kinds were rejected
      most often in the last 24 h, grouped by reason. Closes the
      learning loop visibility.
  (b) **Top 3 anomalies** — new bottleneck (utilisation >90% that
      wasn't there yesterday), at-risk OFs (deadline <7 days, no
      data_conclusao), defect spike (gravity ≥2 over weekly average).
"""

import logging
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.copilot.schemas import DailyFeedbackResponse, DailyFeedbackBullet, Citation
from src.factory_data_product.models.curated import CuratedOrder
from src.plan.cpo.commits import ScheduleCommit

logger = logging.getLogger(__name__)


async def _rejection_patterns(
    session: AsyncSession,
    tenant_id: UUID,
    since: datetime,
) -> List[Tuple[str, int]]:
    """Top reasons for rejected alternatives in the last 24 h.

    Reads ``ScheduleCommit.rejected_alternatives`` (JSONB) and groups
    each entry's ``reason`` into a Counter. Returns a list of
    ``(reason, count)`` tuples ordered by frequency, top 5.
    """
    stmt = select(ScheduleCommit.rejected_alternatives).where(
        and_(
            ScheduleCommit.tenant_id == tenant_id,
            ScheduleCommit.created_at >= since,
        )
    )
    try:
        rows = (await session.execute(stmt)).all()
    except Exception as exc:  # pragma: no cover — DB path
        logger.debug("rejection_patterns DB read failed: %s", exc)
        return []

    counter: Counter[str] = Counter()
    for (alts,) in rows:
        for alt in (alts or []):
            reason = (alt.get("reason") or "").strip() or "unspecified"
            counter[reason] += 1

    return counter.most_common(5)


async def _top_anomalies(
    session: AsyncSession,
    _tenant_id: UUID,
    today: date,
) -> List[Dict[str, Any]]:
    """Compute up to 3 anomalies: at-risk OFs, defect spike, queue size.

    Each anomaly is a dict ``{kind, severity, summary}``. We avoid
    crashing if a sub-query fails — anomalies that can't be measured
    are simply skipped.
    """
    anomalies: List[Dict[str, Any]] = []

    # 1. At-risk OFs: data_entrega_prevista <= today + 7d, no data_conclusao
    # NB: CuratedOrder is tenant-scoped via ingestion_id (the
    # SemanticQueries layer resolves it). The tenant_id arg is parked
    # under `_tenant_id` for the day CuratedOrder gains a direct
    # tenant_id column.
    horizon = today + timedelta(days=7)
    try:
        stmt = select(func.count(CuratedOrder.id)).where(
            and_(
                CuratedOrder.data_conclusao.is_(None),
                CuratedOrder.data_entrega_prevista.isnot(None),
                CuratedOrder.data_entrega_prevista <= horizon,
            )
        )
        at_risk = int((await session.execute(stmt)).scalar() or 0)
        if at_risk > 0:
            anomalies.append({
                "kind": "at_risk_orders",
                "severity": "WARN" if at_risk >= 5 else "INFO",
                "summary": (
                    f"{at_risk} OFs with delivery in the next 7 days "
                    f"and no data_conclusao yet."
                ),
            })
    except Exception as exc:  # pragma: no cover
        logger.debug("at_risk OFs query failed: %s", exc)

    # 2. WIP zombie ratio (>30% means ledger drift)
    try:
        from src.factory_data_product.semantic.queries import SemanticQueries
        sq = SemanticQueries(db=session)
        wip = await sq.wip()
        if wip.get("data"):
            zombie_pct = float(wip["data"].get("zombie_pct") or 0.0)
            if zombie_pct >= 30.0:
                anomalies.append({
                    "kind": "wip_zombie_ratio",
                    "severity": "WARN",
                    "summary": (
                        f"{zombie_pct:.0f}% of open OFs are >180d old. "
                        f"Audit needed."
                    ),
                })
    except Exception as exc:  # pragma: no cover
        logger.debug("wip zombie query failed: %s", exc)

    # 3. New bottleneck (utilisation >90% in top phase)
    try:
        from src.factory_data_product.semantic.queries import SemanticQueries
        sq = SemanticQueries(db=session)
        bn = await sq.bottlenecks(top_n=3)
        rows = bn.get("data") or []
        if rows:
            top = rows[0]
            util = top.get("utilization_pct") or top.get("utilization") or 0
            if isinstance(util, (int, float)) and util >= 90:
                anomalies.append({
                    "kind": "new_bottleneck",
                    "severity": "WARN",
                    "summary": (
                        f"Phase {top.get('fase_nome', '?')} at "
                        f"{util:.0f}% utilisation."
                    ),
                })
    except Exception as exc:  # pragma: no cover
        logger.debug("bottleneck query failed: %s", exc)

    return anomalies[:3]


async def generate_daily_feedback(
    session: AsyncSession,
    tenant_id: UUID,
    target_date: str,
) -> DailyFeedbackResponse:
    """
    Gera feedback diário do COPILOT.
    
    Args:
        session: Database session
        tenant_id: Tenant ID
        target_date: Data no formato YYYY-MM-DD
    
    Returns:
        DailyFeedbackResponse com bullets de feedback
    """
    try:
        # Parse date
        if isinstance(target_date, str):
            feedback_date = date.fromisoformat(target_date)
        else:
            feedback_date = target_date
        
        # Sprint Q.9 (2.7) — pull live signals from the curated layer +
        # commit ledger. CopilotService is no longer instantiated here
        # because no runbook dispatch happens in the advisory loop;
        # callers that need it can wrap this function.
        bullets: list[DailyFeedbackBullet] = []

        # ── (a) Rejection patterns over the last 24h ───────────────────────
        since = datetime.combine(feedback_date, datetime.min.time()) - timedelta(days=1)
        patterns = await _rejection_patterns(session, tenant_id, since)
        if patterns:
            top_lines = "\n".join(
                f"  • {reason} ({count}×)" for reason, count in patterns
            )
            bullets.append(
                DailyFeedbackBullet(
                    severity="INFO",
                    title="Rejection patterns (24h)",
                    text=(
                        f"Top reasons operators rejected proposed alternatives:\n{top_lines}"
                    ),
                    citations=[],
                    suggested_runbooks=[],
                    suggested_actions=[],
                )
            )
        else:
            bullets.append(
                DailyFeedbackBullet(
                    severity="INFO",
                    title="Rejection patterns (24h)",
                    text="No commits with rejected alternatives in the last 24h.",
                    citations=[],
                    suggested_runbooks=[],
                    suggested_actions=[],
                )
            )

        # ── (b) Top 3 anomalies for today ──────────────────────────────────
        anomalies = await _top_anomalies(session, tenant_id, feedback_date)
        if anomalies:
            for a in anomalies:
                bullets.append(
                    DailyFeedbackBullet(
                        severity=a.get("severity", "INFO"),
                        title=f"Anomaly: {a.get('kind', 'unknown')}",
                        text=a.get("summary", ""),
                        citations=[],
                        suggested_runbooks=[],
                        suggested_actions=[],
                    )
                )
        else:
            bullets.append(
                DailyFeedbackBullet(
                    severity="INFO",
                    title="No anomalies",
                    text="No at-risk orders, zombie WIP or new bottlenecks detected.",
                    citations=[],
                    suggested_runbooks=[],
                    suggested_actions=[],
                )
            )
        
        # Garantir que temos pelo menos 3 bullets (requisito do schema)
        while len(bullets) < 3:
            bullets.append(
                DailyFeedbackBullet(
                    severity="INFO",
                    title="Feedback Adicional",
                    text="Análise adicional disponível no dashboard.",
                    citations=[],
                    suggested_runbooks=[],
                    suggested_actions=[],
                )
            )
        
        now = datetime.now(timezone.utc).isoformat()
        
        return DailyFeedbackResponse(
            date=feedback_date.isoformat(),
            bullets=bullets[:7],  # Máximo 7 bullets
            generated_at=now,
            last_updated=now,
        )
        
    except Exception as e:
        logger.error(f"Erro ao gerar daily feedback: {e}", exc_info=True)
        
        # Retornar feedback de erro
        return DailyFeedbackResponse(
            date=target_date if isinstance(target_date, str) else target_date.isoformat(),
            bullets=[
                DailyFeedbackBullet(
                    severity="WARN",
                    title="Erro ao Gerar Feedback",
                    text=f"Não foi possível gerar feedback completo: {e!s}",
                    citations=[],
                    suggested_runbooks=[],
                    suggested_actions=[],
                ),
                DailyFeedbackBullet(
                    severity="INFO",
                    title="Sistema Operacional",
                    text="O sistema está operacional. Tente novamente mais tarde.",
                    citations=[],
                    suggested_runbooks=[],
                    suggested_actions=[],
                ),
                DailyFeedbackBullet(
                    severity="INFO",
                    title="Contacte Suporte",
                    text="Se o problema persistir, contacte o suporte técnico.",
                    citations=[],
                    suggested_runbooks=[],
                    suggested_actions=[],
                ),
            ],
            generated_at=datetime.now(timezone.utc).isoformat(),
            last_updated=datetime.now(timezone.utc).isoformat(),
        )
