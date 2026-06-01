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
    CuratedQualityEvent,
    CuratedSkillMatrix,
)
from src.plan.models.schedule import ProductionSchedule
from src.quality.models.rework import ReworkEntry
from src.workforce.levels import area_group_for_phase

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
    # Q.140.A — quando o score é escopado a um grupo de área (sector), o
    # nome do grupo fica aqui; None = score global (comportamento anterior).
    area_group: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "employee_id": str(self.employee_id),
            "score": round(self.score, 2),
            "defects": self.defects,
            "operations": self.operations,
            "defect_rate": round(self.defect_rate, 4),
            "method": self.method,
            "area_group": self.area_group,
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

    async def quality_score(
        self, employee_id: UUID, *, area_group: Optional[str] = None,
    ) -> QualityScoreResult:
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

        Q.54.P — quando ``ProductionSchedule`` não tem linhas para o
        operador (o caso real hoje: 0 das 159 linhas têm operador
        atribuído), cai na camada ERP curada: 131k linhas em
        ``factory_curated.allocation`` (operações) e 97k em
        ``quality_event`` (defeitos). É o mesmo fallback que o
        ``skill_matrix`` já fazia — sem ele todos os operadores saíam
        como "sem histórico" quando o histórico real existe.

        Q.140.A — ``area_group`` escopa o score a um sector (grupo de
        área). Conta só as ops/defeitos das fases cujo
        ``area_group_for_phase`` casa com o grupo, reusando o histórico
        per-fase do ``skill_matrix``. ``None`` = score global (acima).
        Permite um nível DIFERENTE por sector para a mesma pessoa.
        """
        emp = await self._get_employee(employee_id)
        code = emp.employee_code if emp is not None else None

        if area_group is not None:
            return await self._quality_score_for_area(
                employee_id, code, area_group,
            )

        # Camada de governança: ProductionSchedule + ReworkEntry.
        ops = await self._count_ops(employee_id)
        if ops > 0:
            defects = await self._count_rework(employee_id)
        else:
            # ProductionSchedule não cobre este operador → histórico real
            # do ERP na camada curada, keyed por employee_code.
            ops = await self._count_curated_ops(code)
            defects = await self._count_curated_defects(code)

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

    async def _quality_score_for_area(
        self,
        employee_id: UUID,
        employee_code: Optional[str],
        area_group: str,
    ) -> QualityScoreResult:
        """quality_score escopado a um grupo de área (Q.140.A).

        Reaproveita o histórico per-fase do ``skill_matrix`` (que já junta
        curated + ERP real) e os defeitos per-fase, somando só as fases
        cujo ``area_group_for_phase`` casa com ``area_group``. Mesma
        fórmula Laplace; ``default_no_history`` quando o sector não tem ops.
        """
        rows = await self.skill_matrix(employee_id)
        scoped = [
            r for r in rows
            if area_group_for_phase(r.phase_name, r.phase_id) == area_group
        ]
        ops = sum(r.ops_count for r in scoped)
        defects = 0
        if scoped:
            defects_by_phase = await self._curated_defects_by_phase(employee_code)
            area_phase_ids = {r.phase_id for r in scoped}
            defects = sum(
                v for pid, v in defects_by_phase.items() if pid in area_phase_ids
            )

        if ops == 0 and defects == 0:
            return QualityScoreResult(
                employee_id=employee_id,
                score=DEFAULT_SCORE,
                defects=0,
                operations=0,
                defect_rate=0.0,
                method="default_no_history",
                area_group=area_group,
            )

        rate = (defects + SMOOTHING_ALPHA) / (ops + SMOOTHING_BETA)
        score = max(1.0, min(10.0, 10.0 - 10.0 * rate))
        return QualityScoreResult(
            employee_id=employee_id,
            score=score,
            defects=defects,
            operations=ops,
            defect_rate=rate,
            method="laplace_smoothed",
            area_group=area_group,
        )

    async def _curated_defects_by_phase(
        self, employee_code: Optional[str],
    ) -> dict[str, int]:
        """Defeitos curados agregados POR fase_id para um operador (Q.140.A).

        Mesma junção que ``_count_curated_defects`` (allocation →
        order_phase → quality_event) mas ``GROUP BY fase_id`` — uma única
        query devolve {fase_id: nº de erros}. Usado para escopar o
        quality_score a um grupo de área.
        """
        if not employee_code:
            return {}
        try:
            stmt = (
                select(
                    CuratedOrderPhase.fase_id,
                    func.coalesce(func.sum(CuratedQualityEvent.quantidade), 0),
                )
                .select_from(CuratedAllocation)
                .join(
                    CuratedOrderPhase,
                    CuratedOrderPhase.fase_of_id == CuratedAllocation.fase_of_id,
                )
                .join(
                    CuratedQualityEvent,
                    and_(
                        CuratedQualityEvent.of_id == CuratedOrderPhase.of_id,
                        CuratedQualityEvent.fase_id == CuratedOrderPhase.fase_id,
                    ),
                )
                .where(CuratedAllocation.funcionario_id == employee_code)
                .group_by(CuratedOrderPhase.fase_id)
            )
            rows = (await self.session.execute(stmt)).all()
            return {str(r[0]): int(r[1] or 0) for r in rows}
        except Exception as exc:  # pragma: no cover — defensivo
            logger.warning(
                "curated defects-by-phase failed for employee_code=%s: %s",
                employee_code,
                exc,
            )
            return {}

    # ─────────────────────────────────────────────────────────────────────
    # Q.62.C.1 — Team-wide defect rate (Hipotese A: comportamento da equipa)
    # ─────────────────────────────────────────────────────────────────────

    async def team_defect_rate(
        self, *, window_days: int = 90,
    ) -> float:
        """Hipótese A: comportamento da equipa toda no tenant.

        Mesma fórmula Laplace do `quality_score()` per-employee, mas
        agregada — soma operações e defeitos de TODOS os operadores
        do tenant dentro da janela de `window_days`::

            rate = (sum(defects) + α) / (sum(ops) + β)

        α=1, β=10 (consistente com `quality_score`). Range [0, 1].

        Q.62.C — usado pelo `KPIFactory.team_defect_rate()` para dashboards
        executivos que querem saber "a equipa está a fazer bem?"
        (distinct de `product_defect_rate` que mede qualidade dos barcos
        entregues, ver `FactoryMapService._defect_rate_from_db`).

        Implementação: count de `ProductionSchedule` com operador atribuído
        + count de `ReworkEntry` com causer atribuído. Sem fallback curated
        — quando governance está vazia, retorna o Laplace floor (0.1)
        que sinaliza "sem histórico" honestamente.
        """
        from datetime import timedelta, timezone

        now_utc = datetime.now(timezone.utc)
        since_date = (now_utc - timedelta(days=window_days)).date()

        # Total ops: ProductionSchedule com operador atribuído na janela.
        # `scheduled_start_date` é Date (não datetime); filtramos por date.
        ops_stmt = select(func.count(ProductionSchedule.id)).where(
            and_(
                ProductionSchedule.tenant_id == self.tenant_id,
                ProductionSchedule.assigned_employee_id.is_not(None),
                ProductionSchedule.scheduled_start_date >= since_date,
            )
        )
        ops = int((await self.session.execute(ops_stmt)).scalar_one() or 0)

        # Total defects: ReworkEntry com causer atribuído na janela.
        # `detected_at` é datetime tz-aware.
        since = now_utc - timedelta(days=window_days)
        rework_stmt = select(func.count(ReworkEntry.id)).where(
            and_(
                ReworkEntry.tenant_id == self.tenant_id,
                ReworkEntry.causer_employee_id.is_not(None),
                ReworkEntry.detected_at >= since,
            )
        )
        defects = int(
            (await self.session.execute(rework_stmt)).scalar_one() or 0
        )

        rate = (defects + SMOOTHING_ALPHA) / (ops + SMOOTHING_BETA)
        return round(rate, 4)

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
        # Q.54.P — `phase_name` vem agora do histórico (`fase_nome` do
        # CuratedOrderPhase). Sem ele o fit-score recebia só o `fase_id`
        # (código "5") e nunca casava com o nome da fase do barco
        # ("Pintura Acabamento") → dizia "Sem experiência" a quem tinha.
        for phase_id, hist in history_by_phase.items():
            if phase_id in seen_phases:
                continue
            out.append(
                SkillMatrixRow(
                    phase_id=phase_id,
                    phase_name=hist.get("phase_name"),
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

    async def _count_curated_ops(self, employee_code: Optional[str]) -> int:
        """Nº de operações no histórico ERP curado (`factory_curated.allocation`).

        Q.54.P — usado quando `ProductionSchedule` não cobre o operador. A
        camada curada tem 131k alocações reais, keyed por `funcionario_id`
        = `employee_code`.
        """
        if not employee_code:
            return 0
        try:
            stmt = select(func.count(CuratedAllocation.id)).where(
                CuratedAllocation.funcionario_id == employee_code
            )
            result = await self.session.execute(stmt)
            return int(result.scalar_one() or 0)
        except Exception as exc:  # pragma: no cover — defensivo
            logger.warning(
                "curated ops count failed for employee_code=%s: %s",
                employee_code,
                exc,
            )
            return 0

    async def _count_curated_defects(self, employee_code: Optional[str]) -> int:
        """Defeitos atribuíveis ao operador via o histórico ERP curado.

        Q.54.P — `factory_curated.quality_event` regista erros por
        `(of_id, fase_id)`, sem operador. Atribui-se a um operador
        cruzando com as fases-de-ordem em que ele trabalhou:
        ``allocation → order_phase → quality_event``. Soma `quantidade`
        (nº de erros do evento).
        """
        if not employee_code:
            return 0
        try:
            stmt = (
                select(func.coalesce(func.sum(CuratedQualityEvent.quantidade), 0))
                .select_from(CuratedAllocation)
                .join(
                    CuratedOrderPhase,
                    CuratedOrderPhase.fase_of_id == CuratedAllocation.fase_of_id,
                )
                .join(
                    CuratedQualityEvent,
                    and_(
                        CuratedQualityEvent.of_id == CuratedOrderPhase.of_id,
                        CuratedQualityEvent.fase_id == CuratedOrderPhase.fase_id,
                    ),
                )
                .where(CuratedAllocation.funcionario_id == employee_code)
            )
            result = await self.session.execute(stmt)
            return int(result.scalar_one() or 0)
        except Exception as exc:  # pragma: no cover — defensivo
            logger.warning(
                "curated defects count failed for employee_code=%s: %s",
                employee_code,
                exc,
            )
            return 0

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
                    CuratedOrderPhase.fase_nome.label("phase_name"),
                    func.count(CuratedAllocation.id).label("ops_count"),
                    func.max(CuratedOrderPhase.data_fim).label("last_used_at"),
                )
                .join(
                    CuratedOrderPhase,
                    CuratedOrderPhase.fase_of_id == CuratedAllocation.fase_of_id,
                )
                .where(CuratedAllocation.funcionario_id == employee_code)
                .group_by(CuratedOrderPhase.fase_id, CuratedOrderPhase.fase_nome)
            )
            rows = (await self.session.execute(stmt)).all()
            out: list[dict[str, Any]] = []
            for r in rows:
                last = r[3]
                last_dt: Optional[datetime] = None
                if last is not None:
                    last_dt = (
                        datetime.combine(last, datetime.min.time())
                        if isinstance(last, date) else last
                    )
                out.append(
                    {
                        "phase_id": r[0],
                        "phase_name": r[1],
                        "ops_count": int(r[2] or 0),
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
