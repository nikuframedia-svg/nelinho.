"""
ProdPlan ONE - COPILOT Context Builder
=======================================

Constrói context_facts estruturado a partir da base de dados.

Q.67.4.D — alargado de 5 para 12 keys no snapshot top-level:

* ``operational_snapshot`` — ordens + WIP por fase + retrabalho macro.
* ``quality`` — rework agregado (top tipos + top operadores).
* ``plan_history`` — distribuição de status dos ProductionSchedule.
* ``trust_index`` — Trust Index v2 factory-scope.
* ``warehouse_stock`` — top 5 SKUs por valor mirrored de supply.warehouse_stock.
* ``factory_calendar`` — próximos 7 dias (working flag + shift hours).
* ``employee_skills`` — contagem de operadores por skill (top 10).
* ``cost_calculations`` — última run + summary agregado.
* ``kill_switch`` — estado boolean + scopes activos + razão.
* ``etl_runs`` — status do último sync por mirror (top 7).
* ``error_catalog`` — top 10 códigos mais frequentes em rework_entry.
* ``meta`` — tamanho do snapshot, versão e timestamp de geração.

Orçamento de tamanho: snapshot serializado deve manter-se ≤ 4 KB para
caber no context-window do Gemma sem comer prompt útil. Cada secção
limita o seu fan-out (top-N pequeno) e degrada graciosamente para uma
estrutura vazia se a query falhar (a UI principal vê ``has_data=False``
em vez de stack trace).
"""

import json
import logging
from datetime import datetime, timedelta, timezone, date
from typing import Dict, Any, List, Optional
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.dqa.trust_signals import curated_signals_provider
from src.dqa.trust_v2 import SCOPE_FACTORY, TrustIndexV2Calculator
from src.plan.models.schedule import ProductionSchedule
from src.shared.auth.rbac import Role

logger = logging.getLogger(__name__)

#: Snapshot serializado nunca passa este tamanho — garante margem
#: confortável face ao prompt total do Gemma (token-budget Q.55.B).
MAX_SNAPSHOT_BYTES = 4 * 1024  # 4 KB


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
        Dict com context_facts estruturado (12 keys top-level — ver módulo
        docstring). Cada sub-builder devolve sempre um dict; nenhuma chave
        é omitida mesmo quando a respectiva query falha (estrutura
        estável para o LLM consumir).
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
        "warehouse_stock": await _build_warehouse_stock(session, tenant_id),
        "factory_calendar": await _build_factory_calendar(session, tenant_id),
        "employee_skills": await _build_employee_skills(session, tenant_id),
        "cost_calculations": await _build_cost_calculations(session, tenant_id),
        "kill_switch": await _build_kill_switch(session, tenant_id),
        "etl_runs": await _build_etl_runs(session, tenant_id),
        "error_catalog": await _build_error_catalog(session, tenant_id),
    }

    # Meta: tamanho/timestamp do snapshot — fica como 12ª chave. Ajuda o
    # próprio LLM a saber se o contexto é fresco e cabe no orçamento.
    serialized = json.dumps(context, default=_json_default, separators=(",", ":"))
    snapshot_bytes = len(serialized.encode("utf-8"))
    context["meta"] = {
        "schema_version": "q67.4.d",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_bytes": snapshot_bytes,
        "tables_count": 12,
        "budget_bytes": MAX_SNAPSHOT_BYTES,
    }

    return context


def _json_default(obj: Any) -> Any:
    """JSON fallback para tipos não nativos (Decimal, datetime, UUID).

    Usado só para *medir* o tamanho do snapshot — não muda a forma como
    cada sub-builder devolve dados (esses já normalizam para str/float).
    """
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    # Decimal e outros — fallback razoável.
    try:
        return float(obj)
    except (TypeError, ValueError):
        return str(obj)


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


# ── Q.67.4.D — 7 sub-builders novos ────────────────────────────────────
#
# Cada um lê uma tabela diferente e devolve um *resumo pequeno* (top-N,
# contagens, último estado). Mantemos o fan-out apertado de propósito —
# o snapshot inteiro tem de ficar abaixo de :data:`MAX_SNAPSHOT_BYTES`.


