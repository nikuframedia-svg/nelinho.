"""Q.62.D.1 — Arq worker para o CPO scheduler.

Hoje `POST /v1/plan/cpo/schedule` bloqueia até `time_limit_sec` (default
30s, max 300s). Q.62.D move o cálculo para um Arq job que corre em
background; o endpoint passa a retornar 202 + `job_id` para polling.

ARQUITECTURA:
  * `cpo_schedule_job(ctx, request_dict, tenant_id_str, ...)` — job
    callable executado pelo worker. Reconstroi `CPOScheduleRequest`,
    abre uma DB session limpa, e invoca a mesma lógica que o endpoint
    sincrono original chamava.
  * `WorkerSettings` — configuração Arq (Redis URL via settings, lista
    de jobs, max_jobs, timeouts).

DEPLOYMENT (prod):
  Correr o worker num processo separado (systemd unit em
  `deploy/systemd/nelinho-arq.service`):

      arq src.plan.cpo.worker.WorkerSettings

DEV:
  Em terminal separado:
      $env:PYTHONPATH = "."; .\.venv\Scripts\python.exe -m arq src.plan.cpo.worker.WorkerSettings

Q.62.D.2 vai refactor o endpoint para enfileirar via `redis.enqueue_job`
em vez de chamar engine.schedule() sincronamente. Q.62.D.4 vai
introduzir `ScheduleCommit.status DRAFT|LIVE`.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from src.shared.config import settings

logger = logging.getLogger(__name__)


# ─── Job callable ────────────────────────────────────────────────────


async def cpo_schedule_job(
    ctx: dict,
    request_dict: dict[str, Any],
    tenant_id_str: str,
    user_id_str: str,
) -> dict[str, Any]:
    """Q.62.D.1 — corre o CPO scheduler em background.

    Args:
        ctx: Arq context dict (contém Redis pool, job_id, etc).
        request_dict: payload `CPOScheduleRequest.model_dump()`.
        tenant_id_str: tenant_id da request (string para serializar via Redis).
        user_id_str: user_id que disparou o job (audit).

    Returns:
        dict com o resultado do schedule (mesmo shape de `CPOScheduleResponse`
        modulo `tenant_id`). Em Q.62.D.2 o endpoint converte para CommitSha
        e o polling endpoint serve o commit completo.

    Q.62.D.1 entrega o scaffolding — invocacao concreta do engine.schedule()
    fica para Q.62.D.2 quando o endpoint fizer extraccao do body para
    `run_cpo_schedule_sync(session, tenant_id, request)`. Por agora este
    job é stub que log + raise para sinalizar.
    """
    from src.plan.api.cpo import CPOScheduleRequest
    from src.shared.auth.tenant_context import tenant_scope

    tenant_id = UUID(tenant_id_str)
    request = CPOScheduleRequest(**request_dict)

    logger.info(
        "cpo_schedule_job started: job_id=%s tenant=%s user=%s "
        "horizon_days=%d time_limit=%.1fs",
        ctx.get("job_id"),
        tenant_id,
        user_id_str,
        request.horizon_days,
        request.time_limit_sec,
    )

    # Q.62.D.2 — extrair body de schedule_cpo para
    # `src/plan/cpo/scheduler_run.py:run_cpo_schedule` e chamar aqui:
    #
    #     from src.shared.database import get_session_context
    #     async with get_session_context() as session:
    #         result = await run_cpo_schedule(session, tenant_id, request)
    #     return result
    #
    # Por agora (D.1 scaffolding) levantamos para forçar D.2:
    with tenant_scope(tenant_id):  # noqa: F841  - smoke that ContextVar wires
        raise NotImplementedError(
            "Q.62.D.1: scaffolding only. Q.62.D.2 extrai o body de "
            "schedule_cpo e wire o engine.schedule() aqui."
        )


# ─── Worker settings ─────────────────────────────────────────────────


class WorkerSettings:
    """Arq worker settings — invocado via `arq src.plan.cpo.worker.WorkerSettings`."""

    # Lista de jobs que o worker aceita.
    functions = [cpo_schedule_job]

    # Conexao Redis — reusa a URL configurada via env (settings.redis_url).
    # Arq aceita `RedisSettings(host, port, ...)` ou uma string url.
    from arq.connections import RedisSettings as _RS

    redis_settings = _RS.from_dsn(settings.redis_url)

    # Q.62.D — CPO é heavy (~30s default, max 300s); permitimos jobs
    # longos com timeout generoso.
    job_timeout = 600  # 10 min hard cap (acima do time_limit_sec max=300)
    keep_result = 3600  # mantem o resultado em Redis por 1h (polling)
    max_jobs = 4  # paralelismo modesto — CPO usa cpu+memory pesado

    # Health-check key — Arq escreve heartbeat aqui.
    health_check_key = "arq:nelinho:cpo:health"

    # Log level — vem de settings.
    log_results = True


__all__ = ["WorkerSettings", "cpo_schedule_job"]
