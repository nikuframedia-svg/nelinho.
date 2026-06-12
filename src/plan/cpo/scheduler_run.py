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

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
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
from src.shared.time import utc_now_naive

logger = logging.getLogger(__name__)

# Q.126.E — above this share of ops on the 2x synthetic buffer the plan is
# marked `degraded` and a WARN CopilotAlert is emitted (soft-warn: the plan is
# still returned). Conservative default; the operator decides.
_DURATION_FALLBACK_ALERT_THRESHOLD = 0.20

# Q.162.B — guarda anti-plano-degenerado. Um plano minúsculo face ao scope (ex.:
# falha transitória do solver, regressão de dados) NUNCA deve virar o "plano
# atual" no grid só por ser o mais recente. Marca-se `cpo_meta.degenerate=true`
# (jsonb, NÃO entra no hash) e o /overall salta-o (mostra o último SAUDÁVEL). Só
# dispara quando o scope é GRANDE (planos pequenos intencionais — request com
# `orders` explícito — não são degenerados) E a cobertura é baixa. Honesto
# (invariante #8): se TODOS forem degenerados → empty-state, nunca um plano falso.
_DEGENERATE_MIN_SCOPE = 50         # só guarda quando havia muitas ordens a planear
_DEGENERATE_COVERAGE_FLOOR = 0.50  # < 50% das ordens planeadas = suspeito


def _due_date_coverage(operations) -> Dict[str, Any]:
    """Q.168.A — cobertura de due dates REAIS no scope planeado.

    Conta ORDENS (não ops): uma ordem tem due se ≥1 op transporta due_date.
    Observabilidade/auditoria no cpo_meta (não entra no hash) — é o medidor
    de quantas ordens o backward-scheduling/tardiness consegue honrar. A
    auditoria 2026-06-10 apanhou o loader a deixar cair o campo; este medidor
    torna uma regressão futura visível num relance."""
    orders = {op.order_id for op in operations}
    with_due = {
        op.order_id for op in operations if getattr(op, "due_date", None)
    }
    total = len(orders)
    return {
        "orders_with_due": len(with_due),
        "orders_total": total,
        "pct": round(100.0 * len(with_due) / total, 1) if total else 0.0,
    }


