"""Q.66.A.4 — jobs ML (mold health, quality risk, multivariate drift).

Movidos de `src.shared.scheduler` sem alterações de comportamento.
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID
from src.shared.time import utc_now_naive

logger = logging.getLogger(__name__)


async def _mold_health_scan_job(tenant_id: UUID) -> None:
    """Recompute mold health daily + emit AL08 alerts (Sprint R.6.2/R.6.3)."""
    from src.plan.services.mold_service import MoldService
    from src.shared.database import get_session_context

    started = utc_now_naive()
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
        elapsed_ms = int((utc_now_naive() - started).total_seconds() * 1000)
        logger.info(
            "mold_health_scan tenant=%s scored=%s alerts=%s elapsed_ms=%s",
            tenant_id, scored, alerts, elapsed_ms,
        )
    except Exception as exc:
        logger.error("mold_health_scan tenant=%s failed: %s", tenant_id, exc, exc_info=True)


async def _quality_risk_scoring_job(tenant_id: UUID) -> None:
    """Q.117.G — pontua o risco de defeito das ordens em curso.

    Deixa de ser stub: corre o ``DefectRiskService`` (Q.53.A/Q.115.E) sobre
    as ordens ``in-progress``, o que (a) treina+promove o modelo
    ``quality_risk`` na primeira utilização e (b) regista quantas ordens
    estão em risco alto. O mesmo serviço alimenta o badge on-demand nas
    vistas Overall e o ``quality_risk`` das decisões (Q.117.B).

    Best-effort: degrada com ``model_available=false`` quando o histórico é
    insuficiente; nunca levanta para dentro do scheduler.
    """
    from src.quality.services.defect_risk_service import DefectRiskService
    from src.shared.database import get_session_context

    started = utc_now_naive()
    try:
        async with get_session_context() as session:
            svc = DefectRiskService(session, tenant_id)
            result = await svc.defect_risk(top_n=50)
            await session.commit()
        elapsed_ms = int((utc_now_naive() - started).total_seconds() * 1000)
        logger.info(
            "quality_risk_scoring tenant=%s model_available=%s total=%s "
            "high_risk=%s elapsed_ms=%s",
            tenant_id,
            result.get("model_available"),
            result.get("total_orders", 0),
            result.get("high_risk_count", 0),
            elapsed_ms,
        )
    except Exception as exc:
        logger.error(
            "quality_risk_scoring tenant=%s failed: %s", tenant_id, exc, exc_info=True,
        )


async def _multivariate_drift_job(tenant_id: UUID) -> None:
    """Sprint Q.15.D.3 — every 30 min, check whether ≥ 2 phases drift
    simultaneously; if so, fire the Reichenbach common-cause detector.

    Gated by ConfigStore key ``copilot.diagnostics.reichenbach.enabled``
    (default False). The drift scan runs unconditionally — it's cheap
    and the result is interesting in its own right (logs which phases
    drift). Only the detector invocation is gated so we don't burn
    Beta-Bernoulli math + audit rows for tenants who haven't opted in.

    Best-effort: a failed run logs at warning + the next tick tries
    again. Never raises into the scheduler.
    """
    try:
        from src.core.services.tenant_config_service import TenantConfigService
        from src.explain.diagnostics.multivariate_monitor import (
            MultivariatePhaseMonitor,
        )
        from src.explain.diagnostics.reichenbach import ReichenbachDetector
        from src.shared.database import get_session_context
    except ImportError as exc:
        logger.debug(
            "multivariate_drift: imports missing (%s) — skipping tenant=%s",
            exc, tenant_id,
        )
        return

    started = utc_now_naive()
    try:
        async with get_session_context() as session:
            cfg_svc = TenantConfigService(session, tenant_id)
            enabled = await cfg_svc.get(
                "copilot",
                "diagnostics.reichenbach.enabled",
                default=False,
            )

            monitor = MultivariatePhaseMonitor(
                session=session, tenant_id=tenant_id,
            )
            drifting = await monitor.check()

            if not drifting:
                # Common, healthy case — log and exit. No detector run,
                # no audit row.
                elapsed_ms = int(
                    (utc_now_naive() - started).total_seconds() * 1000
                )
                logger.debug(
                    "multivariate_drift tenant=%s drifting=0 elapsed_ms=%d",
                    tenant_id, elapsed_ms,
                )
                return

            if len(drifting) < 2:
                # Single-phase drift goes through the alerts scan, not
                # Reichenbach. Log and exit.
                logger.info(
                    "multivariate_drift tenant=%s drifting=1 phase=%s "
                    "(single — alerts scan handles)",
                    tenant_id, drifting[0],
                )
                return

            if not enabled:
                logger.info(
                    "multivariate_drift tenant=%s drifting=%d phases=%s "
                    "(reichenbach disabled — flip "
                    "copilot.diagnostics.reichenbach.enabled to activate)",
                    tenant_id, len(drifting), drifting,
                )
                return

            detector = ReichenbachDetector(
                session=session, tenant_id=tenant_id,
            )
            result = await detector.find_common_cause(
                deviating_phases=drifting,
            )
            await session.commit()
            elapsed_ms = int(
                (utc_now_naive() - started).total_seconds() * 1000
            )
            logger.info(
                "multivariate_drift tenant=%s drifting=%d verdict=%s "
                "common_causes=%d elapsed_ms=%d",
                tenant_id, len(drifting), result.verdict,
                len(result.common_causes), elapsed_ms,
            )
    except Exception as exc:
        logger.warning(
            "multivariate_drift tenant=%s failed: %s",
            tenant_id, exc, exc_info=True,
        )
