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
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.cpo.commits import CommitsService, ScheduleCommit
from src.plan.cpo.engine import CPOConfig, CPOv4Engine
from src.plan.cpo.fitness import FitnessConfig
from src.plan.cpo.state import FactoryState
from src.plan.engines.scheduling_adapter import SchedulingMachine
from src.plan.services.routing_resolver import RoutingResolver

logger = logging.getLogger(__name__)

# Q.126.E — above this share of ops on the 2x synthetic buffer the plan is
# marked `degraded` and a WARN CopilotAlert is emitted (soft-warn: the plan is
# still returned). Conservative default; the operator decides.
_DURATION_FALLBACK_ALERT_THRESHOLD = 0.20


async def _upsert_cpo_alert(
    session: AsyncSession,
    tenant_id: UUID,
    code: str,
    title: str,
    message_pt: str,
    context: Dict[str, Any],
    severity: str = "WARN",
) -> None:
    """Q.138.I — upsert CPO alert via INSERT ... ON CONFLICT DO UPDATE.

    Usa o unique partial index (tenant_id, code) WHERE status='active'
    (migração 069) para dedup a nível de BD. Elimina a race-condition do
    SELECT-then-INSERT anterior (Q.138.G) que falhava quando a transacção
    da sessão não tinha ainda visto o flush anterior.
    """
    from sqlalchemy import text as _text
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from src.copilot.alerts.models import CopilotAlert

    now = datetime.utcnow()
    stmt = (
        pg_insert(CopilotAlert)
        .values(
            id=__import__("uuid").uuid4(),
            tenant_id=tenant_id,
            severity=severity,
            code=code,
            title=title,
            message_pt=message_pt,
            context=context,
            entity_refs=[],
            status="active",
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=["tenant_id", "code"],
            index_where=_text("status = 'active'"),
            set_={
                "title": title,
                "message_pt": message_pt,
                "context": context,
                "severity": severity,
                "updated_at": now,
            },
        )
    )
    await session.execute(stmt)
    # Q.138.I — commit explícito: session.execute de statement raw não marca
    # session.new/dirty, por isso get_session/get_session_context não chamam
    # commit() automaticamente. Mesmo padrão do CommitsService (Q.133.A.1).
    await session.commit()


async def _parent_sha(service: CommitsService, commit: ScheduleCommit) -> Optional[str]:
    if commit.parent_id is None:
        return None
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


# Q.132.A — defaults do schema CPOScheduleRequest. Quando o request traz
# exactamente o default, tratamo-lo como "não especificado" e deixamos a
# Configuração (tenant_configuration categoria 'planning') controlar o motor —
# é assim que os controlos da página de Configurações passam a mandar de facto.
# Um caller que peça explicitamente um valor diferente continua a ganhar.
# Q.138.D — alinhado com CPOScheduleRequest.generations default=200 (Blueprint v2.0 §5.5).
_REQ_DEFAULT_POP_SIZE = 100
_REQ_DEFAULT_GENERATIONS = 200
# Q.138.D — alinhado com CPOScheduleRequest.time_limit_sec default=120.
_REQ_DEFAULT_TIME_LIMIT_S = 120.0


