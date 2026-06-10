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

import asyncio
import logging
import time
from typing import Any
from uuid import UUID

from src.shared.config import settings

logger = logging.getLogger(__name__)

# Q.169.E — intervalo do heartbeat de progresso do job. Sem heartbeat, um
# job pendurado (deadlock no load, solver preso) só era detetável quando o
# wall-clock de 1200s o matava — 20 min de silêncio total nos logs.
_HEARTBEAT_INTERVAL_S = 60.0

# Q.162.A — wall-clock máximo do job Arq. INVARIANTE: >> budget do solver do robô
# (_DEFAULT_ROBOT_TIME_LIMIT_S=300, em auto_cpo_replan_job) + overhead de load
# (~4s) + serialização de ~8k ops + trust_index + boost + reapply de overrides.
# Antes era 600 = o tecto _MAX_TIME_LIMIT_S = o time_limit do robô (Q.161.B) → o
# solver comia os 600s e o Arq matava o job ANTES de gravar o commit
# (CancelledError no asyncpg; _arq.err j_complete=0 j_failed=22), deixando o grid
# preso num plano degenerado. Medido live: 8209 ops carregam+resolvem+resolvem+
# gravam em ~168s → 1200s dá folga enorme. Coberto por test_q162_*.
_CPO_JOB_TIMEOUT_S = 1200


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

    # Q.169.E — heartbeat de progresso: com o solve em to_thread (Q.169.E em
    # scheduler_run) o event loop fica livre para isto correr DURANTE o
    # solve. Um job pendurado passa a ser visível nos logs minuto a minuto
    # em vez de 20 min de silêncio até ao wall-clock timeout.
    _hb_stop = asyncio.Event()
    _t0 = time.monotonic()

    async def _heartbeat() -> None:
        while not _hb_stop.is_set():
            try:
                await asyncio.wait_for(
                    _hb_stop.wait(), timeout=_HEARTBEAT_INTERVAL_S,
                )
            except asyncio.TimeoutError:
                logger.info(
                    "cpo_schedule_job vivo: job_id=%s %.0fs decorridos",
                    ctx.get("job_id"), time.monotonic() - _t0,
                )

    _hb_task = asyncio.create_task(_heartbeat())

    try:
        with tenant_scope(tenant_id):
            async with get_session_context() as session:
                result = await run_cpo_schedule(session, tenant_id, request)

                # Q.142.D — re-aplicar os ajustes manuais (drag-drop) por
                # cima do DRAFT fresco para que "se aguentem" ao replan
                # automático. O robô planeia sozinho MAS respeita os moves do
                # humano (revalidados pelos axiomas Spelke; move inviável →
                # alerta, nunca forçado). Best-effort: falha aqui nunca
                # derruba o job — o DRAFT do robô fica de pé.
                from sqlalchemy.exc import SQLAlchemyError

                try:
                    from src.plan.services.manual_reorder import (
                        reapply_manual_overrides,
                    )

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
    finally:
        _hb_stop.set()
        # Parachoque (ressalva do reviewer): se algum dia o Arq fizer cancel
        # múltiplo, o await do heartbeat nunca pendura o teardown do job.
        await asyncio.wait_for(_hb_task, timeout=5.0)

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


async def _worker_startup(ctx: dict) -> None:
    """Q.169.E — o processo arq nasce com root=WARNING e sem handler para os
    loggers da app: nem o "cpo_schedule_job started" nem o heartbeat "vivo"
    chegavam ao log (verificado live: 0 linhas INFO em _arq.err). basicConfig
    só instala handler se o root não tiver — idempotente."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger().setLevel(logging.INFO)


class WorkerSettings:
    """Arq worker settings — invocado via `arq src.plan.cpo.worker.WorkerSettings`."""

    # Lista de jobs que o worker aceita.
    functions = [cpo_schedule_job]

    # Q.169.E — logging INFO da app visível no processo do worker.
    on_startup = _worker_startup

    # Conexao Redis — reusa a URL configurada via env (settings.redis_url).
    # Arq aceita `RedisSettings(host, port, ...)` ou uma string url.
    from arq.connections import RedisSettings as _RS

    redis_settings = _RS.from_dsn(settings.redis_url)

    # Q.162.A — 20 min hard cap (folga sobre o solver do robô + persist). Ver a
    # constante _CPO_JOB_TIMEOUT_S acima para o invariante e a medição.
    job_timeout = _CPO_JOB_TIMEOUT_S
    keep_result = 3600  # mantem o resultado em Redis por 1h (polling)
    max_jobs = 4  # paralelismo modesto — CPO usa cpu+memory pesado

    # Health-check key — Arq escreve heartbeat aqui.
    health_check_key = "arq:nelinho:cpo:health"

    # Log level — vem de settings.
    log_results = True


__all__ = ["WorkerSettings", "cpo_schedule_job"]
