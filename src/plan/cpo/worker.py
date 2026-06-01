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

    Q.62.D.2 — wire concreto: abre session limpa, set tenant_scope, e
    invoca `run_cpo_schedule(session, tenant_id, request)`. O dict
    retornado vai para o Arq result store (acessivel via polling em
    `GET /v1/plan/cpo/schedule/job/{job_id}`).
    """
    from src.plan.api.cpo import CPOScheduleRequest
    from src.plan.cpo.scheduler_run import run_cpo_schedule
    from src.shared.auth.tenant_context import tenant_scope
    from src.shared.database import get_session_context

    tenant_id = UUID(tenant_id_str)
    request = CPOScheduleRequest(**request_dict)

    # Q.132.G — regista o proponente no commit (author) para o write-gate poder
    # aplicar SoD (proposer ≠ approver). Só quando o caller não fixou um autor.
    if user_id_str and getattr(request, "author", "system") == "system":
        request.author = user_id_str

    logger.info(
        "cpo_schedule_job started: job_id=%s tenant=%s user=%s "
        "horizon_days=%d time_limit=%.1fs",
        ctx.get("job_id"),
        tenant_id,
        user_id_str,
        request.horizon_days,
        request.time_limit_sec,
    )

    with tenant_scope(tenant_id):
        async with get_session_context() as session:
            result = await run_cpo_schedule(session, tenant_id, request)

            # Q.142.D — re-aplicar os ajustes manuais (drag-drop) por cima do
            # DRAFT fresco para que "se aguentem" ao replan automático. O robô
            # planeia sozinho MAS respeita os moves do humano (revalidados pelos
            # axiomas Spelke; move inviável → alerta, nunca forçado). Best-effort:
            # falha aqui nunca derruba o job — o DRAFT do robô fica de pé.
            from sqlalchemy.exc import SQLAlchemyError

            try:
                from src.plan.services.manual_reorder import reapply_manual_overrides

                stats = await reapply_manual_overrides(session, tenant_id)
                if stats.get("reapplied") or stats.get("rejected"):
                    logger.info(
                        "cpo_schedule_job: overrides manuais reaplicados=%d "
                        "rejeitados=%d skipped=%d",
                        stats.get("reapplied", 0),
                        stats.get("rejected", 0),
                        stats.get("skipped", 0),
                    )
            except (SQLAlchemyError, RuntimeError, ValueError, OSError, ImportError) as exc:
                logger.warning(
                    "cpo_schedule_job: reapply de overrides manuais falhou (%s)", exc,
                )

    logger.info(
        "cpo_schedule_job complete: job_id=%s commit_sha=%s status=%s "
        "solve_time=%.2fs",
        ctx.get("job_id"),
        (result.get("commit_sha256") or "<none>")[:8],
        result.get("status"),
        result.get("solve_time_sec", 0.0),
    )
    return result


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
