"""Q.66.A.4 — job de causal discovery (PCMCI+).

Movido de `src.shared.scheduler` sem alterações de comportamento.
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from src.scheduling.scheduler_lock import with_advisory_lock

logger = logging.getLogger(__name__)


@with_advisory_lock("causal_discovery")
async def _causal_discovery_job(tenant_id: UUID) -> None:
    """Sprint Q.13.D D.2 — weekly PCMCI+ causal-discovery run.

    Q.61.35 — protegido por advisory lock. PCMCI+ corre 15-45min;
    em multi-node so 1 processo por janela.

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