async def _build_warehouse_stock(
    session: AsyncSession,
    tenant_id: UUID,
) -> Dict[str, Any]:
    """Top 5 SKUs por valor de stock (``supply.warehouse_stock``).

    O ERP NELO é a fonte de verdade do stock; ``supply.warehouse_stock``
    é o mirror onde a UI lê. Para o copiloto interessa só uma vista
    macro: total de linhas, top 5 SKUs por quantidade absoluta + último
    sync.
    """
    empty = {
        "total_rows": 0,
        "top_skus": [],
        "last_synced_at": None,
        "has_data": False,
        "source": "supply.warehouse_stock",
    }
    try:
        from src.supply.models import WarehouseStock

        total = int((await session.execute(
            select(func.count()).where(WarehouseStock.tenant_id == tenant_id)
        )).scalar() or 0)

        rows = (await session.execute(
            select(
                WarehouseStock.product_code,
                WarehouseStock.warehouse_name,
                WarehouseStock.stock,
                WarehouseStock.synced_at,
            )
            .where(WarehouseStock.tenant_id == tenant_id)
            .order_by(WarehouseStock.stock.desc())
            .limit(5)
        )).all()

        last_synced = max((r[3] for r in rows if r[3] is not None), default=None)
        top_skus = [
            {
                "product_code": code,
                "warehouse": wh,
                "stock": float(stock or 0),
            }
            for code, wh, stock, _ in rows
        ]
        return {
            "total_rows": total,
            "top_skus": top_skus,
            "last_synced_at": last_synced.isoformat() if last_synced else None,
            "has_data": total > 0,
            "source": "supply.warehouse_stock",
        }
    except Exception as exc:
        logger.warning("warehouse_stock snapshot failed: %s", exc)
        return empty


async def _build_factory_calendar(
    session: AsyncSession,
    tenant_id: UUID,
) -> Dict[str, Any]:
    """Próximos 7 dias do ``plan.factory_calendar_day``.

    O decoder do CPO consome o calendário; o copiloto precisa de saber
    se hoje/amanhã são working days para responder a "podemos atrasar
    para sexta?". Devolve os próximos 7 dias com flag + horas.
    """
    empty = {
        "days": [],
        "working_days_next_7": 0,
        "total_shift_hours_next_7": 0.0,
        "has_data": False,
        "source": "plan.factory_calendar_day",
    }
    try:
        from src.plan.models.factory_calendar import FactoryCalendarDay

        today = datetime.now(timezone.utc).date()
        horizon = today + timedelta(days=7)
        rows = (await session.execute(
            select(
                FactoryCalendarDay.day,
                FactoryCalendarDay.is_working_day,
                FactoryCalendarDay.shift_hours,
                FactoryCalendarDay.label,
            )
            .where(
                FactoryCalendarDay.tenant_id == tenant_id,
                FactoryCalendarDay.day >= today,
                FactoryCalendarDay.day < horizon,
            )
            .order_by(FactoryCalendarDay.day)
        )).all()

        days = []
        working = 0
        total_hours = 0.0
        for day, is_working, shift_hours, label in rows:
            hours = float(shift_hours or 0)
            days.append({
                "day": day.isoformat() if hasattr(day, "isoformat") else str(day),
                "working": bool(is_working),
                "shift_hours": hours,
                "label": label or "",
            })
            if is_working:
                working += 1
                total_hours += hours

        return {
            "days": days,
            "working_days_next_7": working,
            "total_shift_hours_next_7": round(total_hours, 2),
            "has_data": bool(days),
            "source": "plan.factory_calendar_day",
        }
    except Exception as exc:
        logger.warning("factory_calendar snapshot failed: %s", exc)
        return empty