def _is_degenerate_plan(scope_size: int, orders_coverage: float) -> bool:
    """Q.162.B — plano degenerado: scope GRANDE (≥ _DEGENERATE_MIN_SCOPE) mas a
    cobertura colapsou (< _DEGENERATE_COVERAGE_FLOOR). Pura → testável isolada.
    Planos pequenos intencionais (request com `orders` explícito, scope < mínimo)
    nunca são degenerados."""
    return (
        scope_size >= _DEGENERATE_MIN_SCOPE
        and orders_coverage < _DEGENERATE_COVERAGE_FLOOR
    )


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

    now = utc_now_naive()
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
    (Blueprint v2.0). Flags use_* ficam nos defaults do engine, EXCETO os
    deliberadamente expostos à configuração de tenant: `cpo.use_cpsat_global`
    (Q.166.F) e `cpo.use_queue_time` (Q.173.L)."""
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

    def _bool(key: str, fallback: bool) -> bool:
        if key not in planning:
            return bool(fallback)
        v = planning[key]
        if isinstance(v, str):
            return v.strip().lower() in ("1", "true", "yes", "on")
        return bool(v)

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
    ga_budget = _num("cpo.ga_budget_s", base.ga_budget_s)
    total_budget = _num("cpo.total_budget_s", base.total_budget_s)
    # Q.161.B — caller pede mais tempo que o ga_budget (ex. robô de fundo a pedir
    # 600s para planear os ~1200 em-produção, não-interativo): alarga ga_budget E
    # total_budget para o acomodar. Senão o CPOConfig.__post_init__ corta o
    # time_limit_sec de volta para o ga_budget (120s) e o pedido não tem efeito.
    # Interativo (tlim=120 default ≤ ga 120) fica intacto — só alarga quando >.
    if tlim > ga_budget:
        total_budget += tlim - ga_budget
        ga_budget = tlim
    # Q.166.F — otimizador global CP-SAT. Quando ON, o CP-SAT usa o orçamento de
    # tempo PRINCIPAL (tlim, ex. robô 300-600s) porque SUBSTITUI a GA — o
    # cpsat_budget_s de 15s era só para o L-RHO refiner (não-usado).
    use_cpsat_global = _bool("cpo.use_cpsat_global", base.use_cpsat_global)
    cpsat_budget = (
        tlim if use_cpsat_global else _num("cpo.cpsat_budget_s", base.cpsat_budget_s)
    )
    return CPOConfig(
        population_size=pop,
        generations=gens,
        time_limit_sec=tlim,
        total_budget_s=total_budget,
        greedy_budget_s=_num("cpo.greedy_budget_s", base.greedy_budget_s),
        ga_budget_s=ga_budget,
        mapelites_budget_s=_num("cpo.mapelites_budget_s", base.mapelites_budget_s),
        cpsat_budget_s=cpsat_budget,
        workforce_budget_s=_num("cpo.workforce_budget_s", base.workforce_budget_s),
        use_cpsat_global=use_cpsat_global,
        cpsat_num_workers=int(_num("cpo.cpsat_num_workers", base.cpsat_num_workers)),
        cpsat_deterministic=_bool("cpo.cpsat_deterministic", base.cpsat_deterministic),
        # Q.173.P — isenção dos guardrails soft do gate (decisão Luis).
        cpsat_gate_soft_waiver_gain=_num(
            "cpo.cpsat_gate.soft_waiver_gain", base.cpsat_gate_soft_waiver_gain,
        ),
        # Q.173.L — one-piece-flow configurável: fila inter-fase mediana
        # (True, default) vs fila=0 (False). Antes só mudável em código.
        use_queue_time=_bool("cpo.use_queue_time", base.use_queue_time),
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
    horizon_start = utc_now_naive()
    horizon_end = horizon_start + timedelta(days=request.horizon_days)

    # Q.161.A — o request decide o horizonte: None (interativo)=200, 0=todos os
    # em-produção (robô de fundo). `getattr` p/ back-compat com requests antigos.
    state = await FactoryState.load(
        session, tenant_id, plan_cap=getattr(request, "plan_cap", None),
    )
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
    # Q.153.C1 — honrar exclusões também quando os orders vêm explícitos no
    # request (o filtro de state.load() só cobre state.open_orders).
    if state.excluded_order_ids:
        orders = [
            o for o in orders
            if str(
                (o.get("order_id") or o.get("of_id"))
                if isinstance(o, dict)
                else (getattr(o, "order_id", None) or getattr(o, "of_id", ""))
            ) not in state.excluded_order_ids
        ]
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
            # flush() removido: _upsert_cpo_alert já faz commit() interno (Q.138.I)
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
            # flush() removido: _upsert_cpo_alert já faz commit() interno (Q.138.I)
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
            # Q.168.C (ressalva do reviewer) — "rota_concluida" NÃO é falta de
            # rota: a ordem tem a rota toda feita no ERP. Misturá-las na mesma
            # frase enganava o operador.
            n_done = sum(
                1 for u in resolver.unplanned if u["reason"] == "rota_concluida"
            )
            n_no_route = len(unplanned_ids) - n_done
            done_part = (
                f" e {n_done} já têm a rota concluída no ERP (nada a planear)"
                if n_done else ""
            )
            await _upsert_cpo_alert(
                session, tenant_id,
                code=CODE_ORDERS_WITHOUT_ROUTING,
                title=f"{len(unplanned_ids)} ordens fora do plano",
                message_pt=(
                    f"{n_no_route} ordens não têm rota conhecida (sem "
                    "histórico real nem template de routing no ERP)"
                    f"{done_part}. Fora do plano: {preview}{more}. Cobertura: "
                    f"{coverage_pct}%. Para planear as sem-rota é preciso "
                    "histórico de produção ou um template para esses modelos."
                ),
                context={
                    "unplanned_count": len(unplanned_ids),
                    "unplanned_orders": unplanned_ids[:50],
                    "orders_coverage": round(resolver.orders_coverage, 4),
                    "reasons": sorted({u["reason"] for u in resolver.unplanned}),
                },
            )
            # flush() removido: _upsert_cpo_alert já faz commit() interno (Q.138.I)
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

    # Q.173.S — boosts ANTES do solve: prioridade de cliente/ordem/barco passa
    # a reordenar o priority_order do decoder (Q.116.D) em todos os caminhos
    # greedy/GA — antes era recolhida PÓS-solve e servia só de badge no
    # frontend (auditoria 2026-06-11). O snapshot é reutilizado no commit
    # (entra no sha + coluna boost_inputs_snapshot — zero queries duplicadas).
    boost_snapshot: Dict[str, Any] = {}
    try:
        from src.plan.api._cpo_common import _collect_boost_inputs

        boost_snapshot = await _collect_boost_inputs(
            session, tenant_id,
            [{"order_id": getattr(op, "order_id", None)} for op in operations],
        )
    except Exception as snap_exc:  # noqa: BLE001  # boost é opcional: snapshot falhado não trava o solve
        logger.warning(f"boost snapshot failed: {snap_exc}", exc_info=True)
    boost_map: Dict[str, int] = {
        str(lid): int(comp.get("effective", 0) or 0)
        for lid, comp in boost_snapshot.items()
        if int(comp.get("effective", 0) or 0)
    }

    # Q.169.E — o solve é CPU-bound e SÍNCRONO (greedy+GA em Python; CP-SAT
    # em C++ que LIBERTA o GIL): corrê-lo inline bloqueava o event loop até
    # 600s — /health não respondia e o SSE morria durante cada replan. Em
    # thread, o loop fica livre (totalmente durante o CP-SAT; nos troços
    # Python do GA o GIL alterna). engine.schedule é auto-contido (estado
    # Q.174.F6 — `materials.delay_to_eta` (opt-in, default OFF): ordens cujo
    # material em défice tem encomenda ABERTA com ETA ganham PISO = ETA na 1ª
    # op (decisão do dono: constraint soft; o atraso só se aplica quando há
    # chegada prevista — sem encomenda, fica só o risco anotado). O forecast
    # corre sobre o commit ANTERIOR (a procura ordem×BOM quase não muda entre
    # commits; two-pass do solver seria custo desproporcionado).
    start_floors: Optional[Dict[str, datetime]] = None
    try:
        from src.core.services.tenant_config_service import TenantConfigService
        _mat_cfg = await TenantConfigService(session, tenant_id).get_category(
            "planning"
        )
        _delay_on = str(_mat_cfg.get("materials.delay_to_eta") or "").lower() in (
            "true", "1", "yes",
        ) or _mat_cfg.get("materials.delay_to_eta") is True
    except Exception:  # pragma: no cover — config indisponível
        _delay_on = False
    if _delay_on:
        try:
            from src.supply.services.shortage_forecast_service import (
                ShortageForecastService,
            )
            _fc = await ShortageForecastService(session, tenant_id).forecast()
            # ETA usável = data-limite de encomenda do material em défice
            # (calculada do lead time real). Por ordem afetada, o piso é a
            # MAIOR data-limite dos seus materiais em risco.
            _eta_by_order: Dict[str, datetime] = {}
            for _m in _fc.materiais_em_risco:
                _eta = _m.data_limite_encomenda
                if _eta is None:
                    continue
                _dt = datetime.combine(_eta, datetime.min.time())
                for _oa in _m.ordens_afetadas:
                    cur = _eta_by_order.get(str(_oa.order_id))
                    if cur is None or _dt > cur:
                        _eta_by_order[str(_oa.order_id)] = _dt
            if _eta_by_order:
                first_op_by_order: Dict[str, Any] = {}
                for _op in operations:
                    k = str(_op.order_id)
                    cur_op = first_op_by_order.get(k)
                    if cur_op is None or int(
                        getattr(_op, "sequence", 0) or 0
                    ) < int(getattr(cur_op, "sequence", 0) or 0):
                        first_op_by_order[k] = _op
                start_floors = {}
                for k, dt in _eta_by_order.items():
                    fop = first_op_by_order.get(k)
                    if fop is not None and dt > horizon_start:
                        start_floors[str(fop.operation_id)] = dt
                start_floors = start_floors or None
                if start_floors:
                    logger.info(
                        "Q.174.F6 delay_to_eta: %d ops com piso de material",
                        len(start_floors),
                    )
        except Exception as exc:  # pragma: no cover — forecast nunca trava o solve
            logger.warning("delay_to_eta forecast falhou (%s) — sem pisos", exc)
            start_floors = None

    # em memória, zero sessões/loop por dentro) → thread-safe aqui.
    result = await asyncio.to_thread(
        engine.schedule,
        operations, machines, horizon_start, horizon_end,
        product_price_eur=product_price_eur,
        boost_inputs=boost_map or None,
        start_floors=start_floors,
    )
    if start_floors:
        result.setdefault("cpo_meta", {})["material_floors"] = {
            "ops_com_piso": len(start_floors),
        }

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

    # Q.174.F5 — secção "NÃO PLANEÁVEL" unificada (decisão do dono 2026-06-12:
    # plano parcial + secção inviável — nunca silêncio, nunca plano falso).
    # Junta as razões estruturadas do decoder (blocked → result["unplannable"]:
    # operadores/molde/horizonte/precedência) com as ordens SEM_ROTA do
    # resolver. O caminho CP-SAT agenda tudo no post-pass, por isso as suas
    # entradas vêm daqui. Detalhe no cpo_meta (fora do hash, cap 200).
    from src.plan.cpo import op_status as _op_status
    _unplannable: List[Dict[str, Any]] = list(result.get("unplannable") or [])
    for _u in resolver.unplanned:
        if str(_u.get("reason")) == "rota_concluida":
            continue  # rota concluída = nada por planear, não é bloqueio
        _unplannable.append({
            "operation_id": None,
            "order_id": str(_u["order_id"]),
            "phase_id": None,
            "status": _op_status.SEM_ROTA,
            "missing": {"reason": str(_u.get("reason") or "")},
        })
    if _unplannable:
        from src.plan.cpo.unplannable_suggestions import enrich_unplannable
        _unplannable = enrich_unplannable(_unplannable, state)
    result["unplannable"] = _unplannable
    if _unplannable:
        result.setdefault("cpo_meta", {})["unplannable"] = _unplannable[:200]

    # Q.174.F6 — anotação de RISCO DE MATERIAL no plano em construção
    # (decisão do dono: constraint soft — o plano agenda na mesma, mas marca
    # ops/barcos em risco com material/data/sugestão). Corre o forecast sobre
    # as ops DESTE plano (forecast(ops=...)); best-effort — nunca trava o solve.
    try:
        from src.supply.services.shortage_forecast_service import (
            ShortageForecastService as _SFS,
        )
        _fc2 = await _SFS(session, tenant_id).forecast(
            ops=list(result.get("operations") or []),
        )
        _risk_by_order: Dict[str, list] = {}
        for _m in _fc2.materiais_em_risco:
            for _oa in _m.ordens_afetadas:
                _risk_by_order.setdefault(str(_oa.order_id), []).append({
                    "product_code": _m.product_code,
                    "product_name": _m.product_name,
                    "data_rutura": (
                        _m.data_rutura_prevista.isoformat()
                        if _m.data_rutura_prevista else None
                    ),
                    "data_limite_encomenda": (
                        _m.data_limite_encomenda.isoformat()
                        if _m.data_limite_encomenda else None
                    ),
                    "sugestao": _m.sugestao,
                })
        if _risk_by_order:
            _n_ops_risco = 0
            for _opd in result.get("operations") or []:
                _r = _risk_by_order.get(str(_opd.get("order_id") or ""))
                if _r:
                    _opd["material_risk"] = True
                    _opd["material_risk_detail"] = _r[:3]
                    _n_ops_risco += 1
            result.setdefault("cpo_meta", {})["material_risk"] = {
                "orders_em_risco": len(_risk_by_order),
                "ops_marcadas": _n_ops_risco,
                "materiais": len(_fc2.materiais_em_risco),
            }
            result["orders_material_risk"] = len(_risk_by_order)
    except Exception as exc:  # pragma: no cover — forecast nunca trava o plano
        logger.warning("material_risk annotation falhou (%s)", exc)

    # Q.168.A — observabilidade dos due dates: quantas ordens do scope têm
    # data-alvo real (só essas o backward-scheduling/tardiness honram).
    result.setdefault("cpo_meta", {})["due_date_coverage"] = (
        _due_date_coverage(operations)
    )

    # Q.162.B — guarda anti-plano-degenerado. Quando o scope era grande mas a
    # cobertura colapsou (falha transitória do solver / regressão de dados), marca
    # o commit `cpo_meta.degenerate=true` para o /overall NÃO o mostrar como plano
    # atual (mantém o último saudável). Persiste na mesma (auditoria); cpo_meta
    # não entra no hash. Não levanta erro — soft-flag, honesto (invariante #8).
    _scope_size = len(orders)
    _planned_orders = len(resolver.planned_order_ids)
    _is_degenerate = _is_degenerate_plan(_scope_size, resolver.orders_coverage)
    result.setdefault("cpo_meta", {}).update(
        {
            "degenerate": bool(_is_degenerate),
            "orders_coverage": round(resolver.orders_coverage, 4),
            "planned_orders": _planned_orders,
            "scope_size": _scope_size,
        }
    )
    if _is_degenerate:
        cov_pct = round(resolver.orders_coverage * 100.0, 1)
        msg = (
            f"Plano DEGENERADO: só {_planned_orders}/{_scope_size} ordens planeadas "
            f"(cobertura {cov_pct}%, mínimo {int(_DEGENERATE_COVERAGE_FLOOR * 100)}%). "
            "Não será mostrado como plano atual — mantém-se o último plano saudável."
        )
        result.setdefault("warnings", []).append(msg)
        logger.warning("CPO schedule: %s (tenant=%s)", msg, tenant_id)
        try:
            from src.copilot.alerts.models import CODE_PLAN_DEGENERATE
            await _upsert_cpo_alert(
                session, tenant_id,
                code=CODE_PLAN_DEGENERATE,
                title=f"Plano degenerado — só {_planned_orders}/{_scope_size} ordens",
                message_pt=msg,
                context={
                    "planned_orders": _planned_orders,
                    "scope_size": _scope_size,
                    "orders_coverage": round(resolver.orders_coverage, 4),
                },
            )
            # flush() removido: _upsert_cpo_alert já faz commit() interno (Q.138.I)
        except (SQLAlchemyError, ImportError, TypeError, ValueError) as alert_exc:
            logger.warning("CPO schedule: failed to emit degenerate alert: %s", alert_exc)

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

    # Q.168.C/Q.173.S — o snapshot dos boosts foi recolhido ANTES do solve
    # (ver acima): aqui entra no sha (reprodutibilidade do replay) e na
    # coluna boost_inputs_snapshot, e alimenta o attach pós-commit.

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
            boost_inputs_snapshot=boost_snapshot,
            # Q.169.B — validação ESTRUTURAL completa (cura/skills/pares
            # precisam do state). Erros = sem commit (o /overall mantém o
            # último plano saudável — padrão Q.162.B).
            validation_state=state,
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

        # Q.168.C — reutiliza o snapshot que entrou no hash do commit; {}→None
        # recalcula (resiliência se a recolha falhou transitoriamente).
        await _attach_effective_boost(
            session, tenant_id, operations_out, snapshot=boost_snapshot or None,
        )
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
        # Q.153.A2 — dívida herdada vs atraso novo/evitável.
        "num_already_overdue": int(result.get("num_already_overdue", 0)),
        "num_newly_late": int(result.get("num_newly_late", 0)),
        "tardiness_beyond_today_h": float(result.get("tardiness_beyond_today_h", 0.0)),
        "setups": int(result.get("setups", 0)),
        "avg_utilization": float(result.get("avg_utilization", 0.0)),
        "safety_net_triggered": bool(result.get("safety_net_triggered", False)),
        "degraded": bool(result.get("degraded", False)),
        "fallback_reason": result.get("fallback_reason"),
        "cpo_meta": result.get("cpo_meta", {}),
        "operations": operations_out,
        "warnings": list(result.get("warnings", [])),
        "infeasible_op_ids": list(result.get("infeasible_op_ids", [])),
        # Q.174.F5 — secção "não planeável" (status + recurso em falta por
        # op/ordem) — plano parcial declarado, nunca silêncio.
        "unplannable": list(result.get("unplannable", [])),
        # Q.131.H — ordens sem rota (não planeadas) + cobertura, para o
        # frontend mostrar honestamente o que ficou de fora.
        "unplanned_orders": list(result.get("unplanned_orders", [])),
        "orders_coverage": float(result.get("orders_coverage", 1.0)),
        "commit_sha256": commit_sha,
        "parent_sha256": parent_sha,
    }


__all__ = ["run_cpo_schedule"]
