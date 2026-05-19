"""
ProdPlan ONE - COPILOT Context Builder
=======================================

Constrói context_facts estruturado a partir da base de dados.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.dqa.trust_signals import curated_signals_provider
from src.dqa.trust_v2 import SCOPE_FACTORY, TrustIndexV2Calculator
from src.plan.models.schedule import ProductionSchedule
from src.shared.auth.rbac import Role

logger = logging.getLogger(__name__)


async def build_context_facts(
    session: AsyncSession,
    tenant_id: UUID,
    context_window_hours: int,
    user_role: str,
    kpi_snapshot: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Construir context_facts estruturado.
    
    Args:
        session: Database session
        tenant_id: Tenant ID
        context_window_hours: Janela temporal (horas)
        user_role: Role do utilizador (para redação)
        kpi_snapshot: Snapshot de KPIs (opcional, se fornecido usa valores reais)
    
    Returns:
        Dict com context_facts estruturado
    """
    has_hr_role = user_role in (Role.HR_MANAGER.value, Role.ADMIN_PLATFORM.value)
    
    # Calcular data de início
    window_start = datetime.now(timezone.utc) - timedelta(hours=context_window_hours)
    
    context = {
        "operational_snapshot": await _build_operational_snapshot(
            session, tenant_id, window_start, has_hr_role, kpi_snapshot=kpi_snapshot
        ),
        "quality": await _build_quality_snapshot(session, tenant_id, window_start),
        "plan_history": await _build_plan_history(session, tenant_id),
        "trust_index": await _calculate_trust_index(session, tenant_id),
    }
    
    return context