async def _build_employee_skills(
    session: AsyncSession,
    tenant_id: UUID,
) -> Dict[str, Any]:
    """Contagem de operadores por skill (top 10) — ``hr.employee_skills``.

    Responde a "quantos operadores sabem Laminagem?". Junta com
    ``hr.skills`` para devolver o nome legível.
    """
    empty = {
        "skills": [],
        "total_skills": 0,
        "total_assignments": 0,
        "has_data": False,
        "source": "hr.employee_skills",
    }
    try:
        from src.hr.models.allocation import EmployeeSkill, Skill

        total_assignments = int((await session.execute(
            select(func.count()).where(EmployeeSkill.tenant_id == tenant_id)
        )).scalar() or 0)

        rows = (await session.execute(
            select(
                Skill.skill_code,
                Skill.skill_name,
                func.count(EmployeeSkill.id).label("n"),
            )
            .join(EmployeeSkill, EmployeeSkill.skill_id == Skill.id)
            .where(EmployeeSkill.tenant_id == tenant_id)
            .group_by(Skill.skill_code, Skill.skill_name)
            .order_by(func.count(EmployeeSkill.id).desc())
            .limit(10)
        )).all()

        skills = [
            {"code": code, "name": name, "operators": int(n)}
            for code, name, n in rows
        ]
        return {
            "skills": skills,
            "total_skills": len(skills),
            "total_assignments": total_assignments,
            "has_data": total_assignments > 0,
            "source": "hr.employee_skills",
        }
    except Exception as exc:
        logger.warning("employee_skills snapshot failed: %s", exc)
        return empty


async def _build_cost_calculations(
    session: AsyncSession,
    tenant_id: UUID,
) -> Dict[str, Any]:
    """Última cost calculation + summary — ``profit.cost_calculations``.

    Responde a "qual o último custo calculado?". Devolve o último run
    + média/contagem por status.
    """
    empty = {
        "last_run": None,
        "summary": [],
        "total_calculations": 0,
        "has_data": False,
        "source": "profit.cost_calculations",
    }
    try:
        from src.profit.models.cost import CostCalculation

        total = int((await session.execute(
            select(func.count()).where(CostCalculation.tenant_id == tenant_id)
        )).scalar() or 0)

        last = (await session.execute(
            select(
                CostCalculation.order_id,
                CostCalculation.total_cogs,
                CostCalculation.status,
                CostCalculation.calculated_at,
            )
            .where(CostCalculation.tenant_id == tenant_id)
            .order_by(CostCalculation.calculated_at.desc().nulls_last())
            .limit(1)
        )).all()

        last_run = None
        if last:
            order_id, total_cogs, status, calc_at = last[0]
            last_run = {
                "order_id": order_id,
                "total_cogs_eur": float(total_cogs or 0),
                "status": str(status) if status else None,
                "calculated_at": calc_at.isoformat() if calc_at else None,
            }

        status_rows = (await session.execute(
            select(CostCalculation.status, func.count())
            .where(CostCalculation.tenant_id == tenant_id)
            .group_by(CostCalculation.status)
        )).all()
        summary = [
            {"status": str(s) if s else "UNKNOWN", "count": int(c)}
            for s, c in status_rows
        ]

        return {
            "last_run": last_run,
            "summary": summary,
            "total_calculations": total,
            "has_data": total > 0,
            "source": "profit.cost_calculations",
        }
    except Exception as exc:
        logger.warning("cost_calculations snapshot failed: %s", exc)
        return empty


async def _build_kill_switch(
    session: AsyncSession,
    tenant_id: UUID,
) -> Dict[str, Any]:
    """Estado actual do kill-switch — ``governance.kill_switch_active``.

    O LLM precisa de saber se há um kill-switch activo para nunca propor
    escritas que vão ser bloqueadas. Devolve boolean + lista de scopes
    activos + razão do primeiro.
    """
    empty = {
        "active": False,
        "scopes": [],
        "reason": None,
        "activated_by": None,
        "activated_at": None,
        "source": "governance.kill_switch_active",
    }
    try:
        from src.governance.models import KillSwitchActive

        rows = (await session.execute(
            select(
                KillSwitchActive.scope,
                KillSwitchActive.reason,
                KillSwitchActive.activated_by,
                KillSwitchActive.activated_at,
                KillSwitchActive.deactivated_at,
            )
            .where(
                KillSwitchActive.tenant_id == tenant_id,
                KillSwitchActive.deactivated_at.is_(None),
            )
            .order_by(KillSwitchActive.activated_at.desc())
        )).all()

        if not rows:
            return empty

        scopes = [r[0] for r in rows]
        first = rows[0]
        return {
            "active": True,
            "scopes": scopes,
            "reason": first[1],
            "activated_by": first[2],
            "activated_at": first[3].isoformat() if first[3] else None,
            "source": "governance.kill_switch_active",
        }
    except Exception as exc:
        logger.warning("kill_switch snapshot failed: %s", exc)
        return empty


