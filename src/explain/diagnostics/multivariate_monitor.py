"""
ProdPlan ONE — MultivariatePhaseMonitor (Sprint Q.15.D.2)
==========================================================

Coordinator that runs over every active phase and detects which ones
*drift simultaneously* in a window. When ≥ 2 phases drift at the same
time, the result is fed into :class:`ReichenbachDetector` to find the
shared cause — instead of diagnosing each phase isolated.

Reuses the existing 1D KS test in
:mod:`src.dqa.distribution_drift_detector` rather than inventing a new
drift method. The "multivariate" piece is the *coordination*: a phase
loop + the join logic when multiple drift.

Design notes
------------

  * **Threshold-based recent vs. historical** — the 1D `DriftDetector`
    needs `recent_data + historical_data` lists. We compose those from
    the curated layer per-phase: recent error rates as a small list of
    daily aggregates vs. a longer historical baseline.
  * **Cheap baseline** — when the curated layer is empty / unreachable,
    `check()` returns `[]` rather than raising. The Reichenbach
    fallback path (per-phase ERRO-TREE) handles that gracefully.
  * **Cadence** — designed to be called every 30 min from the
    APScheduler in :mod:`src.shared.scheduler`. Best-effort: if a
    given run produces no drifters, no event is emitted (silence).
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from src.dqa.distribution_drift_detector import DriftDetector
from src.explain.diagnostics.repository import DiagnosticsRepository
from src.shared.time import local_today

logger = logging.getLogger(__name__)


# Default minimum window of error-rate samples. Below this, the drift
# detector reports "insufficient data" rather than a false positive.
_MIN_DAILY_SAMPLES = 7
_DEFAULT_RECENT_DAYS = 7
_DEFAULT_HISTORICAL_DAYS = 90


class MultivariatePhaseMonitor:
    """Runs the 1D drift detector across all active phases + reports
    those that drift simultaneously.

    Args:
        session: AsyncSession for the diagnostics repository.
        tenant_id: tenant scope.
        p_value_threshold: KS p-value below which we call drift
            (default 0.05 — same as `DriftDetector`).
    """

    def __init__(
        self,
        session: Any,
        tenant_id: UUID,
        *,
        p_value_threshold: float = 0.05,
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self._repo = DiagnosticsRepository(session, tenant_id)
        self._drift = DriftDetector(p_value_threshold=p_value_threshold)

    async def check(
        self,
        *,
        phase_ids: Optional[List[str]] = None,
        recent_days: int = _DEFAULT_RECENT_DAYS,
        historical_days: int = _DEFAULT_HISTORICAL_DAYS,
    ) -> List[str]:
        """Return the list of phase_ids that drift in the recent window.

        Empty list when nothing drifts (the common, healthy case) OR
        when the curated layer is unreachable. The Reichenbach
        orchestrator only fires when len(returned) >= 2.

        Args:
            phase_ids: optional explicit list. When omitted, the
                monitor iterates every phase that had at least one
                CuratedOrderPhase row in the recent window — keeps the
                scan tight on busy fleets.
            recent_days: window for "now" samples.
            historical_days: window for the baseline.
        """
        end = local_today()
        recent_start = end - timedelta(days=recent_days)
        historical_start = end - timedelta(days=historical_days)

        if phase_ids is None:
            phase_ids = await self._discover_active_phases(recent_start, end)
        if not phase_ids:
            return []

        drifting: List[str] = []
        for phase_id in phase_ids:
            recent_samples = await self._daily_error_rates(
                phase_id, recent_start, end,
            )
            historical_samples = await self._daily_error_rates(
                phase_id, historical_start, recent_start,
            )
            if (
                len(recent_samples) < _MIN_DAILY_SAMPLES
                or len(historical_samples) < _MIN_DAILY_SAMPLES
            ):
                continue
            verdict = self._drift.detect_drift(
                recent_data=recent_samples,
                historical_data=historical_samples,
                field_name="error_rate",
            )
            if verdict.get("drifted"):
                drifting.append(phase_id)

        if len(drifting) >= 2:
            logger.info(
                "MultivariatePhaseMonitor: %d phases drift together: %s",
                len(drifting), ", ".join(drifting),
            )
        return drifting

    async def _discover_active_phases(
        self, start: date, end: date,
    ) -> List[str]:
        """Distinct phase_ids that had any CuratedOrderPhase row in
        the recent window.

        Uses a defensive direct query rather than a repository helper —
        keeps the monitor self-sufficient when the repository's
        active-phase helper isn't there yet.
        """
        try:
            from sqlalchemy import select
            from src.factory_data_product.models.curated import CuratedOrderPhase
            stmt = (
                select(CuratedOrderPhase.fase_id)
                .where(CuratedOrderPhase.fase_id.isnot(None))
                .where(CuratedOrderPhase.data_inicio.isnot(None))
                .where(CuratedOrderPhase.data_inicio >= start)
                .where(CuratedOrderPhase.data_inicio < end)
                .distinct()
            )
            rows = (await self.session.execute(stmt)).all()
            return [str(r[0]) for r in rows if r[0]]
        except Exception as exc:
            logger.debug("_discover_active_phases failed (%s)", exc)
            return []

    async def _daily_error_rates(
        self, phase_id: str, start: date, end: date,
    ) -> List[Dict[str, float]]:
        """Daily aggregated error-rate samples for a phase.

        Returns a list of ``{"error_rate": float}`` dicts — the shape
        the existing `DriftDetector.detect_drift` expects. One entry
        per day in [start, end). Days with no phase activity are
        skipped (not zero-padded — the KS test handles unequal sample
        sizes natively and zero-padding would smear the distribution).
        """
        samples: List[Dict[str, float]] = []
        cursor = start
        one_day = timedelta(days=1)
        while cursor < end:
            next_day = cursor + one_day
            total = await self._repo.phase_total_count(phase_id, cursor, next_day)
            if total == 0:
                cursor = next_day
                continue
            errors = await self._repo.phase_error_count(
                phase_id, cursor, next_day,
            )
            samples.append({"error_rate": errors / total})
            cursor = next_day
        return samples


__all__ = ["MultivariatePhaseMonitor"]
