"""Q.62.D.2 — body extraído do `schedule_cpo` endpoint.

Este módulo expõe `run_cpo_schedule(session, tenant_id, request)` que
contém TODA a lógica de scheduling (FactoryState load, ML wiring, engine
solve, yaml_policy hook, trust index, commit creation). Antes vivia
inline em `src/plan/api/cpo.py:schedule_cpo`.

Extracção permite:
  * Endpoint sync `POST /schedule` continuar a funcionar (chama este).
  * Arq worker (`src/plan/cpo/worker.py`) chamar a mesma função em
    background → endpoint async retorna 202 + job_id.

Behavioral preservation: o dict retornado tem o mesmo shape que o
endpoint produzia + `commit_sha256`/`parent_sha256` + flags do engine.
Raises `HTTPException` como antes — quem chama (endpoint OU worker)
trata.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.cpo.commits import CommitsService, ScheduleCommit
from src.plan.cpo.engine import CPOConfig, CPOv4Engine
from src.plan.cpo.fitness import FitnessConfig
from src.plan.cpo.state import FactoryState
from src.plan.engines.scheduling_adapter import SchedulingMachine
from src.plan.services.routing_resolver import RoutingResolver

logger = logging.getLogger(__name__)


async def _parent_sha(service: CommitsService, commit: ScheduleCommit) -> Optional[str]:
    if commit.parent_id is None:
        return None
    from sqlalchemy import select
    stmt = select(ScheduleCommit.commit_sha256).where(
        ScheduleCommit.id == commit.parent_id
    )
    result = await service.session.execute(stmt)
    row = result.first()
    return row[0] if row else None


async def _compute_trust_index_for_schedule(
    db: AsyncSession, tenant_id: UUID,
) -> float:
    """Re-export from cpo.py para evitar circular import."""
    from src.plan.api.cpo import _compute_trust_index_for_schedule as impl
    return await impl(db, tenant_id)


async def _load_product_prices(
    db: AsyncSession, tenant_id: UUID,
) -> dict[str, Any]:
    """Re-export from cpo.py para evitar circular import."""
    from src.plan.api.cpo import _load_product_prices as impl
    return await impl(db, tenant_id)


def _extract_mapelites_representatives(
    engine: CPOv4Engine, top_n: int = 10,
) -> list[dict[str, Any]]:
    """Re-export from cpo.py para evitar circular import."""
    from src.plan.api.cpo import _extract_mapelites_representatives as impl
    return impl(engine, top_n)


async def run_cpo_schedule(
    session: AsyncSession,
    tenant_id: UUID,
    request: Any,  # CPOScheduleRequest — import circular se anotado
) -> dict[str, Any]:
    """Executa o CPO scheduler + cria commit + retorna dict-shaped result.

    Retorna o mesmo shape de `CPOScheduleResponse` (sem o wrapper Pydantic)
    + `commit_sha256` + `parent_sha256` para o endpoint serializar.

    Raises:
        HTTPException 503: FactoryState não carregado.
        HTTPException 400: sem orders OR resolver retornou 0 ops.
        HTTPException 409: yaml_policy block disparou.
    """
    horizon_start = datetime.utcnow()
    horizon_end = horizon_start + timedelta(days=request.horizon_days)

    state = await FactoryState.load(session, tenant_id)
    if not state.loaded_ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"FactoryState unavailable for tenant {tenant_id}: "
                f"{state.load_error or 'unknown error'}. Ingest curated "
                "data via /v1/factory-data/ingest before scheduling."
            ),
        )

    orders = request.orders or state.open_orders
    if not orders:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No orders available. Either provide `orders` in the request "
                "or ingest data via /v1/factory-data/ingest to populate the "
                "curated layer."
            ),
        )

    fitness_config = await FitnessConfig.from_tenant_config(session, tenant_id)
    from src.plan.cpo.ml_wiring import apply_ml_to_cpo
    duration_predictor, ml_report = await apply_ml_to_cpo(
        session, tenant_id, fitness_config=fitness_config,
    )
    resolver = RoutingResolver(state, duration_predictor=duration_predictor)
    operations = resolver.resolve_many(orders, horizon_start=horizon_start)

    if resolver.engine_unavailable:
        try:
            from src.copilot.alerts.models import (
                CODE_ROUTING_ENGINE_UNAVAILABLE,
                CopilotAlert,
            )
            alert = CopilotAlert(
                tenant_id=tenant_id,
                severity="WARN",
                code=CODE_ROUTING_ENGINE_UNAVAILABLE,
                title="Routing engine unavailable — schedule built on 2× buffer templates",
                message_pt=(
                    "O motor de routing não conseguiu aceder à camada curada "
                    "(factory_data_product). O scheduler caiu para os templates "
                    "FasesStandardModelos com buffer 2× — durações podem divergir "
                    "até 25× da realidade. Re-ingere os dados curados e volta a planear."
                ),
                context={"resolved_orders": len(orders)},
                entity_refs=[],
            )
            session.add(alert)
            await session.flush()
        except Exception as alert_exc:  # noqa: BLE001  Q.62.E.1: behaviour-preserving copy do endpoint sync (best-effort alert; Q.62 nao mexe na semantica)
            logger.warning("CPO schedule: failed to emit routing alert: %s", alert_exc)

    if not operations:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Routing resolver returned no operations. No history or "
                "standard template found for these orders."
            ),
        )

    if request.machines:
        machines = [
            SchedulingMachine(
                machine_id=m.machine_id,
                name=m.name or m.machine_id,
                capacity=m.capacity,
                speed_factor=m.speed_factor,
                centro_custo=m.centro_custo,
            )
            for m in request.machines
        ]
    else:
        machines = [SchedulingMachine(machine_id="MANUAL", name="Manual pool")]

    engine = CPOv4Engine(
        state=state,
        config=CPOConfig(
            population_size=request.population_size,
            generations=request.generations,
            time_limit_sec=request.time_limit_sec,
        ),
        fitness_config=fitness_config,
    )

    product_price_eur = await _load_product_prices(session, tenant_id)

    result = engine.schedule(
        operations, machines, horizon_start, horizon_end,
        product_price_eur=product_price_eur,
    )

    result.setdefault("cpo_meta", {}).update(ml_report.as_meta())

    # Yaml policy hook (best-effort; 409 if block fired).
    try:
        from src.governance.yaml_policy import EventType as _YPEventType
        from src.governance.yaml_policy.engine import RuleEngine as _RuleEngine
        from src.governance.yaml_policy.runtime import get_engine as _get_yp_engine
        _yp_payload = {
            "tenant_id": str(tenant_id),
            "horizon_days": int(request.horizon_days),
            "operations_count": len(result.get("operations", [])),
            "fitness_score": float(result.get("fitness_score", 0.0)),
            "makespan_hours": float(result.get("makespan_hours", 0.0)),
            "tardiness_hours": float(result.get("total_tardiness_hours", 0.0)),
        }
        _yp_fired = await _get_yp_engine().on_event(
            _YPEventType.SCHEDULE_PROPOSE,
            _yp_payload,
            tenant_id=tenant_id,
            session=session,
        )
        _yp_blocks = _RuleEngine.block_results(_yp_fired)
        if _yp_blocks:
            _block = _yp_blocks[0]
            _rule_id = next(
                (r.id for r, results in _yp_fired
                 if any(rs.action == "block" for rs in results)),
                "?",
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "blocked_by_yaml_policy",
                    "rule_id": _rule_id,
                    "scope": _block.payload.get("scope"),
                    "reason_pt": _block.payload.get("reason_pt", ""),
                },
            )
        if _yp_fired:
            logger.info(
                "yaml_policy: schedule_propose fired %d rules (no blocks)",
                len(_yp_fired),
            )
    except HTTPException:
        raise
    except Exception as _yp_exc:  # noqa: BLE001  Q.62.E.1: yaml_policy hook nunca deve partir o scheduler (best-effort)
        logger.warning(f"yaml_policy SCHEDULE_PROPOSE hook failed: {_yp_exc}")

    trust_index_value = await _compute_trust_index_for_schedule(session, tenant_id)

    commit_sha: Optional[str] = None
    parent_sha: Optional[str] = None
    try:
        commits = CommitsService(session, tenant_id)
        alternatives = _extract_mapelites_representatives(engine)
        commit = await commits.create_from_schedule(
            schedule_result=result,
            mapelites_representatives=alternatives,
            delta=request.delta,
            author=request.author,
            message=request.message,
            trust_index=trust_index_value,
        )
        commit_sha = commit.commit_sha256
        parent_sha = await _parent_sha(commits, commit)
    except Exception as e:  # noqa: BLE001  Q.62.E.1: persistencia do commit nunca deve partir o scheduler (schedule funciona, audit opcional)
        logger.warning(f"Schedule-as-Code commit failed: {e}", exc_info=True)

    return {
        "tenant_id": str(tenant_id),
        "engine_used": result.get("engine_used", "cpo_v4"),
        "status": result.get("status", "unknown"),
        "solve_time_sec": float(result.get("solve_time_sec", 0.0)),
        "makespan_hours": float(result.get("makespan_hours", 0.0)),
        "total_tardiness_hours": float(result.get("total_tardiness_hours", 0.0)),
        "num_late_orders": int(result.get("num_late_orders", 0)),
        "setups": int(result.get("setups", 0)),
        "avg_utilization": float(result.get("avg_utilization", 0.0)),
        "safety_net_triggered": bool(result.get("safety_net_triggered", False)),
        "degraded": bool(result.get("degraded", False)),
        "fallback_reason": result.get("fallback_reason"),
        "cpo_meta": result.get("cpo_meta", {}),
        "operations": result.get("operations", []),
        "warnings": list(result.get("warnings", [])),
        "infeasible_op_ids": list(result.get("infeasible_op_ids", [])),
        "commit_sha256": commit_sha,
        "parent_sha256": parent_sha,
    }


__all__ = ["run_cpo_schedule"]