async def _build_etl_runs(
    session: AsyncSession,
    tenant_id: UUID,
) -> Dict[str, Any]:
    """Último sync por mirror — ``core.etl_run``.

    O copiloto deve saber se os dados que vê são frescos. Esta vista é
    "qual foi o último run de cada mirror" (master, molds, skills,
    quality, time_mining…) — top 7 fontes.
    """
    empty = {
        "last_runs": [],
        "total_runs": 0,
        "has_data": False,
        "source": "core.etl_run",
    }
    try:
        from src.core.models.etl_run import EtlRun

        total = int((await session.execute(
            select(func.count()).where(EtlRun.tenant_id == tenant_id)
        )).scalar() or 0)

        # Última row por source: usa MAX(started_at) agregado por source,
        # depois junta para apanhar o status correspondente. Simplificámos
        # para um único select agregado — basta para o snapshot.
        rows = (await session.execute(
            select(
                EtlRun.source,
                func.max(EtlRun.started_at).label("last_started"),
            )
            .where(EtlRun.tenant_id == tenant_id)
            .group_by(EtlRun.source)
            .order_by(func.max(EtlRun.started_at).desc())
            .limit(7)
        )).all()

        last_runs = []
        for source, last_started in rows:
            status_row = (await session.execute(
                select(EtlRun.status, EtlRun.rows_inserted, EtlRun.rows_updated)
                .where(
                    EtlRun.tenant_id == tenant_id,
                    EtlRun.source == source,
                    EtlRun.started_at == last_started,
                )
                .limit(1)
            )).all()
            status = inserted = updated = None
            if status_row:
                status, inserted, updated = status_row[0]
            last_runs.append({
                "source": source,
                "last_run_at": last_started.isoformat() if last_started else None,
                "status": status,
                "rows_inserted": int(inserted or 0),
                "rows_updated": int(updated or 0),
            })

        return {
            "last_runs": last_runs,
            "total_runs": total,
            "has_data": total > 0,
            "source": "core.etl_run",
        }
    except Exception as exc:
        logger.warning("etl_runs snapshot failed: %s", exc)
        return empty


async def _build_error_catalog(
    session: AsyncSession,
    tenant_id: UUID,
) -> Dict[str, Any]:
    """Top 10 códigos de erro por frequência em ``quality.rework_entry``.

    Complementa ``_build_quality_snapshot`` mas com janela total (não
    30 dias) — útil para o copiloto responder a "quais os defeitos
    crónicos da fábrica?".
    """
    empty = {
        "top_codes": [],
        "total_catalog_entries": 0,
        "has_data": False,
        "source": "quality.error_catalog+rework_entry",
    }
    try:
        from src.quality.models.rework import ErrorCatalog, ReworkEntry

        total_catalog = int((await session.execute(
            select(func.count()).where(ErrorCatalog.tenant_id == tenant_id)
        )).scalar() or 0)

        rows = (await session.execute(
            select(
                ReworkEntry.error_code,
                func.count(ReworkEntry.id).label("n"),
            )
            .where(ReworkEntry.tenant_id == tenant_id)
            .group_by(ReworkEntry.error_code)
            .order_by(func.count(ReworkEntry.id).desc())
            .limit(10)
        )).all()

        codes = [c for c, _ in rows if c is not None]
        names: Dict[str, str] = {}
        if codes:
            name_rows = (await session.execute(
                select(ErrorCatalog.error_code, ErrorCatalog.name).where(
                    ErrorCatalog.tenant_id == tenant_id,
                    ErrorCatalog.error_code.in_(codes),
                )
            )).all()
            names = {code: name for code, name in name_rows}

        top_codes = [
            {
                "code": code,
                "name": names.get(code, code),
                "events": int(n),
            }
            for code, n in rows
        ]
        return {
            "top_codes": top_codes,
            "total_catalog_entries": total_catalog,
            "has_data": bool(top_codes),
            "source": "quality.error_catalog+rework_entry",
        }
    except Exception as exc:
        logger.warning("error_catalog snapshot failed: %s", exc)
        return empty


