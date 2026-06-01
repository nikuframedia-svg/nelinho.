"""src/app/startup.py — extracted startup sequence (Q.67.6.C2).

Holds the body of the `lifespan` startup phase that used to live inline in
`src/main.py`. The order of operations is load-bearing:

  1. structlog (so every log line below already lands as JSON in prod)
  2. OpenTelemetry tracing (must run BEFORE routes are touched so the
     auto-instrumentor catches every FastAPI hook)
  3. Sentry error reporting
  4. init_db (schema deps; everything else needs the DB)
  5. Redis + Kafka + tool_registry + YAML policy refresh — parallel via
     asyncio.gather(return_exceptions=True). One failure does not stall
     the others; degraded subsystems are appended to
     `app.state.degraded_subsystems` for /health/ready to surface.
  6. Background scheduler + factory watcher + ML retrain jobs
  7. RealtimeBridge + NOTIFY listener

Each step has its own try/except — startup never raises; it just logs a
warning and continues so a single hung subsystem cannot block the rest
of the backend coming up.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI

from src.shared.config import settings
from src.shared.database import init_db
from src.shared.kafka_client import get_producer
from src.shared.redis_client import get_redis
from src.shared.scheduler import start_scheduler

logger = logging.getLogger(__name__)

# Q.120.A — refs fortes às tasks de background. Sem isto o GC pode coletar a
# task a meio (RUF006); o done-callback liberta a ref quando ela termina.
_BACKGROUND_TASKS: set = set()


async def run_startup(app: FastAPI) -> None:
    """Execute the startup sequence. Mirrors the old inline body verbatim."""
    logger.info("Starting ProdPlan ONE...")

    # Q.61.37 — structlog setup. Idempotente; chamar antes de tudo
    # para que os logs subsequentes saiam ja estruturados.
    try:
        from src.shared.observability import configure_structlog

        # Dev usa ConsoleRenderer (legivel); prod JSON.
        configure_structlog(json_logs=not settings.is_development)
    except Exception as struct_error:
        logger.warning(f"structlog setup failed: {struct_error}")

    # Sprint Q.13.B (B1) — OpenTelemetry tracing setup. No-op when
    # OTEL_TRACES_EXPORTER is unset OR opentelemetry packages aren't
    # installed; logs the outcome either way. Must run BEFORE the rest
    # of startup so the auto-instrumentor catches subsequent
    # FastAPI route registration + DB connections.
    try:
        from src.shared.tracing import setup_tracing

        setup_tracing(app)
    except Exception as tracing_error:
        logger.warning(f"OTel setup failed: {tracing_error}")

    # Sprint Q.13.F F.4 — Sentry error reporting. Same graceful no-op
    # contract as tracing: when SENTRY_DSN is unset OR sentry-sdk
    # isn't installed, the call returns False and nothing is reported.
    # Pairs with OTel: tracing answers "where slowed", Sentry answers
    # "what raised, who, how often, with which release".
    try:
        from src.shared.error_reporting import setup_error_reporting

        setup_error_reporting()
    except Exception as sentry_error:
        logger.warning(f"Sentry setup failed: {sentry_error}")

    # Q.61.22 — track de subsistemas degradados para health endpoint expor.
    # Antes do Q.61.22 cada step do startup era sequencial; um Kafka lento
    # podia atrasar tudo. Agora init_db continua primeiro (deps de schema),
    # mas Redis + Kafka + tool registry + YAML refresh paralelizam com
    # asyncio.gather(return_exceptions=True).
    degraded_subsystems: list[str] = []
    app.state.degraded_subsystems = degraded_subsystems

    try:
        # 1) DB primeiro (deps de schema para tudo o resto).
        try:
            await init_db()
            logger.info("Database initialized")
        except Exception as db_error:
            logger.warning(f"Database connection failed: {db_error}")
            logger.warning(
                "Backend iniciado SEM base de dados. Algumas funcionalidades estarão limitadas."
            )
            logger.warning("Para usar o COPILOT completo, inicia o PostgreSQL.")
            degraded_subsystems.append("database")

        # 2) Subsistemas paralelizaveis (Q.61.22). asyncio.gather com
        # return_exceptions=True garante que um Kafka caido nao atrasa o
        # Redis nem o YAML refresh.

        async def _init_redis():
            await get_redis()

        async def _init_kafka():
            if settings.is_development:
                return  # dev nao precisa de producer obrigatorio
            await get_producer()

        async def _warm_tool_registry():
            from src.copilot.tool_registry import get_tool_registry

            await get_tool_registry()

        async def _refresh_yaml_policy():
            from src.governance.yaml_policy.runtime import startup_refresh
            from src.shared.database import async_session_factory

            async with async_session_factory() as _session:
                count = await startup_refresh(_session)
            logger.info(f"YAML policy engine warmed: {count} active rules")

        parallel_steps = [
            ("redis", _init_redis()),
            ("kafka", _init_kafka()),
            ("tool_registry", _warm_tool_registry()),
            ("yaml_policy", _refresh_yaml_policy()),
        ]
        results = await asyncio.gather(
            *(coro for _, coro in parallel_steps),
            return_exceptions=True,
        )
        for (name, _), result in zip(parallel_steps, results):
            if isinstance(result, Exception):
                logger.warning(f"{name} startup failed: {result}")
                degraded_subsystems.append(name)
            else:
                logger.info(f"{name} ready")

        # Start background scheduler (alerts scan + daily feedback).
        # In production, list active tenants here from the DB; for dev we start
        # empty and endpoints can register tenants via register_tenant().
        scheduler_instance = None
        try:
            scheduler_instance = start_scheduler(tenants=None)
        except Exception as sched_error:
            logger.warning(f"Scheduler failed to start: {sched_error}")

        # Factory data watcher — no-op unless PRODPLAN_FACTORY_FILE is set
        if scheduler_instance is not None:
            try:
                from src.factory_data_product.watcher import register_with_scheduler

                register_with_scheduler(scheduler_instance)
            except Exception as watcher_error:
                logger.warning(f"Factory watcher registration failed: {watcher_error}")

            # ML retrain jobs — load active tenant ids from DB so retrain
            # jobs actually run in production (FASE 0.1, DEVA-03).
            try:
                from src.core.models.tenant import TenantStatus
                from src.core.services.tenant_service import TenantService
                from src.ml.jobs.scheduling import register_ml_retrain_jobs
                from src.shared.database import get_session_context

                active_tenant_ids: list = []
                try:
                    async with get_session_context() as ml_session:
                        ts = TenantService(ml_session)
                        active = await ts.list_tenants(status=TenantStatus.ACTIVE, limit=1000)
                        active_tenant_ids = [t.id for t in active]
                except Exception as tenant_lookup_error:
                    logger.warning(
                        "ML retrain: could not load active tenants (%s) — jobs stay dormant",
                        tenant_lookup_error,
                    )
                register_ml_retrain_jobs(scheduler_instance, tenants=active_tenant_ids)

                # Q.149.B — jobs por-tenant (afinidade operador/fase @03:30,
                # shortage, quality scoring, mold health, preference detector)
                # só são agendados por register_tenant. Sem isto a aba
                # "Operadores" do FaseSheet fica eternamente "sem dados" e o
                # auto_cpo_replan não tem tenant. Registar os tenants activos
                # da BD (mesma lista do ML retrain) — corrige dev E prod.
                from src.shared.scheduler import register_tenant as _register_tenant

                for _tid in active_tenant_ids:
                    try:
                        _register_tenant(_tid)
                    except Exception as _reg_err:  # noqa: BLE001
                        logger.warning(
                            "register_tenant falhou tid=%s (%s)", _tid, _reg_err
                        )
                if active_tenant_ids:
                    logger.info(
                        "register_tenant: %d tenant(s) — jobs por-tenant agendados",
                        len(active_tenant_ids),
                    )
            except Exception as ml_error:
                logger.warning(f"ML retrain job registration failed: {ml_error}")

        # Sprint D.1 — Realtime bridge (Kafka → SSE fan-out).
        # Graceful when Kafka is unavailable: bridge logs + stays unhealthy
        # so the /v1/realtime/events endpoint answers 503 instead of hanging.
        try:
            from src.shared.realtime import RealtimeBridge

            await RealtimeBridge.instance().start()
        except Exception as bridge_error:
            logger.warning(f"RealtimeBridge failed to start: {bridge_error}")

        # Sprint Q.14.B — Postgres LISTEN/NOTIFY listener for the
        # rule_firing channel. Pushes high-severity firings to SSE
        # within ~5ms. Same graceful contract as the bridge: if asyncpg
        # / Postgres is unreachable, push channel stays silent + Kafka
        # events still flow.
        try:
            from src.shared.realtime.notify_listener import start_notify_listener

            await start_notify_listener()
        except Exception as notify_error:
            logger.warning(f"NOTIFY listener failed to start: {notify_error}")

        # Q.115.D — Auto-propose listener: cria Decisions a partir de eventos Kafka.
        # Graceful: se Kafka não estiver disponível, apenas loga e continua.
        try:
            from src.plan.services.auto_propose import AutoProposeService, HANDLED_TOPICS
            from src.plan.services.auto_propose_cpo_runner import real_cpo_propose_runner
            from src.shared.database import async_session_factory

            # Q.117.B — runner CPO real (propose-only) em vez do noop. Cria um
            # commit real + enriquece sandbox_result com cost_delta (€ vs
            # baseline) e quality_risk (defect-ML). Degrada para proposta sem
            # schedule se o CPO não puder correr — nunca quebra o listener.
            _auto_propose_svc = AutoProposeService(
                session_factory=async_session_factory,
                cpo_engine_runner=real_cpo_propose_runner,
            )

            async def _auto_propose_consumer_task() -> None:
                """Task que consome 4 tópicos Kafka e despacha para AutoProposeService."""
                import json
                from aiokafka import AIOKafkaConsumer

                consumer = AIOKafkaConsumer(
                    *HANDLED_TOPICS,
                    bootstrap_servers=settings.kafka_bootstrap_servers,
                    group_id="auto_propose_q115d",
                    auto_offset_reset="latest",
                    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                )
                try:
                    await consumer.start()
                    logger.info("Q.115.D auto_propose consumer iniciado (tópicos: %s)", list(HANDLED_TOPICS))
                    async for msg in consumer:
                        try:
                            payload = msg.value or {}
                            await _auto_propose_svc.handle_event(
                                topic=msg.topic,
                                payload=payload,
                            )
                        except Exception as msg_err:
                            logger.warning("auto_propose: erro no processamento de mensagem: %s", msg_err)
                except Exception as consumer_err:
                    logger.warning("auto_propose consumer falhou: %s", consumer_err)
                finally:
                    try:
                        await consumer.stop()
                    except Exception as stop_err:
                        logger.debug("auto_propose consumer.stop falhou: %s", stop_err)

            # Lança a task em background; falha silenciosa (degraded_subsystems)
            if not settings.is_development:
                _t = asyncio.create_task(_auto_propose_consumer_task())
                _BACKGROUND_TASKS.add(_t)
                _t.add_done_callback(_BACKGROUND_TASKS.discard)
                logger.info("Q.115.D auto_propose consumer task iniciada")
            else:
                logger.info("Q.115.D auto_propose consumer desactivado em desenvolvimento (Kafka opcional)")
        except Exception as auto_propose_err:
            logger.warning(f"Q.115.D auto_propose startup failed: {auto_propose_err}")
            degraded_subsystems.append("auto_propose")

        logger.info("ProdPlan ONE started successfully")

    except Exception as e:
        logger.error(f"Startup failed: {e}")
        # Não fazer raise - permite iniciar mesmo com erros parciais
        logger.warning("Continuando com funcionalidades limitadas...")


async def run_shutdown() -> None:
    """Graceful shutdown wrapped by `lifespan` with a 30s budget.

    Sprint Q.13.B (B5) — drain outbox ONCE before Kafka closes, then tear
    down each subsystem in its own try/except so a single failure never
    blocks the rest. The 30s `asyncio.wait_for` upper bound is enforced
    by the caller in `lifespan.py`.
    """
    # Stop realtime bridge first — subscribers get a clean "None"
    # sentinel before the Kafka producer/consumer teardown races in.
    try:
        from src.shared.realtime import RealtimeBridge

        await RealtimeBridge.instance().stop()
    except Exception as bridge_error:
        logger.warning(f"RealtimeBridge shutdown failed: {bridge_error}")

    # Sprint Q.14.B — close the asyncpg LISTEN connection cleanly
    # so Postgres releases the backend slot.
    try:
        from src.shared.realtime.notify_listener import stop_notify_listener

        await stop_notify_listener()
    except Exception as notify_error:
        logger.warning(f"NOTIFY listener shutdown failed: {notify_error}")

    # Sprint Q.13.B B5 — final outbox drain. Best effort: when
    # Kafka or the DB is already wedged this just logs and moves
    # on. The existing periodic dispatcher would have caught
    # these on next boot anyway via the table; this just shortens
    # the visibility window.
    try:
        from src.shared.database import get_session_context
        from src.shared.kafka_client import get_producer
        from src.shared.outbox_dispatcher import OutboxDispatcher

        producer = await get_producer()
        if producer is not None:
            dispatcher = OutboxDispatcher(
                db_session_factory=get_session_context,
                kafka_producer=producer,
            )
            await dispatcher.run()
            logger.info("Outbox final drain ok")
    except Exception as outbox_error:
        logger.warning(f"Outbox final drain failed: {outbox_error}")

    try:
        from src.shared.scheduler import shutdown_scheduler

        await shutdown_scheduler()
    except Exception as sched_error:
        logger.warning(f"Scheduler shutdown failed: {sched_error}")

    try:
        from src.shared.database import close_db

        await close_db()
    except Exception as db_error:
        logger.warning(f"DB shutdown failed: {db_error}")

    try:
        from src.shared.redis_client import shutdown_redis

        await shutdown_redis()
    except Exception as redis_error:
        logger.warning(f"Redis shutdown failed: {redis_error}")

    try:
        from src.shared.kafka_client import shutdown_kafka

        await shutdown_kafka()
    except Exception as kafka_error:
        logger.warning(f"Kafka shutdown failed: {kafka_error}")

    # Sprint Q.13.B (B1) — flush OTel spans LAST so the trace for
    # this very shutdown sequence makes it to the collector before
    # the process exits. No-op when tracing wasn't active.
    try:
        from src.shared.tracing import shutdown_tracing

        shutdown_tracing()
    except Exception as tracing_error:
        logger.warning(f"OTel flush failed: {tracing_error}")
