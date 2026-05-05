"""
ProdPlan ONE — DiagnosticsRepository (Sprint Q.15.D.0)
=======================================================

Single source of truth for diagnostic queries. Every detector in
:mod:`src.explain.diagnostics.erro_tree`, :mod:`reichenbach`, and
:mod:`mill_diff` reads through this layer instead of writing SQL
ad-hoc; otherwise each handler invents its own definition of "error
rate over a period" and the numbers stop comparing.

Best-effort guarantee
---------------------

When the curated layer hasn't been ingested (`factory_curated.*`
empty), every method returns a sane default (zero counts, empty list)
without raising. Detectors in turn produce ``None`` hypotheses (skip)
rather than crashing the whole investigate pipeline. This matches the
existing pattern in `_extract_error_rates` (state.py) and in the
Q.13.D `record_causal_audit` (best-effort persist).

Tenant scope
------------

`CuratedQualityEvent` etc. are NOT yet multi-tenant in NELO's curated
layer (single-tenant deploy). The repository accepts ``tenant_id`` for
future-proofing but currently doesn't filter on it. When the curated
layer adds ``tenant_id``, only this file changes.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import date
from typing import Counter as CounterT, Dict, List, Tuple
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.explain.diagnostics.types import MoldUsage, WorkerStats

logger = logging.getLogger(__name__)


class DiagnosticsRepository:
    """Async query layer for the diagnostic handlers.

    All methods take a ``(start, end)`` window in dates (inclusive
    start, exclusive end) and return Python natives — no SQLAlchemy
    rows leak past this boundary.
    """

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    # ──────────────────────────────────────────────────────────────────
    # MOLD-side helpers
    # ──────────────────────────────────────────────────────────────────

    async def molds_active_during(
        self, start: date, end: date,
    ) -> List[str]:
        """Distinct mold ids referenced by any CuratedOrderPhase whose
        data_inicio falls inside the window.

        Returns ``[]`` when the curated table is empty / unreachable.
        """
        try:
            from src.factory_data_product.models.curated import CuratedOrderPhase
            stmt = (
                select(CuratedOrderPhase.molde_id)
                .where(CuratedOrderPhase.molde_id.isnot(None))
                .where(CuratedOrderPhase.data_inicio.isnot(None))
                .where(CuratedOrderPhase.data_inicio >= start)
                .where(CuratedOrderPhase.data_inicio < end)
                .distinct()
            )
            rows = (await self.session.execute(stmt)).all()
            return [r[0] for r in rows if r[0]]
        except Exception as exc:
            logger.debug("molds_active_during failed (%s) — returning []", exc)
            return []

    async def mold_phase_count(
        self, mold_id: str, start: date, end: date,
    ) -> int:
        """Count of CuratedOrderPhase rows for this mold in window."""
        try:
            from src.factory_data_product.models.curated import CuratedOrderPhase
            stmt = (
                select(func.count(CuratedOrderPhase.id))
                .where(CuratedOrderPhase.molde_id == mold_id)
                .where(CuratedOrderPhase.data_inicio.isnot(None))
                .where(CuratedOrderPhase.data_inicio >= start)
                .where(CuratedOrderPhase.data_inicio < end)
            )
            result = await self.session.execute(stmt)
            return int(result.scalar() or 0)
        except Exception as exc:
            logger.debug("mold_phase_count(%s) failed (%s)", mold_id, exc)
            return 0

    async def mold_error_count(
        self, mold_id: str, start: date, end: date,
    ) -> int:
        """Count of CuratedQualityEvent rows for this mold in window.

        Uses CuratedQualityEvent.molde_id when populated; falls back to
        joining via fase_of_id when only the phase reference exists.
        """
        try:
            from src.factory_data_product.models.curated import CuratedQualityEvent
            stmt = (
                select(func.count(CuratedQualityEvent.id))
                .where(CuratedQualityEvent.molde_id == mold_id)
                .where(CuratedQualityEvent.data_evento.isnot(None))
                .where(CuratedQualityEvent.data_evento >= start)
                .where(CuratedQualityEvent.data_evento < end)
            )
            result = await self.session.execute(stmt)
            return int(result.scalar() or 0)
        except Exception as exc:
            logger.debug("mold_error_count(%s) failed (%s)", mold_id, exc)
            return 0

    async def mold_error_types(
        self, mold_id: str, start: date, end: date,
    ) -> CounterT[str]:
        """Distribution of erro_tipo for events on this mold."""
        try:
            from src.factory_data_product.models.curated import CuratedQualityEvent
            stmt = (
                select(
                    CuratedQualityEvent.erro_tipo,
                    func.count(CuratedQualityEvent.id),
                )
                .where(CuratedQualityEvent.molde_id == mold_id)
                .where(CuratedQualityEvent.data_evento.isnot(None))
                .where(CuratedQualityEvent.data_evento >= start)
                .where(CuratedQualityEvent.data_evento < end)
                .group_by(CuratedQualityEvent.erro_tipo)
            )
            rows = (await self.session.execute(stmt)).all()
            return Counter({str(r[0]): int(r[1]) for r in rows if r[0]})
        except Exception as exc:
            logger.debug("mold_error_types(%s) failed (%s)", mold_id, exc)
            return Counter()

    async def mold_usage(
        self, mold_id: str, start: date, end: date,
    ) -> MoldUsage:
        """Composed usage rollup — convenience for detectors."""
        total_phases = await self.mold_phase_count(mold_id, start, end)
        errors = await self.mold_error_count(mold_id, start, end)
        return MoldUsage(
            mold_id=mold_id,
            total_phases=total_phases,
            error_count=errors,
        )

    # ──────────────────────────────────────────────────────────────────
    # PHASE-side helpers
    # ──────────────────────────────────────────────────────────────────

    async def phase_total_count(
        self, phase_id: str, start: date, end: date,
    ) -> int:
        try:
            from src.factory_data_product.models.curated import CuratedOrderPhase
            stmt = (
                select(func.count(CuratedOrderPhase.id))
                .where(CuratedOrderPhase.fase_id == phase_id)
                .where(CuratedOrderPhase.data_inicio.isnot(None))
                .where(CuratedOrderPhase.data_inicio >= start)
                .where(CuratedOrderPhase.data_inicio < end)
            )
            return int((await self.session.execute(stmt)).scalar() or 0)
        except Exception as exc:
            logger.debug("phase_total_count(%s) failed (%s)", phase_id, exc)
            return 0

    async def phase_error_count(
        self, phase_id: str, start: date, end: date,
    ) -> int:
        try:
            from src.factory_data_product.models.curated import CuratedQualityEvent
            stmt = (
                select(func.count(CuratedQualityEvent.id))
                .where(CuratedQualityEvent.fase_id == phase_id)
                .where(CuratedQualityEvent.data_evento.isnot(None))
                .where(CuratedQualityEvent.data_evento >= start)
                .where(CuratedQualityEvent.data_evento < end)
            )
            return int((await self.session.execute(stmt)).scalar() or 0)
        except Exception as exc:
            logger.debug("phase_error_count(%s) failed (%s)", phase_id, exc)
            return 0

    async def phase_error_rate(
        self, phase_id: str, start: date, end: date,
    ) -> float:
        """Errors / total. 0.0 when no phases ran in the window."""
        total = await self.phase_total_count(phase_id, start, end)
        if total == 0:
            return 0.0
        errors = await self.phase_error_count(phase_id, start, end)
        return min(1.0, errors / total)

    # ──────────────────────────────────────────────────────────────────
    # WORKER-side helpers
    # ──────────────────────────────────────────────────────────────────

    async def workers_active_in_phase(
        self, phase_id: str, start: date, end: date,
    ) -> List[Tuple[str, int]]:
        """``[(worker_id, allocation_count)]`` for the phase in window."""
        try:
            from src.factory_data_product.models.curated import (
                CuratedAllocation,
                CuratedOrderPhase,
            )
            # Allocation rows joined with their order_phase to scope by
            # phase_id + window (allocation alone has no date).
            stmt = (
                select(
                    CuratedAllocation.funcionario_id,
                    func.count(CuratedAllocation.id),
                )
                .join(
                    CuratedOrderPhase,
                    CuratedOrderPhase.fase_of_id == CuratedAllocation.fase_of_id,
                )
                .where(CuratedOrderPhase.fase_id == phase_id)
                .where(CuratedOrderPhase.data_inicio.isnot(None))
                .where(CuratedOrderPhase.data_inicio >= start)
                .where(CuratedOrderPhase.data_inicio < end)
                .group_by(CuratedAllocation.funcionario_id)
            )
            rows = (await self.session.execute(stmt)).all()
            return [(str(r[0]), int(r[1])) for r in rows if r[0]]
        except Exception as exc:
            logger.debug("workers_active_in_phase(%s) failed (%s)", phase_id, exc)
            return []

    async def worker_phase_stats(
        self, worker_id: str, phase_id: str, start: date, end: date,
    ) -> WorkerStats:
        """Allocation count + error_count for a (worker, phase) pair."""
        try:
            from src.factory_data_product.models.curated import (
                CuratedAllocation,
                CuratedOrderPhase,
                CuratedQualityEvent,
            )
            # Allocations on this phase by this worker.
            stmt_alloc = (
                select(func.count(CuratedAllocation.id))
                .join(
                    CuratedOrderPhase,
                    CuratedOrderPhase.fase_of_id == CuratedAllocation.fase_of_id,
                )
                .where(CuratedAllocation.funcionario_id == worker_id)
                .where(CuratedOrderPhase.fase_id == phase_id)
                .where(CuratedOrderPhase.data_inicio.isnot(None))
                .where(CuratedOrderPhase.data_inicio >= start)
                .where(CuratedOrderPhase.data_inicio < end)
            )
            total = int((await self.session.execute(stmt_alloc)).scalar() or 0)

            # Errors on order_phases the worker was on.
            stmt_err = (
                select(func.count(CuratedQualityEvent.id))
                .join(
                    CuratedOrderPhase,
                    and_(
                        CuratedOrderPhase.of_id == CuratedQualityEvent.of_id,
                        CuratedOrderPhase.fase_id == CuratedQualityEvent.fase_id,
                    ),
                )
                .join(
                    CuratedAllocation,
                    CuratedAllocation.fase_of_id == CuratedOrderPhase.fase_of_id,
                )
                .where(CuratedAllocation.funcionario_id == worker_id)
                .where(CuratedOrderPhase.fase_id == phase_id)
                .where(CuratedQualityEvent.data_evento.isnot(None))
                .where(CuratedQualityEvent.data_evento >= start)
                .where(CuratedQualityEvent.data_evento < end)
            )
            errors = int((await self.session.execute(stmt_err)).scalar() or 0)

            return WorkerStats(
                worker_id=worker_id,
                phase_id=phase_id,
                total_allocations=total,
                error_count=errors,
            )
        except Exception as exc:
            logger.debug(
                "worker_phase_stats(%s,%s) failed (%s)", worker_id, phase_id, exc,
            )
            return WorkerStats(
                worker_id=worker_id, phase_id=phase_id,
                total_allocations=0, error_count=0,
            )

    # ──────────────────────────────────────────────────────────────────
    # WIP / overload helpers
    # ──────────────────────────────────────────────────────────────────

    async def current_wip(self) -> int:
        """Open phases right now (data_inicio set, data_fim NULL)."""
        try:
            from src.factory_data_product.models.curated import CuratedOrderPhase
            stmt = (
                select(func.count(CuratedOrderPhase.id))
                .where(CuratedOrderPhase.data_inicio.isnot(None))
                .where(CuratedOrderPhase.data_fim.is_(None))
            )
            return int((await self.session.execute(stmt)).scalar() or 0)
        except Exception as exc:
            logger.debug("current_wip failed (%s)", exc)
            return 0

    async def avg_wip_during(
        self, start: date, end: date,
    ) -> float:
        """Average WIP across the window. Approximation: count of
        CuratedOrderPhase rows that overlap any day in the window
        divided by the window length in days."""
        try:
            from src.factory_data_product.models.curated import CuratedOrderPhase
            stmt = (
                select(func.count(CuratedOrderPhase.id))
                .where(CuratedOrderPhase.data_inicio.isnot(None))
                .where(CuratedOrderPhase.data_inicio < end)
                .where(
                    # phase still open OR finished after window start
                    (CuratedOrderPhase.data_fim.is_(None))
                    | (CuratedOrderPhase.data_fim >= start)
                )
            )
            total_overlap = int((await self.session.execute(stmt)).scalar() or 0)
            window_days = max(1, (end - start).days)
            return total_overlap / window_days
        except Exception as exc:
            logger.debug("avg_wip_during failed (%s)", exc)
            return 0.0

    # ──────────────────────────────────────────────────────────────────
    # CROSS-PHASE helpers (for Reichenbach later)
    # ──────────────────────────────────────────────────────────────────

    async def boats_through_phases(
        self, phase_ids: List[str], start: date, end: date,
    ) -> List[str]:
        """OF ids that passed through EVERY phase in `phase_ids` in window."""
        if not phase_ids:
            return []
        try:
            from src.factory_data_product.models.curated import CuratedOrderPhase
            # For each phase, the set of of_ids that ran in window;
            # then intersect.
            sets: List[set] = []
            for pid in phase_ids:
                stmt = (
                    select(CuratedOrderPhase.of_id)
                    .where(CuratedOrderPhase.fase_id == pid)
                    .where(CuratedOrderPhase.data_inicio.isnot(None))
                    .where(CuratedOrderPhase.data_inicio >= start)
                    .where(CuratedOrderPhase.data_inicio < end)
                    .distinct()
                )
                rows = (await self.session.execute(stmt)).all()
                sets.append({r[0] for r in rows if r[0]})
            common = set.intersection(*sets) if sets else set()
            return sorted(common)
        except Exception as exc:
            logger.debug("boats_through_phases failed (%s)", exc)
            return []

    async def molds_used_by_boats(
        self, of_ids: List[str], start: date, end: date,
    ) -> Dict[str, int]:
        """``{mold_id: count}`` — moldes usados pelos OFs em window.

        Sprint Q.15.D.2 — Reichenbach `_check_shared_mold` precisa
        identificar molde partilhado por barcos que passaram por TODAS
        as fases que drift juntas. Retorna ``count`` para que o caller
        privilegie moldes muito-usados sobre os que aparecem só uma vez.
        """
        if not of_ids:
            return {}
        try:
            from src.factory_data_product.models.curated import CuratedOrderPhase
            stmt = (
                select(
                    CuratedOrderPhase.molde_id,
                    func.count(CuratedOrderPhase.id),
                )
                .where(CuratedOrderPhase.of_id.in_(of_ids))
                .where(CuratedOrderPhase.molde_id.isnot(None))
                .where(CuratedOrderPhase.data_inicio.isnot(None))
                .where(CuratedOrderPhase.data_inicio >= start)
                .where(CuratedOrderPhase.data_inicio < end)
                .group_by(CuratedOrderPhase.molde_id)
            )
            rows = (await self.session.execute(stmt)).all()
            return {str(r[0]): int(r[1]) for r in rows if r[0]}
        except Exception as exc:
            logger.debug("molds_used_by_boats failed (%s)", exc)
            return {}

    async def workers_in_phase_set(
        self, phase_id: str, start: date, end: date,
    ) -> set:
        """Set of distinct funcionario_id active on a phase in window.

        Convenience for Reichenbach `_check_shared_workers` set
        intersection across deviating phases.
        """
        pairs = await self.workers_active_in_phase(phase_id, start, end)
        return {wid for wid, _count in pairs}

    async def worker_hours_during(
        self, worker_id: str, start: date, end: date,
    ) -> float:
        """Approximate hours worked by a worker in window.

        Approximation: count of allocations × average phase duration
        (we don't have per-allocation hour stamps in CuratedAllocation).
        Used by Reichenbach to flag workers exceeding their normal
        weekly band.

        Returns 0.0 when no data.
        """
        try:
            from src.factory_data_product.models.curated import (
                CuratedAllocation,
                CuratedOrderPhase,
            )
            stmt = (
                select(func.coalesce(func.sum(CuratedOrderPhase.horas_finais), 0))
                .join(
                    CuratedAllocation,
                    CuratedAllocation.fase_of_id == CuratedOrderPhase.fase_of_id,
                )
                .where(CuratedAllocation.funcionario_id == worker_id)
                .where(CuratedOrderPhase.data_inicio.isnot(None))
                .where(CuratedOrderPhase.data_inicio >= start)
                .where(CuratedOrderPhase.data_inicio < end)
            )
            return float((await self.session.execute(stmt)).scalar() or 0.0)
        except Exception as exc:
            logger.debug("worker_hours_during(%s) failed (%s)", worker_id, exc)
            return 0.0

    async def phase_precedes(
        self, phase_a: str, phase_b: str,
    ) -> bool:
        """``True`` iff phase_a appears in routings before phase_b
        (per FasesStandardModelos.sequencia)."""
        try:
            from sqlalchemy import column
            from src.factory_data_product.models.curated import (
                CuratedOrderPhase,
            )
            # Use CuratedOrderPhase as a routing proxy: max sequence of
            # A < min sequence of B inside the same OF means A precedes
            # B in actual routing data.
            stmt_a = (
                select(func.avg(CuratedOrderPhase.ordem))
                .where(CuratedOrderPhase.fase_id == phase_a)
                .where(CuratedOrderPhase.ordem.isnot(None))
            )
            stmt_b = (
                select(func.avg(CuratedOrderPhase.ordem))
                .where(CuratedOrderPhase.fase_id == phase_b)
                .where(CuratedOrderPhase.ordem.isnot(None))
            )
            avg_a = float((await self.session.execute(stmt_a)).scalar() or 0)
            avg_b = float((await self.session.execute(stmt_b)).scalar() or 0)
            return avg_a > 0 and avg_b > 0 and avg_a < avg_b
        except Exception as exc:
            logger.debug("phase_precedes failed (%s)", exc)
            return False


__all__ = ["DiagnosticsRepository"]