async def _build_operational_snapshot(
    session: AsyncSession,
    tenant_id: UUID,
    window_start: datetime,
    has_hr_role: bool,
    kpi_snapshot: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Snapshot operacional — Q.55.B.1: lê mesmo a base de dados.

    Antes, esta função só relayava um ``kpi_snapshot``; sem ele, devolvia
    zeros. Como o ``kpi_snapshot`` só é buscado para o intent ``kpi_current``,
    quase todas as perguntas chegavam ao LLM com um contexto operacional
    vazio — e o copiloto respondia "não tenho dados" com 164 ordens em curso
    e 100k eventos de retrabalho na BD.

    Agora a BD é a base: contagens de ordens (``plan.production_orders``) e
    de retrabalho (``quality.rework_entry``) vêm sempre de SELECTs reais. O
    ``kpi_snapshot``, quando existe, sobrepõe-se só nos KPIs derivados
    (OEE/disponibilidade/performance/FPY) que precisam do cálculo próprio.
    """
    from src.plan.models.order import ProductionOrder
    from src.quality.models.rework import ReworkEntry

    # ── Base: sempre consultar a BD ───────────────────────────────────────
    orders_total = orders_in_progress = orders_completed = 0
    rework_total = rework_7d = 0
    rework_last: Optional[str] = None
    top_phases: List[Dict[str, Any]] = []
    db_ok = False

    try:
        status_rows = (await session.execute(
            select(ProductionOrder.status, func.count())
            .where(ProductionOrder.tenant_id == tenant_id)
            .group_by(ProductionOrder.status)
        )).all()
        by_status = {str(s): int(c) for s, c in status_rows}
        orders_in_progress = by_status.get("IN_PROGRESS", 0)
        orders_completed = by_status.get("COMPLETED", 0)
        orders_total = sum(by_status.values())

        phase_rows = (await session.execute(
            select(ProductionOrder.current_phase_name, func.count().label("c"))
            .where(
                ProductionOrder.tenant_id == tenant_id,
                ProductionOrder.status == "IN_PROGRESS",
            )
            .group_by(ProductionOrder.current_phase_name)
            .order_by(func.count().desc())
            .limit(5)
        )).all()
        top_phases = [
            {"phase": (p or "?"), "wip": int(c)} for p, c in phase_rows
        ]

        total_rows = (await session.execute(
            select(func.count(), func.max(ReworkEntry.detected_at))
            .where(ReworkEntry.tenant_id == tenant_id)
        )).all()
        if total_rows:
            rework_total = int(total_rows[0][0] or 0)
            last_dt = total_rows[0][1]
            rework_last = last_dt.date().isoformat() if last_dt else None

        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        recent_rows = (await session.execute(
            select(func.count()).where(
                ReworkEntry.tenant_id == tenant_id,
                ReworkEntry.detected_at >= seven_days_ago,
            )
        )).all()
        if recent_rows:
            rework_7d = int(recent_rows[0][0] or 0)

        db_ok = True
    except Exception as exc:
        logger.warning(f"operational_snapshot: query à BD falhou ({exc})")

    # ── Overlay: KPIs derivados, só quando há kpi_snapshot ────────────────
    def _kpi(name: str) -> Optional[float]:
        d = kpi_snapshot.get(name) if kpi_snapshot else None
        v = d.get("value") if isinstance(d, dict) else None
        return float(v) if v is not None else None

    oee = _kpi("oee")
    availability = _kpi("availability")
    performance = _kpi("performance")
    fpy_value = _kpi("quality_fpy")
    rework_rate = _kpi("rework_rate")

    has_data = db_ok and (orders_total > 0 or rework_total > 0)

    return {
        "orders_total": orders_total,
        "orders_in_progress": orders_in_progress,
        "orders_completed": orders_completed,
        "rework_events_total": rework_total,
        "rework_events_7d": rework_7d,
        "rework_last_detected": rework_last,
        "rework_rate": rework_rate if rework_rate is not None else 0.0,
        "fpy": fpy_value if fpy_value is not None else 0.0,
        "oee": oee,
        "availability": availability,
        "performance": performance,
        "quality": fpy_value,
        "top_phases_by_wip": top_phases,
        "allocations": {
            "top_phases": [],
            "top_employees": [],  # Mascarado se não HR role
        },
        "standard_times": {
            "avg_labor_hours": 0.0,
            "avg_machine_hours": 0.0,
        },
        "has_data": has_data,
        "data_status": "DATA_AVAILABLE" if has_data else "NO_DATA_AVAILABLE",
    }


async def _build_quality_snapshot(
    session: AsyncSession,
    tenant_id: UUID,
    window_start: datetime,
) -> Dict[str, Any]:
    """Snapshot de qualidade — Q.55.C.1: lê `quality.rework_entry`.

    Antes chamava `SemanticQueriesInMemory().quality_analysis()` — a classe
    pedia um `engine` (não passado) e o método nem existe → excepção
    silenciada → zeros → o copiloto respondia "não tenho dados" a perguntas
    sobre erros, com 100k+ eventos de retrabalho na BD.

    Agora responde a "qual o erro mais comum" e "que trabalhador tem mais
    erros": tipos de erro agregados de `rework_entry`, ranking de operadores
    via :class:`WorkerRankingService`, nomes legíveis de `core.employees` e
    `quality.error_catalog`. Janela: 30 dias.
    """
    from datetime import timedelta, timezone

    from src.core.models.employee import Employee
    from src.quality.models.rework import ErrorCatalog, ReworkEntry
    from src.quality.services.worker_ranking_service import WorkerRankingService

    empty = {
        "total_errors": 0,
        "most_common_error": None,
        "top_error_types": [],
        "top_workers": [],
        "window_days": 30,
        "has_data": False,
        "source": "quality.rework_entry",
    }
    try:
        since = datetime.now(timezone.utc) - timedelta(days=30)

        # ── Tipos de erro: top 5 por nº de eventos (a linha 0 é o mais comum) ──
        type_rows = (await session.execute(
            select(ReworkEntry.error_code, func.count(ReworkEntry.id).label("n"))
            .where(
                ReworkEntry.tenant_id == tenant_id,
                ReworkEntry.detected_at >= since,
            )
            .group_by(ReworkEntry.error_code)
            .order_by(func.count(ReworkEntry.id).desc())
            .limit(5)
        )).all()

        total_errors = int((await session.execute(
            select(func.count(ReworkEntry.id)).where(
                ReworkEntry.tenant_id == tenant_id,
                ReworkEntry.detected_at >= since,
            )
        )).scalar() or 0)

        # ── Ranking de trabalhadores (reutiliza o serviço da casa) ──
        worker_rows = await WorkerRankingService(session, tenant_id).ranking(
            since=since, limit=5,
        )

        # ── Nomes legíveis: error_code → name, employee_id → name ──
        codes = [c for c, _ in type_rows]
        code_names: Dict[str, str] = {}
        if codes:
            for code, name in (await session.execute(
                select(ErrorCatalog.error_code, ErrorCatalog.name).where(
                    ErrorCatalog.tenant_id == tenant_id,
                    ErrorCatalog.error_code.in_(codes),
                )
            )).all():
                code_names[code] = name

        worker_ids = [w["employee_id"] for w in worker_rows]
        emp_names: Dict[str, str] = {}
        if worker_ids:
            for emp_id, emp_name in (await session.execute(
                select(Employee.id, Employee.employee_name).where(
                    Employee.id.in_(worker_ids),
                )
            )).all():
                emp_names[str(emp_id)] = emp_name

        top_error_types = [
            {"code": code, "name": code_names.get(code, code), "events": int(n)}
            for code, n in type_rows
        ]
        most_common = top_error_types[0] if top_error_types else None
        if most_common:
            most_common = {
                **most_common,
                "share_pct": round(100.0 * most_common["events"] / max(1, total_errors), 1),
            }

        top_workers = [
            {
                "name": emp_names.get(w["employee_id"], "?"),
                "employee_id": w["employee_id"],
                "error_count": w["error_count"],
                "share_pct": w["share_pct"],
            }
            for w in worker_rows
        ]

        return {
            "total_errors": total_errors,
            "most_common_error": most_common,
            "top_error_types": top_error_types,
            "top_workers": top_workers,
            "window_days": 30,
            "has_data": total_errors > 0,
            "source": "quality.rework_entry",
        }
    except Exception as e:
        logger.warning(f"quality_snapshot: query à BD falhou ({e})")
        return empty


async def _build_plan_history(
    session: AsyncSession,
    tenant_id: UUID,
) -> Dict[str, Any]:
    """Build plan history from recent ProductionSchedule records."""
    try:
        stmt = select(
            ProductionSchedule.status,
            func.count().label("count"),
        ).where(
            ProductionSchedule.tenant_id == tenant_id,
        ).group_by(ProductionSchedule.status)

        result = await session.execute(stmt)
        rows = result.all()

        if rows:
            status_counts = {row.status: row.count for row in rows}
            return {
                "has_history": True,
                "status_distribution": status_counts,
                "total_scheduled": sum(status_counts.values()),
            }
    except Exception as e:
        logger.debug(f"Plan history query failed: {e}")

    return {
        "has_history": False,
        "recent_diffs": "NO_PLAN_HISTORY",
    }


async def _calculate_trust_index(
    session: AsyncSession,
    tenant_id: UUID,
) -> Dict[str, Any]:
    """
    Compute the factory-scope Trust Index v2 (Blueprint v2.0 §4.5).

    Returns a dict with:
      - value: composite TI in [0, 1]
      - factors: per-component scores (7 components + optional CC) plus the
        legacy `timeliness` alias mapping to `freshness` so older copilot
        prompt templates that read 4 keys keep working.
      - source: "trust_v2_factory" on success, "trust_v2_fallback" on error.
    """
    try:

        calc = TrustIndexV2Calculator(
            session, tenant_id, signals_provider=curated_signals_provider,
        )
        result = await calc.compute_for_scope(SCOPE_FACTORY)
        factors = {
            k: (round(v, 4) if isinstance(v, float) else v)
            for k, v in result.components.as_dict(include_legacy_keys=True).items()
        }
        return {
            "value": round(result.composite, 4),
            "factors": factors,
            "source": "trust_v2_factory",
        }
    except Exception as exc:
        logger.warning(
            "Trust index v2 failed for tenant=%s, falling back to neutral: %s",
            tenant_id, exc,
        )
        return {
            "value": 0.65,
            "factors": {
                "data_freshness": 0.70,
                "integrity": 0.65,
                "completeness": 0.60,
            },
            "source": "trust_v2_fallback",
        }