async def _build_cpo_config(
    session: AsyncSession, tenant_id: UUID, request: Any,
) -> CPOConfig:
    """Constrói o CPOConfig a partir da Configuração do tenant (categoria
    'planning': cpo.gen_count / cpo.total_budget_s / cpo.pop_size + sub-budgets),
    com os campos do request a sobrepor só quando diferem do default do schema.
    Best-effort: sem config / sem session → defaults canónicos do CPOConfig
    (Blueprint v2.0). NÃO mexe nos flags use_* (ficam nos defaults do engine —
    evita divergências de seeds)."""
    planning: dict[str, Any] = {}
    try:
        from src.core.services.tenant_config_service import TenantConfigService
        planning = await TenantConfigService(session, tenant_id).get_category(
            "planning",
        )
    except (SQLAlchemyError, ImportError, ValueError) as exc:  # sem config = defaults
        logger.debug("CPOConfig: planning config indisponível (%s); defaults", exc)

    base = CPOConfig()  # defaults canónicos Blueprint v2.0

    def _num(key: str, fallback: float) -> float:
        try:
            return float(planning[key]) if key in planning else float(fallback)
        except (TypeError, ValueError):
            return float(fallback)

    pop = (
        request.population_size
        if request.population_size != _REQ_DEFAULT_POP_SIZE
        else int(_num("cpo.pop_size", base.population_size))
    )
    gens = (
        request.generations
        if request.generations != _REQ_DEFAULT_GENERATIONS
        else int(_num("cpo.gen_count", base.generations))
    )
    tlim = (
        request.time_limit_sec
        if request.time_limit_sec != _REQ_DEFAULT_TIME_LIMIT_S
        else _num("cpo.ga_budget_s", base.time_limit_sec)
    )
    return CPOConfig(
        population_size=pop,
        generations=gens,
        time_limit_sec=tlim,
        total_budget_s=_num("cpo.total_budget_s", base.total_budget_s),
        greedy_budget_s=_num("cpo.greedy_budget_s", base.greedy_budget_s),
        ga_budget_s=_num("cpo.ga_budget_s", base.ga_budget_s),
        mapelites_budget_s=_num("cpo.mapelites_budget_s", base.mapelites_budget_s),
        cpsat_budget_s=_num("cpo.cpsat_budget_s", base.cpsat_budget_s),
        workforce_budget_s=_num("cpo.workforce_budget_s", base.workforce_budget_s),
    )


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
            from src.copilot.alerts.models import CODE_ROUTING_ENGINE_UNAVAILABLE
            await _upsert_cpo_alert(
                session, tenant_id,
                code=CODE_ROUTING_ENGINE_UNAVAILABLE,
                title="Routing engine unavailable — schedule built on 2× buffer templates",
                message_pt=(
                    "O motor de routing não conseguiu aceder à camada curada "
                    "(factory_data_product). O scheduler caiu para os templates "
                    "FasesStandardModelos com buffer 2× — durações podem divergir "
                    "até 25× da realidade. Re-ingere os dados curados e volta a planear."
                ),
                context={"resolved_orders": len(orders)},
            )
            await session.flush()
        except Exception as alert_exc:
            logger.warning("CPO schedule: failed to emit routing alert: %s", alert_exc)

    # Q.126.E — noisy fallback: when too many ops fell back to the 2x synthetic
    # buffer (no real factory_raw history for the (fase, modelo) pair), warn
    # loudly and mark the plan degraded — but still RETURN it (soft-warn).
    duration_fallback_high = (
        resolver.fallback_fraction > _DURATION_FALLBACK_ALERT_THRESHOLD
    )
    if duration_fallback_high:
        try:
            from src.shared.metrics import bump_silent_fallback
            bump_silent_fallback("routing_resolver", "duration_2x_buffer_high")
        except ImportError:  # metrics best-effort (prometheus/metrics ausente)
            pass
        try:
            from src.copilot.alerts.models import CODE_DURATION_FALLBACK_HIGH
            pct = round(resolver.fallback_fraction * 100.0)
            await _upsert_cpo_alert(
                session, tenant_id,
                code=CODE_DURATION_FALLBACK_HIGH,
                title=f"Plano degradado — {pct}% das operações sem histórico real",
                message_pt=(
                    f"{pct}% das operações do plano caíram no buffer 2x sintético "
                    "porque não há histórico real (factory_raw.of_fp) para o par "
                    "(fase, modelo). As durações podem divergir muito da realidade "
                    "— sincroniza o ERP ou planeia modelos com histórico."
                ),
                context={
                    "fallback_ops": resolver.fallback_ops,
                    "resolved_ops": resolver.resolved_ops,
                    "fallback_fraction": round(resolver.fallback_fraction, 4),
                },
            )
            await session.flush()
        except (SQLAlchemyError, ImportError, TypeError, ValueError) as alert_exc:
            logger.warning(
                "CPO schedule: failed to emit duration-fallback alert: %s", alert_exc
            )

    # Q.131.H — honestidade: ordens sem rota nenhuma (sem histórico, sem
    # template do ERP) NÃO são saltadas em silêncio. Emite um alerta WARN com a
    # lista, para o operador saber exactamente o que ficou de fora (e porquê). O
    # plano com as restantes é devolvido na mesma — só "tudo falhou" dá 400.
    unplanned_ids = sorted({str(u["order_id"]) for u in resolver.unplanned})
    if unplanned_ids:
        coverage_pct = round(resolver.orders_coverage * 100.0, 1)
        try:
            from src.copilot.alerts.models import CODE_ORDERS_WITHOUT_ROUTING
            preview = ", ".join(unplanned_ids[:5])
            more = f" (+{len(unplanned_ids) - 5})" if len(unplanned_ids) > 5 else ""
            await _upsert_cpo_alert(
                session, tenant_id,
                code=CODE_ORDERS_WITHOUT_ROUTING,
                title=f"{len(unplanned_ids)} ordens sem rota — não planeadas",
                message_pt=(
                    f"{len(unplanned_ids)} ordens não têm rota conhecida (sem "
                    "histórico real nem template de routing no ERP) e ficaram "
                    f"FORA do plano: {preview}{more}. Cobertura do plano: "
                    f"{coverage_pct}%. Para as planear é preciso histórico de "
                    "produção ou um template de routing para esses modelos."
                ),
                context={
                    "unplanned_count": len(unplanned_ids),
                    "unplanned_orders": unplanned_ids[:50],
                    "orders_coverage": round(resolver.orders_coverage, 4),
                    "reasons": sorted({u["reason"] for u in resolver.unplanned}),
                },
            )
            await session.flush()
        except (SQLAlchemyError, ImportError, TypeError, ValueError) as alert_exc:
            logger.warning(
                "CPO schedule: failed to emit unplanned-orders alert: %s", alert_exc
            )

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
    elif state.phase_stations:
        # Q.133.B — N estações paralelas por fase (concorrência real) em vez do
        # pool "MANUAL" único → o decoder paraleliza ops da mesma fase. O molde
        # continua a serializar (mold_free_at); o decoder não é tocado.
        from src.plan.services.phase_workcenters import station_ids_for
        machines = [
            SchedulingMachine(
                machine_id=sid,
                name=f"Estação {sid}",
                capacity=1,
                speed_factor=1.0,
                centro_custo=str(fase),
            )
            for fase, n in sorted(state.phase_stations.items())
            for sid in station_ids_for(fase, n)
        ]
    else:
        machines = [SchedulingMachine(machine_id="MANUAL", name="Manual pool")]

    engine = CPOv4Engine(
        state=state,
        config=await _build_cpo_config(session, tenant_id, request),
        fitness_config=fitness_config,
    )

    product_price_eur = await _load_product_prices(session, tenant_id)

    result = engine.schedule(
        operations, machines, horizon_start, horizon_end,
        product_price_eur=product_price_eur,
    )

    # Q.138.E — honestidade: throughput_eur_day=0.0 é enganador quando não há
    # preços configurados em profit.product_pricing. Nesse caso expõe NULL no
    # cpo_meta e adiciona warning, sem inventar €. CoeficienteX nunca aqui.
    if not product_price_eur and result.get("throughput_eur_day", 0) == 0.0:
        result.setdefault("cpo_meta", {})["throughput_eur_day_status"] = (
            "sem_precos_configurados"
        )
        result.setdefault("warnings", []).append(
            "throughput_eur_day=0: sem preços configurados em profit.product_pricing "
            "— configure preços de venda para ver o KPI de faturação diária."
        )

    result.setdefault("cpo_meta", {}).update(ml_report.as_meta())

    # Q.126.E — surface the degraded state in the response. The response
    # schema already carries `degraded`/`fallback_reason` (read at the return
    # below); we OR our signal so we never clear an engine-set degraded flag.
    if duration_fallback_high:
        result["degraded"] = True
        result.setdefault("fallback_reason", "duration_2x_buffer_high")

    # Q.131.H — honestidade: expor as ordens deixadas FORA do plano (sem rota)
    # e a cobertura. Vai à resposta, aos warnings e ao cpo_meta (auditoria do
    # commit; cpo_meta não entra no hash). Ordenado p/ determinismo.
    result["unplanned_orders"] = unplanned_ids
    result["orders_coverage"] = round(resolver.orders_coverage, 4)
    if unplanned_ids:
        cov_pct = round(resolver.orders_coverage * 100.0, 1)
        result.setdefault("warnings", []).append(
            f"{len(unplanned_ids)} ordens sem rota não planeadas "
            f"(cobertura {cov_pct}%): {', '.join(unplanned_ids[:5])}"
            + (f" (+{len(unplanned_ids) - 5})" if len(unplanned_ids) > 5 else "")
        )
        result.setdefault("cpo_meta", {})["unplanned_orders"] = {
            "count": len(unplanned_ids),
            "orders": unplanned_ids[:50],
            "coverage": round(resolver.orders_coverage, 4),
        }

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
    except Exception as _yp_exc:
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
    except Exception as e:
        logger.warning(f"Schedule-as-Code commit failed: {e}", exc_info=True)

    # Q.116.G — após o commit ser gravado (hash determinístico), enriquece
    # cada op no payload com `effective_boost` para o frontend. Mutação
    # acontece DEPOIS do commit para o snapshot não mudar.
    operations_out: list[dict[str, Any]] = [
        dict(op) for op in result.get("operations", [])
    ]
    try:
        from src.plan.api._cpo_common import _attach_effective_boost

        await _attach_effective_boost(session, tenant_id, operations_out)
    except Exception as boost_exc:  # pragma: no cover — defensive
        logger.warning(
            f"effective_boost attach failed: {boost_exc}", exc_info=True
        )

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
        "operations": operations_out,
        "warnings": list(result.get("warnings", [])),
        "infeasible_op_ids": list(result.get("infeasible_op_ids", [])),
        # Q.131.H — ordens sem rota (não planeadas) + cobertura, para o
        # frontend mostrar honestamente o que ficou de fora.
        "unplanned_orders": list(result.get("unplanned_orders", [])),
        "orders_coverage": float(result.get("orders_coverage", 1.0)),
        "commit_sha256": commit_sha,
        "parent_sha256": parent_sha,
    }


__all__ = ["run_cpo_schedule"]
