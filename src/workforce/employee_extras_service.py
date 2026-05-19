"""
ProdPlan ONE - Employee extras (Sprint Q.3 / GC01-GC10)
=======================================================

Aggregations over per-worker data the EmployeesPage UI needs:

* `quality_score(employee_id)` — Laplace-smoothed defect-rate score in [1, 10]
* `skill_matrix(employee_id)`  — `[{phase_id, can_do, last_used_at, ops_count}]`
* `history(employee_id)`        — paginated operation history (newest first)

Sources:
* `quality.rework_entry.causer_employee_id` for defect counts (Sprint R wiring).
* `factory_curated.skill_matrix.funcionario_id` for the apto/nivel matrix
  (the curated layer joins by ERP business key — Employee.employee_code).
* `plan.production_schedules.assigned_employee_id` for op history + ops counts.

The Camada 1 hook lives in the API layer: when the operator overrides the
ML score / toggles a skill, the route writes a `PreferenceRule` row so the
adaptive-weights pipeline picks it up next training cycle.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.employee import Employee
from src.factory_data_product.models.curated import (
    CuratedAllocation,
    CuratedOrderPhase,
    CuratedSkillMatrix,
)
from src.plan.models.schedule import ProductionSchedule
from src.quality.models.rework import ReworkEntry

logger = logging.getLogger(__name__)


# Smoothing constants — see `quality_score()` docstring.
SMOOTHING_ALPHA = 1.0   # pseudo-defects added to the numerator
SMOOTHING_BETA = 10.0   # pseudo-ops added to the denominator
DEFAULT_SCORE = 9.0     # what a worker with zero history sees

DEFAULT_HISTORY_LIMIT = 50
MAX_HISTORY_LIMIT = 500


@dataclass
class QualityScoreResult:
    employee_id: UUID
    score: float                    # in [1, 10]
    defects: int                    # raw rework count
    operations: int                 # raw scheduled-ops count
    defect_rate: float              # smoothed
    method: str                     # "laplace_smoothed" or "default_no_history"

    def to_dict(self) -> dict[str, Any]:
        return {
            "employee_id": str(self.employee_id),
            "score": round(self.score, 2),
            "defects": self.defects,
            "operations": self.operations,
            "defect_rate": round(self.defect_rate, 4),
            "method": self.method,
        }


@dataclass
class SkillMatrixRow:
    phase_id: str
    phase_name: Optional[str]
    can_do: bool
    nivel: Optional[int]
    ops_count: int
    last_used_at: Optional[datetime]

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase_id": self.phase_id,
            "phase_name": self.phase_name,
            "can_do": self.can_do,
            "nivel": self.nivel,
            "ops_count": self.ops_count,
            "last_used_at": (
                self.last_used_at.isoformat() if self.last_used_at else None
            ),
        }


@dataclass
class QualificationMetrics:
    """Q.53.E — os 3 sinais de qualificação que faltavam.

    Até agora a página workforce só expunha quality-score, skill-match e
    defect-rate. Estes 3 completam o fit-score que a página Fábrica usa:

    * `recency_days` — dias desde a última operação (na fase/área pedida,
      ou em qualquer fase quando `scope` é None). `None` = sem histórico.
    * `versatility` — nº de fases distintas em que o operador é apto/já
      trabalhou. Quanto maior, mais flexível para o scheduler.
    * `productivity` — operações por dia ao longo do histórico observado
      (ops_total / span_dias). `None` quando não dá para calcular.
    """

    employee_id: UUID
    recency_days: Optional[int]
    versatility: int
    productivity: Optional[float]
    ops_total: int
    scope: Optional[str]  # phase_id/area filtrado, ou None = global

    def to_dict(self) -> dict[str, Any]:
        return {
            "employee_id": str(self.employee_id),
            "recency_days": self.recency_days,
            "versatility": self.versatility,
            "productivity": (
                round(self.productivity, 3)
                if self.productivity is not None else None
            ),
            "ops_total": self.ops_total,
            "scope": self.scope,
        }


@dataclass
class OperationHistoryRow:
    schedule_id: UUID
    order_id: str
    scheduled_start_date: date
    scheduled_end_date: date
    status: str
    operation_sequence: int
    actual_duration_hours: Optional[float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schedule_id": str(self.schedule_id),
            "order_id": self.order_id,
            "scheduled_start_date": self.scheduled_start_date.isoformat(),
            "scheduled_end_date": self.scheduled_end_date.isoformat(),
            "status": self.status,
            "operation_sequence": self.operation_sequence,
            "actual_duration_hours": self.actual_duration_hours,
        }


class EmployeeExtrasService:
    """Aggregations over per-worker data — read-only."""

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    # ─────────────────────────────────────────────────────────────────────
    # Quality score
    # ─────────────────────────────────────────────────────────────────────

    async def quality_score(self, employee_id: UUID) -> QualityScoreResult:
        """Laplace-smoothed quality score in [1, 10].

        Formula::
            defect_rate = (rework + α) / (ops + β)
            score       = 10 - 10 × defect_rate

        With α=1, β=10 the prior is "0 ops + 1 phantom ok" → defect_rate
        ≈ 0.1 → score ≈ 9.0. Workers with lots of clean ops trend toward
        10; workers with high rework rates drop. Bounded to [1, 10].

        We use *operations scheduled* as the denominator (not "ops
        completed without rework") because the rework table doesn't
        cover every op and the schedule table is the only authoritative
        per-worker counter we have today.
        """
        ops = await self._count_ops(employee_id)
        defects = await self._count_rework(employee_id)

        if ops == 0 and defects == 0:
            return QualityScoreResult(
                employee_id=employee_id,
                score=DEFAULT_SCORE,
                defects=0,
                operations=0,
                defect_rate=0.0,
                method="default_no_history",
            )

        rate = (defects + SMOOTHING_ALPHA) / (ops + SMOOTHING_BETA)
        raw_score = 10.0 - 10.0 * rate
        score = max(1.0, min(10.0, raw_score))
        return QualityScoreResult(
            employee_id=employee_id,
            score=score,
            defects=defects,
            operations=ops,
            defect_rate=rate,
            method="laplace_smoothed",
        )

    # ─────────────────────────────────────────────────────────────────────
    # Skill matrix
    # ─────────────────────────────────────────────────────────────────────

    async def skill_matrix(self, employee_id: UUID) -> list[SkillMatrixRow]:
        """Per-phase capability + recent activity for one employee.

        Joins the curated `CuratedSkillMatrix` (by `employee_code`) with
        an aggregate over `ProductionSchedule` (last_used_at + ops_count
        per phase). When the curated matrix has no rows for this worker,
        we fall back to the schedule-driven aggregate alone — the
        `can_do` flag is then set from "has done at least one op in this
        phase".
        """
        emp = await self._get_employee(employee_id)
        if emp is None:
            return []

        curated_rows = await self._curated_skills_for(emp.employee_code)
        history_rows = await self._phase_history_for(employee_id)

        # Sprint Q.8 Fase 2.4 — when ProductionSchedule has no rows for
        # this worker (the synthetic schedule may not yet cover them),
        # fall back to the real ERP history materialised in
        # CuratedAllocation. This is the path that turns "0 ops" into
        # the actual hundreds of operations the worker executed.
        if not history_rows:
            history_rows = await self._curated_allocation_history_for(
                emp.employee_code
            )

        history_by_phase = {row["phase_id"]: row for row in history_rows}
        out: list[SkillMatrixRow] = []
        seen_phases: set[str] = set()

        for c in curated_rows:
            phase_id = c["fase_id"]
            seen_phases.add(phase_id)
            hist = history_by_phase.get(phase_id, {})
            out.append(
                SkillMatrixRow(
                    phase_id=phase_id,
                    phase_name=c.get("fase_nome"),
                    can_do=bool(c.get("apto", False)),
                    nivel=c.get("nivel"),
                    ops_count=hist.get("ops_count", 0),
                    last_used_at=hist.get("last_used_at"),
                )
            )

        # Phases the worker has actually done but that aren't in the
        # curated matrix — surface them as `can_do=True, nivel=None`.
        for phase_id, hist in history_by_phase.items():
            if phase_id in seen_phases:
                continue
            out.append(
                SkillMatrixRow(
                    phase_id=phase_id,
                    phase_name=None,
                    can_do=True,
                    nivel=None,
                    ops_count=hist["ops_count"],
                    last_used_at=hist["last_used_at"],
                )
            )

        out.sort(key=lambda r: (-r.ops_count, r.phase_id))
        return out

    # ─────────────────────────────────────────────────────────────────────
    # Qualification metrics (Q.53.E) — recency / versatility / productivity
    # ─────────────────────────────────────────────────────────────────────

    async def qualification_metrics(
        self,
        employee_id: UUID,
        *,
        phase_id: Optional[str] = None,
        area_group: Optional[str] = None,
    ) -> QualificationMetrics:
        """Os 3 sinais de qualificação em falta para o fit-score.

        Deriva tudo da `skill_matrix` (que já junta curated + histórico
        real ERP), evitando uma segunda passagem por queries. Read-only.

        * `phase_id` — quando dado, recency é a recência *nessa fase*.
        * `area_group` — quando dado (e `phase_id` não), recency/ops são
          escopados às fases desse grupo de área. Senão, global.
        """
        from src.workforce.levels import area_group_for_phase

        rows = await self.skill_matrix(employee_id)

        # Recorte do escopo: fase exacta > grupo de área > global.
        if phase_id is not None:
            scope = phase_id
            scoped = [r for r in rows if r.phase_id == phase_id]
        elif area_group is not None:
            scope = area_group
            scoped = [
                r for r in rows
                if area_group_for_phase(r.phase_name, r.phase_id) == area_group
            ]
        else:
            scope = None
            scoped = rows

        # Versatilidade: nº de fases distintas onde é apto OU já trabalhou.
        versatility = sum(
            1 for r in rows if r.can_do or r.ops_count > 0
        )

        # Recência: menor nº de dias desde a última operação no escopo.
        today = datetime.now()
        recency_days: Optional[int] = None
        for r in scoped:
            if r.last_used_at is None:
                continue
            last = r.last_used_at
            # last_used_at pode ser tz-naive (combine de date) — comparar
            # naive com naive para não rebentar com TypeError.
            if last.tzinfo is not None:
                last = last.replace(tzinfo=None)
            delta = (today - last).days
            if delta < 0:
                delta = 0
            if recency_days is None or delta < recency_days:
                recency_days = delta

        # Produtividade: ops_total / span_dias observado no escopo.
        ops_total = sum(r.ops_count for r in scoped)
        last_dates = [
            (r.last_used_at.replace(tzinfo=None)
             if r.last_used_at and r.last_used_at.tzinfo
             else r.last_used_at)
            for r in scoped
            if r.last_used_at is not None
        ]
        productivity: Optional[float] = None
        if ops_total > 0 and last_dates:
            # Sem datas de início por fase, usamos o intervalo entre a
            # operação mais antiga e mais recente como proxy do span.
            span_days = (max(last_dates) - min(last_dates)).days
            # span 0 (uma só fase / mesmo dia) → assume 1 dia para não
            # dividir por zero nem inflar a produtividade ao infinito.
            productivity = ops_total / max(1, span_days)

        return QualificationMetrics(
            employee_id=employee_id,
            recency_days=recency_days,
            versatility=versatility,
            productivity=productivity,
            ops_total=ops_total,
            scope=scope,
        )

    # ─────────────────────────────────────────────────────────────────────
    # Operation history
    # ─────────────────────────────────────────────────────────────────────

    async def history(
        self,
        employee_id: UUID,
        *,
        limit: int = DEFAULT_HISTORY_LIMIT,
        offset: int = 0,
    ) -> list[OperationHistoryRow]:
        """Newest-first paginated operation history for one employee."""
        limit = max(1, min(MAX_HISTORY_LIMIT, limit))
        offset = max(0, offset)

        stmt = (
            select(ProductionSchedule)
            .where(
                and_(
                    ProductionSchedule.tenant_id == self.tenant_id,
                    ProductionSchedule.assigned_employee_id == employee_id,
                )
            )
            .order_by(desc(ProductionSchedule.scheduled_start_date))
            .offset(offset)
            .limit(limit)
        )
        rows = (await self.session.execute(stmt)).scalars().all()

        out: list[OperationHistoryRow] = []
        for r in rows:
            duration: Optional[float] = None
            if r.actual_start and r.actual_end:
                duration = round(
                    (r.actual_end - r.actual_start).total_seconds() / 3600.0, 2,
                )
            out.append(
                OperationHistoryRow(
                    schedule_id=r.id,
                    order_id=r.order_id,
                    scheduled_start_date=r.scheduled_start_date,
                    scheduled_end_date=r.scheduled_end_date,
                    status=r.status.value if hasattr(r.status, "value") else str(r.status),
                    operation_sequence=r.operation_sequence,
                    actual_duration_hours=duration,
                )
            )
        return out

    # ─────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────

    async def _get_employee(self, employee_id: UUID) -> Optional[Employee]:
        stmt = select(Employee).where(
            and_(
                Employee.id == employee_id,
                Employee.tenant_id == self.tenant_id,
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _count_ops(self, employee_id: UUID) -> int:
        stmt = select(func.count(ProductionSchedule.id)).where(
            and_(
                ProductionSchedule.tenant_id == self.tenant_id,
                ProductionSchedule.assigned_employee_id == employee_id,
            )
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def _count_rework(self, employee_id: UUID) -> int:
        stmt = select(func.count(ReworkEntry.id)).where(
            and_(
                ReworkEntry.tenant_id == self.tenant_id,
                ReworkEntry.causer_employee_id == employee_id,
            )
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def _curated_skills_for(
        self, employee_code: Optional[str],
    ) -> list[dict[str, Any]]:
        """The curated layer keys by ERP business key (employee_code)."""
        if not employee_code:
            return []
        try:
            stmt = select(
                CuratedSkillMatrix.fase_id,
                CuratedSkillMatrix.fase_nome,
                CuratedSkillMatrix.apto,
                CuratedSkillMatrix.nivel,
            ).where(CuratedSkillMatrix.funcionario_id == employee_code)
            rows = (await self.session.execute(stmt)).all()
            return [
                {
                    "fase_id": r[0],
                    "fase_nome": r[1],
                    "apto": bool(r[2]),
                    "nivel": int(r[3]) if r[3] is not None else None,
                }
                for r in rows
            ]
        except Exception as exc:  # pragma: no cover — defensive
            # Sprint Q.8 Fase 1 — include the employee_code so the operator
            # can reproduce the failing query directly from the log line
            # (UI showed an employee with zero skills with no other signal).
            logger.warning(
                "skill_matrix query failed for employee_code=%s: %s",
                employee_code,
                exc,
            )
            return []

    async def _phase_history_for(
        self, employee_id: UUID,
    ) -> list[dict[str, Any]]:
        """Operation history aggregated by phase. Uses the joined Operation.

        Returns one row per phase with `ops_count` and `last_used_at`. A
        phase is identified by `Operation.operation_code` because the
        curated layer's `fase_id` matches that string in the legacy
        ingest pipeline.
        """
        from src.core.models.operation import Operation
        try:
            stmt = (
                select(
                    Operation.operation_code.label("phase_id"),
                    func.count(ProductionSchedule.id).label("ops_count"),
                    func.max(ProductionSchedule.scheduled_end_date).label("last_used_at"),
                )
                .join(Operation, Operation.id == ProductionSchedule.operation_id)
                .where(
                    and_(
                        ProductionSchedule.tenant_id == self.tenant_id,
                        ProductionSchedule.assigned_employee_id == employee_id,
                    )
                )
                .group_by(Operation.operation_code)
            )
            rows = (await self.session.execute(stmt)).all()
            out: list[dict[str, Any]] = []
            for r in rows:
                last = r[2]
                last_dt: Optional[datetime] = None
                if last is not None:
                    last_dt = (
                        datetime.combine(last, datetime.min.time())
                        if isinstance(last, date) else last
                    )
                out.append(
                    {
                        "phase_id": r[0],
                        "ops_count": int(r[1] or 0),
                        "last_used_at": last_dt,
                    }
                )
            return out
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("phase history aggregation failed: %s", exc)
            return []

    async def _curated_allocation_history_for(
        self, employee_code: Optional[str],
    ) -> list[dict[str, Any]]:
        """Per-phase ops_count + last_used_at derived from CuratedAllocation.

        Joins `CuratedAllocation` (the ERP allocation log) with
        `CuratedOrderPhase` to recover the phase + completion date that
        the bare allocation row doesn't carry. Returns the same shape as
        `_phase_history_for` so the consumer can drop it in.

        Sprint Q.8 Fase 2.4 — used as a fallback when ProductionSchedule
        has no rows for this worker.
        """
        if not employee_code:
            return []
        try:
            stmt = (
                select(
                    CuratedOrderPhase.fase_id.label("phase_id"),
                    func.count(CuratedAllocation.id).label("ops_count"),
                    func.max(CuratedOrderPhase.data_fim).label("last_used_at"),
                )
                .join(
                    CuratedOrderPhase,
                    CuratedOrderPhase.fase_of_id == CuratedAllocation.fase_of_id,
                )
                .where(CuratedAllocation.funcionario_id == employee_code)
                .group_by(CuratedOrderPhase.fase_id)
            )
            rows = (await self.session.execute(stmt)).all()
            out: list[dict[str, Any]] = []
            for r in rows:
                last = r[2]
                last_dt: Optional[datetime] = None
                if last is not None:
                    last_dt = (
                        datetime.combine(last, datetime.min.time())
                        if isinstance(last, date) else last
                    )
                out.append(
                    {
                        "phase_id": r[0],
                        "ops_count": int(r[1] or 0),
                        "last_used_at": last_dt,
                    }
                )
            return out
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning(
                "curated allocation history failed for employee_code=%s: %s",
                employee_code,
                exc,
            )
            return []
